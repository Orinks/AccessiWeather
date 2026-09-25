//! Air quality and pollen presentation.
//!
//! Port of the parts of `display/presentation/environmental.py` the app
//! uses: the air quality panel, pollen details and the UV category helper.
//! (`format_air_quality_summary`, `format_pollutant_details`,
//! `format_air_quality_brief` and the `environmental_hourly.py` formatters
//! are never called by the Python app.)

use chrono_tz::Tz;

use crate::display::models::AirQualityPresentation;
use crate::display::pyfmt::{round_int, title};
use crate::display::time::{format_display_datetime, PyDateTime, DEFAULT_DATE_FORMAT};
use crate::model::EnvironmentalConditions;
use crate::settings::AppSettings;

fn air_quality_guidance(category: &str) -> &'static str {
    match category {
        "Good" => "Air quality is satisfactory; enjoy normal outdoor activities.",
        "Moderate" => {
            "Air quality is acceptable. People unusually sensitive to air pollution should \
             reduce prolonged or heavy outdoor exertion."
        }
        "Unhealthy for Sensitive Groups" => {
            "Sensitive groups (people with lung or heart disease, older adults, children) \
             should reduce prolonged or heavy outdoor exertion."
        }
        "Unhealthy" => {
            "Everyone should reduce prolonged or heavy outdoor exertion; sensitive groups \
             should avoid extended time outdoors."
        }
        "Very Unhealthy" => "Avoid outdoor exertion and move activities indoors when possible.",
        "Hazardous" => "Avoid all outdoor activity and follow local emergency air quality guidance.",
        _ => "Monitor local guidance and limit exposure if you notice symptoms.",
    }
}

fn pollutant_label(code: &str) -> Option<&'static str> {
    Some(match code {
        "PM2_5" => "PM2.5",
        "PM10" => "PM10",
        "O3" | "OZONE" => "Ozone",
        "SO2" => "Sulfur Dioxide",
        "NO2" => "Nitrogen Dioxide",
        "CO" => "Carbon Monoxide",
        _ => return None,
    })
}

/// `_get_uv_category`: EPA/WHO UV category.
pub fn uv_category(uv_index: Option<f64>) -> Option<&'static str> {
    let uv = uv_index?;
    Some(if uv <= 2.0 {
        "Low"
    } else if uv <= 5.0 {
        "Moderate"
    } else if uv <= 7.0 {
        "High"
    } else if uv <= 10.0 {
        "Very High"
    } else {
        "Extreme"
    })
}

fn nonempty(s: &Option<String>) -> Option<&str> {
    s.as_deref().filter(|s| !s.is_empty())
}

/// `build_air_quality_panel`.
pub fn build_air_quality_panel(
    location_name: &str,
    environmental: &EnvironmentalConditions,
    settings: &AppSettings,
    location_zone: Option<Tz>,
) -> Option<AirQualityPresentation> {
    let index = environmental.air_quality_index;
    let pollutant = nonempty(&environmental.air_quality_pollutant);
    let category = nonempty(&environmental.air_quality_category);
    if index.is_none() && category.is_none() && pollutant.is_none() {
        return None;
    }

    // Python only ever tests this line for truthiness, so "" acts like None.
    let summary_line = summary_line(index, category).filter(|s| !s.is_empty());
    let pollutant_line = pollutant.map(pollutant_line);
    let updated_line = environmental.updated_at.map(|t| {
        let stamp = format_display_datetime(
            &PyDateTime::aware(t, location_zone),
            &settings.time_display_mode,
            settings.time_format_12hour,
            settings.show_timezone_suffix,
            DEFAULT_DATE_FORMAT,
        );
        format!("Updated {stamp}")
    });
    let guidance = air_quality_guidance(category.unwrap_or(""));
    let mut sources: Vec<String> = environmental
        .sources
        .iter()
        .filter(|s| !s.is_empty())
        .cloned()
        .collect();
    sources.sort();
    sources.dedup();

    let title = format!("Air quality for {location_name}");
    let mut lines = vec![title.clone()];
    let mut details = Vec::new();

    let pollen_line = pollen_line(environmental);
    if let Some(p) = &pollen_line {
        lines.push(format!("• {p}"));
        details.push(p.clone());
        if let Some(pd) = format_pollen_details(environmental) {
            details.push(pd);
        }
    }
    for line in [&summary_line, &pollutant_line, &updated_line]
        .into_iter()
        .flatten()
    {
        lines.push(format!("• {line}"));
        details.push(line.clone());
    }
    lines.push(format!("• Advice: {guidance}"));
    if !sources.is_empty() {
        lines.push(format!("Sources: {}", sources.join(", ")));
    }

    let mut summary = summary_line
        .clone()
        .unwrap_or_else(|| "Air quality data not available.".into());
    if let Some(p) = &pollutant_line {
        summary = format!("{summary} – {p}");
    }
    if let Some(p) = &pollen_line {
        summary = if summary_line.is_none() {
            p.clone()
        } else {
            format!("{summary}. {p}")
        };
    }

    Some(AirQualityPresentation {
        title,
        summary,
        guidance: Some(guidance.into()),
        details,
        fallback_text: lines.join("\n"),
        updated_at: updated_line,
        sources,
    })
}

/// `_build_summary_line`.
fn summary_line(index: Option<f64>, category: Option<&str>) -> Option<String> {
    if index.is_none() && category.is_none() {
        return None;
    }
    let mut parts: Vec<String> = Vec::new();
    if let Some(i) = index {
        parts.push(format!("AQI {}", round_int(i)));
    }
    if let Some(c) = category {
        let c = c.trim();
        parts.push(if parts.is_empty() {
            c.to_string()
        } else {
            format!("({c})")
        });
    }
    Some(parts.join(" ").trim().to_string())
}

/// `_build_pollutant_line`.
fn pollutant_line(pollutant: &str) -> String {
    let label = pollutant.trim().to_uppercase();
    let pretty = match pollutant_label(&label) {
        Some(p) => p.to_string(),
        None if label.contains('_') => title(&label.replace('_', " ")),
        None => label,
    };
    format!("Dominant pollutant: {pretty}")
}

/// `_build_pollen_line`.
fn pollen_line(env: &EnvironmentalConditions) -> Option<String> {
    let category = nonempty(&env.pollen_category);
    if env.pollen_index.is_none() && category.is_none() {
        return None;
    }
    let mut parts: Vec<String> = Vec::new();
    if let Some(c) = category {
        parts.push(format!("Pollen: {c}"));
    } else if let Some(i) = env.pollen_index {
        parts.push(format!("Pollen Index: {}", round_int(i)));
    }
    if let Some(a) = nonempty(&env.pollen_primary_allergen) {
        parts.push(format!("({a})"));
    }
    (!parts.is_empty()).then(|| parts.join(" "))
}

/// `format_pollen_details`: "Pollen Levels: Tree: 3, Grass: 1".
pub fn format_pollen_details(env: &EnvironmentalConditions) -> Option<String> {
    let items: Vec<String> = [
        ("Tree", env.pollen_tree_index),
        ("Grass", env.pollen_grass_index),
        ("Weed", env.pollen_weed_index),
    ]
    .into_iter()
    .filter_map(|(name, v)| v.map(|v| format!("{name}: {}", round_int(v))))
    .collect();
    (!items.is_empty()).then(|| format!("Pollen Levels: {}", items.join(", ")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn panel_combines_pollen_and_air_quality() {
        let env = EnvironmentalConditions {
            air_quality_index: Some(52.5),
            air_quality_category: Some("Moderate".into()),
            air_quality_pollutant: Some("pm2_5".into()),
            pollen_category: Some("High".into()),
            pollen_primary_allergen: Some("Oak".into()),
            pollen_tree_index: Some(4.5),
            sources: vec!["Open-Meteo".into(), "".into(), "AirNow".into(), "AirNow".into()],
            ..Default::default()
        };
        let p = build_air_quality_panel("Home", &env, &AppSettings::default(), None).unwrap();
        assert_eq!(p.summary, "AQI 52 (Moderate) – Dominant pollutant: PM2.5. Pollen: High (Oak)");
        assert_eq!(p.sources, ["AirNow", "Open-Meteo"]);
        assert_eq!(p.details[1], "Pollen Levels: Tree: 4");
        assert!(p.fallback_text.ends_with("Sources: AirNow, Open-Meteo"));
    }

    #[test]
    fn unknown_pollutant_codes_are_title_cased() {
        assert_eq!(pollutant_line("nh3_x"), "Dominant pollutant: Nh3 X");
        assert_eq!(pollutant_line("pm10"), "Dominant pollutant: PM10");
        assert_eq!(uv_category(Some(2.5)), Some("Moderate"));
    }
}
