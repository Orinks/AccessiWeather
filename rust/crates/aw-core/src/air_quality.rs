//! Air quality index standards: the US EPA AQI and the European (EEA) AQI.
//!
//! Open-Meteo serves both indexes; AirNow serves only the US one. The
//! "Air quality index" setting picks one, or "auto" picks the European
//! index for locations in Europe and the US index everywhere else.

use serde::{Deserialize, Serialize};

use crate::countries;
use crate::display::pyfmt::round_int;
use crate::location::Location;
use crate::model::{AirQualityProvenance, PollutantReading, ReadingKind, Timestamp};
use crate::settings::AppSettings;

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

// ---------------------------------------------------------------------------
// Alert levels
// ---------------------------------------------------------------------------

/// The "US AQI alert level" setting values, lowest first. Each is a
/// category of the US AQI, starting at Moderate.
pub const US_ALERT_THRESHOLDS: [&str; 5] = [
    "moderate",
    "unhealthy_for_sensitive_groups",
    "unhealthy",
    "very_unhealthy",
    "hazardous",
];

/// The "European AQI alert level" setting values, lowest first. Each is a
/// category of the European AQI, starting at Fair.
pub const EUROPEAN_ALERT_THRESHOLDS: [&str; 5] =
    ["fair", "moderate", "poor", "very_poor", "extremely_poor"];

/// The alert-level setting values for `standard`, lowest first.
pub fn alert_thresholds(standard: AqiStandard) -> &'static [&'static str] {
    match standard {
        AqiStandard::Us => &US_ALERT_THRESHOLDS,
        AqiStandard::European => &EUROPEAN_ALERT_THRESHOLDS,
    }
}

/// The [`AqiStandard::rank`] an alert level stands for. The levels start
/// at the second category, so an unknown key falls back to the default
/// (Unhealthy for Sensitive Groups, or Poor).
pub fn threshold_rank(standard: AqiStandard, key: &str) -> usize {
    let key = key.trim();
    match alert_thresholds(standard).iter().position(|k| *k == key) {
        Some(i) => i + 1,
        None => match standard {
            AqiStandard::Us => 2,
            AqiStandard::European => 3,
        },
    }
}

/// The category name an alert level stands for ("Unhealthy for Sensitive
/// Groups", "Poor").
pub fn threshold_label(standard: AqiStandard, key: &str) -> &'static str {
    standard.categories()[threshold_rank(standard, key)]
}

/// The alert level setting in force for `standard`.
pub fn alert_threshold_key(standard: AqiStandard, settings: &AppSettings) -> &str {
    match standard {
        AqiStandard::Us => &settings.air_quality_alert_threshold_us,
        AqiStandard::European => &settings.air_quality_alert_threshold_european,
    }
}

// ---------------------------------------------------------------------------
// Pollutant readings and where they came from
// ---------------------------------------------------------------------------

/// The pollutant codes a [`PollutantReading`] uses, in display order.
pub const POLLUTANT_CODES: [&str; 6] = ["pm2_5", "pm10", "o3", "no2", "so2", "co"];

/// Column headings of the pollutant readings list.
pub const POLLUTANT_COLUMNS: [&str; 6] = [
    "Pollutant",
    "Concentration",
    "Index",
    "Type",
    "Source",
    "Time",
];

/// A pollutant's display name; unknown codes are returned as they are.
pub fn pollutant_name(code: &str) -> &str {
    match code {
        "pm2_5" => "PM2.5",
        "pm10" => "PM10",
        "o3" => "Ozone (O3)",
        "no2" => "Nitrogen dioxide (NO2)",
        "so2" => "Sulphur dioxide (SO2)",
        "co" => "Carbon monoxide (CO)",
        other => other,
    }
}

/// The averaging period a standard's sub-index uses for `code`; `None`
/// when the standard has no sub-index for it (European CO).
pub fn index_averaging(standard: AqiStandard, code: &str) -> Option<&'static str> {
    Some(match (standard, code) {
        (_, "pm2_5" | "pm10") => "24-hour",
        (AqiStandard::Us, "o3" | "co") => "8-hour",
        (AqiStandard::Us, "no2" | "so2") => "1-hour",
        (AqiStandard::European, "o3" | "no2" | "so2") => "1-hour",
        _ => return None,
    })
}

/// The CAMS model Open-Meteo serves at a point, and its grid spacing:
/// the European model inside its domain, the global one elsewhere.
pub fn cams_domain(latitude: f64, longitude: f64) -> (&'static str, &'static str) {
    if (30.0..=72.0).contains(&latitude) && (-25.0..=45.0).contains(&longitude) {
        ("CAMS European model", "about 11 km grid")
    } else {
        ("CAMS global model", "about 45 km grid")
    }
}

/// [`cams_domain`] as one phrase: "CAMS European model, about 11 km grid".
pub fn cams_detail(latitude: f64, longitude: f64) -> String {
    let (model, grid) = cams_domain(latitude, longitude);
    format!("{model}, {grid}")
}

/// "Observed" or "Modelled".
pub fn kind_label(kind: ReadingKind) -> &'static str {
    match kind {
        ReadingKind::Observed => "Observed",
        ReadingKind::Modelled => "Modelled",
    }
}

/// "24-hour" reads as "24-hour average"; "NowCast" stays as it is.
fn averaging_phrase(averaging: &str) -> String {
    if averaging.ends_with("-hour") {
        format!("{averaging} average")
    } else {
        averaging.to_string()
    }
}

/// A concentration with sensible precision: 0.031, 4.2, 120.
fn format_amount(value: f64) -> String {
    if value.abs() >= 100.0 {
        format!("{value:.0}")
    } else if value.abs() >= 1.0 {
        format!("{value:.1}")
    } else {
        let text = format!("{value:.3}");
        let text = text.trim_end_matches('0').trim_end_matches('.');
        if text.is_empty() || text == "-" {
            "0".into()
        } else {
            text.to_string()
        }
    }
}

/// "12.3 μg/m³, 1-hour average", or "Not measured".
pub fn concentration_text(reading: &PollutantReading) -> String {
    let Some(value) = reading.concentration else {
        return "Not measured".into();
    };
    let mut text = format_amount(value);
    if let Some(unit) = reading
        .unit
        .as_deref()
        .map(str::trim)
        .filter(|u| !u.is_empty())
    {
        text = format!("{text} {unit}");
    }
    if let Some(averaging) = reading.averaging.as_deref().filter(|a| !a.is_empty()) {
        text = format!("{text}, {}", averaging_phrase(averaging));
    }
    text
}

/// "European AQI 25 (Fair), 24-hour average", "US AQI 42 (Good), NowCast",
/// or "Not rated" when the source gives no index.
pub fn index_text(reading: &PollutantReading) -> String {
    let category = reading
        .index_category
        .as_deref()
        .map(str::trim)
        .filter(|c| !c.is_empty());
    let name = reading.index_standard.map_or("AQI", AqiStandard::name);
    let mut text = match (reading.index_value, category) {
        (Some(value), Some(category)) => format!("{name} {} ({category})", round_int(value)),
        (Some(value), None) => format!("{name} {}", round_int(value)),
        (None, Some(category)) => format!("{category} on the {name}"),
        (None, None) => return "Not rated".into(),
    };
    if let Some(averaging) = reading.index_averaging.as_deref().filter(|a| !a.is_empty()) {
        text = format!("{text}, {}", averaging_phrase(averaging));
    }
    text
}

/// "Open-Meteo, CAMS European model, about 11 km grid", "AirNow at
/// Philadelphia", "OpenAQ, reference monitor at Paris 18e, 2.4 km away".
pub fn source_text(provenance: &AirQualityProvenance) -> String {
    let mut text = provenance.provider.trim().to_string();
    if let Some(detail) = provenance
        .detail
        .as_deref()
        .map(str::trim)
        .filter(|d| !d.is_empty())
    {
        text = format!("{text}, {detail}");
    }
    if let Some(station) = provenance
        .station_name
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        text = format!("{text} at {station}");
    }
    if let Some(km) = provenance.station_distance_km.filter(|d| d.is_finite()) {
        text = format!("{text}, {km:.1} km away");
    }
    text
}

/// "Observed 1:00 PM", "Forecast for 2:00 PM" or "Time not available";
/// `clock` formats the time.
pub fn time_text(
    provenance: &AirQualityProvenance,
    clock: &dyn Fn(&Timestamp) -> String,
) -> String {
    match (provenance.kind, &provenance.time) {
        (ReadingKind::Observed, Some(time)) => format!("Observed {}", clock(time)),
        (ReadingKind::Modelled, Some(time)) => format!("Forecast for {}", clock(time)),
        (_, None) => "Time not available".into(),
    }
}

/// "Reading: Modelled by Open-Meteo, CAMS European model, about 11 km
/// grid, forecast for 2:00 PM" or "Reading: Observed by AirNow at
/// Philadelphia, 1:00 PM".
pub fn provenance_line(
    provenance: &AirQualityProvenance,
    clock: &dyn Fn(&Timestamp) -> String,
) -> String {
    let mut text = format!(
        "Reading: {} by {}",
        kind_label(provenance.kind),
        source_text(provenance)
    );
    if let Some(time) = &provenance.time {
        match provenance.kind {
            ReadingKind::Observed => text = format!("{text}, {}", clock(time)),
            ReadingKind::Modelled => text = format!("{text}, forecast for {}", clock(time)),
        }
    }
    text
}

/// One list row, in [`POLLUTANT_COLUMNS`] order. Every cell makes sense
/// on its own, since screen readers announce them one at a time.
pub fn pollutant_row(
    reading: &PollutantReading,
    clock: &dyn Fn(&Timestamp) -> String,
) -> [String; 6] {
    [
        pollutant_name(&reading.code).to_string(),
        concentration_text(reading),
        index_text(reading),
        kind_label(reading.provenance.kind).to_string(),
        source_text(&reading.provenance),
        time_text(&reading.provenance, clock),
    ]
}

/// Which pollutants each source supplied: "Observed by AirNow at
/// Philadelphia: PM2.5, Ozone (O3). Modelled by Open-Meteo, CAMS global
/// model, about 45 km grid: PM10." `None` without readings.
pub fn readings_source_line(readings: &[PollutantReading]) -> Option<String> {
    let mut groups: Vec<(ReadingKind, String, Vec<&str>)> = Vec::new();
    for reading in readings {
        let kind = reading.provenance.kind;
        let source = source_text(&reading.provenance);
        let name = pollutant_name(&reading.code);
        match groups
            .iter_mut()
            .find(|(k, s, _)| *k == kind && *s == source)
        {
            Some((_, _, names)) => names.push(name),
            None => groups.push((kind, source, vec![name])),
        }
    }
    if groups.is_empty() {
        return None;
    }
    let mut sentences: Vec<String> = groups
        .iter()
        .map(|(kind, source, names)| {
            format!("{} by {source}: {}.", kind_label(*kind), names.join(", "))
        })
        .collect();
    if groups.iter().all(|(k, _, _)| *k == ReadingKind::Modelled) {
        sentences.push("None of these readings come from a monitoring station.".into());
    }
    Some(sentences.join(" "))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alert_thresholds_map_to_categories() {
        let us = AqiStandard::Us;
        let eu = AqiStandard::European;
        assert_eq!(threshold_rank(us, "moderate"), 1);
        assert_eq!(
            threshold_label(us, "unhealthy_for_sensitive_groups"),
            "Unhealthy for Sensitive Groups"
        );
        assert_eq!(threshold_label(us, "hazardous"), "Hazardous");
        assert_eq!(threshold_rank(eu, "fair"), 1);
        assert_eq!(threshold_label(eu, "poor"), "Poor");
        assert_eq!(threshold_label(eu, "extremely_poor"), "Extremely poor");
        // Unknown keys fall back to the defaults.
        assert_eq!(
            threshold_label(us, "bogus"),
            "Unhealthy for Sensitive Groups"
        );
        assert_eq!(threshold_label(eu, "bogus"), "Poor");
        // Every key lines up with the category it names.
        for standard in [us, eu] {
            for key in alert_thresholds(standard) {
                let label = threshold_label(standard, key);
                assert_eq!(label.to_lowercase().replace(' ', "_"), *key);
            }
        }
        let settings = AppSettings::default();
        assert_eq!(alert_threshold_key(eu, &settings), "poor");
    }

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

    fn modelled(code: &str) -> PollutantReading {
        PollutantReading {
            code: code.into(),
            concentration: Some(12.34),
            unit: Some("μg/m³".into()),
            averaging: Some("1-hour".into()),
            index_value: Some(25.0),
            index_category: Some("Fair".into()),
            index_standard: Some(AqiStandard::European),
            index_averaging: index_averaging(AqiStandard::European, code).map(str::to_string),
            provenance: AirQualityProvenance {
                kind: ReadingKind::Modelled,
                provider: "Open-Meteo".into(),
                detail: Some(cams_detail(48.85, 2.35)),
                station_name: None,
                station_distance_km: None,
                time: Some(
                    chrono::DateTime::parse_from_rfc3339("2025-06-01T14:00:00+02:00").unwrap(),
                ),
            },
        }
    }

    fn clock(t: &Timestamp) -> String {
        t.format("%H:%M").to_string()
    }

    #[test]
    fn pollutant_names_and_averaging() {
        assert_eq!(pollutant_name("pm2_5"), "PM2.5");
        assert_eq!(pollutant_name("so2"), "Sulphur dioxide (SO2)");
        assert_eq!(pollutant_name("bc"), "bc");
        assert_eq!(index_averaging(AqiStandard::Us, "o3"), Some("8-hour"));
        assert_eq!(index_averaging(AqiStandard::Us, "co"), Some("8-hour"));
        assert_eq!(index_averaging(AqiStandard::Us, "no2"), Some("1-hour"));
        assert_eq!(
            index_averaging(AqiStandard::European, "pm10"),
            Some("24-hour")
        );
        assert_eq!(index_averaging(AqiStandard::European, "o3"), Some("1-hour"));
        assert_eq!(index_averaging(AqiStandard::European, "co"), None);
    }

    #[test]
    fn cams_domain_by_position() {
        assert_eq!(cams_domain(48.85, 2.35).0, "CAMS European model");
        assert_eq!(cams_domain(64.1, -21.9).0, "CAMS European model");
        assert_eq!(
            cams_domain(-33.87, 151.2),
            ("CAMS global model", "about 45 km grid")
        );
        assert_eq!(cams_domain(40.7, -74.0).0, "CAMS global model");
    }

    #[test]
    fn row_cells_read_on_their_own() {
        let reading = modelled("pm2_5");
        assert_eq!(
            pollutant_row(&reading, &clock),
            [
                "PM2.5",
                "12.3 μg/m³, 1-hour average",
                "European AQI 25 (Fair), 24-hour average",
                "Modelled",
                "Open-Meteo, CAMS European model, about 11 km grid",
                "Forecast for 14:00",
            ]
        );
        let airnow = PollutantReading {
            code: "o3".into(),
            concentration: None,
            unit: None,
            averaging: None,
            index_value: Some(42.0),
            index_category: Some("Good".into()),
            index_standard: Some(AqiStandard::Us),
            index_averaging: Some("NowCast".into()),
            provenance: AirQualityProvenance {
                kind: ReadingKind::Observed,
                provider: "AirNow".into(),
                station_name: Some("Philadelphia".into()),
                detail: None,
                ..reading.provenance.clone()
            },
        };
        let row = pollutant_row(&airnow, &clock);
        assert_eq!(row[1], "Not measured");
        assert_eq!(row[2], "US AQI 42 (Good), NowCast");
        assert_eq!(row[3], "Observed");
        assert_eq!(row[4], "AirNow at Philadelphia");
        assert_eq!(row[5], "Observed 14:00");
        let station = AirQualityProvenance {
            provider: "OpenAQ".into(),
            detail: Some("reference monitor".into()),
            station_distance_km: Some(2.43),
            station_name: Some("Paris 18e".into()),
            ..airnow.provenance.clone()
        };
        assert_eq!(
            source_text(&station),
            "OpenAQ, reference monitor at Paris 18e, 2.4 km away"
        );
        let unrated = PollutantReading {
            index_value: None,
            index_category: None,
            concentration: Some(0.0312),
            unit: Some("ppm".into()),
            averaging: Some("Latest sensor reading".into()),
            ..airnow
        };
        assert_eq!(index_text(&unrated), "Not rated");
        assert_eq!(
            concentration_text(&unrated),
            "0.031 ppm, Latest sensor reading"
        );
        let category_only = PollutantReading {
            index_value: None,
            index_averaging: None,
            ..reading
        };
        assert_eq!(index_text(&category_only), "Fair on the European AQI");
    }

    #[test]
    fn provenance_lines() {
        let reading = modelled("no2");
        assert_eq!(
            provenance_line(&reading.provenance, &clock),
            "Reading: Modelled by Open-Meteo, CAMS European model, about 11 km grid, \
             forecast for 14:00"
        );
        let observed = AirQualityProvenance {
            kind: ReadingKind::Observed,
            provider: "AirNow".into(),
            detail: None,
            station_name: Some("Metro".into()),
            ..reading.provenance.clone()
        };
        assert_eq!(
            provenance_line(&observed, &clock),
            "Reading: Observed by AirNow at Metro, 14:00"
        );
        let untimed = AirQualityProvenance {
            time: None,
            ..observed.clone()
        };
        assert_eq!(
            provenance_line(&untimed, &clock),
            "Reading: Observed by AirNow at Metro"
        );
        assert_eq!(time_text(&untimed, &clock), "Time not available");
    }

    #[test]
    fn readings_source_line_groups_by_source() {
        assert_eq!(readings_source_line(&[]), None);
        let all_modelled = [modelled("pm2_5"), modelled("o3")];
        assert_eq!(
            readings_source_line(&all_modelled).unwrap(),
            "Modelled by Open-Meteo, CAMS European model, about 11 km grid: PM2.5, Ozone (O3). \
             None of these readings come from a monitoring station."
        );
        let mut observed = modelled("pm10");
        observed.provenance.kind = ReadingKind::Observed;
        observed.provenance.provider = "AirNow".into();
        observed.provenance.detail = None;
        let mixed = [observed, modelled("co")];
        assert_eq!(
            readings_source_line(&mixed).unwrap(),
            "Observed by AirNow: PM10. Modelled by Open-Meteo, CAMS European model, about 11 km \
             grid: Carbon monoxide (CO)."
        );
    }

    #[test]
    fn readings_round_trip_through_json() {
        let reading = modelled("pm2_5");
        let value = serde_json::to_value(&reading).unwrap();
        assert_eq!(value["provenance"]["kind"], "modelled");
        assert_eq!(value["index_standard"], "european");
        assert!(value["provenance"].get("station_name").is_none());
        let back: PollutantReading = serde_json::from_value(value).unwrap();
        assert_eq!(back, reading);
    }
}
