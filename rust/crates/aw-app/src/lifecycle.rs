//! The application lifecycle around the main window: the startup order of
//! `AccessiWeatherApp.OnInit` (`app.py`), showing or starting in the tray,
//! minimize to tray, notification activation routing (`app_activation.py`),
//! the automatic update schedule (`app_timer_manager.py`,
//! `app_lifecycle.py`), launch-at-login repair (`app_initialization.py`),
//! the startup guidance prompt timings (`app_startup_guidance.py`),
//! startup/exit sounds and the `request_exit` shutdown order.
//!
//! wxDragon has no EVT_ICONIZE or EVT_SHOW. On Windows the frame is
//! subclassed to see the `WM_SIZE`/`SIZE_MINIMIZED` and `WM_SHOWWINDOW`
//! messages wx derives them from. Elsewhere, minimizing is noticed shortly
//! after the frame deactivates, and every show path this module owns sets
//! the initial focus itself.

use std::cell::{OnceCell, RefCell};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use aw_notify::ActivationRequest;
use aw_services::single_instance::SingleInstance;
use aw_services::startup::{StartupManager, StartupSync, STARTUP_FAILED_TITLE};
use aw_services::update;
use wxdragon::prelude::*;
use wxdragon::timer::Timer;

use crate::app::{post_to_ui, with_state, Shared};
use crate::{hotkeys, tray, ui};

/// What the command line asked for (`AccessiWeatherApp.__init__` and the
/// `--fake-version` / `--fake-nightly` overrides in `app.main`).
pub(crate) struct Launch {
    pub version: String,
    pub build_tag: Option<String>,
    pub force_wizard: bool,
    pub activation_request: Option<ActivationRequest>,
    pub smoke: bool,
}

struct Lifecycle {
    launch: Launch,
    single_instance: Option<SingleInstance>,
    /// `_last_update_check_at`.
    last_update_check: Option<Instant>,
    /// `_auto_update_interval_seconds`.
    auto_update_interval: Duration,
    exiting: bool,
}

thread_local! {
    static LIFECYCLE: RefCell<Option<Lifecycle>> = const { RefCell::new(None) };
    /// Owned by the frame, so dropped in `shutdown` before it goes.
    static AUTO_UPDATE_TIMER: RefCell<Option<Timer<Frame>>> = const { RefCell::new(None) };
    static HANDOFF_TIMER: RefCell<Option<Timer<Frame>>> = const { RefCell::new(None) };
    static NOTIFIER: OnceCell<aw_notify::Notifier> = const { OnceCell::new() };
}

/// The exit sound keeps playing while the window closes; `run` waits for it.
static EXIT_SOUND: Mutex<Option<JoinHandle<()>>> = Mutex::new(None);

fn with_lifecycle<R>(f: impl FnOnce(&mut Lifecycle) -> R) -> Option<R> {
    LIFECYCLE.with(|l| l.borrow_mut().as_mut().map(f))
}

/// The running version, honouring `--fake-version`.
pub(crate) fn app_version() -> String {
    with_lifecycle(|l| l.launch.version.clone())
        .unwrap_or_else(|| update::app_version().to_string())
}

/// The nightly build tag, honouring `--fake-nightly`.
pub(crate) fn build_tag() -> Option<String> {
    with_lifecycle(|l| l.launch.build_tag.clone())
        .unwrap_or_else(|| update::build_tag().map(str::to_string))
}

/// `wx.CallLater`: run `f` on the UI thread after `ms` milliseconds.
pub(crate) fn call_later(ms: u64, f: impl FnOnce() + Send + 'static) {
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_millis(ms));
        post_to_ui(f);
    });
}

fn settings() -> Option<aw_core::settings::AppSettings> {
    with_state().map(|s| s.borrow().config.settings.clone())
}

// ---------------------------------------------------------------------------
// Startup (`OnInit`)
// ---------------------------------------------------------------------------

/// Everything `OnInit` does after the single-instance check, in its order.
pub(crate) fn on_init(state: &Shared, launch: Launch, single_instance: Option<SingleInstance>) {
    tracing::info!("Starting AccessiWeather application");
    let (offline, debug) = {
        let st = state.borrow();
        (st.offline, st.debug)
    };
    let smoke = launch.smoke;
    // Registering the toast identity and the login entry points them at
    // this executable; a sample-data or source run must not take them over.
    let registers_system = !offline && !aw_services::is_running_from_source();
    if registers_system {
        aw_notify::ensure_windows_toast_identity(aw_core::VERSION);
    }
    let activation_request = launch.activation_request.clone();
    LIFECYCLE.with(|l| {
        *l.borrow_mut() = Some(Lifecycle {
            launch,
            single_instance,
            last_update_check: None,
            auto_update_interval: Duration::from_secs(24 * 3600),
            exiting: false,
        })
    });

    // `initialize_components`: the deferred launch-at-login repair.
    if registers_system {
        call_later(150, ensure_startup_registration);
    }

    // Main window, initial data and background updates.
    ui::build_main_window(state, smoke);
    let Some(frame) = ui::main_frame() else {
        return;
    };
    watch_frame(&frame);

    if !smoke {
        hotkeys::setup();
    }
    tray::initialize(debug);
    if !smoke {
        start_activation_ipc_server();
        start_activation_handoff_polling();
        play_startup_sound();
    }
    tray::init_updater(&state.borrow().config.settings);
    show_or_minimize_window();
    // `_schedule_startup_activation_request`.
    if let Some(request) = activation_request {
        post_to_ui(move || handle_activation_request(request));
    }
    let force_wizard = with_lifecycle(|l| l.launch.force_wizard).unwrap_or(false);
    if !smoke {
        ui::guidance::schedule_startup_guidance_prompts(force_wizard);
    }
    if !offline {
        start_auto_update_checks();
        // The startup check waits for the onboarding wizard when it shows.
        ui::guidance::check_for_updates_after_startup_guidance(force_wizard);
    }
    tracing::info!("AccessiWeather application started successfully");
}

/// `ConfigManager.ensure_startup_registration`: repair the login entry to
/// match the saved setting, or adopt what the OS says.
fn ensure_startup_registration() {
    let Some(state) = with_state() else { return };
    let enabled = state.borrow().config.settings.startup_enabled;
    if let StartupSync::SetSetting(value) =
        StartupManager::new().ensure_startup_registration(enabled)
    {
        let mut st = state.borrow_mut();
        st.config.settings.startup_enabled = value;
        let _ = crate::app::save(&st);
    }
}

/// The login entry manager, or `None` for sample-data and source runs, which
/// must not point the login entry at themselves (see `on_init`).
fn startup_manager() -> Option<StartupManager> {
    let offline = with_state().is_none_or(|s| s.borrow().offline);
    (!offline && !aw_services::is_running_from_source()).then(StartupManager::new)
}

/// `config_manager.is_startup_enabled`; without a manager, the saved setting.
pub(crate) fn is_startup_enabled() -> bool {
    match startup_manager() {
        Some(manager) => manager.is_startup_enabled(),
        None => settings().is_some_and(|s| s.startup_enabled),
    }
}

/// `SettingsDialog._apply_startup_enabled_setting`: register or remove the
/// login entry for the "launch at login" checkbox. `loaded` is the value
/// the dialog opened with. False (after telling the user) when it could not
/// be applied; the dialog then keeps `loaded`.
pub(crate) fn apply_startup_enabled_setting(
    parent: &dyn WxWidget,
    desired: bool,
    loaded: bool,
) -> bool {
    if desired == loaded && is_startup_enabled() == desired {
        return true;
    }
    let Some(manager) = startup_manager() else {
        tracing::info!("Startup setting saved without OS registration (sample-data or source run)");
        return true;
    };
    let (ok, message) = manager.set_startup(desired);
    if ok {
        tracing::info!("Startup setting applied: {message}");
        return true;
    }
    tracing::error!("Failed to apply startup setting: {message}");
    ui::message_box(
        parent,
        message,
        STARTUP_FAILED_TITLE,
        MessageDialogStyle::OK | MessageDialogStyle::IconError,
    );
    false
}

// ---------------------------------------------------------------------------
// Showing, hiding and minimizing to the tray
// ---------------------------------------------------------------------------

/// `Show(True)`. Off Windows this also stands in for EVT_SHOW's initial
/// focus (Windows sees `WM_SHOWWINDOW` for every show, see `watch_frame`).
pub(crate) fn show_frame(frame: &Frame) {
    frame.show(true);
    if !cfg!(windows) {
        on_frame_shown();
    }
}

/// `_on_window_shown`: focus the location dropdown 100 ms after every show.
fn on_frame_shown() {
    call_later(100, ui::set_initial_focus);
}

/// `_show_or_minimize_window`: start hidden in the tray only when there is one.
fn show_or_minimize_window() {
    let Some(frame) = ui::main_frame() else {
        return;
    };
    let minimize = settings().is_some_and(|s| s.minimize_on_startup);
    if minimize && tray::exists() {
        tracing::info!("Window minimized to tray on startup");
        return;
    }
    show_frame(&frame);
    if minimize {
        tracing::warn!("minimize_on_startup enabled but tray icon unavailable");
    }
}

/// `_should_minimize_to_tray`: the setting, and (unlike Python) a tray icon
/// to come back from, so the window is never hidden with no way back.
pub(crate) fn should_minimize_to_tray() -> bool {
    tray::exists() && settings().is_some_and(|s| s.minimize_to_tray)
}

/// `_minimize_to_tray`: restore from the taskbar first, then hide.
pub(crate) fn minimize_to_tray() {
    if !tray::exists() {
        return;
    }
    if let Some(frame) = ui::main_frame() {
        frame.iconize(false);
        frame.hide();
        tracing::debug!("Window minimized to system tray");
    }
}

/// `_on_escape_pressed`.
pub(crate) fn on_escape_pressed() {
    if should_minimize_to_tray() {
        minimize_to_tray();
    }
}

/// `_on_iconize`: hide to the tray once the minimize has finished.
fn on_frame_iconized() {
    post_to_ui(|| {
        if should_minimize_to_tray() {
            minimize_to_tray();
        }
    });
}

#[cfg(windows)]
fn watch_frame(frame: &Frame) {
    win32::watch_frame(frame.get_handle());
}

#[cfg(not(windows))]
fn watch_frame(frame: &Frame) {
    // ponytail: no EVT_ICONIZE in wxDragon; minimizing deactivates the
    // frame, so look shortly after each deactivation. Bind wxEVT_ICONIZE
    // once wxDragon exposes it.
    frame.bind_internal(EventType::ACTIVATE, |e: Event| {
        e.skip(true);
        call_later(300, || {
            if ui::main_frame().is_some_and(|f| f.is_iconized()) {
                on_frame_iconized();
            }
        });
    });
}

/// Win32 pieces of showing the window.
#[cfg(windows)]
pub(crate) mod win32 {
    use std::ffi::c_void;

    use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
    use windows_sys::Win32::System::Threading::GetCurrentProcessId;
    use windows_sys::Win32::UI::Shell::{DefSubclassProc, RemoveWindowSubclass, SetWindowSubclass};
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        AllowSetForegroundWindow, IsIconic, SetForegroundWindow, ShowWindow, SIZE_MINIMIZED,
        SW_RESTORE, SW_SHOWNORMAL, WM_NCDESTROY, WM_SHOWWINDOW, WM_SIZE,
    };

    const SUBCLASS_ID: usize = 0xA3E1;

    /// Restore and foreground a window the way `show_main_window`
    /// (`show_normal`) and `_force_foreground_window` do.
    pub(crate) fn restore_to_foreground(hwnd: *mut c_void, show_normal: bool) {
        let hwnd = hwnd as HWND;
        if hwnd.is_null() {
            return;
        }
        // SAFETY: plain Win32 calls on our own top-level window.
        unsafe {
            if IsIconic(hwnd) != 0 {
                ShowWindow(hwnd, SW_RESTORE);
            } else if show_normal {
                ShowWindow(hwnd, SW_SHOWNORMAL);
            }
            AllowSetForegroundWindow(GetCurrentProcessId());
            SetForegroundWindow(hwnd);
        }
    }

    pub(super) fn watch_frame(hwnd: *mut c_void) {
        // SAFETY: subclassing our own window on its thread; removed on WM_NCDESTROY.
        unsafe { SetWindowSubclass(hwnd as HWND, Some(subclass_proc), SUBCLASS_ID, 0) };
    }

    /// Only posts work: this can run inside any wx call that resizes or
    /// shows the frame, while app state may be borrowed.
    unsafe extern "system" fn subclass_proc(
        hwnd: HWND,
        msg: u32,
        wparam: WPARAM,
        lparam: LPARAM,
        id: usize,
        _data: usize,
    ) -> LRESULT {
        match msg {
            WM_SIZE if wparam as u32 == SIZE_MINIMIZED => super::on_frame_iconized(),
            WM_SHOWWINDOW if wparam != 0 => super::on_frame_shown(),
            WM_NCDESTROY => {
                // SAFETY: removing the subclass this module installed.
                unsafe { RemoveWindowSubclass(hwnd, Some(subclass_proc), id) };
            }
            _ => {}
        }
        // SAFETY: forwarding the message down the subclass chain.
        unsafe { DefSubclassProc(hwnd, msg, wparam, lparam) }
    }
}

// ---------------------------------------------------------------------------
// Activation (`app_activation.py`)
// ---------------------------------------------------------------------------

fn start_activation_ipc_server() {
    with_lifecycle(|l| {
        if let Some(si) = l.single_instance.as_mut() {
            si.start_activation_ipc_server(|request| {
                post_to_ui(move || handle_activation_request(request))
            });
        }
    });
}

/// `_start_activation_handoff_polling`: the fallback when the pipe is down.
fn start_activation_handoff_polling() {
    let Some(frame) = ui::main_frame() else {
        return;
    };
    let timer = Timer::new(&frame);
    timer.on_tick(|_| {
        let request = with_lifecycle(|l| {
            l.single_instance
                .as_ref()
                .and_then(SingleInstance::consume_activation_handoff)
        })
        .flatten();
        if let Some(request) = request {
            handle_activation_request(request);
        }
    });
    timer.start(
        aw_notify::activation::HANDOFF_POLL_INTERVAL.as_millis() as i32,
        false,
    );
    HANDOFF_TIMER.with(|t| *t.borrow_mut() = Some(timer));
}

/// `_handle_notification_activation_request`: open the discussion or the
/// alert without restoring the window; anything else restores it.
pub(crate) fn handle_activation_request(request: ActivationRequest) {
    let (Some(frame), Some(state)) = (ui::main_frame(), with_state()) else {
        return;
    };
    let route = {
        let st = state.borrow();
        let alerts = st
            .current_weather_data
            .as_ref()
            .and_then(|d| d.alerts.as_ref());
        aw_notify::activation::route(&request, alerts, chrono::Utc::now())
    };
    match route {
        aw_notify::ActivationRoute::OpenDiscussion => ui::on_discussion(),
        aw_notify::ActivationRoute::ShowAlertDetails(index) => ui::show_alert_details_at(index),
        aw_notify::ActivationRoute::Ignore => {}
        aw_notify::ActivationRoute::RestoreMainWindow => {
            if tray::exists() {
                tray::show_main_window();
                return;
            }
            show_frame(&frame);
            frame.iconize(false);
            #[cfg(windows)]
            win32::restore_to_foreground(frame.get_handle(), false);
            #[cfg(not(windows))]
            frame.raise();
        }
    }
}

// ---------------------------------------------------------------------------
// Automatic update checks (`app_timer_manager.py`, `_check_for_updates_on_startup`)
// ---------------------------------------------------------------------------

fn stop_auto_update_checks() {
    if let Some(timer) = AUTO_UPDATE_TIMER.with(|t| t.borrow_mut().take()) {
        timer.stop();
    }
}

/// `start_auto_update_checks`: wake every 15 minutes and check when due,
/// which survives sleep/wake better than one long timer.
fn start_auto_update_checks() {
    stop_auto_update_checks();
    let Some(settings) = settings() else { return };
    let Some(interval) = update::auto_update_interval(&settings) else {
        tracing::info!("Auto-update scheduler: disabled via settings");
        return;
    };
    with_lifecycle(|l| {
        l.auto_update_interval = interval;
        // The startup check runs separately; don't treat the first tick as overdue.
        l.last_update_check.get_or_insert_with(Instant::now);
    });
    let Some(frame) = ui::main_frame() else {
        return;
    };
    let timer = Timer::new(&frame);
    timer.on_tick(|_| on_auto_update_check_timer());
    timer.start(update::AUTO_UPDATE_POLL_INTERVAL.as_millis() as i32, false);
    AUTO_UPDATE_TIMER.with(|t| *t.borrow_mut() = Some(timer));
    tracing::info!(
        "Auto-update scheduler: checks every {}h (polled every {}min, resilient to system sleep/wake)",
        interval.as_secs() / 3600,
        update::AUTO_UPDATE_POLL_INTERVAL.as_secs() / 60
    );
}

/// `_check_for_updates_on_startup`: the automatic (silent unless an update
/// exists) check; `ui::updates` owns the skip rules and the update dialog.
fn check_for_updates_on_startup() {
    with_lifecycle(|l| l.last_update_check = Some(Instant::now()));
    ui::updates::check_for_updates(false);
}

/// `on_auto_update_check_timer`.
fn on_auto_update_check_timer() {
    let Some((last, interval)) = with_lifecycle(|l| (l.last_update_check, l.auto_update_interval))
    else {
        return;
    };
    let now = Instant::now();
    if !update::is_update_check_due(last, now, interval) {
        let elapsed = last.map_or(0, |l| now.duration_since(l).as_secs());
        tracing::debug!(
            "Auto-update tick: {elapsed}s elapsed of {}s \u{2014} not due",
            interval.as_secs()
        );
        return;
    }
    let elapsed = last.map_or("no prior check".to_string(), |l| {
        format!("{}s", now.duration_since(l).as_secs())
    });
    tracing::info!(
        "Auto-update tick: {elapsed} elapsed (threshold {}s) \u{2014} running check",
        interval.as_secs()
    );
    check_for_updates_on_startup();
}

// ---------------------------------------------------------------------------
// Sounds, notifications and the radio
// ---------------------------------------------------------------------------

/// `_play_startup_sound`.
fn play_startup_sound() {
    let Some(s) = settings().filter(|s| s.sound_enabled) else {
        return;
    };
    aw_audio::player().play_event(&s.sound_pack, "startup", &s.muted_sound_events);
    tracing::debug!("Played startup sound from pack: {}", s.sound_pack);
}

/// `play_exit_sound`: started here, finished before the process ends.
fn play_exit_sound() {
    let Some(s) = settings().filter(|s| s.sound_enabled) else {
        return;
    };
    let Some((file, volume)) =
        aw_audio::player().resolve_event(&s.sound_pack, "exit", &s.muted_sound_events)
    else {
        return;
    };
    let handle = std::thread::spawn(move || {
        aw_audio::player().play_file_blocking(&file, volume);
    });
    *EXIT_SOUND.lock().unwrap_or_else(|e| e.into_inner()) = Some(handle);
}

/// Let the exit sound finish (Python's process outlives it by chance).
pub(crate) fn wait_for_exit_sound() {
    let handle = EXIT_SOUND.lock().unwrap_or_else(|e| e.into_inner()).take();
    if let Some(handle) = handle {
        let _ = handle.join();
    }
}

/// The app-wide notifier (`app._notifier`).
pub(crate) fn with_notifier<R>(f: impl FnOnce(&aw_notify::Notifier) -> R) -> R {
    NOTIFIER.with(|n| f(n.get_or_init(|| aw_notify::Notifier::new(aw_notify::toast::APP_NAME))))
}

/// `_on_noaa_radio_hotkey`: play or stop the last station.
pub(crate) fn toggle_noaa_radio() {
    crate::radio::radio_toggle(Arc::new(hotkeys::notify_radio_hotkey));
}

// ---------------------------------------------------------------------------
// Settings changes and shutdown
// ---------------------------------------------------------------------------

/// `refresh_runtime_settings`, for the parts this module owns: the tray
/// tooltip, the hotkeys, the update schedule and the refresh timer.
pub(crate) fn refresh_runtime_settings() {
    tracing::info!("Refreshing runtime settings");
    let Some(state) = with_state() else { return };
    // Settings, the data source and API keys reach the weather client.
    crate::app::refresh_runtime_settings(&state.borrow());
    let offline = state.borrow().offline;
    tray::refresh_updater(&state.borrow().config.settings);
    hotkeys::refresh();
    if !offline {
        start_auto_update_checks();
    }
    ui::start_background_updates();
    tracing::info!("Runtime settings refreshed successfully");
}

/// `request_exit`, minus what the main window's close handler does itself:
/// update timers, hotkeys, the radio, the exit sound, the tray icon, the
/// single-instance lock, then leave the main loop.
pub(crate) fn shutdown() {
    if with_lifecycle(|l| std::mem::replace(&mut l.exiting, true)) != Some(false) {
        return;
    }
    let smoke = with_lifecycle(|l| l.launch.smoke).unwrap_or(false);
    stop_auto_update_checks();
    if let Some(timer) = HANDOFF_TIMER.with(|t| t.borrow_mut().take()) {
        timer.stop();
    }
    hotkeys::shutdown();
    crate::radio::radio_shutdown();
    if !smoke {
        play_exit_sound();
    }
    tray::destroy();
    if let Some(mut si) = with_lifecycle(|l| l.single_instance.take()).flatten() {
        si.release_lock();
    }
    if let Some(app) = wxdragon::get_app_instance() {
        app.exit_main_loop();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Without a real (non-sample, installed) run nothing may touch the
    /// login entry: tests have no app state and run from the target dir.
    #[test]
    fn no_login_entry_without_a_real_run() {
        assert!(startup_manager().is_none());
        assert!(!is_startup_enabled());
    }
}
