//! Presentation view models.
//!
//! Field-for-field ports of `display/presentation/models.py`, plus
//! `AirQualityPresentation` (`environmental.py`) and `ImpactSummary`
//! (`impact_summary.py`). They serialise exactly like Python's
//! `dataclasses.asdict`.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Metric {
    pub label: String,
    pub value: String,
}

impl Metric {
    pub fn new(label: impl Into<String>, value: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            value: value.into(),
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct HourlyPeriodPresentation {
    pub time: String,
    pub temperature: Option<String>,
    pub conditions: Option<String>,
    pub wind: Option<String>,
    pub humidity: Option<String>,
    pub dewpoint: Option<String>,
    pub precipitation_probability: Option<String>,
    pub snowfall: Option<String>,
    pub uv_index: Option<String>,
    pub cloud_cover: Option<String>,
    pub wind_gust: Option<String>,
    pub precipitation_amount: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ForecastPeriodPresentation {
    pub name: String,
    pub temperature: Option<String>,
    pub conditions: Option<String>,
    pub wind: Option<String>,
    pub details: Option<String>,
    pub precipitation_probability: Option<String>,
    pub snowfall: Option<String>,
    pub uv_index: Option<String>,
    pub cloud_cover: Option<String>,
    pub wind_gust: Option<String>,
    pub precipitation_amount: Option<String>,
}

/// `ImpactSummary`: outdoor, driving and allergy guidance.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ImpactSummary {
    pub outdoor: Option<String>,
    pub driving: Option<String>,
    pub allergy: Option<String>,
}

impl ImpactSummary {
    pub fn has_content(&self) -> bool {
        [&self.outdoor, &self.driving, &self.allergy]
            .iter()
            .any(|s| s.as_deref().is_some_and(|s| !s.is_empty()))
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct CurrentConditionsPresentation {
    pub title: String,
    pub description: String,
    pub metrics: Vec<Metric>,
    pub fallback_text: String,
    pub trends: Vec<String>,
    pub impact_summary: Option<ImpactSummary>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ForecastPresentation {
    pub title: String,
    pub periods: Vec<ForecastPeriodPresentation>,
    pub hourly_periods: Vec<HourlyPeriodPresentation>,
    pub hourly_summary: Option<String>,
    pub generated_at: Option<String>,
    pub fallback_text: String,
    pub daily_section_text: String,
    pub hourly_section_text: String,
    pub mobility_briefing: Option<String>,
    pub marine_section_text: String,
    pub marine_summary: Option<String>,
    pub marine_highlights: Vec<String>,
    pub confidence_label: Option<String>,
    pub summary: Option<String>,
    pub impact_summary: Option<ImpactSummary>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct AviationPresentation {
    pub title: String,
    pub airport_name: Option<String>,
    pub station_id: Option<String>,
    pub taf_summary: Option<String>,
    pub raw_taf: Option<String>,
    pub sigmets: Vec<String>,
    pub cwas: Vec<String>,
    pub fallback_text: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct AlertPresentation {
    pub title: String,
    pub severity: Option<String>,
    pub urgency: Option<String>,
    pub event: Option<String>,
    pub areas: Vec<String>,
    pub expires: Option<String>,
    pub description: Option<String>,
    pub instructions: Option<String>,
    pub fallback_text: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct AlertsPresentation {
    pub title: String,
    pub alerts: Vec<AlertPresentation>,
    pub fallback_text: String,
    pub change_summary: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceAttributionPresentation {
    pub contributing_sources: Vec<String>,
    pub failed_sources: Vec<String>,
    pub incomplete_sections: Vec<String>,
    pub summary_text: String,
    pub aria_label: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct AirQualityPresentation {
    pub title: String,
    pub summary: String,
    pub guidance: Option<String>,
    pub details: Vec<String>,
    pub fallback_text: String,
    pub updated_at: Option<String>,
    pub sources: Vec<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct WeatherPresentation {
    pub location_name: String,
    pub summary_text: String,
    pub current_conditions: Option<CurrentConditionsPresentation>,
    pub forecast: Option<ForecastPresentation>,
    pub alerts: Option<AlertsPresentation>,
    pub air_quality: Option<AirQualityPresentation>,
    pub aviation: Option<AviationPresentation>,
    pub trend_summary: Vec<String>,
    pub status_messages: Vec<String>,
    pub source_attribution: Option<SourceAttributionPresentation>,
}
