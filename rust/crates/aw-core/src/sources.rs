//! Data source selection, ported from `weather_client_sources.py` /
//! `weather_client_auto.py`.

use std::fmt;

use crate::location::{is_us_location, Location};
use crate::settings::AppSettings;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum DataSource {
    Nws,
    OpenMeteo,
    PirateWeather,
}

impl DataSource {
    pub fn id(self) -> &'static str {
        match self {
            DataSource::Nws => "nws",
            DataSource::OpenMeteo => "openmeteo",
            DataSource::PirateWeather => "pirateweather",
        }
    }

    pub fn display_name(self) -> &'static str {
        match self {
            DataSource::Nws => "National Weather Service",
            DataSource::OpenMeteo => "Open-Meteo",
            DataSource::PirateWeather => "Pirate Weather",
        }
    }

    pub fn parse(id: &str) -> Option<Self> {
        match id.trim().to_lowercase().as_str() {
            "nws" => Some(DataSource::Nws),
            "openmeteo" | "open-meteo" | "open_meteo" => Some(DataSource::OpenMeteo),
            "pirateweather" | "pirate_weather" | "pirate-weather" => {
                Some(DataSource::PirateWeather)
            }
            _ => None,
        }
    }

    /// Maximum daily forecast days each provider can serve.
    pub fn max_forecast_days(self) -> u32 {
        match self {
            DataSource::Nws => 7,
            DataSource::PirateWeather => 8,
            DataSource::OpenMeteo => 16,
        }
    }
}

impl fmt::Display for DataSource {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.display_name())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ApiBudget {
    Economy,
    Balanced,
    MaxCoverage,
}

impl ApiBudget {
    pub fn parse(value: &str) -> Self {
        match value {
            "economy" => ApiBudget::Economy,
            "balanced" => ApiBudget::Balanced,
            _ => ApiBudget::MaxCoverage,
        }
    }
}

/// Which providers to query for a location and in which priority order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourcePlan {
    /// Providers in priority order. In auto mode with `MaxCoverage` all are
    /// fetched in parallel; otherwise only the primary plus fallbacks on failure.
    pub sources: Vec<DataSource>,
    pub auto_mode: bool,
    pub budget: ApiBudget,
    pub is_us: bool,
}

impl SourcePlan {
    pub fn primary(&self) -> Option<DataSource> {
        self.sources.first().copied()
    }

    /// Sources that should be fetched eagerly (before any failure fallback).
    pub fn eager_sources(&self) -> Vec<DataSource> {
        if self.auto_mode && self.budget == ApiBudget::MaxCoverage {
            self.sources.clone()
        } else {
            self.sources.iter().take(1).copied().collect()
        }
    }
}

/// Build the fetch plan for a location from the user's settings.
///
/// * Explicit `data_source` values (`nws`, `openmeteo`, `pirateweather`) are
///   honoured, except NWS is never used outside the US (Open-Meteo instead).
/// * `auto` follows `auto_sources_us` / `auto_sources_international`.
/// * Pirate Weather is only included when an API key is available.
pub fn plan_sources(
    settings: &AppSettings,
    location: &Location,
    has_pirate_key: bool,
) -> SourcePlan {
    let is_us = is_us_location(location);
    let budget = ApiBudget::parse(&settings.auto_mode_api_budget);
    let explicit = DataSource::parse(&settings.data_source);

    let mut sources: Vec<DataSource> = match explicit {
        Some(DataSource::Nws) if is_us => vec![DataSource::Nws, DataSource::OpenMeteo],
        Some(DataSource::Nws) => vec![DataSource::OpenMeteo],
        Some(DataSource::OpenMeteo) => vec![DataSource::OpenMeteo],
        Some(DataSource::PirateWeather) if has_pirate_key => {
            vec![DataSource::PirateWeather, DataSource::OpenMeteo]
        }
        Some(DataSource::PirateWeather) => vec![DataSource::OpenMeteo],
        None => {
            let configured = if is_us {
                &settings.auto_sources_us
            } else {
                &settings.auto_sources_international
            };
            let mut list: Vec<DataSource> = configured
                .iter()
                .filter_map(|s| DataSource::parse(s))
                .collect();
            if list.is_empty() {
                list = if is_us {
                    vec![
                        DataSource::Nws,
                        DataSource::OpenMeteo,
                        DataSource::PirateWeather,
                    ]
                } else {
                    vec![DataSource::OpenMeteo, DataSource::PirateWeather]
                };
            }
            list
        }
    };

    sources.retain(|s| match s {
        DataSource::Nws => is_us,
        DataSource::PirateWeather => has_pirate_key,
        DataSource::OpenMeteo => true,
    });
    dedupe(&mut sources);
    if sources.is_empty() {
        sources.push(DataSource::OpenMeteo);
    }

    // Requests beyond NWS's 7 day window prefer Open-Meteo for the daily forecast.
    if explicit.is_none() && is_us && settings.forecast_days() > 7 {
        if let Some(pos) = sources.iter().position(|s| *s == DataSource::OpenMeteo) {
            if pos != 0 && sources.first() == Some(&DataSource::Nws) {
                // Keep NWS first for current/alerts but make sure Open-Meteo is eager.
                sources.swap(1, pos);
            }
        }
    }

    SourcePlan {
        sources,
        auto_mode: explicit.is_none(),
        budget,
        is_us,
    }
}

fn dedupe(list: &mut Vec<DataSource>) {
    let mut seen = std::collections::HashSet::new();
    list.retain(|s| seen.insert(*s));
}

#[cfg(test)]
mod tests {
    use super::*;

    fn us() -> Location {
        Location::new("Denver", 39.7, -104.9).with_country("US")
    }
    fn intl() -> Location {
        Location::new("Berlin", 52.5, 13.4).with_country("DE")
    }

    #[test]
    fn auto_us_order_and_pirate_gate() {
        let s = AppSettings::default();
        let plan = plan_sources(&s, &us(), false);
        assert_eq!(plan.sources, vec![DataSource::Nws, DataSource::OpenMeteo]);
        assert!(plan.auto_mode);
        let plan = plan_sources(&s, &us(), true);
        assert_eq!(
            plan.sources,
            vec![
                DataSource::Nws,
                DataSource::OpenMeteo,
                DataSource::PirateWeather
            ]
        );
    }

    #[test]
    fn auto_international_never_uses_nws() {
        let s = AppSettings::default();
        let plan = plan_sources(&s, &intl(), true);
        assert_eq!(
            plan.sources,
            vec![DataSource::OpenMeteo, DataSource::PirateWeather]
        );
    }

    #[test]
    fn explicit_nws_outside_us_falls_back() {
        let s = AppSettings {
            data_source: "nws".into(),
            ..Default::default()
        };
        assert_eq!(
            plan_sources(&s, &intl(), false).sources,
            vec![DataSource::OpenMeteo]
        );
        assert_eq!(
            plan_sources(&s, &us(), false).sources,
            vec![DataSource::Nws, DataSource::OpenMeteo]
        );
    }

    #[test]
    fn economy_budget_fetches_primary_only() {
        let s = AppSettings {
            auto_mode_api_budget: "economy".into(),
            ..Default::default()
        };
        let plan = plan_sources(&s, &us(), true);
        assert_eq!(plan.eager_sources(), vec![DataSource::Nws]);
        let s = AppSettings::default();
        assert_eq!(plan_sources(&s, &us(), true).eager_sources().len(), 3);
    }
}
