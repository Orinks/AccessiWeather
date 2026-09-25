//! Plain-language summaries of text products, the single seam between the
//! Forecaster Notes panels and the AI backend. Port of
//! `ui/dialogs/forecast_product_ai.py` and the generation half of
//! `ForecastProductPanel._run_explain`.

use std::sync::Arc;

use aw_ai::{AiExplainer, CancelToken, ExplanationCache, ExplanationStyle};
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
///
/// Unlike Python (whose explainer never gets a cache), summaries go through
/// the app's shared explanation cache, so reopening a product answers
/// instantly; `regenerate` drops the cached entry first. `cancel` drops the
/// request once the panel closes.
#[allow(clippy::too_many_arguments)]
pub(crate) fn explain_text_product(
    settings: &AppSettings,
    cache: Arc<ExplanationCache>,
    regenerate: bool,
    text: &str,
    product_type: &str,
    location_name: &str,
    status: &dyn Fn(String),
    cancel: &CancelToken,
) -> Result<Summary, String> {
    let Ok(explainer) = AiExplainer::from_settings(settings) else {
        return Err(NOT_CONFIGURED.to_string());
    };
    let explainer = explainer.with_cache(cache.clone());
    if regenerate {
        cache.remove(&explainer.text_product_cache_key(
            product_type,
            location_name,
            text,
            ExplanationStyle::Detailed,
        ));
    }
    let result = explainer
        .explain_text_product(
            text,
            product_type,
            location_name,
            ExplanationStyle::Detailed,
            false,
            &|message| status(message.to_string()),
            Some(cancel),
        )
        .map_err(|e| e.message)?;
    Ok(Summary {
        text: result.text,
        model_used: result.model_used,
        token_count: result.token_count as i64,
        estimated_cost: result.estimated_cost,
        cached: result.cached,
        model_selection_reason: result.model_selection_reason,
        requested_model: result.requested_model,
        model_attempts: result.model_attempts,
    })
}
