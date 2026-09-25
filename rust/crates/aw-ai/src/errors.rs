//! Error types, refusal detection and provider error mapping.
//!
//! Ports `ai_explainer_models.py` (exception classes, refusal check) and the
//! error mappers from `ai_provider.py` (`venice_error`, `openrouter_error`,
//! `ai_request_error`) and `ai_explainer_openrouter_client.py`
//! (`_call_openrouter`'s except block, `_describe_generation_error`).

use std::fmt;

use crate::provider::Provider;

/// The Python exception class an [`AiError`] corresponds to.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AiErrorKind {
    /// `AIExplainerError` (the base class).
    Explainer,
    InsufficientCredits,
    RateLimit,
    InvalidApiKey,
    ProviderPermission,
    InvalidModel,
    Network,
    Timeout,
    EmptyResponse,
    /// The caller cancelled the request; no message is shown.
    Cancelled,
}

/// A user-facing AI failure. `Display` is the message the UI shows.
#[derive(Debug, Clone, PartialEq)]
pub struct AiError {
    pub kind: AiErrorKind,
    pub message: String,
    /// Upstream status and text that Python still reaches through the
    /// exception's `__context__`; used only to describe a failed attempt.
    pub(crate) status: Option<u16>,
    pub(crate) context: String,
}

impl AiError {
    pub fn new(kind: AiErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
            status: None,
            context: String::new(),
        }
    }

    fn caused_by(mut self, cause: &TransportError) -> Self {
        self.status = cause.status();
        self.context = cause.context();
        self
    }

    /// Key, permission and credit failures stop the fallback chain.
    pub fn is_fatal(&self) -> bool {
        matches!(
            self.kind,
            AiErrorKind::InvalidApiKey
                | AiErrorKind::ProviderPermission
                | AiErrorKind::InsufficientCredits
        )
    }
}

impl fmt::Display for AiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for AiError {}

/// A request failure before it is mapped to a user-facing message.
#[derive(Debug, Clone, PartialEq)]
pub enum TransportError {
    /// The service answered with an HTTP error status.
    Status {
        status: u16,
        body: String,
    },
    /// An `error` object arrived inside a streamed response.
    Api {
        code: Option<String>,
        message: String,
    },
    /// The HTTP client's own timeout (connect or read).
    Timeout,
    /// The service could not be reached, or the connection broke.
    Connect,
    /// A [`crate::transport::StreamLimits`] limit expired; the text is shown as is.
    Deadline(String),
    Cancelled,
    /// Unreadable response.
    Other,
}

impl TransportError {
    fn status(&self) -> Option<u16> {
        match self {
            Self::Status { status, .. } => Some(*status),
            _ => None,
        }
    }

    /// The text Python's `_extract_api_error_details` and `str(error)` yield.
    fn context(&self) -> String {
        match self {
            Self::Status { status, body } => format!("{status} Error code: {status} - {body}"),
            Self::Api { code, message } => {
                format!("{} {message} {message}", code.as_deref().unwrap_or(""))
            }
            Self::Timeout => "Request timed out. Request timed out.".into(),
            Self::Connect => "Connection error. Connection error.".into(),
            Self::Deadline(_) | Self::Cancelled | Self::Other => String::new(),
        }
    }

    /// Deadline and cancellation carry their own outcome through every mapper.
    fn passthrough(&self) -> Option<AiError> {
        match self {
            Self::Deadline(message) => Some(AiError::new(AiErrorKind::Timeout, message.clone())),
            Self::Cancelled => Some(AiError::new(AiErrorKind::Cancelled, "Request cancelled.")),
            _ => None,
        }
    }
}

pub const MODEL_REFUSAL_MESSAGE: &str = "The selected model declined this request. Choose another model or revise your custom prompt in Settings > AI.";

const REFUSAL_PREFIXES: [&str; 7] = [
    "i'm sorry, but i can't help with that",
    "sorry, i can't help with that",
    "i can't help with this request",
    "i cannot help with this request",
    "i can't assist with that",
    "i cannot assist with that",
    "i cannot fulfill this request",
];

/// Recognize short, explicit refusals without classifying ordinary weather text.
pub fn is_model_refusal(content: &str) -> bool {
    let folded = crate::pyfmt::casefold(content).replace('\u{2019}', "'");
    let text = folded.split_whitespace().collect::<Vec<_>>().join(" ");
    text.chars().count() < 180 && REFUSAL_PREFIXES.iter().any(|p| text.starts_with(p))
}

/// `venice_error`: map failures without exposing response bodies or credentials.
pub fn venice_error(error: &TransportError) -> AiError {
    if let Some(passed) = error.passthrough() {
        return passed;
    }
    use AiErrorKind::*;
    let (kind, message) = match (error, error.status()) {
        (_, Some(401)) => (
            InvalidApiKey,
            "Venice rejected this API key. It may be invalid or expired. Check your Venice key in Settings > AI.",
        ),
        (_, Some(403)) => (
            ProviderPermission,
            "Venice denied permission for this request. Check your key and account permissions. This does not establish that your key is invalid.",
        ),
        (_, Some(402)) => (
            InsufficientCredits,
            "Your Venice account has insufficient API credits. Add prepaid USD credits in your Venice account, then try again.",
        ),
        (_, Some(429)) => (RateLimit, "Venice rate limit reached. Wait a moment and try again."),
        (_, Some(404)) => (
            InvalidModel,
            "The selected Venice model is unavailable. Check Settings > AI.",
        ),
        (TransportError::Timeout, _) => (Timeout, "Venice request timed out. Please try again."),
        (TransportError::Connect, _) => (
            Network,
            "Could not reach Venice. Check your internet connection and try again.",
        ),
        (_, Some(s)) if s >= 500 => (
            Network,
            "Venice is temporarily unavailable. Please try again later.",
        ),
        _ => (
            Explainer,
            "Venice could not complete the request. Check your selected model and try again.",
        ),
    };
    AiError::new(kind, message).caused_by(error)
}

/// `openrouter_error`: map a completion failure without showing upstream text.
pub fn openrouter_error(error: &TransportError) -> AiError {
    if let Some(passed) = error.passthrough() {
        return passed;
    }
    use AiErrorKind::*;
    let (kind, message) = match (error, error.status()) {
        (_, Some(401)) => (
            InvalidApiKey,
            "OpenRouter could not authenticate this request. Validate your key in Settings > AI.",
        ),
        (_, Some(402)) => (
            InsufficientCredits,
            "Your OpenRouter account has insufficient credits for this request. Add credits or choose a free model in Settings > AI.",
        ),
        (_, Some(403)) => (
            ProviderPermission,
            "OpenRouter denied this request. Check your account and model permissions. This does not establish that your key is invalid.",
        ),
        (_, Some(404)) => (
            InvalidModel,
            "The selected OpenRouter model is unavailable. Choose another model in Settings > AI.",
        ),
        (_, Some(429)) => (
            RateLimit,
            "OpenRouter rate limit reached. Wait a moment and try again.",
        ),
        (TransportError::Timeout, _) => (
            Timeout,
            "OpenRouter request timed out. Please try again.",
        ),
        (TransportError::Connect, _) => (
            Network,
            "Could not reach OpenRouter. Check your internet connection and try again.",
        ),
        (_, Some(s)) if s >= 500 => (
            Network,
            "OpenRouter is temporarily unavailable. Please try again later.",
        ),
        _ => (
            Explainer,
            "OpenRouter could not complete the request. Check your selected model and try again.",
        ),
    };
    AiError::new(kind, message).caused_by(error)
}

/// `ai_request_error`: the safe message for any failure of `provider`.
pub fn ai_request_error(error: &TransportError, provider: Provider) -> AiError {
    match provider {
        Provider::Venice => venice_error(error),
        Provider::OpenRouter => openrouter_error(error),
    }
}

/// `_call_openrouter`'s mapping of an explanation request failure for `model`.
pub fn openrouter_generation_error(error: &TransportError, model: &str) -> AiError {
    if let Some(passed) = error.passthrough() {
        return passed;
    }
    use AiErrorKind::*;
    let status = error.status();
    if status == Some(403) {
        return AiError::new(
            ProviderPermission,
            "OpenRouter denied this generation request. The model, provider, or account permissions may restrict access. This does not establish that your key is invalid.",
        )
        .caused_by(error);
    }
    if status == Some(401) {
        return AiError::new(
            InvalidApiKey,
            "OpenRouter could not authenticate this generation request. Validate your key in Settings; model or provider access may also need checking.",
        )
        .caused_by(error);
    }
    // Structured statuses take priority over arbitrary upstream error prose.
    let text = match status {
        Some(s) => s.to_string(),
        None => error.context().to_lowercase(),
    };
    let has = |needle: &str| text.contains(needle);
    let (kind, message) = if has("api key required") || has("api key") {
        (
            InvalidApiKey,
            "OpenRouter API key is required.\n\nPlease add your API key in Settings > AI.\nGet a free key at: openrouter.ai/keys".to_string(),
        )
    } else if has("invalid api key") || has("authentication") {
        (
            InvalidApiKey,
            "Your OpenRouter API key is invalid.\n\nPlease check Settings > AI and verify your API key.\nGet a free key at: openrouter.ai/keys".to_string(),
        )
    } else if has("401") || has("unauthorized") {
        (
            InvalidApiKey,
            "API key authentication failed.\n\nYour API key may be expired or incorrectly entered.\nPlease check Settings > AI.".to_string(),
        )
    } else if status == Some(402) || has("insufficient") || has("no credits") {
        (
            InsufficientCredits,
            "Your OpenRouter account has no funds.\n\nOptions:\n• Add credits at openrouter.ai/credits\n• Switch to a free model in Settings > AI".to_string(),
        )
    } else if status == Some(429)
        || has("429")
        || has("rate limit")
        || has("rate_limit")
        || has("too many requests")
        || has("rate-limited")
    {
        let detail = if model.contains(":free") {
            "Free models share rate limits with all users and may be busy.\n\nOptions:\n• Wait a few minutes and try again\n• Add credits to get your own rate limit\n• Switch to a paid model for faster access"
        } else {
            "Please wait a few minutes and try again."
        };
        (RateLimit, format!("Rate limit exceeded.\n\n{detail}"))
    } else if has("timed out") || has("timeout") {
        (
            Timeout,
            "Request timed out.\n\nThe AI service is taking too long to respond.\nThis usually means the servers are busy. Please try again.".to_string(),
        )
    } else if matches!(status, Some(502 | 503))
        || has("502")
        || has("503")
        || has("network error")
        || has("connection refused")
        || has("connection reset")
    {
        (
            Network,
            "Network connection error.\n\nCould not reach the AI service. This is usually temporary.\nPlease check your internet connection and try again.".to_string(),
        )
    } else if status == Some(404)
        || has("404")
        || has("not found")
        || has("no endpoints found")
        || has("does not exist")
    {
        (
            InvalidModel,
            format!(
                "The AI model '{model}' was not found.\n\nIt may have been removed or renamed by OpenRouter.\nPlease go to Settings > AI and select a different model."
            ),
        )
    } else {
        tracing::error!("OpenRouter generation request failed");
        (
            Explainer,
            "Unable to generate explanation.\n\nIf this persists, try:\n• Checking your internet connection\n• Selecting a different AI model in Settings\n• Trying again in a few minutes".to_string(),
        )
    };
    AiError::new(kind, message).caused_by(error)
}

/// `_describe_generation_error`: a short, non-technical reason for a failed attempt.
pub fn describe_generation_error(error: &AiError) -> &'static str {
    let text = format!("{} {}", error.context, error.message).to_lowercase();
    let has = |needle: &str| text.contains(needle);
    if error.status == Some(429)
        || has("429")
        || has("rate limit")
        || has("rate_limit")
        || has("rate-limited")
        || has("too many requests")
    {
        "rate limits"
    } else if has("timed out") || has("timeout") {
        "a timeout"
    } else if error.status == Some(404) || has("404") || has("not found") || has("does not exist") {
        "the model was unavailable"
    } else if has("empty") || has("short") || has("insufficient") {
        "an empty response"
    } else {
        "a service error"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn status(code: u16) -> TransportError {
        TransportError::Status {
            status: code,
            body: "secret-key upstream response".into(),
        }
    }

    #[test]
    fn refusals_are_short_explicit_and_typography_insensitive() {
        assert!(is_model_refusal(
            "I\u{2019}m sorry, but I can\u{2019}t help with that."
        ));
        assert!(is_model_refusal("  I cannot   assist with that request."));
        assert!(!is_model_refusal("Sorry, the forecast calls for rain."));
        let long = format!("I can't assist with that. {}", "x".repeat(200));
        assert!(!is_model_refusal(&long));
    }

    #[test]
    fn assistant_status_errors_are_specific_and_redacted() {
        for (code, kind, expected) in [
            (401, AiErrorKind::InvalidApiKey, "authenticate"),
            (402, AiErrorKind::InsufficientCredits, "credits"),
            (403, AiErrorKind::ProviderPermission, "permission"),
            (404, AiErrorKind::InvalidModel, "model"),
            (429, AiErrorKind::RateLimit, "rate limit"),
            (503, AiErrorKind::Network, "temporarily unavailable"),
        ] {
            let mapped = openrouter_error(&status(code));
            assert_eq!(mapped.kind, kind);
            assert!(mapped.message.to_lowercase().contains(expected));
            assert!(!mapped.message.contains("secret"));
        }
        assert!(openrouter_error(&TransportError::Timeout)
            .message
            .contains("timed out"));
        assert!(openrouter_error(&TransportError::Connect)
            .message
            .contains("internet connection"));
        assert!(openrouter_error(&TransportError::Other)
            .message
            .contains("could not complete"));
    }

    #[test]
    fn venice_failures_map_by_status() {
        for (code, kind) in [
            (401, AiErrorKind::InvalidApiKey),
            (403, AiErrorKind::ProviderPermission),
            (402, AiErrorKind::InsufficientCredits),
            (429, AiErrorKind::RateLimit),
            (503, AiErrorKind::Network),
        ] {
            assert_eq!(venice_error(&status(code)).kind, kind);
        }
        let network = venice_error(&TransportError::Connect);
        assert_eq!(network.kind, AiErrorKind::Network);
    }

    #[test]
    fn generation_errors_prefer_structured_status() {
        let limited = openrouter_generation_error(&status(429), "vendor/model:free");
        assert_eq!(limited.kind, AiErrorKind::RateLimit);
        assert!(limited.message.contains("Free models share rate limits"));
        assert_eq!(describe_generation_error(&limited), "rate limits");
        let missing = openrouter_generation_error(&status(404), "gone/model");
        assert!(missing.message.contains("'gone/model' was not found"));
        let midstream = TransportError::Api {
            code: Some("502".into()),
            message: "Provider returned error".into(),
        };
        assert_eq!(
            openrouter_generation_error(&midstream, "m").kind,
            AiErrorKind::Network
        );
        let generic = openrouter_generation_error(&TransportError::Connect, "m");
        assert!(generic
            .message
            .starts_with("Unable to generate explanation."));
        let deadline =
            TransportError::Deadline("The AI model stopped answering for 15 seconds.".into());
        let passed = openrouter_generation_error(&deadline, "m");
        assert_eq!(passed.kind, AiErrorKind::Timeout);
        assert_eq!(describe_generation_error(&passed), "a service error");
    }
}
