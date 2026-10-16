//! Weather Assistant tools: schemas, per-message tool selection and the
//! executor that runs tool calls against the app.
//!
//! Ports `ai_tool_schemas.py`, `ai_tools.py` and the tool-data adapter in
//! `WeatherAssistantDialog._get_tool_executor`.

use aw_core::model::{Location, WeatherAlert, WeatherData};
use chrono::{DateTime, Utc};
use serde_json::{json, Map, Value};

use crate::formatters::{
    format_alerts, format_current_weather, format_forecast, format_hourly_forecast,
    format_location_search, format_open_meteo_response,
};
use crate::pyfmt::{self, casefold};

/// What the tools need from the application. All weather methods return the
/// raw provider JSON the Python tools format (see [`crate::formatters`]);
/// `Err` carries the failure text shown after "Error fetching weather data: ".
///
/// Python's adapter tries NWS first and falls back to Open-Meteo for
/// current conditions, forecasts and hourly forecasts; implementations
/// should do the same:
///
/// | method | NWS (`api.weather.gov`) | Open-Meteo fallback |
/// |---|---|---|
/// | `current_conditions` | `/stations/{first station}/observations/latest` | `OpenMeteoApiClient.get_current_weather` response |
/// | `forecast` | `/gridpoints/.../forecast` (ignores `days`) | `get_forecast(days=days)` response (`daily`) |
/// | `hourly_forecast` | `/gridpoints/.../forecast/hourly` | `get_hourly_forecast` response (`hourly`) |
/// | `alerts` | `/alerts/active?point={lat},{lon}` (no fallback) | — |
/// | `discussion` | latest AFD text for the point's office, `None` if none | — |
///
/// Open-Meteo calls use Python's client defaults (fahrenheit, mph, inch,
/// `best_match`). The WPC and SPC texts are `NationalDiscussionService`'s
/// `short_range` and `day1` discussions (15 s timeout, two retries).
pub trait AssistantHost: Send + Sync {
    /// `GeocodingService.geocode_address`: `(lat, lon, display name)`.
    fn geocode(&self, query: &str) -> Option<(f64, f64, String)>;
    /// `GeocodingService.suggest_locations(query, limit)`: display names.
    fn suggest_locations(&self, query: &str, limit: usize) -> Vec<String>;
    fn current_conditions(&self, lat: f64, lon: f64) -> Result<Value, String>;
    fn forecast(&self, lat: f64, lon: f64, days: u32) -> Result<Value, String>;
    fn hourly_forecast(&self, lat: f64, lon: f64) -> Result<Value, String>;
    /// Any `Err` is reported as "Weather alerts could not be checked. Alert
    /// status is unknown." (Python's adapter replaces the upstream error).
    fn alerts(&self, lat: f64, lon: f64) -> Result<Value, String>;
    fn discussion(&self, lat: f64, lon: f64) -> Result<Option<String>, String>;
    /// WPC short-range discussion text; empty when unavailable.
    fn wpc_short_range_discussion(&self) -> Result<String, String>;
    /// SPC day 1 convective outlook text; empty when unavailable.
    fn spc_day1_outlook(&self) -> Result<String, String>;
    /// GET `https://api.open-meteo.com/v1/forecast` with exactly these query
    /// parameters, returning the response JSON.
    fn open_meteo_forecast(&self, params: &[(&'static str, String)]) -> Result<Value, String>;
    /// Names of the saved locations.
    fn location_names(&self) -> Vec<String>;
    /// `ConfigManager.add_location` then save: false when rejected (invalid
    /// coordinates, duplicate name) or not saved. The first saved location
    /// becomes current.
    fn add_location(&self, name: &str, latitude: f64, longitude: f64) -> bool;
    fn saved_locations(&self) -> Vec<Location>;
    fn current_location_name(&self) -> Option<String>;
}

fn tool(name: &str, description: &str, properties: Value, required: &[&str]) -> Value {
    let mut parameters = json!({"type": "object", "properties": properties});
    if !required.is_empty() {
        parameters["required"] = json!(required);
    }
    json!({"type": "function", "function": {"name": name, "description": description, "parameters": parameters}})
}

fn location_tool(name: &str, description: &str, location: &str) -> Value {
    tool(
        name,
        description,
        json!({"location": {"type": "string", "description": location}}),
        &["location"],
    )
}

/// `CORE_TOOLS`: current conditions, forecast, alerts.
pub fn core_tools() -> Vec<Value> {
    vec![
        location_tool(
            "get_current_weather",
            "Get current weather conditions for a location.",
            "The location to get weather for, e.g. 'New York, NY' or '10001'.",
        ),
        location_tool(
            "get_forecast",
            "Get the weather forecast for a location.",
            "The location to get the forecast for, e.g. 'New York, NY' or '10001'.",
        ),
        location_tool(
            "get_alerts",
            "Get active weather alerts for a location.",
            "The location to get weather alerts for, e.g. 'New York, NY' or '10001'.",
        ),
    ]
}

/// `DISCUSSION_TOOLS`: AFD, WPC and SPC discussions.
pub fn discussion_tools() -> Vec<Value> {
    vec![
        location_tool(
            "get_area_forecast_discussion",
            "Get the Area Forecast Discussion (AFD) for a location. This is a detailed technical forecast discussion written by local NWS forecasters. Great for understanding the reasoning behind the forecast.",
            "Location to get the AFD for, e.g. 'New York, NY'.",
        ),
        tool(
            "get_wpc_discussion",
            "Get the Weather Prediction Center (WPC) Short Range Forecast Discussion. A nationwide weather discussion covering the next 1-3 days. Covers major weather systems, precipitation patterns, and significant weather events across the US.",
            json!({}),
            &[],
        ),
        tool(
            "get_spc_outlook",
            "Get the Storm Prediction Center (SPC) Day 1 Convective Outlook discussion. Covers severe weather risks including tornadoes, large hail, and damaging winds. Explains the meteorological reasoning behind severe weather risk areas.",
            json!({}),
            &[],
        ),
    ]
}

/// `EXTENDED_TOOLS`: hourly forecast, search, Open-Meteo query, saved locations.
pub fn extended_tools() -> Vec<Value> {
    let variables = |description: &str| json!({"type": "array", "items": {"type": "string"}, "description": description});
    vec![
        location_tool(
            "get_hourly_forecast",
            "Get an hourly weather forecast for a location. Useful for questions like 'will it rain at 3pm?' or 'what's the temperature tonight?'.",
            "The location to get the hourly forecast for, e.g. 'New York, NY' or '10001'.",
        ),
        tool(
            "search_location",
            "Search for a location by name or ZIP code to find its full name and coordinates. Useful when the user mentions an ambiguous place name.",
            json!({"query": {"type": "string", "description": "Location name or ZIP code to search for, e.g. 'Paris' or '90210'."}}),
            &["query"],
        ),
        tool(
            "query_open_meteo",
            "Query the Open-Meteo API with custom parameters. Use this for weather questions not covered by other tools, such as soil temperature, cloud cover, dew point, snow depth, precipitation probability, UV index, visibility, surface pressure, cape, and more. Open-Meteo has global coverage and is free.\n\n\
Common hourly variables: temperature_2m, relative_humidity_2m, dew_point_2m, apparent_temperature, precipitation_probability, precipitation, rain, showers, snowfall, snow_depth, weather_code, pressure_msl, surface_pressure, cloud_cover, cloud_cover_low, cloud_cover_mid, cloud_cover_high, visibility, wind_speed_10m, wind_direction_10m, wind_gusts_10m, uv_index, soil_temperature_0cm, soil_temperature_6cm, soil_moisture_0_to_1cm\n\n\
Common daily variables: temperature_2m_max, temperature_2m_min, apparent_temperature_max, apparent_temperature_min, sunrise, sunset, uv_index_max, precipitation_sum, rain_sum, showers_sum, snowfall_sum, precipitation_hours, precipitation_probability_max, wind_speed_10m_max, wind_gusts_10m_max, wind_direction_10m_dominant\n\n\
Common current variables: temperature_2m, relative_humidity_2m, apparent_temperature, is_day, precipitation, rain, showers, snowfall, weather_code, cloud_cover, pressure_msl, surface_pressure, wind_speed_10m, wind_direction_10m, wind_gusts_10m",
            json!({
                "location": {"type": "string", "description": "Location name or coordinates, e.g. 'Paris, France'."},
                "hourly": variables("List of hourly variables to fetch."),
                "daily": variables("List of daily variables to fetch."),
                "current": variables("List of current variables to fetch."),
                "forecast_days": {"type": "integer", "description": "Number of forecast days (1-16, default 7)."},
                "timezone": {"type": "string", "description": "Timezone for results, e.g. 'America/New_York'. Default: auto."},
            }),
            &["location"],
        ),
        tool(
            "add_location",
            "Add a location to the user's saved locations list. Use after confirming with the user which location they want to add.",
            json!({
                "name": {"type": "string", "description": "Display name for the location, e.g. 'New York, NY' or 'Paris, France'."},
                "latitude": {"type": "number", "description": "Latitude of the location."},
                "longitude": {"type": "number", "description": "Longitude of the location."},
            }),
            &["name", "latitude", "longitude"],
        ),
        tool(
            "list_locations",
            "List all saved locations and show which one is currently selected.",
            json!({}),
            &[],
        ),
    ]
}

/// `WEATHER_TOOLS`: every tool.
pub fn weather_tools() -> Vec<Value> {
    let mut tools = core_tools();
    tools.extend(extended_tools());
    tools.extend(discussion_tools());
    tools
}

const EXTENDED_TRIGGERS: [&str; 27] = [
    "hour",
    "tonight",
    "this afternoon",
    "this morning",
    "at ",
    " pm",
    " am",
    "soil",
    "uv",
    "cloud",
    "dew",
    "snow depth",
    "visibility",
    "pressure",
    "sunrise",
    "sunset",
    "cape",
    "custom",
    "add",
    "save",
    "location",
    "list",
    "my locations",
    "search",
    "find",
    "where is",
    "zip",
];
const DISCUSSION_TRIGGERS: [&str; 18] = [
    "discussion",
    "afd",
    "forecast discussion",
    "wpc",
    "spc",
    "storm prediction",
    "weather prediction center",
    "convective",
    "outlook",
    "severe",
    "tornado",
    "supercell",
    "explain the forecast",
    "why is",
    "reasoning",
    "meteorolog",
    "synoptic",
    "national",
];

/// `get_tools_for_message`: core tools always; extended and discussion tools
/// only when the message suggests them, saving tokens on simple questions.
pub fn tools_for_message(message: &str) -> Vec<Value> {
    let text = message.to_lowercase();
    let mut tools = core_tools();
    if EXTENDED_TRIGGERS.iter().any(|t| text.contains(t)) {
        tools.extend(extended_tools());
    }
    if DISCUSSION_TRIGGERS.iter().any(|t| text.contains(t)) {
        tools.extend(discussion_tools());
    }
    tools
}

/// A tool failure before formatting: `ValueError`s print as "Error: ...",
/// anything else as "Error fetching weather data: ...".
enum ToolError {
    Value(String),
    Other(String),
}

type ToolResult = Result<String, ToolError>;

fn required<'a>(arguments: &'a Map<String, Value>, key: &str) -> Result<&'a Value, ToolError> {
    // str(KeyError('location')) is "'location'".
    arguments
        .get(key)
        .ok_or_else(|| ToolError::Other(format!("'{key}'")))
}

fn truncated(text: &str) -> String {
    if text.chars().count() > 3000 {
        format!(
            "{}\n\n[Truncated — full discussion is longer]",
            pyfmt::head(text, 3000)
        )
    } else {
        text.to_string()
    }
}

/// Runs tool calls with the app's data (`WeatherToolExecutor`).
pub struct WeatherToolExecutor<'a> {
    host: &'a dyn AssistantHost,
    /// The selected location, used without geocoding when a tool names it.
    default_location: Option<(f64, f64, String)>,
    /// Alerts the app displays for the selected location.
    displayed_alerts: Option<Vec<WeatherAlert>>,
    /// Reference time for hourly rows and alert expiry.
    now: DateTime<Utc>,
}

impl<'a> WeatherToolExecutor<'a> {
    /// `_get_tool_executor`: the selected location plus the alerts the app is
    /// showing for it (only when `displayed_weather` is for that location).
    pub fn new(
        host: &'a dyn AssistantHost,
        location: Option<&Location>,
        displayed_weather: Option<&WeatherData>,
        now: DateTime<Utc>,
    ) -> Self {
        let displayed_alerts = match (location, displayed_weather) {
            (Some(loc), Some(weather))
                if weather.location.latitude == loc.latitude
                    && weather.location.longitude == loc.longitude =>
            {
                weather.alerts.as_ref().map(|alerts| {
                    alerts
                        .alerts
                        .iter()
                        .filter(|a| !a.is_expired(now))
                        .cloned()
                        .collect()
                })
            }
            _ => None,
        };
        Self {
            host,
            default_location: location.map(|l| (l.latitude, l.longitude, l.name.clone())),
            displayed_alerts,
            now,
        }
    }

    /// The selected location's name (the assistant pins tools to it).
    pub fn selected_location(&self) -> Option<&str> {
        self.default_location
            .as_ref()
            .map(|(_, _, name)| name.as_str())
    }

    /// Run `tool_name`; `Err` only for an unknown tool (Python's `ValueError`).
    pub fn execute(
        &self,
        tool_name: &str,
        arguments: &Map<String, Value>,
    ) -> Result<String, String> {
        let result = match tool_name {
            "get_current_weather" => self.current_weather(arguments),
            "get_forecast" => self.forecast(arguments),
            "get_alerts" => self.alerts(arguments),
            "get_hourly_forecast" => self.hourly_forecast(arguments),
            "search_location" => self.search_location(arguments),
            "add_location" => self.add_location(arguments),
            "list_locations" => Ok(self.list_locations()),
            "query_open_meteo" => self.query_open_meteo(arguments),
            "get_area_forecast_discussion" => self.area_forecast_discussion(arguments),
            "get_wpc_discussion" => Ok(national(
                "WPC Short Range Forecast Discussion",
                "WPC discussion",
                self.host.wpc_short_range_discussion(),
            )),
            "get_spc_outlook" => Ok(national(
                "SPC Day 1 Convective Outlook",
                "SPC outlook",
                self.host.spc_day1_outlook(),
            )),
            _ => return Err(format!("Unknown tool: {tool_name}")),
        };
        Ok(match result {
            Ok(text) => text,
            Err(ToolError::Value(message)) => format!("Error: {message}"),
            Err(ToolError::Other(message)) => format!("Error fetching weather data: {message}"),
        })
    }

    fn matches_default(&self, location: &str) -> bool {
        self.default_location.as_ref().is_some_and(|(_, _, name)| {
            location.trim().to_lowercase() == name.trim().to_lowercase()
        })
    }

    /// `LocationResolver.resolve`.
    fn resolve(
        &self,
        arguments: &Map<String, Value>,
    ) -> Result<(String, f64, f64, String), ToolError> {
        let location = pyfmt::str(required(arguments, "location")?);
        if self.matches_default(&location) {
            if let Some((lat, lon, name)) = &self.default_location {
                return Ok((location, *lat, *lon, name.clone()));
            }
        }
        match self.host.geocode(&location) {
            Some((lat, lon, name)) => Ok((location, lat, lon, name)),
            None => Err(ToolError::Value(format!(
                "Could not resolve location: {location}"
            ))),
        }
    }

    fn current_weather(&self, arguments: &Map<String, Value>) -> ToolResult {
        let (_, lat, lon, name) = self.resolve(arguments)?;
        let data = self
            .host
            .current_conditions(lat, lon)
            .map_err(ToolError::Other)?;
        Ok(format_current_weather(&data, &name))
    }

    fn forecast(&self, arguments: &Map<String, Value>) -> ToolResult {
        let (_, lat, lon, name) = self.resolve(arguments)?;
        let days = match arguments.get("forecast_days") {
            None | Some(Value::Null) => 7,
            Some(value) => match value.as_i64() {
                Some(days) if (1..=16).contains(&days) && value.is_number() => days,
                _ => return Ok("Error: forecast_days must be a whole number from 1 to 16.".into()),
            },
        };
        let data = self
            .host
            .forecast(lat, lon, days as u32)
            .map_err(ToolError::Other)?;
        Ok(format_forecast(&data, &name, days))
    }

    fn alerts(&self, arguments: &Map<String, Value>) -> ToolResult {
        let (location, lat, lon, name) = self.resolve(arguments)?;
        let displayed = if self.matches_default(&location) {
            self.displayed_alerts.as_deref().filter(|a| !a.is_empty())
        } else {
            None
        };
        let data = match self.host.alerts(lat, lon) {
            Ok(data) => data,
            Err(_) => {
                return match displayed {
                    Some(alerts) => Ok(format!(
                        "{}\nLive alert lookup failed; current alert status is unknown.",
                        self.format_displayed(&name, alerts)
                    )),
                    None => Err(ToolError::Other(
                        "Weather alerts could not be checked. Alert status is unknown.".into(),
                    )),
                };
            }
        };
        let live = data
            .get("alerts")
            .or_else(|| data.get("features"))
            .and_then(Value::as_array)
            .map_or(&[][..], Vec::as_slice);
        if let (true, Some(alerts)) = (live.is_empty(), displayed) {
            return Ok(format!(
                "{}\nLive alert lookup found none. The app still displays these alerts; verify their current status before relying on either result.",
                self.format_displayed(&name, alerts)
            ));
        }
        let live_events: Vec<String> = live
            .iter()
            .filter_map(Value::as_object)
            .map(|alert| {
                let props = alert
                    .get("properties")
                    .and_then(Value::as_object)
                    .unwrap_or(alert);
                casefold(&props.get("event").map_or(String::new(), pyfmt::str))
            })
            .collect();
        let displayed_only: Vec<WeatherAlert> = displayed
            .unwrap_or_default()
            .iter()
            .filter(|a| !live_events.contains(&casefold(alert_event(a))))
            .cloned()
            .collect();
        let mut result = format_alerts(&data, &name);
        if !displayed_only.is_empty() {
            result.push_str(&format!(
                "\n\n{}\nThese app-displayed alerts were not returned by the live point lookup. Mention the discrepancy and do not claim they are currently verified.",
                self.format_displayed(&name, &displayed_only)
            ));
        }
        Ok(result)
    }

    /// Describe alerts already visible in the app without claiming they are
    /// newly verified.
    fn format_displayed(&self, name: &str, alerts: &[WeatherAlert]) -> String {
        let rows: Vec<Value> = alerts
            .iter()
            .filter(|a| !a.is_expired(self.now))
            .map(|a| {
                json!({"event": alert_event(a), "severity": a.severity,
                       "headline": a.headline, "description": a.description})
            })
            .collect();
        format!(
            "Alerts currently displayed in the app for {name}:\n{}",
            format_alerts(&json!({"alerts": rows}), name)
        )
    }

    fn hourly_forecast(&self, arguments: &Map<String, Value>) -> ToolResult {
        let (_, lat, lon, name) = self.resolve(arguments)?;
        let data = self
            .host
            .hourly_forecast(lat, lon)
            .map_err(ToolError::Other)?;
        Ok(format_hourly_forecast(&data, &name, self.now))
    }

    fn search_location(&self, arguments: &Map<String, Value>) -> ToolResult {
        let query = pyfmt::str(required(arguments, "query")?);
        let suggestions = self.host.suggest_locations(&query, 5);
        Ok(format_location_search(&suggestions, &query))
    }

    fn add_location(&self, arguments: &Map<String, Value>) -> ToolResult {
        let name = pyfmt::str(required(arguments, "name")?);
        // Python's float() also accepts numeric strings.
        let coordinate = |v: &Value| v.as_f64().or_else(|| v.as_str()?.trim().parse().ok());
        let latitude = coordinate(required(arguments, "latitude")?);
        let longitude = coordinate(required(arguments, "longitude")?);
        if self.host.location_names().contains(&name) {
            return Ok(format!("'{name}' is already in your saved locations."));
        }
        match (latitude, longitude) {
            (Some(lat), Some(lon)) if self.host.add_location(&name, lat, lon) => {
                Ok(format!("Added '{name}' to your saved locations."))
            }
            _ => Ok(format!(
                "Failed to add '{name}'. It may already exist under a similar name."
            )),
        }
    }

    fn list_locations(&self) -> String {
        let locations = self.host.saved_locations();
        if locations.is_empty() {
            return "No saved locations.".into();
        }
        let current = self.host.current_location_name();
        let mut lines = vec!["Your saved locations:".to_string()];
        for loc in &locations {
            let marker = if current.as_deref() == Some(loc.name.as_str()) {
                " (current)"
            } else {
                ""
            };
            lines.push(format!(
                "- {} ({:.2}, {:.2}){marker}",
                loc.name, loc.latitude, loc.longitude
            ));
        }
        lines.join("\n")
    }

    fn query_open_meteo(&self, arguments: &Map<String, Value>) -> ToolResult {
        let (_, lat, lon, name) = self.resolve(arguments)?;
        let mut params: Vec<(&'static str, String)> = vec![
            ("latitude", pyfmt::float(lat)),
            ("longitude", pyfmt::float(lon)),
            (
                "timezone",
                arguments.get("timezone").map_or("auto".into(), query_value),
            ),
        ];
        for key in ["current", "hourly", "daily"] {
            if let Some(value) = arguments.get(key) {
                params.push((key, join_variables(value)?));
            }
        }
        if let Some(days) = arguments.get("forecast_days") {
            params.push(("forecast_days", query_value(days)));
        }
        if !params
            .iter()
            .any(|(k, _)| matches!(*k, "current" | "hourly" | "daily"))
        {
            return Ok(
                "Error: specify at least one of current, hourly, or daily variables.".into(),
            );
        }
        Ok(match self.host.open_meteo_forecast(&params) {
            Ok(data) => format_open_meteo_response(&data, &name, self.now),
            Err(error) => format!("Error querying Open-Meteo: {error}"),
        })
    }

    fn area_forecast_discussion(&self, arguments: &Map<String, Value>) -> ToolResult {
        let (_, lat, lon, name) = self.resolve(arguments)?;
        Ok(match self.host.discussion(lat, lon) {
            Ok(Some(text)) if !text.is_empty() => {
                format!(
                    "Area Forecast Discussion for {name}:\n\n{}",
                    truncated(&text)
                )
            }
            Ok(_) => format!("No Area Forecast Discussion available for {name}."),
            Err(error) => format!("Error fetching AFD: {error}"),
        })
    }
}

fn alert_event(alert: &WeatherAlert) -> &str {
    alert
        .event
        .as_deref()
        .filter(|e| !e.is_empty())
        .unwrap_or(&alert.title)
}

/// `",".join(value)` as Python evaluates it for a tool argument.
fn join_variables(value: &Value) -> Result<String, ToolError> {
    match value {
        Value::Array(items) => items
            .iter()
            .enumerate()
            .map(|(i, item)| match item {
                Value::String(s) => Ok(s.clone()),
                _ => Err(ToolError::Other(format!(
                    "sequence item {i}: expected str instance, {} found",
                    type_name(item)
                ))),
            })
            .collect::<Result<Vec<_>, _>>()
            .map(|parts| parts.join(",")),
        Value::String(s) => Ok(s.chars().map(String::from).collect::<Vec<_>>().join(",")),
        _ => Err(ToolError::Other("can only join an iterable".into())),
    }
}

/// How httpx renders a primitive query parameter.
fn query_value(value: &Value) -> String {
    match value {
        Value::Bool(b) => b.to_string(),
        Value::Null => String::new(),
        other => pyfmt::str(other),
    }
}

fn type_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::Number(n) if n.is_f64() => "float",
        Value::Number(_) => "int",
        Value::String(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
    }
}

fn national(title: &str, short: &str, result: Result<String, String>) -> String {
    match result {
        Ok(text) if !text.is_empty() => format!("{title}:\n\n{}", truncated(&text)),
        Ok(_) => format!("{short} unavailable."),
        Err(error) => format!("Error fetching {short}: {error}"),
    }
}
