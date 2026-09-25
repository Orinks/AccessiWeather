//! Payload parsers from `weather_client_nws_parsers.py`.

use std::collections::HashSet;

use aw_core::model::{
    CurrentConditions, Forecast, ForecastPeriod, HourlyForecast, HourlyForecastPeriod, Location,
    Timestamp, WeatherAlert, WeatherAlerts, WindDirection,
};
use chrono::DateTime;
use serde_json::Value;

use super::common::{
    extract_float, extract_scalar, extract_temperature, extract_wind_speed_mph, format_wind_speed,
    fromisoformat, opt_str, parse_z_datetime, py_float, py_str, str_field, str_or, truthy,
    PyDateTime,
};
use super::normalize::{
    calculate_heat_index_f, calculate_wind_chill_f, convert_pa_to_inches, convert_pa_to_mb,
    convert_wind_speed_to_mph_and_kph, normalize_humidity_percent, normalize_pressure,
    normalize_pressure_pair, normalize_temperature_pair, sanitize_thermal_comfort_readings,
    ThermalInputs,
};

/// A payload Python would have choked on (an exception in the parser).
#[derive(Debug, Clone, PartialEq, thiserror::Error)]
#[error("malformed NWS payload: {0}")]
pub struct Malformed(pub String);

fn unit_or<'a>(measurement: &'a Value, default: &'a str) -> &'a str {
    measurement
        .get("unitCode")
        .filter(|u| truthy(u))
        .and_then(Value::as_str)
        .unwrap_or(default)
}

/// `parse_nws_current_conditions`.
pub fn parse_current_conditions(data: &Value) -> CurrentConditions {
    let props = &data["properties"];

    let temperature = &props["temperature"];
    let (temp_f, temp_c) = normalize_temperature_pair(
        &temperature["value"],
        Some(unit_or(temperature, "wmoUnit:degC")),
    );

    let humidity = normalize_humidity_percent(&props["relativeHumidity"]["value"]);

    let dewpoint = &props["dewpoint"];
    let (dew_f, dew_c) =
        normalize_temperature_pair(&dewpoint["value"], Some(unit_or(dewpoint, "wmoUnit:degC")));

    let visibility_m = props["visibility"]["value"].as_f64();

    let uv_index = match &props["uvIndex"]["value"] {
        Value::Null => None,
        v => py_float(v),
    };

    let wind_speed = &props["windSpeed"];
    let (wind_mph, wind_kph) = convert_wind_speed_to_mph_and_kph(
        wind_speed["value"].as_f64(),
        wind_speed["unitCode"].as_str(),
    );

    let wind_direction = match &props["windDirection"]["value"] {
        Value::Number(n) => n.as_f64().map(WindDirection::Degrees),
        Value::String(s) => Some(WindDirection::Text(s.clone())),
        _ => None,
    };

    let pressure = &props["barometricPressure"];
    let (pressure_in, pressure_mb) =
        normalize_pressure_pair(&pressure["value"], Some(unit_or(pressure, "wmoUnit:Pa")));

    let wind_chill = &props["windChill"];
    let (chill_f, chill_c) = normalize_temperature_pair(
        &wind_chill["value"],
        Some(unit_or(wind_chill, "wmoUnit:degC")),
    );
    let heat_index = &props["heatIndex"];
    let (heat_f, heat_c) = normalize_temperature_pair(
        &heat_index["value"],
        Some(unit_or(heat_index, "wmoUnit:degC")),
    );

    let derived_chill = match (chill_f, temp_f, wind_mph) {
        (None, Some(t), Some(w)) => calculate_wind_chill_f(t, w),
        _ => None,
    };
    let humidity_f = humidity.map(|h| h as f64);
    let derived_heat = match (heat_f, temp_f, humidity_f) {
        (None, Some(t), Some(h)) => calculate_heat_index_f(t, h),
        _ => None,
    };

    let comfort = sanitize_thermal_comfort_readings(ThermalInputs {
        temperature_f: temp_f,
        temperature_c: temp_c,
        humidity: humidity_f,
        feels_like_f: derived_chill.or(derived_heat),
        feels_like_c: None,
        wind_chill_f: chill_f.or(derived_chill),
        wind_chill_c: chill_c,
        heat_index_f: heat_f.or(derived_heat),
        heat_index_c: heat_c,
    });

    let mut current = CurrentConditions {
        temperature_f: temp_f,
        temperature_c: temp_c,
        condition: str_field(props, "textDescription").map(str::to_string),
        humidity,
        dewpoint_f: dew_f,
        dewpoint_c: dew_c,
        wind_speed_mph: wind_mph,
        wind_speed_kph: wind_kph,
        wind_direction,
        pressure_in,
        pressure_mb,
        feels_like_f: comfort.feels_like_f,
        feels_like_c: comfort.feels_like_c,
        visibility_miles: visibility_m.map(|m| m / 1609.344),
        visibility_km: visibility_m.map(|m| m / 1000.0),
        uv_index,
        wind_chill_f: comfort.wind_chill_f,
        wind_chill_c: comfort.wind_chill_c,
        heat_index_f: comfort.heat_index_f,
        heat_index_c: comfort.heat_index_c,
        ..Default::default()
    };
    current.backfill();
    current
}

fn wind_direction_text(period: &Value) -> Option<String> {
    extract_scalar(&period["windDirection"]).map(py_str)
}

/// A timestamp field parsed with `datetime.fromisoformat(s.replace("Z", ...))`,
/// failing on a truthy non-string like Python's `AttributeError`.
fn strict_time(v: &Value, what: &str) -> Result<Option<Timestamp>, Malformed> {
    if !truthy(v) {
        return Ok(None);
    }
    let s = v
        .as_str()
        .ok_or_else(|| Malformed(format!("{what} is not a string")))?;
    let parsed = parse_z_datetime(s);
    if parsed.is_none() {
        tracing::warn!("Failed to parse {what}: {s}");
    }
    Ok(parsed)
}

/// `parse_nws_forecast`. `now` stands in for `datetime.now()`.
pub fn parse_forecast(data: &Value, now: Timestamp) -> Forecast {
    let raw_periods: &[Value] = data["properties"]["periods"]
        .as_array()
        .map(Vec::as_slice)
        .unwrap_or_default();

    let lenient_time = |v: &Value, what: &str| {
        if !truthy(v) {
            return None;
        }
        let parsed = v.as_str().and_then(parse_z_datetime);
        if parsed.is_none() {
            tracing::warn!("Failed to parse {what}: {v}");
        }
        parsed
    };

    let mut periods: Vec<ForecastPeriod> = raw_periods
        .iter()
        .map(|p| {
            let (temperature, unit) = extract_temperature(&p["temperature"], &p["temperatureUnit"]);
            ForecastPeriod {
                name: str_or(p, "name", ""),
                temperature,
                temperature_unit: unit.to_string(),
                short_forecast: opt_str(p, "shortForecast"),
                detailed_forecast: opt_str(p, "detailedForecast"),
                wind_speed: format_wind_speed(&p["windSpeed"]),
                wind_speed_mph: extract_wind_speed_mph(&p["windSpeed"]),
                wind_direction: wind_direction_text(p),
                icon: opt_str(p, "icon"),
                start_time: lenient_time(&p["startTime"], "startTime"),
                end_time: lenient_time(&p["endTime"], "endTime"),
                precipitation_probability: extract_float(&p["probabilityOfPrecipitation"]),
                ..Default::default()
            }
        })
        .collect();

    // NWS alternates day/night periods: a daytime period's low is the
    // following night's temperature.
    for (i, p) in raw_periods.iter().enumerate() {
        let Some(next) = raw_periods.get(i + 1) else {
            break;
        };
        if truthy(&p["isDaytime"]) && !truthy(&next["isDaytime"]) {
            let (night, _) = extract_temperature(&next["temperature"], &next["temperatureUnit"]);
            if night.is_some() {
                periods[i].temperature_low = night;
            }
        }
    }

    Forecast {
        periods,
        generated_at: Some(now),
        summary: None,
    }
}

/// `parse_nws_alerts`: every message type is kept; duplicate IDs collapse
/// to their first occurrence.
pub fn parse_alerts(data: &Value) -> Result<WeatherAlerts, Malformed> {
    let features: &[Value] = data["features"]
        .as_array()
        .map(Vec::as_slice)
        .unwrap_or_default();
    let mut alerts = Vec::with_capacity(features.len());

    for feature in features {
        let props = &feature["properties"];

        let id = if let Some(v) = feature.get("id") {
            Some(v)
        } else if let Some(v) = props.get("identifier") {
            Some(v)
        } else {
            props.get("@id")
        }
        .filter(|v| !v.is_null())
        .map(py_str);

        let references = match &props["references"] {
            Value::Array(refs) => refs
                .iter()
                .filter(|r| r.is_object())
                .filter_map(|r| {
                    ["identifier", "@id", "id"]
                        .iter()
                        .find_map(|k| r.get(*k).filter(|v| truthy(v)))
                        .map(py_str)
                })
                .collect(),
            _ => Vec::new(),
        };

        let areas = match &props["areaDesc"] {
            Value::String(desc) => desc
                .split(';')
                .map(str::trim)
                .filter(|a| !a.is_empty())
                .map(str::to_string)
                .collect(),
            _ => Vec::new(),
        };

        let affected_zones = match &props["affectedZones"] {
            Value::Array(zones) => zones
                .iter()
                .filter_map(Value::as_str)
                .filter(|z| !z.is_empty())
                .map(|z| z.rsplit('/').next().unwrap_or(z).to_string())
                .collect(),
            _ => Vec::new(),
        };

        // geocode.SAME holds county codes; eventCode.SAME the SAME/EAS event
        // code broadcast in the radio header -- different things entirely.
        let same_codes = match &props["geocode"]["SAME"] {
            Value::Array(codes) => codes
                .iter()
                .filter_map(|c| match c {
                    Value::String(s) => Some(s.trim().to_string()),
                    Value::Bool(_) => Some(py_str(c)),
                    Value::Number(n) if !n.is_f64() => Some(n.to_string()),
                    _ => None,
                })
                .filter(|s| !s.is_empty())
                .collect(),
            _ => Vec::new(),
        };
        let same_event_codes = match &props["eventCode"]["SAME"] {
            Value::Array(codes) => codes
                .iter()
                .filter_map(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .collect(),
            _ => Vec::new(),
        };

        let mut alert = WeatherAlert::new(
            str_or(props, "headline", "Weather Alert"),
            str_or(props, "description", ""),
        );
        alert.severity = str_or(props, "severity", "Unknown");
        alert.urgency = str_or(props, "urgency", "Unknown");
        alert.certainty = str_or(props, "certainty", "Unknown");
        alert.event = opt_str(props, "event");
        alert.headline = opt_str(props, "headline");
        alert.instruction = opt_str(props, "instruction");
        alert.onset = strict_time(&props["onset"], "onset time")?;
        alert.expires = strict_time(&props["expires"], "expires time")?;
        alert.sent = strict_time(&props["sent"], "sent time")?;
        alert.effective = strict_time(&props["effective"], "effective time")?;
        alert.areas = areas;
        alert.references = references;
        alert.id = id;
        alert.source = Some("NWS".into());
        alert.message_type = opt_str(props, "messageType");
        alert.affected_zones = affected_zones;
        alert.same_codes = same_codes;
        alert.same_event_codes = same_event_codes;
        alerts.push(alert);
    }

    let mut seen = HashSet::new();
    alerts.retain(|a| match a.id.as_deref().filter(|id| !id.is_empty()) {
        Some(id) => seen.insert(id.to_string()),
        None => true,
    });
    tracing::info!("Parsed {} alerts from NWS API", alerts.len());
    Ok(WeatherAlerts { alerts })
}

/// `parse_nws_hourly_forecast`: times shift into the location's timezone
/// when it has a valid one; `now` stands in for `datetime.now()`.
pub fn parse_hourly_forecast(
    data: &Value,
    location: Option<&Location>,
    now: Timestamp,
) -> Result<HourlyForecast, Malformed> {
    let tz: Option<chrono_tz::Tz> = location
        .and_then(|l| l.timezone.as_deref())
        .filter(|tz| !tz.is_empty())
        .and_then(|name| match name.parse() {
            Ok(tz) => Some(tz),
            Err(_) => {
                tracing::warn!("Failed to load timezone: {name}");
                None
            }
        });
    let localize = |t: Timestamp| match tz {
        Some(tz) => t.with_timezone(&tz).fixed_offset(),
        None => t,
    };

    let mut periods = Vec::new();
    for p in data["properties"]["periods"]
        .as_array()
        .map(Vec::as_slice)
        .unwrap_or_default()
    {
        let start = strict_time(&p["startTime"], "start time")?.map(localize);
        let end = strict_time(&p["endTime"], "end time")?.map(localize);
        let (temperature, unit) = extract_temperature(&p["temperature"], &p["temperatureUnit"]);

        let mut period = HourlyForecastPeriod::new(start.unwrap_or(now));
        period.end_time = end;
        period.temperature = temperature;
        period.temperature_unit = unit.to_string();
        period.short_forecast = opt_str(p, "shortForecast");
        period.wind_speed = format_wind_speed(&p["windSpeed"]);
        period.wind_speed_mph = extract_wind_speed_mph(&p["windSpeed"]);
        period.wind_direction = wind_direction_text(p);
        period.icon = opt_str(p, "icon");
        period.precipitation_probability = extract_float(&p["probabilityOfPrecipitation"]);
        periods.push(period);
    }

    Ok(HourlyForecast {
        periods,
        generated_at: Some(now),
        summary: None,
    })
}

/// (inHg, mb).
pub type PressurePair = (Option<f64>, Option<f64>);

/// Gridpoint pressure keyed by valid-time start.
pub type PressureByTime = Vec<(Timestamp, PressurePair)>;

/// `parse_nws_gridpoint_pressure`. Later entries with an equal start time
/// replace earlier ones, as in the Python dict.
pub fn parse_gridpoint_pressure(data: &Value) -> PressureByTime {
    let pressure = &data["properties"]["pressure"];
    let layer_unit = get_unit(pressure);
    let mut out: PressureByTime = Vec::new();
    for item in pressure["values"]
        .as_array()
        .map(Vec::as_slice)
        .unwrap_or_default()
    {
        if !item.is_object() {
            continue;
        }
        let (Some(start), Some(value)) = (
            parse_valid_time_start(&item["validTime"]),
            extract_float(&item["value"]),
        ) else {
            continue;
        };
        let unit = get_unit(item).or(layer_unit.clone());
        let pair = normalize_gridpoint_pressure(value, unit.as_deref());
        match out.iter_mut().find(|(t, _)| *t == start) {
            Some(slot) => slot.1 = pair,
            None => out.push((start, pair)),
        }
    }
    out
}

/// `pressure.get("uom") or pressure.get("unitCode")`.
fn get_unit(v: &Value) -> Option<String> {
    ["uom", "unitCode"]
        .iter()
        .find_map(|k| v.get(*k).filter(|u| truthy(u)))
        .map(py_str)
}

/// `_normalize_nws_gridpoint_pressure`: unlabelled values around 29-31 are
/// inches, around 850-1100 millibars, anything else pascals.
fn normalize_gridpoint_pressure(value: f64, unit: Option<&str>) -> PressurePair {
    if let Some(unit) = unit.filter(|u| !u.is_empty()) {
        let (i, m) = normalize_pressure(value, Some(unit));
        if i.is_some() || m.is_some() {
            return (i, m);
        }
    }
    if (20.0..=35.0).contains(&value) {
        return (Some(value), Some(value * 33.8639));
    }
    if (850.0..=1100.0).contains(&value) {
        return (Some(value * 0.0295299830714), Some(value));
    }
    (
        Some(convert_pa_to_inches(value)),
        Some(convert_pa_to_mb(value)),
    )
}

/// `_parse_valid_time_start`: the start of an ISO interval "start/duration".
/// Naive values end up compared as UTC (`_timestamp_utc`).
fn parse_valid_time_start(valid_time: &Value) -> Option<Timestamp> {
    if !truthy(valid_time) {
        return None;
    }
    let text = valid_time.as_str()?;
    let start = text.split('/').next().unwrap_or(text);
    let parsed = fromisoformat(&start.replace('Z', "+00:00")).map(PyDateTime::assume_utc);
    if parsed.is_none() {
        tracing::debug!("Failed to parse NWS gridpoint validTime: {text}");
    }
    parsed
}

/// `apply_nws_gridpoint_pressure`: fill hourly periods lacking pressure from
/// the nearest gridpoint valid time within 90 minutes.
pub fn apply_gridpoint_pressure(
    mut hourly: HourlyForecast,
    pressure: &PressureByTime,
) -> HourlyForecast {
    if pressure.is_empty() {
        return hourly;
    }
    for period in &mut hourly.periods {
        if period.pressure_in.is_some() || period.pressure_mb.is_some() {
            continue;
        }
        if let Some((pressure_in, pressure_mb)) = nearest_pressure(period.start_time, pressure) {
            period.pressure_in = pressure_in;
            period.pressure_mb = pressure_mb;
        }
    }
    hourly
}

fn nearest_pressure(start: Timestamp, pressure: &PressureByTime) -> Option<PressurePair> {
    let target = timestamp_secs(start);
    let mut best: Option<(f64, PressurePair)> = None;
    for (valid, pair) in pressure {
        let delta = (timestamp_secs(*valid) - target).abs();
        if best.is_none_or(|(d, _)| delta < d) {
            best = Some((delta, *pair));
        }
    }
    best.filter(|(d, _)| *d <= 90.0 * 60.0)
        .map(|(_, pair)| pair)
}

fn timestamp_secs<Tz: chrono::TimeZone>(t: DateTime<Tz>) -> f64 {
    t.timestamp() as f64 + f64::from(t.timestamp_subsec_nanos()) / 1e9
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn now() -> Timestamp {
        DateTime::parse_from_rfc3339("2026-01-20T12:00:00+00:00").unwrap()
    }

    // tests/test_nws_current_parser.py
    #[test]
    fn current_conditions_normalise_measurements() {
        let payload = json!({"properties": {
            "temperature": {"value": 0.0, "unitCode": "wmoUnit:degC"},
            "dewpoint": {"value": -5.0, "unitCode": "wmoUnit:degC"},
            "relativeHumidity": {"value": 72.4, "unitCode": "wmoUnit:percent"},
            "windSpeed": {"value": 10.0, "unitCode": "wmoUnit:km_h-1"},
            "windDirection": {"value": 270},
            "barometricPressure": {"value": 101325.0, "unitCode": "wmoUnit:Pa"},
            "visibility": {"value": 1609.344, "unitCode": "wmoUnit:m"},
            "windChill": {"value": -8.0, "unitCode": "wmoUnit:degC"},
            "heatIndex": {"value": null, "unitCode": "wmoUnit:degC"},
            "textDescription": "Mostly Cloudy",
            "uvIndex": {"value": "2.5"},
        }});
        let c = parse_current_conditions(&payload);
        assert_eq!(c.temperature_f, Some(32.0));
        assert_eq!(c.temperature_c, Some(0.0));
        assert!((c.dewpoint_f.unwrap() - 23.0).abs() < 1e-9);
        assert_eq!(c.humidity, Some(72));
        assert!((c.wind_speed_mph.unwrap() - 6.21).abs() < 0.01);
        assert_eq!(c.wind_speed_kph, Some(10.0));
        assert_eq!(c.wind_direction, Some(WindDirection::Degrees(270.0)));
        assert!((c.pressure_mb.unwrap() - 1013.25).abs() < 1e-9);
        assert!((c.pressure_in.unwrap() - 29.92).abs() < 0.01);
        assert!((c.visibility_miles.unwrap() - 1.0).abs() < 1e-12);
        assert!((c.feels_like_f.unwrap() - 17.6).abs() < 1e-9);
        assert!((c.wind_chill_f.unwrap() - 17.6).abs() < 1e-9);
        assert_eq!(c.heat_index_f, None);
        assert_eq!(c.condition.as_deref(), Some("Mostly Cloudy"));
        assert_eq!(c.uv_index, Some(2.5));
        assert_eq!(c.temperature, Some(32.0));
    }

    #[test]
    fn current_conditions_derive_wind_chill_and_heat_index() {
        let cold = json!({"properties": {
            "temperature": {"value": 0.0, "unitCode": "wmoUnit:degC"},
            "relativeHumidity": {"value": 72.4},
            "windSpeed": {"value": 16.09344, "unitCode": "wmoUnit:km_h-1"},
            "windChill": {"value": null}, "heatIndex": {"value": null},
        }});
        let c = parse_current_conditions(&cold);
        let expected = calculate_wind_chill_f(32.0, 10.0).unwrap();
        assert!((c.feels_like_f.unwrap() - expected).abs() < 0.1);
        assert!((c.wind_chill_f.unwrap() - expected).abs() < 0.1);
        assert_eq!(c.heat_index_f, None);

        let hot = json!({"properties": {
            "temperature": {"value": 32.2222222, "unitCode": "wmoUnit:degC"},
            "relativeHumidity": {"value": 70.0},
            "windSpeed": {"value": 7.0, "unitCode": "wmoUnit:mi_h-1"},
        }});
        let c = parse_current_conditions(&hot);
        let expected = calculate_heat_index_f(90.0, 70.0).unwrap();
        assert!((c.heat_index_f.unwrap() - expected).abs() < 0.1);
        assert!((c.feels_like_f.unwrap() - expected).abs() < 0.1);
        assert_eq!(c.wind_chill_f, None);
    }

    // tests/test_nws_high_low.py
    #[test]
    fn forecast_pairs_day_high_with_night_low() {
        let data = json!({"properties": {"periods": [
            {"name": "Tonight", "temperature": 30, "temperatureUnit": "F", "isDaytime": false},
            {"name": "Monday", "temperature": 45, "temperatureUnit": "F", "isDaytime": true,
             "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 40},
             "detailedForecast": "Sunny.", "windSpeed": "5 to 10 mph", "windDirection": "SW"},
            {"name": "Monday Night", "temperature": 28, "temperatureUnit": "F", "isDaytime": false},
            {"name": "Tuesday", "temperature": 50, "temperatureUnit": "F", "isDaytime": true},
            {"name": "Wednesday", "temperature": 52, "temperatureUnit": "F", "isDaytime": true},
        ]}});
        let f = parse_forecast(&data, now());
        let lows: Vec<_> = f.periods.iter().map(|p| p.temperature_low).collect();
        assert_eq!(lows, [None, Some(28.0), None, None, None]);
        let monday = &f.periods[1];
        assert_eq!(monday.precipitation_probability, Some(40.0));
        assert_eq!(monday.detailed_forecast.as_deref(), Some("Sunny."));
        assert_eq!(monday.wind_speed.as_deref(), Some("5 to 10 mph"));
        assert_eq!(monday.wind_speed_mph, Some(10.0));
        assert_eq!(f.generated_at, Some(now()));
        assert!(
            parse_forecast(&json!({"properties": {"periods": []}}), now())
                .periods
                .is_empty()
        );
    }

    #[test]
    fn forecast_reads_quantitative_values() {
        let data = json!({"properties": {"periods": [{
            "name": "Today", "isDaytime": true,
            "temperature": {"unitCode": "wmoUnit:degC", "value": 10},
            "windSpeed": {"unitCode": "wmoUnit:km_h-1", "minValue": 10, "maxValue": 20},
            "startTime": "2026-01-20T06:00:00-05:00", "endTime": "bad",
        }]}});
        let p = &parse_forecast(&data, now()).periods[0];
        assert_eq!(p.temperature, Some(50.0));
        assert_eq!(p.temperature_unit, "F");
        assert_eq!(p.wind_speed.as_deref(), Some("12 mph (20 km/h)"));
        assert_eq!(
            p.start_time.unwrap().to_rfc3339(),
            "2026-01-20T06:00:00-05:00"
        );
        assert_eq!(p.end_time, None);
    }

    // tests/test_nws_alerts.py
    #[test]
    fn alerts_keep_every_message_type_and_dedupe_ids() {
        let data = json!({"features": [
            {"id": "a", "properties": {"messageType": "Alert", "event": "Flash Flood Warning"}},
            {"id": "b", "properties": {"messageType": "Update", "event": "Severe Thunderstorm Warning"}},
            {"id": "c", "properties": {"messageType": "Cancel", "event": "Heat Advisory"}},
            {"id": "a", "properties": {"messageType": "Alert", "event": "Duplicate"}},
            {"properties": {"event": "No id"}},
            {"properties": {"event": "No id again"}},
        ]});
        let alerts = parse_alerts(&data).unwrap().alerts;
        let events: Vec<_> = alerts.iter().map(|a| a.event.clone().unwrap()).collect();
        assert_eq!(
            events,
            [
                "Flash Flood Warning",
                "Severe Thunderstorm Warning",
                "Heat Advisory",
                "No id",
                "No id again"
            ]
        );
        assert_eq!(alerts[0].title, "Weather Alert");
        assert_eq!(alerts[0].severity, "Unknown");
        assert_eq!(alerts[0].source.as_deref(), Some("NWS"));
        assert!(parse_alerts(&json!({})).unwrap().alerts.is_empty());
    }

    #[test]
    fn alert_ids_references_areas_zones_and_codes() {
        let data = json!({"features": [
            {"properties": {"identifier": "identifier-based-id"}},
            {"properties": {"@id": "at-id-based-id"}},
            {"properties": {
                "id": "urn:oid:2.49.0.1.840.0.123",
                "references": [{"identifier": "ref-A"}, {"@id": "ref-B"}, {"id": "ref-C"}, "junk"],
                "areaDesc": "County A;County B; County C ",
                "affectedZones": ["https://api.weather.gov/zones/county/TXC121",
                                  "https://api.weather.gov/zones/forecast/TXZ119", 5, ""],
                "geocode": {"SAME": ["048121", 48122, 1.5, " "]},
                "eventCode": {"SAME": ["TOR", " ", 7], "NationalWeatherService": ["TOW"]},
                "onset": "2026-01-24T12:00:00Z",
                "expires": "2026-01-24T18:00:00-05:00",
            }},
            {"id": "bad-same", "properties": {"geocode": {"SAME": "048121"}}},
        ]});
        let alerts = parse_alerts(&data).unwrap().alerts;
        assert_eq!(alerts[0].id.as_deref(), Some("identifier-based-id"));
        assert_eq!(alerts[1].id.as_deref(), Some("at-id-based-id"));
        let a = &alerts[2];
        assert_eq!(a.id, None, "properties.id is not an alert id source");
        assert_eq!(a.references, ["ref-A", "ref-B", "ref-C"]);
        assert_eq!(a.areas, ["County A", "County B", "County C"]);
        assert_eq!(a.affected_zones, ["TXC121", "TXZ119"]);
        assert_eq!(a.same_codes, ["048121", "48122"]);
        assert_eq!(a.same_event_codes, ["TOR"]);
        assert_eq!(a.onset.unwrap().to_rfc3339(), "2026-01-24T12:00:00+00:00");
        assert_eq!(a.expires.unwrap().to_rfc3339(), "2026-01-24T18:00:00-05:00");
        assert!(alerts[3].same_codes.is_empty());
    }

    #[test]
    fn alert_with_non_string_time_is_malformed() {
        let data = json!({"features": [{"properties": {"onset": 5}}]});
        assert!(parse_alerts(&data).is_err());
    }

    #[test]
    fn hourly_converts_to_location_timezone() {
        let data = json!({"properties": {"periods": [
            {"startTime": "2026-01-20T18:00:00+00:00", "endTime": "2026-01-20T19:00:00+00:00",
             "temperature": 40, "temperatureUnit": "F", "windSpeed": "10 mph",
             "probabilityOfPrecipitation": {"value": 20}},
            {"temperature": 41},
        ]}});
        let mut loc = Location::new("NYC", 40.7, -74.0);
        loc.timezone = Some("America/New_York".into());
        let h = parse_hourly_forecast(&data, Some(&loc), now()).unwrap();
        assert_eq!(
            h.periods[0].start_time.to_rfc3339(),
            "2026-01-20T13:00:00-05:00"
        );
        assert_eq!(h.periods[0].wind_speed_mph, Some(10.0));
        assert_eq!(h.periods[0].precipitation_probability, Some(20.0));
        assert_eq!(h.periods[1].start_time, now());
        loc.timezone = Some("Not/AZone".into());
        let h = parse_hourly_forecast(&data, Some(&loc), now()).unwrap();
        assert_eq!(
            h.periods[0].start_time.to_rfc3339(),
            "2026-01-20T18:00:00+00:00"
        );
    }

    #[test]
    fn gridpoint_pressure_units_and_nearest_time() {
        let data = json!({"properties": {"pressure": {"values": [
            {"validTime": "2026-01-20T18:00:00+00:00/PT1H", "value": 30.1},
            {"validTime": "2026-01-20T19:00:00+00:00/PT1H", "value": 1012},
            {"validTime": "2026-01-20T20:00:00+00:00/PT1H", "value": 101200, "uom": "wmoUnit:Pa"},
            {"validTime": "bad", "value": 1},
            {"validTime": "2026-01-20T21:00:00+00:00/PT1H", "value": null},
        ]}}});
        let pressure = parse_gridpoint_pressure(&data);
        assert_eq!(pressure.len(), 3);
        assert_eq!(pressure[0].1, (Some(30.1), Some(30.1 * 33.8639)));
        assert_eq!(
            pressure[1].1,
            (Some(1012.0 * 0.0295299830714), Some(1012.0))
        );
        assert_eq!(pressure[2].1, (Some(101200.0 * 0.0002953), Some(1012.0)));

        let t = |s: &str| DateTime::parse_from_rfc3339(s).unwrap();
        let mut keep = HourlyForecastPeriod::new(t("2026-01-20T18:00:00+00:00"));
        keep.pressure_mb = Some(999.0);
        let hourly = HourlyForecast {
            periods: vec![
                keep,
                HourlyForecastPeriod::new(t("2026-01-20T14:10:00-05:00")),
                HourlyForecastPeriod::new(t("2026-01-20T23:00:00+00:00")),
            ],
            ..Default::default()
        };
        let out = apply_gridpoint_pressure(hourly, &pressure);
        assert_eq!(out.periods[0].pressure_in, None);
        assert_eq!(out.periods[1].pressure_mb, Some(1012.0));
        assert_eq!(out.periods[2].pressure_mb, None, "3h away is too far");
    }
}
