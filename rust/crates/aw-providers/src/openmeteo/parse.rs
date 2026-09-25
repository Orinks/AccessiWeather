//! Open-Meteo daily and hourly parsing, ported from the parse functions in
//! `accessiweather.weather_client_openmeteo`.

use aw_core::model::{Forecast, ForecastPeriod, HourlyForecast, HourlyForecastPeriod, Timestamp};
use aw_core::provider_normalization::{classify_apparent_temperature, normalize_dewpoint_pair};
use aw_core::py;
use aw_core::weather_client_parsers::{
    convert_wind_speed_to_mph_and_kph, degrees_to_cardinal, format_date_name, normalize_pressure,
    weather_code_to_description,
};
use serde_json::Value;

use super::current::{get, parse_iso_datetime, unit, utc_offset};
use super::units::{
    normalize_height_to_feet, normalize_snow_depth_to_inches_and_cm,
    normalize_visibility_to_miles_and_km,
};

/// A named array from a `daily`/`hourly` block (missing → empty).
fn series<'a>(block: &'a Value, key: &str) -> &'a [Value] {
    get(block, key)
        .and_then(Value::as_array)
        .map_or(&[], Vec::as_slice)
}

fn at(values: &[Value], i: usize) -> Option<&Value> {
    values.get(i).filter(|v| !v.is_null())
}

fn num(values: &[Value], i: usize) -> Option<f64> {
    py::as_float(at(values, i))
}

/// `f"{value:.1f}"` without trailing zeros, plus " mph".
pub fn format_wind_speed_mph(value: Option<f64>) -> Option<String> {
    let text = format!("{:.1}", value?);
    Some(format!(
        "{} mph",
        text.trim_end_matches('0').trim_end_matches('.')
    ))
}

/// Daily forecast; `now` (local) stands in for Python's `datetime.now()`.
pub fn parse_openmeteo_forecast(data: &Value, now: Timestamp) -> Forecast {
    let empty = Value::Null;
    let daily = get(data, "daily").unwrap_or(&empty);
    let units = get(data, "daily_units").unwrap_or(&empty);
    let offset = utc_offset(data);

    let dates = series(daily, "time");
    let max_temps = series(daily, "temperature_2m_max");
    let min_temps = series(daily, "temperature_2m_min");
    let weather_codes = series(daily, "weather_code");
    let wind_speeds = series(daily, "wind_speed_10m_max");
    let wind_directions = series(daily, "wind_direction_10m_dominant");
    let precip_probs = series(daily, "precipitation_probability_max");
    let snowfall_sums = series(daily, "snowfall_sum");
    let uv_indices = series(daily, "uv_index_max");

    let mut periods = Vec::new();
    for (i, date) in dates.iter().enumerate() {
        if i >= max_temps.len() || i >= weather_codes.len() {
            continue;
        }
        let date = py::value_str(date);
        let (wind_speed_mph, _) = convert_wind_speed_to_mph_and_kph(
            num(wind_speeds, i),
            Some(unit(units, "wind_speed_10m_max").unwrap_or("mph")),
        );
        let start_time = parse_iso_datetime(Some(&format!("{date}T12:00:00")), offset)
            .unwrap_or_else(|| now.to_utc().fixed_offset());
        periods.push(ForecastPeriod {
            name: format_date_name(&date, i),
            temperature: num(max_temps, i),
            temperature_low: num(min_temps, i),
            temperature_unit: "F".into(),
            short_forecast: weather_code_to_description(at(weather_codes, i)),
            wind_speed: format_wind_speed_mph(wind_speed_mph),
            wind_speed_mph,
            wind_direction: degrees_to_cardinal(num(wind_directions, i)),
            start_time: Some(start_time),
            precipitation_probability: num(precip_probs, i),
            snowfall: num(snowfall_sums, i),
            uv_index: num(uv_indices, i),
            ..Default::default()
        });
    }
    Forecast {
        periods,
        generated_at: Some(now),
        summary: None,
    }
}

/// Hourly forecast; `now` (local) stands in for Python's `datetime.now()`.
pub fn parse_openmeteo_hourly_forecast(data: &Value, now: Timestamp) -> HourlyForecast {
    let empty = Value::Null;
    let hourly = get(data, "hourly").unwrap_or(&empty);
    let units = get(data, "hourly_units").unwrap_or(&empty);
    let offset = utc_offset(data);

    let times = series(hourly, "time");
    let temperatures = series(hourly, "temperature_2m");
    let humidities = series(hourly, "relative_humidity_2m");
    let dew_points = series(hourly, "dew_point_2m");
    let weather_codes = series(hourly, "weather_code");
    let wind_speeds = series(hourly, "wind_speed_10m");
    let wind_directions = series(hourly, "wind_direction_10m");
    let pressures = series(hourly, "pressure_msl");
    let precip_probs = series(hourly, "precipitation_probability");
    let snowfalls = series(hourly, "snowfall");
    let uv_indices = series(hourly, "uv_index");
    let snow_depths = series(hourly, "snow_depth");
    let freezing_levels = series(hourly, "freezing_level_height");
    let visibilities = series(hourly, "visibility");
    let apparent_temps = series(hourly, "apparent_temperature");
    let dewpoint_unit =
        unit(units, "dew_point_2m").or(Some(unit(units, "temperature_2m").unwrap_or("°F")));

    let mut periods = Vec::with_capacity(times.len());
    for (i, time) in times.iter().enumerate() {
        let start_time = parse_iso_datetime(time.as_str(), offset).unwrap_or(now);
        let temperature = num(temperatures, i);
        let humidity = num(humidities, i);
        let (wind_speed_mph, _) = convert_wind_speed_to_mph_and_kph(
            num(wind_speeds, i),
            Some(unit(units, "wind_speed_10m").unwrap_or("mph")),
        );
        let (pressure_in, pressure_mb) = normalize_pressure(
            num(pressures, i),
            Some(unit(units, "pressure_msl").unwrap_or("hPa")),
        );
        let (snow_depth_in, _) =
            normalize_snow_depth_to_inches_and_cm(num(snow_depths, i), unit(units, "snow_depth"));
        let freezing_level_ft = normalize_height_to_feet(
            num(freezing_levels, i),
            unit(units, "freezing_level_height"),
        );
        let (visibility_miles, visibility_km) =
            normalize_visibility_to_miles_and_km(num(visibilities, i), unit(units, "visibility"));
        let apparent_temp = num(apparent_temps, i);
        let dewpoint =
            normalize_dewpoint_pair(num(dew_points, i), dewpoint_unit, temperature, humidity);
        let apparent = classify_apparent_temperature(temperature, apparent_temp, None);

        let mut period = HourlyForecastPeriod::new(start_time);
        period.temperature = temperature;
        period.short_forecast = weather_code_to_description(at(weather_codes, i));
        period.wind_speed = format_wind_speed_mph(wind_speed_mph);
        period.wind_direction = degrees_to_cardinal(num(wind_directions, i));
        period.humidity = humidity.map(|h| h as i64);
        period.dewpoint_f = dewpoint.fahrenheit;
        period.dewpoint_c = dewpoint.celsius;
        period.pressure_mb = pressure_mb;
        period.pressure_in = pressure_in;
        period.precipitation_probability = num(precip_probs, i);
        period.snowfall = num(snowfalls, i);
        period.uv_index = num(uv_indices, i);
        period.wind_speed_mph = wind_speed_mph;
        period.snow_depth = snow_depth_in;
        period.freezing_level_ft = freezing_level_ft;
        period.visibility_miles = visibility_miles;
        period.visibility_km = visibility_km;
        period.feels_like = apparent_temp;
        period.wind_chill_f = apparent.wind_chill_f;
        period.wind_chill_c = apparent.wind_chill_c;
        period.heat_index_f = apparent.heat_index_f;
        period.heat_index_c = apparent.heat_index_c;
        periods.push(period);
    }
    HourlyForecast {
        periods,
        generated_at: Some(now),
        summary: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn now() -> Timestamp {
        chrono::DateTime::parse_from_rfc3339("2025-01-15T12:30:00-05:00").unwrap()
    }

    #[test]
    fn wind_speed_text_trims_zeros() {
        assert_eq!(format_wind_speed_mph(Some(12.0)).as_deref(), Some("12 mph"));
        assert_eq!(
            format_wind_speed_mph(Some(12.34)).as_deref(),
            Some("12.3 mph")
        );
        assert_eq!(format_wind_speed_mph(Some(0.04)).as_deref(), Some("0 mph"));
        assert_eq!(format_wind_speed_mph(None), None);
    }

    #[test]
    fn forecast_periods_carry_start_low_and_numeric_wind() {
        let data = json!({
            "utc_offset_seconds": 3600,
            "daily": {"time": ["2025-06-01", "2025-06-02", "2025-06-03"],
                "temperature_2m_max": [70, 72, 74], "temperature_2m_min": [50, 52, 54],
                "weather_code": [0, 1, 2], "wind_speed_10m_max": [10.0, 12.5, null],
                "wind_direction_10m_dominant": [180, 270, 90]},
            "daily_units": {"wind_speed_10m_max": "km/h"}
        });
        let f = parse_openmeteo_forecast(&data, now());
        assert_eq!(f.periods.len(), 3);
        assert_eq!(f.periods[2].name, "Tuesday");
        assert_eq!(f.periods[0].temperature_low, Some(50.0));
        assert!((f.periods[0].wind_speed_mph.unwrap() - 6.21371).abs() < 1e-9);
        assert_eq!(f.periods[0].wind_speed.as_deref(), Some("6.2 mph"));
        assert_eq!(f.periods[2].wind_speed, None);
        assert_eq!(
            f.periods[0].start_time.unwrap().to_rfc3339(),
            "2025-06-01T12:00:00+01:00"
        );
    }

    #[test]
    fn hourly_calculates_dewpoint_when_missing() {
        let data = json!({
            "utc_offset_seconds": 0,
            "hourly": {"time": ["2025-01-15T12:00"], "temperature_2m": [70.0],
                "relative_humidity_2m": [50]},
        });
        let h = parse_openmeteo_hourly_forecast(&data, now());
        let p = &h.periods[0];
        assert!((p.dewpoint_f.unwrap() - 50.5).abs() < 0.1);
        assert_eq!(p.humidity, Some(50));
    }
}
