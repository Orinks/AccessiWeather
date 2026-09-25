//! Pirate Weather client (Dark Sky compatible JSON, api.pirateweather.net).

use aw_core::units::wind_direction_to_cardinal;
use aw_core::weather::{
    CurrentConditions, Forecast, ForecastPeriod, HourlyForecast, HourlyForecastPeriod,
};
use aw_core::Location;
use chrono::{DateTime, TimeZone, Utc};
use serde_json::Value;

use crate::http::{HttpClient, HttpError};
use crate::openmeteo::Bundle;

pub const BASE_URL: &str = "https://api.pirateweather.net";
pub const SOURCE: &str = "pirateweather";

pub struct PirateWeatherClient<'a> {
    http: &'a dyn HttpClient,
    base: String,
    api_key: String,
}

fn f(v: &Value, key: &str) -> Option<f64> {
    v.get(key).and_then(Value::as_f64)
}

fn s(v: &Value, key: &str) -> Option<String> {
    v.get(key).and_then(Value::as_str).map(str::to_string)
}

fn ts(v: &Value, key: &str) -> Option<DateTime<Utc>> {
    v.get(key)
        .and_then(Value::as_i64)
        .and_then(|t| Utc.timestamp_opt(t, 0).single())
}

impl<'a> PirateWeatherClient<'a> {
    pub fn new(http: &'a dyn HttpClient, api_key: &str) -> Self {
        Self {
            http,
            base: BASE_URL.into(),
            api_key: api_key.to_string(),
        }
    }

    pub fn with_base(mut self, base: &str) -> Self {
        self.base = base.trim_end_matches('/').to_string();
        self
    }

    pub fn fetch(&self, location: &Location) -> Result<Bundle, HttpError> {
        let url = format!(
            "{}/forecast/{}/{:.4},{:.4}?units=us&exclude=minutely",
            self.base, self.api_key, location.latitude, location.longitude
        );
        let v = self.http.get_json(&url)?;
        Ok(parse_bundle(&v))
    }
}

pub fn parse_bundle(v: &Value) -> Bundle {
    let current = v.get("currently").map(|c| {
        let deg = f(c, "windBearing");
        let mut cur = CurrentConditions {
            temperature_f: f(c, "temperature"),
            condition: s(c, "summary"),
            humidity: f(c, "humidity").map(|h| h * 100.0),
            dewpoint_f: f(c, "dewPoint"),
            wind_speed_mph: f(c, "windSpeed"),
            wind_direction: deg.map(|d| wind_direction_to_cardinal(Some(d))),
            wind_gust_mph: f(c, "windGust"),
            pressure_mb: f(c, "pressure"),
            feels_like_f: f(c, "apparentTemperature"),
            visibility_miles: f(c, "visibility"),
            uv_index: f(c, "uvIndex"),
            cloud_cover: f(c, "cloudCover").map(|c| c * 100.0),
            precipitation_in: f(c, "precipIntensity"),
            observed_at: ts(c, "time"),
            source: Some(SOURCE.into()),
            ..Default::default()
        };
        cur.fill_unit_pairs();
        cur
    });
    let forecast = v
        .get("daily")
        .and_then(|d| d.get("data"))
        .and_then(Value::as_array)
        .map(|days| Forecast {
            periods: days
                .iter()
                .enumerate()
                .map(|(i, d)| {
                    let start = ts(d, "time");
                    let deg = f(d, "windBearing");
                    ForecastPeriod {
                        name: match i {
                            0 => "Today".into(),
                            1 => "Tomorrow".into(),
                            _ => start
                                .map(|t| t.format("%A").to_string())
                                .unwrap_or_else(|| format!("Day {}", i + 1)),
                        },
                        temperature: f(d, "temperatureHigh").or_else(|| f(d, "temperatureMax")),
                        temperature_low: f(d, "temperatureLow").or_else(|| f(d, "temperatureMin")),
                        temperature_unit: "F".into(),
                        short_forecast: s(d, "summary"),
                        detailed_forecast: None,
                        wind_speed: f(d, "windSpeed").map(|w| format!("{} mph", w.round())),
                        wind_speed_mph: f(d, "windSpeed"),
                        wind_direction: deg.map(|d| wind_direction_to_cardinal(Some(d))),
                        start_time: start,
                        end_time: start
                            .and_then(|t| t.checked_add_signed(chrono::Duration::days(1))),
                        precipitation_probability: f(d, "precipProbability").map(|p| p * 100.0),
                        precipitation_amount_in: f(d, "precipAccumulation"),
                        uv_index_max: f(d, "uvIndex"),
                        is_daytime: Some(true),
                    }
                })
                .collect(),
            generated_at: Some(Utc::now()),
            source: Some(SOURCE.into()),
        });
    let hourly = v
        .get("hourly")
        .and_then(|h| h.get("data"))
        .and_then(Value::as_array)
        .map(|hours| HourlyForecast {
            periods: hours
                .iter()
                .filter_map(|h| {
                    let deg = f(h, "windBearing");
                    Some(HourlyForecastPeriod {
                        start_time: ts(h, "time")?,
                        temperature: f(h, "temperature"),
                        temperature_unit: "F".into(),
                        short_forecast: s(h, "summary"),
                        wind_speed: f(h, "windSpeed").map(|w| format!("{} mph", w.round())),
                        wind_speed_mph: f(h, "windSpeed"),
                        wind_direction: deg.map(|d| wind_direction_to_cardinal(Some(d))),
                        humidity: f(h, "humidity").map(|x| x * 100.0),
                        precipitation_probability: f(h, "precipProbability").map(|p| p * 100.0),
                        pressure_mb: f(h, "pressure"),
                        pressure_in: f(h, "pressure").map(|mb| mb / 33.8639),
                    })
                })
                .collect(),
            generated_at: Some(Utc::now()),
            source: Some(SOURCE.into()),
        });
    Bundle {
        current,
        forecast,
        hourly,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parses_dark_sky_shape() {
        let v = json!({
            "currently": {"time": 1700000000, "summary": "Clear", "temperature": 60.0,
                "humidity": 0.5, "windSpeed": 5.0, "windBearing": 90, "cloudCover": 0.1},
            "daily": {"data": [{"time": 1700000000, "summary": "Sunny", "temperatureHigh": 65.0,
                "temperatureLow": 45.0, "precipProbability": 0.2}]},
            "hourly": {"data": [{"time": 1700000000, "temperature": 60.0}]}
        });
        let b = parse_bundle(&v);
        let c = b.current.unwrap();
        assert_eq!(c.humidity, Some(50.0));
        assert_eq!(c.wind_direction.as_deref(), Some("E"));
        assert_eq!(c.cloud_cover, Some(10.0));
        let fc = b.forecast.unwrap();
        assert_eq!(fc.periods[0].precipitation_probability, Some(20.0));
        assert_eq!(fc.periods[0].temperature_low, Some(45.0));
        assert_eq!(b.hourly.unwrap().periods.len(), 1);
    }
}
