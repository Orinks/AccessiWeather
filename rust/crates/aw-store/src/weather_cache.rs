//! Offline weather cache in `<config>/weather_cache`, one JSON file per
//! location. Port of `WeatherDataCache` (`accessiweather/cache.py`) and
//! `accessiweather/cache_serialization.py`.
//!
//! Files are written exactly as Python's `json.dump(payload, fh, indent=2)`
//! writes them (ASCII escapes, Python float repr, same key order), so either
//! edition reads the other's cache. Two things cannot match byte for byte:
//! Python lists its sets (`contributing_sources`, `incomplete_sections`) in
//! arbitrary hash order where Rust sorts them, and Rust datetimes carry a
//! fixed offset only, so they are stored with `utc_offset_seconds` where
//! Python may store a named `original_tz`. Named zones are still read.

use std::fs;
use std::path::PathBuf;

use aw_core::model::{
    CurrentConditions, EnvironmentalConditions, Forecast, ForecastPeriod, HourlyForecast,
    HourlyForecastPeriod, Location, PyTimestamp, SourceAttribution, Timestamp, TrendInsight,
    WeatherAlert, WeatherAlerts, WeatherData,
};
use chrono::{
    DateTime, Duration, FixedOffset, Local, NaiveDate, NaiveDateTime, SecondsFormat, TimeZone,
    Timelike, Utc,
};
use serde_json::{json, Map, Value};

/// Bumped whenever the cache layout changes; other versions are discarded.
pub const CACHE_SCHEMA_VERSION: i64 = 6;
/// Python constructs the cache with its default age (the
/// `offline_cache_max_age_minutes` setting is not consulted).
pub const DEFAULT_MAX_AGE_MINUTES: i64 = 180;
/// `stale_reason` given to every entry loaded from disk.
pub const CACHED_DATA_REASON: &str = "Cached data";

/// Persists the latest weather data per location for offline fallback.
#[derive(Debug, Clone)]
pub struct WeatherDataCache {
    pub cache_dir: PathBuf,
    pub max_age: Duration,
}

impl WeatherDataCache {
    /// Create the cache, making `cache_dir` if needed.
    pub fn new(cache_dir: impl Into<PathBuf>, max_age_minutes: i64) -> std::io::Result<Self> {
        let cache_dir = cache_dir.into();
        fs::create_dir_all(&cache_dir)?;
        Ok(Self {
            cache_dir,
            max_age: Duration::minutes(max_age_minutes),
        })
    }

    /// Write `weather` for `location`, stamped `now`. Failures are logged only.
    pub fn store(&self, location: &Location, weather: &WeatherData, now: DateTime<Utc>) {
        let mut stored_location = Map::new();
        stored_location.insert("name".into(), json!(location.name));
        stored_location.insert("latitude".into(), json!(location.latitude));
        stored_location.insert("longitude".into(), json!(location.longitude));
        if let Some(code) = location.country_code.as_deref().filter(|c| !c.is_empty()) {
            stored_location.insert("country_code".into(), json!(code));
        }
        let mut payload = Map::new();
        payload.insert("schema_version".into(), json!(CACHE_SCHEMA_VERSION));
        payload.insert(
            "saved_at".into(),
            serialize_datetime(Some(&now.fixed_offset())),
        );
        payload.insert("location".into(), Value::Object(stored_location));
        payload.insert("weather".into(), serialize_weather_data(weather));
        let mut text = to_python_json(&Value::Object(payload));
        if cfg!(windows) {
            // Python writes the file in text mode, which uses CRLF on Windows.
            text = text.replace('\n', "\r\n");
        }
        if let Err(e) = crate::write_atomic(&self.path_for_location(location), text.as_bytes()) {
            tracing::debug!("Failed to persist weather cache: {e}");
        }
    }

    /// Load the cached entry for `location`, marked stale when older than
    /// `max_age`. With `allow_stale == false` stale entries are not returned.
    /// Entries from another schema version are deleted.
    pub fn load(
        &self,
        location: &Location,
        allow_stale: bool,
        now: DateTime<Utc>,
    ) -> Option<WeatherData> {
        let path = self.path_for_location(location);
        let text = fs::read_to_string(&path).ok()?;
        let payload: Value = match serde_json::from_str(&text) {
            Ok(v) => v,
            Err(e) => {
                tracing::debug!("Failed to read cached weather data: {e}");
                return None;
            }
        };
        let schema = payload.get("schema_version").map_or(Some(1), Value::as_i64);
        if schema != Some(CACHE_SCHEMA_VERSION) {
            tracing::debug!(
                "Cache schema version mismatch for {}; invalidating",
                location.name
            );
            let _ = fs::remove_file(&path);
            return None;
        }
        let saved_at = deserialize_datetime(payload.get("saved_at")).unwrap_or(now.fixed_offset());
        let age = now - saved_at.with_timezone(&Utc);
        if !allow_stale && age > self.max_age {
            return None;
        }

        let stored = payload.get("location").filter(|v| v.is_object());
        let stored_str = |key: &str| stored.and_then(|l| l.get(key)).and_then(Value::as_str);
        let stored_num = |key: &str| stored.and_then(|l| l.get(key)).and_then(Value::as_f64);
        let mut normalized = Location::new(
            stored_str("name").unwrap_or(&location.name),
            stored_num("latitude").unwrap_or(location.latitude),
            stored_num("longitude").unwrap_or(location.longitude),
        );
        normalized.country_code = stored_str("country_code").map(str::to_string);
        normalized.normalize();

        let weather_payload = payload.get("weather").filter(|v| v.is_object())?;
        let mut weather = deserialize_weather_data(weather_payload, normalized, now);
        weather.stale = age > self.max_age;
        weather.stale_since = Some(saved_at);
        weather.stale_reason = Some(CACHED_DATA_REASON.into());
        Some(weather)
    }

    /// Delete entries older than twice `max_age`, and unreadable ones.
    pub fn purge_expired(&self, now: DateTime<Utc>) {
        let Ok(entries) = fs::read_dir(&self.cache_dir) else {
            return;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("json") {
                continue;
            }
            let saved_at = fs::read_to_string(&path)
                .ok()
                .and_then(|text| serde_json::from_str::<Value>(&text).ok())
                .filter(Value::is_object)
                .map(|payload| {
                    deserialize_datetime(payload.get("saved_at")).unwrap_or(now.fixed_offset())
                });
            let expired = saved_at.is_none_or(|s| now - s.with_timezone(&Utc) > self.max_age * 2);
            if expired {
                let _ = fs::remove_file(&path);
            }
        }
    }

    pub fn invalidate(&self, location: &Location) {
        let _ = fs::remove_file(self.path_for_location(location));
    }

    pub fn path_for_location(&self, location: &Location) -> PathBuf {
        self.cache_dir
            .join(format!("{}.json", safe_location_key(location)))
    }
}

/// `_safe_location_key`: `"{name}-{lat}-{lon}"` with every run of characters
/// outside `[A-Za-z0-9_-]` replaced by `_`, then `_` trimmed from both ends.
pub fn safe_location_key(location: &Location) -> String {
    let raw = format!(
        "{}-{}-{}",
        location.name,
        py_float_repr(location.latitude),
        py_float_repr(location.longitude)
    );
    let mut out = String::with_capacity(raw.len());
    let mut in_run = false;
    for c in raw.chars() {
        if c.is_ascii_alphanumeric() || c == '_' || c == '-' {
            out.push(c);
            in_run = false;
        } else if !in_run {
            out.push('_');
            in_run = true;
        }
    }
    let trimmed = out.trim_matches('_');
    if trimmed.is_empty() {
        "location".into()
    } else {
        trimmed.into()
    }
}

// ---------------------------------------------------------------------------
// Python-compatible JSON text
// ---------------------------------------------------------------------------

/// A float as Python's `json.dump` writes it: `repr`, with the `NaN` and
/// `Infinity` tokens for non-finite values.
pub fn py_float_repr(value: f64) -> String {
    if value.is_nan() {
        return "NaN".into();
    }
    if value.is_infinite() {
        return if value > 0.0 { "Infinity" } else { "-Infinity" }.into();
    }
    aw_core::py::float_repr(value)
}

/// `json.dumps(value, indent=2)` with Python's defaults (`ensure_ascii`).
pub fn to_python_json(value: &Value) -> String {
    let mut out = String::new();
    write_value(&mut out, value, 0);
    out
}

fn write_value(out: &mut String, value: &Value, level: usize) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Number(n) => match n.as_f64().filter(|_| n.is_f64()) {
            Some(f) => out.push_str(&py_float_repr(f)),
            None => out.push_str(&n.to_string()),
        },
        Value::String(s) => write_string(out, s),
        Value::Array(items) if items.is_empty() => out.push_str("[]"),
        Value::Object(map) if map.is_empty() => out.push_str("{}"),
        Value::Array(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                out.push_str(if i == 0 { "\n" } else { ",\n" });
                indent(out, level + 1);
                write_value(out, item, level + 1);
            }
            out.push('\n');
            indent(out, level);
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            for (i, (key, item)) in map.iter().enumerate() {
                out.push_str(if i == 0 { "\n" } else { ",\n" });
                indent(out, level + 1);
                write_string(out, key);
                out.push_str(": ");
                write_value(out, item, level + 1);
            }
            out.push('\n');
            indent(out, level);
            out.push('}');
        }
    }
}

fn indent(out: &mut String, level: usize) {
    out.push_str(&"  ".repeat(level));
}

fn write_string(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            ' '..='~' => out.push(c),
            _ => {
                let mut units = [0u16; 2];
                for unit in c.encode_utf16(&mut units) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
        }
    }
    out.push('"');
}

// ---------------------------------------------------------------------------
// datetimes
// ---------------------------------------------------------------------------

/// `_serialize_datetime`: `{"iso": <UTC isoformat>}` plus the original
/// offset in `utc_offset_seconds` when it is not UTC.
pub fn serialize_datetime(value: Option<&Timestamp>) -> Value {
    let Some(value) = value else {
        return Value::Null;
    };
    let mut out = Map::new();
    out.insert(
        "iso".into(),
        json!(python_isoformat(&value.with_timezone(&Utc).fixed_offset())),
    );
    let offset = value.offset().local_minus_utc();
    if offset != 0 {
        out.insert("utc_offset_seconds".into(), json!(offset));
    }
    Value::Object(out)
}

/// `datetime.isoformat()`: microseconds only when non-zero.
fn python_isoformat(value: &Timestamp) -> String {
    let value = value
        .with_nanosecond(value.nanosecond() / 1000 * 1000)
        .unwrap_or(*value);
    let format = if value.nanosecond() == 0 {
        SecondsFormat::Secs
    } else {
        SecondsFormat::Micros
    };
    value.to_rfc3339_opts(format, false)
}

/// `datetime.fromisoformat`, with naive values taken as local time.
fn parse_iso(text: &str) -> Option<Timestamp> {
    let text = text.trim();
    if text.is_empty() {
        return None;
    }
    let normalized = text.replacen(' ', "T", 1);
    if let Ok(dt) = DateTime::parse_from_rfc3339(&normalized) {
        return Some(dt);
    }
    for format in ["%Y-%m-%dT%H:%M:%S%.f%:z", "%Y-%m-%dT%H:%M%:z"] {
        if let Ok(dt) = DateTime::parse_from_str(&normalized, format) {
            return Some(dt);
        }
    }
    let naive = ["%Y-%m-%dT%H:%M:%S%.f", "%Y-%m-%dT%H:%M"]
        .iter()
        .find_map(|f| NaiveDateTime::parse_from_str(&normalized, f).ok())
        .or_else(|| {
            NaiveDate::parse_from_str(&normalized, "%Y-%m-%d")
                .ok()
                .and_then(|d| d.and_hms_opt(0, 0, 0))
        })?;
    Local
        .from_local_datetime(&naive)
        .earliest()
        .map(|dt| dt.fixed_offset())
}

/// `_deserialize_datetime`: the `{"iso", "original_tz" | "utc_offset_seconds"}`
/// form or a legacy ISO string.
pub fn deserialize_datetime(value: Option<&Value>) -> Option<Timestamp> {
    match value? {
        Value::Object(map) => {
            let dt = parse_iso(map.get("iso")?.as_str()?)?;
            if let Some(tz) = map
                .get("original_tz")
                .and_then(Value::as_str)
                .filter(|s| !s.is_empty())
                .and_then(|name| name.parse::<chrono_tz::Tz>().ok())
            {
                return Some(dt.with_timezone(&tz).fixed_offset());
            }
            let offset = map
                .get("utc_offset_seconds")
                .filter(|v| !v.is_null())
                .and_then(|v| v.as_i64().or(v.as_f64().map(|f| f.trunc() as i64)))
                .and_then(|secs| i32::try_from(secs).ok())
                .and_then(FixedOffset::east_opt);
            Some(match offset {
                Some(offset) => dt.with_timezone(&offset),
                None => dt,
            })
        }
        Value::String(s) => parse_iso(s),
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// weather data
// ---------------------------------------------------------------------------

fn obj(pairs: Vec<(&str, Value)>) -> Value {
    Value::Object(pairs.into_iter().map(|(k, v)| (k.to_string(), v)).collect())
}

fn ts(value: &Option<Timestamp>) -> Value {
    serialize_datetime(value.as_ref())
}

/// Python stores a naive datetime as its wall time in UTC.
fn py_ts(value: &Option<PyTimestamp>) -> Value {
    serialize_datetime(value.map(|v| v.coerce_utc().fixed_offset()).as_ref())
}

fn serialize_current(c: &CurrentConditions) -> Value {
    obj(vec![
        ("temperature_f", json!(c.temperature_f)),
        ("temperature_c", json!(c.temperature_c)),
        ("condition", json!(c.condition)),
        ("humidity", json!(c.humidity)),
        ("dewpoint_f", json!(c.dewpoint_f)),
        ("dewpoint_c", json!(c.dewpoint_c)),
        ("wind_speed_mph", json!(c.wind_speed_mph)),
        ("wind_speed_kph", json!(c.wind_speed_kph)),
        ("wind_direction", json!(c.wind_direction)),
        ("pressure_in", json!(c.pressure_in)),
        ("pressure_mb", json!(c.pressure_mb)),
        ("feels_like_f", json!(c.feels_like_f)),
        ("feels_like_c", json!(c.feels_like_c)),
        ("visibility_miles", json!(c.visibility_miles)),
        ("visibility_km", json!(c.visibility_km)),
        ("uv_index", json!(c.uv_index)),
        ("sunrise_time", ts(&c.sunrise_time)),
        ("sunset_time", ts(&c.sunset_time)),
    ])
}

fn serialize_forecast_period(p: &ForecastPeriod) -> Value {
    obj(vec![
        ("name", json!(p.name)),
        ("temperature", json!(p.temperature)),
        ("temperature_unit", json!(p.temperature_unit)),
        ("short_forecast", json!(p.short_forecast)),
        ("detailed_forecast", json!(p.detailed_forecast)),
        ("wind_speed", json!(p.wind_speed)),
        ("wind_direction", json!(p.wind_direction)),
        ("icon", json!(p.icon)),
        ("start_time", ts(&p.start_time)),
        ("end_time", ts(&p.end_time)),
    ])
}

fn serialize_hourly_period(p: &HourlyForecastPeriod) -> Value {
    obj(vec![
        ("start_time", serialize_datetime(Some(&p.start_time))),
        ("end_time", ts(&p.end_time)),
        ("temperature", json!(p.temperature)),
        ("temperature_unit", json!(p.temperature_unit)),
        ("short_forecast", json!(p.short_forecast)),
        ("wind_speed", json!(p.wind_speed)),
        ("wind_direction", json!(p.wind_direction)),
        ("icon", json!(p.icon)),
        ("humidity", json!(p.humidity)),
        ("dewpoint_f", json!(p.dewpoint_f)),
        ("dewpoint_c", json!(p.dewpoint_c)),
        ("pressure_mb", json!(p.pressure_mb)),
        ("pressure_in", json!(p.pressure_in)),
    ])
}

fn serialize_alert(a: &WeatherAlert) -> Value {
    let mut pairs = vec![
        ("title", json!(a.title)),
        ("description", json!(a.description)),
        ("severity", json!(a.severity)),
        ("urgency", json!(a.urgency)),
        ("certainty", json!(a.certainty)),
        ("event", json!(a.event)),
        ("headline", json!(a.headline)),
        ("instruction", json!(a.instruction)),
        ("onset", ts(&a.onset)),
        ("expires", ts(&a.expires)),
        ("areas", json!(a.areas)),
        ("id", json!(a.id)),
        ("source", json!(a.source)),
    ];
    // Only when populated, keeping legacy entries' shape.
    for (key, list) in [
        ("affected_zones", &a.affected_zones),
        ("same_codes", &a.same_codes),
        ("same_event_codes", &a.same_event_codes),
    ] {
        if !list.is_empty() {
            pairs.push((key, json!(list)));
        }
    }
    obj(pairs)
}

fn serialize_environmental(e: &EnvironmentalConditions) -> Value {
    obj(vec![
        ("air_quality_index", json!(e.air_quality_index)),
        ("air_quality_category", json!(e.air_quality_category)),
        ("air_quality_pollutant", json!(e.air_quality_pollutant)),
        ("air_quality_updated_at", ts(&e.air_quality_updated_at)),
        (
            "air_quality_reporting_area",
            json!(e.air_quality_reporting_area),
        ),
        ("air_quality_source", json!(e.air_quality_source)),
        ("pollen_index", json!(e.pollen_index)),
        ("pollen_category", json!(e.pollen_category)),
        ("pollen_tree_index", json!(e.pollen_tree_index)),
        ("pollen_grass_index", json!(e.pollen_grass_index)),
        ("pollen_weed_index", json!(e.pollen_weed_index)),
        ("pollen_primary_allergen", json!(e.pollen_primary_allergen)),
        ("updated_at", ts(&e.updated_at)),
        ("sources", json!(e.sources)),
    ])
}

fn serialize_trend(t: &TrendInsight) -> Value {
    obj(vec![
        ("metric", json!(t.metric)),
        ("direction", json!(t.direction)),
        ("change", json!(t.change)),
        ("unit", json!(t.unit)),
        ("timeframe_hours", json!(t.timeframe_hours)),
        ("summary", json!(t.summary)),
        ("sparkline", json!(t.sparkline)),
    ])
}

fn serialize_attribution(a: &SourceAttribution) -> Value {
    obj(vec![
        ("contributing_sources", json!(a.contributing_sources)),
        ("failed_sources", json!(a.failed_sources)),
        ("field_sources", json!(a.field_sources)),
    ])
}

/// `_serialize_weather_data`: the subset of `WeatherData` the cache keeps.
pub fn serialize_weather_data(w: &WeatherData) -> Value {
    let or_null = |v: Option<Value>| v.unwrap_or(Value::Null);
    obj(vec![
        (
            "current",
            or_null(w.current.as_ref().map(serialize_current)),
        ),
        (
            "forecast",
            or_null(w.forecast.as_ref().map(|f| {
                obj(vec![
                    (
                        "periods",
                        Value::Array(f.periods.iter().map(serialize_forecast_period).collect()),
                    ),
                    ("generated_at", py_ts(&f.generated_at)),
                ])
            })),
        ),
        (
            "hourly_forecast",
            or_null(w.hourly_forecast.as_ref().map(|h| {
                obj(vec![
                    (
                        "periods",
                        Value::Array(h.periods.iter().map(serialize_hourly_period).collect()),
                    ),
                    ("generated_at", py_ts(&h.generated_at)),
                ])
            })),
        ),
        ("discussion", json!(w.discussion)),
        ("discussion_issuance_time", ts(&w.discussion_issuance_time)),
        (
            "alerts",
            or_null(w.alerts.as_ref().map(|a| {
                obj(vec![(
                    "alerts",
                    Value::Array(a.alerts.iter().map(serialize_alert).collect()),
                )])
            })),
        ),
        (
            "environmental",
            or_null(w.environmental.as_ref().map(serialize_environmental)),
        ),
        (
            "trend_insights",
            Value::Array(w.trend_insights.iter().map(serialize_trend).collect()),
        ),
        (
            "source_attribution",
            or_null(w.source_attribution.as_ref().map(serialize_attribution)),
        ),
        ("incomplete_sections", json!(w.incomplete_sections)),
        ("stale", json!(w.stale)),
        ("stale_since", ts(&w.stale_since)),
        ("stale_reason", json!(w.stale_reason)),
    ])
}

/// Lenient field access mirroring Python's `data.get(key)` on cached dicts.
struct Fields<'a>(&'a Map<String, Value>, DateTime<Utc>);

impl Fields<'_> {
    fn f64(&self, key: &str) -> Option<f64> {
        self.0.get(key).and_then(Value::as_f64)
    }
    fn i64(&self, key: &str) -> Option<i64> {
        let v = self.0.get(key)?;
        v.as_i64().or(v.as_f64().map(|f| f.round() as i64))
    }
    /// `CurrentConditions.wind_direction`: Python caches degrees or text as-is.
    fn wind_direction(&self, key: &str) -> Option<aw_core::model::WindDirection> {
        match self.0.get(key)? {
            Value::Number(n) => n.as_f64().map(aw_core::model::WindDirection::Degrees),
            Value::String(s) => Some(aw_core::model::WindDirection::Text(s.clone())),
            _ => None,
        }
    }

    fn string(&self, key: &str) -> Option<String> {
        self.0.get(key).and_then(Value::as_str).map(str::to_string)
    }
    fn string_or(&self, key: &str, default: &str) -> String {
        self.string(key).unwrap_or_else(|| default.to_string())
    }
    fn time(&self, key: &str) -> Option<Timestamp> {
        deserialize_datetime(self.0.get(key))
    }
    fn strings(&self, key: &str) -> Vec<String> {
        self.0
            .get(key)
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default()
    }
    fn objects(&self, key: &str) -> Vec<&Map<String, Value>> {
        self.0
            .get(key)
            .and_then(Value::as_array)
            .map(|items| items.iter().filter_map(Value::as_object).collect())
            .unwrap_or_default()
    }
}

fn section<'a>(data: &'a Map<String, Value>, key: &str, now: DateTime<Utc>) -> Option<Fields<'a>> {
    data.get(key)
        .and_then(Value::as_object)
        .map(|m| Fields(m, now))
}

fn deserialize_current(d: &Fields) -> CurrentConditions {
    let mut current = CurrentConditions {
        temperature_f: d.f64("temperature_f"),
        temperature_c: d.f64("temperature_c"),
        condition: d.string("condition"),
        humidity: d.i64("humidity"),
        dewpoint_f: d.f64("dewpoint_f"),
        dewpoint_c: d.f64("dewpoint_c"),
        wind_speed_mph: d.f64("wind_speed_mph"),
        wind_speed_kph: d.f64("wind_speed_kph"),
        wind_direction: d.wind_direction("wind_direction"),
        pressure_in: d.f64("pressure_in"),
        pressure_mb: d.f64("pressure_mb"),
        feels_like_f: d.f64("feels_like_f"),
        feels_like_c: d.f64("feels_like_c"),
        visibility_miles: d.f64("visibility_miles"),
        visibility_km: d.f64("visibility_km"),
        uv_index: d.f64("uv_index"),
        sunrise_time: d.time("sunrise_time"),
        sunset_time: d.time("sunset_time"),
        ..Default::default()
    };
    current.backfill();
    current
}

fn deserialize_forecast_period(d: &Fields) -> ForecastPeriod {
    ForecastPeriod {
        name: d.string_or("name", ""),
        temperature: d.f64("temperature"),
        temperature_unit: d.string_or("temperature_unit", "F"),
        short_forecast: d.string("short_forecast"),
        detailed_forecast: d.string("detailed_forecast"),
        wind_speed: d.string("wind_speed"),
        wind_direction: d.string("wind_direction"),
        icon: d.string("icon"),
        start_time: d.time("start_time"),
        end_time: d.time("end_time"),
        ..Default::default()
    }
}

fn deserialize_hourly_period(d: &Fields) -> HourlyForecastPeriod {
    // Python falls back to a naive local `datetime.now()`.
    let start = d
        .time("start_time")
        .unwrap_or_else(|| d.1.with_timezone(&Local).fixed_offset());
    HourlyForecastPeriod {
        end_time: d.time("end_time"),
        temperature: d.f64("temperature"),
        temperature_unit: d.string_or("temperature_unit", "F"),
        short_forecast: d.string("short_forecast"),
        wind_speed: d.string("wind_speed"),
        wind_direction: d.string("wind_direction"),
        icon: d.string("icon"),
        humidity: d.i64("humidity"),
        dewpoint_f: d.f64("dewpoint_f"),
        dewpoint_c: d.f64("dewpoint_c"),
        pressure_mb: d.f64("pressure_mb"),
        pressure_in: d.f64("pressure_in"),
        ..HourlyForecastPeriod::new(start)
    }
}

fn deserialize_alert(d: &Fields) -> WeatherAlert {
    WeatherAlert {
        severity: d.string_or("severity", "Unknown"),
        urgency: d.string_or("urgency", "Unknown"),
        certainty: d.string_or("certainty", "Unknown"),
        event: d.string("event"),
        headline: d.string("headline"),
        instruction: d.string("instruction"),
        onset: d.time("onset"),
        expires: d.time("expires"),
        areas: d.strings("areas"),
        id: d.string("id"),
        source: d.string("source"),
        affected_zones: d.strings("affected_zones"),
        same_codes: d.strings("same_codes"),
        same_event_codes: d.strings("same_event_codes"),
        ..WeatherAlert::new(
            d.string_or("title", "Weather Alert"),
            d.string_or("description", ""),
        )
    }
}

fn deserialize_environmental(d: &Fields) -> Option<EnvironmentalConditions> {
    let env = EnvironmentalConditions {
        air_quality_index: d.f64("air_quality_index"),
        air_quality_category: d.string("air_quality_category"),
        air_quality_pollutant: d.string("air_quality_pollutant"),
        air_quality_updated_at: d.time("air_quality_updated_at"),
        air_quality_reporting_area: d.string("air_quality_reporting_area"),
        air_quality_source: d.string("air_quality_source"),
        pollen_index: d.f64("pollen_index"),
        pollen_category: d.string("pollen_category"),
        pollen_tree_index: d.f64("pollen_tree_index"),
        pollen_grass_index: d.f64("pollen_grass_index"),
        pollen_weed_index: d.f64("pollen_weed_index"),
        pollen_primary_allergen: d.string("pollen_primary_allergen"),
        updated_at: d.time("updated_at"),
        sources: d.strings("sources"),
        ..Default::default()
    };
    env.has_data().then_some(env)
}

fn deserialize_trend(d: &Fields) -> TrendInsight {
    let hours = d.0.get("timeframe_hours").and_then(|v| match v {
        Value::String(s) => s.trim().parse().ok(),
        _ => v.as_i64().or(v.as_f64().map(|f| f.trunc() as i64)),
    });
    TrendInsight {
        metric: d.string_or("metric", ""),
        direction: d.string_or("direction", "steady"),
        change: d.f64("change"),
        unit: d.string("unit"),
        timeframe_hours: hours.unwrap_or(24),
        summary: d.string("summary"),
        sparkline: d.string("sparkline"),
    }
}

/// `_deserialize_weather_data`.
pub fn deserialize_weather_data(
    data: &Value,
    location: Location,
    now: DateTime<Utc>,
) -> WeatherData {
    let empty = Map::new();
    let map = data.as_object().unwrap_or(&empty);
    let top = Fields(map, now);
    let with_periods = |key: &str| section(map, key, now);
    WeatherData {
        current: section(map, "current", now).map(|d| deserialize_current(&d)),
        forecast: with_periods("forecast").map(|d| Forecast {
            periods: d
                .objects("periods")
                .into_iter()
                .map(|p| deserialize_forecast_period(&Fields(p, now)))
                .collect(),
            generated_at: d.time("generated_at").map(PyTimestamp::Aware),
            summary: None,
        }),
        hourly_forecast: with_periods("hourly_forecast").map(|d| HourlyForecast {
            periods: d
                .objects("periods")
                .into_iter()
                .map(|p| deserialize_hourly_period(&Fields(p, now)))
                .collect(),
            generated_at: d.time("generated_at").map(PyTimestamp::Aware),
            summary: None,
        }),
        discussion: top.string("discussion"),
        discussion_issuance_time: top.time("discussion_issuance_time"),
        alerts: section(map, "alerts", now).map(|d| WeatherAlerts {
            alerts: d
                .objects("alerts")
                .into_iter()
                .map(|a| deserialize_alert(&Fields(a, now)))
                .collect(),
        }),
        environmental: section(map, "environmental", now)
            .and_then(|d| deserialize_environmental(&d)),
        trend_insights: top
            .objects("trend_insights")
            .into_iter()
            .map(|t| deserialize_trend(&Fields(t, now)))
            .collect(),
        source_attribution: section(map, "source_attribution", now).map(|d| SourceAttribution {
            contributing_sources: d.strings("contributing_sources").into_iter().collect(),
            failed_sources: d.strings("failed_sources").into_iter().collect(),
            field_sources: d
                .0
                .get("field_sources")
                .and_then(Value::as_object)
                .map(|m| {
                    m.iter()
                        .filter_map(|(k, v)| v.as_str().map(|s| (k.clone(), s.to_string())))
                        .collect()
                })
                .unwrap_or_default(),
            conflicts: Vec::new(),
        }),
        incomplete_sections: top.strings("incomplete_sections").into_iter().collect(),
        stale: map.get("stale").and_then(Value::as_bool).unwrap_or(false),
        stale_since: top.time("stale_since"),
        stale_reason: top.string("stale_reason"),
        ..WeatherData::new(location)
    }
}

#[cfg(test)]
mod tests;
