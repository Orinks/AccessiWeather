//! Tray icon tooltip text.
//!
//! Ports `format_string_parser.py` and the formatting half of
//! `taskbar_icon_updater.py` (placeholders, feels-like fragment removal,
//! the 127-character cap).

use std::collections::BTreeMap;
use std::sync::LazyLock;

use chrono::{DateTime, Utc};
use regex::Regex;

use crate::display::pyfmt::{char_len, fixed};
use crate::display::units::{
    celsius_to_fahrenheit, fahrenheit_to_celsius, format_precipitation, format_pressure,
    format_visibility, format_wind_speed, resolve_display_unit_system,
    resolve_temperature_unit_preference, resolve_wind_display_unit_system, TemperatureUnit,
};
use crate::location::Location;
use crate::model::{CurrentConditions, ForecastPeriod, HourlyForecastPeriod, WeatherData};
use crate::settings::AppSettings;

pub const DEFAULT_TOOLTIP_TEXT: &str = "AccessiWeather";
pub const DEFAULT_TOOLTIP_FORMAT: &str = "{temp} {condition}";
pub const TOOLTIP_MAX_LENGTH: usize = 127;
const NA: &str = "N/A";

/// `FormatStringParser.SUPPORTED_PLACEHOLDERS`, in Python's order.
pub const SUPPORTED_PLACEHOLDERS: &[(&str, &str)] = &[
    (
        "alert",
        "Most severe active weather alert event name (e.g. 'Tornado Watch'), or empty if none",
    ),
    (
        "condition",
        "Current weather condition (e.g., 'Partly Cloudy')",
    ),
    (
        "feels_like",
        "Feels-like temperature (follows your temperature unit setting)",
    ),
    (
        "high",
        "Forecast high temperature when available (follows your temperature unit setting)",
    ),
    ("humidity", "Current humidity percentage"),
    ("location", "Current location name"),
    (
        "low",
        "Forecast low temperature when available (follows your temperature unit setting)",
    ),
    (
        "precip",
        "Precipitation amount (follows your temperature unit setting)",
    ),
    ("precip_chance", "Chance of precipitation percentage"),
    (
        "pressure",
        "Barometric pressure (follows your temperature unit setting)",
    ),
    (
        "temp",
        "Current temperature (follows your temperature unit setting)",
    ),
    ("temp_c", "Current temperature in Celsius"),
    ("temp_f", "Current temperature in Fahrenheit"),
    ("uv", "UV index"),
    (
        "visibility",
        "Visibility (follows your temperature unit setting)",
    ),
    (
        "wind",
        "Wind direction with speed text (e.g., 'NW at 5 mph')",
    ),
    ("wind_dir", "Wind direction (e.g., 'NW')"),
    (
        "wind_speed",
        "Wind speed (follows your temperature unit setting)",
    ),
];

fn is_supported(name: &str) -> bool {
    SUPPORTED_PLACEHOLDERS.iter().any(|(p, _)| *p == name)
}

// ---------------------------------------------------------------------------
// format_string_parser
// ---------------------------------------------------------------------------

/// `get_placeholders`: names in `{name}` (letters and underscores).
pub fn get_placeholders(format_string: &str) -> Vec<String> {
    let chars: Vec<char> = format_string.chars().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '{' {
            let mut j = i + 1;
            while j < chars.len() && (chars[j].is_ascii_alphabetic() || chars[j] == '_') {
                j += 1;
            }
            if j > i + 1 && chars.get(j) == Some(&'}') {
                out.push(chars[i + 1..j].iter().collect());
                i = j + 1;
                continue;
            }
        }
        i += 1;
    }
    out
}

fn braces_balanced(s: &str) -> bool {
    s.matches('{').count() == s.matches('}').count()
}

/// `validate_format_string`: `Err(message)` when invalid.
pub fn validate_format_string(format_string: &str) -> Result<(), String> {
    if format_string.is_empty() {
        return Ok(());
    }
    if !braces_balanced(format_string) {
        return Err("Unbalanced braces in format string".into());
    }
    let unsupported: Vec<String> = get_placeholders(format_string)
        .into_iter()
        .filter(|p| !is_supported(p))
        .collect();
    if !unsupported.is_empty() {
        let supported: Vec<&str> = SUPPORTED_PLACEHOLDERS.iter().map(|(p, _)| *p).collect();
        return Err(format!(
            "Unsupported placeholder(s): {}. Supported placeholders are: {}",
            unsupported.join(", "),
            supported.join(", ")
        ));
    }
    Ok(())
}

/// `FormatStringParser.format_string`: unknown placeholders stay literal.
pub fn format_string(format_string: &str, data: &BTreeMap<String, String>) -> String {
    if format_string.is_empty() {
        return String::new();
    }
    if !braces_balanced(format_string) {
        return "Error: Unbalanced braces in format string".into();
    }
    let mut result = format_string.to_string();
    for p in get_placeholders(format_string) {
        let key = format!("{{{p}}}");
        let value = data.get(&p).cloned().unwrap_or_else(|| key.clone());
        result = result.replace(&key, &value);
    }
    result
}

/// `get_supported_placeholders_help`.
pub fn supported_placeholders_help() -> String {
    let mut text = "Supported Placeholders:\n\n".to_string();
    for (p, d) in SUPPORTED_PLACEHOLDERS {
        text.push_str(&format!("{{{p}}}: {d}\n"));
    }
    text
}

// ---------------------------------------------------------------------------
// taskbar_icon_updater
// ---------------------------------------------------------------------------

static FEELS_LIKE_PATTERNS: LazyLock<[Regex; 2]> = LazyLock::new(|| {
    [
        Regex::new(r"(?i)\s*\((?:feels(?:\s+like)?|heat\s+index)\s+\{feels_like\}\)"),
        Regex::new(
            r"(?i)\s*(?:[|•,;:-]\s*)?(?:feels(?:\s+like)?|heat\s+index):?\s*\{feels_like\}(?:\s*[|•,;:-])?",
        ),
    ]
    .map(|r| r.expect("static regex"))
});
static MULTI_SPACE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\s{2,}").expect("static regex"));

/// `TaskbarIconUpdater`'s settings and formatting.
#[derive(Debug, Clone, PartialEq)]
pub struct TaskbarIconUpdater {
    pub text_enabled: bool,
    pub dynamic_enabled: bool,
    pub format_string: String,
    pub temperature_unit: String,
    pub wind_speed_unit: String,
    pub verbosity_level: String,
    pub round_values: bool,
}

impl Default for TaskbarIconUpdater {
    fn default() -> Self {
        Self {
            text_enabled: false,
            dynamic_enabled: true,
            format_string: DEFAULT_TOOLTIP_FORMAT.into(),
            temperature_unit: "both".into(),
            wind_speed_unit: "auto".into(),
            verbosity_level: "standard".into(),
            round_values: false,
        }
    }
}

/// The inputs placeholder extraction reads.
struct Source<'a> {
    current: &'a CurrentConditions,
    /// `current.precipitation_probability`: only the preview sample has one.
    current_precip_chance: Option<f64>,
    forecast_periods: &'a [ForecastPeriod],
    hourly_now: Option<&'a HourlyForecastPeriod>,
    alert: String,
    /// The location used to resolve "auto" units (none for previews).
    location: Option<&'a Location>,
}

impl TaskbarIconUpdater {
    /// The updater as `app_lifecycle.py` configures it from settings.
    pub fn from_settings(s: &AppSettings) -> Self {
        Self {
            text_enabled: s.taskbar_icon_text_enabled,
            dynamic_enabled: s.taskbar_icon_dynamic_enabled,
            format_string: s.taskbar_icon_text_format.clone(),
            temperature_unit: s.temperature_unit.clone(),
            wind_speed_unit: s.wind_speed_unit.clone(),
            verbosity_level: s.verbosity_level.clone(),
            round_values: s.round_values,
        }
    }

    /// `format_tooltip`.
    pub fn format_tooltip(
        &self,
        weather_data: Option<&WeatherData>,
        location_name: Option<&str>,
        now: DateTime<Utc>,
    ) -> String {
        if !self.text_enabled {
            return DEFAULT_TOOLTIP_TEXT.into();
        }
        let Some(data) = weather_data else {
            return DEFAULT_TOOLTIP_TEXT.into();
        };
        match data.current.as_ref().filter(|c| c.has_data()) {
            Some(current) => {
                let vars = self.extract(
                    &live_source(data, current, Some(&data.location), now),
                    location_name,
                );
                self.format_text(&vars, None)
            }
            None => DEFAULT_TOOLTIP_TEXT.into(),
        }
    }

    /// `extract_weather_variables` for live data (as `format_tooltip` sees it).
    pub fn extract_weather_variables(
        &self,
        data: &WeatherData,
        location_name: Option<&str>,
        now: DateTime<Utc>,
    ) -> BTreeMap<String, String> {
        let current = data.current.clone().unwrap_or_default();
        self.extract(
            &live_source(data, &current, Some(&data.location), now),
            location_name,
        )
    }

    /// `format_text`: substitute and cap at 127 characters.
    pub fn format_text(&self, data: &BTreeMap<String, String>, format: Option<&str>) -> String {
        let fmt = format
            .filter(|f| !f.is_empty())
            .unwrap_or(&self.format_string);
        truncate_tooltip(&self.format_with_fallback(fmt, data))
    }

    /// `build_preview`: live data when present, else the sample values.
    /// (Python resolves "auto" units without a location here.)
    pub fn build_preview(
        &self,
        format: &str,
        weather_data: Option<&WeatherData>,
        location_name: Option<&str>,
        now: DateTime<Utc>,
    ) -> String {
        if let Some(data) = weather_data {
            if let Some(current) = data.current.as_ref().filter(|c| c.has_data()) {
                let vars = self.extract(&live_source(data, current, None, now), location_name);
                return self.format_text(&vars, Some(format));
            }
        }
        let current = CurrentConditions {
            temperature_f: Some(72.0),
            temperature_c: Some(22.0),
            condition: Some("Partly Cloudy".into()),
            humidity: Some(55),
            wind_speed: Some(8.0),
            wind_speed_mph: Some(8.0),
            wind_speed_kph: Some(12.9),
            wind_direction: Some("NW".into()),
            pressure: Some(30.1),
            pressure_in: Some(30.1),
            pressure_mb: Some(1019.3),
            feels_like_f: Some(74.0),
            feels_like_c: Some(23.0),
            uv_index: Some(5.0),
            visibility_miles: Some(10.0),
            visibility_km: Some(16.1),
            precipitation_in: Some(0.0),
            precipitation_mm: Some(0.0),
            ..Default::default()
        };
        let periods = [
            ForecastPeriod {
                name: "Today".into(),
                temperature: Some(78.0),
                ..Default::default()
            },
            ForecastPeriod {
                name: "Tonight".into(),
                temperature: Some(61.0),
                ..Default::default()
            },
        ];
        let source = Source {
            current: &current,
            current_precip_chance: Some(20.0),
            forecast_periods: &periods,
            hourly_now: None,
            alert: String::new(),
            location: None,
        };
        let vars = self.extract(
            &source,
            Some(
                location_name
                    .filter(|n| !n.is_empty())
                    .unwrap_or("Sample Location"),
            ),
        );
        self.format_text(&vars, Some(format))
    }

    fn temperature_unit(&self, location: Option<&Location>) -> TemperatureUnit {
        resolve_temperature_unit_preference(&self.temperature_unit, location)
    }

    fn extract(&self, src: &Source, location_name: Option<&str>) -> BTreeMap<String, String> {
        let c = src.current;
        let unit = self.temperature_unit(src.location);
        let system = resolve_display_unit_system(&self.temperature_unit, src.location);
        let wind_system = resolve_wind_display_unit_system(
            &self.wind_speed_unit,
            &self.temperature_unit,
            src.location,
        );
        let round = self.round_values;

        let wind_speed = format_wind_speed(
            c.wind_speed_mph,
            unit,
            c.wind_speed_kph,
            if round { 0 } else { 1 },
            wind_system,
        );
        let wind_dir = c.wind_direction.clone().unwrap_or_else(|| NA.into());
        let mut wind_parts: Vec<String> = Vec::new();
        if wind_dir != NA {
            wind_parts.push(wind_dir.clone());
        }
        if wind_speed != NA {
            wind_parts.push(format!("at {wind_speed}"));
        } else if let Some(legacy) = c.wind_speed {
            wind_parts.push(format!("at {} mph", fixed(legacy, 0)));
        }
        let wind = if wind_parts.is_empty() {
            NA.into()
        } else {
            wind_parts.join(" ")
        };

        let precip_in = c.precipitation_in;
        let precip_in = if precip_in.is_none() && c.precipitation_mm.is_none() {
            src.hourly_now.and_then(|p| p.precipitation_amount)
        } else {
            precip_in
        };
        let precip_chance = src
            .current_precip_chance
            .or(src.hourly_now.and_then(|p| p.precipitation_probability));
        let (high, low) = self.forecast_temperatures(src.forecast_periods, unit);

        let mut m = BTreeMap::new();
        let mut put = |k: &str, v: String| {
            m.insert(k.to_string(), v);
        };
        put(
            "location",
            location_name.filter(|n| !n.is_empty()).unwrap_or(NA).into(),
        );
        put("temp", self.format_temperature(c, unit));
        put("temp_f", temp_value(c.temperature_f, "F"));
        put("temp_c", temp_value(c.temperature_c, "C"));
        put(
            "condition",
            c.condition
                .clone()
                .filter(|s| !s.is_empty())
                .unwrap_or_else(|| NA.into()),
        );
        // `humidity or relative_humidity`: 0% reads as missing.
        put(
            "humidity",
            c.humidity
                .filter(|h| *h != 0)
                .map(|h| format!("{h}%"))
                .unwrap_or_else(|| NA.into()),
        );
        put("wind", wind);
        put("wind_speed", wind_speed);
        put("wind_dir", wind_dir);
        put(
            "pressure",
            format_pressure(
                c.pressure_in,
                unit,
                c.pressure_mb,
                if round { 0 } else { 2 },
                system,
            ),
        );
        put("feels_like", format_feels_like(c, unit));
        put("uv", format_numeric(c.uv_index, ""));
        put(
            "visibility",
            format_visibility(
                c.visibility_miles,
                unit,
                c.visibility_km,
                if round { 0 } else { 1 },
                system,
            ),
        );
        put("high", high);
        put("low", low);
        put(
            "precip",
            format_precipitation(
                precip_in,
                unit,
                c.precipitation_mm,
                if round { 0 } else { 2 },
                system,
            ),
        );
        put("precip_chance", format_numeric(precip_chance, ""));
        put("alert", src.alert.clone());
        m
    }

    fn format_temperature(&self, c: &CurrentConditions, unit: TemperatureUnit) -> String {
        match (c.temperature_f, c.temperature_c, unit) {
            (None, None, _) => NA.into(),
            (f, _, TemperatureUnit::Fahrenheit) => temp_value(f, "F"),
            (_, c, TemperatureUnit::Celsius) => temp_value(c, "C"),
            (Some(f), Some(c), TemperatureUnit::Both) => {
                format!("{}F/{}C", fixed(f, 0), fixed(c, 0))
            }
            (Some(f), None, _) => format!("{}F", fixed(f, 0)),
            (None, Some(c), _) => format!("{}C", fixed(c, 0)),
        }
    }

    /// `_format_forecast_temperatures`: (high, low).
    fn forecast_temperatures(
        &self,
        periods: &[ForecastPeriod],
        unit: TemperatureUnit,
    ) -> (String, String) {
        if periods.is_empty() {
            return (NA.into(), NA.into());
        }
        let is_night = |p: &ForecastPeriod| {
            let n = p.name.to_lowercase();
            ["night", "tonight", "overnight"]
                .iter()
                .any(|t| n.contains(t))
        };
        let high_period = periods
            .iter()
            .find(|p| !is_night(p))
            .or_else(|| periods.iter().find(|p| p.temperature.is_some()));
        let high = forecast_temperature(
            high_period.and_then(|p| p.temperature),
            high_period.map_or("F", |p| p.temperature_unit.as_str()),
            unit,
        );
        let (low_value, low_unit) = match periods.iter().find(|p| is_night(p)) {
            Some(p) => (
                p.temperature_low.or(p.temperature),
                p.temperature_unit.as_str(),
            ),
            None => periods
                .iter()
                .find_map(|p| {
                    p.temperature_low
                        .map(|v| (Some(v), p.temperature_unit.as_str()))
                })
                .unwrap_or((None, "F")),
        };
        (high, forecast_temperature(low_value, low_unit, unit))
    }

    /// `_format_with_fallback`.
    fn format_with_fallback(&self, fmt: &str, data: &BTreeMap<String, String>) -> String {
        if !braces_balanced(fmt) {
            return DEFAULT_TOOLTIP_TEXT.into();
        }
        let effective = omit_missing_feels_like_item(fmt, data);
        let result = format_string(&effective, data);
        if result.starts_with("Error:") {
            return DEFAULT_TOOLTIP_TEXT.into();
        }
        let result = result.trim();
        if result.is_empty() {
            DEFAULT_TOOLTIP_TEXT.into()
        } else {
            result.to_string()
        }
    }
}

fn live_source<'a>(
    data: &'a WeatherData,
    current: &'a CurrentConditions,
    location: Option<&'a Location>,
    now: DateTime<Utc>,
) -> Source<'a> {
    let alert = data
        .alerts
        .as_ref()
        .and_then(|a| {
            // `max(key=severity)` keeps the first of equal maxima.
            let mut best = a.alerts.first()?;
            for x in &a.alerts[1..] {
                if x.severity_priority() > best.severity_priority() {
                    best = x;
                }
            }
            Some(
                best.event
                    .clone()
                    .filter(|e| !e.is_empty())
                    .unwrap_or_else(|| best.title.clone()),
            )
        })
        .unwrap_or_default();
    Source {
        current,
        current_precip_chance: None,
        forecast_periods: data.forecast.as_ref().map_or(&[], |f| f.periods.as_slice()),
        hourly_now: data
            .hourly_forecast
            .as_ref()
            .and_then(|h| h.next_hours(1, now).into_iter().next()),
        alert,
        location,
    }
}

fn temp_value(value: Option<f64>, suffix: &str) -> String {
    value.map_or_else(|| NA.into(), |v| format!("{}{suffix}", fixed(v, 0)))
}

/// `_format_numeric` for a float: whole values drop the decimals.
fn format_numeric(value: Option<f64>, suffix: &str) -> String {
    match value {
        None => NA.into(),
        Some(v) if v == v.trunc() => format!("{}{suffix}", v as i64),
        Some(v) => format!("{}{suffix}", fixed(v, 1)),
    }
}

fn format_feels_like(c: &CurrentConditions, unit: TemperatureUnit) -> String {
    let (f, c) = match (c.feels_like_f, c.feels_like_c) {
        (None, None) => return String::new(),
        (Some(f), None) => (f, fahrenheit_to_celsius(f)),
        (None, Some(c)) => (celsius_to_fahrenheit(c), c),
        (Some(f), Some(c)) => (f, c),
    };
    match unit {
        TemperatureUnit::Fahrenheit => temp_value(Some(f), "F"),
        TemperatureUnit::Celsius => temp_value(Some(c), "C"),
        TemperatureUnit::Both => format!("{}F/{}C", fixed(f, 0), fixed(c, 0)),
    }
}

/// `_format_forecast_temperature`. A unit other than F or C is converted
/// both ways, as in Python.
fn forecast_temperature(value: Option<f64>, unit_code: &str, unit: TemperatureUnit) -> String {
    let Some(v) = value else {
        return NA.into();
    };
    let code = if unit_code.is_empty() { "F" } else { unit_code }
        .trim()
        .to_uppercase();
    let f = if code == "F" {
        v
    } else {
        celsius_to_fahrenheit(v)
    };
    let c = if code == "C" {
        v
    } else {
        fahrenheit_to_celsius(v)
    };
    match unit {
        TemperatureUnit::Fahrenheit => temp_value(Some(f), "F"),
        TemperatureUnit::Celsius => temp_value(Some(c), "C"),
        TemperatureUnit::Both => format!("{}F/{}C", fixed(f, 0), fixed(c, 0)),
    }
}

/// `_omit_missing_feels_like_item`: drop "(feels like {feels_like})" style
/// fragments when there is no feels-like value.
fn omit_missing_feels_like_item(fmt: &str, data: &BTreeMap<String, String>) -> String {
    if data.get("feels_like").is_some_and(|v| !v.is_empty()) {
        return fmt.to_string();
    }
    let mut cleaned = fmt.to_string();
    for pattern in FEELS_LIKE_PATTERNS.iter() {
        cleaned = pattern.replace_all(&cleaned, " ").into_owned();
    }
    MULTI_SPACE.replace_all(&cleaned, " ").trim().to_string()
}

/// `_truncate_tooltip`.
fn truncate_tooltip(text: &str) -> String {
    if text.is_empty() {
        return DEFAULT_TOOLTIP_TEXT.into();
    }
    if char_len(text) <= TOOLTIP_MAX_LENGTH {
        return text.to_string();
    }
    let kept: String = text.chars().take(TOOLTIP_MAX_LENGTH - 3).collect();
    format!("{kept}...")
}
