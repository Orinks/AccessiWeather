//! Provider selection and key validation.
//!
//! Ports `ai_settings.py`, the constants of `ai_provider.py` and
//! `ai_explainer_openrouter.py`, `validate_venice_api_key` (`ai_provider.py`)
//! and `validate_openrouter_api_key` (`ai_explainer_validation.py`).

use std::time::Duration;

use aw_core::settings::AppSettings;
use serde_json::Value;

use crate::errors::{venice_error, AiError, AiErrorKind, TransportError};
use crate::transport;

pub const OPENROUTER_BASE_URL: &str = "https://openrouter.ai/api/v1";
pub const VENICE_BASE_URL: &str = "https://api.venice.ai/api/v1";
pub const DEFAULT_FREE_MODEL: &str = "openrouter/free";
pub const DEFAULT_PAID_MODEL: &str = "openrouter/auto";
pub const DEFAULT_VENICE_MODEL: &str = "venice-uncensored-1-2";

const VALIDATION_TIMEOUT: Duration = Duration::from_secs(15);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Provider {
    OpenRouter,
    Venice,
}

impl Provider {
    /// The value stored in `AppSettings::ai_provider`.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::OpenRouter => "openrouter",
            Self::Venice => "venice",
        }
    }

    pub fn base_url(self) -> &'static str {
        match self {
            Self::OpenRouter => OPENROUTER_BASE_URL,
            Self::Venice => VENICE_BASE_URL,
        }
    }
}

/// `selected_provider`: validate the choice rather than silently switching services.
pub fn selected_provider(settings: &AppSettings) -> Result<Provider, AiError> {
    match settings.ai_provider.as_str() {
        "openrouter" => Ok(Provider::OpenRouter),
        "venice" => Ok(Provider::Venice),
        _ => Err(AiError::new(
            AiErrorKind::Explainer,
            "Unknown AI provider. Choose a provider in Settings > AI.",
        )),
    }
}

/// `selected_model`: the model saved for the active provider.
pub fn selected_model(settings: &AppSettings) -> Result<String, AiError> {
    Ok(match selected_provider(settings)? {
        Provider::Venice if settings.venice_model.is_empty() => DEFAULT_VENICE_MODEL.into(),
        Provider::Venice => settings.venice_model.clone(),
        Provider::OpenRouter => match settings.ai_model_preference.as_str() {
            "auto" => DEFAULT_PAID_MODEL.into(),
            "" => DEFAULT_FREE_MODEL.into(),
            model => model.into(),
        },
    })
}

/// `selected_key`: only the selected provider's key.
pub fn selected_key(settings: &AppSettings) -> Result<String, AiError> {
    Ok(match selected_provider(settings)? {
        Provider::OpenRouter => settings.openrouter_api_key.clone(),
        Provider::Venice => settings.venice_api_key.clone(),
    })
}

/// The startup check in `app_initialization.py`: the OpenRouter model that
/// should be looked up in the catalog (see
/// [`crate::models::validate_and_get_fallback`]), if any.
pub fn startup_model_to_validate(settings: &AppSettings) -> Option<&str> {
    let model = settings.ai_model_preference.as_str();
    if settings.ai_provider != "openrouter"
        || model.is_empty()
        || model == "auto"
        || model == DEFAULT_PAID_MODEL
        || settings.openrouter_api_key.is_empty()
    {
        return None;
    }
    Some(model)
}

/// Check an OpenRouter key without generating text or exposing remote error
/// details. Returns `(valid, message)`.
pub fn validate_openrouter_api_key(api_key: &str) -> (bool, String) {
    validate_openrouter_api_key_at(OPENROUTER_BASE_URL, api_key)
}

pub(crate) fn validate_openrouter_api_key_at(base_url: &str, api_key: &str) -> (bool, String) {
    let key = api_key.trim();
    if key.is_empty() {
        return (false, "Please enter your OpenRouter API key first.".into());
    }
    let response = match transport::get(&format!("{base_url}/key"), Some(key), VALIDATION_TIMEOUT) {
        Ok(response) => response,
        Err(TransportError::Timeout) => {
            return (
                false,
                "OpenRouter key validation timed out. Please try again.".into(),
            )
        }
        Err(_) => {
            return (
                false,
                "Could not reach OpenRouter. Check your connection and try again.".into(),
            )
        }
    };
    let message = match response.status {
        200 => {
            let remaining = serde_json::from_str::<Value>(&response.body)
                .ok()
                .and_then(|payload| payload.get("data")?.get("limit_remaining")?.as_f64());
            return if remaining.is_some_and(|r| r <= 0.0) {
                (true, "OpenRouter API key is valid, but its spending allowance is exhausted. Paid models may fail; free models may still work.".into())
            } else {
                (true, "OpenRouter API key is valid. Account credits and model access are checked when you use a model.".into())
            };
        }
        401 => "OpenRouter rejected this API key. Check your key and try again.",
        403 => "OpenRouter denied access. Check your key and account permissions.",
        429 => "OpenRouter rate limit reached. Wait a moment and try validation again.",
        _ => "OpenRouter key validation is unavailable. Please try again later.",
    };
    (false, message.into())
}

/// Validate a Venice key with an authenticated read that spends no credits.
/// Returns `(valid, message)`.
pub fn validate_venice_api_key(api_key: &str) -> (bool, String) {
    validate_venice_api_key_at(VENICE_BASE_URL, api_key)
}

pub(crate) fn validate_venice_api_key_at(base_url: &str, api_key: &str) -> (bool, String) {
    let key = api_key.trim();
    if key.is_empty() {
        return (
            false,
            "A Venice API key is required. Add your own key in Settings > AI.".into(),
        );
    }
    let url = format!("{base_url}/api_keys/rate_limits");
    let data = match transport::get(&url, Some(key), VALIDATION_TIMEOUT) {
        Err(error) => return (false, venice_error(&error).message),
        Ok(response) if response.status >= 400 => {
            let error = TransportError::Status {
                status: response.status,
                body: String::new(),
            };
            return (false, venice_error(&error).message);
        }
        Ok(response) => match serde_json::from_str::<Value>(&response.body)
            .ok()
            .and_then(|payload| payload.get("data").cloned())
            .filter(Value::is_object)
        {
            Some(data) => data,
            None => return (false, venice_error(&TransportError::Other).message),
        },
    };
    if data.get("accessPermitted") == Some(&Value::Bool(false)) {
        return (
            false,
            "Your Venice key is recognized but API access is not permitted. Check your Venice account.".into(),
        );
    }
    let no_positive_balance =
        data.get("balances")
            .and_then(Value::as_object)
            .is_some_and(|balances| {
                ["USD", "DIEM", "BUNDLED_CREDITS"]
                    .iter()
                    .all(|k| balances.contains_key(*k))
                    && balances
                        .values()
                        .all(|v| v.as_f64().is_some_and(|amount| amount <= 0.0))
            });
    if no_positive_balance {
        (true, "Venice API key verified, but no positive balance is listed. Generation may require credits; other credit types may still apply.".into())
    } else {
        (
            true,
            "Venice API key verified. Generating responses uses your account's API credits.".into(),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_server::{Reply, TestServer};
    use serde_json::json;

    fn settings(provider: &str) -> AppSettings {
        let mut s: AppSettings = serde_json::from_str("{}").unwrap();
        s.ai_provider = provider.into();
        s.openrouter_api_key = "or-key".into();
        s.venice_api_key = "v-key".into();
        s
    }

    #[test]
    fn routing_never_borrows_the_other_providers_key_or_model() {
        let mut s = settings("venice");
        s.ai_model_preference = "vendor/model".into();
        assert_eq!(selected_key(&s).unwrap(), "v-key");
        assert_eq!(selected_model(&s).unwrap(), DEFAULT_VENICE_MODEL);
        s.ai_provider = "openrouter".into();
        assert_eq!(selected_key(&s).unwrap(), "or-key");
        assert_eq!(selected_model(&s).unwrap(), "vendor/model");
        s.ai_model_preference = "auto".into();
        assert_eq!(selected_model(&s).unwrap(), DEFAULT_PAID_MODEL);
        s.ai_provider = "other".into();
        assert!(selected_provider(&s)
            .unwrap_err()
            .message
            .contains("Unknown AI provider"));
    }

    #[test]
    fn startup_validation_skips_defaults_and_missing_keys() {
        let mut s = settings("openrouter");
        s.ai_model_preference = "vendor/model".into();
        assert_eq!(startup_model_to_validate(&s), Some("vendor/model"));
        s.ai_model_preference = "openrouter/auto".into();
        assert_eq!(startup_model_to_validate(&s), None);
        s.ai_model_preference = "vendor/model".into();
        s.openrouter_api_key.clear();
        assert_eq!(startup_model_to_validate(&s), None);
    }

    #[test]
    fn openrouter_key_check_uses_auth_endpoint_and_safe_messages() {
        let cases = [
            (
                Reply::json(200, json!({"data": {"limit_remaining": 5}})),
                true,
                "is valid. Account credits",
            ),
            (
                Reply::json(200, json!({"data": {"limit_remaining": 0}})),
                true,
                "allowance is exhausted",
            ),
            (
                Reply::json(200, json!({"data": {"limit_remaining": null}})),
                true,
                "is valid. Account credits",
            ),
            (
                Reply::text(401, "private-response-secret"),
                false,
                "rejected this API key",
            ),
            (Reply::text(403, "x"), false, "denied access"),
            (Reply::text(429, "x"), false, "rate limit reached"),
            (Reply::text(500, "x"), false, "unavailable"),
        ];
        for (reply, valid, phrase) in cases {
            let server = TestServer::start(vec![reply]);
            let (ok, message) = validate_openrouter_api_key_at(&server.url(), " test-key ");
            assert_eq!(ok, valid, "{message}");
            assert!(message.contains(phrase), "{message}");
            assert!(!message.contains("secret"));
            let request = &server.requests()[0];
            assert_eq!(request.method, "GET");
            assert_eq!(request.path, "/key");
            assert_eq!(request.header("authorization"), Some("Bearer test-key"));
        }
        assert_eq!(
            validate_openrouter_api_key("  ").1,
            "Please enter your OpenRouter API key first."
        );
        let (ok, message) = validate_openrouter_api_key_at("http://127.0.0.1:9", "k");
        assert!(!ok && message.contains("Could not reach OpenRouter"));
    }

    #[test]
    fn venice_validation_reports_only_known_balance_shortfall() {
        let cases = [
            (json!({"USD": 0, "DIEM": 0, "BUNDLED_CREDITS": 0}), true),
            (json!({"USD": 0, "DIEM": 0, "BUNDLED_CREDITS": 2}), false),
            (json!({"USD": 0, "DIEM": 0}), false),
            (
                json!({"USD": 0, "DIEM": 0, "BUNDLED_CREDITS": 0, "OTHER": 3}),
                false,
            ),
            (json!({"USD": null, "DIEM": 0, "BUNDLED_CREDITS": 0}), false),
            (
                json!({"USD": false, "DIEM": 0, "BUNDLED_CREDITS": 0}),
                false,
            ),
            (json!({}), false),
            (Value::Null, false),
        ];
        for (balances, shortfall) in cases {
            let server = TestServer::start(vec![Reply::json(
                200,
                json!({"data": {"accessPermitted": true, "balances": balances}}),
            )]);
            let (ok, message) = validate_venice_api_key_at(&server.url(), "test-key");
            assert!(ok);
            assert_eq!(message.contains("no positive balance is listed"), shortfall);
            let request = &server.requests()[0];
            assert_eq!(request.path, "/api_keys/rate_limits");
            assert_eq!(request.header("authorization"), Some("Bearer test-key"));
        }
    }

    #[test]
    fn venice_validation_distinguishes_rejection_denial_and_permission() {
        let server = TestServer::start(vec![Reply::json(
            200,
            json!({"data": {"accessPermitted": false, "balances": {"USD": 0, "DIEM": 0}}}),
        )]);
        let (ok, message) = validate_venice_api_key_at(&server.url(), "k");
        assert!(!ok && message.contains("not permitted"));
        for (status, phrase) in [(401, "rejected this API key"), (403, "denied permission")] {
            let server = TestServer::start(vec![Reply::text(status, "private-response-secret")]);
            let (ok, message) = validate_venice_api_key_at(&server.url(), "test-secret-key");
            assert!(!ok && message.contains(phrase), "{message}");
            assert!(!message.contains("secret"));
        }
        assert!(validate_venice_api_key("")
            .1
            .contains("A Venice API key is required"));
    }
}
