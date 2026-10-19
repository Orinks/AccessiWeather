//! Screen reader announcements through prism, like the Python app's
//! `ScreenReaderAnnouncer`: the best backend is acquired once, used only when
//! it reports `IS_SUPPORTED_AT_RUNTIME`, and text is spoken without
//! interrupting. Everything runs on the UI thread.

use std::cell::{Cell, RefCell};

use prismer::{Backend, BackendId, Features, Prism};

thread_local! {
    static BACKEND: RefCell<Option<Backend<'static>>> = const { RefCell::new(None) };
    static PRISM: Cell<Option<&'static Prism>> = const { Cell::new(None) };
    /// The system voice, used for scheduled readings when no screen reader runs.
    static VOICE: RefCell<Option<Backend<'static>>> = const { RefCell::new(None) };
}

/// System text-to-speech engines, best first, for when no screen reader runs.
#[cfg(windows)]
const SYSTEM_VOICES: [&str; 2] = ["OneCore", "SAPI"];
#[cfg(target_os = "macos")]
const SYSTEM_VOICES: [&str; 1] = ["AVSpeech"];
#[cfg(not(any(windows, target_os = "macos")))]
const SYSTEM_VOICES: [&str; 1] = ["SpeechDispatcher"];

fn prism() -> Option<&'static Prism> {
    if let Some(prism) = PRISM.with(Cell::get) {
        return Some(prism);
    }
    // The context lives for the whole process, as it does in the Python app.
    let prism: &'static Prism = match Prism::new() {
        Ok(p) => Box::leak(Box::new(p)),
        Err(e) => {
            tracing::debug!("prism not available; announcer will be a no-op: {e}");
            return None;
        }
    };
    PRISM.with(|p| p.set(Some(prism)));
    Some(prism)
}

/// Prism backends that are text-to-speech engines rather than screen readers.
const TTS_ENGINES: [BackendId; 7] = [
    BackendId::SAPI,
    BackendId::ONE_CORE,
    BackendId::AV_SPEECH,
    BackendId::SPEECH_DISPATCHER,
    BackendId::ANDROID_TTS,
    BackendId::WEB_SPEECH,
    BackendId::SPIEL,
];

/// The highest-priority screen reader that is running right now.
///
/// Not `acquire_best`: that ranks the OneCore and SAPI voices above
/// Narrator, and returns whatever backend is already cached before probing,
/// so a running Narrator was never used. Narrator's route (UIA) reports
/// runtime support whenever UI Automation exists, so it is only a candidate
/// while Narrator itself is running.
fn running_screen_reader(prism: &'static Prism) -> Option<Backend<'static>> {
    let mut ids = prism.backend_ids();
    ids.sort_by_key(|&id| std::cmp::Reverse(prism.backend_priority(id)));
    ids.into_iter()
        .filter(|id| !TTS_ENGINES.contains(id))
        .filter(|&id| id != BackendId::UIA || narrator_running())
        .find_map(|id| {
            let backend = prism.create(id).ok()?;
            backend.initialize().ok()?;
            backend
                .features()
                .contains(Features::IS_SUPPORTED_AT_RUNTIME)
                .then_some(backend)
        })
}

/// True when Windows Narrator is running.
#[cfg(windows)]
fn narrator_running() -> bool {
    use windows_sys::Win32::Foundation::{CloseHandle, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W,
        TH32CS_SNAPPROCESS,
    };

    // SAFETY: a plain Toolhelp32 walk. The snapshot handle is closed on every
    // path out, and `entry` is a zeroed PROCESSENTRY32W with `dwSize` set
    // before the first call, as the API requires.
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if snapshot.is_null() || snapshot == INVALID_HANDLE_VALUE {
            return false;
        }
        let mut entry: PROCESSENTRY32W = std::mem::zeroed();
        entry.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
        let mut found = Process32FirstW(snapshot, &mut entry) != 0;
        let mut running = false;
        while found {
            let len = entry
                .szExeFile
                .iter()
                .position(|&c| c == 0)
                .unwrap_or(entry.szExeFile.len());
            if String::from_utf16_lossy(&entry.szExeFile[..len])
                .eq_ignore_ascii_case("narrator.exe")
            {
                running = true;
                break;
            }
            found = Process32NextW(snapshot, &mut entry) != 0;
        }
        CloseHandle(snapshot);
        running
    }
}

#[cfg(not(windows))]
fn narrator_running() -> bool {
    false
}

/// Acquire the running screen reader's backend for this (UI) thread.
pub fn init() {
    let Some(prism) = prism() else { return };
    let Some(backend) = running_screen_reader(prism) else {
        tracing::debug!("No screen reader running");
        return;
    };
    tracing::info!("Screen reader backend active: {}", backend.name());
    BACKEND.with(|b| *b.borrow_mut() = Some(backend));
}

/// Speak `text` through the screen reader. No-op when none is available.
pub fn announce(text: &str) {
    if text.trim().is_empty() {
        return;
    }
    BACKEND.with(|b| {
        if let Some(backend) = b.borrow().as_ref() {
            if let Err(e) = backend.speak(text, false) {
                tracing::warn!("Failed to announce text: {e}");
            }
        }
    });
}

fn system_voice(prism: &'static Prism) -> Option<Backend<'static>> {
    SYSTEM_VOICES.iter().find_map(|name| {
        let id = prism.backend_id_by_name(name).ok()?;
        let backend = prism.create(id).ok()?;
        match backend.initialize() {
            Ok(()) => {
                tracing::info!("System voice for scheduled readings: {name}");
                Some(backend)
            }
            Err(e) => {
                tracing::debug!("System voice {name} unavailable: {e}");
                None
            }
        }
    })
}

/// Read `text` aloud: through the screen reader when one is running, or
/// else the system voice. Returns false when nothing could speak it.
pub fn speak_aloud(text: &str) -> bool {
    if text.trim().is_empty() {
        return false;
    }
    // A screen reader started after the app was opened is picked up here.
    if BACKEND.with(|b| b.borrow().is_none()) {
        init();
    }
    let spoken = BACKEND.with(|b| {
        b.borrow()
            .as_ref()
            .is_some_and(|backend| backend.speak(text, false).is_ok())
    });
    if spoken {
        return true;
    }
    let Some(prism) = prism() else { return false };
    VOICE.with(|v| {
        let mut voice = v.borrow_mut();
        if voice.is_none() {
            *voice = system_voice(prism);
        }
        match voice.as_ref().map(|backend| backend.speak(text, false)) {
            Some(Ok(())) => true,
            Some(Err(e)) => {
                tracing::warn!("System voice failed to speak: {e}");
                false
            }
            None => {
                tracing::warn!("No screen reader or system voice available to read aloud");
                false
            }
        }
    })
}

/// Release the backends before the UI thread winds down.
pub fn shutdown() {
    BACKEND.with(|b| b.borrow_mut().take());
    VOICE.with(|v| v.borrow_mut().take());
}

// prism's macOS backends (AVSpeech, VoiceOver) marshal onto the main thread
// unless they are already on it. The app calls them from the main thread;
// cargo runs tests on worker threads while the main thread just waits, so
// on macOS these would deadlock.
#[cfg(all(test, not(target_os = "macos")))]
mod tests {
    /// Every backend must initialise or fail cleanly, including those whose
    /// DLLs are absent (prism's delay-load hook substitutes stubs).
    #[test]
    fn every_backend_initialises_or_fails_cleanly() {
        let prism = prismer::Prism::new().unwrap();
        for id in prism.backend_ids() {
            if let Ok(backend) = prism.create(id) {
                let _ = backend.initialize();
            }
        }
    }

    #[test]
    fn init_and_shutdown_never_panic() {
        super::init();
        super::shutdown();
    }
}
