//! Which weather source(s) to ask, and how much. Port of the pure decisions
//! in `accessiweather/weather_client_sources.py`, `weather_client_base.py`
//! and the staged automatic-mode budget rules in `weather_client_auto.py`.
//!
//! Supersedes the legacy [`crate::sources`] planner, which only the legacy
//! `aw_providers::weather_client` still uses.

use crate::location::Location;
use crate::units::{resolve_auto_unit_system, DisplayUnitSystem};

pub const NWS: &str = "nws";
pub const OPENMETEO: &str = "openmeteo";
pub const PIRATEWEATHER: &str = "pirateweather";

const VALID_DATA_SOURCES: [&str; 4] = ["auto", NWS, OPENMETEO, PIRATEWEATHER];

/// Normalise the configured `data_source` ("auto" when unrecognised).
pub fn normalize_data_source(data_source: &str) -> &str {
    if VALID_DATA_SOURCES.contains(&data_source) {
        data_source
    } else {
        "auto"
    }
}

/// `_determine_api_choice`: the single API used outside automatic mode.
/// Pirate Weather without a key falls back to NWS (US) or Open-Meteo.
pub fn determine_api_choice(data_source: &str, has_pirate_key: bool, is_us: bool) -> &'static str {
    let regional = if is_us { NWS } else { OPENMETEO };
    match normalize_data_source(data_source) {
        PIRATEWEATHER if has_pirate_key => PIRATEWEATHER,
        OPENMETEO => OPENMETEO,
        NWS => NWS,
        _ => regional,
    }
}

/// Display name used in log lines ("Using NWS API for ...").
pub fn api_display_name(api: &str) -> &'static str {
    match api {
        OPENMETEO => "Open-Meteo",
        PIRATEWEATHER => "Pirate Weather",
        _ => "NWS",
    }
}

/// `_get_forecast_days_for_source`: configured days clamped to 3..=16 and
/// to the source's own limit.
pub fn forecast_days_for_source(forecast_duration_days: i64, source: &str) -> i64 {
    let configured = forecast_duration_days.clamp(3, 16);
    let limit = match source {
        PIRATEWEATHER => 8,
        NWS => 7,
        _ => 16,
    };
    configured.min(limit)
}

/// `_get_hourly_hours_for_pressure_outlook`: enough hours for the hourly
/// display and the pressure/temperature trend window.
pub fn hourly_hours_for_pressure_outlook(hourly_forecast_hours: i64, trend_hours: i64) -> i64 {
    let hourly = if hourly_forecast_hours == 0 {
        6
    } else {
        hourly_forecast_hours
    };
    let trend = if trend_hours == 0 { 24 } else { trend_hours };
    hourly.max(trend).clamp(1, 384)
}

/// `_should_use_openmeteo_for_extended_forecast`: only automatic mode, only
/// US locations, only when more than NWS's 7 days are wanted.
pub fn should_use_openmeteo_for_extended_forecast(
    source: &str,
    is_us: bool,
    forecast_duration_days: i64,
) -> bool {
    source.trim().to_lowercase() == "auto"
        && is_us
        && forecast_days_for_source(forecast_duration_days, OPENMETEO) > 7
}

/// `_resolve_pirate_weather_units`: the Pirate Weather `units` bundle.
pub fn resolve_pirate_weather_units(temperature_unit: &str, location: &Location) -> &'static str {
    let preference = temperature_unit.trim().to_lowercase();
    let preference = if preference.is_empty() {
        "both".to_string()
    } else {
        preference
    };
    if preference == "auto" {
        return match resolve_auto_unit_system(Some(location)) {
            DisplayUnitSystem::Us => "us",
            DisplayUnitSystem::Uk => "uk",
            DisplayUnitSystem::Ca => "ca",
            DisplayUnitSystem::Si => "si",
        };
    }
    if preference == "c" || preference == "celsius" {
        "ca"
    } else {
        "us"
    }
}

/// Automatic-mode API budget.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AutoBudget {
    Economy,
    Balanced,
    MaxCoverage,
}

impl AutoBudget {
    /// `_get_auto_mode_api_budget`: unknown values mean max coverage.
    pub fn parse(value: &str) -> Self {
        match value {
            "economy" => Self::Economy,
            "balanced" => Self::Balanced,
            _ => Self::MaxCoverage,
        }
    }
}

/// The settings validation for `auto_sources_us` / `auto_sources_international`:
/// keep known source ids; fall back to the regional default when none remain.
pub fn validated_auto_sources(configured: &[String], is_us_setting: bool) -> Vec<String> {
    let filtered: Vec<String> = configured
        .iter()
        .filter(|s| [NWS, OPENMETEO, PIRATEWEATHER].contains(&s.as_str()))
        .cloned()
        .collect();
    if !filtered.is_empty() {
        return filtered;
    }
    let default: &[&str] = if is_us_setting {
        &[NWS, OPENMETEO, PIRATEWEATHER]
    } else {
        &[OPENMETEO, PIRATEWEATHER]
    };
    default.iter().map(|s| s.to_string()).collect()
}

/// Sources automatic mode can fetch right now: configured for the region,
/// NWS only for US locations, Pirate Weather only with an API key.
pub fn auto_fetchable_sources(
    active: &[String],
    is_us: bool,
    has_pirate_key: bool,
) -> Vec<&'static str> {
    let wanted = |s: &str| active.iter().any(|a| a == s);
    let mut out = Vec::new();
    if wanted(OPENMETEO) {
        out.push(OPENMETEO);
    }
    if is_us && wanted(NWS) {
        out.push(NWS);
    }
    if has_pirate_key && wanted(PIRATEWEATHER) {
        out.push(PIRATEWEATHER);
    }
    out
}

/// `_configured_sources_in_fetch_order`: fetchable sources in the user's
/// configured order, skipping ones already fetched.
pub fn configured_sources_in_fetch_order(
    active: &[String],
    fetchable: &[&str],
    fetched: &[String],
) -> Vec<String> {
    active
        .iter()
        .filter(|s| fetchable.contains(&s.as_str()) && !fetched.contains(s))
        .cloned()
        .collect()
}

/// The first automatic-mode request: every fetchable source for max
/// coverage, otherwise just the first configured one.
pub fn auto_initial_sources(
    budget: AutoBudget,
    active: &[String],
    fetchable: &[&str],
) -> Vec<String> {
    if budget == AutoBudget::MaxCoverage {
        return active
            .iter()
            .filter(|s| fetchable.contains(&s.as_str()))
            .cloned()
            .collect();
    }
    configured_sources_in_fetch_order(active, fetchable, &[])
        .into_iter()
        .take(1)
        .collect()
}

/// What the staged (economy/balanced) mode knows after the primary fetch.
#[derive(Debug, Clone)]
pub struct AutoPrimaryOutcome<'a> {
    pub is_us: bool,
    pub active: &'a [String],
    pub fetchable: &'a [&'a str],
    /// Sources already fetched (in result order).
    pub fetched: &'a [String],
    pub primary_source: Option<&'a str>,
    /// The first result had current, daily and hourly data.
    pub core_complete: bool,
    /// `should_use_openmeteo_for_extended_forecast("auto", ...)`.
    pub wants_extended_forecast: bool,
}

/// The single follow-up source staged automatic mode asks for, if any.
pub fn auto_secondary_sources(outcome: &AutoPrimaryOutcome) -> Vec<String> {
    let o = outcome;
    let fetched = |s: &str| o.fetched.iter().any(|f| f == s);
    let fetchable = |s: &str| o.fetchable.contains(&s);

    let needs_us_extended_openmeteo =
        o.is_us && fetchable(OPENMETEO) && !fetched(OPENMETEO) && o.wants_extended_forecast;
    let needs_us_core_fallback =
        o.is_us && !o.core_complete && o.active.iter().any(|s| !fetched(s) && fetchable(s));
    let needs_intl_alert_source =
        !o.is_us && o.primary_source == Some(OPENMETEO) && !fetched(PIRATEWEATHER);
    let needs_intl_core_fallback = !o.is_us && !o.core_complete;

    let remaining = configured_sources_in_fetch_order(o.active, o.fetchable, o.fetched);
    let pick = |predicate: &dyn Fn(&str) -> bool| -> Vec<String> {
        remaining
            .iter()
            .find(|s| predicate(s))
            .map(|s| vec![s.clone()])
            .unwrap_or_default()
    };
    if needs_us_extended_openmeteo {
        pick(&|s| s == OPENMETEO)
    } else if needs_us_core_fallback {
        pick(&|_| true)
    } else if needs_intl_alert_source {
        pick(&|s| s == PIRATEWEATHER)
    } else if needs_intl_core_fallback {
        pick(&|_| true)
    } else {
        Vec::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn list(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn api_choice_matches_python() {
        assert_eq!(determine_api_choice("pirateweather", false, true), "nws");
        assert_eq!(
            determine_api_choice("pirateweather", false, false),
            "openmeteo"
        );
        assert_eq!(
            determine_api_choice("pirateweather", true, false),
            "pirateweather"
        );
        assert_eq!(determine_api_choice("nws", false, false), "nws");
        assert_eq!(determine_api_choice("bogus", false, true), "nws");
        assert_eq!(determine_api_choice("auto", false, false), "openmeteo");
    }

    #[test]
    fn forecast_days_and_hours() {
        assert_eq!(forecast_days_for_source(10, "nws"), 7);
        assert_eq!(forecast_days_for_source(10, "pirateweather"), 8);
        assert_eq!(forecast_days_for_source(20, "openmeteo"), 16);
        assert_eq!(forecast_days_for_source(1, "openmeteo"), 3);
        assert_eq!(hourly_hours_for_pressure_outlook(6, 24), 24);
        assert_eq!(hourly_hours_for_pressure_outlook(48, 24), 48);
        assert_eq!(hourly_hours_for_pressure_outlook(0, 0), 24);
        assert_eq!(hourly_hours_for_pressure_outlook(500, 1), 384);
    }

    #[test]
    fn extended_forecast_only_in_auto_for_us() {
        assert!(should_use_openmeteo_for_extended_forecast(
            " Auto ", true, 10
        ));
        assert!(!should_use_openmeteo_for_extended_forecast("nws", true, 10));
        assert!(!should_use_openmeteo_for_extended_forecast(
            "auto", false, 10
        ));
        assert!(!should_use_openmeteo_for_extended_forecast("auto", true, 7));
    }

    #[test]
    fn pirate_units() {
        let gb = Location::new("London", 51.5, -0.1).with_country("GB");
        assert_eq!(resolve_pirate_weather_units("auto", &gb), "uk");
        assert_eq!(resolve_pirate_weather_units("C", &gb), "ca");
        assert_eq!(resolve_pirate_weather_units("both", &gb), "us");
        assert_eq!(resolve_pirate_weather_units("", &gb), "us");
    }

    #[test]
    fn auto_sources_validation() {
        assert_eq!(
            validated_auto_sources(&list(&["bogus", "nws"]), true),
            list(&["nws"])
        );
        assert_eq!(
            validated_auto_sources(&list(&["bogus"]), false),
            list(&["openmeteo", "pirateweather"])
        );
    }

    #[test]
    fn staged_budget_rules() {
        let active = list(&["nws", "pirateweather", "openmeteo"]);
        let fetchable = auto_fetchable_sources(&active, true, true);
        assert_eq!(
            auto_initial_sources(AutoBudget::Economy, &active, &fetchable),
            list(&["nws"])
        );
        assert_eq!(
            auto_initial_sources(AutoBudget::MaxCoverage, &active, &fetchable).len(),
            3
        );
        let fetched = list(&["nws"]);
        let outcome = AutoPrimaryOutcome {
            is_us: true,
            active: &active,
            fetchable: &fetchable,
            fetched: &fetched,
            primary_source: Some("nws"),
            core_complete: true,
            wants_extended_forecast: true,
        };
        assert_eq!(auto_secondary_sources(&outcome), list(&["openmeteo"]));
        let outcome = AutoPrimaryOutcome {
            wants_extended_forecast: false,
            core_complete: false,
            ..outcome
        };
        assert_eq!(auto_secondary_sources(&outcome), list(&["pirateweather"]));
    }
}
