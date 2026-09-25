//! Desktop notification delivery (`notifications/toast_notifier.py`,
//! `toast_notifier_windows.py`, `windows_toast_identity*.py`).
//!
//! * Windows: WinRT toasts under the AppUserModelID `Orinks.AccessiWeather`,
//!   built from the same XML Python's `toasted` path produces (silent audio,
//!   protocol activation carrying the serialized [`ActivationRequest`]).
//!   Call [`ensure_windows_toast_identity`] once at startup, as Python's
//!   `OnInit` does, so the Start Menu shortcut, AUMID and protocol handler
//!   exist for an unpackaged exe. Clicks relaunch the exe with the
//!   activation token (see [`crate::activation`]).
//! * macOS / Linux: `notify-rust`, matching Python's `desktop-notifier` use
//!   (app name, title, body, timeout; no click handling, as in Python).
//!
//! wxDragon's `NotificationMessage::msw_use_toasts` was not used: it cannot
//! attach launch arguments, so clicks could not carry the alert id or open
//! the discussion the way Python's toasts do.
//!
//! Sounds are not played here: the app plays [`crate::Toast::sound_keys`]
//! through the audio layer whether or not the toast could be shown.

#[cfg(not(windows))]
mod desktop;
#[cfg(windows)]
mod winrt;

#[cfg(windows)]
pub use winrt::ensure_windows_toast_identity;

use crate::activation::ActivationRequest;
use crate::Toast;

pub const WINDOWS_APP_USER_MODEL_ID: &str = "Orinks.AccessiWeather";
pub const WINDOWS_TOAST_PROTOCOL_SCHEME: &str = "accessiweather-toast";
pub const WINDOWS_TOAST_ACTIVATOR_CLSID: &str = "{0D3C3F8E-7303-4C9B-81C7-FF8D8C1AFC07}";
pub const APP_NAME: &str = "AccessiWeather";

/// No-op outside Windows (Python's `ensure_windows_toast_identity` returns early).
#[cfg(not(windows))]
pub fn ensure_windows_toast_identity(_app_version: &str) {}

/// Python never shows real notifications under test
/// (`ACCESSIWEATHER_TEST_MODE=1`); neither do we.
fn suppressed_for_tests() -> bool {
    std::env::var("ACCESSIWEATHER_TEST_MODE").is_ok_and(|v| v == "1")
}

/// Shows toasts on a background worker thread (fire and forget, like
/// Python's persistent notifier worker).
pub struct Notifier {
    #[cfg(windows)]
    backend: Option<winrt::Backend>,
    #[cfg(not(windows))]
    backend: Option<desktop::Backend>,
}

impl Notifier {
    /// `app_name` is the display name registered for the AUMID the first
    /// time (Windows) or the notification's app name (Linux).
    pub fn new(app_name: &str) -> Self {
        if suppressed_for_tests() {
            tracing::info!("Using test-mode no-op backend for notifications");
            return Self { backend: None };
        }
        #[cfg(windows)]
        let backend = winrt::Backend::new(app_name);
        #[cfg(not(windows))]
        let backend = desktop::Backend::new(app_name);
        Self {
            backend: Some(backend),
        }
    }

    /// Queue a toast. Returns false only when the worker is gone. On macOS
    /// and Linux `activation` is ignored, as in Python.
    pub fn show(
        &self,
        title: &str,
        body: &str,
        timeout_secs: u32,
        activation: Option<&ActivationRequest>,
    ) -> bool {
        let Some(backend) = &self.backend else {
            tracing::info!("Test-mode notification suppressed: {title} - {body}");
            return true;
        };
        #[cfg(windows)]
        {
            let _ = timeout_secs; // WinRT toasts use the system duration, like `toasted`.
            backend.show(toast_xml(title, body, activation))
        }
        #[cfg(not(windows))]
        {
            let _ = activation;
            backend.show(title, body, timeout_secs)
        }
    }

    pub fn send(&self, toast: &Toast) -> bool {
        self.show(
            &toast.title,
            &toast.message,
            toast.timeout,
            toast.activation.as_ref(),
        )
    }
}

fn xml_escape(text: &str, attribute: bool) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' if attribute => out.push_str("&quot;"),
            '\n' if attribute => out.push_str("&#10;"),
            c => out.push(c),
        }
    }
    out
}

/// The toast XML Python hands to WinRT: two `ToastGeneric` text lines,
/// silent audio (the app plays its own sounds) and, with an activation,
/// protocol activation launching the serialized request.
pub fn toast_xml(title: &str, body: &str, activation: Option<&ActivationRequest>) -> String {
    let launch = activation
        .map(|a| {
            format!(
                r#" launch="{}" activationType="protocol""#,
                xml_escape(&a.serialize(), true)
            )
        })
        .unwrap_or_default();
    format!(
        r#"<toast{launch}><visual><binding template="ToastGeneric"><text>{}</text><text>{}</text></binding></visual><audio silent="true" loop="false" /></toast>"#,
        xml_escape(title, false),
        xml_escape(body, false)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn toast_xml_escapes_and_uses_protocol_activation() {
        let xml = toast_xml(
            "SEVERE ALERT: A & B <x>",
            "line1\n\nline2",
            Some(&ActivationRequest::alert_details("urn:oid:1")),
        );
        assert_eq!(
            xml,
            "<toast launch=\"accessiweather-toast:kind=alert_details&amp;alert_id=urn%3Aoid%3A1\" \
             activationType=\"protocol\"><visual><binding template=\"ToastGeneric\">\
             <text>SEVERE ALERT: A &amp; B &lt;x&gt;</text><text>line1\n\nline2</text></binding>\
             </visual><audio silent=\"true\" loop=\"false\" /></toast>"
        );
        assert!(toast_xml("t", "b", None).starts_with("<toast><visual>"));
    }

    #[test]
    fn test_mode_notifier_is_a_no_op() {
        std::env::set_var("ACCESSIWEATHER_TEST_MODE", "1");
        let n = Notifier::new(APP_NAME);
        assert!(n.show("t", "b", 10, None));
    }
}
