//! Weather history comparisons and anomaly callouts against the Open-Meteo
//! archive. Port of `WeatherHistoryService` (`accessiweather/weather_history.py`)
//! and the fetch loop of `weather_anomaly.compute_anomaly`.
//!
//! Python constructs the service (when `weather_history_enabled`) but never
//! calls it, and nothing calls `compute_anomaly`; both are ported for
//! completeness.

use std::sync::Arc;

use aw_core::model::{AnomalyCallout, CurrentConditions, Location};
use aw_core::weather_anomaly;
use aw_core::weather_history::{
    parse_historical_weather, HistoricalWeatherData, WeatherComparison, HISTORY_DAILY_FIELDS,
};
use chrono::{Duration, NaiveDate};
use serde_json::Value;

use super::sources::SourceResult;

/// One archive request (`GET {archive}/archive`, `timezone=auto`).
#[derive(Debug, Clone, PartialEq)]
pub struct ArchiveRequest {
    pub latitude: f64,
    pub longitude: f64,
    pub start_date: NaiveDate,
    pub end_date: NaiveDate,
    /// Daily variables, sent as repeated `daily=` parameters.
    pub daily: Vec<&'static str>,
    /// "fahrenheit" or "celsius".
    pub temperature_unit: String,
}

/// Open-Meteo archive API (`OpenMeteoApiClient._make_request("archive", ...,
/// use_archive=True)`; Python uses a 30 s timeout for history).
pub trait ArchiveSource: Send + Sync {
    /// The response JSON.
    fn archive(&self, request: &ArchiveRequest) -> SourceResult<Value>;
    /// `OpenMeteoApiClient.get_weather_description` for a WMO code value.
    fn weather_description(&self, code: &Value) -> String;
}

pub struct WeatherHistoryService {
    archive: Arc<dyn ArchiveSource>,
}

impl WeatherHistoryService {
    pub fn new(archive: Arc<dyn ArchiveSource>) -> Self {
        Self { archive }
    }

    /// `get_historical_weather`: one day from the archive, `None` when the
    /// request fails or required values are missing.
    pub fn get_historical_weather(
        &self,
        latitude: f64,
        longitude: f64,
        target_date: NaiveDate,
        temperature_unit: &str,
    ) -> Option<HistoricalWeatherData> {
        let request = ArchiveRequest {
            latitude,
            longitude,
            start_date: target_date,
            end_date: target_date,
            daily: HISTORY_DAILY_FIELDS.to_vec(),
            temperature_unit: temperature_unit.to_string(),
        };
        let response = match self.archive.archive(&request) {
            Ok(response) => response,
            Err(e) => {
                tracing::error!("Failed to fetch historical weather data: {e}");
                return None;
            }
        };
        let parsed = parse_historical_weather(&response, target_date, |code| {
            self.archive.weather_description(code)
        });
        if parsed.is_none() {
            tracing::warn!("No historical data available for {target_date}");
        }
        parsed
    }

    /// Compare with `today - 1 day` (`compare_with_yesterday`).
    pub fn compare_with_yesterday(
        &self,
        location: &Location,
        current: &CurrentConditions,
        temperature_unit: &str,
        today: NaiveDate,
    ) -> Option<WeatherComparison> {
        self.compare_days_ago(location, current, temperature_unit, today, 1)
    }

    /// Compare with `today - 7 days` (`compare_with_last_week`).
    pub fn compare_with_last_week(
        &self,
        location: &Location,
        current: &CurrentConditions,
        temperature_unit: &str,
        today: NaiveDate,
    ) -> Option<WeatherComparison> {
        self.compare_days_ago(location, current, temperature_unit, today, 7)
    }

    /// Compare with a specific date (`compare_with_date`).
    pub fn compare_with_date(
        &self,
        location: &Location,
        current: &CurrentConditions,
        target_date: NaiveDate,
        temperature_unit: &str,
        today: NaiveDate,
    ) -> Option<WeatherComparison> {
        let days_ago = (today - target_date).num_days();
        let historical = self.get_historical_weather(
            location.latitude,
            location.longitude,
            target_date,
            temperature_unit,
        )?;
        WeatherComparison::compare(current, &historical, days_ago)
    }

    fn compare_days_ago(
        &self,
        location: &Location,
        current: &CurrentConditions,
        temperature_unit: &str,
        today: NaiveDate,
        days: i64,
    ) -> Option<WeatherComparison> {
        let date = today - Duration::days(days);
        let historical = self.get_historical_weather(
            location.latitude,
            location.longitude,
            date,
            temperature_unit,
        )?;
        WeatherComparison::compare(current, &historical, days)
    }
}

/// `compute_anomaly`: current temperature versus the five-year archive
/// baseline for the same ±7 days.
pub fn compute_anomaly(
    archive: &dyn ArchiveSource,
    latitude: f64,
    longitude: f64,
    current_temp_f: f64,
    current_date: NaiveDate,
    today: NaiveDate,
) -> Option<AnomalyCallout> {
    weather_anomaly::compute_anomaly(current_temp_f, current_date, today, |start, end| {
        let request = ArchiveRequest {
            latitude,
            longitude,
            start_date: start,
            end_date: end,
            daily: vec!["temperature_2m_mean"],
            temperature_unit: "fahrenheit".into(),
        };
        archive
            .archive(&request)
            .map_err(|e| tracing::debug!("Anomaly archive fetch failed: {e}"))
            .ok()
    })
}

#[cfg(test)]
mod tests {
    use std::sync::Mutex;

    use aw_core::golden::{self, field};

    use super::*;
    use crate::client::SourceError;

    struct FakeArchive {
        response: SourceResult<Value>,
        requests: Mutex<Vec<ArchiveRequest>>,
    }

    impl ArchiveSource for FakeArchive {
        fn archive(&self, request: &ArchiveRequest) -> SourceResult<Value> {
            self.requests.lock().unwrap().push(request.clone());
            self.response.clone()
        }
        fn weather_description(&self, code: &Value) -> String {
            format!("code {code}")
        }
    }

    fn service(response: SourceResult<Value>) -> (Arc<FakeArchive>, WeatherHistoryService) {
        let fake = Arc::new(FakeArchive {
            response,
            requests: Mutex::default(),
        });
        (fake.clone(), WeatherHistoryService::new(fake))
    }

    #[test]
    fn golden_archive_responses_through_the_service() {
        for case in golden::load("history/archive_parsing.json")
            .as_array()
            .unwrap()
        {
            let (fake, service) = service(Ok(case["response"].clone()));
            let date: NaiveDate = field(case, "date");
            let result = service.get_historical_weather(40.0, -75.0, date, "fahrenheit");
            let expected: Option<HistoricalWeatherData> = field(case, "result");
            assert_eq!(result, expected, "{}", case["name"]);
            let request = &fake.requests.lock().unwrap()[0];
            assert_eq!(request.daily, HISTORY_DAILY_FIELDS.to_vec());
            assert_eq!((request.start_date, request.end_date), (date, date));
        }
    }

    #[test]
    fn failed_request_gives_none_and_comparisons_use_today() {
        let (_, failing) = service(Err(SourceError::new("offline")));
        let today = NaiveDate::from_ymd_opt(2026, 7, 15).unwrap();
        assert!(failing
            .get_historical_weather(1.0, 2.0, today, "celsius")
            .is_none());

        let response = serde_json::json!({"daily": {
            "time": ["2026-07-08"], "weather_code": [0], "temperature_2m_max": [80.0],
            "temperature_2m_min": [60.0], "temperature_2m_mean": [70.0], "wind_speed_10m_max": [5.0]}});
        let (fake, service) = service(Ok(response));
        let location = Location::new("Here", 40.0, -75.0);
        let current = CurrentConditions {
            temperature: Some(75.0),
            condition: Some("code 0".into()),
            ..Default::default()
        };
        let week = service
            .compare_with_last_week(&location, &current, "fahrenheit", today)
            .unwrap();
        assert_eq!(
            week.accessible_summary(),
            "Compared to last week: 5.0 degrees warmer."
        );
        assert_eq!(
            fake.requests.lock().unwrap()[0].start_date,
            NaiveDate::from_ymd_opt(2026, 7, 8).unwrap()
        );
        let dated = service
            .compare_with_date(
                &location,
                &current,
                NaiveDate::from_ymd_opt(2026, 7, 5).unwrap(),
                "fahrenheit",
                today,
            )
            .unwrap();
        assert_eq!(dated.days_ago, 10);
    }
}
