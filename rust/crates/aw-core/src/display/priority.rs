//! Category ordering for current-conditions metrics.
//!
//! Port of `display/priority_engine.py`.

use chrono::{DateTime, Utc};

use crate::model::WeatherAlerts;

/// `WeatherCategory`, in declaration order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum WeatherCategory {
    Temperature,
    Precipitation,
    Wind,
    HumidityPressure,
    VisibilityClouds,
    UvIndex,
}

impl WeatherCategory {
    pub const ALL: [WeatherCategory; 6] = [
        WeatherCategory::Temperature,
        WeatherCategory::Precipitation,
        WeatherCategory::Wind,
        WeatherCategory::HumidityPressure,
        WeatherCategory::VisibilityClouds,
        WeatherCategory::UvIndex,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            WeatherCategory::Temperature => "temperature",
            WeatherCategory::Precipitation => "precipitation",
            WeatherCategory::Wind => "wind",
            WeatherCategory::HumidityPressure => "humidity_pressure",
            WeatherCategory::VisibilityClouds => "visibility_clouds",
            WeatherCategory::UvIndex => "uv_index",
        }
    }

    /// `WeatherCategory.from_string` (case-insensitive).
    pub fn from_name(value: &str) -> Option<Self> {
        let v = value.to_lowercase();
        Self::ALL.into_iter().find(|c| c.as_str() == v)
    }
}

/// `ALERT_CATEGORY_MAP`: alert keywords and the categories they promote, in
/// Python's dict order.
const ALERT_CATEGORY_MAP: &[(&str, &[&str])] = &[
    ("heat", &["temperature", "uv_index"]),
    ("excessive heat", &["temperature", "uv_index"]),
    ("wind", &["wind"]),
    ("high wind", &["wind"]),
    ("gale", &["wind"]),
    ("hurricane", &["wind", "precipitation"]),
    ("tropical storm", &["wind", "precipitation"]),
    ("tornado", &["wind"]),
    ("flood", &["precipitation"]),
    ("flash flood", &["precipitation"]),
    ("rain", &["precipitation"]),
    ("thunderstorm", &["precipitation", "wind"]),
    ("severe thunderstorm", &["precipitation", "wind"]),
    ("winter storm", &["precipitation", "temperature"]),
    ("winter weather", &["precipitation", "temperature"]),
    ("blizzard", &["precipitation", "temperature", "wind"]),
    ("ice storm", &["precipitation", "temperature"]),
    ("freeze", &["temperature"]),
    ("frost", &["temperature"]),
    ("cold", &["temperature"]),
    ("snow", &["precipitation", "temperature"]),
    ("fog", &["visibility_clouds"]),
    ("dense fog", &["visibility_clouds"]),
    ("smoke", &["visibility_clouds"]),
];

/// `CATEGORY_FIELDS`: fields per category per verbosity level.
fn category_fields(category: WeatherCategory, verbosity: &str) -> &'static [&'static str] {
    use WeatherCategory::*;
    let (minimal, standard, detailed): (&[&str], &[&str], &[&str]) = match category {
        Temperature => (
            &["temperature"],
            &["temperature", "feels_like"],
            &["temperature", "feels_like", "dewpoint", "heat_index", "wind_chill"],
        ),
        Precipitation => (
            &["precipitation_chance"],
            &["precipitation_chance", "precipitation_amount"],
            &[
                "precipitation_chance",
                "precipitation_amount",
                "precipitation_type",
                "snowfall",
            ],
        ),
        Wind => (
            &["wind_speed"],
            &["wind_speed", "wind_direction"],
            &["wind_speed", "wind_direction", "wind_gusts"],
        ),
        HumidityPressure => (
            &["humidity"],
            &["humidity", "pressure"],
            &["humidity", "pressure", "pressure_trend"],
        ),
        VisibilityClouds => (&[], &["visibility"], &["visibility", "cloud_cover"]),
        UvIndex => (&[], &["uv_index"], &["uv_index"]),
    };
    match verbosity {
        "minimal" => minimal,
        "detailed" => detailed,
        _ => standard,
    }
}

/// `PriorityEngine`.
#[derive(Debug, Clone)]
pub struct PriorityEngine {
    pub verbosity_level: String,
    pub category_order: Vec<String>,
    pub severe_weather_override: bool,
}

impl PriorityEngine {
    pub fn new(verbosity_level: &str, category_order: &[String], severe_weather_override: bool) -> Self {
        let category_order = if category_order.is_empty() {
            WeatherCategory::ALL
                .iter()
                .map(|c| c.as_str().to_string())
                .collect()
        } else {
            category_order.to_vec()
        };
        Self {
            verbosity_level: verbosity_level.to_string(),
            category_order,
            severe_weather_override,
        }
    }

    /// `get_category_order`: categories named by active alerts first (when the
    /// override is on), then the user's order.
    ///
    /// Python raises on an unknown category name; here it is skipped. Python
    /// appends categories missing from a partial order in set (hash) order,
    /// which is not stable between runs; here they follow declaration order.
    pub fn get_category_order(
        &self,
        alerts: Option<&WeatherAlerts>,
        now: DateTime<Utc>,
    ) -> Vec<WeatherCategory> {
        let base: Vec<WeatherCategory> = self
            .category_order
            .iter()
            .filter_map(|c| WeatherCategory::from_name(c))
            .collect();
        let Some(alerts) = alerts.filter(|_| self.severe_weather_override) else {
            return ensure_all(base);
        };
        let active: Vec<_> = alerts
            .alerts
            .iter()
            .filter(|a| a.expires.is_none_or(|e| e > now))
            .collect();
        if active.is_empty() {
            return ensure_all(base);
        }
        let mut priority: Vec<&str> = Vec::new();
        for alert in active {
            let event = alert
                .event
                .as_deref()
                .filter(|e| !e.is_empty())
                .unwrap_or(&alert.title)
                .to_lowercase();
            for (keyword, categories) in ALERT_CATEGORY_MAP {
                if event.contains(keyword) {
                    for cat in *categories {
                        if !priority.contains(cat) {
                            priority.push(cat);
                        }
                    }
                }
            }
        }
        if priority.is_empty() {
            return ensure_all(base);
        }
        let mut order: Vec<WeatherCategory> = Vec::new();
        for cat in priority.iter().filter_map(|c| WeatherCategory::from_name(c)) {
            if !order.contains(&cat) {
                order.push(cat);
            }
        }
        for cat in base {
            if !order.contains(&cat) {
                order.push(cat);
            }
        }
        ensure_all(order)
    }

    /// `get_fields_for_category`.
    pub fn get_fields_for_category(&self, category: WeatherCategory) -> &'static [&'static str] {
        category_fields(category, &self.verbosity_level)
    }

    /// `should_include_field`.
    pub fn should_include_field(&self, category: WeatherCategory, field: &str) -> bool {
        self.get_fields_for_category(category).contains(&field)
    }
}

fn ensure_all(mut order: Vec<WeatherCategory>) -> Vec<WeatherCategory> {
    for cat in WeatherCategory::ALL {
        if !order.contains(&cat) {
            order.push(cat);
        }
    }
    order
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::WeatherAlert;
    use WeatherCategory::*;

    fn alerts(events: &[&str]) -> WeatherAlerts {
        WeatherAlerts {
            alerts: events
                .iter()
                .map(|e| {
                    let mut a = WeatherAlert::new(*e, "");
                    a.event = Some(e.to_string());
                    a
                })
                .collect(),
        }
    }

    #[test]
    fn default_order_without_alerts() {
        let engine = PriorityEngine::new("standard", &[], true);
        assert_eq!(engine.get_category_order(None, Utc::now()), WeatherCategory::ALL.to_vec());
    }

    #[test]
    fn alerts_promote_their_categories_only_with_override() {
        let a = alerts(&["Dense Fog Advisory", "Winter Storm Warning"]);
        let on = PriorityEngine::new("standard", &[], true);
        assert_eq!(
            on.get_category_order(Some(&a), Utc::now()),
            vec![VisibilityClouds, Precipitation, Temperature, Wind, HumidityPressure, UvIndex]
        );
        let off = PriorityEngine::new("standard", &[], false);
        assert_eq!(off.get_category_order(Some(&a), Utc::now()), WeatherCategory::ALL.to_vec());
    }

    #[test]
    fn heat_alert_keywords_follow_map_order() {
        let a = alerts(&["Excessive Heat Warning"]);
        let engine = PriorityEngine::new("standard", &["wind".into(), "temperature".into()], true);
        assert_eq!(
            engine.get_category_order(Some(&a), Utc::now()),
            vec![Temperature, UvIndex, Wind, Precipitation, HumidityPressure, VisibilityClouds]
        );
    }

    #[test]
    fn fields_follow_verbosity() {
        let minimal = PriorityEngine::new("minimal", &[], false);
        assert!(minimal.get_fields_for_category(VisibilityClouds).is_empty());
        let detailed = PriorityEngine::new("detailed", &[], false);
        assert!(detailed.should_include_field(Wind, "wind_gusts"));
        let odd = PriorityEngine::new("chatty", &[], false);
        assert_eq!(odd.get_fields_for_category(Wind), ["wind_speed", "wind_direction"]);
    }
}
