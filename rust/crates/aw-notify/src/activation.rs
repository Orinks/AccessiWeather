//! Toast click activation, ported from `notification_activation.py` plus the
//! routing in `app_activation.py`.
//!
//! On Windows every toast that carries an activation uses protocol
//! activation: clicking it launches `AccessiWeather.exe
//! "accessiweather-toast:kind=...&alert_id=..."` (the handler is registered by
//! [`crate::toast::ensure_windows_toast_identity`]). That process finds the
//! request with [`ActivationRequest::from_argv`]; if another instance is
//! already running it hands the request over through the handoff file
//! ([`write_handoff`]) and exits, and the running instance picks it up with
//! [`consume_handoff`] (Python polls every 2 s, see
//! [`spawn_handoff_listener`]). [`route`] then says what the UI should do.

use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver};
use std::time::Duration;

use aw_core::model::WeatherAlerts;
use chrono::{DateTime, Utc};
use serde_json::{json, Value};

use crate::py;

pub const ACTIVATION_PREFIX: &str = "accessiweather-toast:";
/// `_ACTIVATION_HANDOFF_POLL_MS`.
pub const HANDOFF_POLL_INTERVAL: Duration = Duration::from_millis(2000);
pub const HANDOFF_FILE_NAME: &str = "activation_request.json";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ActivationKind {
    Discussion,
    AlertDetails,
    GenericFallback,
}

impl ActivationKind {
    pub fn as_str(self) -> &'static str {
        match self {
            ActivationKind::Discussion => "discussion",
            ActivationKind::AlertDetails => "alert_details",
            ActivationKind::GenericFallback => "generic_fallback",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "discussion" => Some(ActivationKind::Discussion),
            "alert_details" => Some(ActivationKind::AlertDetails),
            "generic_fallback" => Some(ActivationKind::GenericFallback),
            _ => None,
        }
    }
}

/// `NotificationActivationRequest`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ActivationRequest {
    pub kind: ActivationKind,
    pub alert_id: Option<String>,
}

impl ActivationRequest {
    /// Validating constructor: `alert_details` needs a non-empty alert id.
    pub fn new(kind: ActivationKind, alert_id: Option<String>) -> Option<Self> {
        if kind == ActivationKind::AlertDetails && alert_id.as_deref().is_none_or(str::is_empty) {
            return None;
        }
        Some(Self { kind, alert_id })
    }

    pub fn discussion() -> Self {
        Self {
            kind: ActivationKind::Discussion,
            alert_id: None,
        }
    }

    pub fn generic_fallback() -> Self {
        Self {
            kind: ActivationKind::GenericFallback,
            alert_id: None,
        }
    }

    pub fn alert_details(alert_id: impl Into<String>) -> Self {
        Self {
            kind: ActivationKind::AlertDetails,
            alert_id: Some(alert_id.into()),
        }
    }

    /// `serialize_activation_request`: one argv-safe token.
    pub fn serialize(&self) -> String {
        let mut s = format!(
            "{ACTIVATION_PREFIX}kind={}",
            py::quote_plus(self.kind.as_str())
        );
        if let Some(id) = self.alert_id.as_deref().filter(|id| !id.is_empty()) {
            s.push_str("&alert_id=");
            s.push_str(&py::quote_plus(id));
        }
        s
    }

    /// `extract_activation_request_from_argv`: the first token carrying the
    /// prefix decides (an invalid one yields `None`).
    pub fn from_argv<I, S>(argv: I) -> Option<Self>
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let arg = argv
            .into_iter()
            .find(|a| a.as_ref().starts_with(ACTIVATION_PREFIX))?;
        let pairs = py::parse_qsl(&arg.as_ref()[ACTIVATION_PREFIX.len()..]);
        let first = |key: &str| pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v.clone());
        let kind = ActivationKind::parse(&first("kind")?)?;
        Self::new(kind, first("alert_id"))
    }

    /// `json.dumps(asdict(request))`: what the handoff file and the single
    /// instance pipe carry.
    pub fn to_json(&self) -> String {
        py::json_dumps(&json!({"kind": self.kind.as_str(), "alert_id": self.alert_id}))
    }

    pub fn from_json(text: &str) -> Option<Self> {
        let payload: Value = serde_json::from_str(text).ok()?;
        let kind = ActivationKind::parse(payload.get("kind")?.as_str()?)?;
        let alert_id = payload
            .get("alert_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        Self::new(kind, alert_id)
    }
}

/// `RuntimeStoragePaths.activation_request_file`.
pub fn handoff_file(config_root: &Path) -> PathBuf {
    config_root.join("state").join(HANDOFF_FILE_NAME)
}

/// `write_activation_request_handoff`.
pub fn write_handoff(path: &Path, request: &ActivationRequest) -> bool {
    let text = request.to_json();
    let tmp = path.with_extension("tmp");
    let result = path
        .parent()
        .map_or(Ok(()), std::fs::create_dir_all)
        .and_then(|_| std::fs::write(&tmp, text))
        .and_then(|_| std::fs::rename(&tmp, path));
    match result {
        Ok(()) => true,
        Err(e) => {
            tracing::warn!("Failed to write activation handoff: {e}");
            let _ = std::fs::remove_file(&tmp);
            false
        }
    }
}

/// `consume_activation_request_handoff`: read and always delete the file.
pub fn consume_handoff(path: &Path) -> Option<ActivationRequest> {
    if !path.exists() {
        return None;
    }
    let request = std::fs::read_to_string(path)
        .ok()
        .and_then(|text| ActivationRequest::from_json(&text));
    if request.is_none() {
        tracing::warn!("Failed to consume activation handoff at {}", path.display());
    }
    let _ = std::fs::remove_file(path);
    request
}

/// Poll the handoff file on a background thread; requests arrive on the
/// returned channel. The thread stops once the receiver is dropped.
pub fn spawn_handoff_listener(path: PathBuf, interval: Duration) -> Receiver<ActivationRequest> {
    let (tx, rx) = mpsc::channel();
    std::thread::Builder::new()
        .name("AccessiWeatherActivationHandoff".into())
        .spawn(move || loop {
            std::thread::sleep(interval);
            if let Some(request) = consume_handoff(&path) {
                if tx.send(request).is_err() {
                    return;
                }
            }
        })
        .expect("spawning the activation handoff thread");
    rx
}

/// What the app should do for an activation (`_handle_notification_activation_request`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActivationRoute {
    /// Open the forecast discussion dialog without restoring the main window.
    OpenDiscussion,
    /// Show the details of the active alert at this index (in
    /// `WeatherAlerts::active` order) without restoring the main window.
    ShowAlertDetails(usize),
    /// The alert is no longer active: do nothing.
    Ignore,
    /// Restore and focus the main window.
    RestoreMainWindow,
}

pub fn route(
    request: &ActivationRequest,
    alerts: Option<&WeatherAlerts>,
    now: DateTime<Utc>,
) -> ActivationRoute {
    match request.kind {
        ActivationKind::Discussion => ActivationRoute::OpenDiscussion,
        ActivationKind::AlertDetails => {
            let Some(id) = request.alert_id.as_deref().filter(|id| !id.is_empty()) else {
                return ActivationRoute::RestoreMainWindow;
            };
            alerts
                .and_then(|a| {
                    a.active(now)
                        .iter()
                        .position(|alert| alert.unique_id() == id)
                })
                .map_or(ActivationRoute::Ignore, ActivationRoute::ShowAlertDetails)
        }
        ActivationKind::GenericFallback => ActivationRoute::RestoreMainWindow,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use aw_core::model::WeatherAlert;

    #[test]
    fn serialize_round_trips() {
        let request = ActivationRequest::alert_details("https://alerts.weather.gov/id/123");
        let token = request.serialize();
        assert_eq!(
            token,
            "accessiweather-toast:kind=alert_details&alert_id=https%3A%2F%2Falerts.weather.gov%2Fid%2F123"
        );
        assert_eq!(
            ActivationRequest::from_argv(["accessiweather.exe", &token]),
            Some(request)
        );
        let g = ActivationRequest::generic_fallback();
        assert_eq!(g.serialize(), "accessiweather-toast:kind=generic_fallback");
        assert_eq!(ActivationRequest::from_argv(["x", &g.serialize()]), Some(g));
    }

    #[test]
    fn invalid_tokens_are_ignored() {
        assert_eq!(ActivationRequest::from_argv(["app.exe", "--debug"]), None);
        assert_eq!(
            ActivationRequest::from_argv(["app.exe", "accessiweather-toast:kind=unknown_kind"]),
            None
        );
        assert_eq!(
            ActivationRequest::from_argv(["app.exe", "accessiweather-toast:kind=alert_details"]),
            None
        );
        assert!(ActivationRequest::new(ActivationKind::AlertDetails, None).is_none());
    }

    #[test]
    fn handoff_round_trips_and_cleans_up() {
        let dir = tempfile::tempdir().unwrap();
        let path = handoff_file(&dir.path().join("config"));
        assert_eq!(consume_handoff(&path), None);
        assert!(write_handoff(&path, &ActivationRequest::discussion()));
        assert_eq!(
            std::fs::read_to_string(&path).unwrap(),
            r#"{"kind": "discussion", "alert_id": null}"#
        );
        assert_eq!(
            consume_handoff(&path),
            Some(ActivationRequest::discussion())
        );
        assert!(!path.exists());
        std::fs::write(&path, "NOT JSON").unwrap();
        assert_eq!(consume_handoff(&path), None);
        assert!(!path.exists());
    }

    #[test]
    fn json_escapes_like_python_and_round_trips() {
        let request = ActivationRequest::alert_details("\u{e9}\"\u{1}");
        assert_eq!(
            request.to_json(),
            r#"{"kind": "alert_details", "alert_id": "\u00e9\"\u0001"}"#
        );
        assert_eq!(
            ActivationRequest::from_json(&request.to_json()),
            Some(request)
        );
        assert_eq!(
            ActivationRequest::from_json(r#"{"kind": "alert_details", "alert_id": ""}"#),
            None
        );
    }

    #[test]
    fn routes_like_the_app() {
        let now: DateTime<Utc> = "2026-09-25T12:00:00Z".parse().unwrap();
        let mut a = WeatherAlert::new("t", "d");
        a.id = Some("one".into());
        let mut b = a.clone();
        b.id = Some("two".into());
        let alerts = WeatherAlerts { alerts: vec![a, b] };
        assert_eq!(
            route(&ActivationRequest::alert_details("two"), Some(&alerts), now),
            ActivationRoute::ShowAlertDetails(1)
        );
        assert_eq!(
            route(
                &ActivationRequest::alert_details("gone"),
                Some(&alerts),
                now
            ),
            ActivationRoute::Ignore
        );
        assert_eq!(
            route(&ActivationRequest::discussion(), None, now),
            ActivationRoute::OpenDiscussion
        );
        assert_eq!(
            route(&ActivationRequest::generic_fallback(), None, now),
            ActivationRoute::RestoreMainWindow
        );
    }
}
