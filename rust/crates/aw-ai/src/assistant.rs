//! The Weather Assistant conversation.
//!
//! Ports `ui/dialogs/weather_assistant_request.py` (the bounded tool-calling
//! loop and its grounding checks), `weather_assistant_prompt.py`,
//! `weather_assistant_context.py` and the non-UI parts of
//! `weather_assistant_dialog.py` (request preparation, context limit,
//! welcome and error texts).

use std::collections::HashSet;
use std::sync::LazyLock;

use aw_core::model::WeatherData;
use aw_core::model::WindDirection;
use aw_core::settings::AppSettings;
use chrono::{DateTime, FixedOffset, Local};
use regex::{Regex, RegexBuilder};
use serde_json::{json, Map, Value};

use crate::errors::{
    ai_request_error, is_model_refusal, AiError, AiErrorKind, MODEL_REFUSAL_MESSAGE,
};
use crate::provider::{selected_provider, Provider, DEFAULT_FREE_MODEL, DEFAULT_VENICE_MODEL};
use crate::pyfmt::{self, casefold};
use crate::tools::{tools_for_message, WeatherToolExecutor};
use crate::transport::{self, CancelToken, StreamLimits, REQUEST_DEADLINE};

/// Conversation turns kept in context.
pub const MAX_CONTEXT_TURNS: usize = 20;
pub const DEFAULT_WEATHER_ASSISTANT_MODEL: &str = DEFAULT_FREE_MODEL;
/// Tool rounds allowed before the assistant gives up on a lookup.
pub const MAX_TOOL_ROUNDS: usize = 5;
/// Appended to the error announcement when the failed question is put back.
pub const RESTORED_QUESTION_NOTE: &str = " Your question is restored in the input for editing.";

pub const SYSTEM_PROMPT: &str = "You are Weather Assistant, a friendly and knowledgeable weather assistant built into AccessiWeather. You help users understand weather conditions in plain, accessible language optimized for screen reader users.\n\n\
You have access to live weather tools that can fetch current conditions, forecasts, and active alerts for any location. The available tools are:\n\
- get_current_weather: Get current weather conditions for a location\n\
- get_forecast: Get the weather forecast for a location\n\
- get_hourly_forecast: Get hourly forecast (great for specific time questions)\n\
- get_alerts: Get active weather alerts for a location\n\
- search_location: Search for a location by name or ZIP code\n\
- add_location: Save a location to the user's locations list\n\
- list_locations: Show all saved locations\n\
- query_open_meteo: Custom Open-Meteo API query for any weather variable (soil temp, UV, cloud cover, dew point, snow depth, visibility, etc.)\n\
- get_area_forecast_discussion: Local NWS forecaster's detailed discussion\n\
- get_wpc_discussion: National WPC short range forecast discussion\n\
- get_spc_outlook: Storm Prediction Center severe weather outlook\n\n\
Use the provided tools to fetch weather data when users ask about specific locations or conditions not in the current context. You can call multiple tools if needed to give a complete answer. Use search_location when a place name is ambiguous. When adding locations, first resolve coordinates with search_location, then use add_location with the resolved name and coordinates.\n\n\
Guidelines:\n\
- Be conversational and helpful\n\
- Explain weather in practical terms (what to wear, activity suitability, etc.)\n\
- Avoid visual-only descriptions\n\
- When referencing data, use the weather context provided\n\
- For live weather requests, fetch the requested data before answering; never finish with a promise to check later\n\
- After tool results arrive, answer using those results and their observation times\n\
- A failed alert lookup means alerts are unknown, not that there are no alerts\n\
- Keep responses concise but thorough\n\
- Respond in plain text only \u{2014} no markdown formatting\n\
- Do not repeat information the user can already see\n\n\
IMPORTANT: Respond in plain text. No bold, italic, headers, or bullet markers.";

const HEADERS: [(&str, &str); 2] = [
    ("HTTP-Referer", "https://accessiweather.orinks.net"),
    ("X-Title", "AccessiWeather Weather Assistant"),
];

/// Tools that read weather for a location; these are pinned to the selected
/// location unless the user named another place.
const LOCATION_WEATHER_TOOLS: [&str; 6] = [
    "get_current_weather",
    "get_forecast",
    "get_hourly_forecast",
    "get_alerts",
    "query_open_meteo",
    "get_area_forecast_discussion",
];

fn regex_i(pattern: &str) -> Regex {
    RegexBuilder::new(pattern)
        .case_insensitive(true)
        .build()
        .expect("valid pattern")
}

static LIVE_CUE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b(now|today|tomorrow|tonight|currently|current|this week|next week)\b").unwrap()
});
static CONCEPTUAL: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b(explain|define|meaning|how does|how do|why does|what is a)\b").unwrap()
});
static WEATHER_WORD: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\b(weather|forecast|alerts?|warnings?|advisories|advisory|temperature|rain|raining|snow|snowing|wind|windy|humidity|uv|outlook|conditions)\b").unwrap()
});
static ALERT_QUESTION: LazyLock<Regex> =
    LazyLock::new(|| regex_i(r"\b(alerts?|warnings?|advisories|advisory)\b"));
static NO_ALERTS_CLAIM: LazyLock<Regex> =
    LazyLock::new(|| regex_i(r"\b(?:no|zero|without)\s+(?:active\s+)?(?:weather\s+)?alerts?\b"));

/// `needs_live_weather`: concrete weather lookups, not conceptual chat.
pub fn needs_live_weather(message: &str) -> bool {
    let text = message.to_lowercase();
    let text = text.trim();
    if !LIVE_CUE.is_match(text) && CONCEPTUAL.is_match(text) {
        return false;
    }
    WEATHER_WORD.is_match(text)
}

/// `_explicitly_requested_location`: allow a different place only when the
/// user's question identifies it.
pub(crate) fn explicitly_requested_location(
    user_text: &str,
    tool_location: &str,
    selected: &str,
) -> bool {
    let text = casefold(user_text);
    let requested = casefold(tool_location.trim());
    let current = casefold(selected.trim());
    if requested == current || (!requested.is_empty() && text.contains(&requested)) {
        return true;
    }
    let city = |s: &str| s.split(',').next().unwrap_or("").trim().to_string();
    let (requested_city, current_city) = (city(&requested), city(&current));
    requested_city != current_city
        && Regex::new(&format!(r"\b{}\b", regex::escape(&requested_city)))
            .is_ok_and(|re| re.is_match(&text))
}

/// Whether `content` names the selected city with a different two-letter
/// region the user did not ask about ("Lumberton, NC" for "Lumberton, NJ").
fn names_other_region(content: &str, latest: &str, selected: &str) -> bool {
    let Some((city, region)) = selected.rsplit_once(',') else {
        return false;
    };
    let (city, region) = (city.trim(), region.trim());
    if region.chars().count() != 2 {
        return false;
    }
    let named = regex_i(&format!(r"\b{},\s*([A-Z]{{2}})\b", regex::escape(city)));
    let other_region = named
        .captures_iter(content)
        .any(|c| casefold(&c[1]) != casefold(region));
    other_region && !named.is_match(latest)
}

/// A completed answer and the full protocol history including tool results.
#[derive(Debug, Clone, PartialEq)]
pub struct AssistantAnswer {
    pub text: String,
    pub model: String,
    pub messages: Vec<Value>,
}

/// Chat completions for the Weather Assistant (non-streamed, 30 s ceiling).
#[derive(Debug, Clone)]
pub struct AssistantClient {
    pub provider: Provider,
    api_key: String,
    pub(crate) base_url: String,
    pub(crate) limits: StreamLimits,
}

impl AssistantClient {
    pub fn new(provider: Provider, api_key: impl Into<String>) -> Self {
        let api_key = api_key.into();
        Self {
            provider,
            // Only the Venice client strips the key.
            api_key: match provider {
                Provider::Venice => api_key.trim().to_string(),
                Provider::OpenRouter => api_key,
            },
            base_url: provider.base_url().to_string(),
            limits: StreamLimits::deadline(REQUEST_DEADLINE),
        }
    }

    fn complete(&self, body: &Value, cancel: Option<&CancelToken>) -> Result<Value, AiError> {
        if self.provider == Provider::Venice && self.api_key.is_empty() {
            return Err(AiError::new(
                AiErrorKind::InvalidApiKey,
                "A Venice API key is required. Add your own key in Settings > AI.",
            ));
        }
        let url = format!("{}/chat/completions", self.base_url);
        transport::chat_completion(&url, &self.api_key, &HEADERS, body, self.limits, cancel)
            .map_err(|e| ai_request_error(&e, self.provider))
    }
}

fn grounding(message: &str) -> AiError {
    AiError::new(AiErrorKind::Explainer, message)
}

fn tool_name(tool: &Value) -> &str {
    tool["function"]["name"].as_str().unwrap_or("")
}

/// Runs one tool call: the tool's text, or `Err` when the call failed
/// (normally [`WeatherToolExecutor::execute`]).
pub type ToolRunner<'a> = &'a dyn Fn(&str, &Map<String, Value>) -> Result<String, String>;

/// `run_assistant_request`: real completion/tool turns that refuse empty
/// promises, ungrounded answers and unbounded tool calls. `options` holds
/// the extra request fields (`tools`, `venice_parameters`).
#[allow(clippy::too_many_arguments)]
pub fn run_assistant_request(
    client: &AssistantClient,
    model: &str,
    messages: &[Value],
    executor: Option<ToolRunner>,
    options: &Map<String, Value>,
    selected_location: Option<&str>,
    max_tool_rounds: usize,
    cancel: Option<&CancelToken>,
) -> Result<AssistantAnswer, AiError> {
    let mut history = messages.to_vec();
    let latest = history
        .iter()
        .rev()
        .find(|m| m["role"] == "user")
        .and_then(|m| m.get("content"))
        .map_or(String::new(), pyfmt::str);
    let require_lookup = needs_live_weather(&latest) && executor.is_some();
    let all_tools = options
        .get("tools")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut read_tools: Vec<Value> = all_tools
        .into_iter()
        .filter(|t| LOCATION_WEATHER_TOOLS.contains(&tool_name(t)))
        .collect();
    if require_lookup && ALERT_QUESTION.is_match(&latest) {
        let alert_tools: Vec<Value> = read_tools
            .iter()
            .filter(|t| tool_name(t) == "get_alerts")
            .cloned()
            .collect();
        if !alert_tools.is_empty() {
            read_tools = alert_tools;
        }
    }
    let read_names: HashSet<String> = read_tools
        .iter()
        .map(|t| tool_name(t).to_string())
        .collect();
    let mut tool_rounds = 0;
    let mut retried = false;
    let mut lookup_completed = false;
    let mut alert_result_has_alerts = false;
    loop {
        let mut request = options.clone();
        if require_lookup && tool_rounds == 0 && !read_tools.is_empty() {
            request.insert("tools".into(), Value::Array(read_tools.clone()));
            request.insert("tool_choice".into(), json!("required"));
        }
        let mut body = json!({"model": model, "messages": history, "max_tokens": 2000});
        for (key, value) in &request {
            body[key] = value.clone();
        }
        let response = client.complete(&body, cancel)?;
        let Some(choice) = response
            .get("choices")
            .and_then(Value::as_array)
            .and_then(|c| c.first())
        else {
            return Err(grounding(
                "Received an empty response. Try again or switch models in Settings.",
            ));
        };
        let reply = &choice["message"];
        let calls = reply
            .get("tool_calls")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        if !calls.is_empty() {
            let Some(executor) = executor.filter(|_| tool_rounds < max_tool_rounds) else {
                return Err(grounding(
                    "The assistant could not finish its weather lookup. Please try a simpler question.",
                ));
            };
            let content = reply["content"].as_str().unwrap_or("");
            let protocol_calls: Vec<Value> = calls
                .iter()
                .map(|call| {
                    json!({"id": call["id"], "type": "function",
                           "function": {"name": call["function"]["name"],
                                        "arguments": call["function"]["arguments"]}})
                })
                .collect();
            history.push(
                json!({"role": "assistant", "content": content, "tool_calls": protocol_calls}),
            );
            let allowed: HashSet<&str> = request
                .get("tools")
                .and_then(Value::as_array)
                .map(|tools| tools.iter().map(tool_name).collect())
                .unwrap_or_default();
            for call in &calls {
                let name = call["function"]["name"].as_str().unwrap_or("");
                let arguments = call["function"]["arguments"]
                    .as_str()
                    .and_then(|a| serde_json::from_str::<Value>(a).ok());
                let result = match arguments {
                    None => None,
                    Some(Value::Object(_)) if !allowed.contains(name) => {
                        Some("Error: this tool call is not available for this request.".to_string())
                    }
                    Some(Value::Object(mut arguments)) => {
                        if let Some(selected) = selected_location {
                            if LOCATION_WEATHER_TOOLS.contains(&name) {
                                let explicit = arguments
                                    .get("location")
                                    .and_then(Value::as_str)
                                    .is_some_and(|requested| {
                                        explicitly_requested_location(&latest, requested, selected)
                                    });
                                if !explicit {
                                    arguments.insert("location".into(), json!(selected));
                                }
                            }
                        }
                        executor(name, &arguments).ok().inspect(|result| {
                            if read_names.contains(name) && !result.starts_with("Error") {
                                lookup_completed = true;
                            }
                            if name == "get_alerts" && !result.starts_with("Error:") {
                                alert_result_has_alerts |=
                                    result.contains("- ") && !result.contains("No active alerts");
                            }
                        })
                    }
                    Some(_) => {
                        Some("Error: this tool call is not available for this request.".to_string())
                    }
                };
                let result = result.unwrap_or_else(|| {
                    "Error: the weather lookup failed. Do not report unavailable data as verified conditions.".to_string()
                });
                history
                    .push(json!({"role": "tool", "tool_call_id": call["id"], "content": result}));
            }
            tool_rounds += 1;
            continue;
        }
        if require_lookup && !lookup_completed && !read_tools.is_empty() {
            if tool_rounds > 0 {
                return Err(grounding(
                    "The weather lookup did not return usable data. Please try again.",
                ));
            }
            if retried {
                return Err(grounding(
                    "The model did not perform the requested weather lookup. Try another model.",
                ));
            }
            retried = true;
            continue;
        }
        let content = reply["content"].as_str().unwrap_or("").trim().to_string();
        if content.is_empty() {
            return Err(grounding(
                "Received an empty response. Try again or switch models in Settings.",
            ));
        }
        if is_model_refusal(&content) {
            return Err(grounding(MODEL_REFUSAL_MESSAGE));
        }
        if alert_result_has_alerts && NO_ALERTS_CLAIM.is_match(&content) {
            return Err(grounding(
                "The model contradicted the alert lookup. Please try again or use the app's alert list.",
            ));
        }
        if selected_location.is_some_and(|s| names_other_region(&content, &latest, s)) {
            return Err(grounding(
                "The model named a different place. Please try again or check the selected location.",
            ));
        }
        history.push(json!({"role": "assistant", "content": content}));
        let used = response["model"]
            .as_str()
            .filter(|m| !m.is_empty())
            .unwrap_or(model)
            .to_string();
        return Ok(AssistantAnswer {
            text: content,
            model: used,
            messages: history,
        });
    }
}

/// `build_weather_context`: the app's current weather for the system message.
pub fn build_weather_context(weather: Option<&WeatherData>) -> String {
    let Some(weather) = weather else {
        return "No weather data currently loaded.".into();
    };
    let loc = &weather.location;
    let mut parts = vec![format!(
        "Location: {} ({}, {})",
        loc.name,
        pyfmt::float(loc.latitude),
        pyfmt::float(loc.longitude)
    )];
    if let Some(cur) = &weather.current {
        if let Some(t) = cur.temperature_f {
            parts.push(format!("Temperature: {t:.0}°F"));
        }
        if let Some(t) = cur.feels_like_f {
            parts.push(format!("Feels like: {t:.0}°F"));
        }
        if let Some(c) = cur.condition.as_deref().filter(|c| !c.is_empty()) {
            parts.push(format!("Conditions: {c}"));
        }
        if let Some(h) = cur.humidity {
            parts.push(format!("Humidity: {h}%"));
        }
        if let Some(mph) = cur.wind_speed_mph {
            let mut wind = format!("Wind: {mph:.0} mph");
            // `if cur.wind_direction:` then the raw value (degrees or text).
            let direction = match &cur.wind_direction {
                Some(WindDirection::Degrees(d)) if *d != 0.0 => Some(if d.fract() == 0.0 {
                    format!("{d:.0}")
                } else {
                    d.to_string()
                }),
                Some(WindDirection::Text(s)) if !s.is_empty() => Some(s.clone()),
                _ => None,
            };
            if let Some(d) = direction {
                wind.push_str(&format!(" from {d}"));
            }
            parts.push(wind);
        }
        if let Some(p) = cur.pressure_in {
            parts.push(format!("Pressure: {p:.2} inHg"));
        }
        if let Some(v) = cur.visibility_miles {
            parts.push(format!("Visibility: {v:.1} miles"));
        }
        if let Some(uv) = cur.uv_index {
            parts.push(format!("UV Index: {}", pyfmt::whole_or_float(uv)));
        }
    }
    if let Some(forecast) = weather.forecast.as_ref().filter(|f| !f.periods.is_empty()) {
        parts.push("\nForecast:".into());
        for period in forecast.periods.iter().take(6) {
            let temperature = period
                .temperature
                .map_or("None".into(), pyfmt::whole_or_float);
            let mut line = format!(
                "  {}: {temperature}°{}",
                period.name, period.temperature_unit
            );
            if let Some(short) = period.short_forecast.as_deref().filter(|s| !s.is_empty()) {
                line.push_str(&format!(", {short}"));
            }
            parts.push(line);
        }
    }
    if let Some(alerts) = weather.alerts.as_ref().filter(|a| a.has_alerts()) {
        parts.push("\nActive Alerts:".into());
        for alert in alerts.alerts.iter().take(5) {
            let title = alert
                .event
                .as_deref()
                .filter(|e| !e.is_empty())
                .unwrap_or(&alert.title);
            parts.push(format!("  - {title} (Severity: {})", alert.severity));
        }
    }
    if !weather.trend_insights.is_empty() {
        parts.push("\nTrend Insights:".into());
        for insight in weather.trend_insights.iter().take(3) {
            let mut text = insight
                .summary
                .clone()
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| format!("{}: {}", insight.metric, insight.direction));
            if let (Some(change), Some(unit)) = (
                insight.change,
                insight.unit.as_deref().filter(|u| !u.is_empty()),
            ) {
                text.push_str(&format!(" ({change:+.1}{unit})"));
            }
            parts.push(format!("  - {text}"));
        }
    }
    parts.join("\n")
}

/// The greeting shown (and announced as "Weather Assistant: ...") when the
/// dialog opens or the chat is cleared.
pub fn welcome_message(location_name: Option<&str>) -> String {
    format!(
        "Welcome to Weather Assistant! I can help you understand the weather conditions for {}. Ask me anything about the current weather, forecast, what to wear, or how conditions might affect your plans.",
        location_name.unwrap_or("your area")
    )
}

/// `_append_to_display`: one chat history entry.
pub fn chat_entry(speaker: &str, text: &str, time: DateTime<Local>) -> String {
    format!("[{}] {speaker}:\n{text}\n\n", time.format("%I:%M %p"))
}

/// The text displayed for a failed response (announced with a
/// "Weather Assistant: " prefix, plus [`RESTORED_QUESTION_NOTE`] when the
/// question was put back in the input).
pub fn error_message(error: &str) -> String {
    format!("Sorry, I couldn't respond: {error}")
}

/// The conversation kept between turns (without the system message).
#[derive(Debug, Clone, Default)]
pub struct AssistantConversation {
    pub messages: Vec<Value>,
}

impl AssistantConversation {
    pub fn new() -> Self {
        Self::default()
    }

    /// Record the user's message, keeping at most [`MAX_CONTEXT_TURNS`] user turns.
    pub fn push_user(&mut self, message: &str) {
        self.messages
            .push(json!({"role": "user", "content": message}));
        let user_turns: Vec<usize> = self
            .messages
            .iter()
            .enumerate()
            .filter(|(_, m)| m["role"] == "user")
            .map(|(i, _)| i)
            .collect();
        if user_turns.len() > MAX_CONTEXT_TURNS {
            let start = user_turns[user_turns.len() - MAX_CONTEXT_TURNS];
            self.messages.drain(..start);
        }
    }

    /// Keep the answer's full history (tool calls included) for follow-ups.
    pub fn accept(&mut self, answer: &AssistantAnswer) {
        self.messages = answer.messages.iter().skip(1).cloned().collect();
    }

    /// After a failure: remove and return the unanswered question so the UI
    /// can restore it when the input is empty.
    pub fn take_failed_question(&mut self) -> Option<String> {
        if self.messages.last().is_some_and(|m| m["role"] == "user") {
            self.messages.pop().map(|m| pyfmt::str(&m["content"]))
        } else {
            None
        }
    }

    pub fn clear(&mut self) {
        self.messages.clear();
    }
}

/// Everything a response needs from the settings, resolved on the UI thread.
#[derive(Debug, Clone)]
pub struct AssistantRequest {
    pub provider: Provider,
    pub api_key: String,
    pub model: String,
    pub system_message: String,
}

/// `_generate_response`'s preparation. `Err` is the text for
/// [`error_message`]. `weather_context` comes from [`build_weather_context`];
/// `now` is the device time (`datetime.now().astimezone()`).
pub fn prepare_request(
    settings: &AppSettings,
    weather_context: &str,
    now: DateTime<FixedOffset>,
) -> Result<AssistantRequest, String> {
    let provider = selected_provider(settings)
        .map_err(|_| "Unknown AI provider. Select one in Settings > AI.".to_string())?;
    let (api_key, model) = match provider {
        Provider::Venice => (
            settings.venice_api_key.clone(),
            if settings.venice_model.is_empty() {
                DEFAULT_VENICE_MODEL.to_string()
            } else {
                settings.venice_model.clone()
            },
        ),
        Provider::OpenRouter => (
            settings.openrouter_api_key.clone(),
            if settings.ai_model_preference.is_empty() {
                DEFAULT_WEATHER_ASSISTANT_MODEL.to_string()
            } else {
                settings.ai_model_preference.clone()
            },
        ),
    };
    if api_key.is_empty() {
        let name = match provider {
            Provider::Venice => "Venice",
            Provider::OpenRouter => "OpenRouter",
        };
        return Err(format!(
            "No {name} API key configured. Set one in Settings > AI."
        ));
    }
    let prompt = settings
        .custom_system_prompt
        .as_deref()
        .map(str::trim)
        .filter(|p| !p.is_empty())
        .unwrap_or(SYSTEM_PROMPT);
    let mut system_message = format!(
        "{prompt}\n\nCurrent device time: {}\nUse the weather location's provider timezone for forecast times; the device timezone may differ.\nTreat weather observation timestamps as the time of that data, not as the current time.\n\nCurrent weather data:\n{weather_context}",
        pyfmt::isoformat(&now)
    );
    if let Some(instructions) = settings
        .custom_instructions
        .as_deref()
        .map(str::trim)
        .filter(|i| !i.is_empty())
    {
        system_message.push_str(&format!("\n\nAdditional instructions: {instructions}"));
    }
    Ok(AssistantRequest {
        provider,
        api_key,
        model,
        system_message,
    })
}

/// `_build_completion_request`'s tools for this turn (the model default is
/// applied by [`prepare_request`]).
fn completion_options(messages: &[Value], with_tools: bool) -> Map<String, Value> {
    let mut options = Map::new();
    if with_tools {
        let latest = messages
            .iter()
            .rev()
            .find(|m| m["role"] == "user")
            .and_then(|m| m.get("content"))
            .map_or(String::new(), pyfmt::str);
        options.insert("tools".into(), Value::Array(tools_for_message(&latest)));
    }
    options
}

/// Answer the conversation's latest question. On success pass the answer to
/// [`AssistantConversation::accept`] and show "Model: {model}" as status.
pub fn generate_response(
    request: &AssistantRequest,
    conversation: &AssistantConversation,
    executor: Option<&WeatherToolExecutor>,
    cancel: Option<&CancelToken>,
) -> Result<AssistantAnswer, AiError> {
    let client = AssistantClient::new(request.provider, request.api_key.clone());
    respond(&client, request, conversation, executor, cancel)
}

fn respond(
    client: &AssistantClient,
    request: &AssistantRequest,
    conversation: &AssistantConversation,
    executor: Option<&WeatherToolExecutor>,
    cancel: Option<&CancelToken>,
) -> Result<AssistantAnswer, AiError> {
    let mut messages = vec![json!({"role": "system", "content": request.system_message})];
    messages.extend(conversation.messages.iter().cloned());
    let mut options = completion_options(&messages, executor.is_some());
    if request.provider == Provider::Venice {
        options.insert(
            "venice_parameters".into(),
            json!({"include_venice_system_prompt": false}),
        );
    }
    let selected = executor.and_then(WeatherToolExecutor::selected_location);
    let execute = |name: &str, arguments: &Map<String, Value>| match executor {
        Some(executor) => executor.execute(name, arguments),
        None => Err(String::new()),
    };
    run_assistant_request(
        client,
        &request.model,
        &messages,
        executor.is_some().then_some(&execute as ToolRunner),
        &options,
        selected,
        MAX_TOOL_ROUNDS,
        cancel,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_server::{Reply, TestServer};
    use crate::tools::AssistantHost;
    use aw_core::model::Location;
    use chrono::{TimeZone, Utc};
    use std::sync::Mutex;

    /// Records tool calls; every weather read returns the same observation.
    #[derive(Default)]
    struct Host {
        calls: Mutex<Vec<(String, f64, f64)>>,
        alerts: Option<Value>,
    }

    impl AssistantHost for Host {
        fn geocode(&self, query: &str) -> Option<(f64, f64, String)> {
            Some((1.0, 2.0, query.to_string()))
        }
        fn suggest_locations(&self, _: &str, _: usize) -> Vec<String> {
            Vec::new()
        }
        fn current_conditions(&self, lat: f64, lon: f64) -> Result<Value, String> {
            self.calls
                .lock()
                .unwrap()
                .push(("current".into(), lat, lon));
            Ok(
                json!({"properties": {"timestamp": "noon", "temperature": {"value": 21, "unitCode": "wmoUnit:degC"}}}),
            )
        }
        fn forecast(&self, _: f64, _: f64, _: u32) -> Result<Value, String> {
            Err("down".into())
        }
        fn hourly_forecast(&self, _: f64, _: f64) -> Result<Value, String> {
            Err("down".into())
        }
        fn alerts(&self, lat: f64, lon: f64) -> Result<Value, String> {
            self.calls.lock().unwrap().push(("alerts".into(), lat, lon));
            self.alerts.clone().ok_or_else(|| "down".into())
        }
        fn discussion(&self, _: f64, _: f64) -> Result<Option<String>, String> {
            Ok(None)
        }
        fn wpc_short_range_discussion(&self) -> Result<String, String> {
            Ok(String::new())
        }
        fn spc_day1_outlook(&self) -> Result<String, String> {
            Ok(String::new())
        }
        fn open_meteo_forecast(&self, _: &[(&'static str, String)]) -> Result<Value, String> {
            Err("down".into())
        }
        fn location_names(&self) -> Vec<String> {
            Vec::new()
        }
        fn add_location(&self, _: &str, _: f64, _: f64) -> bool {
            false
        }
        fn saved_locations(&self) -> Vec<Location> {
            Vec::new()
        }
        fn current_location_name(&self) -> Option<String> {
            None
        }
    }

    fn reply(text: &str, tool: Option<&str>, location: &str) -> Reply {
        let calls = match tool {
            Some(name) => json!([{"id": "call-1", "type": "function",
                "function": {"name": name, "arguments": json!({"location": location}).to_string()}}]),
            None => json!([]),
        };
        Reply::json(
            200,
            json!({"model": "chosen", "choices": [{"message": {"content": text, "tool_calls": calls}}]}),
        )
    }

    fn options(names: &[&str]) -> Map<String, Value> {
        let tools: Vec<Value> = names
            .iter()
            .map(|n| json!({"type": "function", "function": {"name": n}}))
            .collect();
        let mut map = Map::new();
        map.insert("tools".into(), Value::Array(tools));
        map
    }

    fn client(server: &TestServer) -> AssistantClient {
        let mut c = AssistantClient::new(Provider::OpenRouter, "key");
        c.base_url = server.url();
        c
    }

    fn user(text: &str) -> Vec<Value> {
        vec![json!({"role": "user", "content": text})]
    }

    fn home() -> Location {
        Location::new("Home", 40.1, -74.2)
    }

    fn runner<'a>(
        executor: &'a WeatherToolExecutor<'a>,
    ) -> impl Fn(&str, &Map<String, Value>) -> Result<String, String> + 'a {
        move |name, arguments| executor.execute(name, arguments)
    }

    fn now() -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 9, 12, 12, 0, 0).unwrap()
    }

    #[test]
    fn live_request_requires_a_read_tool_then_answers_with_history() {
        let server = TestServer::start(vec![
            reply("Checking", Some("get_current_weather"), "Home"),
            reply("It is 70 F.", None, ""),
        ]);
        let host = Host::default();
        let executor = WeatherToolExecutor::new(&host, Some(&home()), None, now());
        let answer = run_assistant_request(
            &client(&server),
            "model",
            &user("Current weather at Home?"),
            Some(&runner(&executor)),
            &options(&["get_current_weather", "add_location"]),
            None,
            5,
            None,
        )
        .unwrap();
        let requests = server.requests();
        let first = requests[0].json();
        assert_eq!(first["tool_choice"], "required");
        assert_eq!(first["tools"].as_array().unwrap().len(), 1);
        assert_eq!(first["max_tokens"], 2000);
        assert_eq!(
            requests[0].header("X-Title"),
            Some("AccessiWeather Weather Assistant")
        );
        assert!(requests[1].json().get("tool_choice").is_none());
        assert_eq!(answer.text, "It is 70 F.");
        assert_eq!(answer.model, "chosen");
        let roles: Vec<&str> = answer
            .messages
            .iter()
            .map(|m| m["role"].as_str().unwrap())
            .collect();
        assert_eq!(roles, ["user", "assistant", "tool", "assistant"]);
        assert!(answer.messages[2]["content"]
            .as_str()
            .unwrap()
            .contains("Temperature: 21°C"));
        assert_eq!(
            *host.calls.lock().unwrap(),
            [("current".to_string(), 40.1, -74.2)]
        );
    }

    #[test]
    fn model_ignoring_required_tool_never_returns_a_promise() {
        let server = TestServer::start(vec![
            reply("I'll check.", None, ""),
            reply("Let me fetch that.", None, ""),
        ]);
        let host = Host::default();
        let executor = WeatherToolExecutor::new(&host, None, None, now());
        let error = run_assistant_request(
            &client(&server),
            "m",
            &user("Weather tomorrow?"),
            Some(&runner(&executor)),
            &options(&["get_current_weather"]),
            None,
            5,
            None,
        )
        .unwrap_err();
        assert!(error.message.contains("did not perform"));
        assert_eq!(server.requests().len(), 2);
        assert!(host.calls.lock().unwrap().is_empty());
    }

    #[test]
    fn refusal_and_conceptual_questions() {
        let server = TestServer::start(vec![
            reply(
                "I\u{2019}m sorry, but I can\u{2019}t help with that.",
                None,
                "",
            ),
            reply("Rain forms from condensed moisture.", None, ""),
        ]);
        let host = Host::default();
        let executor = WeatherToolExecutor::new(&host, None, None, now());
        let opts = options(&["get_current_weather"]);
        let error = run_assistant_request(
            &client(&server),
            "m",
            &user("Explain how fog forms."),
            Some(&runner(&executor)),
            &opts,
            None,
            5,
            None,
        )
        .unwrap_err();
        assert!(error.message.contains("declined this request"));
        run_assistant_request(
            &client(&server),
            "m",
            &user("How does rain form?"),
            Some(&runner(&executor)),
            &opts,
            None,
            5,
            None,
        )
        .unwrap();
        assert!(server.requests()[1].json().get("tool_choice").is_none());
    }

    #[test]
    fn tool_round_exhaustion_and_blocked_write_tools() {
        let loops = (0..3)
            .map(|_| reply("Checking", Some("get_current_weather"), "Home"))
            .collect();
        let server = TestServer::start(loops);
        let host = Host::default();
        let executor = WeatherToolExecutor::new(&host, None, None, now());
        let opts = options(&["get_current_weather", "add_location"]);
        let error = run_assistant_request(
            &client(&server),
            "m",
            &user("Weather now?"),
            Some(&runner(&executor)),
            &opts,
            None,
            2,
            None,
        )
        .unwrap_err();
        assert!(error.message.contains("could not finish"));
        assert_eq!(host.calls.lock().unwrap().len(), 2);

        let server = TestServer::start(vec![
            reply("Saving", Some("add_location"), "x"),
            reply("I could not check.", None, ""),
        ]);
        let error = run_assistant_request(
            &client(&server),
            "m",
            &user("Weather now?"),
            Some(&runner(&executor)),
            &opts,
            None,
            5,
            None,
        )
        .unwrap_err();
        assert!(error.message.contains("did not return usable data"));
        let tool_message = &server.requests()[1].json()["messages"][2];
        assert_eq!(
            tool_message["content"],
            "Error: this tool call is not available for this request."
        );
    }

    #[test]
    fn alert_question_uses_selected_location_despite_namesake() {
        let server = TestServer::start(vec![
            reply("Checking", Some("get_alerts"), "Home"),
            reply("Alert checked.", None, ""),
        ]);
        let host = Host {
            alerts: Some(json!({"features": []})),
            ..Host::default()
        };
        let selected = Location::new("Lumberton, NJ", 39.97, -74.8);
        let executor = WeatherToolExecutor::new(&host, Some(&selected), None, now());
        run_assistant_request(
            &client(&server),
            "m",
            &user("Are there alerts for Lumberton right now?"),
            Some(&runner(&executor)),
            &options(&["get_current_weather", "get_alerts", "add_location"]),
            Some("Lumberton, NJ"),
            5,
            None,
        )
        .unwrap();
        let first = server.requests()[0].json();
        assert_eq!(
            first["tools"],
            json!([{"type": "function", "function": {"name": "get_alerts"}}])
        );
        assert_eq!(
            *host.calls.lock().unwrap(),
            [("alerts".to_string(), 39.97, -74.8)]
        );
    }

    #[test]
    fn explicit_other_location_remains_available() {
        let server = TestServer::start(vec![
            reply("Checking", Some("get_current_weather"), "Home"),
            reply("Done", None, ""),
        ]);
        let host = Host::default();
        let selected = Location::new("Lumberton, NJ", 39.97, -74.8);
        let executor = WeatherToolExecutor::new(&host, Some(&selected), None, now());
        run_assistant_request(
            &client(&server),
            "m",
            &user("What is the current weather in Home?"),
            Some(&runner(&executor)),
            &options(&["get_current_weather"]),
            Some("Lumberton, NJ"),
            5,
            None,
        )
        .unwrap();
        assert_eq!(
            *host.calls.lock().unwrap(),
            [("current".to_string(), 1.0, 2.0)]
        );
    }

    #[test]
    fn grounding_checks_reject_contradictions_and_namesakes() {
        let server = TestServer::start(vec![
            reply("Checking", Some("get_alerts"), "Home"),
            reply("There are no active alerts.", None, ""),
        ]);
        let host = Host {
            alerts: Some(json!({"features": [{"properties": {"event": "Coastal Flood Warning"}}]})),
            ..Host::default()
        };
        let executor = WeatherToolExecutor::new(&host, Some(&home()), None, now());
        let error = run_assistant_request(
            &client(&server),
            "m",
            &user("Any alerts now?"),
            Some(&runner(&executor)),
            &options(&["get_alerts"]),
            Some("Home"),
            5,
            None,
        )
        .unwrap_err();
        assert!(error.message.contains("contradicted"));

        let server = TestServer::start(vec![
            reply("Checking", Some("get_current_weather"), "x"),
            reply("Lumberton, NC is sunny.", None, ""),
        ]);
        let selected = Location::new("Lumberton, NJ", 39.97, -74.8);
        let executor = WeatherToolExecutor::new(&host, Some(&selected), None, now());
        let error = run_assistant_request(
            &client(&server),
            "m",
            &user("What is the weather now?"),
            Some(&runner(&executor)),
            &options(&["get_current_weather"]),
            Some("Lumberton, NJ"),
            5,
            None,
        )
        .unwrap_err();
        assert!(error.message.contains("different place"));
    }

    #[test]
    fn failures_are_redacted_and_tool_history_carries_into_followups() {
        let server = TestServer::start(vec![
            Reply::text(402, "secret-key response body"),
            reply("", Some("get_current_weather"), "Home"),
            reply("70 F", None, ""),
            reply("That is mild.", None, ""),
        ]);
        let request = AssistantRequest {
            provider: Provider::OpenRouter,
            api_key: "secret-key".into(),
            model: DEFAULT_WEATHER_ASSISTANT_MODEL.into(),
            system_message: "sys".into(),
        };
        let host = Host::default();
        let executor = WeatherToolExecutor::new(&host, Some(&home()), None, now());
        let mut conversation = AssistantConversation::new();
        conversation.push_user("What are current conditions?");
        let c = client(&server);
        let error = respond(&c, &request, &conversation, Some(&executor), None).unwrap_err();
        assert!(error.message.contains("credits") && !error.message.contains("secret"));
        assert_eq!(
            conversation.take_failed_question().as_deref(),
            Some("What are current conditions?")
        );
        conversation.push_user("What are current conditions?");
        let answer = respond(&c, &request, &conversation, Some(&executor), None).unwrap();
        conversation.accept(&answer);
        conversation.push_user("What does that mean?");
        respond(&c, &request, &conversation, Some(&executor), None).unwrap();
        let sent = server.requests()[3].json();
        assert_eq!(sent["model"], DEFAULT_WEATHER_ASSISTANT_MODEL);
        assert_eq!(sent["messages"][0]["content"], "sys");
        assert!(sent["messages"]
            .as_array()
            .unwrap()
            .iter()
            .any(|m| m["role"] == "tool"));
    }

    #[test]
    fn deadline_error_is_shown_as_is() {
        let server = TestServer::start(vec![Reply::raw(
            200,
            "application/json",
            vec![crate::test_server::Step::Sleep(
                std::time::Duration::from_secs(2),
            )],
        )]);
        let mut c = client(&server);
        c.limits = StreamLimits::deadline(std::time::Duration::from_millis(300));
        let error = run_assistant_request(&c, "m", &user("hi"), None, &Map::new(), None, 5, None)
            .unwrap_err();
        assert_eq!(
            error.message,
            "The AI service did not answer within 0 seconds."
        );
    }

    #[test]
    fn prepare_request_uses_provider_prompt_and_instructions() {
        let mut settings: AppSettings = serde_json::from_str("{}").unwrap();
        let now = FixedOffset::west_opt(4 * 3600)
            .unwrap()
            .with_ymd_and_hms(2026, 9, 25, 14, 3, 5)
            .unwrap();
        assert_eq!(
            prepare_request(&settings, "ctx", now).unwrap_err(),
            "No OpenRouter API key configured. Set one in Settings > AI."
        );
        settings.ai_provider = "venice".into();
        settings.venice_api_key = "v".into();
        settings.venice_model = String::new();
        settings.custom_system_prompt = Some("  Custom assistant prompt ".into());
        settings.custom_instructions = Some("Use Celsius".into());
        let request = prepare_request(&settings, "Sunny", now).unwrap();
        assert_eq!(request.model, DEFAULT_VENICE_MODEL);
        assert_eq!(request.system_message, "Custom assistant prompt\n\nCurrent device time: 2026-09-25T14:03:05-04:00\nUse the weather location's provider timezone for forecast times; the device timezone may differ.\nTreat weather observation timestamps as the time of that data, not as the current time.\n\nCurrent weather data:\nSunny\n\nAdditional instructions: Use Celsius");
        settings.ai_provider = "unknown".into();
        assert!(prepare_request(&settings, "", now)
            .unwrap_err()
            .contains("Unknown AI provider. Select one"));
    }

    #[test]
    fn conversation_keeps_twenty_user_turns() {
        let mut conversation = AssistantConversation::new();
        for i in 0..25 {
            conversation.push_user(&format!("q{i}"));
            conversation
                .messages
                .push(json!({"role": "assistant", "content": "a"}));
        }
        let users = conversation
            .messages
            .iter()
            .filter(|m| m["role"] == "user")
            .count();
        assert_eq!(users, MAX_CONTEXT_TURNS);
        assert_eq!(conversation.messages[0]["content"], "q5");
        assert_eq!(conversation.take_failed_question(), None);
    }

    #[test]
    fn live_weather_detection() {
        for q in [
            "Explain today\u{2019}s forecast",
            "Why is it so windy now?",
            "Explain current conditions",
        ] {
            assert!(needs_live_weather(q), "{q}");
        }
        for q in [
            "Explain how forecasts work",
            "What is a weather warning?",
            "How does rain form?",
        ] {
            assert!(!needs_live_weather(q), "{q}");
        }
    }

    #[test]
    fn welcome_and_error_texts() {
        assert!(welcome_message(None).contains("conditions for your area."));
        assert_eq!(error_message("x"), "Sorry, I couldn't respond: x");
        let time = Local.with_ymd_and_hms(2026, 9, 25, 14, 3, 0).unwrap();
        assert_eq!(chat_entry("You", "Hi", time), "[02:03 PM] You:\nHi\n\n");
    }
}
