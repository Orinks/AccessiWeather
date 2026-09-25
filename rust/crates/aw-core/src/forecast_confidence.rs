//! Forecast confidence from cross-source agreement.
//! Port of `accessiweather/forecast_confidence.py`; the result types live in
//! [`crate::model`].

use crate::model::{
    Forecast, ForecastConfidence, ForecastConfidenceLevel, ForecastPeriod, SourceData,
};

const TEMP_HIGH: f64 = 5.0;
const TEMP_MED: f64 = 10.0;
const PRECIP_HIGH: f64 = 15.0;
const PRECIP_MED: f64 = 25.0;

/// Human-readable name for a source id (`str.title()` for unknown ids).
pub fn source_display_name(source_id: &str) -> String {
    match source_id.to_lowercase().as_str() {
        "nws" => "NWS".into(),
        "openmeteo" => "Open-Meteo".into(),
        "pirateweather" => "Pirate Weather".into(),
        _ => title_case(source_id),
    }
}

/// Python's `str.title()`: upper-case letters that follow a non-letter.
fn title_case(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut previous_cased = false;
    for c in s.chars() {
        if previous_cased {
            out.extend(c.to_lowercase());
        } else {
            out.extend(c.to_uppercase());
        }
        previous_cased = c.is_alphabetic();
    }
    out
}

/// "A", "A and B", "A, B, and C".
fn join_sources(names: &[String]) -> String {
    match names {
        [] => String::new(),
        [one] => one.clone(),
        [a, b] => format!("{a} and {b}"),
        [rest @ .., last] => format!("{}, and {last}", rest.join(", ")),
    }
}

/// First period with a temperature that is not a night period, else the
/// first period (sources disagree on whether periods[0] is a high or a low).
fn representative_period(forecast: &Forecast) -> Option<&ForecastPeriod> {
    forecast
        .periods
        .iter()
        .find(|p| p.temperature.is_some() && !p.name.to_lowercase().contains("night"))
        .or(forecast.periods.first())
}

fn spread(values: &[f64]) -> Option<f64> {
    if values.len() < 2 {
        return None;
    }
    let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let min = values.iter().copied().fold(f64::INFINITY, f64::min);
    Some(max - min)
}

/// `calculate_forecast_confidence`: compare the representative period's
/// temperature and precipitation chance across the sources that have a forecast.
pub fn calculate_forecast_confidence(sources: &[SourceData]) -> ForecastConfidence {
    let valid: Vec<&SourceData> = sources
        .iter()
        .filter(|s| s.success && s.forecast.as_ref().is_some_and(Forecast::has_data))
        .collect();
    let names: Vec<String> = valid
        .iter()
        .map(|s| source_display_name(&s.source))
        .collect();
    let joined = join_sources(&names);
    let n = valid.len() as i64;
    let result = |level, rationale: String| ForecastConfidence {
        level,
        rationale,
        sources_compared: n,
        source_names: names.clone(),
    };

    match n {
        0 => {
            return result(
                ForecastConfidenceLevel::Low,
                "No forecast sources available".into(),
            )
        }
        1 => {
            return result(
                ForecastConfidenceLevel::Medium,
                format!("Based on {joined} — single source, no cross-reference available"),
            )
        }
        _ => {}
    }

    let mut temps = Vec::new();
    let mut precips = Vec::new();
    for s in &valid {
        if let Some(period) = s.forecast.as_ref().and_then(representative_period) {
            temps.extend(period.temperature);
            precips.extend(period.precipitation_probability);
        }
    }
    let temp_spread = spread(&temps).unwrap_or(0.0);

    if let Some(precip_spread) = spread(&precips) {
        if temp_spread <= TEMP_HIGH && precip_spread <= PRECIP_HIGH {
            return result(
                ForecastConfidenceLevel::High,
                format!("{joined} agree on temperature and precipitation"),
            );
        }
        if temp_spread <= TEMP_MED || precip_spread <= PRECIP_MED {
            return result(
                ForecastConfidenceLevel::Medium,
                format!("Moderate agreement between {joined}"),
            );
        }
        return result(
            ForecastConfidenceLevel::Low,
            format!("{joined} show significant disagreement on temperature or precipitation"),
        );
    }

    if temp_spread <= TEMP_HIGH {
        result(
            ForecastConfidenceLevel::High,
            format!("{joined} agree on temperature"),
        )
    } else if temp_spread <= TEMP_MED {
        result(
            ForecastConfidenceLevel::Medium,
            format!("Moderate temperature agreement between {joined}"),
        )
    } else {
        result(
            ForecastConfidenceLevel::Low,
            format!("{joined} show significant temperature disagreement"),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::golden::{self, field};

    #[test]
    fn golden_forecast_confidence() {
        let cases = golden::load("confidence/cases.json");
        for case in cases.as_array().unwrap() {
            let sources: Vec<SourceData> = field(case, "sources");
            let expected: ForecastConfidence = field(case, "confidence");
            assert_eq!(
                calculate_forecast_confidence(&sources),
                expected,
                "{}",
                case["name"]
            );
        }
    }

    #[test]
    fn display_names_and_joining() {
        assert_eq!(source_display_name("OpenMeteo"), "Open-Meteo");
        assert_eq!(source_display_name("visual_crossing"), "Visual_Crossing");
        assert_eq!(source_display_name("abc123def"), "Abc123Def");
        let names: Vec<String> = ["A", "B", "C"].iter().map(|s| s.to_string()).collect();
        assert_eq!(join_sources(&names), "A, B, and C");
        assert_eq!(join_sources(&names[..2]), "A and B");
    }
}
