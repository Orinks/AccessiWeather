//! Historical temperature anomaly callouts. Port of
//! `accessiweather/weather_anomaly.py`; the archive requests are made by the
//! caller-supplied `fetch` closure (see `aw_providers::client::history`).

use chrono::{Datelike, Duration, NaiveDate};
use serde_json::Value;

use crate::model::AnomalyCallout;

pub const YEARS_OF_HISTORY: i32 = 5;
pub const MIN_YEARS_REQUIRED: usize = 3;
pub const DATE_WINDOW_DAYS: i64 = 7;

pub fn classify_severity(anomaly_f: f64) -> &'static str {
    let diff = anomaly_f.abs();
    if diff >= 5.0 {
        "significant"
    } else if diff >= 2.0 {
        "notable"
    } else {
        "normal"
    }
}

pub fn build_description(anomaly_f: f64, years: usize) -> String {
    let diff = anomaly_f.abs();
    if diff < 0.5 {
        return format!("Near the {years}-year average for this date.");
    }
    let direction = if anomaly_f > 0.0 { "warmer" } else { "cooler" };
    format!("Currently {diff:.1}\u{b0}F {direction} than the {years}-year average for this date.")
}

/// `compute_anomaly`: compare `current_temp_f` with the mean daily
/// temperature of the same ±7-day window in each of the last five years.
///
/// `fetch(start, end)` returns the archive JSON for a date range
/// (`daily=temperature_2m_mean`, Fahrenheit), or `None` on failure. `today`
/// clamps windows the archive (≈5 days behind) cannot serve yet.
pub fn compute_anomaly(
    current_temp_f: f64,
    current_date: NaiveDate,
    today: NaiveDate,
    mut fetch: impl FnMut(NaiveDate, NaiveDate) -> Option<Value>,
) -> Option<AnomalyCallout> {
    let mut yearly_means = Vec::new();
    for years_back in 1..=YEARS_OF_HISTORY {
        let year = current_date.year() - years_back;
        let anchor = current_date
            .with_year(year)
            .or_else(|| NaiveDate::from_ymd_opt(year, current_date.month(), 28))?;
        let start = anchor - Duration::days(DATE_WINDOW_DAYS);
        let end = (anchor + Duration::days(DATE_WINDOW_DAYS)).min(today - Duration::days(5));
        if start >= end {
            continue;
        }
        let Some(response) = fetch(start, end) else {
            continue;
        };
        let temps: Vec<f64> = response
            .get("daily")
            .and_then(|d| d.get("temperature_2m_mean"))
            .and_then(Value::as_array)
            .map(|values| values.iter().filter_map(Value::as_f64).collect())
            .unwrap_or_default();
        if temps.is_empty() {
            continue;
        }
        yearly_means.push(temps.iter().sum::<f64>() / temps.len() as f64);
    }
    if yearly_means.len() < MIN_YEARS_REQUIRED {
        return None;
    }
    let baseline = yearly_means.iter().sum::<f64>() / yearly_means.len() as f64;
    let anomaly = current_temp_f - baseline;
    Some(AnomalyCallout {
        temp_anomaly: anomaly,
        temp_anomaly_description: build_description(anomaly, yearly_means.len()),
        precip_anomaly_description: None,
        severity: classify_severity(anomaly).into(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::golden::{self, field};

    #[test]
    fn golden_anomalies() {
        let cases = golden::load("history/anomaly.json");
        for case in cases.as_array().unwrap() {
            let responses = case["responses"].as_object().unwrap().clone();
            let mut requests = Vec::new();
            let result = compute_anomaly(
                field(case, "current_temp_f"),
                field(case, "current_date"),
                field(case, "today"),
                |start, end| {
                    let key = format!("{start}/{end}");
                    requests.push(key.clone());
                    responses.get(&key).cloned().filter(|v| !v.is_null())
                },
            );
            let expected: Option<AnomalyCallout> = field(case, "result");
            let expected_requests: Vec<String> = field(case, "requests");
            assert_eq!(result, expected, "{}", case["name"]);
            assert_eq!(requests, expected_requests, "{}", case["name"]);
        }
    }

    #[test]
    fn severity_buckets_and_text() {
        assert_eq!(classify_severity(-5.0), "significant");
        assert_eq!(classify_severity(2.0), "notable");
        assert_eq!(classify_severity(1.9), "normal");
        assert_eq!(
            build_description(0.4, 5),
            "Near the 5-year average for this date."
        );
        assert_eq!(
            build_description(-3.25, 4),
            "Currently 3.2°F cooler than the 4-year average for this date."
        );
    }
}
