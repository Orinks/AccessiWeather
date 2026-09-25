//! Model catalogs and the model browser's filtering and text.
//!
//! Ports `api/openrouter_models.py`, `api/venice_models.py` and the
//! non-widget logic of `ui/dialogs/model_browser_dialog.py` (filters,
//! provider list, list items, descriptions, pricing and Venice credit status).

use std::time::Duration;

use serde_json::{Map, Value};

use crate::errors::TransportError;
use crate::provider::{
    Provider, DEFAULT_FREE_MODEL, DEFAULT_PAID_MODEL, OPENROUTER_BASE_URL, VENICE_BASE_URL,
};
use crate::pyfmt::{self, casefold, format_g};
use crate::transport;

const CATALOG_TIMEOUT: Duration = Duration::from_secs(30);

/// A text model from either catalog. Prices are USD per million tokens as
/// the services report them; `None` means unknown (Venice only).
#[derive(Debug, Clone, PartialEq)]
pub struct CatalogModel {
    pub id: String,
    pub name: String,
    pub description: String,
    pub context_length: Option<i64>,
    pub pricing_prompt: Option<f64>,
    pub pricing_completion: Option<f64>,
    pub is_free: bool,
    /// OpenRouter `architecture` modalities (Venice lists only text models).
    pub input_modalities: Vec<String>,
    pub output_modalities: Vec<String>,
    /// Venice: usable by the Weather Assistant.
    pub supports_function_calling: bool,
    /// Venice: listed but unavailable for selection.
    pub offline: bool,
    /// Vendor id used by the provider filter.
    pub provider: String,
}

impl CatalogModel {
    /// Name plus "(Free)" and, for Venice, "(Offline)".
    pub fn display_name(&self) -> String {
        let mut name = self.name.clone();
        if self.is_free {
            name.push_str(" (Free)");
        }
        if self.offline {
            name.push_str(" (Offline)");
        }
        name
    }

    pub fn context_display(&self) -> String {
        match self.context_length {
            None => "Unknown".into(),
            Some(n) if n >= 1_000_000 => format!("{:.1}M", n as f64 / 1_000_000.0),
            Some(n) if n >= 1000 => format!("{:.0}K", n as f64 / 1000.0),
            Some(n) => n.to_string(),
        }
    }

    fn is_text(&self) -> bool {
        self.input_modalities.iter().any(|m| m == "text")
            && self.output_modalities.iter().any(|m| m == "text")
    }
}

/// `_parse_pricing`: numbers or numeric strings; anything else is 0.
fn parse_pricing(value: Option<&Value>) -> f64 {
    match value {
        Some(Value::Number(n)) => n.as_f64().unwrap_or(0.0),
        Some(Value::String(s)) => s.trim().parse().unwrap_or(0.0),
        _ => 0.0,
    }
}

fn object(value: Option<&Value>) -> Map<String, Value> {
    value
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default()
}

fn strings(value: Option<&Value>) -> Option<Vec<String>> {
    value?
        .as_array()
        .map(|items| items.iter().map(pyfmt::str).collect())
}

/// `OpenRouterModelsClient._parse_model`.
pub fn parse_openrouter_model(data: &Map<String, Value>) -> CatalogModel {
    let id = data.get("id").map_or(String::new(), pyfmt::str);
    let pricing = object(data.get("pricing"));
    let architecture = object(data.get("architecture"));
    let prompt = parse_pricing(pricing.get("prompt"));
    let completion = parse_pricing(pricing.get("completion"));
    let provider = match id.split_once('/') {
        Some((vendor, _)) => vendor.to_string(),
        None => "unknown".into(),
    };
    CatalogModel {
        is_free: id.ends_with(":free") || (prompt == 0.0 && completion == 0.0),
        name: data
            .get("name")
            .filter(|n| !n.is_null())
            .map_or_else(|| id.clone(), pyfmt::str),
        description: data
            .get("description")
            .filter(|d| !d.is_null())
            .map_or(String::new(), pyfmt::str),
        context_length: data.get("context_length").and_then(Value::as_i64),
        pricing_prompt: Some(prompt),
        pricing_completion: Some(completion),
        input_modalities: strings(architecture.get("input_modalities"))
            .unwrap_or_else(|| vec!["text".into()]),
        output_modalities: strings(architecture.get("output_modalities"))
            .unwrap_or_else(|| vec!["text".into()]),
        supports_function_calling: false,
        offline: false,
        provider,
        id,
    }
}

/// `_number`: a finite nonnegative number (numeric strings count).
fn venice_number(value: Option<&Value>) -> Option<f64> {
    let number = match value? {
        Value::Number(n) => n.as_f64()?,
        Value::String(s) => s.trim().parse().ok()?,
        _ => return None,
    };
    (number.is_finite() && number >= 0.0).then_some(number)
}

/// Ordered (keywords, provider id) pairs; earlier entries win.
const VENICE_PROVIDER_KEYWORDS: [(&[&str], &str); 18] = [
    (&["venice"], "venice"),
    (&["hermes"], "nousresearch"),
    (&["claude"], "anthropic"),
    (&["openai", "gpt"], "openai"),
    (&["gemini", "gemma", "google"], "google"),
    (&["grok"], "x-ai"),
    (&["qwen"], "qwen"),
    (&["deepseek"], "deepseek"),
    (&["llama"], "meta-llama"),
    (&["mistral"], "mistralai"),
    (&["kimi"], "moonshotai"),
    (&["glm", "z-ai", "zai-org"], "z-ai"),
    (&["minimax"], "minimax"),
    (&["nvidia", "nemotron"], "nvidia"),
    (&["xiaomi", "mimo"], "xiaomi"),
    (&["seed"], "bytedance"),
    (&["mercury"], "inception"),
    (&["aion"], "aion-labs"),
];

/// `infer_venice_provider`: vendor id from the model id and name; Venice-hosted
/// originals fall back to "venice".
pub fn infer_venice_provider(model_id: &str, name: &str) -> String {
    let haystack = format!("{model_id} {name}").to_lowercase();
    let haystack = haystack.strip_prefix("e2ee-").unwrap_or(&haystack);
    VENICE_PROVIDER_KEYWORDS
        .iter()
        .find(|(keywords, _)| keywords.iter().any(|k| haystack.contains(k)))
        .map_or("venice", |(_, provider)| provider)
        .to_string()
}

/// `VeniceModelsClient._parse_model`.
pub fn parse_venice_model(data: &Map<String, Value>) -> CatalogModel {
    let spec = object(data.get("model_spec"));
    let pricing = object(spec.get("pricing"));
    let prompt = venice_number(object(pricing.get("input")).get("usd"));
    let completion = venice_number(object(pricing.get("output")).get("usd"));
    let context = venice_number(spec.get("availableContextTokens"));
    let id = data.get("id").map_or(String::new(), pyfmt::str);
    let name = spec
        .get("name")
        .and_then(Value::as_str)
        .map_or_else(|| id.clone(), String::from);
    CatalogModel {
        provider: infer_venice_provider(&id, &name),
        description: spec
            .get("description")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        context_length: context.filter(|c| *c > 0.0).map(|c| c as i64),
        is_free: prompt == Some(0.0) && completion == Some(0.0),
        pricing_prompt: prompt,
        pricing_completion: completion,
        input_modalities: vec!["text".into()],
        output_modalities: vec!["text".into()],
        supports_function_calling: object(spec.get("capabilities")).get("supportsFunctionCalling")
            == Some(&Value::Bool(true)),
        offline: spec.get("offline") == Some(&Value::Bool(true)),
        name,
        id,
    }
}

/// `OpenRouterModelsClient.fetch_models`: every model, sorted by name.
pub fn fetch_openrouter_models(api_key: Option<&str>) -> Result<Vec<CatalogModel>, String> {
    fetch_openrouter_models_at(OPENROUTER_BASE_URL, api_key)
}

pub(crate) fn fetch_openrouter_models_at(
    base_url: &str,
    api_key: Option<&str>,
) -> Result<Vec<CatalogModel>, String> {
    let response = transport::get(
        &format!("{base_url}/models"),
        api_key.filter(|k| !k.is_empty()),
        CATALOG_TIMEOUT,
    )
    .map_err(|_| "Failed to fetch models: request failed".to_string())?;
    if response.status >= 400 {
        return Err(format!("Failed to fetch models: HTTP {}", response.status));
    }
    let payload: Value = serde_json::from_str(&response.body)
        .map_err(|_| "Failed to fetch models: invalid response".to_string())?;
    let rows = payload
        .get("data")
        .cloned()
        .unwrap_or(Value::Array(Vec::new()));
    let rows = rows
        .as_array()
        .ok_or("Failed to fetch models: invalid response")?;
    let mut models = rows
        .iter()
        .map(|row| {
            row.as_object()
                .map(parse_openrouter_model)
                .ok_or("Failed to fetch models: invalid response".to_string())
        })
        .collect::<Result<Vec<_>, _>>()?;
    models.sort_by_cached_key(|m| m.name.to_lowercase());
    Ok(models)
}

/// A safe user-facing Venice catalog or account failure (`VeniceModelsError`).
fn venice_failure(error: TransportError) -> String {
    match error {
        TransportError::Status { status: 401, .. } => {
            "Venice could not authenticate this request. Check your API key in Settings."
        }
        TransportError::Status { status: 403, .. } => {
            "Your Venice key cannot access this information. Check your account permissions or view it on the Venice website."
        }
        TransportError::Status { status: 429, .. } => {
            "Venice rate limit reached. Wait a moment and try again."
        }
        TransportError::Status { .. } => {
            "Venice could not retrieve this information. Please try again later."
        }
        TransportError::Timeout => "Venice request timed out. Please try again.",
        TransportError::Connect => "Could not reach Venice. Check your internet connection.",
        _ => "Venice returned unreadable information. Please try again later.",
    }
    .to_string()
}

fn venice_get(base_url: &str, path: &str, api_key: &str) -> Result<Map<String, Value>, String> {
    let response = transport::get(
        &format!("{base_url}/{path}"),
        (!api_key.is_empty()).then_some(api_key),
        CATALOG_TIMEOUT,
    )
    .map_err(venice_failure)?;
    if response.status >= 400 {
        return Err(venice_failure(TransportError::Status {
            status: response.status,
            body: String::new(),
        }));
    }
    serde_json::from_str::<Value>(&response.body)
        .ok()
        .and_then(|v| v.as_object().cloned())
        .ok_or_else(|| venice_failure(TransportError::Other))
}

/// `VeniceModelsClient.fetch_models`: the public text catalog (offline models
/// and unknown prices kept), sorted by name. `Err` is shown to the user.
pub fn fetch_venice_models(api_key: Option<&str>) -> Result<Vec<CatalogModel>, String> {
    fetch_venice_models_at(VENICE_BASE_URL, api_key.unwrap_or("").trim())
}

pub(crate) fn fetch_venice_models_at(
    base_url: &str,
    api_key: &str,
) -> Result<Vec<CatalogModel>, String> {
    let payload = venice_get(base_url, "models?type=text", api_key)?;
    let rows = payload
        .get("data")
        .and_then(Value::as_array)
        .ok_or("Venice returned an unreadable model catalog.")?;
    let mut models: Vec<CatalogModel> = rows
        .iter()
        .filter_map(Value::as_object)
        .filter(|row| {
            row.get("id")
                .and_then(Value::as_str)
                .is_some_and(|id| !id.is_empty())
                && row.get("type").is_none_or(|t| t == "text")
        })
        .map(parse_venice_model)
        .collect();
    models.sort_by_cached_key(|m| casefold(&m.name));
    Ok(models)
}

/// Venice account state; `None` means the service did not supply a known value.
#[derive(Debug, Clone, PartialEq)]
pub struct VeniceBalance {
    pub can_consume: Option<bool>,
    pub consumption_currency: Option<String>,
    pub usd: Option<f64>,
    pub diem: Option<f64>,
}

/// `parse` half of `VeniceModelsClient.fetch_balance`.
pub fn parse_venice_balance(payload: &Map<String, Value>) -> VeniceBalance {
    let balances = object(payload.get("balances"));
    VeniceBalance {
        can_consume: payload.get("canConsume").and_then(Value::as_bool),
        consumption_currency: payload
            .get("consumptionCurrency")
            .and_then(Value::as_str)
            .filter(|c| ["USD", "DIEM", "VCU", "BUNDLED_CREDITS"].contains(c))
            .map(String::from),
        usd: venice_number(balances.get("usd")),
        diem: venice_number(balances.get("diem")),
    }
}

/// Fresh authenticated balance state; never infers missing amounts.
pub fn fetch_venice_balance(api_key: &str) -> Result<VeniceBalance, String> {
    fetch_venice_balance_at(VENICE_BASE_URL, api_key.trim())
}

pub(crate) fn fetch_venice_balance_at(
    base_url: &str,
    api_key: &str,
) -> Result<VeniceBalance, String> {
    if api_key.is_empty() {
        return Err("A Venice API key is required to check your balance.".into());
    }
    venice_get(base_url, "billing/balance", api_key).map(|p| parse_venice_balance(&p))
}

/// `validate_model_id`: whether OpenRouter lists the model; assumed valid
/// when the catalog cannot be fetched.
pub fn validate_model_id(model_id: &str) -> bool {
    fetch_openrouter_models(None).map_or(true, |models| models.iter().any(|m| m.id == model_id))
}

/// `validate_and_get_fallback`: `(model, was_fallback)`; unknown models fall
/// back to the free router (the startup check then offers a reset).
pub fn validate_and_get_fallback(model_id: &str) -> (String, bool) {
    if ["auto", DEFAULT_PAID_MODEL, DEFAULT_FREE_MODEL].contains(&model_id)
        || validate_model_id(model_id)
    {
        (model_id.to_string(), false)
    } else {
        (DEFAULT_FREE_MODEL.to_string(), true)
    }
}

/// Text of the startup "AI Model Not Found" question.
pub fn invalid_model_warning(invalid_model: &str) -> String {
    format!(
        "Your configured AI model '{invalid_model}' is no longer available on OpenRouter.\n\nIt may have been removed or renamed.\n\nWould you like to reset to the default model ({DEFAULT_FREE_MODEL})?\n\nClick 'Yes' to reset, or 'No' to open Settings and choose a different model."
    )
}

/// What the model browser shows after loading.
#[derive(Debug, Clone, PartialEq)]
pub struct CatalogLoad {
    /// The models, or the error for the status label ("Error: {error}").
    pub models: Result<Vec<CatalogModel>, String>,
    /// Venice only, when a key was given and the lookup succeeded.
    pub balance: Option<VeniceBalance>,
}

/// The model browser's background load: text models (and Venice credit
/// status). OpenRouter failures get one generic message.
pub fn load_catalog(provider: Provider, api_key: Option<&str>) -> CatalogLoad {
    match provider {
        Provider::OpenRouter => CatalogLoad {
            models: fetch_openrouter_models(api_key)
                .map(|models| models.into_iter().filter(CatalogModel::is_text).collect())
                .map_err(|_| {
                    "Unable to load models. Check your connection and API key, then refresh."
                        .to_string()
                }),
            balance: None,
        },
        Provider::Venice => {
            let key = api_key.unwrap_or("").trim();
            let models = fetch_venice_models(Some(key));
            let balance = models
                .is_ok()
                .then(|| fetch_venice_balance(key).ok())
                .flatten();
            CatalogLoad { models, balance }
        }
    }
}

/// `PROVIDER_DISPLAY_NAMES` with the title-case fallback.
pub fn provider_display_name(provider: &str) -> String {
    let known = match provider {
        "openai" => "OpenAI",
        "anthropic" => "Anthropic",
        "google" => "Google",
        "meta-llama" => "Meta",
        "mistralai" => "Mistral AI",
        "cohere" => "Cohere",
        "perplexity" => "Perplexity",
        "deepseek" => "DeepSeek",
        "microsoft" => "Microsoft",
        "amazon" => "Amazon",
        "nvidia" => "NVIDIA",
        "qwen" => "Qwen",
        "x-ai" => "xAI",
        "ai21" => "AI21 Labs",
        "databricks" => "Databricks",
        "inflection" => "Inflection",
        "cognitivecomputations" => "Cognitive Computations",
        "nousresearch" => "Nous Research",
        "openchat" => "OpenChat",
        "openrouter" => "OpenRouter",
        "neversleep" => "NeverSleep",
        "gryphe" => "Gryphe",
        "undi95" => "Undi95",
        "huggingfaceh4" => "Hugging Face",
        "pygmalionai" => "Pygmalion AI",
        "mancer" => "Mancer",
        "lynn" => "Lynn",
        "thedrummer" => "TheDrummer",
        "sao10k" => "Sao10k",
        "eva-unit-01" => "Eva Unit 01",
        "aetherwiing" => "Aetherwiing",
        "sophosympatheia" => "Sophosympatheia",
        "liquid" => "Liquid",
        "01-ai" => "01.AI",
        "venice" => "Venice",
        "moonshotai" => "Moonshot AI",
        "z-ai" => "Z.ai",
        "minimax" => "MiniMax",
        "xiaomi" => "Xiaomi",
        "bytedance" => "ByteDance",
        "inception" => "Inception",
        "aion-labs" => "Aion Labs",
        other => return pyfmt::title(&other.replace('-', " ")),
    };
    known.to_string()
}

/// The Venice "Price:" choice.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum PriceFilter {
    #[default]
    All,
    Free,
    Paid,
}

/// The model browser's filter controls.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct BrowserFilter {
    pub search: String,
    /// OpenRouter "Free only".
    pub free_only: bool,
    /// Venice "Price:".
    pub price: PriceFilter,
    /// Venice "Weather assistant compatible".
    pub function_calling_only: bool,
    /// Selected provider id; `None` is "All Providers".
    pub provider: Option<String>,
}

/// `_matches_price_and_capability`: only explicitly known metadata counts.
pub fn matches_price_and_capability(
    catalog: Provider,
    model: &CatalogModel,
    filter: &BrowserFilter,
) -> bool {
    if catalog == Provider::OpenRouter {
        return !filter.free_only || model.is_free;
    }
    let priced = |p: Option<f64>| p.is_some_and(|p| p > 0.0);
    match filter.price {
        PriceFilter::Free if !model.is_free => return false,
        PriceFilter::Paid
            if !(priced(model.pricing_prompt) || priced(model.pricing_completion)) =>
        {
            return false
        }
        _ => {}
    }
    !filter.function_calling_only || model.supports_function_calling
}

/// `_update_provider_list`: sorted provider ids among models passing the
/// price/capability filters (shown after "All Providers" by display name).
pub fn provider_ids(
    catalog: Provider,
    models: &[CatalogModel],
    filter: &BrowserFilter,
) -> Vec<String> {
    let mut ids: Vec<String> = models
        .iter()
        .filter(|m| matches_price_and_capability(catalog, m, filter))
        .map(|m| m.provider.clone())
        .collect();
    ids.sort();
    ids.dedup();
    ids
}

/// `_apply_filters`: price/capability, provider, then search on name, id and
/// description.
pub fn filter_models<'a>(
    catalog: Provider,
    models: &'a [CatalogModel],
    filter: &BrowserFilter,
) -> Vec<&'a CatalogModel> {
    let search = filter.search.to_lowercase();
    let search = search.trim();
    models
        .iter()
        .filter(|m| matches_price_and_capability(catalog, m, filter))
        .filter(|m| filter.provider.as_ref().is_none_or(|p| &m.provider == p))
        .filter(|m| {
            search.is_empty()
                || m.name.to_lowercase().contains(search)
                || m.id.to_lowercase().contains(search)
                || m.description.to_lowercase().contains(search)
        })
        .collect()
}

/// `_model_pricing`: both token directions, unknown values explicit.
pub fn model_pricing(model: &CatalogModel) -> String {
    if model.is_free {
        return "Free".into();
    }
    let price =
        |value: Option<f64>| value.map_or("unknown".into(), |v| format!("${}", format_g(v)));
    format!(
        "Input: {}; output: {} per million tokens",
        price(model.pricing_prompt),
        price(model.pricing_completion)
    )
}

/// One entry of the "Available models" list.
pub fn list_item(catalog: Provider, model: &CatalogModel) -> String {
    let pricing = match catalog {
        Provider::Venice => model_pricing(model),
        Provider::OpenRouter if model.is_free => "Free".into(),
        // Prices are per token-million; the list shows "per 1K" as Python does.
        Provider::OpenRouter => format!(
            "${:.6} per 1K tokens",
            model.pricing_prompt.unwrap_or(0.0) / 1000.0
        ),
    };
    let mut item = format!(
        "{} - Context: {} - {pricing}",
        model.display_name(),
        model.context_display()
    );
    if catalog == Provider::Venice {
        item.push_str(if model.supports_function_calling {
            " - Weather assistant compatible"
        } else {
            " - Explanations only"
        });
    }
    item
}

/// The status label after filtering.
pub fn status_text(showing: usize, total: usize) -> String {
    if showing == total {
        format!("{total} models available")
    } else {
        format!("Showing {showing} of {total} models")
    }
}

/// The "Model description" text for a selected model.
pub fn description_text(catalog: Provider, model: &CatalogModel) -> String {
    let mut description = if model.description.is_empty() {
        "No description available.".to_string()
    } else {
        model.description.clone()
    };
    if catalog == Provider::Venice {
        if model.offline {
            description.push_str("\nThis model is offline and unavailable for selection.");
        }
        description.push('\n');
        description.push_str(&model_pricing(model));
        description.push_str(if model.supports_function_calling {
            "\nSupports weather assistant function calling."
        } else {
            "\nDoes not support weather assistant function calling; use for explanations only."
        });
    }
    description
}

/// Announced when an offline Venice model is chosen.
pub const OFFLINE_MODEL_MESSAGE: &str = "This model is offline and unavailable for selection.";
/// The Venice credit label without a key.
pub const VENICE_NO_KEY_STATUS: &str = "Add a Venice API key to check account credits. The public model catalog is available without a key.";
/// The Venice credit label while loading.
pub const VENICE_CHECKING_STATUS: &str = "Checking Venice account credit status\u{2026}";

/// `_balance_status`: account permission without implying a model is
/// affordable or free.
pub fn balance_status(balance: Option<&VeniceBalance>) -> String {
    let mut amounts = Vec::new();
    if let Some(b) = balance {
        if let Some(usd) = b.usd {
            amounts.push(format!("USD: ${}", format_g(usd)));
        }
        if let Some(diem) = b.diem {
            amounts.push(format!("DIEM: {}", format_g(diem)));
        }
        if let Some(currency) = &b.consumption_currency {
            amounts.push(format!("Consumption currency: {currency}"));
        }
    }
    let prefix = if amounts.is_empty() {
        String::new()
    } else {
        format!("{}. ", amounts.join("; "))
    };
    let status = match balance.and_then(|b| b.can_consume.map(|c| (b, c))) {
        None => "Credit status unknown. Paid models remain selectable; check your Venice API account before use.",
        Some((b, false)) if b.usd == Some(0.0) && b.diem == Some(0.0) => {
            "No API credits available. Paid models remain selectable but need credits before use."
        }
        Some((_, false)) => "Account cannot currently consume API credits. Paid models remain selectable but require usable credits before use.",
        Some((_, true)) => "Account can consume API credits. Paid model charges still apply; this does not guarantee enough credit for a request.",
    };
    format!("{prefix}{status}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_server::{Reply, TestServer};
    use serde_json::json;

    fn venice(row: Value) -> CatalogModel {
        parse_venice_model(row.as_object().unwrap())
    }

    #[test]
    fn venice_prices_are_free_only_when_explicitly_zero() {
        let free = venice(
            json!({"id": "a", "model_spec": {"pricing": {"input": {"usd": 0}, "output": {"usd": "0"}}}}),
        );
        assert!(free.is_free);
        for value in [json!(null), json!("x"), json!(-1), json!(true)] {
            let m = venice(
                json!({"id": "a", "model_spec": {"pricing": {"input": {"usd": value}, "output": {"usd": 0}}}}),
            );
            assert!(!m.is_free);
            assert_eq!(m.pricing_prompt, None);
        }
    }

    #[test]
    fn venice_filters_keep_unknown_prices_out_of_free_and_paid() {
        let models = [
            venice(
                json!({"id": "free", "model_spec": {"pricing": {"input": {"usd": 0}, "output": {"usd": 0}}, "capabilities": {"supportsFunctionCalling": true}}}),
            ),
            venice(
                json!({"id": "paid", "model_spec": {"pricing": {"input": {"usd": 0.5}, "output": {"usd": 2}}}}),
            ),
            venice(json!({"id": "unknown", "model_spec": {}})),
        ];
        let ids = |f: &BrowserFilter| -> Vec<String> {
            filter_models(Provider::Venice, &models, f)
                .iter()
                .map(|m| m.id.clone())
                .collect()
        };
        let mut filter = BrowserFilter {
            price: PriceFilter::Free,
            ..Default::default()
        };
        assert_eq!(ids(&filter), ["free"]);
        filter.price = PriceFilter::Paid;
        assert_eq!(ids(&filter), ["paid"]);
        filter.price = PriceFilter::All;
        filter.function_calling_only = true;
        assert_eq!(ids(&filter), ["free"]);
        assert_eq!(
            model_pricing(&models[1]),
            "Input: $0.5; output: $2 per million tokens"
        );
        assert_eq!(
            model_pricing(&models[2]),
            "Input: unknown; output: unknown per million tokens"
        );
        assert!(list_item(Provider::Venice, &models[0])
            .ends_with("Free - Weather assistant compatible"));
    }

    #[test]
    fn credit_status_uses_permission_not_positive_balance() {
        let balance = |c: Option<bool>, usd: Option<f64>, diem: Option<f64>| VeniceBalance {
            can_consume: c,
            consumption_currency: None,
            usd,
            diem,
        };
        assert!(balance_status(None).starts_with("Credit status unknown."));
        assert_eq!(
            balance_status(Some(&balance(Some(false), Some(0.0), Some(0.0)))),
            "USD: $0; DIEM: 0. No API credits available. Paid models remain selectable but need credits before use."
        );
        assert!(balance_status(Some(&balance(Some(true), Some(0.0), None)))
            .contains("Account can consume"));
        assert!(balance_status(Some(&balance(Some(false), Some(3.5), None)))
            .contains("cannot currently consume"));
    }

    #[test]
    fn catalogs_load_sort_filter_and_redact_errors() {
        let server = TestServer::start(vec![Reply::json(
            200,
            json!({"data": [
                {"id": "b/model", "name": "Beta", "pricing": {"prompt": "0.000002", "completion": "0.000004"}, "context_length": 128000},
                {"id": "a/img", "name": "alpha", "architecture": {"input_modalities": ["image"], "output_modalities": ["image"]}},
                {"id": "c/free:free", "name": "Gamma", "pricing": {"prompt": "0.1"}},
            ]}),
        )]);
        let models = fetch_openrouter_models_at(&server.url(), Some("k")).unwrap();
        let names: Vec<&str> = models.iter().map(|m| m.name.as_str()).collect();
        assert_eq!(names, ["alpha", "Beta", "Gamma"]);
        assert!(models[0].is_free && !models[1].is_free && models[2].is_free);
        assert_eq!(
            list_item(Provider::OpenRouter, &models[1]),
            "Beta - Context: 128K - $0.000000 per 1K tokens"
        );
        assert_eq!(
            server.requests()[0].header("authorization"),
            Some("Bearer k")
        );

        let server = TestServer::start(vec![
            Reply::json(
                200,
                json!({"data": [
                    {"id": "z", "type": "text", "model_spec": {"name": "Zeta", "offline": true}},
                    {"id": "img", "type": "image", "model_spec": {}},
                    {"id": "", "model_spec": {}},
                    {"id": "qwen-3", "model_spec": {"name": "alpha"}},
                ]}),
            ),
            Reply::text(403, "private"),
        ]);
        let models = fetch_venice_models_at(&server.url(), "").unwrap();
        assert_eq!(
            models.iter().map(|m| m.id.as_str()).collect::<Vec<_>>(),
            ["qwen-3", "z"]
        );
        assert_eq!(models[0].provider, "qwen");
        assert!(models[1].display_name().ends_with("(Offline)"));
        assert_eq!(server.requests()[0].path, "/models?type=text");
        assert!(server.requests()[0].header("authorization").is_none());
        let error = fetch_venice_balance_at(&server.url(), "key").unwrap_err();
        assert!(error.starts_with("Your Venice key cannot access") && !error.contains("private"));
        assert!(fetch_venice_balance_at(&server.url(), "")
            .unwrap_err()
            .contains("required"));
    }

    #[test]
    fn provider_names_and_inference() {
        assert_eq!(provider_display_name("meta-llama"), "Meta");
        assert_eq!(provider_display_name("some-new-lab"), "Some New Lab");
        assert_eq!(
            infer_venice_provider("e2ee-venice-uncensored", ""),
            "venice"
        );
        assert_eq!(
            infer_venice_provider("llama-3.3-70b", "Llama"),
            "meta-llama"
        );
        assert_eq!(infer_venice_provider("mystery", "Unknown"), "venice");
    }
}
