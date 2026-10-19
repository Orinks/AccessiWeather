//! Screen reader announcements through prism (the `prismer` crate).
//!
//! Announcements go to a running screen reader or nowhere. prism ranks text
//! to speech engines (OneCore, SAPI, AVSpeech, ...) alongside screen readers,
//! so its own "best backend" pick can land on a system voice while Narrator
//! is running. Instead the screen readers are tried in prism's priority order
//! and only one reporting `IS_SUPPORTED_AT_RUNTIME` is used. Narrator has no
//! backend of its own; it is reached through prism's UI Automation backend,
//! which needs a visible app window when it starts, so the pick is retried
//! on each announcement until one succeeds, and redone when the reader stops
//! running or fails. Scheduled readings fall back to the system voice when no
//! screen reader runs. Everything runs on the UI thread.

use std::cell::{Cell, RefCell};

use prismer::{Backend, BackendId, Error, Features, Prism};

thread_local! {
    /// The screen reader in use and its backend id.
    static READER: RefCell<Option<(BackendId, Backend<'static>)>> = const { RefCell::new(None) };
    static PRISM: Cell<Option<&'static Prism>> = const { Cell::new(None) };
    /// The system voice, used for scheduled readings when no screen reader runs.
    static VOICE: RefCell<Option<Backend<'static>>> = const { RefCell::new(None) };
}

/// Text to speech engines. Never used for announcements.
const SPEECH_ENGINES: [BackendId; 7] = [
    BackendId::ONE_CORE,
    BackendId::SAPI,
    BackendId::AV_SPEECH,
    BackendId::SPEECH_DISPATCHER,
    BackendId::SPIEL,
    BackendId::ANDROID_TTS,
    BackendId::WEB_SPEECH,
];

/// System voices for scheduled readings, best first.
#[cfg(windows)]
const SYSTEM_VOICES: [BackendId; 2] = [BackendId::ONE_CORE, BackendId::SAPI];
#[cfg(target_os = "macos")]
const SYSTEM_VOICES: [BackendId; 1] = [BackendId::AV_SPEECH];
#[cfg(not(any(windows, target_os = "macos")))]
const SYSTEM_VOICES: [BackendId; 2] = [BackendId::SPEECH_DISPATCHER, BackendId::SPIEL];

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

/// Screen reader backends, highest priority first.
fn screen_reader_ids(prism: &Prism) -> Vec<BackendId> {
    let mut ids: Vec<BackendId> = prism
        .backend_ids()
        .into_iter()
        .filter(|id| !SPEECH_ENGINES.contains(id))
        .collect();
    ids.sort_by_key(|id| std::cmp::Reverse(prism.backend_priority(*id)));
    ids
}

fn is_running(backend: &Backend<'_>) -> bool {
    backend.supports(Features::IS_SUPPORTED_AT_RUNTIME)
}

fn initialize(backend: &Backend<'_>) -> prismer::Result<()> {
    match backend.initialize() {
        Ok(()) | Err(Error::AlreadyInitialized) => Ok(()),
        Err(e) => Err(e),
    }
}

/// The highest priority screen reader that is running and starts up.
fn find_screen_reader(prism: &'static Prism) -> Option<(BackendId, Backend<'static>)> {
    screen_reader_ids(prism).into_iter().find_map(|id| {
        let backend = prism.create(id).ok()?;
        if !is_running(&backend) {
            return None;
        }
        match initialize(&backend) {
            Ok(()) => {
                tracing::info!("Screen reader backend active: {}", backend.name());
                Some((id, backend))
            }
            Err(e) => {
                tracing::debug!("Screen reader {} did not start: {e}", backend.name());
                None
            }
        }
    })
}

/// Whether a screen reader ranked above `current` is now running, such as
/// NVDA started while Narrator (through UIA) was in use.
fn better_reader_running(prism: &Prism, current: BackendId) -> bool {
    let floor = prism.backend_priority(current);
    screen_reader_ids(prism)
        .into_iter()
        .take_while(|&id| id != current && prism.backend_priority(id) > floor)
        .any(|id| prism.create(id).is_ok_and(|b| is_running(&b)))
}

/// Speak through the current screen reader, picking one first when there is
/// none, the last one stopped running, or a higher ranked one has started. A failed speak (for example the
/// window UI Automation was bound to has closed) re-picks once. Returns
/// whether a screen reader took the text.
fn speak_with_screen_reader(text: &str) -> bool {
    let Some(prism) = prism() else { return false };
    READER.with(|cell| {
        let mut reader = cell.borrow_mut();
        for attempt in 0..2 {
            if reader.as_ref().is_some_and(|(id, b)| {
                attempt > 0 || !is_running(b) || better_reader_running(prism, *id)
            }) {
                *reader = None;
            }
            if reader.is_none() {
                *reader = find_screen_reader(prism);
            }
            let Some((_, backend)) = reader.as_ref() else {
                return false;
            };
            match backend.speak(text, false) {
                Ok(()) => return true,
                Err(e) => tracing::debug!("{} failed to speak: {e}", backend.name()),
            }
        }
        *reader = None;
        false
    })
}

/// Look for a running screen reader. Announcements also look on demand, so
/// one started later, or reachable only once the main window is up, is found.
pub fn init() {
    let Some(prism) = prism() else { return };
    READER.with(|r| {
        let mut reader = r.borrow_mut();
        if reader.is_none() {
            *reader = find_screen_reader(prism);
        }
        if reader.is_none() {
            tracing::debug!("No screen reader running yet");
        }
    });
}

/// Speak `text` through the screen reader. No-op when none is running.
pub fn announce(text: &str) {
    if text.trim().is_empty() {
        return;
    }
    if !speak_with_screen_reader(text) {
        tracing::debug!("No screen reader to announce to");
    }
}

fn system_voice(prism: &'static Prism) -> Option<Backend<'static>> {
    SYSTEM_VOICES.iter().find_map(|&id| {
        let backend = prism.create(id).ok()?;
        match initialize(&backend) {
            Ok(()) => {
                tracing::info!("System voice for scheduled readings: {}", backend.name());
                Some(backend)
            }
            Err(e) => {
                tracing::debug!("System voice {} unavailable: {e}", backend.name());
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
    if speak_with_screen_reader(text) {
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
    READER.with(|b| b.borrow_mut().take());
    VOICE.with(|v| v.borrow_mut().take());
}

// prism's macOS backends (AVSpeech, VoiceOver) marshal onto the main thread
// unless they are already on it. The app calls them from the main thread;
// cargo runs tests on worker threads while the main thread just waits, so
// on macOS these would deadlock.
#[cfg(all(test, not(target_os = "macos")))]
mod tests {
    use std::sync::{Mutex, MutexGuard};

    use super::*;

    /// prism's Linux backends register GLib types on first use, which races
    /// and can crash when tests start contexts on several threads at once.
    fn serial() -> MutexGuard<'static, ()> {
        static LOCK: Mutex<()> = Mutex::new(());
        LOCK.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Every backend must initialise or fail cleanly, including those whose
    /// libraries are absent.
    #[test]
    fn every_backend_initialises_or_fails_cleanly() {
        let _serial = serial();
        let prism = Prism::new().unwrap();
        for id in prism.backend_ids() {
            if let Ok(backend) = prism.create(id) {
                let _ = backend.initialize();
            }
        }
    }

    #[test]
    fn screen_readers_exclude_speech_engines_and_run_best_first() {
        let _serial = serial();
        let prism = Prism::new().unwrap();
        let ids = screen_reader_ids(&prism);
        assert!(ids.iter().all(|id| !SPEECH_ENGINES.contains(id)));
        let priorities: Vec<i32> = ids.iter().map(|id| prism.backend_priority(*id)).collect();
        assert!(priorities.windows(2).all(|w| w[0] >= w[1]));
        #[cfg(windows)]
        assert!(
            ids.contains(&BackendId::UIA),
            "Narrator is reached through UIA"
        );
    }

    #[test]
    fn init_announce_and_shutdown_never_panic() {
        let _serial = serial();
        init();
        announce("test");
        shutdown();
    }
}
