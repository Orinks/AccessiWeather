//! Air quality index standards: the US EPA AQI and the European (EEA) AQI.
//!
//! Open-Meteo serves both indexes; AirNow serves only the US one. The
//! "Air quality index" setting picks one, or "auto" picks the European
//! index for locations in Europe and the US index everywhere else.

use serde::{Deserialize, Serialize};

use crate::countries;
use crate::location::Location;

/// The scale an AQI value and its category belong to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AqiStandard {
    /// US EPA AQI, 0-500.
    Us,
    /// European Air Quality Index (EEA scale as served by Open-Meteo).
    European,
}

const US_CATEGORIES: [&str; 6] = [
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
];

const EUROPEAN_CATEGORIES: [&str; 6] = [
    "Good",
    "Fair",
    "Moderate",
    "Poor",
    "Very poor",
    "Extremely poor",
];

impl AqiStandard {
    /// The index name shown next to every value, so a number is never
    /// read without its scale.
    pub fn name(self) -> &'static str {
        match self {
            Self::Us => "US AQI",
            Self::European => "European AQI",
        }
    }

    /// The category a value falls in on this scale.
    pub fn category(self, value: f64) -> &'static str {
        match self {
            Self::Us => air_quality_category(value),
            Self::European => {
                let i = if value <= 20.0 {
                    0
                } else if value <= 40.0 {
                    1
                } else if value <= 60.0 {
                    2
                } else if value <= 80.0 {
                    3
                } else if value <= 100.0 {
                    4
                } else {
                    5
                };
                EUROPEAN_CATEGORIES[i]
            }
        }
    }

    /// Every category, best first.
    pub fn categories(self) -> &'static [&'static str] {
        match self {
            Self::Us => &US_CATEGORIES,
            Self::European => &EUROPEAN_CATEGORIES,
        }
    }

    /// Position of `category` in [`categories`](Self::categories), ignoring case.
    pub fn rank(self, category: &str) -> Option<usize> {
        let category = category.trim();
        self.categories()
            .iter()
            .position(|c| c.eq_ignore_ascii_case(category))
    }
}

/// AQI category by EPA breakpoints.
pub fn air_quality_category(value: f64) -> &'static str {
    if value <= 50.0 {
        "Good"
    } else if value <= 100.0 {
        "Moderate"
    } else if value <= 150.0 {
        "Unhealthy for Sensitive Groups"
    } else if value <= 200.0 {
        "Unhealthy"
    } else if value <= 300.0 {
        "Very Unhealthy"
    } else {
        "Hazardous"
    }
}

/// The "Air quality index" setting.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum AqiPreference {
    /// European AQI in Europe, US AQI elsewhere.
    #[default]
    Auto,
    Us,
    European,
}

impl AqiPreference {
    /// `"us"` and `"european"`; anything else is automatic.
    pub fn from_setting(value: &str) -> Self {
        match value.trim().to_ascii_lowercase().as_str() {
            "us" => Self::Us,
            "european" => Self::European,
            _ => Self::Auto,
        }
    }

    /// The standard to use for `location`. Automatic picks European only
    /// when the location's country code is European; an unknown country
    /// keeps the US index.
    pub fn resolve(self, location: &Location) -> AqiStandard {
        match self {
            Self::Us => AqiStandard::Us,
            Self::European => AqiStandard::European,
            Self::Auto => {
                if location
                    .country_code
                    .as_deref()
                    .is_some_and(countries::is_european)
                {
                    AqiStandard::European
                } else {
                    AqiStandard::Us
                }
            }
        }
    }
}

/// [`AqiPreference::resolve`] for a raw setting value.
pub fn resolve_standard(preference: &str, location: &Location) -> AqiStandard {
    AqiPreference::from_setting(preference).resolve(location)
}

/// Health advice for a category of `standard`.
pub fn guidance(standard: AqiStandard, category: &str) -> &'static str {
    match standard {
        AqiStandard::Us => match category {
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
            "Hazardous" => {
                "Avoid all outdoor activity and follow local emergency air quality guidance."
            }
            _ => "Monitor local guidance and limit exposure if you notice symptoms.",
        },
        AqiStandard::European => match category {
            "Good" => "Air quality is good; enjoy your usual outdoor activities.",
            "Fair" => "Enjoy your usual outdoor activities.",
            "Moderate" => {
                "Enjoy your usual outdoor activities. Sensitive groups should consider reducing \
                 intense outdoor activity if they have symptoms."
            }
            "Poor" => {
                "Consider reducing intense outdoor activity if you have symptoms such as sore \
                 eyes, a cough or a sore throat. Sensitive groups should reduce outdoor exertion."
            }
            "Very poor" => {
                "Everyone should reduce outdoor exertion; sensitive groups should avoid it."
            }
            "Extremely poor" => {
                "Avoid outdoor exertion and follow local health advice; sensitive groups should \
                 stay indoors."
            }
            _ => "Monitor local guidance and limit exposure if you notice symptoms.",
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn european_band_edges() {
        let e = AqiStandard::European;
        for (value, category) in [
            (0.0, "Good"),
            (20.0, "Good"),
            (20.1, "Fair"),
            (40.0, "Fair"),
            (60.0, "Moderate"),
            (80.0, "Poor"),
            (100.0, "Very poor"),
            (101.0, "Extremely poor"),
        ] {
            assert_eq!(e.category(value), category, "{value}");
        }
    }

    #[test]
    fn us_bands_unchanged() {
        assert_eq!(AqiStandard::Us.category(50.0), "Good");
        assert_eq!(
            AqiStandard::Us.category(101.0),
            "Unhealthy for Sensitive Groups"
        );
        assert_eq!(AqiStandard::Us.category(301.0), "Hazardous");
    }

    #[test]
    fn names_and_serde() {
        assert_eq!(AqiStandard::Us.name(), "US AQI");
        assert_eq!(AqiStandard::European.name(), "European AQI");
        assert_eq!(
            serde_json::to_value(AqiStandard::European).unwrap(),
            "european"
        );
        assert_eq!(
            serde_json::from_value::<AqiStandard>("us".into()).unwrap(),
            AqiStandard::Us
        );
    }

    #[test]
    fn resolve_by_country() {
        let at = |code: Option<&str>| {
            let mut l = Location::new("x", 48.85, 2.35);
            l.country_code = code.map(str::to_string);
            l
        };
        for code in ["DE", "GB", "CH", "NO", "gb"] {
            assert_eq!(
                resolve_standard("auto", &at(Some(code))),
                AqiStandard::European,
                "{code}"
            );
        }
        for code in [Some("US"), Some("BR"), Some("RU"), Some("TR"), None] {
            assert_eq!(
                resolve_standard("auto", &at(code)),
                AqiStandard::Us,
                "{code:?}"
            );
        }
        // Coordinates in Paris but no country: stays US AQI.
        assert_eq!(resolve_standard("", &at(None)), AqiStandard::Us);
        assert_eq!(resolve_standard("us", &at(Some("FR"))), AqiStandard::Us);
        assert_eq!(
            resolve_standard("european", &at(Some("US"))),
            AqiStandard::European
        );
    }

    #[test]
    fn ranks_and_guidance() {
        assert_eq!(AqiStandard::European.rank("very poor"), Some(4));
        assert_eq!(AqiStandard::European.rank("Unhealthy"), None);
        assert_eq!(AqiStandard::Us.rank("Hazardous"), Some(5));
        for standard in [AqiStandard::Us, AqiStandard::European] {
            let fallback = guidance(standard, "");
            for category in standard.categories() {
                assert_ne!(guidance(standard, category), fallback, "{category}");
            }
        }
        assert!(guidance(AqiStandard::European, "Poor").contains("sore throat"));
    }
}
