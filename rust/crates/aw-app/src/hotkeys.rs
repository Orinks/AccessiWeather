//! System-wide hotkeys (`global_hotkeys.py` and the global half of
//! `app_shortcuts.py`): the NOAA Weather Radio play/stop hotkey and the
//! configurable show window / hide window / read tray information
//! shortcuts, plus those shortcuts' in-window accelerators.
//!
//! Windows only, as in Python (wx implements `RegisterHotKey` nowhere
//! else). The hotkeys are registered by a dedicated thread that owns a
//! message loop; each `WM_HOTKEY` is posted to the UI thread.

use std::cell::RefCell;

use aw_core::shortcuts::{
    active_window_tray_bindings, normalize_hotkey, parse_hotkey, WindowTrayAction,
    WINDOW_TRAY_SHORTCUTS,
};

use crate::app::{post_to_ui, with_state};
use crate::{lifecycle, tray, ui};

const RADIO_HOTKEY_ID: i32 = 1;
/// Window/tray shortcuts use `WINDOW_TRAY_BASE_ID + index`.
const WINDOW_TRAY_BASE_ID: i32 = 2;

pub(crate) const RADIO_NOTIFICATION_TITLE: &str = "NOAA Weather Radio";
const SHORTCUTS_NOTIFICATION_TITLE: &str = "AccessiWeather shortcuts";

#[derive(Default)]
struct Hotkeys {
    #[cfg(windows)]
    thread: Option<win::HotkeyThread>,
    /// `GlobalHotkeyManager.registered_combo`.
    radio_combo: Option<String>,
    /// `_registered_hotkey_ids`.
    window_tray_ids: Vec<i32>,
}

thread_local! {
    /// `None` until `setup` (and forever in smoke runs).
    static HOTKEYS: RefCell<Option<Hotkeys>> = const { RefCell::new(None) };
}

/// `global_hotkeys.is_supported`.
pub(crate) fn is_supported() -> bool {
    cfg!(windows)
}

fn with_hotkeys<R>(f: impl FnOnce(&mut Hotkeys) -> R) -> Option<R> {
    HOTKEYS.with(|h| h.borrow_mut().as_mut().map(f))
}

/// Ask the OS for a hotkey; false when refused or unsupported.
fn register(id: i32, modifiers: u32, keycode: u32) -> bool {
    #[cfg(windows)]
    {
        with_hotkeys(|h| {
            h.thread
                .as_ref()
                .is_some_and(|t| t.register(id, modifiers, win::wx_to_vk(keycode)))
        })
        .unwrap_or(false)
    }
    #[cfg(not(windows))]
    {
        let _ = (id, modifiers, keycode);
        false
    }
}

fn unregister(id: i32) {
    #[cfg(windows)]
    with_hotkeys(|h| {
        if let Some(t) = &h.thread {
            t.unregister(id);
        }
    });
    #[cfg(not(windows))]
    let _ = id;
}

/// Startup: `_setup_accelerators` (window/tray hotkeys), then
/// `_setup_global_hotkeys` (the radio hotkey).
pub(crate) fn setup() {
    let hotkeys = Hotkeys {
        #[cfg(windows)]
        thread: win::HotkeyThread::spawn(|id| post_to_ui(move || on_hotkey(id))),
        ..Default::default()
    };
    HOTKEYS.with(|h| *h.borrow_mut() = Some(hotkeys));
    register_window_tray_hotkeys();
    refresh_radio_hotkey();
}

/// After a settings save (`refresh_runtime_settings`): `refresh_global_hotkeys`
/// then `_setup_accelerators`.
pub(crate) fn refresh() {
    refresh_radio_hotkey();
    register_window_tray_hotkeys();
}

/// Shutdown: release everything and stop the thread.
pub(crate) fn shutdown() {
    unregister_window_tray_hotkeys();
    unregister_radio_hotkey();
    HOTKEYS.with(|h| h.borrow_mut().take());
}

#[cfg_attr(not(windows), allow(dead_code))]
fn on_hotkey(id: i32) {
    if id == RADIO_HOTKEY_ID {
        lifecycle::toggle_noaa_radio();
        return;
    }
    let index = (id - WINDOW_TRAY_BASE_ID) as usize;
    if let Some(pref) = WINDOW_TRAY_SHORTCUTS.get(index) {
        run_window_tray_action(pref.action);
    }
}

// ---------------------------------------------------------------------------
// NOAA Weather Radio hotkey (`GlobalHotkeyManager`, `refresh_global_hotkeys`)
// ---------------------------------------------------------------------------

fn unregister_radio_hotkey() {
    if with_hotkeys(|h| h.radio_combo.take()).flatten().is_some() {
        unregister(RADIO_HOTKEY_ID);
    }
}

/// `GlobalHotkeyManager.apply`: whether the requested state was reached
/// (an empty combo means disabled).
fn apply_radio_hotkey(combo: &str) -> bool {
    unregister_radio_hotkey();
    if combo.trim().is_empty() {
        return true;
    }
    if !is_supported() {
        tracing::info!("System-wide hotkeys are only supported on Windows; {combo} ignored");
        return false;
    }
    let (modifiers, keycode) = match parse_hotkey(combo) {
        Ok(parsed) => parsed,
        Err(e) => {
            tracing::warn!("Could not register global hotkey: {e}");
            return false;
        }
    };
    if !register(RADIO_HOTKEY_ID, modifiers, keycode) {
        tracing::warn!("Windows refused global hotkey {combo}; another app likely owns it");
        return false;
    }
    let normalized = normalize_hotkey(combo).unwrap_or_else(|_| combo.to_string());
    tracing::info!("Registered global hotkey {normalized}");
    with_hotkeys(|h| h.radio_combo = Some(normalized));
    true
}

/// `refresh_global_hotkeys`: apply the configured combo, reporting one
/// Windows will not give us.
fn refresh_radio_hotkey() {
    let Some(combo) = with_state().map(|s| s.borrow().config.settings.noaa_radio_hotkey.clone())
    else {
        return;
    };
    let Some(registered) = with_hotkeys(|h| h.radio_combo.clone()) else {
        return;
    };
    if registered.as_deref() == Some(combo.as_str()) {
        return;
    }
    if !apply_radio_hotkey(&combo) && !combo.is_empty() && is_supported() {
        notify_radio_hotkey(format!(
            "Could not register {combo} as the NOAA Weather Radio hotkey. Another program is \
             probably using it. Choose a different combination in Settings, General."
        ));
    }
}

/// `_notify_radio_hotkey`.
pub(crate) fn notify_radio_hotkey(message: String) {
    notify_hotkey(RADIO_NOTIFICATION_TITLE, message);
}

/// `_notify_hotkey`: a desktop notification without sound, since the
/// window may be hidden.
fn notify_hotkey(title: &'static str, message: String) {
    post_to_ui(move || {
        lifecycle::with_notifier(|n| n.show(title, &message, 10, None));
    });
}

// ---------------------------------------------------------------------------
// Window/tray shortcuts (`_register_global_hotkeys` and the accelerators)
// ---------------------------------------------------------------------------

fn unregister_window_tray_hotkeys() {
    for id in with_hotkeys(|h| std::mem::take(&mut h.window_tray_ids)).unwrap_or_default() {
        unregister(id);
    }
}

/// `_register_global_hotkeys`: every active shortcut with Ctrl or Alt
/// becomes system-wide.
fn register_window_tray_hotkeys() {
    unregister_window_tray_hotkeys();
    let Some(settings) = with_state().map(|s| s.borrow().config.settings.clone()) else {
        return;
    };
    if with_hotkeys(|_| ()).is_none() {
        return;
    }
    let mut registered = Vec::new();
    for (pref, binding) in active_window_tray_bindings(&settings) {
        if !binding.has_ctrl_or_alt() {
            continue;
        }
        let normalized = binding.normalized();
        let Some(keycode) = binding.key_code() else {
            tracing::debug!(
                "Failed to register global hotkey {normalized} for {}",
                pref.label
            );
            continue;
        };
        let index = WINDOW_TRAY_SHORTCUTS
            .iter()
            .position(|p| p.action == pref.action)
            .unwrap_or_default();
        let id = WINDOW_TRAY_BASE_ID + index as i32;
        if !register(id, binding.hotkey_modifiers(), keycode) {
            tracing::warn!(
                "Global hotkey {normalized} for {} could not be registered",
                pref.label
            );
            if is_supported() {
                notify_hotkey(
                    SHORTCUTS_NOTIFICATION_TITLE,
                    format!(
                        "Could not register {normalized} as the {}. Another program is probably \
                         using it. Choose a different combination in Settings, Advanced.",
                        pref.label.to_lowercase()
                    ),
                );
            }
            continue;
        }
        registered.push(id);
    }
    with_hotkeys(|h| h.window_tray_ids = registered);
}

/// The window/tray shortcuts' in-window accelerators: true when the key
/// matched one (and it ran).
pub(crate) fn on_window_tray_accelerator(key: i32, ctrl: bool, alt: bool, shift: bool) -> bool {
    let Some(settings) = with_state().map(|s| s.borrow().config.settings.clone()) else {
        return false;
    };
    let action = active_window_tray_bindings(&settings)
        .into_iter()
        .find(|(_, b)| {
            b.key_code() == u32::try_from(key).ok()
                && b.has("Ctrl") == ctrl
                && b.has("Alt") == alt
                && b.has("Shift") == shift
        })
        .map(|(pref, _)| pref.action);
    match action {
        Some(action) => {
            run_window_tray_action(action);
            true
        }
        None => false,
    }
}

fn run_window_tray_action(action: WindowTrayAction) {
    match action {
        WindowTrayAction::ShowMainWindow => on_show_main_window_shortcut(),
        WindowTrayAction::HideMainWindow => on_hide_main_window_shortcut(),
        WindowTrayAction::ReadTrayInfo => on_read_tray_info_shortcut(),
    }
}

/// `_on_show_main_window_shortcut`.
fn on_show_main_window_shortcut() {
    if tray::exists() {
        tray::show_main_window();
        return;
    }
    let Some(frame) = ui::main_frame() else {
        return;
    };
    lifecycle::show_frame(&frame);
    frame.iconize(false);
    wxdragon::prelude::WxWidget::raise(&frame);
    wxdragon::prelude::WxWidget::set_focus(&frame);
}

/// `_on_hide_main_window_shortcut`.
fn on_hide_main_window_shortcut() {
    if tray::exists() {
        tray::hide_main_window();
        return;
    }
    ui::set_status("Tray icon unavailable, so the window cannot be hidden.");
}

/// `_on_read_tray_info_shortcut`.
fn on_read_tray_info_shortcut() {
    if tray::exists() {
        tray::announce_tooltip();
        return;
    }
    ui::set_status("Tray information is unavailable.");
}

#[cfg(windows)]
mod win {
    //! `RegisterHotKey` with no window: the hotkeys belong to this thread,
    //! and `WM_HOTKEY` arrives in its message queue.

    use std::collections::BTreeSet;
    use std::sync::mpsc::{self, Receiver, Sender};
    use std::time::Duration;

    use aw_core::shortcuts::WXK_F1;
    use windows_sys::Win32::System::Threading::GetCurrentThreadId;
    use windows_sys::Win32::UI::Input::KeyboardAndMouse::{RegisterHotKey, UnregisterHotKey};
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        GetMessageW, PeekMessageW, PostThreadMessageW, MSG, PM_NOREMOVE, WM_APP, WM_HOTKEY, WM_USER,
    };

    const VK_F1: u32 = 0x70;

    /// wx key code → virtual key (`wxMSWKeyboard::WXToVK` for the keys
    /// shortcuts can use: letters, digits, F1-F24, Escape, Space, Tab).
    pub fn wx_to_vk(keycode: u32) -> u32 {
        if (WXK_F1..WXK_F1 + 24).contains(&keycode) {
            VK_F1 + keycode - WXK_F1
        } else {
            keycode
        }
    }

    enum Command {
        Register {
            id: i32,
            modifiers: u32,
            vk: u32,
            reply: Sender<bool>,
        },
        Unregister(i32),
        Quit,
    }

    pub struct HotkeyThread {
        thread_id: u32,
        commands: Sender<Command>,
    }

    impl HotkeyThread {
        pub fn spawn(on_hotkey: impl Fn(i32) + Send + 'static) -> Option<Self> {
            let (commands, rx) = mpsc::channel();
            let (ready_tx, ready_rx) = mpsc::channel();
            std::thread::Builder::new()
                .name("AccessiWeatherHotkeys".into())
                .spawn(move || run(&rx, &ready_tx, &on_hotkey))
                .inspect_err(|e| tracing::warn!("Could not start the hotkey thread: {e}"))
                .ok()?;
            let thread_id = ready_rx.recv_timeout(Duration::from_secs(5)).ok()?;
            Some(Self {
                thread_id,
                commands,
            })
        }

        fn send(&self, command: Command) -> bool {
            // SAFETY: posting a message with no payload to a live thread.
            self.commands.send(command).is_ok()
                && unsafe { PostThreadMessageW(self.thread_id, WM_APP, 0, 0) } != 0
        }

        pub fn register(&self, id: i32, modifiers: u32, vk: u32) -> bool {
            let (reply, result) = mpsc::channel();
            let command = Command::Register {
                id,
                modifiers,
                vk,
                reply,
            };
            self.send(command) && result.recv_timeout(Duration::from_secs(5)).unwrap_or(false)
        }

        pub fn unregister(&self, id: i32) {
            self.send(Command::Unregister(id));
        }
    }

    impl Drop for HotkeyThread {
        fn drop(&mut self) {
            self.send(Command::Quit);
        }
    }

    fn run(commands: &Receiver<Command>, ready: &Sender<u32>, on_hotkey: &dyn Fn(i32)) {
        let mut msg: MSG = unsafe { std::mem::zeroed() };
        let mut registered = BTreeSet::new();
        // SAFETY: plain Win32 calls on this thread's own message queue.
        unsafe {
            // Create the queue before anyone posts to it.
            PeekMessageW(
                &mut msg,
                std::ptr::null_mut(),
                WM_USER,
                WM_USER,
                PM_NOREMOVE,
            );
            let _ = ready.send(GetCurrentThreadId());
            while GetMessageW(&mut msg, std::ptr::null_mut(), 0, 0) > 0 {
                match msg.message {
                    WM_HOTKEY => on_hotkey(msg.wParam as i32),
                    WM_APP => {
                        while let Ok(command) = commands.try_recv() {
                            match command {
                                Command::Register {
                                    id,
                                    modifiers,
                                    vk,
                                    reply,
                                } => {
                                    let ok =
                                        RegisterHotKey(std::ptr::null_mut(), id, modifiers, vk)
                                            != 0;
                                    if ok {
                                        registered.insert(id);
                                    }
                                    let _ = reply.send(ok);
                                }
                                Command::Unregister(id) => {
                                    if registered.remove(&id) {
                                        UnregisterHotKey(std::ptr::null_mut(), id);
                                    }
                                }
                                Command::Quit => {
                                    for id in registered {
                                        UnregisterHotKey(std::ptr::null_mut(), id);
                                    }
                                    return;
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn keys_map_to_virtual_keys() {
            assert_eq!(wx_to_vk('R' as u32), 0x52);
            assert_eq!(wx_to_vk('5' as u32), 0x35);
            assert_eq!(wx_to_vk(WXK_F1), 0x70);
            assert_eq!(wx_to_vk(WXK_F1 + 23), 0x87);
            assert_eq!(wx_to_vk(27), 0x1B);
        }
    }
}
