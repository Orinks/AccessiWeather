//! Open-Meteo current-condition parsing, ported from
//! `accessiweather.weather_client_openmeteo_current`.

use aw_core::model::{CurrentConditions, Timestamp};
use aw_core::provider_normalization::{
    normalize_dewpoint_pair, normalize_humidity_percent, normalize_temperature_pair,
};
use aw_core::py;
use aw_core::thermal_comfort::{sanitize_thermal_comfort_readings, ThermalComfortInput};
use aw_core::weather_client_parsers::{
    convert_wind_speed_to_mph_and_kph, degrees_to_cardinal, normalize_pressure, py_int,
    weather_code_to_description,
};
use chrono::{FixedOffset, TimeZone};
use serde_json::Value;

use super::units::{
    normalize_precipitation_to_inches_and_mm, normalize_snow_depth_to_inches_and_cm,
    normalize_visibility_to_miles_and_km,
};

const SNOW_WEATHER_CODES: [i64; 6] = [71, 73, 75, 77, 85, 86];
const RAIN_WEATHER_CODES: [i64; 13] = [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82];
const ACTIVE_PRECIP_EPSILON_IN: f64 = 0.001;
const NEAR_ZERO_SNOW_EPSILON_IN: f64 = 0.0005;

/// `data.get(key)` on a JSON object, treating non-objects as empty.
pub(crate) fn get<'a>(data: &'a Value, key: &str) -> Option<&'a Value> {
    data.as_object()?.get(key)
}

/// `units.get(key)` as a string.
pub(crate) fn unit<'a>(units: &'a Value, key: &str) -> Option<&'a str> {
    get(units, key).and_then(Value::as_str)
}

/// `float(x or 0.0)`.
fn rate(current: &Value, key: &str) -> f64 {
    let value = get(current, key);
    if py::truthy(value) {
        py::as_float(value).unwrap_or(0.0)
    } else {
        0.0
    }
}

/// Infer precipitation type from rain/snow rates with conservative thresholds.
pub fn pick_precipitation_type(rain_in: f64, snow_in: f64) -> Option<Vec<String>> {
    let has_rain = rain_in > ACTIVE_PRECIP_EPSILON_IN;
    let has_snow = snow_in > ACTIVE_PRECIP_EPSILON_IN;
    let types: &[&str] = match (has_rain, has_snow) {
        (true, true) => &["rain", "snow"],
        (true, false) => &["rain"],
        (false, true) => &["snow"],
        (false, false) => return None,
    };
    Some(types.iter().map(|s| s.to_string()).collect())
}

/// Current condition text from `weather_code` refined by rain/snow rates.
pub fn resolve_current_condition_description(current: &Value) -> Option<String> {
    let weather_code = get(current, "weather_code").filter(|v| !v.is_null());
    let base = weather_code_to_description(weather_code);
    let code = weather_code.and_then(py_int);

    let rain = rate(current, "rain") + rate(current, "showers");
    let snow = rate(current, "snowfall");

    if rain <= ACTIVE_PRECIP_EPSILON_IN && snow <= ACTIVE_PRECIP_EPSILON_IN {
        return base;
    }
    if rain > ACTIVE_PRECIP_EPSILON_IN && snow <= NEAR_ZERO_SNOW_EPSILON_IN {
        if code.is_some_and(|c| SNOW_WEATHER_CODES.contains(&c)) {
            return Some(
                if rain < 0.02 {
                    "Light drizzle"
                } else {
                    "Slight rain"
                }
                .into(),
            );
        }
        return base;
    }
    if snow > rain * 1.5 {
        if code.is_some_and(|c| RAIN_WEATHER_CODES.contains(&c)) {
            return Some("Mixed rain and snow".into());
        }
        return base;
    }
    if rain > ACTIVE_PRECIP_EPSILON_IN && snow > ACTIVE_PRECIP_EPSILON_IN {
        return Some("Mixed rain and snow".into());
    }
    base
}

/// Parse an ISO 8601 string, attaching (or converting UTC values to) the
/// location offset; naive values without an offset are UTC.
pub fn parse_iso_datetime(
    value: Option<&str>,
    utc_offset_seconds: Option<i64>,
) -> Option<Timestamp> {
    let value = value.filter(|v| !v.is_empty())?;
    let (naive, offset) = py::fromisoformat(value)?;
    let local = match utc_offset_seconds {
        Some(secs) => Some(FixedOffset::east_opt(i32::try_from(secs).ok()?)?),
        None => None,
    };
    let utc = FixedOffset::east_opt(0)?;
    match (offset, local) {
        (None, local) => local.unwrap_or(utc).from_local_datetime(&naive).single(),
        (Some(off), Some(local)) if off.local_minus_utc() == 0 => Some(
            utc.from_local_datetime(&naive)
                .single()?
                .with_timezone(&local),
        ),
        (Some(off), _) => off.from_local_datetime(&naive).single(),
    }
}

/// `utc_offset_seconds` from a response, when it is an integer.
pub(crate) fn utc_offset(data: &Value) -> Option<i64> {
    get(data, "utc_offset_seconds")
        .and_then(|v| v.as_i64().or_else(|| v.as_f64().map(|f| f as i64)))
}

fn parse_uv_index(current: &Value, daily: &Value) -> Option<f64> {
    if let Some(raw) = get(current, "uv_index").filter(|v| !v.is_null()) {
        return py::as_float(Some(raw));
    }
    match get(daily, "uv_index_max").and_then(Value::as_array) {
        Some(values) if !values.is_empty() => py::as_float(values.first()),
        _ => None,
    }
}

fn first_time(daily: &Value, key: &str, offset: Option<i64>) -> Option<Timestamp> {
    let first = get(daily, key)?.as_array()?.first()?;
    parse_iso_datetime(first.as_str(), offset)
}

/// Parse an Open-Meteo current payload. Unlike Python (which converts
/// afterwards in the fetch helper) the wind direction is returned as a
/// cardinal label, since the model stores text.
pub fn parse_openmeteo_current_conditions(data: &Value) -> CurrentConditions {
    let empty = Value::Null;
    let current = get(data, "current").unwrap_or(&empty);
    let units = get(data, "current_units").unwrap_or(&empty);
    let daily = get(data, "daily").unwrap_or(&empty);
    let offset = utc_offset(data);
    let num = |key: &str| py::as_float(get(current, key));

    let temperature =
        normalize_temperature_pair(num("temperature_2m"), unit(units, "temperature_2m"));
    let humidity = normalize_humidity_percent(num("relative_humidity_2m"), false);
    let dewpoint = normalize_dewpoint_pair(
        None,
        unit(units, "temperature_2m"),
        temperature.fahrenheit,
        humidity.map(|h| h as f64),
    );
    let (wind_speed_mph, wind_speed_kph) =
        convert_wind_speed_to_mph_and_kph(num("wind_speed_10m"), unit(units, "wind_speed_10m"));
    let (pressure_in, pressure_mb) =
        normalize_pressure(num("pressure_msl"), unit(units, "pressure_msl"));
    let feels_like = normalize_temperature_pair(
        num("apparent_temperature"),
        unit(units, "apparent_temperature"),
    );

    let has_daily = daily.as_object().is_some_and(|d| !d.is_empty());
    let (sunrise_time, sunset_time) = if has_daily {
        (
            first_time(daily, "sunrise", offset),
            first_time(daily, "sunset", offset),
        )
    } else {
        (None, None)
    };

    let rain_rate_in = rate(current, "rain") + rate(current, "showers");
    let snow_rate_in = rate(current, "snowfall");
    let (precipitation_in, precipitation_mm) = normalize_precipitation_to_inches_and_mm(
        num("precipitation"),
        unit(units, "precipitation"),
    );
    let (snow_depth_in, snow_depth_cm) =
        normalize_snow_depth_to_inches_and_cm(num("snow_depth"), unit(units, "snow_depth"));
    let (visibility_miles, visibility_km) =
        normalize_visibility_to_miles_and_km(num("visibility"), unit(units, "visibility"));

    let comfort = sanitize_thermal_comfort_readings(ThermalComfortInput {
        temperature_f: temperature.fahrenheit,
        temperature_c: temperature.celsius,
        humidity: humidity.map(|h| h as f64),
        feels_like_f: feels_like.fahrenheit,
        feels_like_c: feels_like.celsius,
        ..Default::default()
    });

    let mut conditions = CurrentConditions {
        temperature_f: temperature.fahrenheit,
        temperature_c: temperature.celsius,
        condition: resolve_current_condition_description(current),
        humidity,
        dewpoint_f: dewpoint.fahrenheit,
        dewpoint_c: dewpoint.celsius,
        wind_speed_mph,
        wind_speed_kph,
        wind_direction: degrees_to_cardinal(py::number(get(current, "wind_direction_10m")))
            .map(Into::into),
        pressure_in,
        pressure_mb,
        feels_like_f: comfort.feels_like_f,
        feels_like_c: comfort.feels_like_c,
        visibility_miles,
        visibility_km,
        sunrise_time,
        sunset_time,
        uv_index: parse_uv_index(current, daily),
        snowfall_rate_in: num("snowfall"),
        snow_depth_in,
        snow_depth_cm,
        wind_chill_f: comfort.wind_chill_f,
        wind_chill_c: comfort.wind_chill_c,
        heat_index_f: comfort.heat_index_f,
        heat_index_c: comfort.heat_index_c,
        precipitation_type: pick_precipitation_type(rain_rate_in, snow_rate_in),
        precipitation_in,
        precipitation_mm,
        ..Default::default()
    };
    conditions.backfill();
    conditions
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn precipitation_type_thresholds() {
        assert_eq!(
            pick_precipitation_type(0.0, 0.01),
            Some(vec!["snow".to_string()])
        );
        assert_eq!(pick_precipitation_type(0.0, 0.0), None);
        assert_eq!(pick_precipitation_type(0.01, 0.01).unwrap().len(), 2);
    }

    #[test]
    fn drizzle_not_mapped_to_snow_when_snowfall_zero() {
        let c = json!({"weather_code": 71, "rain": 0.01, "showers": 0.0, "snowfall": 0.0});
        assert_eq!(
            resolve_current_condition_description(&c).as_deref(),
            Some("Light drizzle")
        );
        let c = json!({"weather_code": 73, "rain": 0.05, "snowfall": 0.0});
        assert_eq!(
            resolve_current_condition_description(&c).as_deref(),
            Some("Slight rain")
        );
    }

    #[test]
    fn mixed_precipitation_labels() {
        let c = json!({"weather_code": 61, "rain": 0.01, "snowfall": 0.05});
        assert_eq!(
            resolve_current_condition_description(&c).as_deref(),
            Some("Mixed rain and snow")
        );
        let c = json!({"weather_code": 73, "rain": 0.01, "snowfall": 0.05});
        assert_eq!(
            resolve_current_condition_description(&c).as_deref(),
            Some("Moderate snow fall")
        );
        let c = json!({"weather_code": 3, "rain": 0.02, "snowfall": 0.02});
        assert_eq!(
            resolve_current_condition_description(&c).as_deref(),
            Some("Mixed rain and snow")
        );
        let c = json!({"weather_code": "bad", "rain": 0.0});
        assert_eq!(
            resolve_current_condition_description(&c).as_deref(),
            Some("Weather code bad")
        );
    }

    #[test]
    fn iso_datetime_offsets() {
        let t = parse_iso_datetime(Some("2025-01-15T07:15"), Some(-18000)).unwrap();
        assert_eq!(t.to_rfc3339(), "2025-01-15T07:15:00-05:00");
        let t = parse_iso_datetime(Some("2025-01-15T12:00Z"), Some(3600)).unwrap();
        assert_eq!(t.to_rfc3339(), "2025-01-15T13:00:00+01:00");
        let t = parse_iso_datetime(Some("2025-01-15T12:00"), None).unwrap();
        assert_eq!(t.to_rfc3339(), "2025-01-15T12:00:00+00:00");
        assert!(parse_iso_datetime(Some("junk"), None).is_none());
    }

    #[test]
    fn uv_index_sources() {
        let data = json!({"current": {"uv_index": 4.2}, "daily": {"uv_index_max": [7.0]}});
        assert_eq!(
            parse_openmeteo_current_conditions(&data).uv_index,
            Some(4.2)
        );
        let data = json!({"current": {}, "daily": {"uv_index_max": [7.0]}});
        assert_eq!(
            parse_openmeteo_current_conditions(&data).uv_index,
            Some(7.0)
        );
        let data = json!({"current": {"uv_index": "bad"}, "daily": {"uv_index_max": [7.0]}});
        assert_eq!(parse_openmeteo_current_conditions(&data).uv_index, None);
    }

    #[test]
    fn precipitation_units() {
        let data =
            json!({"current": {"precipitation": 0.2}, "current_units": {"precipitation": "inch"}});
        let c = parse_openmeteo_current_conditions(&data);
        assert_eq!(c.precipitation_in, Some(0.2));
        assert!((c.precipitation_mm.unwrap() - 5.08).abs() < 1e-9);
        let data =
            json!({"current": {"precipitation": 5.08}, "current_units": {"precipitation": "mm"}});
        assert!(
            (parse_openmeteo_current_conditions(&data)
                .precipitation_in
                .unwrap()
                - 0.2)
                .abs()
                < 1e-9
        );
        let c = parse_openmeteo_current_conditions(&json!({"current": {}}));
        assert_eq!((c.precipitation_in, c.precipitation_mm), (None, None));
    }
}
