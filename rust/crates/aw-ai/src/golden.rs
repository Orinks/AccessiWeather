//! Golden parity tests: outputs recorded from the Python app by
//! `rust/tools/golden/ai.py` into `rust/testdata/golden/ai/`.

use std::sync::Mutex;

use aw_core::model::{Location, WeatherAlert, WeatherAlerts, WeatherData};
use aw_core::settings::AppSettings;
use chrono::{DateTime, FixedOffset, Utc};
use serde_json::{json, Map, Value};

use crate::assistant::{
    build_weather_context, explicitly_requested_location, needs_live_weather, prepare_request,
    run_assistant_request, AssistantClient, SYSTEM_PROMPT,
};
use crate::errors::{
    describe_generation_error, is_model_refusal, openrouter_error, openrouter_generation_error,
    venice_error, AiError, AiErrorKind, TransportError,
};
use crate::explainer::{
    default_system_prompt, describe_model_attempt, estimate_cost, format_response,
    model_selection_reason, sanitize_prompt, AiExplainer, ExplanationStyle,
};
use crate::formatters::{
    format_alerts, format_current_weather, format_forecast, format_hourly_forecast,
    format_location_search, format_open_meteo_response,
};
use crate::models::{
    balance_status, description_text, filter_models, list_item, parse_openrouter_model,
    parse_venice_balance, parse_venice_model, provider_display_name, provider_ids, status_text,
    BrowserFilter, CatalogModel, PriceFilter,
};
use crate::payload::{add_location_time_context, build_current_weather_payload};
use crate::provider::Provider;
use crate::test_server::{Reply, TestServer};
use crate::tools::{
    core_tools, discussion_tools, extended_tools, tools_for_message, AssistantHost,
    WeatherToolExecutor,
};

fn load(name: &str) -> Value {
    let path = format!(
        "{}/../../testdata/golden/ai/{name}.json",
        env!("CARGO_MANIFEST_DIR")
    );
    serde_json::from_str(&std::fs::read_to_string(&path).expect(&path)).expect("golden JSON")
}

/// JSON equality with numbers compared by value (Python ints vs Rust f64).
fn same(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => close(x.as_f64(), y.as_f64()),
        (Value::Array(x), Value::Array(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(a, b)| same(a, b))
        }
        (Value::Object(x), Value::Object(y)) => {
            x.len() == y.len() && x.iter().all(|(k, v)| y.get(k).is_some_and(|w| same(v, w)))
        }
        _ => a == b,
    }
}

/// serde_json's default float parsing can be one ulp off Python's repr.
fn close(a: Option<f64>, b: Option<f64>) -> bool {
    match (a, b) {
        (Some(a), Some(b)) => a == b || (a - b).abs() <= 1e-12 * a.abs().max(b.abs()),
        _ => a == b,
    }
}

fn s(v: &Value) -> &str {
    v.as_str().unwrap_or("")
}

fn opt(v: &Value) -> Option<&str> {
    v.as_str()
}

fn utc(v: &Value) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(s(v))
        .unwrap()
        .with_timezone(&Utc)
}

fn style(v: &Value) -> ExplanationStyle {
    ExplanationStyle::from_setting(s(v))
}

fn provider(v: &Value) -> Provider {
    match s(v) {
        "venice" => Provider::Venice,
        _ => Provider::OpenRouter,
    }
}

fn explainer(config: &Value) -> AiExplainer {
    AiExplainer::new(
        provider(&config["provider"]),
        opt(&config["api_key"]).map(String::from),
        s(&config["model"]),
        opt(&config["custom_system_prompt"]),
        opt(&config["custom_instructions"]),
    )
}

fn object(v: &Value) -> &Map<String, Value> {
    v.as_object().expect("object")
}

#[test]
fn prompts_match_python() {
    let golden = load("prompts");
    assert_eq!(default_system_prompt(), golden["default_system_prompt"]);
    for case in golden["payload_cases"].as_array().unwrap() {
        let weather: WeatherData = serde_json::from_value(case["weather"].clone()).unwrap();
        let location: Location = serde_json::from_value(case["location"].clone()).unwrap();
        let mut payload = build_current_weather_payload(
            &weather,
            s(&case["temperature_unit"]),
            s(&case["wind_speed_unit"]),
            Some(&location),
        );
        add_location_time_context(&mut payload, &location, utc(&case["now"]));
        let label = format!("{} {}", case["fixture"], case["temperature_unit"]);
        assert!(
            same(&Value::Object(payload.clone()), &case["payload"]),
            "{label}\n{}\n{}",
            Value::Object(payload.clone()),
            case["payload"]
        );
        let e = explainer(&case["config"]);
        let st = style(&case["style"]);
        let preserve = case["preserve_markdown"].as_bool().unwrap();
        assert_eq!(e.effective_model(), case["effective_model"], "{label}");
        assert_eq!(e.effective_system_prompt(st), case["system"], "{label}");
        assert_eq!(
            e.build_prompt(&payload, &location.name),
            case["user"],
            "{label}"
        );
        assert_eq!(
            e.cache_key(&payload, &location.name, st, preserve),
            case["cache_key"],
            "{label}"
        );
    }
    for case in golden["dict_cases"].as_array().unwrap() {
        let e = explainer(&case["config"]);
        let weather = object(&case["weather"]);
        let st = style(&case["style"]);
        assert_eq!(e.effective_system_prompt(st), case["system"]);
        assert_eq!(
            e.build_prompt(weather, "Sample Location"),
            case["user"],
            "{case}"
        );
        assert_eq!(
            e.cache_key(weather, "Sample Location", st, false),
            case["cache_key"]
        );
    }
    for case in golden["text_product_cases"].as_array().unwrap() {
        let e = explainer(&case["config"]);
        let st = style(&case["style"]);
        let (text, kind, location) = (
            s(&case["product_text"]),
            s(&case["product_type"]),
            s(&case["location"]),
        );
        assert_eq!(e.effective_system_prompt(st), case["system"]);
        assert_eq!(
            e.build_text_product_prompt(text, kind, location, st),
            case["user"]
        );
        assert_eq!(
            e.text_product_cache_key(kind, location, text, st),
            case["cache_key"]
        );
    }
    for case in golden["sanitize_cases"].as_array().unwrap() {
        assert_eq!(
            sanitize_prompt(opt(&case["input"])).as_deref(),
            opt(&case["output"]),
            "{case}"
        );
    }
}

fn names(tools: &[Value]) -> Vec<String> {
    tools
        .iter()
        .map(|t| s(&t["function"]["name"]).to_string())
        .collect()
}

#[test]
fn tool_schemas_and_selection_match_python() {
    let golden = load("tools");
    assert_eq!(Value::Array(core_tools()), golden["core"]);
    assert_eq!(Value::Array(extended_tools()), golden["extended"]);
    assert_eq!(Value::Array(discussion_tools()), golden["discussion"]);
    for case in golden["selection"].as_array().unwrap() {
        assert_eq!(
            json!(names(&tools_for_message(s(&case["message"])))),
            case["tools"],
            "{}",
            case["message"]
        );
    }
}

#[test]
fn tool_formatters_match_python() {
    for case in load("formatters").as_array().unwrap() {
        let data = &case["data"];
        let name = s(&case["display_name"]);
        let output = match s(&case["fn"]) {
            "current" => format_current_weather(data, name),
            "forecast" => format_forecast(data, name, case["forecast_days"].as_i64().unwrap_or(7)),
            "alerts" => format_alerts(data, name),
            "hourly" => format_hourly_forecast(data, name, utc(&case["now"])),
            "open_meteo" => format_open_meteo_response(data, name, utc(&case["now"])),
            _ => {
                let suggestions: Vec<String> =
                    serde_json::from_value(case["suggestions"].clone()).unwrap();
                format_location_search(&suggestions, s(&case["query"]))
            }
        };
        assert_eq!(output, s(&case["output"]), "{} {}", case["fn"], data);
    }
}

/// The scripted host of an executor scenario; records calls like the
/// Python fakes do.
struct GoldenHost {
    host: Value,
    calls: Mutex<Vec<Value>>,
}

impl GoldenHost {
    fn record(&self, call: Value) {
        self.calls.lock().unwrap().push(call);
    }

    fn data(&self, key: &str) -> Result<Value, String> {
        match &self.host[key] {
            Value::Object(o) if o.len() == 1 && o.contains_key("error") => {
                Err(s(&o["error"]).to_string())
            }
            other => Ok(other.clone()),
        }
    }
}

impl AssistantHost for GoldenHost {
    fn geocode(&self, query: &str) -> Option<(f64, f64, String)> {
        self.record(json!(["geocode", query]));
        let found = self.host["geocode"].get(query)?;
        Some((
            found[0].as_f64()?,
            found[1].as_f64()?,
            s(&found[2]).to_string(),
        ))
    }
    fn suggest_locations(&self, query: &str, limit: usize) -> Vec<String> {
        self.record(json!(["suggest", query, limit]));
        serde_json::from_value(
            self.host["suggest"]
                .get(query)
                .cloned()
                .unwrap_or(json!([])),
        )
        .unwrap()
    }
    fn current_conditions(&self, lat: f64, lon: f64) -> Result<Value, String> {
        self.record(json!(["current", lat, lon]));
        self.data("current")
    }
    fn forecast(&self, lat: f64, lon: f64, days: u32) -> Result<Value, String> {
        self.record(json!(["forecast", lat, lon, days]));
        self.data("forecast")
    }
    fn hourly_forecast(&self, lat: f64, lon: f64) -> Result<Value, String> {
        self.record(json!(["hourly", lat, lon]));
        self.data("hourly")
    }
    fn alerts(&self, lat: f64, lon: f64) -> Result<Value, String> {
        self.record(json!(["alerts", lat, lon]));
        self.data("alerts")
    }
    fn discussion(&self, lat: f64, lon: f64) -> Result<Option<String>, String> {
        self.record(json!(["discussion", lat, lon]));
        self.data("discussion")
            .map(|v| v.as_str().map(String::from))
    }
    fn wpc_short_range_discussion(&self) -> Result<String, String> {
        self.data("wpc").map(|v| s(&v).to_string())
    }
    fn spc_day1_outlook(&self) -> Result<String, String> {
        self.data("spc").map(|v| s(&v).to_string())
    }
    fn open_meteo_forecast(&self, params: &[(&'static str, String)]) -> Result<Value, String> {
        self.record(json!(["open_meteo", params]));
        self.data("open_meteo")
    }
    fn location_names(&self) -> Vec<String> {
        serde_json::from_value(self.host["location_names"].clone()).unwrap()
    }
    fn add_location(&self, name: &str, latitude: f64, longitude: f64) -> bool {
        self.record(json!(["add_location", name, latitude, longitude]));
        self.host["add_result"] == true
            && (-90.0..=90.0).contains(&latitude)
            && (-180.0..=180.0).contains(&longitude)
    }
    fn saved_locations(&self) -> Vec<Location> {
        serde_json::from_value(self.host["saved"].clone()).unwrap()
    }
    fn current_location_name(&self) -> Option<String> {
        opt(&self.host["current_name"]).map(String::from)
    }
}

#[test]
fn tool_executor_matches_python() {
    let now = DateTime::parse_from_rfc3339("2026-09-25T18:05:30.123456Z")
        .unwrap()
        .with_timezone(&Utc);
    for scenario in load("executor").as_array().unwrap() {
        let host = GoldenHost {
            host: scenario["host"].clone(),
            calls: Mutex::new(Vec::new()),
        };
        let default = &scenario["default"];
        let location = default.is_object().then(|| {
            Location::new(
                s(&default["name"]),
                default["lat"].as_f64().unwrap(),
                default["lon"].as_f64().unwrap(),
            )
        });
        let displayed = location.as_ref().and_then(|loc| {
            let alerts: Vec<WeatherAlert> =
                serde_json::from_value(scenario["displayed_alerts"].clone()).ok()?;
            let mut weather = WeatherData::new(loc.clone());
            weather.alerts = Some(WeatherAlerts { alerts });
            Some(weather)
        });
        let executor = WeatherToolExecutor::new(&host, location.as_ref(), displayed.as_ref(), now);
        for call in scenario["calls"].as_array().unwrap() {
            host.calls.lock().unwrap().clear();
            let output = match executor.execute(s(&call["tool"]), object(&call["args"])) {
                Ok(text) => json!(text),
                Err(raised) => json!({"raised": raised}),
            };
            let label = format!("{} {} {}", scenario["name"], call["tool"], call["args"]);
            assert_eq!(output, call["output"], "{label}");
            let calls = Value::Array(host.calls.lock().unwrap().clone());
            assert!(
                same(&calls, &call["host_calls"]),
                "{label}: {calls} vs {}",
                call["host_calls"]
            );
        }
    }
}

fn catalog_row(model: &CatalogModel) -> Value {
    json!({
        "id": model.id, "name": model.name, "description": model.description,
        "context_length": model.context_length, "pricing_prompt": model.pricing_prompt,
        "pricing_completion": model.pricing_completion, "is_free": model.is_free,
        "provider": model.provider, "display_name": model.display_name(),
        "context_display": model.context_display(),
        "supports_function_calling": model.supports_function_calling, "offline": model.offline,
    })
}

fn check_browser(catalog: Provider, models: &[CatalogModel], cases: &Value) {
    for case in cases.as_array().unwrap() {
        let f = &case["filter"];
        let filter = BrowserFilter {
            search: s(&f["search"]).into(),
            free_only: f["free_only"] == true,
            price: match f["price"].as_u64() {
                Some(1) => PriceFilter::Free,
                Some(2) => PriceFilter::Paid,
                _ => PriceFilter::All,
            },
            function_calling_only: f["function_calling_only"] == true,
            provider: None,
        };
        let providers = provider_ids(catalog, models, &filter);
        assert_eq!(json!(providers), case["providers"], "{f}");
        let display: Vec<String> = providers.iter().map(|p| provider_display_name(p)).collect();
        assert_eq!(json!(display), case["provider_names"]);
        let filter = BrowserFilter {
            provider: opt(&f["provider"])
                .filter(|p| providers.iter().any(|x| x == p))
                .map(String::from),
            ..filter
        };
        let shown = filter_models(catalog, models, &filter);
        let ids: Vec<&str> = shown.iter().map(|m| m.id.as_str()).collect();
        assert_eq!(json!(ids), case["ids"], "{f}");
        let items: Vec<String> = shown.iter().map(|m| list_item(catalog, m)).collect();
        assert_eq!(json!(items), case["items"], "{f}");
        assert_eq!(status_text(shown.len(), models.len()), case["status"]);
        let descriptions: Vec<String> =
            shown.iter().map(|m| description_text(catalog, m)).collect();
        assert_eq!(json!(descriptions), case["descriptions"], "{f}");
    }
}

#[test]
fn model_catalogs_and_browser_match_python() {
    let golden = load("models");
    let mut openrouter: Vec<CatalogModel> = golden["openrouter_rows"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| parse_openrouter_model(object(row)))
        .collect();
    openrouter.sort_by_cached_key(|m| m.name.to_lowercase());
    for (model, expected) in openrouter
        .iter()
        .zip(golden["openrouter"].as_array().unwrap())
    {
        let mut expected = expected.clone();
        if expected["description"].is_null() {
            expected["description"] = json!("");
        }
        assert!(
            same(&catalog_row(model), &expected),
            "{}\n{expected}",
            catalog_row(model)
        );
    }
    let text: Vec<CatalogModel> = openrouter
        .iter()
        .filter(|m| {
            m.input_modalities.iter().any(|x| x == "text")
                && m.output_modalities.iter().any(|x| x == "text")
        })
        .cloned()
        .collect();
    let ids: Vec<&str> = text.iter().map(|m| m.id.as_str()).collect();
    assert_eq!(json!(ids), golden["openrouter_text_ids"]);
    check_browser(Provider::OpenRouter, &text, &golden["openrouter_browser"]);

    let mut venice: Vec<CatalogModel> = golden["venice_rows"]
        .as_array()
        .unwrap()
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
    venice.sort_by_cached_key(|m| crate::pyfmt::casefold(&m.name));
    let rows: Vec<Value> = venice.iter().map(catalog_row).collect();
    assert!(same(&json!(rows), &golden["venice"]), "{}", json!(rows));
    check_browser(Provider::Venice, &venice, &golden["venice_browser"]);

    for case in golden["balances"].as_array().unwrap() {
        let balance = case["payload"].as_object().map(parse_venice_balance);
        if let Some(b) = &balance {
            let fields = json!({"can_consume": b.can_consume, "consumption_currency": b.consumption_currency,
                                "usd": b.usd, "diem": b.diem});
            assert!(
                same(&fields, &case["balance"]),
                "{fields} vs {}",
                case["balance"]
            );
        }
        assert_eq!(balance_status(balance.as_ref()), case["status"]);
    }
    for (id, name) in object(&golden["provider_names"]) {
        assert_eq!(provider_display_name(id), s(name));
    }
}

fn kind_name(kind: AiErrorKind) -> &'static str {
    match kind {
        AiErrorKind::Explainer => "AIExplainerError",
        AiErrorKind::InsufficientCredits => "InsufficientCreditsError",
        AiErrorKind::RateLimit => "RateLimitError",
        AiErrorKind::InvalidApiKey => "InvalidAPIKeyError",
        AiErrorKind::ProviderPermission => "ProviderPermissionError",
        AiErrorKind::InvalidModel => "InvalidModelError",
        AiErrorKind::Network => "NetworkError",
        AiErrorKind::Timeout => "RequestTimeoutError",
        AiErrorKind::EmptyResponse => "EmptyResponseError",
        AiErrorKind::Cancelled => "Cancelled",
    }
}

fn kind_from_name(name: &str) -> AiErrorKind {
    [
        AiErrorKind::Explainer,
        AiErrorKind::InsufficientCredits,
        AiErrorKind::RateLimit,
        AiErrorKind::InvalidApiKey,
        AiErrorKind::ProviderPermission,
        AiErrorKind::InvalidModel,
        AiErrorKind::Network,
        AiErrorKind::Timeout,
        AiErrorKind::EmptyResponse,
    ]
    .into_iter()
    .find(|k| kind_name(*k) == name)
    .expect(name)
}

fn transport(v: &Value) -> TransportError {
    if let Some(status) = v["status"].as_u64() {
        TransportError::Status {
            status: status as u16,
            body: s(&v["body"]).into(),
        }
    } else if v["api"].is_object() {
        TransportError::Api {
            code: opt(&v["api"]["code"]).map(String::from),
            message: s(&v["api"]["message"]).into(),
        }
    } else if v["timeout"] == true {
        TransportError::Timeout
    } else {
        TransportError::Connect
    }
}

#[test]
fn responses_and_errors_match_python() {
    let golden = load("responses");
    for case in golden["markdown"].as_array().unwrap() {
        assert_eq!(
            format_response(s(&case["input"]), case["preserve"] == true),
            case["output"],
            "{case}"
        );
    }
    for case in golden["refusals"].as_array().unwrap() {
        assert_eq!(
            is_model_refusal(s(&case["input"])),
            case["refusal"] == true,
            "{case}"
        );
    }
    for case in golden["live_weather"].as_array().unwrap() {
        assert_eq!(
            needs_live_weather(s(&case["input"])),
            case["live"] == true,
            "{case}"
        );
    }
    for case in golden["explicit_location"].as_array().unwrap() {
        assert_eq!(
            explicitly_requested_location(s(&case["user"]), s(&case["tool"]), s(&case["selected"])),
            case["explicit"] == true,
            "{case}"
        );
    }
    for case in golden["attempts"].as_array().unwrap() {
        let text = describe_model_attempt(
            provider(&case["provider"]),
            s(&case["model"]),
            s(&case["primary"]),
            case["index"].as_u64().unwrap() as usize,
        );
        assert_eq!(text, case["text"], "{case}");
    }
    for case in golden["selection_reasons"].as_array().unwrap() {
        let attempted: Vec<String> = serde_json::from_value(case["attempted"].clone()).unwrap();
        let error = case["error"]
            .as_object()
            .map(|e| AiError::new(kind_from_name(s(&e["kind"])), s(&e["message"])));
        let text = model_selection_reason(
            provider(&case["provider"]),
            s(&case["requested"]),
            s(&case["used"]),
            &attempted,
            error.as_ref(),
        );
        assert_eq!(text, case["text"], "{case}");
    }
    for case in golden["costs"].as_array().unwrap() {
        let cost = estimate_cost(
            provider(&case["provider"]),
            s(&case["model"]),
            case["tokens"].as_u64().unwrap(),
        );
        assert!(close(cost, case["cost"].as_f64()), "{case}: {cost:?}");
    }
    for case in golden["errors"].as_array().unwrap() {
        let error = transport(&case["transport"]);
        let generated = openrouter_generation_error(&error, s(&case["model"]));
        let expected = &case["generation"];
        assert_eq!(kind_name(generated.kind), expected["kind"], "{case}");
        assert_eq!(generated.message, s(&expected["message"]), "{case}");
        assert_eq!(
            describe_generation_error(&generated),
            expected["describe"],
            "{case}"
        );
        for (mapped, key) in [
            (openrouter_error(&error), "openrouter"),
            (venice_error(&error), "venice"),
        ] {
            assert_eq!(kind_name(mapped.kind), case[key]["kind"], "{key} {case}");
            assert_eq!(mapped.message, s(&case[key]["message"]), "{key} {case}");
        }
    }
}

fn scripted_reply(item: &Value) -> Reply {
    if item.is_null() {
        return Reply::json(200, json!({"model": "m", "choices": []}));
    }
    let calls: Vec<Value> = item["calls"]
        .as_array()
        .unwrap()
        .iter()
        .map(|c| {
            json!({"id": c["id"], "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]}})
        })
        .collect();
    let model = item.get("model").cloned().unwrap_or(json!("chosen"));
    Reply::json(
        200,
        json!({"model": model, "choices": [{"message": {"content": item["content"], "tool_calls": calls}}]}),
    )
}

#[test]
fn weather_assistant_matches_python() {
    let golden = load("assistant");
    assert_eq!(SYSTEM_PROMPT, golden["system_prompt"]);
    for case in golden["contexts"].as_array().unwrap() {
        let weather: Option<WeatherData> = serde_json::from_value(case["weather"].clone()).unwrap();
        assert_eq!(build_weather_context(weather.as_ref()), case["context"]);
    }
    for case in golden["requests"].as_array().unwrap() {
        let settings: AppSettings = serde_json::from_value(case["settings"].clone()).unwrap();
        let now: DateTime<FixedOffset> = DateTime::parse_from_rfc3339(s(&case["now"])).unwrap();
        match prepare_request(&settings, s(&case["context"]), now) {
            Ok(request) => {
                assert_eq!(request.model, case["model"]);
                assert_eq!(request.system_message, case["system"]);
                assert_eq!(request.provider == Provider::Venice, case["venice"] == true);
            }
            Err(error) => assert_eq!(error, case["error"]),
        }
    }
    for scenario in golden["loops"].as_array().unwrap() {
        let replies = scenario["responses"]
            .as_array()
            .unwrap()
            .iter()
            .map(scripted_reply)
            .collect();
        let server = TestServer::start(replies);
        let mut client = AssistantClient::new(Provider::OpenRouter, "key");
        client.base_url = server.url();
        let executed = Mutex::new(Vec::new());
        let results = &scenario["results"];
        let run = |name: &str, args: &Map<String, Value>| {
            executed.lock().unwrap().push(json!([name, args]));
            match results.get(name).and_then(Value::as_str).unwrap_or("ok") {
                "raise" => Err("tool failed".to_string()),
                text => Ok(text.to_string()),
            }
        };
        let tools: Vec<Value> = scenario["tools"]
            .as_array()
            .unwrap()
            .iter()
            .map(|n| json!({"type": "function", "function": {"name": n}}))
            .collect();
        let mut options = Map::new();
        options.insert("tools".into(), Value::Array(tools));
        let messages = scenario["messages"].as_array().unwrap().clone();
        let with_executor = scenario.get("executor") != Some(&Value::Bool(false));
        let outcome = run_assistant_request(
            &client,
            "model",
            &messages,
            with_executor.then_some(&run as crate::assistant::ToolRunner),
            &options,
            opt(&scenario["selected"]),
            scenario["max_rounds"].as_u64().unwrap_or(5) as usize,
            None,
        );
        let name = &scenario["name"];
        let outcome = match outcome {
            Ok(answer) => {
                json!({"answer": {"text": answer.text, "model": answer.model, "messages": answer.messages}})
            }
            Err(error) => json!({"error": error.message}),
        };
        assert!(
            same(&outcome, &scenario["outcome"]),
            "{name}: {outcome}\nvs {}",
            scenario["outcome"]
        );
        let requests: Vec<Value> = server
            .requests()
            .iter()
            .map(|r| {
                let body = r.json();
                json!({"tools": names(body["tools"].as_array().map_or(&[][..], Vec::as_slice)),
                       "tool_choice": body["tool_choice"],
                       "messages": body["messages"].as_array().map_or(0, Vec::len)})
            })
            .collect();
        assert_eq!(json!(requests), scenario["requests"], "{name}");
        assert!(
            same(&json!(*executed.lock().unwrap()), &scenario["executed"]),
            "{name}"
        );
    }
}
