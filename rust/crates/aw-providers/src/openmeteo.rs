//! Open-Meteo forecast client (api.open-meteo.com).

use aw_core::units::wind_direction_to_cardinal;
use aw_core::weather::{
    CurrentConditions, Forecast, ForecastPeriod, HourlyForecast, HourlyForecastPeriod,
};
use aw_core::Location;
use chrono::{DateTime, NaiveDateTime, TimeZone, Utc};
use serde_json::Value;

use crate::http::{HttpClient, HttpError};

pub const BASE_URL: &str = "https://api.open-meteo.com/v1";
pub const SOURCE: &str = "openmeteo";

const CURRENT_FIELDS: &str = "temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,is_day,precipitation,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index,snowfall,snow_depth,visibility";
const DAILY_FIELDS: &str = "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,sunrise,sunset,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant,uv_index_max";
const HOURLY_FIELDS: &str = "temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl";

pub fn weather_code_description(code: i64) -> &'static str {
    match code {
        0 => "Clear sky",
        1 => "Mainly clear",
        2 => "Partly cloudy",
        3 => "Overcast",
        45 => "Fog",
        48 => "Depositing rime fog",
        51 => "Light drizzle",
        53 => "Moderate drizzle",
        55 => "Dense drizzle",
        56 => "Light freezing drizzle",
        57 => "Dense freezing drizzle",
        61 => "Slight rain",
        63 => "Moderate rain",
        65 => "Heavy rain",
        66 => "Light freezing rain",
        67 => "Heavy freezing rain",
        71 => "Slight snow fall",
        73 => "Moderate snow fall",
        75 => "Heavy snow fall",
        77 => "Snow grains",
        80 => "Slight rain showers",
        81 => "Moderate rain showers",
        82 => "Violent rain showers",
        85 => "Slight snow showers",
        86 => "Heavy snow showers",
        95 => "Thunderstorm",
        96 => "Thunderstorm with slight hail",
        99 => "Thunderstorm with heavy hail",
        _ => "Unknown conditions",
    }
}

pub struct OpenMeteoClient<'a> {
    http: &'a dyn HttpClient,
    base: String,
}

fn f(v: &Value, key: &str) -> Option<f64> {
    v.get(key).and_then(Value::as_f64)
}

fn arr_f(v: &Value, key: &str, i: usize) -> Option<f64> {
    v.get(key)?.as_array()?.get(i)?.as_f64()
}

fn arr_s<'v>(v: &'v Value, key: &str, i: usize) -> Option<&'v str> {
    v.get(key)?.as_array()?.get(i)?.as_str()
}

/// Open-Meteo returns local times without an offset plus `utc_offset_seconds`.
fn local_to_utc(text: &str, offset_seconds: i64) -> Option<DateTime<Utc>> {
    let naive = NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M")
        .or_else(|_| NaiveDateTime::parse_from_str(text, "%Y-%m-%dT%H:%M:%S"))
        .or_else(|_| {
            chrono::NaiveDate::parse_from_str(text, "%Y-%m-%d")
                .map(|d| d.and_hms_opt(0, 0, 0).unwrap())
        })
        .ok()?;
    let offset = chrono::FixedOffset::east_opt(offset_seconds as i32)?;
    Some(
        offset
            .from_local_datetime(&naive)
            .single()?
            .with_timezone(&Utc),
    )
}

fn day_name(dt: DateTime<Utc>, offset_seconds: i64) -> String {
    let offset = chrono::FixedOffset::east_opt(offset_seconds as i32)
        .unwrap_or_else(|| chrono::FixedOffset::east_opt(0).expect("zero offset"));
    let local = dt.with_timezone(&offset);
    let today = Utc::now().with_timezone(&offset).date_naive();
    let date = local.date_naive();
    if date == today {
        "Today".to_string()
    } else if date == today.succ_opt().unwrap_or(today) {
        "Tomorrow".to_string()
    } else {
        format!("{}", local.format("%A"))
    }
}

impl<'a> OpenMeteoClient<'a> {
    pub fn new(http: &'a dyn HttpClient) -> Self {
        Self {
            http,
            base: BASE_URL.to_string(),
        }
    }

    pub fn with_base(mut self, base: &str) -> Self {
        self.base = base.trim_end_matches('/').to_string();
        self
    }

    /// One request for current + daily + hourly data, US units (the
    /// presenter converts for display).
    pub fn fetch(&self, location: &Location, days: u32, hours: usize) -> Result<Bundle, HttpError> {
        let forecast_days = days.clamp(1, 16);
        let url = format!(
            "{}/forecast?latitude={:.4}&longitude={:.4}&current={}&daily={}&hourly={}&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&forecast_days={}",
            self.base,
            location.latitude,
            location.longitude,
            CURRENT_FIELDS,
            DAILY_FIELDS,
            HOURLY_FIELDS,
            forecast_days
        );
        let v = self.http.get_json(&url)?;
        Ok(parse_bundle(&v, hours))
    }
}

#[derive(Debug, Default)]
pub struct Bundle {
    pub current: Option<CurrentConditions>,
    pub forecast: Option<Forecast>,
    pub hourly: Option<HourlyForecast>,
}

pub fn parse_bundle(v: &Value, hours: usize) -> Bundle {
    let offset = v
        .get("utc_offset_seconds")
        .and_then(Value::as_i64)
        .unwrap_or(0);
    Bundle {
        current: v
            .get("current")
            .map(|c| parse_current(c, v.get("daily"), offset)),
        forecast: v.get("daily").map(|d| parse_daily(d, offset)),
        hourly: v
            .get("hourly")
            .map(|h| parse_hourly(h, offset, hours.max(1))),
    }
}

fn parse_current(c: &Value, daily: Option<&Value>, offset: i64) -> CurrentConditions {
    let wind_dir = f(c, "wind_direction_10m");
    let mut cur = CurrentConditions {
        temperature_f: f(c, "temperature_2m"),
        condition: c
            .get("weather_code")
            .and_then(Value::as_i64)
            .map(|code| weather_code_description(code).to_string()),
        humidity: f(c, "relative_humidity_2m"),
        dewpoint_f: f(c, "dew_point_2m"),
        wind_speed_mph: f(c, "wind_speed_10m"),
        wind_direction: wind_dir.map(|d| wind_direction_to_cardinal(Some(d))),
        wind_gust_mph: f(c, "wind_gusts_10m"),
        pressure_mb: f(c, "pressure_msl").or_else(|| f(c, "surface_pressure")),
        feels_like_f: f(c, "apparent_temperature"),
        visibility_miles: f(c, "visibility").map(|ft| ft / 5280.0),
        uv_index: f(c, "uv_index"),
        cloud_cover: f(c, "cloud_cover"),
        precipitation_in: f(c, "precipitation"),
        snow_depth_in: f(c, "snow_depth").map(|m| m * 39.3701),
        observed_at: c
            .get("time")
            .and_then(Value::as_str)
            .and_then(|t| local_to_utc(t, offset)),
        sunrise_time: daily
            .and_then(|d| arr_s(d, "sunrise", 0))
            .and_then(|t| local_to_utc(t, offset)),
        sunset_time: daily
            .and_then(|d| arr_s(d, "sunset", 0))
            .and_then(|t| local_to_utc(t, offset)),
        source: Some(SOURCE.into()),
        ..Default::default()
    };
    cur.fill_unit_pairs();
    cur
}

fn parse_daily(d: &Value, offset: i64) -> Forecast {
    let n = d.get("time").and_then(Value::as_array).map_or(0, Vec::len);
    let mut periods = Vec::with_capacity(n);
    for i in 0..n {
        let Some(start) = arr_s(d, "time", i).and_then(|t| local_to_utc(t, offset)) else {
            continue;
        };
        let code = d
            .get("weather_code")
            .and_then(Value::as_array)
            .and_then(|a| a.get(i))
            .and_then(Value::as_i64);
        let wind_dir = arr_f(d, "wind_direction_10m_dominant", i);
        let wind_mph = arr_f(d, "wind_speed_10m_max", i);
        periods.push(ForecastPeriod {
            name: day_name(start, offset),
            temperature: arr_f(d, "temperature_2m_max", i),
            temperature_low: arr_f(d, "temperature_2m_min", i),
            temperature_unit: "F".into(),
            short_forecast: code.map(|c| weather_code_description(c).to_string()),
            detailed_forecast: None,
            wind_speed: wind_mph.map(|w| format!("{} mph", w.round())),
            wind_speed_mph: wind_mph,
            wind_direction: wind_dir.map(|deg| wind_direction_to_cardinal(Some(deg))),
            start_time: Some(start),
            end_time: start.checked_add_signed(chrono::Duration::days(1)),
            precipitation_probability: arr_f(d, "precipitation_probability_max", i),
            precipitation_amount_in: arr_f(d, "precipitation_sum", i),
            uv_index_max: arr_f(d, "uv_index_max", i),
            is_daytime: Some(true),
        });
    }
    Forecast {
        periods,
        generated_at: Some(Utc::now()),
        source: Some(SOURCE.into()),
    }
}

fn parse_hourly(h: &Value, offset: i64, limit: usize) -> HourlyForecast {
    let n = h.get("time").and_then(Value::as_array).map_or(0, Vec::len);
    let now = Utc::now() - chrono::Duration::hours(1);
    let mut periods = Vec::new();
    for i in 0..n {
        let Some(start) = arr_s(h, "time", i).and_then(|t| local_to_utc(t, offset)) else {
            continue;
        };
        if start < now {
            continue;
        }
        let code = h
            .get("weather_code")
            .and_then(Value::as_array)
            .and_then(|a| a.get(i))
            .and_then(Value::as_i64);
        let wind_mph = arr_f(h, "wind_speed_10m", i);
        periods.push(HourlyForecastPeriod {
            start_time: start,
            temperature: arr_f(h, "temperature_2m", i),
            temperature_unit: "F".into(),
            short_forecast: code.map(|c| weather_code_description(c).to_string()),
            wind_speed: wind_mph.map(|w| format!("{} mph", w.round())),
            wind_speed_mph: wind_mph,
            wind_direction: arr_f(h, "wind_direction_10m", i)
                .map(|deg| wind_direction_to_cardinal(Some(deg))),
            humidity: arr_f(h, "relative_humidity_2m", i),
            precipitation_probability: arr_f(h, "precipitation_probability", i),
            pressure_mb: arr_f(h, "pressure_msl", i),
            pressure_in: arr_f(h, "pressure_msl", i).map(|mb| mb / 33.8639),
        });
        if periods.len() >= limit.max(48) {
            break;
        }
    }
    HourlyForecast {
        periods,
        generated_at: Some(Utc::now()),
        source: Some(SOURCE.into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parses_current_and_daily() {
        let v = json!({
            "utc_offset_seconds": -18000,
            "current": {"time": "2026-01-01T12:00", "temperature_2m": 50.0,
                "relative_humidity_2m": 40, "weather_code": 3, "wind_speed_10m": 8.0,
                "wind_direction_10m": 180, "pressure_msl": 1013.0, "visibility": 52800},
            "daily": {"time": ["2026-01-01", "2026-01-02"], "weather_code": [0, 61],
                "temperature_2m_max": [55.0, 48.0], "temperature_2m_min": [35.0, 30.0],
                "sunrise": ["2026-01-01T07:20", "2026-01-02T07:20"],
                "sunset": ["2026-01-01T16:50", "2026-01-02T16:50"],
                "precipitation_probability_max": [0, 80]},
            "hourly": {"time": ["2099-01-01T12:00"], "temperature_2m": [50.0]}
        });
        let b = parse_bundle(&v, 6);
        let c = b.current.unwrap();
        assert_eq!(c.condition.as_deref(), Some("Overcast"));
        assert_eq!(c.wind_direction.as_deref(), Some("S"));
        assert!((c.visibility_miles.unwrap() - 10.0).abs() < 0.01);
        assert!((c.temperature_c.unwrap() - 10.0).abs() < 0.01);
        assert!(c.sunrise_time.is_some());
        let fc = b.forecast.unwrap();
        assert_eq!(fc.periods.len(), 2);
        assert_eq!(fc.periods[1].short_forecast.as_deref(), Some("Slight rain"));
        assert_eq!(fc.periods[1].precipitation_probability, Some(80.0));
        assert_eq!(b.hourly.unwrap().periods.len(), 1);
    }

    #[test]
    fn local_time_applies_offset() {
        let t = local_to_utc("2026-01-01T12:00", -18000).unwrap();
        assert_eq!(t.to_rfc3339(), "2026-01-01T17:00:00+00:00");
    }
}
