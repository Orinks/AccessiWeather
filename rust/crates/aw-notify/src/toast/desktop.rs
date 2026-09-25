//! macOS / Linux notifications through `notify-rust`, standing in for
//! Python's `desktop-notifier` backend: app name, title, body and the
//! timeout (seconds, sent as the D-Bus expiry), normal urgency.

use std::sync::mpsc::{self, Sender};

use notify_rust::{Notification, Timeout};

pub(super) struct Backend {
    tx: Sender<(String, String, u32)>,
}

impl Backend {
    pub(super) fn new(app_name: &str) -> Self {
        let (tx, rx) = mpsc::channel::<(String, String, u32)>();
        let app_name = app_name.to_string();
        let spawned = std::thread::Builder::new()
            .name("DesktopNotifierWorker".into())
            .spawn(move || {
                for (title, body, timeout) in rx {
                    let mut n = Notification::new();
                    n.appname(&app_name)
                        .summary(&title)
                        .body(&body)
                        .timeout(Timeout::Milliseconds(timeout.saturating_mul(1000)));
                    #[cfg(all(unix, not(target_os = "macos")))]
                    n.urgency(notify_rust::Urgency::Normal);
                    if let Err(e) = n.show() {
                        tracing::warn!("[toast] send_notification failed: {e}");
                    }
                }
            });
        if let Err(e) = spawned {
            tracing::error!("Desktop notifier worker failed to start: {e}");
        }
        Self { tx }
    }

    pub(super) fn show(&self, title: &str, body: &str, timeout: u32) -> bool {
        self.tx
            .send((title.to_string(), body.to_string(), timeout))
            .is_ok()
    }
}
