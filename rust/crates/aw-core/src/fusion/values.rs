//! Current-condition value helpers for data fusion.
//! Port of `accessiweather/weather_client_fusion_values.py`.

use std::collections::BTreeMap;

use serde_json::{Map, Value};

use crate::model::{CurrentConditions, DataConflict, SourceAttribution, SourceData};
use crate::thermal_comfort::{sanitize_thermal_comfort_readings, ThermalComfortInput};
use crate::units::{c_to_f, f_to_c};

pub const KM_PER_MILE: f64 = 1.609344;
pub const MB_PER_INHG: f64 = 33.8639;
const MM_PER_INCH: f64 = 25.4;
const CM_PER_INCH: f64 = 2.54;
const METERS_PER_FOOT: f64 = 0.3048;

/// One semantic reading expressed as `(field name, value)` pairs, in the
/// order Python's builder dicts list them.
pub type GroupValues = Vec<(&'static str, Option<f64>)>;

/// `build_value_pair`: fill the missing Fahrenheit/Celsius half.
pub fn value_pair(
    value_f: Option<f64>,
    value_c: Option<f64>,
    f_name: &'static str,
    c_name: &'static str,
) -> GroupValues {
    let f = value_f.or(value_c.map(c_to_f));
    let c = value_c.or(f.map(f_to_c));
    vec![(f_name, f), (c_name, c)]
}

/// `build_speed_pair`: fill the missing mph/kph half.
pub fn speed_pair(
    mph: Option<f64>,
    kph: Option<f64>,
    mph_name: &'static str,
    kph_name: &'static str,
) -> GroupValues {
    let mph = mph.or(kph.map(|k| k / KM_PER_MILE));
    let kph = kph.or(mph.map(|m| m * KM_PER_MILE));
    vec![(mph_name, mph), (kph_name, kph)]
}

/// Fill the missing half of a pair related by `a = b / factor`.
fn scaled_pair(
    a: Option<f64>,
    b: Option<f64>,
    factor: f64,
    a_name: &'static str,
    b_name: &'static str,
) -> GroupValues {
    let a = a.or(b.map(|b| b / factor));
    let b = b.or(a.map(|a| a * factor));
    vec![(a_name, a), (b_name, b)]
}

pub fn temperature_values(c: &CurrentConditions) -> GroupValues {
    let pair = value_pair(
        c.temperature_f,
        c.temperature_c,
        "temperature_f",
        "temperature_c",
    );
    let base = c.temperature.or(pair[0].1).or(pair[1].1);
    let mut out = vec![("temperature", base)];
    out.extend(pair);
    out
}

pub fn dewpoint_values(c: &CurrentConditions) -> GroupValues {
    value_pair(c.dewpoint_f, c.dewpoint_c, "dewpoint_f", "dewpoint_c")
}

pub fn feels_like_values(c: &CurrentConditions) -> GroupValues {
    value_pair(
        c.feels_like_f,
        c.feels_like_c,
        "feels_like_f",
        "feels_like_c",
    )
}

pub fn wind_chill_values(c: &CurrentConditions) -> GroupValues {
    value_pair(
        c.wind_chill_f,
        c.wind_chill_c,
        "wind_chill_f",
        "wind_chill_c",
    )
}

pub fn heat_index_values(c: &CurrentConditions) -> GroupValues {
    value_pair(
        c.heat_index_f,
        c.heat_index_c,
        "heat_index_f",
        "heat_index_c",
    )
}

pub fn speed_values(c: &CurrentConditions) -> GroupValues {
    let pair = speed_pair(
        c.wind_speed_mph,
        c.wind_speed_kph,
        "wind_speed_mph",
        "wind_speed_kph",
    );
    let base = c.wind_speed.or(pair[0].1).or(pair[1].1);
    let mut out = vec![("wind_speed", base)];
    out.extend(pair);
    out
}

pub fn wind_gust_values(c: &CurrentConditions) -> GroupValues {
    speed_pair(
        c.wind_gust_mph,
        c.wind_gust_kph,
        "wind_gust_mph",
        "wind_gust_kph",
    )
}

pub fn pressure_values(c: &CurrentConditions) -> GroupValues {
    let pair = scaled_pair(
        c.pressure_in,
        c.pressure_mb,
        MB_PER_INHG,
        "pressure_in",
        "pressure_mb",
    );
    let base = c.pressure.or(pair[0].1).or(pair[1].1);
    let mut out = vec![("pressure", base)];
    out.extend(pair);
    out
}

pub fn precipitation_values(c: &CurrentConditions) -> GroupValues {
    scaled_pair(
        c.precipitation_in,
        c.precipitation_mm,
        MM_PER_INCH,
        "precipitation_in",
        "precipitation_mm",
    )
}

pub fn snow_depth_values(c: &CurrentConditions) -> GroupValues {
    scaled_pair(
        c.snow_depth_in,
        c.snow_depth_cm,
        CM_PER_INCH,
        "snow_depth_in",
        "snow_depth_cm",
    )
}

pub fn freezing_level_values(c: &CurrentConditions) -> GroupValues {
    scaled_pair(
        c.freezing_level_ft,
        c.freezing_level_m,
        METERS_PER_FOOT,
        "freezing_level_ft",
        "freezing_level_m",
    )
}

fn number(merged: &Map<String, Value>, field: &str) -> Option<f64> {
    merged.get(field).and_then(Value::as_f64)
}

fn remove_field(merged: &mut Map<String, Value>, attribution: &mut SourceAttribution, field: &str) {
    merged.shift_remove(field);
    attribution.field_sources.remove(field);
}

/// Drop the fused gust when it is lower than the fused sustained wind.
pub fn discard_gust_if_below_wind_speed(
    merged: &mut Map<String, Value>,
    attribution: &mut SourceAttribution,
) {
    if let (Some(speed), Some(gust)) = (
        number(merged, "wind_speed_mph"),
        number(merged, "wind_gust_mph"),
    ) {
        if gust < speed {
            remove_field(merged, attribution, "wind_gust_mph");
            remove_field(merged, attribution, "wind_gust_kph");
        }
    }
}

/// Drop apparent-temperature readings that no longer fit after fusion.
pub fn sanitize_thermal_comfort_values(
    merged: &mut Map<String, Value>,
    attribution: &mut SourceAttribution,
) {
    let comfort = sanitize_thermal_comfort_readings(ThermalComfortInput {
        temperature_f: number(merged, "temperature_f"),
        temperature_c: number(merged, "temperature_c"),
        humidity: number(merged, "humidity"),
        feels_like_f: number(merged, "feels_like_f"),
        feels_like_c: number(merged, "feels_like_c"),
        wind_chill_f: number(merged, "wind_chill_f"),
        wind_chill_c: number(merged, "wind_chill_c"),
        heat_index_f: number(merged, "heat_index_f"),
        heat_index_c: number(merged, "heat_index_c"),
    });
    for (field, value) in [
        ("feels_like_f", comfort.feels_like_f),
        ("feels_like_c", comfort.feels_like_c),
        ("wind_chill_f", comfort.wind_chill_f),
        ("wind_chill_c", comfort.wind_chill_c),
        ("heat_index_f", comfort.heat_index_f),
        ("heat_index_c", comfort.heat_index_c),
    ] {
        match value {
            None => remove_field(merged, attribution, field),
            Some(v) => {
                merged.insert(field.to_string(), Value::from(v));
                if let Some(source) = thermal_field_source(field, attribution) {
                    attribution.field_sources.insert(field.to_string(), source);
                }
            }
        }
    }
}

fn thermal_field_source(field: &str, attribution: &SourceAttribution) -> Option<String> {
    if let Some(source) = attribution.field_sources.get(field) {
        return Some(source.clone());
    }
    let fallbacks: &[&str] = match field {
        "feels_like_f" => &["feels_like_c", "wind_chill_f", "heat_index_f"],
        "feels_like_c" => &["feels_like_f", "wind_chill_c", "heat_index_c"],
        "wind_chill_f" => &["wind_chill_c", "feels_like_f", "feels_like_c"],
        "wind_chill_c" => &["wind_chill_f", "feels_like_c", "feels_like_f"],
        "heat_index_f" => &["heat_index_c", "feels_like_f", "feels_like_c"],
        "heat_index_c" => &["heat_index_f", "feels_like_c", "feels_like_f"],
        _ => &[],
    };
    fallbacks
        .iter()
        .find_map(|f| attribution.field_sources.get(*f).cloned())
}

/// Record a conflict when the temperature spread across sources exceeds the
/// threshold, and force the highest-priority source's value for that field.
pub fn check_temperature_conflicts(
    sources: &[&SourceData],
    merged: &mut Map<String, Value>,
    attribution: &mut SourceAttribution,
    threshold: f64,
    priority_for: impl Fn(&str) -> Vec<String>,
) {
    for field in ["temperature", "temperature_f", "temperature_c"] {
        let mut values: BTreeMap<String, f64> = BTreeMap::new();
        for source in sources {
            let Some(current) = &source.current else {
                continue;
            };
            let value = match field {
                "temperature" => current.temperature,
                "temperature_f" => current.temperature_f,
                _ => current.temperature_c,
            };
            if let Some(v) = value {
                values.insert(source.source.clone(), v);
            }
        }
        if values.len() < 2 {
            continue;
        }
        let max = values.values().copied().fold(f64::NEG_INFINITY, f64::max);
        let min = values.values().copied().fold(f64::INFINITY, f64::min);
        if max - min <= threshold {
            continue;
        }
        let selected = priority_for(field)
            .into_iter()
            .find_map(|name| values.get(&name).map(|v| (name, *v)));
        if let Some((selected_source, selected_value)) = selected {
            attribution.conflicts.push(DataConflict {
                field_name: field.to_string(),
                values: values
                    .iter()
                    .map(|(k, v)| (k.clone(), Value::from(*v)))
                    .collect(),
                selected_source: selected_source.clone(),
                selected_value: Value::from(selected_value),
            });
            merged.insert(field.to_string(), Value::from(selected_value));
            attribution
                .field_sources
                .insert(field.to_string(), selected_source);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `pytest.approx` default: relative tolerance 1e-6.
    fn close(a: Option<f64>, b: f64) {
        assert!((a.unwrap() - b).abs() <= 1e-6 * b.abs(), "{a:?} != {b}");
    }

    #[test]
    fn builders_fill_missing_units_and_base_values() {
        let t = temperature_values(&CurrentConditions {
            temperature_c: Some(10.0),
            ..Default::default()
        });
        close(t[0].1, 50.0);
        close(t[1].1, 50.0);
        let w = speed_values(&CurrentConditions {
            wind_speed_mph: Some(12.0),
            ..Default::default()
        });
        close(w[2].1, 19.312128);
        let g = wind_gust_values(&CurrentConditions {
            wind_gust_kph: Some(40.0),
            ..Default::default()
        });
        close(g[0].1, 24.8548476895);
        let p = pressure_values(&CurrentConditions {
            pressure_mb: Some(1013.25),
            ..Default::default()
        });
        close(p[0].1, 29.9212524019);
        let f = freezing_level_values(&CurrentConditions {
            freezing_level_m: Some(304.8),
            ..Default::default()
        });
        close(f[0].1, 1000.0);
        let s = snow_depth_values(&CurrentConditions {
            snow_depth_in: Some(4.0),
            ..Default::default()
        });
        close(s[1].1, 10.16);
        let r = precipitation_values(&CurrentConditions {
            precipitation_mm: Some(12.7),
            ..Default::default()
        });
        close(r[0].1, 0.5);
    }
}
