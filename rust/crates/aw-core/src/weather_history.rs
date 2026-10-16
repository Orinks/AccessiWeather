//! Historical weather comparison. Pure part of
//! `accessiweather/weather_history.py`; the archive fetch lives in
//! `aw_providers::client::history`.

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::model::CurrentConditions;

/// Daily fields requested from the Open-Meteo archive.
pub const HISTORY_DAILY_FIELDS: [&str; 6] = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct HistoricalWeatherData {
    pub date: NaiveDate,
    pub temperature_max: f64,
    pub temperature_min: f64,
    pub temperature_mean: f64,
    pub condition: String,
    pub humidity: Option<i64>,
    pub wind_speed: f64,
    pub wind_direction: Option<i64>,
    pub pressure: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WeatherComparison {
    pub temperature_difference: f64,
    pub temperature_description: String,
    pub condition_changed: bool,
    pub previous_condition: String,
    pub condition_description: Option<String>,
    pub days_ago: i64,
}

impl WeatherComparison {
    /// Compare current conditions with a historical day's mean temperature.
    /// `None` when the current temperature is unknown (Python raises there).
    pub fn compare(
        current: &CurrentConditions,
        historical: &HistoricalWeatherData,
        days_ago: i64,
    ) -> Option<Self> {
        let diff = current.temperature? - historical.temperature_mean;
        let temperature_description = if diff.abs() < 1.0 {
            "about the same temperature".to_string()
        } else if diff > 0.0 {
            format!("{:.1} degrees warmer", diff.abs())
        } else {
            format!("{:.1} degrees cooler", diff.abs())
        };
        let condition_changed = current.condition.as_deref() != Some(historical.condition.as_str());
        let condition_description = condition_changed.then(|| {
            format!(
                "Changed from {} to {}",
                historical.condition,
                current.condition.as_deref().unwrap_or("None")
            )
        });
        Some(Self {
            temperature_difference: diff,
            temperature_description,
            condition_changed,
            previous_condition: historical.condition.clone(),
            condition_description,
            days_ago,
        })
    }

    /// `get_accessible_summary`.
    pub fn accessible_summary(&self) -> String {
        let time_ref = match self.days_ago {
            1 => "yesterday".to_string(),
            7 => "last week".to_string(),
            n => format!("{n} days ago"),
        };
        let mut parts = vec![format!(
            "Compared to {time_ref}: {}",
            self.temperature_description
        )];
        if self.condition_changed {
            if let Some(desc) = &self.condition_description {
                parts.push(desc.clone());
            }
        }
        parts.join(". ") + "."
    }
}

fn first_value<'a>(daily: &'a Value, field: &str) -> Option<&'a Value> {
    daily
        .get(field)?
        .as_array()?
        .first()
        .filter(|v| !v.is_null())
}

fn as_float(value: &Value) -> Option<f64> {
    match value {
        Value::Number(n) => n.as_f64(),
        Value::String(s) => s.trim().parse().ok(),
        _ => None,
    }
}

fn as_int(value: &Value) -> Option<i64> {
    match value {
        Value::Number(n) => n.as_i64().or(n.as_f64().map(|f| f.trunc() as i64)),
        Value::String(s) => s.trim().parse().ok(),
        _ => None,
    }
}

/// Parse a single-day archive response (`get_historical_weather`).
/// `describe` maps the WMO weather code to text (Open-Meteo's
/// `get_weather_description`).
pub fn parse_historical_weather(
    response: &Value,
    target_date: NaiveDate,
    describe: impl Fn(&Value) -> String,
) -> Option<HistoricalWeatherData> {
    let daily = response.get("daily")?;
    if daily.get("time")?.as_array()?.is_empty() {
        return None;
    }
    let weather_code = first_value(daily, "weather_code")?;
    let temperature_max = as_float(first_value(daily, "temperature_2m_max")?)?;
    let temperature_min = as_float(first_value(daily, "temperature_2m_min")?)?;
    let temperature_mean = as_float(first_value(daily, "temperature_2m_mean")?)?;
    let wind_speed = as_float(first_value(daily, "wind_speed_10m_max")?)?;
    let wind_direction = match first_value(daily, "wind_direction_10m_dominant") {
        Some(v) => Some(as_int(v)?),
        None => None,
    };
    Some(HistoricalWeatherData {
        date: target_date,
        temperature_max,
        temperature_min,
        temperature_mean,
        condition: describe(weather_code),
        humidity: None,
        wind_speed,
        wind_direction,
        pressure: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::golden::{self, field};

    #[test]
    fn golden_comparisons() {
        let cases = golden::load("history/comparisons.json");
        for case in cases.as_array().unwrap() {
            let current: CurrentConditions = field(case, "current");
            let historical: HistoricalWeatherData = field(case, "historical");
            let comparison =
                WeatherComparison::compare(&current, &historical, field(case, "days_ago"));
            let expected: WeatherComparison = field(case, "comparison");
            assert_eq!(comparison.as_ref(), Some(&expected), "{}", case["name"]);
            assert_eq!(
                comparison.unwrap().accessible_summary(),
                case["summary"].as_str().unwrap()
            );
        }
    }

    #[test]
    fn golden_archive_parsing() {
        let cases = golden::load("history/archive_parsing.json");
        for case in cases.as_array().unwrap() {
            let date: NaiveDate = field(case, "date");
            let parsed =
                parse_historical_weather(&case["response"], date, |code| format!("code {code}"));
            let expected: Option<HistoricalWeatherData> = field(case, "result");
            assert_eq!(parsed, expected, "{}", case["name"]);
        }
    }
}
