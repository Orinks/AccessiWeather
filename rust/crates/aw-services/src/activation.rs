//! Activation requests handed from a second launch (or a toast click) to the
//! running instance (`notification_activation.py`, the handoff-file half of
//! `app_activation.py`).
//!
//! The handoff file `<config>/state/activation_request.json` has Python's
//! exact format, so either edition can pick up a request the other wrote.

use std::path::{Path, PathBuf};
use std::time::Duration;

use serde_json::Value;

/// Prefix of the argv token Windows passes when a toast is clicked.
pub const ACTIVATION_PREFIX: &str = "accessiweather-toast:";

/// How often the running instance polls the handoff file.
pub const HANDOFF_POLL_INTERVAL: Duration = Duration::from_millis(2000);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActivationKind {
    Discussion,
    AlertDetails,
    GenericFallback,
}

impl ActivationKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Discussion => "discussion",
            Self::AlertDetails => "alert_details",
            Self::GenericFallback => "generic_fallback",
        }
    }

    fn parse(text: &str) -> Option<Self> {
        match text {
            "discussion" => Some(Self::Discussion),
            "alert_details" => Some(Self::AlertDetails),
            "generic_fallback" => Some(Self::GenericFallback),
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
    /// Validated like Python's `__post_init__`: a known kind, and an alert id
    /// for `alert_details`.
    pub fn new(kind: &str, alert_id: Option<String>) -> Option<Self> {
        let kind = ActivationKind::parse(kind)?;
        if kind == ActivationKind::AlertDetails && alert_id.as_deref().is_none_or(str::is_empty) {
            return None;
        }
        Some(Self { kind, alert_id })
    }

    pub fn generic_fallback() -> Self {
        Self {
            kind: ActivationKind::GenericFallback,
            alert_id: None,
        }
    }

    /// One argv-safe token (`serialize_activation_request`).
    pub fn to_token(&self) -> String {
        let mut pairs = vec![("kind", self.kind.as_str())];
        if let Some(id) = self.alert_id.as_deref().filter(|id| !id.is_empty()) {
            pairs.push(("alert_id", id));
        }
        format!("{ACTIVATION_PREFIX}{}", crate::urlencode(&pairs))
    }

    /// The first activation token in `argv` (`extract_activation_request_from_argv`).
    pub fn from_argv<S: AsRef<str>>(argv: &[S]) -> Option<Self> {
        let token = argv
            .iter()
            .find_map(|a| a.as_ref().strip_prefix(ACTIVATION_PREFIX))?;
        let first = |key: &str| {
            token
                .split('&')
                .filter_map(|pair| pair.split_once('='))
                .map(|(k, v)| (crate::unquote_plus(k), crate::unquote_plus(v)))
                .find(|(k, v)| k == key && !v.is_empty())
                .map(|(_, v)| v)
        };
        Self::new(&first("kind")?, first("alert_id"))
    }

    /// `json.dumps(asdict(request))`.
    pub fn to_json(&self) -> String {
        let alert_id = self
            .alert_id
            .as_deref()
            .map_or("null".to_string(), py_json_string);
        format!(
            "{{\"kind\": {}, \"alert_id\": {alert_id}}}",
            py_json_string(self.kind.as_str())
        )
    }

    pub fn from_json(text: &str) -> Option<Self> {
        let payload: Value = serde_json::from_str(text).ok()?;
        let kind = payload.get("kind").and_then(Value::as_str).unwrap_or("");
        let alert_id = payload
            .get("alert_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        Self::new(kind, alert_id)
    }
}

/// A JSON string literal as Python's `json.dumps` writes it (`ensure_ascii`).
fn py_json_string(text: &str) -> String {
    let mut out = String::from("\"");
    for c in text.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\x08' => out.push_str("\\b"),
            '\x0c' => out.push_str("\\f"),
            c if (c as u32) < 0x20 || (c as u32) > 0x7e => {
                for unit in c.encode_utf16(&mut [0; 2]) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// `RuntimeStoragePaths.activation_request_file`.
pub fn activation_request_file(config_dir: &Path) -> PathBuf {
    config_dir.join("state").join("activation_request.json")
}

/// Write a request for the running instance (temp file + replace).
pub fn write_handoff(config_dir: &Path, request: &ActivationRequest) -> bool {
    let file = activation_request_file(config_dir);
    let tmp = file.with_extension("tmp");
    let result = file
        .parent()
        .map_or(Ok(()), std::fs::create_dir_all)
        .and_then(|()| std::fs::write(&tmp, request.to_json()))
        .and_then(|()| std::fs::rename(&tmp, &file));
    if let Err(e) = result {
        tracing::warn!("Failed to write activation handoff: {e}");
        let _ = std::fs::remove_file(&tmp);
        return false;
    }
    true
}

/// Read and delete a pending request; an unreadable file is deleted too.
pub fn consume_handoff(config_dir: &Path) -> Option<ActivationRequest> {
    let file = activation_request_file(config_dir);
    if !file.exists() {
        return None;
    }
    let request = std::fs::read_to_string(&file)
        .ok()
        .and_then(|text| ActivationRequest::from_json(&text));
    if request.is_none() {
        tracing::warn!("Failed to consume activation handoff: invalid request");
    }
    let _ = std::fs::remove_file(&file);
    request
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_round_trips() {
        let req = ActivationRequest::new("alert_details", Some("urn:oid:2.49 x&y".into())).unwrap();
        let token = req.to_token();
        assert_eq!(
            token,
            "accessiweather-toast:kind=alert_details&alert_id=urn%3Aoid%3A2.49+x%26y"
        );
        assert_eq!(
            ActivationRequest::from_argv(&["app.exe", &token]),
            Some(req)
        );
        assert_eq!(
            ActivationRequest::generic_fallback().to_token(),
            "accessiweather-toast:kind=generic_fallback"
        );
    }

    #[test]
    fn invalid_tokens_are_ignored() {
        assert!(ActivationRequest::from_argv(&["--debug"]).is_none());
        assert!(ActivationRequest::from_argv(&["accessiweather-toast:kind=bogus"]).is_none());
        assert!(
            ActivationRequest::from_argv(&["accessiweather-toast:kind=alert_details"]).is_none()
        );
        assert!(ActivationRequest::new("alert_details", Some(String::new())).is_none());
    }

    #[test]
    fn handoff_file_round_trips_and_is_consumed() {
        let dir = tempfile::tempdir().unwrap();
        assert!(consume_handoff(dir.path()).is_none());
        let req = ActivationRequest::new("discussion", None).unwrap();
        assert!(write_handoff(dir.path(), &req));
        let file = activation_request_file(dir.path());
        assert_eq!(
            std::fs::read_to_string(&file).unwrap(),
            r#"{"kind": "discussion", "alert_id": null}"#
        );
        assert_eq!(consume_handoff(dir.path()), Some(req));
        assert!(!file.exists());

        std::fs::write(&file, "not json").unwrap();
        assert!(consume_handoff(dir.path()).is_none());
        assert!(!file.exists());
    }

    #[test]
    fn json_escapes_like_python() {
        let req = ActivationRequest::new("alert_details", Some("é\"\u{1}".into())).unwrap();
        assert_eq!(
            req.to_json(),
            r#"{"kind": "alert_details", "alert_id": "\u00e9\"\u0001"}"#
        );
    }
}
