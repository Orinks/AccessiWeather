//! Next-90-minutes mobility briefing.
//!
//! Port of `services/mobility_briefing.py`.

use chrono::{DateTime, Duration, Utc};

use crate::display::pyfmt::fixed;
use crate::model::{HourlyForecastPeriod, WeatherData};

const ACTIONABLE_GUST_THRESHOLD_MPH: f64 = 25.0;
const VISIBILITY_CONCERN_THRESHOLD_MILES: f64 = 6.0;
const PRECIP_INTENSITY_THRESHOLD: f64 = 0.01;

/// `_infer_reference_time`: the earliest of the first minutely point, the
/// first hourly period and the hourly generation time.
fn infer_reference_time(data: &WeatherData) -> Option<DateTime<Utc>> {
    let mut candidates = Vec::new();
    if let Some(p) = data.minutely_precipitation.as_ref().and_then(|m| m.points.first()) {
        candidates.push(p.time.with_timezone(&Utc));
    }
    if let Some(h) = &data.hourly_forecast {
        if let Some(p) = h.periods.first() {
            candidates.push(p.start_time.with_timezone(&Utc));
        }
        if let Some(g) = h.generated_at {
            candidates.push(g.with_timezone(&Utc));
        }
    }
    candidates.into_iter().min()
}

fn minutes_floor(delta: Duration) -> i64 {
    // `int(delta.total_seconds() // 60)`: floor division.
    (delta.num_milliseconds() as f64 / 1000.0 / 60.0).floor() as i64
}

fn first_precip_start_minutes(data: &WeatherData, now: DateTime<Utc>) -> Option<i64> {
    let forecast = data.minutely_precipitation.as_ref()?;
    for point in &forecast.points {
        let minutes = minutes_floor(point.time.with_timezone(&Utc) - now);
        if !(0..=90).contains(&minutes) {
            continue;
        }
        let intensity = point.precipitation_intensity.unwrap_or(0.0);
        let probability = point.precipitation_probability.unwrap_or(0.0);
        if intensity >= PRECIP_INTENSITY_THRESHOLD || probability >= 0.5 {
            return Some(minutes);
        }
    }
    None
}

/// Hourly periods starting within the next 90 minutes, with their offsets.
fn near_periods(data: &WeatherData, now: DateTime<Utc>) -> Vec<(&HourlyForecastPeriod, Duration)> {
    let Some(hourly) = &data.hourly_forecast else {
        return Vec::new();
    };
    hourly
        .periods
        .iter()
        .filter_map(|p| {
            let delta = p.start_time.with_timezone(&Utc) - now;
            (delta >= Duration::zero() && delta <= Duration::minutes(90)).then_some((p, delta))
        })
        .collect()
}

fn gust_increase_phrase(data: &WeatherData, now: DateTime<Utc>) -> Option<String> {
    let candidates = near_periods(data, now);
    let first_gust = candidates.first()?.0.wind_gust_mph.unwrap_or(0.0);
    // `max()` keeps the first of equal maxima.
    let mut best = candidates[0];
    for c in &candidates[1..] {
        if c.0.wind_gust_mph.unwrap_or(0.0) > best.0.wind_gust_mph.unwrap_or(0.0) {
            best = *c;
        }
    }
    let max_gust = best.0.wind_gust_mph.unwrap_or(0.0);
    if max_gust < ACTIONABLE_GUST_THRESHOLD_MPH || max_gust <= first_gust + 5.0 {
        return None;
    }
    let minutes = minutes_floor(best.1);
    Some(if minutes <= 0 {
        "gusts increase soon".into()
    } else {
        format!("gusts increase within {minutes} minutes")
    })
}

fn hourly_fallback_phrase(data: &WeatherData, now: DateTime<Utc>) -> Option<String> {
    for (p, _) in near_periods(data, now) {
        let prob = p.precipitation_probability.unwrap_or(0.0);
        let short = p.short_forecast.as_deref().filter(|s| !s.is_empty());
        if prob >= 60.0 || short.is_some_and(|s| s.to_lowercase().contains("rain")) {
            return Some(short.unwrap_or("Rain likely").to_string());
        }
    }
    None
}

fn visibility_phrase(data: &WeatherData, now: DateTime<Utc>) -> Option<String> {
    if data.hourly_forecast.as_ref().is_some_and(|h| !h.periods.is_empty()) {
        let min = near_periods(data, now)
            .into_iter()
            .filter_map(|(p, _)| p.visibility_miles)
            .reduce(f64::min);
        if let Some(min) = min {
            return Some(if min < VISIBILITY_CONCERN_THRESHOLD_MILES {
                format!("visibility may drop to around {} miles", fixed(min, 0))
            } else {
                "visibility stays good".into()
            });
        }
    }
    data.current
        .as_ref()
        .and_then(|c| c.visibility_miles)
        .filter(|v| *v >= VISIBILITY_CONCERN_THRESHOLD_MILES)
        .map(|_| "visibility stays good".into())
}

/// `build_mobility_briefing`. `reference_time` defaults to the earliest
/// timestamp in the data, else `now`.
pub fn build_mobility_briefing(
    data: &WeatherData,
    reference_time: Option<DateTime<Utc>>,
    now: DateTime<Utc>,
) -> Option<String> {
    let now = reference_time
        .or_else(|| infer_reference_time(data))
        .unwrap_or(now);
    let mut phrases: Vec<String> = Vec::new();
    match first_precip_start_minutes(data, now) {
        Some(m) if m <= 0 => phrases.push("Rain is starting now".into()),
        Some(m) => phrases.push(format!("Dry for {m} minutes, then rain likely")),
        None => phrases.extend(hourly_fallback_phrase(data, now)),
    }
    phrases.extend(gust_increase_phrase(data, now));
    if let Some(v) = visibility_phrase(data, now) {
        if !phrases.is_empty() || v != "visibility stays good" {
            phrases.push(v);
        }
    }
    if phrases.is_empty() {
        return None;
    }
    let sentence = phrases.join("; ").trim().to_string();
    let mut chars = sentence.chars();
    let first = chars.next()?;
    let mut out: String = first.to_uppercase().collect();
    out.push_str(chars.as_str());
    if !out.ends_with('.') {
        out.push('.');
    }
    Some(out)
}
