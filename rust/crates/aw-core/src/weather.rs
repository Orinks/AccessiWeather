//! Weather data models, ported from `accessiweather.models.weather_*`.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::alerts::WeatherAlerts;
use crate::location::Location;

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct CurrentConditions {
    pub temperature_f: Option<f64>,
    pub temperature_c: Option<f64>,
    pub condition: Option<String>,
    pub humidity: Option<f64>,
    pub dewpoint_f: Option<f64>,
    pub dewpoint_c: Option<f64>,
    pub wind_speed_mph: Option<f64>,
    pub wind_speed_kph: Option<f64>,
    /// Either a cardinal direction ("NW") or degrees as text ("315").
    pub wind_direction: Option<String>,
    pub wind_gust_mph: Option<f64>,
    pub wind_gust_kph: Option<f64>,
    pub pressure_in: Option<f64>,
    pub pressure_mb: Option<f64>,
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
    pub visibility_miles: Option<f64>,
    pub visibility_km: Option<f64>,
    pub uv_index: Option<f64>,
    pub cloud_cover: Option<f64>,
    pub precipitation_in: Option<f64>,
    pub precipitation_mm: Option<f64>,
    pub snow_depth_in: Option<f64>,
    pub snow_depth_cm: Option<f64>,
    pub sunrise_time: Option<DateTime<Utc>>,
    pub sunset_time: Option<DateTime<Utc>>,
    pub observed_at: Option<DateTime<Utc>>,
    pub station_id: Option<String>,
    pub source: Option<String>,
}

impl CurrentConditions {
    pub fn has_data(&self) -> bool {
        self.temperature_f.is_some() || self.temperature_c.is_some() || self.condition.is_some()
    }

    /// Fill in the missing half of paired unit fields so every consumer can
    /// rely on both values being present when either was reported.
    pub fn fill_unit_pairs(&mut self) {
        use crate::units::{c_to_f, f_to_c};
        fn pair(
            a: &mut Option<f64>,
            b: &mut Option<f64>,
            a_to_b: fn(f64) -> f64,
            b_to_a: fn(f64) -> f64,
        ) {
            match (*a, *b) {
                (Some(x), None) => *b = Some(a_to_b(x)),
                (None, Some(y)) => *a = Some(b_to_a(y)),
                _ => {}
            }
        }
        pair(
            &mut self.temperature_f,
            &mut self.temperature_c,
            f_to_c,
            c_to_f,
        );
        pair(&mut self.dewpoint_f, &mut self.dewpoint_c, f_to_c, c_to_f);
        pair(
            &mut self.feels_like_f,
            &mut self.feels_like_c,
            f_to_c,
            c_to_f,
        );
        pair(
            &mut self.wind_chill_f,
            &mut self.wind_chill_c,
            f_to_c,
            c_to_f,
        );
        pair(
            &mut self.heat_index_f,
            &mut self.heat_index_c,
            f_to_c,
            c_to_f,
        );
        pair(
            &mut self.wind_speed_mph,
            &mut self.wind_speed_kph,
            |m| m * 1.60934,
            |k| k * 0.621371,
        );
        pair(
            &mut self.wind_gust_mph,
            &mut self.wind_gust_kph,
            |m| m * 1.60934,
            |k| k * 0.621371,
        );
        pair(
            &mut self.pressure_in,
            &mut self.pressure_mb,
            |i| i * 33.8639,
            |m| m / 33.8639,
        );
        pair(
            &mut self.visibility_miles,
            &mut self.visibility_km,
            |m| m * 1.60934,
            |k| k * 0.621371,
        );
        pair(
            &mut self.precipitation_in,
            &mut self.precipitation_mm,
            |i| i * 25.4,
            |m| m / 25.4,
        );
        pair(
            &mut self.snow_depth_in,
            &mut self.snow_depth_cm,
            |i| i * 2.54,
            |c| c / 2.54,
        );
        // A gust below the sustained wind is noise; drop it (parity with fusion rules).
        if let (Some(gust), Some(wind)) = (self.wind_gust_mph, self.wind_speed_mph) {
            if gust < wind {
                self.wind_gust_mph = None;
                self.wind_gust_kph = None;
            }
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct ForecastPeriod {
    pub name: String,
    /// High temperature (or single temperature for the period).
    pub temperature: Option<f64>,
    pub temperature_low: Option<f64>,
    /// "F" or "C"
    pub temperature_unit: String,
    pub short_forecast: Option<String>,
    pub detailed_forecast: Option<String>,
    pub wind_speed: Option<String>,
    pub wind_speed_mph: Option<f64>,
    pub wind_direction: Option<String>,
    pub start_time: Option<DateTime<Utc>>,
    pub end_time: Option<DateTime<Utc>>,
    pub precipitation_probability: Option<f64>,
    pub precipitation_amount_in: Option<f64>,
    pub uv_index_max: Option<f64>,
    pub is_daytime: Option<bool>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Forecast {
    pub periods: Vec<ForecastPeriod>,
    pub generated_at: Option<DateTime<Utc>>,
    pub source: Option<String>,
}

impl Forecast {
    pub fn has_data(&self) -> bool {
        !self.periods.is_empty()
    }
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct HourlyForecastPeriod {
    pub start_time: DateTime<Utc>,
    pub temperature: Option<f64>,
    pub temperature_unit: String,
    pub short_forecast: Option<String>,
    pub wind_speed: Option<String>,
    pub wind_speed_mph: Option<f64>,
    pub wind_direction: Option<String>,
    pub humidity: Option<f64>,
    pub precipitation_probability: Option<f64>,
    pub pressure_mb: Option<f64>,
    pub pressure_in: Option<f64>,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct HourlyForecast {
    pub periods: Vec<HourlyForecastPeriod>,
    pub generated_at: Option<DateTime<Utc>>,
    pub source: Option<String>,
}

impl HourlyForecast {
    pub fn has_data(&self) -> bool {
        !self.periods.is_empty()
    }

    /// The next `count` periods starting no earlier than one hour before `now`.
    /// Falls back to the first periods if everything is in the past.
    pub fn next_hours(&self, count: usize, now: DateTime<Utc>) -> Vec<&HourlyForecastPeriod> {
        let mut sorted: Vec<&HourlyForecastPeriod> = self.periods.iter().collect();
        sorted.sort_by_key(|p| p.start_time);
        let cutoff = now - chrono::Duration::hours(1);
        let upcoming: Vec<&HourlyForecastPeriod> = sorted
            .iter()
            .copied()
            .filter(|p| p.start_time >= cutoff)
            .take(count)
            .collect();
        if upcoming.is_empty() {
            sorted.into_iter().take(count).collect()
        } else {
            upcoming
        }
    }
}

/// Everything fetched for a location in one refresh.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct WeatherData {
    pub location: Location,
    pub current: Option<CurrentConditions>,
    pub forecast: Option<Forecast>,
    pub hourly_forecast: Option<HourlyForecast>,
    pub alerts: Option<WeatherAlerts>,
    pub discussion: Option<String>,
    pub last_updated: Option<DateTime<Utc>>,
    pub stale: bool,
    pub stale_since: Option<DateTime<Utc>>,
    pub stale_reason: Option<String>,
    /// Sources that contributed data, in priority order.
    pub sources: Vec<String>,
    /// Sources that failed, with a short reason.
    pub failed_sources: Vec<(String, String)>,
}

impl WeatherData {
    pub fn new(location: Location) -> Self {
        Self {
            location,
            ..Default::default()
        }
    }

    pub fn has_any_data(&self) -> bool {
        self.current.as_ref().is_some_and(|c| c.has_data())
            || self.forecast.as_ref().is_some_and(|f| f.has_data())
            || self.hourly_forecast.as_ref().is_some_and(|h| h.has_data())
            || self.alerts.as_ref().is_some_and(|a| a.has_alerts())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn next_hours_skips_past_periods_with_tolerance() {
        let now = Utc.with_ymd_and_hms(2026, 1, 1, 12, 0, 0).unwrap();
        let periods = (8..18)
            .map(|h| HourlyForecastPeriod {
                start_time: Utc.with_ymd_and_hms(2026, 1, 1, h, 0, 0).unwrap(),
                ..Default::default()
            })
            .collect();
        let hourly = HourlyForecast {
            periods,
            ..Default::default()
        };
        let next = hourly.next_hours(3, now);
        let hours: Vec<u32> = next
            .iter()
            .map(|p| chrono::Timelike::hour(&p.start_time))
            .collect();
        assert_eq!(hours, vec![11, 12, 13]);
    }

    #[test]
    fn unit_pairs_are_filled_and_bad_gusts_dropped() {
        let mut c = CurrentConditions {
            temperature_c: Some(0.0),
            wind_speed_mph: Some(10.0),
            wind_gust_mph: Some(5.0),
            ..Default::default()
        };
        c.fill_unit_pairs();
        assert_eq!(c.temperature_f, Some(32.0));
        assert!((c.wind_speed_kph.unwrap() - 16.0934).abs() < 1e-6);
        assert!(c.wind_gust_mph.is_none());
    }
}
