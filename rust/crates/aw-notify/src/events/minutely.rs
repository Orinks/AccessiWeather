//! Minutely precipitation transition and likelihood detection, ported from
//! `notifications/minutely_precipitation.py` (parsing the Pirate Weather
//! payload belongs to the provider layer and is not here).

use aw_core::model::{MinutelyPrecipitationForecast, MinutelyPrecipitationPoint};

pub const NO_TRANSITION_SIGNATURE: &str = "__none__";
pub const NO_LIKELIHOOD_SIGNATURE: &str = "__no_likelihood__";
pub const INTENSITY_THRESHOLD_LIGHT: f64 = 0.01;
pub const INTENSITY_THRESHOLD_MODERATE: f64 = 0.1;
pub const INTENSITY_THRESHOLD_HEAVY: f64 = 1.0;
/// Transitions further out than this are held back until they are near.
pub const TRANSITION_NOTICE_LEAD_MINUTES: usize = 10;

/// `SENSITIVITY_THRESHOLDS` (unknown values fall back to "light").
pub fn sensitivity_threshold(sensitivity: &str) -> f64 {
    match sensitivity {
        "moderate" => INTENSITY_THRESHOLD_MODERATE,
        "heavy" => INTENSITY_THRESHOLD_HEAVY,
        _ => INTENSITY_THRESHOLD_LIGHT,
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Transition {
    /// "starting" or "stopping".
    pub transition_type: &'static str,
    pub minutes_until: usize,
    pub precipitation_type: Option<String>,
}

impl Transition {
    pub fn event_type(&self) -> &'static str {
        if self.transition_type == "starting" {
            "minutely_precipitation_start"
        } else {
            "minutely_precipitation_stop"
        }
    }

    /// e.g. "Rain starting in 5 minutes".
    pub fn title(&self) -> String {
        let unit = if self.minutes_until == 1 {
            "minute"
        } else {
            "minutes"
        };
        format!(
            "{} {} in {} {unit}",
            precipitation_type_label(self.precipitation_type.as_deref()),
            self.transition_type,
            self.minutes_until
        )
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Likelihood {
    pub max_probability: f64,
    pub precipitation_type: Option<String>,
    pub probability_band: &'static str,
}

impl Likelihood {
    pub const EVENT_TYPE: &'static str = "minutely_precipitation_likelihood";

    /// e.g. "Rain likely in the next hour (75% chance)".
    pub fn title(&self) -> String {
        format!(
            "{} likely in the next hour ({}% chance)",
            precipitation_type_label(self.precipitation_type.as_deref()),
            (self.max_probability * 100.0) as i64
        )
    }
}

/// `is_wet`: intensity (less its error bar) above the threshold, else any
/// probability.
pub fn is_wet(point: &MinutelyPrecipitationPoint, threshold: f64) -> bool {
    if let Some(intensity) = point.precipitation_intensity {
        return match point.precipitation_intensity_error {
            Some(error) if error > 0.0 => intensity - error > threshold,
            _ => intensity > threshold,
        };
    }
    point.precipitation_probability.is_some_and(|p| p > 0.0)
}

pub fn precipitation_type_label(precipitation_type: Option<&str>) -> &'static str {
    match precipitation_type {
        Some("sleet") => "Sleet",
        Some("snow") => "Snow",
        Some("hail") => "Hail",
        Some("freezing-rain") => "Freezing rain",
        Some("ice") => "Ice",
        Some("rain") => "Rain",
        _ => "Precipitation",
    }
}

fn first_precipitation_type(
    points: &[MinutelyPrecipitationPoint],
    threshold: f64,
) -> Option<String> {
    points
        .iter()
        .find(|p| {
            is_wet(p, threshold)
                && p.precipitation_type
                    .as_deref()
                    .is_some_and(|t| !t.is_empty())
        })
        .and_then(|p| p.precipitation_type.clone())
}

/// `detect_minutely_precipitation_transition`: the first dry/wet flip.
pub fn detect_transition(
    forecast: Option<&MinutelyPrecipitationForecast>,
    threshold: f64,
) -> Option<Transition> {
    let points = &forecast?.points;
    let baseline_wet = is_wet(points.first()?, threshold);
    let idx = points
        .iter()
        .skip(1)
        .position(|p| is_wet(p, threshold) != baseline_wet)?
        + 1;
    Some(if baseline_wet {
        Transition {
            transition_type: "stopping",
            minutes_until: idx,
            precipitation_type: first_precipitation_type(&points[..idx], threshold),
        }
    } else {
        Transition {
            transition_type: "starting",
            minutes_until: idx,
            precipitation_type: first_precipitation_type(&points[idx..], threshold),
        }
    })
}

/// `build_minutely_transition_signature` (excludes the countdown).
pub fn transition_signature(
    forecast: Option<&MinutelyPrecipitationForecast>,
    threshold: f64,
) -> Option<String> {
    if forecast?.points.is_empty() {
        return None;
    }
    Some(match detect_transition(forecast, threshold) {
        None => NO_TRANSITION_SIGNATURE.to_string(),
        Some(t) => format!(
            "{}:{}",
            t.transition_type,
            t.precipitation_type.as_deref().unwrap_or("precipitation")
        ),
    })
}

fn probability_band(prob: f64) -> &'static str {
    if prob >= 0.9 {
        "90%+"
    } else if prob >= 0.7 {
        "70-90%"
    } else {
        "50-70%"
    }
}

/// `detect_minutely_precipitation_likelihood`: only while it is dry now.
pub fn detect_likelihood(
    forecast: Option<&MinutelyPrecipitationForecast>,
    threshold: f64,
) -> Option<Likelihood> {
    let points = &forecast?.points;
    if is_wet(points.first()?, 0.0) {
        return None;
    }
    let mut max_prob = 0.0;
    let mut max_type = None;
    for p in points {
        if let Some(prob) = p.precipitation_probability {
            if prob > max_prob {
                max_prob = prob;
                max_type = p.precipitation_type.clone();
            }
        }
    }
    if max_prob < threshold {
        return None;
    }
    Some(Likelihood {
        max_probability: max_prob,
        precipitation_type: max_type,
        probability_band: probability_band(max_prob),
    })
}

/// `build_minutely_likelihood_signature`.
pub fn likelihood_signature(
    forecast: Option<&MinutelyPrecipitationForecast>,
    threshold: f64,
) -> Option<String> {
    if forecast?.points.is_empty() {
        return None;
    }
    Some(match detect_likelihood(forecast, threshold) {
        None => NO_LIKELIHOOD_SIGNATURE.to_string(),
        Some(l) => format!(
            "likelihood:{}:{}",
            l.probability_band,
            l.precipitation_type.as_deref().unwrap_or("precipitation")
        ),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn point(
        intensity: Option<f64>,
        prob: Option<f64>,
        kind: Option<&str>,
    ) -> MinutelyPrecipitationPoint {
        MinutelyPrecipitationPoint {
            time: "2026-09-25T12:00:00Z".parse().unwrap(),
            precipitation_intensity: intensity,
            precipitation_probability: prob,
            precipitation_type: kind.map(str::to_string),
            precipitation_intensity_unit: "mm/hr".into(),
            precipitation_intensity_error: None,
            precipitation_intensity_error_unit: "mm/hr".into(),
        }
    }

    #[test]
    fn start_transition_and_signature() {
        let mut points = vec![point(Some(0.0), Some(0.0), None); 4];
        points.push(point(Some(0.5), Some(0.8), Some("rain")));
        let f = MinutelyPrecipitationForecast {
            points,
            ..Default::default()
        };
        let t = detect_transition(Some(&f), 0.0).unwrap();
        assert_eq!(t.title(), "Rain starting in 4 minutes");
        assert_eq!(
            transition_signature(Some(&f), 0.0).as_deref(),
            Some("starting:rain")
        );
        let l = detect_likelihood(Some(&f), 0.5).unwrap();
        assert_eq!(l.title(), "Rain likely in the next hour (80% chance)");
        assert_eq!(
            likelihood_signature(Some(&f), 0.5).as_deref(),
            Some("likelihood:70-90%:rain")
        );
    }

    #[test]
    fn error_bar_lowers_intensity() {
        let mut p = point(Some(0.05), None, None);
        p.precipitation_intensity_error = Some(0.045);
        assert!(!is_wet(&p, INTENSITY_THRESHOLD_LIGHT));
        assert!(is_wet(&point(None, Some(0.1), None), 1.0));
    }
}
