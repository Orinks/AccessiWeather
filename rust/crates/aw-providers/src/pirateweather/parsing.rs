//! Pirate Weather payload parsing, ported from
//! `accessiweather.pirate_weather_parsing`, `pirate_weather_current` and the
//! minutely parser in `accessiweather.notifications.minutely_precipitation`.

use aw_core::model::{
    CurrentConditions, Forecast, ForecastPeriod, HourlyForecast, HourlyForecastPeriod,
    MinutelyPrecipitationForecast, MinutelyPrecipitationPoint, Timestamp, WeatherAlert,
    WeatherAlerts,
};
use aw_core::provider_normalization::{
    format_speed, normalize_dewpoint_pair, normalize_humidity_percent, normalize_millibars,
    normalize_speed_pair, normalize_temperature_pair, normalize_visibility_pair,
    pirate_temperature_unit, pirate_visibility_unit, pirate_wind_unit,
};
use aw_core::py;
use aw_core::thermal_comfort::{sanitize_thermal_comfort_readings, ThermalComfortInput};
use aw_core::weather_client_parsers::{degrees_to_cardinal, describe_moon_phase, weekday_name};
use chrono::{DateTime, Datelike, Duration, FixedOffset, NaiveDate, TimeZone, Utc};
use chrono_tz::Tz;
use serde_json::Value;
use sha1::{Digest, Sha1};

const MIN_INCLUDED_SEVERITIES: [&str; 2] = ["Severe", "Extreme"];

fn get<'a>(data: &'a Value, key: &str) -> Option<&'a Value> {
    data.as_object()?.get(key)
}

fn num(data: &Value, key: &str) -> Option<f64> {
    py::as_float(get(data, key))
}

/// Timezone of a response: the IANA name when known, else the hour offset.
#[derive(Debug, Clone, Copy)]
pub enum ResponseTz {
    Named(Tz),
    Fixed(FixedOffset),
}

impl ResponseTz {
    /// `_resolve_response_timezone`.
    pub fn resolve(data: &Value) -> Self {
        if let Some(name) = get(data, "timezone")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
        {
            match name.parse::<Tz>() {
                Ok(tz) => return ResponseTz::Named(tz),
                Err(_) => tracing::warn!(
                    "Unknown Pirate Weather timezone '{name}'; falling back to offset"
                ),
            }
        }
        let hours = py::as_float(get(data, "offset")).unwrap_or(0.0);
        let secs = (hours * 3600.0).round() as i32;
        ResponseTz::Fixed(
            FixedOffset::east_opt(secs).unwrap_or(FixedOffset::east_opt(0).expect("utc")),
        )
    }

    fn at(&self, utc: DateTime<Utc>) -> Timestamp {
        match self {
            ResponseTz::Named(tz) => utc.with_timezone(tz).fixed_offset(),
            ResponseTz::Fixed(off) => utc.with_timezone(off),
        }
    }

    /// `datetime.fromtimestamp(ts, tz)`.
    pub fn from_timestamp(&self, timestamp: f64) -> Option<Timestamp> {
        Some(self.at(utc_from_timestamp(timestamp)?))
    }

    /// Noon on `date` in this zone.
    fn noon(&self, date: NaiveDate) -> Option<Timestamp> {
        let naive = date.and_hms_opt(12, 0, 0)?;
        match self {
            ResponseTz::Named(tz) => tz
                .from_local_datetime(&naive)
                .earliest()
                .map(|t| t.fixed_offset()),
            ResponseTz::Fixed(off) => off.from_local_datetime(&naive).single(),
        }
    }
}

fn utc_from_timestamp(timestamp: f64) -> Option<DateTime<Utc>> {
    let micros = py::round(timestamp * 1e6) as i64;
    DateTime::from_timestamp_micros(micros)
}

/// `truthy(time)` epoch from a data point.
fn epoch(data: &Value, key: &str) -> Option<f64> {
    let value = get(data, key);
    if py::truthy(value) {
        py::number(value)
    } else {
        None
    }
}

fn percent(data: &Value, key: &str) -> Option<f64> {
    num(data, key).map(|v| py::round(v * 100.0))
}

/// Icon string to a human-readable condition.
pub fn icon_to_condition(icon: Option<&str>) -> Option<String> {
    let icon = icon.filter(|s| !s.is_empty())?;
    let known = match icon {
        "clear-day" | "clear-night" => "Clear",
        "rain" => "Rain",
        "snow" => "Snow",
        "sleet" => "Sleet",
        "wind" => "Windy",
        "fog" => "Fog",
        "cloudy" => "Cloudy",
        "partly-cloudy-day" | "partly-cloudy-night" => "Partly Cloudy",
        "thunderstorm" => "Thunderstorm",
        "hail" => "Hail",
        "tornado" => "Tornado",
        "ice" => "Freezing Rain",
        "mixed" => "Wintry Mix",
        other => return Some(py::title(&other.replace('-', " "))),
    };
    Some(known.to_string())
}

/// `precipType` normalized to lowercase unique names.
pub fn normalize_precipitation_type(precip_type: Option<&Value>) -> Option<Vec<String>> {
    let raw: Vec<String> = match precip_type? {
        Value::String(s) => vec![s.clone()],
        Value::Array(items) => items.iter().map(py::value_str).collect(),
        _ => return None,
    };
    let mut normalized: Vec<String> = Vec::new();
    for name in raw {
        let name = name.trim().to_lowercase();
        if name.is_empty() || name == "none" || name == "null" || normalized.contains(&name) {
            continue;
        }
        normalized.push(name);
    }
    (!normalized.is_empty()).then_some(normalized)
}

fn precip_type_to_condition(precip_type: Option<&Value>) -> Option<String> {
    let names = normalize_precipitation_type(precip_type)?;
    let labels: Vec<String> = names
        .iter()
        .map(|name| match name.as_str() {
            "rain" => "Rain".to_string(),
            "snow" => "Snow".to_string(),
            "sleet" => "Sleet".to_string(),
            "hail" => "Hail".to_string(),
            "ice" => "Freezing Rain".to_string(),
            "mixed" => "Wintry Mix".to_string(),
            other => py::title(&other.replace('-', " ")),
        })
        .collect();
    Some(labels.join(", "))
}

/// Best display condition for a data point: summary, icon, then precipType.
pub fn data_point_condition(point: &Value) -> Option<String> {
    if let Some(summary) = get(point, "summary").and_then(Value::as_str) {
        if !summary.trim().is_empty() {
            return Some(summary.to_string());
        }
    }
    if let Some(icon) = get(point, "icon").and_then(Value::as_str) {
        return icon_to_condition(Some(icon));
    }
    precip_type_to_condition(get(point, "precipType"))
}

/// Deterministic lifecycle ID for a Pirate Weather / WMO alert.
pub fn build_alert_id(alert: &Value) -> String {
    let text = |key: &str, default: &str| {
        let value = get(alert, key);
        if py::truthy(value) {
            py::value_str(value.expect("truthy value exists"))
        } else {
            default.to_string()
        }
    };
    let title = text("title", "Weather Alert").trim().to_lowercase();
    let severity = text("severity", "").trim().to_lowercase();
    let onset = text("time", "");
    let mut regions: Vec<String> = get(alert, "regions")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter(|r| py::truthy(Some(r)))
                .map(|r| py::value_str(r).trim().to_lowercase())
                .collect()
        })
        .unwrap_or_default();
    regions.sort();
    let fingerprint = [title, severity, onset, regions.join(",")].join("|");
    let digest = Sha1::digest(fingerprint.as_bytes());
    let hex: String = digest.iter().map(|b| format!("{b:02x}")).collect();
    format!("pw-wmo-{}", &hex[..16])
}

fn normalize_regions(regions: Option<&Value>) -> Vec<String> {
    regions
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .map(|r| py::value_str(r).trim().to_string())
                .filter(|r| !r.is_empty())
                .collect()
        })
        .unwrap_or_default()
}

/// Epoch timestamp with `-999`/empty sentinels treated as missing.
fn epoch_to_datetime(value: Option<&Value>, tz: &ResponseTz) -> Option<Timestamp> {
    let value = value.filter(|v| !v.is_null() && v.as_str() != Some(""))?;
    let timestamp = py::as_float(Some(value))?;
    if timestamp == -999.0 {
        return None;
    }
    tz.from_timestamp(timestamp)
}

/// Accumulation depth in inches (non-US unit groups report centimeters).
fn accumulation_inches(units: &str, value: Option<f64>) -> Option<f64> {
    let amount = value?;
    Some(if units == "us" { amount } else { amount / 2.54 })
}

/// Accumulated precipitation (never the rate).
fn precipitation_amount_inches(units: &str, point: &Value) -> Option<f64> {
    ["liquidAccumulation", "precipAccumulation"]
        .iter()
        .find_map(|key| accumulation_inches(units, num(point, key)))
}

/// Pirate Weather severity to the standard CAP levels.
pub fn map_severity(severity: Option<&str>) -> String {
    let Some(severity) = severity.filter(|s| !s.is_empty()) else {
        return "Unknown".into();
    };
    match severity.to_lowercase().as_str() {
        "extreme" => "Extreme",
        "severe" | "warning" => "Severe",
        "moderate" | "watch" => "Moderate",
        "minor" | "advisory" => "Minor",
        _ => "Unknown",
    }
    .into()
}

fn block<'a>(data: &'a Value, key: &str) -> &'a [Value] {
    get(data, key)
        .and_then(|b| get(b, "data"))
        .and_then(Value::as_array)
        .map_or(&[], Vec::as_slice)
}

/// `currently` block → current conditions.
pub fn parse_current_conditions(units: &str, data: &Value) -> CurrentConditions {
    let empty = Value::Null;
    let current = get(data, "currently").unwrap_or(&empty);
    let temperature_unit = Some(pirate_temperature_unit(units));
    let wind_unit = Some(pirate_wind_unit(units));
    let visibility_unit = Some(pirate_visibility_unit(units));

    let temperature = normalize_temperature_pair(num(current, "temperature"), temperature_unit);
    let humidity = normalize_humidity_percent(num(current, "humidity"), true);
    let dewpoint = normalize_dewpoint_pair(
        num(current, "dewPoint"),
        temperature_unit,
        temperature.fahrenheit,
        humidity.map(|h| h as f64),
    );
    let wind_speed = normalize_speed_pair(num(current, "windSpeed"), wind_unit);
    let pressure = normalize_millibars(num(current, "pressure"));
    let visibility = normalize_visibility_pair(num(current, "visibility"), visibility_unit, None);
    let feels_like =
        normalize_temperature_pair(num(current, "apparentTemperature"), temperature_unit);
    let comfort = sanitize_thermal_comfort_readings(ThermalComfortInput {
        temperature_f: temperature.fahrenheit,
        temperature_c: temperature.celsius,
        humidity: humidity.map(|h| h as f64),
        feels_like_f: feels_like.fahrenheit,
        feels_like_c: feels_like.celsius,
        ..Default::default()
    });
    let wind_gust = normalize_speed_pair(num(current, "windGust"), wind_unit);

    let (mut sunrise_time, mut sunset_time, mut moon_phase) = (None, None, None);
    if let Some(today) = block(data, "daily").first() {
        let tz = ResponseTz::resolve(data);
        sunrise_time = epoch(today, "sunriseTime").and_then(|t| tz.from_timestamp(t));
        sunset_time = epoch(today, "sunsetTime").and_then(|t| tz.from_timestamp(t));
        moon_phase = describe_moon_phase(get(today, "moonPhase"));
    }

    let mut conditions = CurrentConditions {
        temperature_f: temperature.fahrenheit,
        temperature_c: temperature.celsius,
        condition: data_point_condition(current),
        humidity,
        dewpoint_f: dewpoint.fahrenheit,
        dewpoint_c: dewpoint.celsius,
        wind_speed_mph: wind_speed.mph,
        wind_speed_kph: wind_speed.kph,
        wind_direction: degrees_to_cardinal(py::number(get(current, "windBearing"))),
        pressure_in: pressure.inches,
        pressure_mb: pressure.millibars,
        feels_like_f: comfort.feels_like_f,
        feels_like_c: comfort.feels_like_c,
        visibility_miles: visibility.miles,
        visibility_km: visibility.kilometers,
        uv_index: num(current, "uvIndex"),
        cloud_cover: percent(current, "cloudCover"),
        wind_gust_mph: wind_gust.mph,
        wind_gust_kph: wind_gust.kph,
        // precipIntensity is a rate; the model's amount fields stay empty.
        precipitation_in: None,
        precipitation_mm: None,
        precipitation_type: normalize_precipitation_type(get(current, "precipType")),
        sunrise_time,
        sunset_time,
        moon_phase,
        wind_chill_f: comfort.wind_chill_f,
        wind_chill_c: comfort.wind_chill_c,
        heat_index_f: comfort.heat_index_f,
        heat_index_c: comfort.heat_index_c,
        ..Default::default()
    };
    conditions.backfill();
    conditions
}

/// `daily` block → forecast. All days are returned; a payload whose local
/// dates are not consecutive (e.g. a DST glitch) is rejected with `None`.
pub fn parse_forecast(units: &str, data: &Value, now: Timestamp) -> Option<Forecast> {
    let tz = ResponseTz::resolve(data);
    let temperature_unit = pirate_temperature_unit(units);
    let wind_unit = pirate_wind_unit(units);

    let mut periods = Vec::new();
    let mut parsed_dates: Vec<NaiveDate> = Vec::new();
    for (i, day) in block(data, "daily").iter().enumerate() {
        let (name, start_time) = match epoch(day, "time").and_then(|t| tz.from_timestamp(t)) {
            Some(local) => {
                let date = local.date_naive();
                parsed_dates.push(date);
                let start = tz.noon(date);
                let name = match i {
                    0 => "Today".to_string(),
                    1 => "Tomorrow".to_string(),
                    _ => weekday_name(date.weekday()).to_string(),
                };
                (name, start)
            }
            None => (format!("Day {}", i + 1), None),
        };
        let condition = data_point_condition(day);
        periods.push(ForecastPeriod {
            name,
            temperature: num(day, "temperatureHigh").or_else(|| num(day, "temperatureMax")),
            temperature_low: num(day, "temperatureLow").or_else(|| num(day, "temperatureMin")),
            temperature_unit: temperature_unit.into(),
            short_forecast: condition.clone(),
            detailed_forecast: condition,
            wind_speed: format_speed(num(day, "windSpeed"), wind_unit),
            wind_direction: degrees_to_cardinal(py::number(get(day, "windBearing"))),
            precipitation_probability: percent(day, "precipProbability"),
            snowfall: accumulation_inches(units, num(day, "snowAccumulation")),
            uv_index: num(day, "uvIndex"),
            cloud_cover: percent(day, "cloudCover"),
            wind_gust: format_speed(num(day, "windGust"), wind_unit),
            precipitation_amount: precipitation_amount_inches(units, day),
            precipitation_type: normalize_precipitation_type(get(day, "precipType")),
            start_time,
            ..Default::default()
        });
    }

    if let Some(first) = parsed_dates.first() {
        let consecutive = parsed_dates
            .iter()
            .enumerate()
            .all(|(i, d)| *d == *first + Duration::days(i as i64));
        if !consecutive {
            tracing::warn!(
                "Rejecting Pirate Weather daily forecast with non-consecutive local dates: {parsed_dates:?}"
            );
            return None;
        }
    }

    Some(Forecast {
        periods,
        generated_at: Some(now.to_utc().fixed_offset()),
        summary: get(data, "daily")
            .and_then(|d| get(d, "summary"))
            .and_then(Value::as_str)
            .map(str::to_string),
    })
}

/// `hourly` block → hourly forecast (temperatures always stored in °F).
pub fn parse_hourly_forecast(units: &str, data: &Value, now: Timestamp) -> HourlyForecast {
    let tz = ResponseTz::resolve(data);
    let temperature_unit = Some(pirate_temperature_unit(units));
    let wind_unit = pirate_wind_unit(units);
    let visibility_unit = Some(pirate_visibility_unit(units));

    let periods = block(data, "hourly")
        .iter()
        .map(|hour| {
            let start_time = epoch(hour, "time")
                .and_then(|t| tz.from_timestamp(t))
                .unwrap_or_else(|| now.to_utc().fixed_offset());
            let temperature =
                normalize_temperature_pair(num(hour, "temperature"), temperature_unit);
            let humidity = normalize_humidity_percent(num(hour, "humidity"), true);
            let dewpoint = normalize_dewpoint_pair(
                num(hour, "dewPoint"),
                temperature_unit,
                temperature.fahrenheit,
                humidity.map(|h| h as f64),
            );
            let pressure = normalize_millibars(num(hour, "pressure"));
            let wind_raw = num(hour, "windSpeed");
            let visibility =
                normalize_visibility_pair(num(hour, "visibility"), visibility_unit, None);
            let feels_like =
                normalize_temperature_pair(num(hour, "apparentTemperature"), temperature_unit);

            let mut p = HourlyForecastPeriod::new(start_time);
            p.temperature = temperature.fahrenheit;
            p.short_forecast = data_point_condition(hour);
            p.wind_speed = format_speed(wind_raw, wind_unit);
            p.wind_speed_mph = normalize_speed_pair(wind_raw, Some(wind_unit)).mph;
            p.wind_direction = degrees_to_cardinal(py::number(get(hour, "windBearing")));
            p.humidity = humidity;
            p.dewpoint_f = dewpoint.fahrenheit;
            p.dewpoint_c = dewpoint.celsius;
            p.pressure_mb = pressure.millibars;
            p.pressure_in = pressure.inches;
            p.precipitation_probability = percent(hour, "precipProbability");
            p.snowfall = accumulation_inches(units, num(hour, "snowAccumulation"));
            p.uv_index = num(hour, "uvIndex");
            p.cloud_cover = percent(hour, "cloudCover");
            p.wind_gust_mph = normalize_speed_pair(num(hour, "windGust"), Some(wind_unit)).mph;
            p.precipitation_amount = precipitation_amount_inches(units, hour);
            p.precipitation_type = normalize_precipitation_type(get(hour, "precipType"));
            p.feels_like = feels_like.fahrenheit;
            p.visibility_miles = visibility.miles;
            p.visibility_km = visibility.kilometers;
            p
        })
        .collect();

    HourlyForecast {
        periods,
        generated_at: Some(now.to_utc().fixed_offset()),
        summary: get(data, "hourly")
            .and_then(|h| get(h, "summary"))
            .and_then(Value::as_str)
            .map(str::to_string),
    }
}

/// `alerts` list → alerts; only Severe/Extreme regional alerts are kept.
pub fn parse_alerts(data: &Value) -> WeatherAlerts {
    let tz = ResponseTz::resolve(data);
    let raw_alerts = get(data, "alerts")
        .and_then(Value::as_array)
        .map_or(&[][..], Vec::as_slice);
    let mut alerts = Vec::new();
    for alert in raw_alerts {
        let title = get(alert, "title")
            .filter(|v| py::truthy(Some(v)))
            .map_or_else(|| "Weather Alert".to_string(), py::value_str);
        let description = get(alert, "description")
            .filter(|v| py::truthy(Some(v)))
            .map_or_else(|| title.clone(), py::value_str);
        let severity = map_severity(get(alert, "severity").and_then(Value::as_str));
        if !MIN_INCLUDED_SEVERITIES.contains(&severity.as_str()) {
            tracing::info!(
                "Skipping lower-severity Pirate Weather regional alert '{title}' (severity={severity})"
            );
            continue;
        }
        let onset = epoch_to_datetime(get(alert, "time"), &tz);
        let mut a = WeatherAlert::new(title.clone(), description);
        a.id = Some(build_alert_id(alert));
        a.severity = severity;
        a.urgency = "Unknown".into();
        a.certainty = "Possible".into();
        a.event = Some(title.clone());
        a.headline = Some(title);
        a.areas = normalize_regions(get(alert, "regions"));
        a.onset = onset;
        a.expires = epoch_to_datetime(get(alert, "expires"), &tz);
        a.sent = onset;
        a.effective = onset;
        a.source = Some("PirateWeather".into());
        alerts.push(a);
    }
    tracing::info!("Parsed {} Pirate Weather alerts", alerts.len());
    WeatherAlerts { alerts }
}

/// `parse_pirate_weather_minutely_block`: accepts the full response or the
/// `minutely` object; intensities are stored in mm/hr.
pub fn parse_minutely_block(payload: &Value, units: &str) -> Option<MinutelyPrecipitationForecast> {
    let object = payload.as_object().filter(|o| !o.is_empty())?;
    let minutely = match object.get("minutely") {
        Some(inner) => inner.as_object()?,
        None => object,
    };
    let to_mm = |v: Option<f64>| v.map(|x| if units == "us" { x * 25.4 } else { x });
    let points: Vec<MinutelyPrecipitationPoint> = minutely
        .get("data")?
        .as_array()?
        .iter()
        .filter_map(|point| {
            let time = utc_from_timestamp(py::number(point.get("time"))?)?.fixed_offset();
            Some(MinutelyPrecipitationPoint {
                time,
                precipitation_intensity: to_mm(py::number(point.get("precipIntensity"))),
                precipitation_probability: py::number(point.get("precipProbability")),
                precipitation_type: point
                    .get("precipType")
                    .and_then(Value::as_str)
                    .map(|s| s.trim().to_lowercase())
                    .filter(|s| !s.is_empty()),
                precipitation_intensity_unit: "mm/hr".into(),
                precipitation_intensity_error: to_mm(py::number(point.get("precipIntensityError"))),
                precipitation_intensity_error_unit: "mm/hr".into(),
            })
        })
        .collect();
    if points.is_empty() {
        return None;
    }
    Some(MinutelyPrecipitationForecast {
        summary: minutely
            .get("summary")
            .and_then(Value::as_str)
            .map(str::to_string),
        icon: minutely
            .get("icon")
            .and_then(Value::as_str)
            .map(str::to_string),
        points,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn icons_map_to_conditions() {
        assert_eq!(
            icon_to_condition(Some("clear-day")).as_deref(),
            Some("Clear")
        );
        assert_eq!(
            icon_to_condition(Some("mixed")).as_deref(),
            Some("Wintry Mix")
        );
        assert_eq!(
            icon_to_condition(Some("some-new-icon")).as_deref(),
            Some("Some New Icon")
        );
        assert_eq!(icon_to_condition(None), None);
        assert_eq!(icon_to_condition(Some("")), None);
    }

    #[test]
    fn severity_mapping() {
        assert_eq!(map_severity(Some("warning")), "Severe");
        assert_eq!(map_severity(Some("Watch")), "Moderate");
        assert_eq!(map_severity(Some("advisory")), "Minor");
        assert_eq!(map_severity(Some("bogus")), "Unknown");
        assert_eq!(map_severity(None), "Unknown");
    }

    #[test]
    fn alert_id_is_a_stable_fingerprint() {
        let a = json!({"title": "Winter Storm Warning", "severity": "severe", "time": 1700000000,
            "expires": 1700050000, "uri": "https://a/1", "regions": ["New York"]});
        let mut b = a.clone();
        b["uri"] = json!("https://a/2");
        b["expires"] = json!(1700090000);
        assert_eq!(build_alert_id(&a), build_alert_id(&b));
        assert!(build_alert_id(&a).starts_with("pw-wmo-"));
        assert_eq!(build_alert_id(&a).len(), 23);
    }

    #[test]
    fn precipitation_types_normalize() {
        assert_eq!(
            normalize_precipitation_type(Some(&json!(["Rain", "rain", "none", " snow "]))),
            Some(vec!["rain".to_string(), "snow".to_string()])
        );
        assert_eq!(normalize_precipitation_type(Some(&json!("none"))), None);
        assert_eq!(
            precip_type_to_condition(Some(&json!(["ice", "freezing-drizzle"]))).as_deref(),
            Some("Freezing Rain, Freezing Drizzle")
        );
    }

    #[test]
    fn timezone_prefers_iana_name() {
        let tz = ResponseTz::resolve(&json!({"timezone": "Europe/London", "offset": 0}));
        let t = tz.from_timestamp(1719835200.0).unwrap(); // 2024-07-01 12:00 UTC
        assert_eq!(t.to_rfc3339(), "2024-07-01T13:00:00+01:00");
        let tz = ResponseTz::resolve(&json!({"timezone": "Nowhere/Land", "offset": 5.5}));
        assert_eq!(
            tz.from_timestamp(0.0).unwrap().to_rfc3339(),
            "1970-01-01T05:30:00+05:30"
        );
    }

    #[test]
    fn minutely_intensity_is_stored_in_mm_per_hour() {
        let payload = json!({"minutely": {"summary": "Rain", "data": [
            {"time": 1700000000, "precipIntensity": 0.1, "precipType": "Rain"},
            {"time": "bad"}]}});
        let m = parse_minutely_block(&payload, "us").unwrap();
        assert_eq!(m.points.len(), 1);
        assert!((m.points[0].precipitation_intensity.unwrap() - 2.54).abs() < 1e-9);
        assert_eq!(m.points[0].precipitation_type.as_deref(), Some("rain"));
        assert!(parse_minutely_block(&json!({"minutely": null}), "us").is_none());
        assert!(parse_minutely_block(&json!({}), "si").is_none());
    }
}
