//! App-wide NOAA Weather Radio: the one radio context, created at startup
//! (`app_initialization.py`), the play/stop hotkey (`app_shortcuts.py`
//! `_on_noaa_radio_hotkey`), the alert auto-tuner (`app.alert_radio_auto_tuner`)
//! and the stop at exit (`app_lifecycle.py`).
//!
//! Everything here may be called from any thread.

use std::path::Path;
use std::sync::{mpsc, Arc, OnceLock};
use std::time::Duration;

use aw_providers::HttpClient;
use aw_radio::toggle::NotifyCallback;
use aw_radio::{AlertRadioAutoTuner, RadioContext, RadioToggleController, RodioBackend};

use crate::app::{post_to_ui, with_state, State};

pub(crate) struct Radio {
    pub ctx: RadioContext,
    pub auto_tuner: Arc<AlertRadioAutoTuner>,
    toggle: OnceLock<Arc<RadioToggleController>>,
}

static RADIO: OnceLock<Radio> = OnceLock::new();

/// Create the radio context and the auto-tuner. Call once at startup.
pub(crate) fn init(config_dir: &Path, http: Arc<dyn HttpClient>) {
    let backend = match RodioBackend::new() {
        Ok(backend) => backend,
        Err(e) => {
            tracing::error!("NOAA Weather Radio is unavailable: {e}");
            return;
        }
    };
    let ctx = RadioContext::new(config_dir, http, Arc::new(backend));
    let auto_tuner = ctx.auto_tuner(
        Box::new(|| read_state(|st| st.config.settings.clone())),
        Box::new(|| read_state(|st| st.config.current_location.clone()).flatten()),
        // Python: `app.main_window.set_status(message)` via wx.CallAfter.
        Some(Arc::new(|message: String| {
            post_to_ui(move || {
                if crate::ui::main_frame().is_some() {
                    crate::ui::set_status(&message);
                }
            })
        })),
    );
    let _ = RADIO.set(Radio {
        ctx,
        auto_tuner,
        toggle: OnceLock::new(),
    });
}

pub(crate) fn radio() -> Option<&'static Radio> {
    RADIO.get()
}

/// The alert auto-tuner, for the alert notification system
/// (`tune_for_alerts`).
pub(crate) fn auto_tuner() -> Option<Arc<AlertRadioAutoTuner>> {
    radio().map(|r| r.auto_tuner.clone())
}

/// The system-wide NOAA Weather Radio hotkey: stop if playing, otherwise
/// resume the last station. `notify` shows a desktop notification titled
/// "NOAA Weather Radio" (`_notify_radio_hotkey`). Like Python, the
/// controller is created on the first press and keeps that callback.
pub(crate) fn radio_toggle(notify: NotifyCallback) {
    let Some(radio) = radio() else { return };
    radio
        .toggle
        .get_or_init(|| {
            radio
                .ctx
                .toggle_controller(Some(notify), Some(radio.auto_tuner.clone()))
        })
        .toggle();
}

/// App exit: `alert_radio_auto_tuner.stop()`, then stop the stream.
pub(crate) fn radio_shutdown() {
    crate::ui::close_noaa_radio_dialog();
    if let Some(radio) = radio() {
        radio.auto_tuner.stop();
        radio.ctx.shutdown();
    }
}

/// Read app state from any thread: directly on the UI thread (where it
/// lives), otherwise by a round trip through it. `None` if the UI is gone.
fn read_state<T: Send + 'static>(read: fn(&State) -> T) -> Option<T> {
    if let Some(state) = with_state() {
        let st = state.try_borrow().ok()?;
        return Some(read(&st));
    }
    let (tx, rx) = mpsc::channel();
    post_to_ui(move || {
        let Some(state) = with_state() else { return };
        let Ok(st) = state.try_borrow() else { return };
        let _ = tx.send(read(&st));
    });
    rx.recv_timeout(Duration::from_secs(10)).ok()
}
