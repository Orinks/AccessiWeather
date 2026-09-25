//! Rule-based outdoor, driving and allergy guidance.
//!
//! Port of `accessiweather/impact_summary.py`.

use crate::display::models::ImpactSummary;
use crate::model::{CurrentConditions, EnvironmentalConditions, ForecastPeriod};

/// `_OUTDOOR_TEMP_BANDS`: (upper bound exclusive, label).
const OUTDOOR_TEMP_BANDS: &[(f64, &str)] = &[
    (0.0, "Dangerous cold - avoid prolonged outdoor exposure"),
    (
        15.0,
        "Extreme cold - dress in heavy layers, limit time outside",
    ),
    (25.0, "Very cold - heavy winter clothing required"),
    (32.0, "Cold - wear a heavy coat"),
    (50.0, "Cool - coat or warm jacket recommended"),
    (60.0, "Mild - light jacket may be needed"),
    (78.0, "Comfortable - good conditions for outdoor activities"),
    (85.0, "Warm - pleasant for most outdoor activities"),
    (95.0, "Hot - stay hydrated and seek shade during peak hours"),
    (105.0, "Very hot - limit strenuous outdoor activity"),
    (f64::INFINITY, "Extreme heat - avoid outdoor exertion"),
];

const PRECIP_CONDITION_KEYWORDS: &[&str] = &[
    "rain", "snow", "storm", "drizzle", "shower", "sleet", "hail", "flurr",
];
const ICE_KEYWORDS: &[&str] = &["ice", "freezing", "sleet", "glaze"];
const SNOW_KEYWORDS: &[&str] = &["snow", "blizzard", "flurr"];
const RAIN_KEYWORDS: &[&str] = &["rain", "downpour", "drizzle", "shower"];
const THUNDER_KEYWORDS: &[&str] = &["thunder", "storm", "lightning"];

fn has_keyword(text: &str, keywords: &[&str]) -> bool {
    let lower = text.to_lowercase();
    keywords.iter().any(|k| lower.contains(k))
}

/// `_outdoor_from_conditions`.
fn outdoor_from_conditions(
    feels_like_f: Option<f64>,
    temp_f: Option<f64>,
    uv_index: Option<f64>,
    condition: Option<&str>,
) -> Option<String> {
    let reference = feels_like_f.or(temp_f)?;
    if !reference.is_finite() {
        return None;
    }
    let comfort = OUTDOOR_TEMP_BANDS
        .iter()
        .find(|(upper, _)| reference < *upper)
        .map(|(_, label)| *label)?;
    let mut modifiers: Vec<&str> = Vec::new();
    if let Some(uv) = uv_index {
        if uv >= 8.0 {
            modifiers.push("UV very high - sun protection essential");
        } else if uv >= 6.0 {
            modifiers.push("wear sunscreen");
        }
    }
    if has_keyword(condition.unwrap_or(""), PRECIP_CONDITION_KEYWORDS) {
        modifiers.push("active precipitation - bring appropriate gear");
    }
    Some(if modifiers.is_empty() {
        comfort.to_string()
    } else {
        format!("{comfort}; {}", modifiers.join("; "))
    })
}

/// `_driving_from_conditions`.
fn driving_from_conditions(
    visibility_miles: Option<f64>,
    wind_speed_mph: Option<f64>,
    wind_gust_mph: Option<f64>,
    temp_f: Option<f64>,
    condition: Option<&str>,
    precipitation_type: Option<&[String]>,
) -> String {
    let mut issues: Vec<&str> = Vec::new();
    if let Some(v) = visibility_miles {
        if v < 0.25 {
            issues.push("near-zero visibility - do not drive unless essential");
        } else if v < 1.0 {
            issues.push("very low visibility - drive with extreme caution");
        } else if v < 3.0 {
            issues.push("reduced visibility - drive carefully");
        }
    }

    let condition = condition.unwrap_or("");
    let precip_text = format!(
        "{} {condition}",
        precipitation_type.unwrap_or_default().join(" ")
    );
    if has_keyword(&precip_text, ICE_KEYWORDS) {
        issues.push("ice possible - slow down, allow extra stopping distance");
    } else if has_keyword(&precip_text, SNOW_KEYWORDS) {
        issues.push("snow on roads - reduce speed and increase following distance");
    } else if has_keyword(&precip_text, THUNDER_KEYWORDS) {
        issues.push("thunderstorms - avoid driving if possible");
    } else if has_keyword(&precip_text, RAIN_KEYWORDS) {
        issues.push("wet roads - allow extra stopping distance");
    }

    if temp_f.is_some_and(|t| (25.0..=36.0).contains(&t)) {
        let moisture = has_keyword(
            condition,
            &[
                "rain", "drizzle", "snow", "sleet", "cloud", "fog", "mist", "overcast",
            ],
        );
        if moisture && !issues.iter().any(|i| i.contains("ice")) {
            issues.push("near-freezing temperatures - watch for black ice");
        }
    }

    let effective_wind = wind_speed_mph
        .unwrap_or(0.0)
        .max(wind_gust_mph.unwrap_or(0.0));
    if effective_wind >= 45.0 {
        issues.push("dangerous winds - high-profile vehicles at serious risk");
    } else if effective_wind >= 30.0 {
        issues.push("high winds - caution especially for tall vehicles");
    } else if effective_wind >= 20.0 {
        issues.push("gusty winds - minor effect on steering");
    }

    if issues.is_empty() {
        "Normal driving conditions".into()
    } else {
        format!("Caution: {}", issues.join("; "))
    }
}

fn pollen_rank(category: &str) -> i32 {
    match category {
        "None" => 0,
        "Very Low" => 1,
        "Low" => 2,
        "Moderate" => 3,
        "High" => 4,
        "Very High" => 5,
        "Extreme" => 6,
        _ => -1,
    }
}

fn air_quality_rank(category: &str) -> i32 {
    match category {
        "Good" => 1,
        "Moderate" => 2,
        "Unhealthy for Sensitive Groups" => 3,
        "Unhealthy" => 4,
        "Very Unhealthy" => 5,
        "Hazardous" => 6,
        _ => 0,
    }
}

/// `_allergy_from_conditions`.
fn allergy_from_conditions(
    pollen_index: Option<f64>,
    pollen_category: Option<&str>,
    pollen_primary_allergen: Option<&str>,
    wind_speed_mph: Option<f64>,
    air_quality_category: Option<&str>,
) -> Option<String> {
    let mut parts: Vec<String> = Vec::new();
    let rank = pollen_rank(pollen_category.unwrap_or(""));
    let allergen = pollen_primary_allergen
        .filter(|a| !a.is_empty())
        .map(|a| format!(" ({a})"))
        .unwrap_or_default();

    if let Some(category) = pollen_category {
        parts.push(match rank {
            r if r >= 5 => format!("Very high pollen{allergen} - take allergy precautions"),
            4 => format!("High pollen{allergen} - sensitive individuals should limit exposure"),
            3 => {
                format!("Moderate pollen{allergen} - sensitive individuals may experience symptoms")
            }
            1 | 2 => format!("Low pollen{allergen}"),
            _ => format!("Pollen: {category}{allergen}"),
        });
    } else if let Some(index) = pollen_index {
        parts.push(
            if index >= 10.0 {
                "High pollen index - allergy precautions recommended"
            } else if index >= 5.0 {
                "Moderate pollen index"
            } else {
                "Low pollen index"
            }
            .into(),
        );
    }

    if !parts.is_empty() && wind_speed_mph.is_some_and(|w| w >= 15.0) && rank >= 3 {
        parts.push("wind increasing pollen dispersion".into());
    }

    let aq_rank = air_quality_rank(air_quality_category.unwrap_or(""));
    if aq_rank >= 4 {
        parts.push(format!(
            "air quality {} - limit outdoor exposure",
            air_quality_category.unwrap_or("")
        ));
    } else if aq_rank == 3 {
        parts.push("air quality unhealthy for sensitive groups".into());
    }

    (!parts.is_empty()).then(|| parts.join("; "))
}

/// `build_impact_summary`.
pub fn build_impact_summary(
    current: Option<&CurrentConditions>,
    environmental: Option<&EnvironmentalConditions>,
) -> ImpactSummary {
    let Some(current) = current else {
        return ImpactSummary::default();
    };
    let outdoor = outdoor_from_conditions(
        current.feels_like_f,
        current.temperature_f,
        current.uv_index,
        current.condition.as_deref(),
    );
    let driving = driving_from_conditions(
        current.visibility_miles,
        current.wind_speed_mph,
        current.wind_gust_mph,
        current.temperature_f,
        current.condition.as_deref(),
        current.precipitation_type.as_deref(),
    );
    let allergy = allergy_from_conditions(
        environmental.and_then(|e| e.pollen_index),
        environmental.and_then(|e| e.pollen_category.as_deref()),
        environmental.and_then(|e| e.pollen_primary_allergen.as_deref()),
        current.wind_speed_mph,
        environmental.and_then(|e| e.air_quality_category.as_deref()),
    );
    ImpactSummary {
        outdoor,
        driving: Some(driving),
        allergy,
    }
}

/// `build_forecast_impact_summary`.
pub fn build_forecast_impact_summary(period: &ForecastPeriod) -> ImpactSummary {
    let temp_f = period.temperature.map(|t| {
        if period.temperature_unit == "C" {
            t * 9.0 / 5.0 + 32.0
        } else {
            t
        }
    });
    let feels_f = period.feels_like_high.or(temp_f);
    // `uv_index_max or uv_index`: a zero maximum falls through.
    let uv = period
        .uv_index_max
        .filter(|u| *u != 0.0)
        .or(period.uv_index);
    let outdoor = outdoor_from_conditions(feels_f, temp_f, uv, period.short_forecast.as_deref());

    let wind_mph = period
        .wind_speed
        .as_deref()
        .map(numbers_in)
        .and_then(|nums| nums.into_iter().reduce(f64::max));

    let driving = driving_from_conditions(
        None,
        wind_mph,
        None,
        temp_f,
        period.short_forecast.as_deref(),
        period.precipitation_type.as_deref(),
    );
    let allergy = allergy_from_conditions(
        None,
        period.pollen_forecast.as_deref(),
        None,
        wind_mph,
        None,
    );
    ImpactSummary {
        outdoor,
        driving: Some(driving),
        allergy,
    }
}

/// `re.findall(r"\d+(?:\.\d+)?", text)` parsed as floats.
fn numbers_in(text: &str) -> Vec<f64> {
    let chars: Vec<char> = text.chars().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        if !chars[i].is_ascii_digit() {
            i += 1;
            continue;
        }
        let start = i;
        while i < chars.len() && chars[i].is_ascii_digit() {
            i += 1;
        }
        if i + 1 < chars.len() && chars[i] == '.' && chars[i + 1].is_ascii_digit() {
            i += 1;
            while i < chars.len() && chars[i].is_ascii_digit() {
                i += 1;
            }
        }
        let s: String = chars[start..i].iter().collect();
        if let Ok(v) = s.parse() {
            out.push(v);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn outdoor_bands_and_modifiers() {
        assert_eq!(
            outdoor_from_conditions(None, Some(72.0), Some(9.0), Some("Light Rain")).unwrap(),
            "Comfortable - good conditions for outdoor activities; UV very high - sun protection essential; active precipitation - bring appropriate gear"
        );
        assert_eq!(
            outdoor_from_conditions(Some(-5.0), Some(10.0), None, None).unwrap(),
            "Dangerous cold - avoid prolonged outdoor exposure"
        );
        assert_eq!(outdoor_from_conditions(None, None, None, None), None);
    }

    #[test]
    fn driving_priorities() {
        assert_eq!(
            driving_from_conditions(None, None, None, None, Some("Sunny"), None),
            "Normal driving conditions"
        );
        assert_eq!(
            driving_from_conditions(Some(0.5), Some(10.0), Some(32.0), Some(30.0), Some("Fog"), None),
            "Caution: very low visibility - drive with extreme caution; near-freezing temperatures - watch for black ice; high winds - caution especially for tall vehicles"
        );
        assert_eq!(
            driving_from_conditions(None, None, None, Some(30.0), Some("Freezing Rain"), None),
            "Caution: ice possible - slow down, allow extra stopping distance"
        );
    }

    #[test]
    fn allergy_rules() {
        assert_eq!(
            allergy_from_conditions(None, Some("High"), Some("Oak"), Some(20.0), Some("Unhealthy")).unwrap(),
            "High pollen (Oak) - sensitive individuals should limit exposure; wind increasing pollen dispersion; air quality Unhealthy - limit outdoor exposure"
        );
        assert_eq!(
            allergy_from_conditions(Some(6.0), None, None, None, None).unwrap(),
            "Moderate pollen index"
        );
        assert_eq!(
            allergy_from_conditions(None, None, None, None, Some("Good")),
            None
        );
    }

    #[test]
    fn forecast_wind_takes_the_largest_number() {
        assert_eq!(numbers_in("10 to 20.5 mph"), vec![10.0, 20.5]);
        let mut p = ForecastPeriod {
            name: "Today".into(),
            temperature: Some(40.0),
            wind_speed: Some("15 to 35 mph".into()),
            short_forecast: Some("Cloudy".into()),
            ..Default::default()
        };
        let s = build_forecast_impact_summary(&p);
        assert_eq!(
            s.driving.unwrap(),
            "Caution: high winds - caution especially for tall vehicles"
        );
        p.temperature_unit = "C".into();
        p.temperature = Some(0.0);
        let s = build_forecast_impact_summary(&p);
        assert_eq!(s.outdoor.unwrap(), "Cool - coat or warm jacket recommended");
    }
}
