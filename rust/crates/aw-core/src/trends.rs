//! Trend insights (temperature, pressure outlook, day-over-day) computed
//! from fused weather data. Port of `accessiweather/weather_client_trends.py`.
//!
//! Python compares naive local datetimes; here the instants are compared
//! directly, which is the same except across a DST change inside the window.

use chrono::{DateTime, Duration, Utc};

use crate::model::{HourlyForecastPeriod, TrendInsight, WeatherData};

const MAX_PRESSURE_TREND_MB: f64 = 24.0;
const MAX_PRESSURE_TREND_IN: f64 = MAX_PRESSURE_TREND_MB / 33.8639;
const MIN_PRESSURE_TREND_MB: f64 = 10.0;
const MIN_PRESSURE_TREND_IN: f64 = 0.30;
const MIXED_PRESSURE_REFERENCE_SUMMARY: &str =
    "Pressure outlook unavailable: pressure data uses mixed reference levels.";

/// Python's `round(x, ndigits)` (correctly rounded, ties to even).
pub fn py_round(value: f64, ndigits: usize) -> f64 {
    format!("{value:.ndigits$}").parse().unwrap_or(value)
}

/// `apply_trend_insights`: replace `trend_insights` on `weather`.
pub fn apply_trend_insights(
    weather: &mut WeatherData,
    enabled: bool,
    trend_hours: i64,
    include_pressure: bool,
    now: DateTime<Utc>,
) {
    if !enabled {
        weather.trend_insights.clear();
        return;
    }
    let mut insights = Vec::new();
    insights.extend(compute_temperature_trend(weather, trend_hours, now));
    if include_pressure {
        match compute_pressure_trend(weather, trend_hours, now) {
            Some(insight) => insights.push(insight),
            None => insights.extend(compute_pressure_outlook_unavailable(weather, trend_hours)),
        }
    }
    insights.extend(compute_daily_trend(weather));
    weather.trend_insights = insights;
}

fn hourly_periods(weather: &WeatherData) -> &[HourlyForecastPeriod] {
    weather
        .hourly_forecast
        .as_ref()
        .map_or(&[], |h| h.periods.as_slice())
}

pub fn compute_temperature_trend(
    weather: &WeatherData,
    trend_hours: i64,
    now: DateTime<Utc>,
) -> Option<TrendInsight> {
    let current = weather.current.as_ref()?;
    let hourly = hourly_periods(weather);
    if hourly.is_empty() {
        return None;
    }
    let (base, unit) = match (current.temperature_f, current.temperature_c) {
        (Some(f), _) => (f, "°F"),
        (None, Some(c)) => (c, "°C"),
        _ => return None,
    };
    let target = period_for_hours_ahead(hourly, trend_hours, None, now)?;
    let change = target.temperature? - base;
    let fahrenheit = unit == "°F";
    let (direction, sparkline) = trend_descriptor(
        change,
        if fahrenheit { 1.0 } else { 0.5 },
        if fahrenheit { 3.0 } else { 1.5 },
    );
    Some(TrendInsight {
        metric: "temperature".into(),
        direction: direction.into(),
        change: Some(py_round(change, 1)),
        unit: Some(unit.into()),
        timeframe_hours: trend_hours,
        summary: Some(format!(
            "Temperature {direction} {change:+.1}{unit} over {trend_hours}h"
        )),
        sparkline: Some(sparkline.into()),
    })
}

pub fn compute_pressure_trend(
    weather: &WeatherData,
    trend_hours: i64,
    now: DateTime<Utc>,
) -> Option<TrendInsight> {
    let current = weather.current.as_ref()?;
    let hourly = hourly_periods(weather);
    if hourly.is_empty() {
        return None;
    }
    let tolerance = (trend_hours as f64 * 0.25).clamp(3.0, 12.0);
    let target = period_for_hours_ahead(hourly, trend_hours, Some(tolerance), now)?;

    let (base, future, unit) = match (current.pressure_mb, target.pressure_mb) {
        (Some(b), Some(f)) => (b, f, "mb"),
        _ => match (current.pressure_in, target.pressure_in) {
            (Some(b), Some(f)) => (b, f, "inHg"),
            _ => return None,
        },
    };
    let change = future - base;
    if pressure_change_is_implausible(change, unit, trend_hours) {
        return Some(pressure_unavailable(
            MIXED_PRESSURE_REFERENCE_SUMMARY,
            trend_hours,
        ));
    }
    let mb = unit == "mb";
    let (direction, sparkline) = trend_descriptor(
        change,
        if mb { 0.5 } else { 0.02 },
        if mb { 1.5 } else { 0.05 },
    );
    Some(TrendInsight {
        metric: "pressure".into(),
        direction: direction.into(),
        change: Some(py_round(change, 2)),
        unit: Some(unit.into()),
        timeframe_hours: trend_hours,
        summary: Some(pressure_trend_summary(direction, change, unit, trend_hours)),
        sparkline: Some(sparkline.into()),
    })
}

/// Too large a change to present as a reliable trend (usually station vs
/// sea-level pressure mixed across sources).
pub fn pressure_change_is_implausible(change: f64, unit: &str, trend_hours: i64) -> bool {
    let hours = trend_hours as f64;
    let max_change = if unit == "mb" {
        MIN_PRESSURE_TREND_MB.max(MAX_PRESSURE_TREND_MB.min(hours * 1.0))
    } else {
        MIN_PRESSURE_TREND_IN.max(MAX_PRESSURE_TREND_IN.min(hours / 33.8639))
    };
    change.abs() > max_change
}

/// Explain why no pressure outlook could be calculated.
pub fn compute_pressure_outlook_unavailable(
    weather: &WeatherData,
    trend_hours: i64,
) -> Option<TrendInsight> {
    let current = weather.current.as_ref().filter(|c| c.has_data())?;
    if current.pressure_mb.is_none() && current.pressure_in.is_none() {
        return Some(pressure_unavailable(
            "Pressure outlook unavailable: current pressure data is missing.",
            trend_hours,
        ));
    }
    let Some(hourly) = weather.hourly_forecast.as_ref().filter(|h| h.has_data()) else {
        return Some(pressure_unavailable(
            "Pressure outlook unavailable: hourly forecast data is missing.",
            trend_hours,
        ));
    };
    if !hourly
        .periods
        .iter()
        .any(|p| p.pressure_mb.is_some() || p.pressure_in.is_some())
    {
        let source = weather
            .source_attribution
            .as_ref()
            .and_then(|a| a.field_sources.get("hourly_source"))
            .filter(|s| !s.is_empty())
            .map(|s| format_source_name(s));
        let summary = match source {
            Some(label) => format!(
                "Pressure outlook unavailable: {label} hourly forecast does not include pressure data."
            ),
            None => {
                "Pressure outlook unavailable: hourly forecast does not include pressure data."
                    .into()
            }
        };
        return Some(pressure_unavailable(&summary, trend_hours));
    }
    Some(pressure_unavailable(
        &format!(
            "Pressure outlook unavailable: not enough hourly pressure data for the next {trend_hours}h."
        ),
        trend_hours,
    ))
}

fn pressure_unavailable(summary: &str, trend_hours: i64) -> TrendInsight {
    TrendInsight {
        metric: "pressure".into(),
        direction: "unavailable".into(),
        change: None,
        unit: None,
        timeframe_hours: trend_hours,
        summary: Some(summary.into()),
        sparkline: None,
    }
}

fn format_source_name(source: &str) -> String {
    match source {
        "nws" => "NWS".into(),
        "openmeteo" => "Open-Meteo".into(),
        "pirateweather" => "Pirate Weather".into(),
        other => other.into(),
    }
}

pub fn pressure_trend_summary(
    direction: &str,
    change: f64,
    unit: &str,
    trend_hours: i64,
) -> String {
    let action = match direction {
        "falling" => "drop predicted",
        "rising" => "rise predicted",
        _ => return format!("Pressure steady over next {trend_hours}h"),
    };
    format!("Pressure {action}: {change:+.2} {unit} over next {trend_hours}h")
}

/// Direction word and sparkline for a change of the given magnitude.
pub fn trend_descriptor(change: f64, minor: f64, strong: f64) -> (&'static str, &'static str) {
    if change >= strong {
        ("rising", "↑↑")
    } else if change >= minor {
        ("rising", "↑")
    } else if change <= -strong {
        ("falling", "↓↓")
    } else if change <= -minor {
        ("falling", "↓")
    } else {
        ("steady", "→")
    }
}

/// The period closest to `now + hours_ahead` (first one on ties), or `None`
/// when it is further than `max_delta_hours` from the target.
pub fn period_for_hours_ahead(
    periods: &[HourlyForecastPeriod],
    hours_ahead: i64,
    max_delta_hours: Option<f64>,
    now: DateTime<Utc>,
) -> Option<&HourlyForecastPeriod> {
    let target = now + Duration::hours(hours_ahead);
    let mut best: Option<(&HourlyForecastPeriod, Duration)> = None;
    for period in periods {
        let delta = (period.start_time.with_timezone(&Utc) - target).abs();
        if best.is_none_or(|(_, d)| delta < d) {
            best = Some((period, delta));
        }
    }
    let (period, delta) = best?;
    if let Some(max_hours) = max_delta_hours {
        let delta_seconds = delta.num_microseconds().unwrap_or(i64::MAX) as f64 / 1e6;
        if delta_seconds > max_hours * 3600.0 {
            return None;
        }
    }
    Some(period)
}

/// Today's forecast high versus yesterday's (`daily_history[0]`).
pub fn compute_daily_trend(weather: &WeatherData) -> Option<TrendInsight> {
    let today = weather.forecast.as_ref()?.periods.first()?;
    let yesterday = weather.daily_history.first()?;
    let change = today.temperature? - yesterday.temperature?;
    let unit = if today.temperature_unit.is_empty() {
        "F"
    } else {
        today.temperature_unit.as_str()
    };
    let threshold = if unit == "F" { 2.0 } else { 1.0 };
    let direction = if change >= threshold {
        "warmer"
    } else if change <= -threshold {
        "cooler"
    } else {
        "similar"
    };
    let summary = if direction == "similar" {
        "Temperatures similar to yesterday".to_string()
    } else {
        format!("{:.0}°{unit} {direction} than yesterday", change.abs())
    };
    let sparkline = if change > 0.0 {
        "↑"
    } else if change < 0.0 {
        "↓"
    } else {
        "→"
    };
    Some(TrendInsight {
        metric: "daily_trend".into(),
        direction: direction.into(),
        change: Some(py_round(change, 1)),
        unit: Some(unit.into()),
        timeframe_hours: 24,
        summary: Some(summary),
        sparkline: Some(sparkline.into()),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::golden::{self, field};

    #[test]
    fn golden_trend_insights() {
        let cases = golden::load("trends/cases.json");
        for case in cases.as_array().unwrap() {
            let mut weather: WeatherData = field(case, "weather");
            let now: DateTime<Utc> = field(case, "now");
            apply_trend_insights(
                &mut weather,
                field(case, "enabled"),
                field(case, "trend_hours"),
                field(case, "include_pressure"),
                now,
            );
            let expected: Vec<TrendInsight> = field(case, "insights");
            assert_eq!(weather.trend_insights, expected, "{}", case["name"]);
        }
    }

    #[test]
    fn python_round_and_descriptors() {
        assert_eq!(py_round(2.675, 2), 2.67);
        assert_eq!(py_round(0.25, 1), 0.2);
        assert_eq!(trend_descriptor(3.0, 1.0, 3.0), ("rising", "↑↑"));
        assert_eq!(trend_descriptor(-1.0, 1.0, 3.0), ("falling", "↓"));
        assert_eq!(trend_descriptor(0.5, 1.0, 3.0), ("steady", "→"));
        assert_eq!(
            pressure_trend_summary("falling", -4.8, "mb", 24),
            "Pressure drop predicted: -4.80 mb over next 24h"
        );
        assert_eq!(
            pressure_trend_summary("steady", 0.1, "mb", 6),
            "Pressure steady over next 6h"
        );
    }

    #[test]
    fn implausible_pressure_limits() {
        assert!(pressure_change_is_implausible(10.5, "mb", 6));
        assert!(!pressure_change_is_implausible(10.0, "mb", 6));
        assert!(pressure_change_is_implausible(0.31, "inHg", 6));
    }
}
