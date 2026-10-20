//! Local official readings: observations and short-range forecasts from
//! official national sources, each labelled with the station or area it
//! covers, its time and its averaging period.
//!
//! Every source implements [`RegionalSource`]. [`default_sources`] lists
//! them in display order: country-specific sources first, then the
//! worldwide airport (METAR) baseline that covers every location.
//! [`fetch_local_readings`] runs each source that covers a location and
//! keeps one source's failure from hiding another's readings.
//!
//! Adding a country means one new module with a `RegionalSource` impl and
//! an entry in [`default_sources`].

pub mod germany;
pub mod metar;
pub mod singapore;

use aw_core::Location;
use chrono::{DateTime, FixedOffset, Offset, Utc};
use chrono_tz::Tz;

use crate::http::{HttpClient, HttpError};

/// What a reading measures; also the order readings are listed in within
/// one source.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum ReadingKind {
    Conditions,
    Forecast,
    Temperature,
    DewPoint,
    Humidity,
    Rainfall,
    Wind,
    Pressure,
    Visibility,
    Pm25,
    Psi,
}

/// What a reading covers.
#[derive(Debug, Clone, PartialEq)]
pub struct Coverage {
    /// "Ang Mo Kio Avenue 5 station", "Bishan forecast area", "Central region".
    pub name: String,
    /// Distance from the location to the station or area centre.
    pub distance_km: Option<f64>,
}

impl Coverage {
    pub fn new(name: impl Into<String>, distance_km: Option<f64>) -> Self {
        Self {
            name: name.into(),
            distance_km,
        }
    }
}

/// When a reading applies.
#[derive(Debug, Clone, PartialEq)]
pub enum ReadingTime {
    Observed(DateTime<FixedOffset>),
    Valid {
        start: DateTime<FixedOffset>,
        end: DateTime<FixedOffset>,
    },
    Unknown,
}

/// One labelled reading from an official source.
#[derive(Debug, Clone, PartialEq)]
pub struct LocalReading {
    pub kind: ReadingKind,
    /// "Rainfall", "PM2.5", "2-hour forecast".
    pub label: String,
    /// "0.4 mm", "Thundery Showers".
    pub value: String,
    /// Extra meaning for the value, such as an index band ("Good").
    pub detail: Option<String>,
    /// "5-minute total", "1-hour average", "24-hour average".
    pub period: Option<String>,
    pub coverage: Coverage,
    pub time: ReadingTime,
    /// "Singapore NEA".
    pub source: String,
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum RegionalError {
    #[error(transparent)]
    Http(#[from] HttpError),
    #[error("{0}")]
    Data(String),
}

/// An official source of local readings for part of the world.
pub trait RegionalSource: Send + Sync {
    /// Short display name, such as "Singapore NEA".
    fn name(&self) -> &'static str;
    /// Whether this source has data for `location`. Sources are never
    /// fetched for locations they don't cover.
    fn covers(&self, location: &Location) -> bool;
    /// This source's readings for `location`, nearest station or area first.
    fn fetch(
        &self,
        http: &dyn HttpClient,
        location: &Location,
    ) -> Result<Vec<LocalReading>, RegionalError>;
}

/// Every source, in display order: country sources, then the worldwide
/// airport baseline.
pub fn default_sources() -> Vec<Box<dyn RegionalSource>> {
    vec![
        Box::new(singapore::SingaporeNea::default()),
        Box::new(germany::BrightSkyDwd::default()),
        Box::new(metar::NearestMetar::default()),
    ]
}

/// One source's failure, kept so the dialog can say what's missing.
#[derive(Debug, Clone, PartialEq)]
pub struct SourceFailure {
    pub source: String,
    pub message: String,
}

/// The readings for one location from every covering source.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct LocalReadingsReport {
    pub readings: Vec<LocalReading>,
    /// Names of the sources that covered the location, in order.
    pub sources: Vec<String>,
    pub failures: Vec<SourceFailure>,
}

/// Run every source in `sources` that covers `location`. A failing source
/// is logged and recorded; the others still contribute. Readings keep the
/// source order, then [`ReadingKind`] order within a source.
pub fn fetch_local_readings(
    http: &dyn HttpClient,
    location: &Location,
    sources: &[Box<dyn RegionalSource>],
) -> LocalReadingsReport {
    let mut report = LocalReadingsReport::default();
    if !location.valid_coordinates() {
        return report;
    }
    for source in sources.iter().filter(|s| s.covers(location)) {
        report.sources.push(source.name().to_string());
        match source.fetch(http, location) {
            Ok(mut readings) => {
                readings.sort_by_key(|r| r.kind);
                report.readings.extend(readings);
            }
            Err(e) => {
                tracing::warn!(
                    "Local readings from {} failed for {}: {e}",
                    source.name(),
                    location.name
                );
                report.failures.push(SourceFailure {
                    source: source.name().to_string(),
                    message: e.to_string(),
                });
            }
        }
    }
    report
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

/// Whether a location is in `country` (ISO 3166-1 alpha-2): the country
/// code decides when set; otherwise `bbox` (min lat, min lon, max lat,
/// max lon) does.
pub(crate) fn in_country(location: &Location, country: &str, bbox: [f64; 4]) -> bool {
    if let Some(code) = location
        .country_code
        .as_deref()
        .map(str::trim)
        .filter(|c| !c.is_empty())
    {
        return code.eq_ignore_ascii_case(country);
    }
    let [min_lat, min_lon, max_lat, max_lon] = bbox;
    (min_lat..=max_lat).contains(&location.latitude)
        && (min_lon..=max_lon).contains(&location.longitude)
}

/// Great-circle distance in kilometres.
pub fn distance_km(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    const EARTH_RADIUS_KM: f64 = 6371.0088;
    let (p1, p2) = (lat1.to_radians(), lat2.to_radians());
    let dp = (lat2 - lat1).to_radians();
    let dl = (lon2 - lon1).to_radians();
    let a = (dp / 2.0).sin().powi(2) + p1.cos() * p2.cos() * (dl / 2.0).sin().powi(2);
    2.0 * EARTH_RADIUS_KM * a.sqrt().atan2((1.0 - a).sqrt())
}

/// The item nearest `location` among those with coordinates, with its
/// distance in kilometres.
pub(crate) fn nearest<T>(
    location: &Location,
    items: impl IntoIterator<Item = T>,
    coords: impl Fn(&T) -> Option<(f64, f64)>,
) -> Option<(T, f64)> {
    items
        .into_iter()
        .filter_map(|item| {
            let (lat, lon) = coords(&item)?;
            let d = distance_km(location.latitude, location.longitude, lat, lon);
            d.is_finite().then_some((item, d))
        })
        .min_by(|a, b| a.1.total_cmp(&b.1))
}

/// An RFC 3339 timestamp.
pub(crate) fn parse_time(text: &str) -> Option<DateTime<FixedOffset>> {
    DateTime::parse_from_rfc3339(text.trim()).ok()
}

/// "29.4°C (84.9°F)".
pub(crate) fn celsius(value: f64) -> String {
    format!("{value:.1}°C ({:.1}°F)", value * 9.0 / 5.0 + 32.0)
}

/// "12 km/h (7 mph)".
pub(crate) fn kmh(value: f64) -> String {
    format!("{value:.0} km/h ({:.0} mph)", value / 1.609_344)
}

// ---------------------------------------------------------------------------
// Presentation
// ---------------------------------------------------------------------------

/// How times are written: the location's zone (else each timestamp's own
/// offset), 12- or 24-hour clock, and "now" for the age.
#[derive(Debug, Clone, Copy)]
pub struct TimeStyle<'a> {
    pub timezone: Option<&'a str>,
    pub twelve_hour: bool,
    pub now: DateTime<Utc>,
}

impl TimeStyle<'_> {
    fn clock(&self, ts: &DateTime<FixedOffset>) -> String {
        let pattern = if self.twelve_hour {
            "%-I:%M %p"
        } else {
            "%H:%M"
        };
        match self.timezone.and_then(|tz| tz.parse::<Tz>().ok()) {
            Some(tz) => ts.with_timezone(&tz).format(pattern).to_string(),
            None if ts.offset().fix().local_minus_utc() == 0 => {
                format!("{} UTC", ts.format(pattern))
            }
            None => ts.format(pattern).to_string(),
        }
    }

    /// ", 12 minutes ago" for an observation in the past.
    fn age(&self, ts: &DateTime<FixedOffset>) -> String {
        let minutes = (self.now - ts.with_timezone(&Utc)).num_minutes();
        match minutes {
            m if m < 0 => String::new(),
            0 => ", just now".into(),
            1 => ", 1 minute ago".into(),
            m if m < 120 => format!(", {m} minutes ago"),
            m if m < 48 * 60 => format!(", {} hours ago", m / 60),
            m => format!(", {} days ago", m / (24 * 60)),
        }
    }
}

/// "2.1 km away" (metres under 1 km).
pub fn format_distance(km: f64) -> String {
    if km < 1.0 {
        format!("{:.0} m away", (km * 1000.0 / 10.0).round() * 10.0)
    } else if km < 10.0 {
        format!("{km:.1} km away")
    } else {
        format!("{km:.0} km away")
    }
}

impl LocalReading {
    /// One self-contained sentence group a screen reader can read on its
    /// own: value, period, coverage, time and source.
    ///
    /// "Rainfall: 0.2 mm, 5-minute total. Ang Mo Kio Avenue 5 station,
    /// 2.1 km away. Observed 3:05 PM, 2 minutes ago. Source: Singapore NEA."
    pub fn to_line(&self, style: &TimeStyle<'_>) -> String {
        let mut value = format!("{}: {}", self.label, self.value);
        if let Some(detail) = &self.detail {
            value.push_str(&format!(" ({detail})"));
        }
        if let Some(period) = &self.period {
            value.push_str(&format!(", {period}"));
        }
        let coverage = match self.coverage.distance_km {
            Some(km) => format!("{}, {}", self.coverage.name, format_distance(km)),
            None => self.coverage.name.clone(),
        };
        let time = match &self.time {
            ReadingTime::Observed(ts) => {
                format!(" Observed {}{}.", style.clock(ts), style.age(ts))
            }
            ReadingTime::Valid { start, end } => {
                format!(" Valid {} to {}.", style.clock(start), style.clock(end))
            }
            ReadingTime::Unknown => String::new(),
        };
        format!("{value}. {coverage}.{time} Source: {}.", self.source)
    }
}

/// A fixed `+08:00`-style offset for test timestamps.
#[cfg(test)]
pub(crate) fn offset_hours(hours: i32) -> FixedOffset {
    FixedOffset::east_opt(hours * 3600).expect("offset in range")
}

#[cfg(test)]
pub(crate) mod test_support {
    use std::sync::Arc;

    use super::*;

    /// A source with canned behaviour, for registry tests.
    pub struct StubSource {
        pub name: &'static str,
        pub covers: bool,
        pub result: Result<Vec<LocalReading>, String>,
        pub calls: Arc<std::sync::atomic::AtomicUsize>,
    }

    impl RegionalSource for StubSource {
        fn name(&self) -> &'static str {
            self.name
        }
        fn covers(&self, _: &Location) -> bool {
            self.covers
        }
        fn fetch(
            &self,
            _: &dyn HttpClient,
            _: &Location,
        ) -> Result<Vec<LocalReading>, RegionalError> {
            self.calls.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            self.result.clone().map_err(RegionalError::Data)
        }
    }

    pub fn reading(kind: ReadingKind, source: &str) -> LocalReading {
        LocalReading {
            kind,
            label: format!("{kind:?}"),
            value: "1".into(),
            detail: None,
            period: None,
            coverage: Coverage::new("Somewhere", None),
            time: ReadingTime::Unknown,
            source: source.into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    use chrono::TimeZone;

    use super::test_support::*;
    use super::*;
    use crate::http::FixtureClient;

    fn stub(
        name: &'static str,
        covers: bool,
        result: Result<Vec<LocalReading>, String>,
    ) -> (Box<dyn RegionalSource>, Arc<AtomicUsize>) {
        let calls = Arc::new(AtomicUsize::new(0));
        (
            Box::new(StubSource {
                name,
                covers,
                result,
                calls: calls.clone(),
            }),
            calls,
        )
    }

    #[test]
    fn registry_skips_uncovered_sources_and_isolates_failures() {
        let (a, a_calls) = stub("A", false, Ok(vec![reading(ReadingKind::Rainfall, "A")]));
        let (b, _) = stub("B", true, Err("boom".into()));
        let (c, _) = stub(
            "C",
            true,
            Ok(vec![
                reading(ReadingKind::Wind, "C"),
                reading(ReadingKind::Temperature, "C"),
            ]),
        );
        let report = fetch_local_readings(
            &FixtureClient::new(),
            &Location::new("X", 1.0, 2.0),
            &[a, b, c],
        );
        assert_eq!(
            a_calls.load(Ordering::SeqCst),
            0,
            "uncovered source never fetched"
        );
        assert_eq!(report.sources, vec!["B", "C"]);
        assert_eq!(
            report.failures,
            vec![SourceFailure {
                source: "B".into(),
                message: "boom".into()
            }]
        );
        let kinds: Vec<_> = report.readings.iter().map(|r| r.kind).collect();
        assert_eq!(kinds, vec![ReadingKind::Temperature, ReadingKind::Wind]);
    }

    #[test]
    fn invalid_coordinates_fetch_nothing() {
        let (a, calls) = stub("A", true, Ok(vec![]));
        let report =
            fetch_local_readings(&FixtureClient::new(), &Location::new("X", 95.0, 0.0), &[a]);
        assert_eq!(calls.load(Ordering::SeqCst), 0);
        assert_eq!(report, LocalReadingsReport::default());
    }

    #[test]
    fn default_sources_end_with_the_worldwide_baseline() {
        let sources = default_sources();
        let london = Location::new("London", 51.5, -0.12).with_country("GB");
        let covering: Vec<_> = sources
            .iter()
            .filter(|s| s.covers(&london))
            .map(|s| s.name())
            .collect();
        assert_eq!(covering, vec![metar::SOURCE_NAME]);
        assert_eq!(sources.last().unwrap().name(), metar::SOURCE_NAME);
    }

    #[test]
    fn haversine_distance_is_sane() {
        // Singapore Changi to Ang Mo Kio is roughly 17 km.
        let d = distance_km(1.3502, 103.9940, 1.3691, 103.8454);
        assert!((16.0..18.0).contains(&d), "{d}");
        assert_eq!(distance_km(1.0, 1.0, 1.0, 1.0), 0.0);
    }

    #[test]
    fn country_code_wins_over_bounding_box() {
        let bbox = [1.0, 103.0, 2.0, 104.0];
        assert!(in_country(&Location::new("x", 1.3, 103.8), "SG", bbox));
        assert!(!in_country(
            &Location::new("x", 1.3, 103.8).with_country("MY"),
            "SG",
            bbox
        ));
        assert!(in_country(
            &Location::new("x", 50.0, 0.0).with_country("sg"),
            "SG",
            bbox
        ));
        assert!(!in_country(&Location::new("x", 3.0, 103.8), "SG", bbox));
    }

    #[test]
    fn lines_state_value_period_coverage_time_and_source() {
        let observed = offset_hours(8)
            .with_ymd_and_hms(2026, 10, 20, 15, 5, 0)
            .unwrap();
        let reading = LocalReading {
            kind: ReadingKind::Rainfall,
            label: "Rainfall".into(),
            value: "0.2 mm".into(),
            detail: None,
            period: Some("5-minute total".into()),
            coverage: Coverage::new("Ang Mo Kio Avenue 5 station", Some(2.14)),
            time: ReadingTime::Observed(observed),
            source: "Singapore NEA".into(),
        };
        let style = TimeStyle {
            timezone: Some("Asia/Singapore"),
            twelve_hour: true,
            now: observed.with_timezone(&Utc) + chrono::Duration::minutes(2),
        };
        assert_eq!(
            reading.to_line(&style),
            "Rainfall: 0.2 mm, 5-minute total. Ang Mo Kio Avenue 5 station, 2.1 km away. \
             Observed 3:05 PM, 2 minutes ago. Source: Singapore NEA."
        );
        let utc = TimeStyle {
            timezone: None,
            twelve_hour: false,
            now: style.now,
        };
        let line = LocalReading {
            time: ReadingTime::Observed(observed.with_timezone(&Utc).fixed_offset()),
            ..reading
        }
        .to_line(&utc);
        assert!(
            line.contains("Observed 07:05 UTC, 2 minutes ago."),
            "{line}"
        );
    }

    #[test]
    fn distances_read_naturally() {
        assert_eq!(format_distance(0.234), "230 m away");
        assert_eq!(format_distance(2.14), "2.1 km away");
        assert_eq!(format_distance(23.6), "24 km away");
    }
}
