//! Open-Meteo → NWS-shaped JSON mapping used by the dict-based weather
//! service (AI tools) and the hourly UV fetch. Ported from
//! `accessiweather.openmeteo_mapper` and `openmeteo_forecast_mapper`.

use aw_core::model::{HourlyUVIndex, Timestamp};
use aw_core::provider_normalization::{calculate_dewpoint, normalize_pressure_to_pascals};
use aw_core::py;
use aw_core::weather_client_parsers::weekday_name;
use chrono::{Datelike, Duration, FixedOffset, NaiveDateTime, TimeZone, Timelike};
use serde_json::{json, Value};

use super::current::{get, utc_offset};
use super::OpenMeteoApiClient;

/// `_parse_openmeteo_datetime`: local wall-clock → UTC ISO string; the input
/// is returned unchanged when there is no offset or it cannot be parsed.
pub fn parse_openmeteo_datetime(datetime_str: Option<&str>, utc_offset_seconds: Option<i64>) -> Option<String> {
    let text = datetime_str.filter(|s| !s.is_empty())?;
    let Some(offset) = utc_offset_seconds else {
        return Some(text.to_string());
    };
    let converted = py::fromisoformat(&text.replace('Z', "")).and_then(|(naive, _)| {
        let tz = FixedOffset::east_opt(i32::try_from(offset).ok()?)?;
        let utc = tz.from_local_datetime(&naive).single()?.naive_utc();
        Some(py::isoformat(utc, FixedOffset::east_opt(0)))
    });
    Some(converted.unwrap_or_else(|| text.to_string()))
}

fn temperature_unit_code(unit: &str) -> &'static str {
    let lower = unit.to_lowercase();
    if lower.contains("fahrenheit") || lower.contains("°f") {
        "wmoUnit:degF"
    } else {
        "wmoUnit:degC"
    }
}

fn wind_speed_unit_code(unit: &str) -> &'static str {
    let lower = unit.to_lowercase();
    let has = |s: &str| lower.contains(s);
    if has("mph") {
        "wmoUnit:mi_h-1"
    } else if has("kmh") || has("km/h") {
        "wmoUnit:km_h-1"
    } else if has("m/s") || has("ms") {
        "wmoUnit:m_s-1"
    } else if has("kn") || has("knot") {
        "wmoUnit:kn"
    } else {
        "wmoUnit:m_s-1"
    }
}

/// `_calculate_dewpoint`: the unit hint defaults to Celsius when empty.
fn mapper_dewpoint(temperature: Option<&Value>, humidity: Option<&Value>, unit_hint: &str) -> Value {
    let unit = if unit_hint.is_empty() { "celsius" } else { unit_hint };
    calculate_dewpoint(py::as_float(temperature), py::as_float(humidity), unit)
        .map_or(Value::Null, |v| json!(v))
}

fn cloud_cover_to_amount(cloud_cover: f64) -> &'static str {
    if cloud_cover <= 12.5 {
        "CLR"
    } else if cloud_cover <= 25.0 {
        "FEW"
    } else if cloud_cover <= 50.0 {
        "SCT"
    } else if cloud_cover <= 87.5 {
        "BKN"
    } else {
        "OVC"
    }
}

/// `_degrees_to_direction`: "VAR" when missing.
pub fn degrees_to_direction(degrees: Option<f64>) -> &'static str {
    const DIRECTIONS: [&str; 16] = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW",
        "NW", "NNW",
    ];
    match degrees {
        None => "VAR",
        Some(d) => {
            let d = d.rem_euclid(360.0);
            DIRECTIONS[(((d + 11.25) / 22.5) as usize) % 16]
        }
    }
}

/// `_get_uv_category` (EPA/WHO bands).
pub fn uv_category(uv_index: f64) -> &'static str {
    if uv_index <= 2.0 {
        "Low"
    } else if uv_index <= 5.0 {
        "Moderate"
    } else if uv_index <= 7.0 {
        "High"
    } else if uv_index <= 10.0 {
        "Very High"
    } else {
        "Extreme"
    }
}

fn str_unit<'a>(units: &'a Value, key: &str, default: &'a str) -> &'a str {
    get(units, key).and_then(Value::as_str).unwrap_or(default)
}

/// `current.get(key)` cloned, `null` when missing.
fn raw(block: &Value, key: &str) -> Value {
    get(block, key).cloned().unwrap_or(Value::Null)
}

fn now_utc_iso(now: Timestamp) -> String {
    py::isoformat(now.naive_utc(), FixedOffset::east_opt(0))
}

/// `map_current_conditions` → NWS observation-shaped JSON.
pub fn map_current_conditions(data: &Value, now: Timestamp) -> Value {
    let empty = Value::Null;
    let current = get(data, "current").unwrap_or(&empty);
    let units = get(data, "current_units").unwrap_or(&empty);
    let daily = get(data, "daily").filter(|d| py::truthy(Some(d))).unwrap_or(&empty);
    let uv_index_value = get(daily, "uv_index_max")
        .filter(|v| py::truthy(Some(v)))
        .and_then(|v| v.as_array()?.first().cloned())
        .unwrap_or(Value::Null);
    let offset = utc_offset(data);
    let now_iso = now_utc_iso(now);
    let temperature_unit = str_unit(units, "temperature_2m", "°C");
    let weather_code = get(current, "weather_code").cloned().unwrap_or(json!(0));
    let description = OpenMeteoApiClient::get_weather_description(&weather_code);
    let cloud_cover = get(current, "cloud_cover").filter(|v| !v.is_null());
    let daily_first = |key: &str| {
        get(daily, key)
            .filter(|v| py::truthy(Some(v)))
            .and_then(|v| v.as_array()?.first().cloned())
            .unwrap_or(Value::Null)
    };
    let timestamp = parse_openmeteo_datetime(get(current, "time").and_then(Value::as_str), offset)
        .unwrap_or_else(|| now_iso.clone());

    json!({
        "properties": {
            "@id": format!("open-meteo-current-{now_iso}"),
            "timestamp": timestamp,
            "temperature": {
                "value": raw(current, "temperature_2m"),
                "unitCode": temperature_unit_code(str_unit(units, "temperature_2m", "°F")),
                "qualityControl": "qc:V",
            },
            "dewpoint": {
                "value": mapper_dewpoint(get(current, "temperature_2m"), get(current, "relative_humidity_2m"), temperature_unit),
                "unitCode": temperature_unit_code(temperature_unit),
                "qualityControl": "qc:V",
            },
            "apparentTemperature": {
                "value": raw(current, "apparent_temperature"),
                "unitCode": temperature_unit_code(str_unit(units, "apparent_temperature", "°F")),
                "qualityControl": "qc:V",
            },
            "windDirection": {
                "value": raw(current, "wind_direction_10m"),
                "unitCode": "wmoUnit:degree_(angle)",
                "qualityControl": "qc:V",
            },
            "windSpeed": {
                "value": raw(current, "wind_speed_10m"),
                "unitCode": wind_speed_unit_code(str_unit(units, "wind_speed_10m", "mph")),
                "qualityControl": "qc:V",
            },
            "windGust": {
                "value": raw(current, "wind_gusts_10m"),
                "unitCode": wind_speed_unit_code(str_unit(units, "wind_speed_10m", "mph")),
                "qualityControl": "qc:V",
            },
            "barometricPressure": {
                "value": normalize_pressure_to_pascals(
                    py::as_float(get(current, "pressure_msl")),
                    Some(str_unit(units, "pressure_msl", "hPa")),
                ),
                "unitCode": "wmoUnit:Pa",
                "qualityControl": "qc:V",
            },
            "relativeHumidity": {
                "value": raw(current, "relative_humidity_2m"),
                "unitCode": "wmoUnit:percent",
                "qualityControl": "qc:V",
            },
            "visibility": {"value": null, "unitCode": "wmoUnit:m", "qualityControl": "qc:Z"},
            "uvIndex": {
                "value": uv_index_value,
                "unitCode": "unit:dimensionless",
                "qualityControl": "qc:Z",
            },
            "cloudLayers": match cloud_cover {
                Some(cc) => json!([{
                    "amount": py::as_float(Some(cc)).map_or("UNK", cloud_cover_to_amount),
                    "base": {"value": null, "unitCode": "wmoUnit:m"},
                }]),
                None => json!([]),
            },
            "textDescription": description,
            "rawMessage": format!("Open-Meteo data: {}", py::value_str(&weather_code)),
            "presentWeather": [{
                "intensity": null,
                "modifier": null,
                "weather": OpenMeteoApiClient::get_weather_description(&weather_code),
                "rawString": py::value_str(&weather_code),
            }],
            "sunrise": daily_first("sunrise"),
            "sunset": daily_first("sunset"),
        }
    })
}

/// `list.get(key, [None])[i]`: `Err` models Python's IndexError.
fn indexed(block: &Value, key: &str, i: usize) -> Result<Value, ()> {
    match get(block, key) {
        Some(Value::Array(items)) => items.get(i).cloned().ok_or(()),
        Some(_) => Err(()),
        None if i == 0 => Ok(Value::Null),
        None => Err(()),
    }
}

/// A value from a parallel series when `i < len` and it is not null.
fn series_at(block: &Value, key: &str, i: usize) -> Option<Value> {
    get(block, key)?.as_array()?.get(i).filter(|v| !v.is_null()).cloned()
}

/// `int(x)` of a JSON number (truncation toward zero).
fn int_value(value: Option<Value>) -> Value {
    value
        .and_then(|v| py::as_float(Some(&v)))
        .map_or(Value::Null, |f| json!(f.trunc() as i64))
}

/// `weather_codes[i] if i < len(weather_codes) else 0`.
fn code_or_zero(block: &Value, i: usize) -> Value {
    get(block, "weather_code")
        .and_then(Value::as_array)
        .and_then(|codes| codes.get(i).cloned())
        .unwrap_or(json!(0))
}

/// Python `str()` of a value or the fallback `0` when it is falsy.
fn or_zero_str(value: &Value) -> String {
    if py::truthy(Some(value)) {
        py::value_str(value)
    } else {
        "0".into()
    }
}

fn create_detailed_forecast(daily: &Value, units: &Value, index: usize, is_daytime: bool) -> String {
    let build = || -> Result<String, ()> {
        let code = get(daily, "weather_code")
            .and_then(Value::as_array)
            .and_then(|codes| codes.get(index).cloned())
            .unwrap_or(json!(0));
        let description = OpenMeteoApiClient::get_weather_description(&code);
        let temp = indexed(
            daily,
            if is_daytime { "temperature_2m_max" } else { "temperature_2m_min" },
            index,
        )?;
        let wind_speed = indexed(daily, "wind_speed_10m_max", index)?;
        let wind_unit = str_unit(units, "wind_speed_10m_max", "mph");
        let wind_dir = indexed(daily, "wind_direction_10m_dominant", index)?;
        let precip = indexed(daily, "precipitation_sum", index)?;
        let precip_unit = str_unit(units, "precipitation_sum", "in");

        let mut parts = vec![description];
        if let Some(t) = py::as_float(Some(&temp)) {
            let label = if is_daytime { "high" } else { "low" };
            parts.push(format!("with a {label} near {}", t.trunc() as i64));
        }
        if let Some(speed) = py::as_float(Some(&wind_speed)).filter(|s| *s > 0.0) {
            let dir = match py::as_float(Some(&wind_dir)) {
                Some(d) => degrees_to_direction(Some(d)),
                None => "",
            };
            parts.push(format!("Wind {dir} {speed:.0} {wind_unit}"));
        }
        if let Some(p) = py::as_float(Some(&precip)).filter(|p| *p > 0.0) {
            parts.push(format!("Precipitation {p:.2} {precip_unit}"));
        }
        Ok(parts.join(". ") + ".")
    };
    build().unwrap_or_else(|_| "Weather conditions expected.".into())
}

/// Wall-clock `datetime` with an optional fixed offset, as Python keeps it.
#[derive(Clone, Copy)]
struct PyDateTime {
    naive: NaiveDateTime,
    offset: Option<FixedOffset>,
}

impl PyDateTime {
    fn with_hour(self, hour: u32) -> Self {
        Self {
            naive: self.naive.with_hour(hour).unwrap_or(self.naive),
            ..self
        }
    }

    fn plus(self, delta: Duration) -> Self {
        Self {
            naive: self.naive + delta,
            ..self
        }
    }

    fn iso(self) -> String {
        py::isoformat(self.naive, self.offset)
    }

    fn weekday(self) -> &'static str {
        weekday_name(self.naive.weekday())
    }
}

fn parse_py_datetime(text: &str) -> Option<PyDateTime> {
    let (naive, offset) = py::fromisoformat(text)?;
    Some(PyDateTime { naive, offset })
}

fn units_are_fahrenheit(units: &Value) -> bool {
    // Python checks `str(daily_units)`, i.e. the dict repr, for these markers.
    let text = units.to_string().to_lowercase();
    text.contains("fahrenheit") || text.contains("°f")
}

fn day_night_periods(
    daily: &Value,
    units: &Value,
    i: usize,
    date_str: &Value,
    offset: Option<i64>,
) -> Result<[Value; 2], ()> {
    let text = date_str.as_str().ok_or(())?;
    let mut date = parse_py_datetime(text).ok_or(())?;
    if date.offset.is_none() {
        if let Some(secs) = offset {
            date.offset = Some(FixedOffset::east_opt(i32::try_from(secs).map_err(|_| ())?).ok_or(())?);
        }
    }
    let wind_speed = indexed(daily, "wind_speed_10m_max", i)?;
    let wind_unit = str_unit(units, "wind_speed_10m_max", "mph");
    let wind_text = format!("{} {wind_unit}", or_zero_str(&wind_speed));
    let direction = degrees_to_direction(py::as_float(Some(&indexed(daily, "wind_direction_10m_dominant", i)?)));
    let code = code_or_zero(daily, i);
    let icon = format!("https://open-meteo.com/images/weather/{}.png", py::value_str(&code));
    let short = OpenMeteoApiClient::get_weather_description(&code);
    let unit_letter = |key: &str| {
        if str_unit(units, key, "°F").to_lowercase().contains("°f") {
            "F"
        } else {
            "C"
        }
    };
    let day = json!({
        "number": i * 2 + 1,
        "name": date.weekday(),
        "startTime": date.with_hour(6).iso(),
        "endTime": date.with_hour(18).iso(),
        "isDaytime": true,
        "temperature": int_value(series_at(daily, "temperature_2m_max", i)),
        "temperatureUnit": unit_letter("temperature_2m_max"),
        "temperatureTrend": null,
        "windSpeed": wind_text,
        "windDirection": direction,
        "icon": icon,
        "shortForecast": short,
        "detailedForecast": create_detailed_forecast(daily, units, i, true),
    });
    let night = json!({
        "number": i * 2 + 2,
        "name": format!("{} Night", date.weekday()),
        "startTime": date.with_hour(18).iso(),
        "endTime": date.with_hour(6).plus(Duration::days(1)).iso(),
        "isDaytime": false,
        "temperature": int_value(series_at(daily, "temperature_2m_min", i)),
        "temperatureUnit": unit_letter("temperature_2m_min"),
        "temperatureTrend": null,
        "windSpeed": wind_text,
        "windDirection": direction,
        "icon": icon,
        "shortForecast": short,
        "detailedForecast": create_detailed_forecast(daily, units, i, false),
    });
    Ok([day, night])
}

/// `map_forecast` → NWS forecast-shaped JSON (day and night periods).
pub fn map_forecast(data: &Value, now: Timestamp) -> Value {
    let empty = Value::Null;
    let daily = get(data, "daily").unwrap_or(&empty);
    let units = get(data, "daily_units").unwrap_or(&empty);
    if !py::truthy(Some(daily)) {
        return json!({"properties": {"periods": []}});
    }
    let offset = utc_offset(data);
    let dates = get(daily, "time").and_then(Value::as_array).cloned().unwrap_or_default();

    let mut periods: Vec<Value> = Vec::new();
    for (i, date_str) in dates.iter().enumerate() {
        match day_night_periods(daily, units, i, date_str, offset) {
            Ok(pair) => periods.extend(pair),
            Err(()) => tracing::warn!("Error processing forecast day {i}"),
        }
    }
    for i in 0..periods.len().saturating_sub(1) {
        let is_day = periods[i]["isDaytime"] == json!(true);
        let next_night = periods[i + 1]["isDaytime"] != json!(true);
        let night_temp = periods[i + 1]["temperature"].clone();
        if is_day && next_night && !night_temp.is_null() {
            periods[i]["temperature_low"] = night_temp;
        }
    }
    let now_iso = now_utc_iso(now);
    json!({
        "properties": {
            "updated": now_iso,
            "units": {
                "temperature": if units_are_fahrenheit(units) { "F" } else { "C" },
                "windSpeed": str_unit(units, "wind_speed_10m_max", "mph"),
                "precipitation": str_unit(units, "precipitation_sum", "in"),
            },
            "forecastGenerator": "Open-Meteo API",
            "generatedAt": now_iso,
            "periods": periods,
        }
    })
}

/// `map_hourly_forecast` → NWS hourly-shaped JSON.
pub fn map_hourly_forecast(data: &Value, now: Timestamp) -> Value {
    let empty = Value::Null;
    let hourly = get(data, "hourly").unwrap_or(&empty);
    let units = get(data, "hourly_units").unwrap_or(&empty);
    if !py::truthy(Some(hourly)) {
        return json!({"properties": {"periods": []}});
    }
    let offset = utc_offset(data);
    let times = get(hourly, "time").and_then(Value::as_array).cloned().unwrap_or_default();
    let temp_unit = str_unit(units, "temperature_2m", "°F");
    let wind_unit = str_unit(units, "wind_speed_10m", "mph");
    let arr = |key: &str| get(hourly, key).and_then(Value::as_array).cloned().unwrap_or_default();
    let (temperatures, humidities, dew_points) =
        (arr("temperature_2m"), arr("relative_humidity_2m"), arr("dew_point_2m"));
    let (wind_speeds, wind_directions, is_day) =
        (arr("wind_speed_10m"), arr("wind_direction_10m"), arr("is_day"));

    let mut periods = Vec::new();
    for (i, time) in times.iter().enumerate() {
        let Some(time_str) = time.as_str() else {
            tracing::warn!("Error processing hourly forecast hour {i}");
            continue;
        };
        let parsed = match parse_openmeteo_datetime(Some(time_str), offset) {
            Some(s) => parse_py_datetime(&s),
            None => parse_py_datetime(&time_str.replace('Z', "+00:00")),
        };
        let Some(start) = parsed else {
            tracing::warn!("Error processing hourly forecast hour {i}");
            continue;
        };
        let end = PyDateTime {
            naive: start
                .naive
                .date()
                .and_hms_opt(start.naive.hour(), 0, 0)
                .unwrap_or(start.naive),
            ..start
        }
        .plus(Duration::hours(1));
        let non_null = |v: &[Value]| v.get(i).filter(|x| !x.is_null()).cloned();
        let name = if i == 0 {
            "This Hour".to_string()
        } else {
            start.naive.format("%I %p").to_string().trim_start_matches('0').to_string()
        };
        let dewpoint = match non_null(&dew_points) {
            Some(d) => d,
            None => mapper_dewpoint(temperatures.get(i), humidities.get(i), temp_unit),
        };
        let wind = non_null(&wind_speeds).map_or("0".to_string(), |w| py::value_str(&w));
        let code = code_or_zero(hourly, i);
        periods.push(json!({
            "number": i + 1,
            "name": name,
            "startTime": start.iso(),
            "endTime": end.iso(),
            "isDaytime": is_day.get(i).map_or(true, |v| py::truthy(Some(v))),
            "temperature": int_value(non_null(&temperatures)),
            "temperatureUnit": if temp_unit.to_lowercase().contains("°f") { "F" } else { "C" },
            "temperatureTrend": null,
            "relativeHumidity": {
                "value": non_null(&humidities).unwrap_or(Value::Null),
                "unitCode": "wmoUnit:percent",
                "qualityControl": "qc:V",
            },
            "dewpoint": {
                "value": dewpoint,
                "unitCode": temperature_unit_code(temp_unit),
                "qualityControl": "qc:V",
            },
            "windSpeed": format!("{wind} {wind_unit}"),
            "windDirection": degrees_to_direction(py::as_float(wind_directions.get(i))),
            "icon": format!("https://open-meteo.com/images/weather/{}.png", py::value_str(&code)),
            "shortForecast": OpenMeteoApiClient::get_weather_description(&code),
            "detailedForecast": "",
        }));
    }
    let now_iso = now_utc_iso(now);
    json!({
        "properties": {
            "updated": now_iso,
            "units": {
                "temperature": if units_are_fahrenheit(units) { "F" } else { "C" },
                "windSpeed": wind_unit,
                "precipitation": str_unit(units, "precipitation", "in"),
            },
            "forecastGenerator": "Open-Meteo API",
            "generatedAt": now_iso,
            "periods": periods,
        }
    })
}

/// `map_hourly_uv_index`: hourly UV readings converted to UTC.
pub fn map_hourly_uv_index(data: &Value) -> Vec<HourlyUVIndex> {
    let empty = Value::Null;
    let hourly = get(data, "hourly").unwrap_or(&empty);
    let offset = utc_offset(data);
    let times = get(hourly, "time").and_then(Value::as_array).map_or(&[][..], Vec::as_slice);
    let uv = get(hourly, "uv_index").and_then(Value::as_array).map_or(&[][..], Vec::as_slice);

    let mut out = Vec::new();
    for (time, value) in times.iter().zip(uv) {
        let Some(uv_value) = py::as_float(Some(value).filter(|v| !v.is_null())) else {
            continue;
        };
        let Some(text) = time.as_str() else { continue };
        let parsed = match parse_openmeteo_datetime(Some(text), offset) {
            Some(s) => py::fromisoformat(&s),
            None => py::fromisoformat(&text.replace('Z', "+00:00")),
        };
        // A naive time (no utc_offset_seconds in the payload) is taken as UTC.
        let Some(timestamp) = parsed.and_then(|(naive, off)| {
            off.unwrap_or(FixedOffset::east_opt(0)?)
                .from_local_datetime(&naive)
                .single()
        }) else {
            continue;
        };
        out.push(HourlyUVIndex {
            timestamp,
            uv_index: uv_value,
            category: uv_category(uv_value).into(),
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn now() -> Timestamp {
        chrono::DateTime::parse_from_rfc3339("2025-01-15T17:30:00+00:00").unwrap()
    }

    #[test]
    fn current_pressure_mapped_to_pascals_once() {
        let data = json!({"current": {"pressure_msl": 1013.2}, "current_units": {"pressure_msl": "hPa"}});
        let mapped = map_current_conditions(&data, now());
        let v = mapped["properties"]["barometricPressure"]["value"].as_f64().unwrap();
        assert!((v - 101320.0).abs() < 1e-6);
        let data = json!({"current": {"pressure_msl": 101320.0}, "current_units": {"pressure_msl": "Pa"}});
        let mapped = map_current_conditions(&data, now());
        assert_eq!(mapped["properties"]["barometricPressure"]["value"], json!(101320.0));
    }

    #[test]
    fn daytime_period_gets_following_night_low() {
        let data = json!({
            "utc_offset_seconds": 0,
            "daily": {"time": ["2025-01-15", "2025-01-16"], "temperature_2m_max": [50.4, 52.9],
                "temperature_2m_min": [30.7, null], "weather_code": [3, 61],
                "wind_speed_10m_max": [10.0, 0.0], "wind_direction_10m_dominant": [180, 90],
                "precipitation_sum": [0.0, 0.25]},
            "daily_units": {"temperature_2m_max": "°F", "temperature_2m_min": "°F"}
        });
        let mapped = map_forecast(&data, now());
        let periods = mapped["properties"]["periods"].as_array().unwrap();
        assert_eq!(periods.len(), 4);
        assert_eq!(periods[0]["temperature_low"], json!(30));
        assert!(periods[2].get("temperature_low").is_none());
        assert_eq!(periods[0]["name"], json!("Wednesday"));
        assert_eq!(periods[1]["name"], json!("Wednesday Night"));
        assert_eq!(periods[0]["startTime"], json!("2025-01-15T06:00:00+00:00"));
        assert_eq!(periods[1]["endTime"], json!("2025-01-16T06:00:00+00:00"));
        assert_eq!(periods[0]["windSpeed"], json!("10.0 mph"));
        assert_eq!(periods[2]["windSpeed"], json!("0 mph"));
        assert_eq!(
            periods[0]["detailedForecast"],
            json!("Overcast. with a high near 50. Wind S 10 mph.")
        );
        assert_eq!(
            periods[3]["detailedForecast"],
            json!("Slight rain. Precipitation 0.25 in.")
        );
    }

    #[test]
    fn eastern_hemisphere_weekday_uses_local_date() {
        let data = json!({"utc_offset_seconds": 36000,
            "daily": {"time": ["2025-01-15"], "temperature_2m_max": [80], "weather_code": [0],
                "wind_speed_10m_max": [5], "wind_direction_10m_dominant": [0]}});
        let mapped = map_forecast(&data, now());
        assert_eq!(mapped["properties"]["periods"][0]["name"], json!("Wednesday"));
        assert_eq!(
            mapped["properties"]["periods"][0]["startTime"],
            json!("2025-01-15T06:00:00+10:00")
        );
    }

    #[test]
    fn hourly_includes_humidity_and_calculated_dewpoint() {
        let data = json!({"utc_offset_seconds": -18000,
            "hourly": {"time": ["2025-01-15T07:00", "2025-01-15T08:00"],
                "temperature_2m": [70.0, 71.0], "relative_humidity_2m": [50, 55],
                "dew_point_2m": [null, 54.0], "weather_code": [1, 2]},
            "hourly_units": {"temperature_2m": "°F"}});
        let mapped = map_hourly_forecast(&data, now());
        let p = &mapped["properties"]["periods"];
        assert_eq!(p[0]["name"], json!("This Hour"));
        assert_eq!(p[1]["name"], json!("1 PM"));
        assert_eq!(p[0]["startTime"], json!("2025-01-15T12:00:00+00:00"));
        assert!((p[0]["dewpoint"]["value"].as_f64().unwrap() - 50.5).abs() < 0.1);
        assert_eq!(p[1]["dewpoint"]["value"], json!(54.0));
        assert_eq!(p[0]["relativeHumidity"]["value"], json!(50));
    }

    #[test]
    fn uv_index_mapping() {
        let data = json!({"utc_offset_seconds": 3600,
            "hourly": {"time": ["2025-06-01T12:00", "2025-06-01T13:00"], "uv_index": [6.5, null]}});
        let uv = map_hourly_uv_index(&data);
        assert_eq!(uv.len(), 1);
        assert_eq!(uv[0].category, "High");
        assert_eq!(uv[0].timestamp.to_rfc3339(), "2025-06-01T11:00:00+00:00");
        assert_eq!(uv_category(2.0), "Low");
        assert_eq!(uv_category(11.0), "Extreme");
    }
}
