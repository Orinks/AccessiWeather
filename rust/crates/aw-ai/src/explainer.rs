//! Weather and text-product explanations.
//!
//! Ports `ai_explainer.py`, `ai_explainer_models.py` (`ExplanationStyle`,
//! `ExplanationResult`, `WeatherContext`), `ai_explainer_prompting.py`,
//! `ai_explainer_text_products.py` and the model-attempt helpers of
//! `ai_explainer_openrouter_client.py`, plus the model-information text the
//! explanation, discussion and forecast-product dialogs show.

use std::collections::HashMap;
use std::sync::{LazyLock, Mutex};
use std::time::{Duration, Instant};

use aw_core::settings::AppSettings;
use chrono::{DateTime, Local};
use regex::Regex;
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};

use crate::errors::{
    describe_generation_error, is_model_refusal, openrouter_generation_error, venice_error,
    AiError, AiErrorKind, MODEL_REFUSAL_MESSAGE,
};
use crate::provider::{
    selected_key, selected_model, selected_provider, Provider, DEFAULT_FREE_MODEL,
    DEFAULT_VENICE_MODEL,
};
use crate::pyfmt::{self, truthy};
use crate::transport::{self, CancelToken, StreamLimits};

/// How long an explanation stays cached. Python's `Cache` is created with
/// `ai_cache_ttl`, but the explainer always stores with `ttl=300`.
pub const EXPLANATION_CACHE_TTL: Duration = Duration::from_secs(300);

/// Shown by forecast-product summaries when no explainer can be built for
/// the selected provider ([`AiExplainer::from_settings`] failed).
pub const PROVIDER_UNAVAILABLE_MESSAGE: &str =
    "Selected AI provider API key not configured. Set it in Settings > AI.";

const MAX_PROMPT_LENGTH: usize = 2000;
const MAX_TOKENS: u32 = 4000;
const OPENROUTER_HEADERS: [(&str, &str); 2] = [
    ("HTTP-Referer", "https://accessiweather.orinks.net"),
    ("X-Title", "AccessiWeather"),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ExplanationStyle {
    /// 1-2 sentences.
    Brief,
    /// 3-4 sentences (default).
    Standard,
    /// Full paragraph with context.
    Detailed,
}

impl ExplanationStyle {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Brief => "brief",
            Self::Standard => "standard",
            Self::Detailed => "detailed",
        }
    }

    /// `resolve_explanation_style`: unknown values fall back to standard.
    pub fn from_setting(value: &str) -> Self {
        match value {
            "brief" => Self::Brief,
            "detailed" => Self::Detailed,
            _ => Self::Standard,
        }
    }
}

/// The outcome of one explanation.
#[derive(Debug, Clone, PartialEq)]
pub struct ExplanationResult {
    pub text: String,
    pub model_used: String,
    pub token_count: u64,
    /// USD; `None` when the provider's prices are not known (Venice).
    pub estimated_cost: Option<f64>,
    pub cached: bool,
    pub timestamp: DateTime<Local>,
    pub requested_model: Option<String>,
    pub model_attempts: Vec<String>,
    pub model_selection_reason: Option<String>,
}

impl ExplanationResult {
    fn cost_text(&self) -> String {
        match self.estimated_cost {
            None => "See provider account".into(),
            Some(0.0) => "No cost".into(),
            Some(cost) => format!("~${cost:.6}"),
        }
    }

    /// The "Model information" box of the weather explanation dialog.
    pub fn explanation_info(&self) -> String {
        let mut info = format!(
            "Model: {}\nTokens: {}\nCost: {}",
            self.model_used,
            self.token_count,
            self.cost_text()
        );
        if self.cached {
            info.push_str("\nCached: Yes");
        }
        info
    }

    /// `_build_model_info` of the discussion dialog and forecast-product panel.
    pub fn summary_info(&self) -> String {
        let mut lines = vec![
            format!("Model: {}", self.model_used),
            format!("Tokens: {}", self.token_count),
            format!("Cost: {}", self.cost_text()),
        ];
        if let Some(requested) = self
            .requested_model
            .as_deref()
            .filter(|r| !r.is_empty() && *r != self.model_used)
        {
            lines.push(format!("Requested: {requested}"));
        }
        if let Some(reason) = self
            .model_selection_reason
            .as_deref()
            .filter(|r| !r.is_empty())
        {
            lines.push(format!("Selection: {reason}"));
        }
        if self.model_attempts.len() > 1 {
            lines.push(format!("Tried: {}", self.model_attempts.join(", ")));
        }
        if self.cached {
            lines.push("Cached: Yes".into());
        }
        lines.join("\n")
    }

    /// "Generated: ..." timestamp text (`%B %d, %Y at %I:%M %p`).
    pub fn timestamp_text(&self) -> String {
        self.timestamp.format("%B %d, %Y at %I:%M %p").to_string()
    }
}

/// In-memory explanation cache shared by explanation dialogs
/// (`app.ai_explanation_cache`).
#[derive(Debug, Default)]
pub struct ExplanationCache {
    entries: Mutex<HashMap<String, (Instant, ExplanationResult)>>,
}

impl ExplanationCache {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn get(&self, key: &str) -> Option<ExplanationResult> {
        let mut entries = self.entries.lock().unwrap_or_else(|e| e.into_inner());
        match entries.get(key) {
            Some((expires, value)) if *expires >= Instant::now() => Some(value.clone()),
            Some(_) => {
                entries.remove(key);
                None
            }
            None => None,
        }
    }

    pub fn set(&self, key: String, value: ExplanationResult, ttl: Duration) {
        let mut entries = self.entries.lock().unwrap_or_else(|e| e.into_inner());
        entries.insert(key, (Instant::now() + ttl, value));
    }

    /// Forget one entry (Forecaster Notes' Regenerate Summary).
    pub fn remove(&self, key: &str) {
        self.entries
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .remove(key);
    }

    /// Emptied by the explanation dialog's Regenerate button.
    pub fn clear(&self) {
        self.entries
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clear();
    }
}

static INJECTION_PATTERNS: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    [
        r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
        r"(?i)you\s+are\s+now\s+(?:a|an|in)\s+(?:new|different|unrestricted)",
        r"(?i)disregard\s+(all\s+)?(previous|above|prior|your)\s+(instructions?|programming|rules?)",
        r"(?i)system\s*:\s*",
        r"(?i)\n\s*system\s*:",
    ]
    .iter()
    .map(|p| Regex::new(p).expect("valid pattern"))
    .collect()
});

/// `_sanitize_prompt`: bound custom prompt length and strip common prompt
/// injection patterns.
pub fn sanitize_prompt(prompt: Option<&str>) -> Option<String> {
    let trimmed = prompt?.trim();
    if trimmed.is_empty() {
        return None;
    }
    let mut sanitized = pyfmt::head(trimmed, MAX_PROMPT_LENGTH).to_string();
    for pattern in INJECTION_PATTERNS.iter() {
        if pattern.is_match(&sanitized) {
            tracing::warn!("Prompt injection pattern detected and stripped");
            sanitized = pattern.replace_all(&sanitized, "[filtered]").into_owned();
        }
    }
    (!sanitized.trim().is_empty()).then_some(sanitized)
}

/// The default system prompt (also shown by Settings > AI's reset button).
pub fn default_system_prompt() -> &'static str {
    "You are a helpful weather assistant that explains weather information in plain, accessible language. Your explanations should be easy to understand for screen reader users and people who prefer audio descriptions. Use only the information provided in the request. Do not invent missing details, hazards, records, dates, locations, or forecast impacts. If something is unclear or not provided, say so plainly.\n\n\
Avoid visual-only descriptions. When useful, explain what the weather information means for comfort, travel, planning, or safety, but only when supported by the provided text or data.\n\n\
IMPORTANT: Do NOT repeat the location name, date, time, or timezone in your response unless it is necessary for clarity. The user already sees this information. Jump straight into the explanation.\n\n\
IMPORTANT: Respond in plain text only. Do NOT use markdown formatting such as bold (**text**), italic (*text*), headers (#), bullet points, or any other markdown syntax. Use simple paragraph text."
}

fn style_instruction(style: ExplanationStyle) -> &'static str {
    match style {
        ExplanationStyle::Brief => "Keep your response to 1-2 sentences.",
        ExplanationStyle::Standard => "Provide a 3-4 sentence explanation.",
        ExplanationStyle::Detailed => "Provide a comprehensive paragraph with context about how the weather might affect daily activities.",
    }
}

fn product_style_instruction(style: ExplanationStyle) -> &'static str {
    match style {
        ExplanationStyle::Brief => "Provide a 2-3 sentence summary of the key points.",
        ExplanationStyle::Standard => "Provide a clear 1-2 paragraph summary.",
        ExplanationStyle::Detailed => "Provide a comprehensive summary covering all major points from the discussion, organized by topic.",
    }
}

static MARKDOWN: LazyLock<Vec<(Regex, &'static str)>> = LazyLock::new(|| {
    [
        (r"\*\*(.+?)\*\*", "$1"),
        (r"\*(.+?)\*", "$1"),
        (r"__(.+?)__", "$1"),
        (r"_(.+?)_", "$1"),
        (r"(?m)^#{1,6}\s+", ""),
        (r"```[\s\S]*?```", ""),
        (r"`(.+?)`", "$1"),
        (r"\[(.+?)\]\(.+?\)", "$1"),
        (r"(?m)^\s*[-*+]\s+", ""),
        (r"\n{3,}", "\n\n"),
    ]
    .iter()
    .map(|(p, r)| (Regex::new(p).expect("valid pattern"), *r))
    .collect()
});

/// `_format_response`: keep markdown, or strip it for plain-text display.
pub fn format_response(text: &str, preserve_markdown: bool) -> String {
    if preserve_markdown {
        return text.to_string();
    }
    let mut out = text.to_string();
    for (pattern, replacement) in MARKDOWN.iter() {
        out = pattern.replace_all(&out, *replacement).into_owned();
    }
    out.trim().to_string()
}

/// `dict.get(key)` for a JSON-decoded dict: missing and null are both `None`.
fn field<'a>(map: &'a Map<String, Value>, key: &str) -> Option<&'a Value> {
    map.get(key).filter(|v| !v.is_null())
}

/// `str(dict.get(key, default))`.
fn get_or(map: &Map<String, Value>, key: &str, default: &str) -> String {
    map.get(key).map_or_else(|| default.to_string(), pyfmt::str)
}

fn truthy_field<'a>(map: &'a Map<String, Value>, key: &str) -> Option<&'a Value> {
    map.get(key).filter(|v| truthy(v))
}

/// `WeatherContext.to_prompt_text` for the explainer's weather dict.
fn weather_context_text(weather: &Map<String, Value>, location: &str) -> String {
    let s = |key: &str| truthy_field(weather, key).map(pyfmt::str);
    let mut parts = vec![format!("Location: {location}")];
    if let (Some(local), Some(zone)) = (s("local_time"), s("timezone")) {
        parts.push(format!("Local Time: {local} ({zone})"));
    }
    if let Some(utc) = s("utc_time") {
        parts.push(format!("UTC Time: {utc}"));
    }
    if let Some(time_of_day) = s("time_of_day") {
        parts.push(format!("Time of Day: {time_of_day}"));
    }
    if let Some(text) = s("temperature_text") {
        parts.push(format!("Temperature: {text}"));
    } else if let Some(temp) = field(weather, "temperature") {
        let unit = get_or(weather, "temperature_unit", "F");
        parts.push(format!("Temperature: {}°{unit}", pyfmt::str(temp)));
    }
    if let Some(conditions) = s("conditions") {
        parts.push(format!("Conditions: {conditions}"));
    }
    if let Some(humidity) = field(weather, "humidity") {
        parts.push(format!("Humidity: {}%", pyfmt::str(humidity)));
    }
    let direction = s("wind_direction")
        .map(|d| format!(" from {d}"))
        .unwrap_or_default();
    if let Some(text) = s("wind_text") {
        parts.push(format!("Wind: {text}{direction}"));
    } else if let Some(speed) = field(weather, "wind_speed") {
        let unit = s("wind_speed_unit").unwrap_or_else(|| "mph".into());
        parts.push(format!("Wind: {} {unit}{direction}", pyfmt::str(speed)));
    }
    for (label, key, default_unit) in [
        ("Visibility", "visibility", "miles"),
        ("Pressure", "pressure", "inHg"),
    ] {
        if let Some(text) = s(&format!("{key}_text")) {
            parts.push(format!("{label}: {text}"));
        } else if let Some(value) = field(weather, key) {
            let unit = s(&format!("{key}_unit")).unwrap_or_else(|| default_unit.into());
            parts.push(format!("{label}: {} {unit}", pyfmt::str(value)));
        }
    }
    if let Some(alerts) = truthy_field(weather, "alerts").and_then(Value::as_array) {
        let lines: Vec<String> = alerts
            .iter()
            .filter_map(Value::as_object)
            .map(|alert| {
                format!(
                    "- {} (Severity: {})",
                    get_or(alert, "title", "Weather Alert"),
                    get_or(alert, "severity", "Unknown")
                )
            })
            .collect();
        parts.push(format!("Active Alerts:\n{}", lines.join("\n")));
    }
    if let Some(summary) = s("forecast_summary") {
        parts.push(format!("Forecast: {summary}"));
    }
    parts.join("\n")
}

/// Generates plain-language explanations with the selected provider.
#[derive(Debug, Clone)]
pub struct AiExplainer {
    pub provider: Provider,
    pub api_key: Option<String>,
    pub model: String,
    custom_system_prompt: Option<String>,
    custom_instructions: Option<String>,
    cache: Option<std::sync::Arc<ExplanationCache>>,
    pub(crate) base_url: String,
    pub(crate) limits: StreamLimits,
}

/// A provider response the fallback loop inspects.
struct Completion {
    content: String,
    model: String,
    total_tokens: u64,
}

impl AiExplainer {
    /// Custom prompts are sanitized as in Python's constructor.
    pub fn new(
        provider: Provider,
        api_key: Option<String>,
        model: impl Into<String>,
        custom_system_prompt: Option<&str>,
        custom_instructions: Option<&str>,
    ) -> Self {
        Self {
            provider,
            api_key,
            model: model.into(),
            custom_system_prompt: sanitize_prompt(custom_system_prompt),
            custom_instructions: sanitize_prompt(custom_instructions),
            cache: None,
            base_url: provider.base_url().to_string(),
            limits: StreamLimits::STREAMING,
        }
    }

    /// `AIExplainer(**explainer_options(settings))`.
    pub fn from_settings(settings: &AppSettings) -> Result<Self, AiError> {
        let key = selected_key(settings)?;
        Ok(Self::new(
            selected_provider(settings)?,
            (!key.is_empty()).then_some(key),
            selected_model(settings)?,
            settings.custom_system_prompt.as_deref(),
            settings.custom_instructions.as_deref(),
        ))
    }

    /// Share the application's explanation cache (only the weather
    /// explanation dialog passes one).
    pub fn with_cache(mut self, cache: std::sync::Arc<ExplanationCache>) -> Self {
        self.cache = Some(cache);
        self
    }

    /// `get_effective_model`.
    pub fn effective_model(&self) -> String {
        match self.provider {
            Provider::Venice if self.model.is_empty() || self.model == DEFAULT_FREE_MODEL => {
                DEFAULT_VENICE_MODEL.into()
            }
            Provider::Venice => self.model.clone(),
            // Without an API key, always use the free model.
            Provider::OpenRouter
                if self.api_key.as_deref().unwrap_or("").is_empty() || self.model.is_empty() =>
            {
                DEFAULT_FREE_MODEL.into()
            }
            Provider::OpenRouter => self.model.clone(),
        }
    }

    /// `get_effective_system_prompt`: the custom prompt, else the default
    /// prompt plus the style instruction.
    pub fn effective_system_prompt(&self, style: ExplanationStyle) -> String {
        match &self.custom_system_prompt {
            Some(custom) => custom.clone(),
            None => format!(
                "{}\n\n{}",
                default_system_prompt(),
                style_instruction(style)
            ),
        }
    }

    fn instructions(&self) -> Option<&str> {
        self.custom_instructions
            .as_deref()
            .filter(|i| !i.trim().is_empty())
    }

    /// `_build_prompt`: the user message for a weather explanation.
    pub fn build_prompt(&self, weather: &Map<String, Value>, location_name: &str) -> String {
        let mut prompt = String::from("Weather information to explain:\n");
        prompt.push_str(&weather_context_text(weather, location_name));
        if let Some(periods) = truthy_field(weather, "forecast_periods").and_then(Value::as_array) {
            prompt.push_str("\n\nUpcoming Forecast:");
            for period in periods.iter().filter_map(Value::as_object) {
                prompt.push_str(&format!("\n- {}: ", get_or(period, "name", "Unknown")));
                match truthy_field(period, "temperature_text") {
                    Some(text) => prompt.push_str(&pyfmt::str(text)),
                    None => prompt.push_str(&format!(
                        "{}°{}",
                        get_or(period, "temperature", "N/A"),
                        get_or(period, "temperature_unit", "F")
                    )),
                }
                if let Some(short) = truthy_field(period, "short_forecast") {
                    prompt.push_str(&format!(", {}", pyfmt::str(short)));
                }
                if let Some(wind) = truthy_field(period, "wind_speed") {
                    prompt.push_str(&format!(" (Wind: {}", pyfmt::str(wind)));
                    if let Some(direction) = truthy_field(period, "wind_direction") {
                        prompt.push_str(&format!(" {}", pyfmt::str(direction)));
                    }
                    prompt.push(')');
                }
            }
        }
        if self.custom_system_prompt.is_none() {
            prompt.push_str("\n\nProvide a natural language explanation of the current conditions and what to expect over the coming days for someone planning their activities.");
        }
        if let Some(instructions) = self.instructions() {
            prompt.push_str(&format!("\n\nAdditional Instructions: {instructions}"));
        }
        prompt
    }

    /// `_build_text_product_user_prompt`.
    pub fn build_text_product_prompt(
        &self,
        product_text: &str,
        product_type: &str,
        location_name: &str,
        style: ExplanationStyle,
    ) -> String {
        let label = if product_type.is_empty() {
            "unknown type"
        } else {
            product_type
        };
        let mut prompt = format!(
            "Please explain this National Weather Service text product ({label}) for {location_name} in plain language:\n\n{product_text}\n\n{}",
            product_style_instruction(style)
        );
        if let Some(instructions) = self.instructions() {
            prompt.push_str(&format!("\n\nAdditional Instructions: {instructions}"));
        }
        prompt
    }

    /// `_generate_cache_key`: keyed by every prompt input.
    pub fn cache_key(
        &self,
        weather: &Map<String, Value>,
        location_name: &str,
        style: ExplanationStyle,
        preserve_markdown: bool,
    ) -> String {
        // json.dumps(inputs, sort_keys=True, ensure_ascii=False)
        let string = |s: &str| Value::String(s.to_string()).to_string();
        let dumped = format!(
            "{{\"model\": {}, \"preserve_markdown\": {preserve_markdown}, \"provider\": {}, \"style\": {}, \"system\": {}, \"user\": {}}}",
            string(&self.effective_model()),
            string(self.provider.as_str()),
            string(style.as_str()),
            string(&self.effective_system_prompt(style)),
            string(&self.build_prompt(weather, location_name)),
        );
        format!("ai_explanation:v2:{:x}", Sha256::digest(dumped.as_bytes()))
    }

    /// `_text_product_cache_key`.
    pub fn text_product_cache_key(
        &self,
        product_type: &str,
        location_name: &str,
        product_text: &str,
        style: ExplanationStyle,
    ) -> String {
        format!(
            "ai_text_product:{}:{}:{product_type}:{location_name}:{:x}:{}",
            self.provider.as_str(),
            self.effective_model(),
            Sha256::digest(product_text.as_bytes()),
            style.as_str()
        )
    }

    /// Explain the current conditions in `weather` (built by
    /// [`crate::payload::build_current_weather_payload`]).
    /// `status` receives user-facing progress about model attempts.
    pub fn explain_weather(
        &self,
        weather: &Map<String, Value>,
        location_name: &str,
        style: ExplanationStyle,
        preserve_markdown: bool,
        status: &dyn Fn(&str),
        cancel: Option<&CancelToken>,
    ) -> Result<ExplanationResult, AiError> {
        let key = self.cache_key(weather, location_name, style, preserve_markdown);
        let system = self.effective_system_prompt(style);
        let user = self.build_prompt(weather, location_name);
        self.cached_generate(key, &system, &user, preserve_markdown, status, cancel)
    }

    /// Explain any NWS/IEM text product (AFD, HWO, SPS, CLI, ...).
    #[allow(clippy::too_many_arguments)]
    pub fn explain_text_product(
        &self,
        product_text: &str,
        product_type: &str,
        location_name: &str,
        style: ExplanationStyle,
        preserve_markdown: bool,
        status: &dyn Fn(&str),
        cancel: Option<&CancelToken>,
    ) -> Result<ExplanationResult, AiError> {
        let key = self.text_product_cache_key(product_type, location_name, product_text, style);
        let system = self.effective_system_prompt(style);
        let user = self.build_text_product_prompt(product_text, product_type, location_name, style);
        self.cached_generate(key, &system, &user, preserve_markdown, status, cancel)
    }

    /// `explain_afd`: an Area Forecast Discussion (the discussion dialog uses
    /// the detailed style).
    pub fn explain_afd(
        &self,
        afd_text: &str,
        location_name: &str,
        style: ExplanationStyle,
        status: &dyn Fn(&str),
        cancel: Option<&CancelToken>,
    ) -> Result<ExplanationResult, AiError> {
        self.explain_text_product(afd_text, "AFD", location_name, style, false, status, cancel)
    }

    fn cached_generate(
        &self,
        key: String,
        system: &str,
        user: &str,
        preserve_markdown: bool,
        status: &dyn Fn(&str),
        cancel: Option<&CancelToken>,
    ) -> Result<ExplanationResult, AiError> {
        if let Some(hit) = self.cache.as_ref().and_then(|c| c.get(&key)) {
            return Ok(ExplanationResult {
                cached: true,
                ..hit
            });
        }
        let result = self.generate(system, user, preserve_markdown, status, cancel)?;
        // Only successes are cached; a retry after a failure re-asks the model.
        if let Some(cache) = &self.cache {
            cache.set(key, result.clone(), EXPLANATION_CACHE_TTL);
        }
        Ok(result)
    }

    fn model_attempts(&self, primary: &str) -> Vec<String> {
        match self.provider {
            Provider::Venice => vec![primary.to_string()],
            // One retry through the free router, which lands on another free model.
            Provider::OpenRouter => vec![primary.to_string(), DEFAULT_FREE_MODEL.to_string()],
        }
    }

    /// The fallback loop shared by weather and text-product explanations.
    fn generate(
        &self,
        system: &str,
        user: &str,
        preserve_markdown: bool,
        status: &dyn Fn(&str),
        cancel: Option<&CancelToken>,
    ) -> Result<ExplanationResult, AiError> {
        let primary = self.effective_model();
        let models = self.model_attempts(&primary);
        let mut attempted = Vec::new();
        let mut last_error: Option<AiError> = None;
        for (index, model) in models.iter().enumerate() {
            attempted.push(model.clone());
            status(&describe_model_attempt(
                self.provider,
                model,
                &primary,
                index,
            ));
            let more = index + 1 < models.len();
            match self.call_provider(system, user, model, cancel) {
                Ok(response) if is_model_refusal(&response.content) => {
                    last_error = Some(AiError::new(AiErrorKind::Explainer, MODEL_REFUSAL_MESSAGE));
                }
                Ok(response) if response.content.trim().chars().count() >= 20 => {
                    let reason = model_selection_reason(
                        self.provider,
                        &primary,
                        &response.model,
                        &attempted,
                        last_error.as_ref(),
                    );
                    return Ok(ExplanationResult {
                        text: format_response(&response.content, preserve_markdown),
                        estimated_cost: estimate_cost(
                            self.provider,
                            &response.model,
                            response.total_tokens,
                        ),
                        model_used: response.model,
                        token_count: response.total_tokens,
                        cached: false,
                        timestamp: Local::now(),
                        requested_model: Some(primary),
                        model_attempts: attempted,
                        model_selection_reason: Some(reason),
                    });
                }
                Ok(_) => {
                    tracing::warn!("Model {model} returned an insufficient response");
                    last_error = Some(AiError::new(
                        AiErrorKind::EmptyResponse,
                        "empty or too-short response",
                    ));
                    status(&format!(
                        "{model} returned an empty response.{}",
                        if more {
                            " Trying another available model."
                        } else {
                            " Please try again."
                        }
                    ));
                }
                Err(error) => {
                    if error.is_fatal() || error.kind == AiErrorKind::Cancelled {
                        return Err(error);
                    }
                    tracing::warn!("Model attempt failed ({:?})", error.kind);
                    if more {
                        status(&format!(
                            "{model} could not generate a summary because of {}; trying another available model.",
                            describe_generation_error(&error)
                        ));
                    }
                    last_error = Some(error);
                }
            }
        }
        // Python re-raises the last attempt's error; the "all empty" message
        // is only reachable when no attempt ran.
        Err(last_error.unwrap_or_else(|| {
            AiError::new(
                AiErrorKind::EmptyResponse,
                "All AI models returned empty responses.\n\nThis can happen when models are overloaded.\nPlease try again in a few minutes.",
            )
        }))
    }

    /// `_call_provider`: one streamed completion from the selected provider only.
    fn call_provider(
        &self,
        system: &str,
        user: &str,
        model: &str,
        cancel: Option<&CancelToken>,
    ) -> Result<Completion, AiError> {
        let messages = json!([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]);
        let url = format!("{}/chat/completions", self.base_url);
        match self.provider {
            Provider::OpenRouter => {
                // OpenRouter needs a key even for free models.
                let key = self.api_key.as_deref().unwrap_or("");
                if key.is_empty() {
                    return Err(AiError::new(
                        AiErrorKind::Explainer,
                        "OpenRouter API key required. Get a free key at openrouter.ai/keys - free models won't charge your account.",
                    ));
                }
                // Free reasoning models can think for a minute or use the whole
                // token budget and return no text; a summary needs no reasoning.
                let body = json!({"model": model, "messages": messages, "max_tokens": MAX_TOKENS,
                                  "reasoning": {"effort": "none"}});
                let stream = transport::stream_chat_completion(
                    &url,
                    key,
                    &OPENROUTER_HEADERS,
                    &body,
                    self.limits,
                    cancel,
                )
                .map_err(|e| openrouter_generation_error(&e, model))?;
                Ok(Completion {
                    content: stream.content,
                    model: stream.model.unwrap_or_else(|| "unknown".into()),
                    total_tokens: stream.total_tokens,
                })
            }
            Provider::Venice => {
                let key = self.api_key.as_deref().unwrap_or("").trim();
                if key.is_empty() {
                    return Err(AiError::new(
                        AiErrorKind::InvalidApiKey,
                        "A Venice API key is required. Add your own key in Settings > AI.",
                    ));
                }
                let body = json!({"model": model, "messages": messages, "max_tokens": MAX_TOKENS,
                                  "venice_parameters": {"include_venice_system_prompt": false}});
                let stream =
                    transport::stream_chat_completion(&url, key, &[], &body, self.limits, cancel)
                        .map_err(|e| venice_error(&e))?;
                Ok(Completion {
                    content: stream.content,
                    model: stream.model.unwrap_or_else(|| self.effective_model()),
                    total_tokens: stream.total_tokens,
                })
            }
        }
    }
}

/// `_describe_model_attempt`: status text before each model attempt.
pub fn describe_model_attempt(
    provider: Provider,
    model: &str,
    primary: &str,
    index: usize,
) -> String {
    if provider == Provider::Venice {
        return format!("Trying selected Venice model {model}.");
    }
    if index == 0 {
        if model == DEFAULT_FREE_MODEL {
            return "Trying OpenRouter's free router. Free models share capacity; if this one does not answer, the router tries another free model.".into();
        }
        if model.contains(":free") {
            return format!("Trying selected free model {model}. Free models share rate limits; the free router will be tried if this one is busy.");
        }
        return format!("Trying selected model {model}.");
    }
    if model == DEFAULT_FREE_MODEL {
        return "Trying OpenRouter's free router as a backup because the selected model did not answer.".into();
    }
    if model.contains(":free") {
        return format!(
            "Trying backup free model {model} because an earlier model did not answer."
        );
    }
    format!("Trying backup model {model} because {primary} did not answer.")
}

/// `_build_model_selection_reason`: why this model answered.
pub fn model_selection_reason(
    provider: Provider,
    requested: &str,
    model_used: &str,
    attempted: &[String],
    last_error: Option<&AiError>,
) -> String {
    if provider == Provider::Venice {
        return "Used the selected Venice model.".into();
    }
    if model_used == requested && attempted.len() <= 1 {
        if requested == DEFAULT_FREE_MODEL {
            return "OpenRouter's free router selected the answering free model.".into();
        }
        return "Used the selected model.".into();
    }
    if requested == DEFAULT_FREE_MODEL && last_error.is_none() {
        return format!(
            "OpenRouter's free router selected {model_used} from available free models."
        );
    }
    let reason = last_error.map_or("an earlier model", describe_generation_error);
    if requested.contains(":free") {
        return format!("Selected free model was limited by {reason}, so AccessiWeather tried backup free models and {model_used} answered.");
    }
    if requested == DEFAULT_FREE_MODEL {
        return format!("OpenRouter's free router or an earlier free model did not answer, so {model_used} answered.");
    }
    format!("The selected model {requested} did not answer because of {reason}, so {model_used} answered instead.")
}

/// `_estimate_cost`: rough USD cost; `None` for Venice, whose prices vary.
pub fn estimate_cost(provider: Provider, model: &str, token_count: u64) -> Option<f64> {
    if provider == Provider::Venice {
        return None;
    }
    if model.contains(":free") {
        return Some(0.0);
    }
    const RATES: [(&str, f64); 6] = [
        ("openrouter/auto", 0.5),
        ("gpt-4", 30.0),
        ("gpt-3.5-turbo", 0.5),
        ("claude-3-opus", 15.0),
        ("claude-3-sonnet", 3.0),
        ("claude-3-haiku", 0.25),
    ];
    let rate = RATES
        .iter()
        .find(|(prefix, _)| model.contains(prefix))
        .map_or(0.5, |(_, rate)| *rate);
    Some((token_count as f64 / 1_000_000.0) * rate)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_server::{sse_chunk, Reply, Step, TestServer};
    use std::cell::RefCell;
    use std::sync::Arc;

    fn answer(text: &str, model: &str) -> Reply {
        let usage = json!({"prompt_tokens": 1, "completion_tokens": 9, "total_tokens": 10});
        let mut body = sse_chunk(Some(text), Some("stop"), None);
        body.extend(sse_chunk(None, None, Some(usage)));
        body.extend(b"data: [DONE]\n\n");
        let body = String::from_utf8(body)
            .unwrap()
            .replace("picked/model", model);
        Reply::sse(vec![Step::Send(body.into_bytes())])
    }

    fn explainer(server: &TestServer, provider: Provider, model: &str) -> AiExplainer {
        let mut e = AiExplainer::new(provider, Some("test-secret".into()), model, None, None);
        e.base_url = server.url();
        e
    }

    fn run(e: &AiExplainer, product: bool) -> (Result<ExplanationResult, AiError>, Vec<String>) {
        let statuses = RefCell::new(Vec::new());
        let push = |m: &str| statuses.borrow_mut().push(m.to_string());
        let result = if product {
            e.explain_text_product(
                "Forecast discussion",
                "AFD",
                "Test",
                ExplanationStyle::Detailed,
                false,
                &push,
                None,
            )
        } else {
            e.explain_weather(
                &Map::new(),
                "Test",
                ExplanationStyle::Standard,
                false,
                &push,
                None,
            )
        };
        (result, statuses.into_inner())
    }

    #[test]
    fn access_failures_stop_without_fallback_and_hide_upstream_text() {
        for product in [false, true] {
            for (code, kind) in [
                (401, AiErrorKind::InvalidApiKey),
                (403, AiErrorKind::ProviderPermission),
                (402, AiErrorKind::InsufficientCredits),
            ] {
                let server =
                    TestServer::start(vec![Reply::text(code, "secret api key authentication")]);
                let (result, _) = run(
                    &explainer(&server, Provider::OpenRouter, "openrouter/free"),
                    product,
                );
                let error = result.unwrap_err();
                assert_eq!(error.kind, kind);
                assert!(!error.message.contains("secret"));
                assert_eq!(server.requests().len(), 1);
                if code == 401 {
                    assert!(error
                        .message
                        .contains("could not authenticate this generation request"));
                }
            }
        }
    }

    #[test]
    fn empty_or_busy_free_model_uses_one_fallback() {
        for product in [false, true] {
            for first in [
                answer("User Safety: safe", "a:free"),
                Reply::text(429, "busy"),
            ] {
                let good = "A clear weather summary with enough useful detail.";
                let server = TestServer::start(vec![first, answer(good, "backup:free")]);
                let (result, statuses) = run(
                    &explainer(&server, Provider::OpenRouter, "openrouter/free"),
                    product,
                );
                let result = result.unwrap();
                assert_eq!(result.text, good);
                assert_eq!(
                    result.model_attempts,
                    ["openrouter/free", "openrouter/free"]
                );
                assert_eq!(statuses.len(), 3, "{statuses:?}");
                assert_eq!(server.requests().len(), 2);
            }
        }
    }

    #[test]
    fn empty_responses_stop_after_two_attempts() {
        let server = TestServer::start(vec![answer("", "m"), answer("", "m")]);
        let (result, statuses) = run(
            &explainer(&server, Provider::OpenRouter, "openrouter/free"),
            false,
        );
        let error = result.unwrap_err();
        assert_eq!(error.kind, AiErrorKind::EmptyResponse);
        assert_eq!(error.message, "empty or too-short response");
        assert_eq!(
            statuses[1],
            "openrouter/free returned an empty response. Trying another available model."
        );
        assert_eq!(
            statuses[3],
            "openrouter/free returned an empty response. Please try again."
        );
    }

    #[test]
    fn refusal_is_reported_after_fallback() {
        let refusal = "I'm sorry, but I can't help with that.";
        let server = TestServer::start(vec![answer(refusal, "m"), answer(refusal, "m")]);
        let (result, _) = run(
            &explainer(&server, Provider::OpenRouter, "vendor/model"),
            false,
        );
        assert_eq!(result.unwrap_err().message, MODEL_REFUSAL_MESSAGE);
    }

    #[test]
    fn fallback_progress_and_selection_reason_name_the_cause() {
        let good = "A clear weather summary with enough useful detail.";
        let server = TestServer::start(vec![Reply::text(429, "rate"), answer(good, "backup:free")]);
        let (result, statuses) = run(
            &explainer(&server, Provider::OpenRouter, "vendor/model:free"),
            true,
        );
        let result = result.unwrap();
        assert_eq!(statuses, [
            "Trying selected free model vendor/model:free. Free models share rate limits; the free router will be tried if this one is busy.",
            "vendor/model:free could not generate a summary because of rate limits; trying another available model.",
            "Trying OpenRouter's free router as a backup because the selected model did not answer.",
        ]);
        assert_eq!(
            result.model_selection_reason.as_deref(),
            Some("Selected free model was limited by rate limits, so AccessiWeather tried backup free models and backup:free answered.")
        );
        assert_eq!(result.estimated_cost, Some(0.0));
        assert_eq!(result.requested_model.as_deref(), Some("vendor/model:free"));
        let sent = server.requests()[1].json();
        assert_eq!(sent["model"], "openrouter/free");
        assert_eq!(sent["reasoning"], json!({"effort": "none"}));
        assert_eq!(sent["max_tokens"], 4000);
        assert_eq!(
            server.requests()[0].header("X-Title"),
            Some("AccessiWeather")
        );
    }

    #[test]
    fn venice_preserves_prompts_and_never_retries() {
        let server = TestServer::start(vec![answer(
            "A useful weather explanation here.",
            DEFAULT_VENICE_MODEL,
        )]);
        let mut e = AiExplainer::new(
            Provider::Venice,
            Some("test-key".into()),
            "",
            Some("My custom system prompt"),
            Some("Use Celsius only"),
        );
        e.base_url = server.url();
        let mut weather = Map::new();
        weather.insert("temperature".into(), json!(20));
        let result = e
            .explain_weather(
                &weather,
                "Venice",
                ExplanationStyle::Standard,
                false,
                &|_| {},
                None,
            )
            .unwrap();
        let sent = server.requests()[0].json();
        assert_eq!(sent["model"], DEFAULT_VENICE_MODEL);
        assert_eq!(
            sent["venice_parameters"],
            json!({"include_venice_system_prompt": false})
        );
        assert_eq!(sent["messages"][0]["content"], "My custom system prompt");
        assert!(sent["messages"][1]["content"]
            .as_str()
            .unwrap()
            .contains("Use Celsius only"));
        assert_eq!(result.model_attempts, [DEFAULT_VENICE_MODEL]);
        assert_eq!(result.estimated_cost, None);
        assert_eq!(
            result.model_selection_reason.as_deref(),
            Some("Used the selected Venice model.")
        );

        for code in [401, 403, 402, 429, 503] {
            let server = TestServer::start(vec![Reply::text(code, "secret-key body")]);
            let mut e =
                AiExplainer::new(Provider::Venice, Some("secret-key".into()), "", None, None);
            e.base_url = server.url();
            let error = e
                .explain_weather(
                    &Map::new(),
                    "T",
                    ExplanationStyle::Standard,
                    false,
                    &|_| {},
                    None,
                )
                .unwrap_err();
            assert!(!error.message.contains("secret-key"));
            assert_eq!(server.requests().len(), 1);
        }
        let missing = AiExplainer::new(Provider::Venice, None, "", None, None)
            .explain_weather(
                &Map::new(),
                "T",
                ExplanationStyle::Standard,
                false,
                &|_| {},
                None,
            )
            .unwrap_err();
        assert!(missing.message.contains("Venice API key is required"));
    }

    #[test]
    fn cache_hits_skip_the_model_and_failures_are_not_cached() {
        let good = "A clear weather summary with enough useful detail.";
        let server = TestServer::start(vec![
            Reply::text(500, "x"),
            Reply::text(500, "x"),
            answer(good, "m:free"),
        ]);
        let cache = Arc::new(ExplanationCache::new());
        let e =
            explainer(&server, Provider::OpenRouter, "openrouter/free").with_cache(cache.clone());
        assert!(run(&e, true).0.is_err());
        let first = run(&e, true).0.unwrap();
        let second = run(&e, true).0.unwrap();
        assert!(!first.cached && second.cached);
        assert_eq!(second.text, first.text);
        assert_eq!(server.requests().len(), 3);
        cache.clear();
        assert!(cache
            .get(&e.text_product_cache_key(
                "AFD",
                "Test",
                "Forecast discussion",
                ExplanationStyle::Detailed
            ))
            .is_none());
    }

    #[test]
    fn removing_one_entry_forces_a_fresh_answer() {
        let good = "A clear weather summary with enough useful detail.";
        let server = TestServer::start(vec![answer(good, "m:free"), answer(good, "m:free")]);
        let cache = Arc::new(ExplanationCache::new());
        let e =
            explainer(&server, Provider::OpenRouter, "openrouter/free").with_cache(cache.clone());
        assert!(!run(&e, true).0.unwrap().cached);
        assert!(run(&e, true).0.unwrap().cached);
        cache.remove(&e.text_product_cache_key(
            "AFD",
            "Test",
            "Forecast discussion",
            ExplanationStyle::Detailed,
        ));
        assert!(!run(&e, true).0.unwrap().cached);
        assert_eq!(server.requests().len(), 2);
    }

    #[test]
    fn missing_openrouter_key_uses_free_model_and_explains() {
        let e = AiExplainer::new(Provider::OpenRouter, None, "vendor/model", None, None);
        assert_eq!(e.effective_model(), DEFAULT_FREE_MODEL);
        let error = e
            .explain_weather(
                &Map::new(),
                "T",
                ExplanationStyle::Standard,
                false,
                &|_| {},
                None,
            )
            .unwrap_err();
        assert!(error.message.starts_with("OpenRouter API key required."));
    }

    #[test]
    fn cache_key_tracks_provider_prompt_style_and_format() {
        let base = AiExplainer::new(Provider::OpenRouter, Some("k".into()), "same", None, None);
        let venice = AiExplainer::new(Provider::Venice, Some("k".into()), "same", None, None);
        let custom = AiExplainer::new(
            Provider::OpenRouter,
            Some("k".into()),
            "same",
            Some("Be brief"),
            None,
        );
        let empty = Map::new();
        let key = base.cache_key(&empty, "T", ExplanationStyle::Standard, false);
        assert_ne!(
            key,
            venice.cache_key(&empty, "T", ExplanationStyle::Standard, false)
        );
        assert_ne!(
            key,
            custom.cache_key(&empty, "T", ExplanationStyle::Standard, false)
        );
        assert_ne!(
            key,
            base.cache_key(&empty, "T", ExplanationStyle::Brief, false)
        );
        assert_ne!(
            key,
            base.cache_key(&empty, "T", ExplanationStyle::Standard, true)
        );
    }

    #[test]
    fn model_info_texts() {
        let result = ExplanationResult {
            text: "t".into(),
            model_used: "b:free".into(),
            token_count: 12,
            estimated_cost: Some(0.0),
            cached: true,
            timestamp: Local::now(),
            requested_model: Some("a:free".into()),
            model_attempts: vec!["a:free".into(), "openrouter/free".into()],
            model_selection_reason: Some("Why.".into()),
        };
        assert_eq!(
            result.explanation_info(),
            "Model: b:free\nTokens: 12\nCost: No cost\nCached: Yes"
        );
        assert_eq!(
            result.summary_info(),
            "Model: b:free\nTokens: 12\nCost: No cost\nRequested: a:free\nSelection: Why.\nTried: a:free, openrouter/free\nCached: Yes"
        );
        let paid = ExplanationResult {
            estimated_cost: Some(0.0005),
            cached: false,
            ..result.clone()
        };
        assert!(paid.explanation_info().ends_with("Cost: ~$0.000500"));
        let venice = ExplanationResult {
            estimated_cost: None,
            ..result
        };
        assert!(venice
            .explanation_info()
            .contains("Cost: See provider account"));
    }
}
