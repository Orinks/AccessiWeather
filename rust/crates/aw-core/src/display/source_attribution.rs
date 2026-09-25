//! Data source attribution.
//!
//! Port of `display/presentation/source_attribution.py`.

use crate::display::models::SourceAttributionPresentation;
use crate::display::pyfmt::title;
use crate::model::{MinutelyPrecipitationForecast, WeatherData};

const WET_MARKERS: [&str; 9] = [
    "thunderstorm",
    "t-storm",
    "rain",
    "shower",
    "drizzle",
    "snow",
    "sleet",
    "hail",
    "freezing rain",
];
const DRY_MARKERS: [&str; 5] = ["clear", "sunny", "cloudy", "overcast", "fair"];

fn source_name(source: &str) -> String {
    match source {
        "nws" => "National Weather Service".into(),
        "openmeteo" => "Open-Meteo".into(),
        "pirateweather" => "Pirate Weather".into(),
        other => title(other),
    }
}

/// `build_source_attribution`.
///
/// Python lists `incomplete_sections` in set iteration order, which varies
/// between runs; here they are sorted.
pub fn build_source_attribution(data: &WeatherData) -> Option<SourceAttributionPresentation> {
    let attribution = data.source_attribution.as_ref()?;
    let contributing: Vec<String> = attribution
        .contributing_sources
        .iter()
        .map(|s| source_name(s))
        .collect();
    let failed: Vec<String> = attribution
        .failed_sources
        .iter()
        .map(|s| source_name(s))
        .collect();
    let incomplete: Vec<String> = data.incomplete_sections.iter().cloned().collect();

    let mut summary = if !contributing.is_empty() {
        let mut s = format!("Data from: {}", contributing.join(", "));
        if !failed.is_empty() {
            s.push_str(&format!(". Unavailable: {}", failed.join(", ")));
        }
        s
    } else if !failed.is_empty() {
        format!("Sources unavailable: {}", failed.join(", "))
    } else {
        String::new()
    };

    let note = disagreement_note(data);
    if let Some(n) = &note {
        summary = if summary.is_empty() {
            n.clone()
        } else {
            format!("{summary}. {n}")
        };
    }

    let mut aria = Vec::new();
    if !contributing.is_empty() {
        aria.push(format!("Weather data provided by {}", contributing.join(", ")));
    }
    if !failed.is_empty() {
        aria.push(format!("Data unavailable from {}", failed.join(", ")));
    }
    if !incomplete.is_empty() {
        aria.push(format!("Missing sections: {}", incomplete.join(", ")));
    }
    if let Some(n) = note {
        aria.push(n);
    }
    let aria_label = if aria.is_empty() {
        "Weather data source information".into()
    } else {
        aria.join(". ")
    };

    Some(SourceAttributionPresentation {
        contributing_sources: contributing,
        failed_sources: failed,
        incomplete_sections: incomplete,
        summary_text: summary,
        aria_label,
    })
}

/// `_clean_condition_text`.
fn clean(value: Option<&str>) -> Option<String> {
    let cleaned = value?.trim();
    (!cleaned.is_empty()).then(|| cleaned.trim_end_matches('.').to_string())
}

/// `_precipitation_state`: "wet", "dry" or ambiguous.
fn precipitation_state(value: Option<&str>) -> Option<&'static str> {
    let v = value?.to_lowercase();
    if WET_MARKERS.iter().any(|m| v.contains(m)) {
        Some("wet")
    } else if DRY_MARKERS.iter().any(|m| v.contains(m)) {
        Some("dry")
    } else {
        None
    }
}

fn minutely_state(minutely: Option<&MinutelyPrecipitationForecast>) -> Option<&'static str> {
    let m = minutely?;
    if !m.points.is_empty() {
        let wet = m.points.iter().any(|p| {
            p.precipitation_intensity.is_some_and(|i| i > 0.0)
                || p.precipitation_probability.is_some_and(|p| p > 0.0)
        });
        return Some(if wet { "wet" } else { "dry" });
    }
    precipitation_state(clean(m.summary.as_deref()).as_deref())
}

fn format_source(source: Option<&String>) -> String {
    match source.filter(|s| !s.is_empty()) {
        Some(s) => source_name(s),
        None => "another source".into(),
    }
}

/// `_build_source_disagreement_note`.
fn disagreement_note(data: &WeatherData) -> Option<String> {
    let attribution = data.source_attribution.as_ref()?;
    let current = data.current.as_ref()?;
    let current_text = clean(current.condition.as_deref())?;
    let current_state = precipitation_state(Some(&current_text))?;

    let hourly_text = data
        .hourly_forecast
        .as_ref()
        .and_then(|h| h.periods.first())
        .and_then(|p| clean(p.short_forecast.as_deref()));
    let hourly_state = precipitation_state(hourly_text.as_deref());
    let minutely = data.minutely_precipitation.as_ref();
    let minutely_text = minutely.and_then(|m| clean(m.summary.as_deref()));
    let minutely_state = minutely_state(minutely);

    let fs = &attribution.field_sources;
    let current_source = format_source(fs.get("condition"));
    let hourly_source = format_source(fs.get("hourly_source"));
    let minutely_source = format_source(
        fs.get("minutely_precipitation")
            .filter(|s| !s.is_empty())
            .or(fs.get("hourly_summary")),
    );

    let mut parts = Vec::new();
    if let (Some(text), Some(state)) = (&hourly_text, hourly_state) {
        if state != current_state {
            parts.push(format!("hourly forecast from {hourly_source} says {text}"));
        }
    }
    if let (Some(text), Some(state)) = (&minutely_text, minutely_state) {
        if state != current_state {
            parts.push(format!(
                "minute-by-minute precipitation outlook from {minutely_source} says {text}"
            ));
        }
    }
    if parts.is_empty() {
        return None;
    }
    Some(format!(
        "Data note: current conditions from {current_source} report {current_text}; {}.",
        parts.join("; ")
    ))
}
