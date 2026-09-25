//! Plain-language summaries of text products, the single seam between the
//! Forecaster Notes panels and the AI backend. Port of
//! `ui/dialogs/forecast_product_ai.py` and the generation half of
//! `ForecastProductPanel._run_explain`.
//!
//! Integration (AI workstream): replace the body of [`explain_text_product`]
//! with `AIExplainer(**explainer_options(settings)).explain_text_product(...)`,
//! reporting progress through `status` and returning errors already passed
//! through `ai_request_error`. Nothing else in the dialogs needs to change.

use aw_core::settings::AppSettings;

/// Shown when no explainer can be built for the selected provider.
pub(crate) const NOT_CONFIGURED: &str =
    "Selected AI provider API key not configured. Set it in Settings > AI.";

/// The parts of Python's `ExplanationResult` the panel shows.
#[derive(Debug, Clone, Default, PartialEq)]
#[cfg_attr(test, derive(serde::Deserialize))]
pub(crate) struct Summary {
    pub text: String,
    pub model_used: String,
    pub token_count: i64,
    /// `None` when the provider does not report a cost.
    pub estimated_cost: Option<f64>,
    pub cached: bool,
    pub model_selection_reason: Option<String>,
    pub requested_model: Option<String>,
    pub model_attempts: Vec<String>,
}

/// `has_openrouter_key` (`ai_settings.selected_key`): the selected provider
/// has an API key. An unknown provider counts as no key.
pub(crate) fn has_selected_key(settings: &AppSettings) -> bool {
    match settings.ai_provider.as_str() {
        "openrouter" => !settings.openrouter_api_key.is_empty(),
        "venice" => !settings.venice_api_key.is_empty(),
        _ => false,
    }
}

/// Summarise `text` (blocking; call on a worker thread). `status` receives
/// model-selection progress. `Err` carries the message the panel shows after
/// "Failed to generate summary: ".
pub(crate) fn explain_text_product(
    settings: &AppSettings,
    text: &str,
    product_type: &str,
    location_name: &str,
    status: &dyn Fn(String),
) -> Result<Summary, String> {
    let _ = (settings, text, product_type, location_name, status);
    Err(NOT_CONFIGURED.to_string())
}
