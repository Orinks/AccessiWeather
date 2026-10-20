//! The worldwide baseline: the nearest airport weather report (METAR) from
//! NOAA's Aviation Weather Center data API, which is keyless and global.
//! METARs are official observations made by each country's weather or
//! aviation service, so every location gets at least one observed reading
//! with a named station, distance and observation time.
//!
//! The app's TAF support already talks to aviationweather.gov
//! ([`crate::nws::aviation`]); weather and cloud groups are decoded with
//! the same decoders the TAF reader uses ([`crate::nws::taf`]).

use aw_core::weather_client_parsers::degrees_to_cardinal;
use aw_core::Location;
use chrono::{DateTime, FixedOffset, NaiveDateTime, Utc};
use serde_json::Value;

use super::{
    celsius, nearest, parse_time, Coverage, LocalReading, ReadingKind, ReadingTime, RegionalError,
    RegionalSource,
};
use crate::http::{build_url, HttpClient};
use crate::nws::taf::{decode_cloud, decode_weather};

/// aviationweather.gov's JSON METAR feed (sibling of
/// [`crate::nws::aviation::AWC_TAF_URL`]).
pub const AWC_METAR_URL: &str = "https://aviationweather.gov/api/data/metar";
pub const SOURCE_NAME: &str = "Nearest airport (METAR)";
const READING_SOURCE: &str = "METAR via NOAA Aviation Weather Center";

/// Search half-widths in degrees of latitude: nearby first, then wider
/// for remote places.
const SEARCH_RADII_DEG: [f64; 2] = [1.0, 3.0];
/// Reports older than this are only used when nothing fresher is near.
const STALE_AFTER_HOURS: i64 = 3;

/// The nearest-METAR source; covers every location.
#[derive(Debug, Clone)]
pub struct NearestMetar {
    pub url: String,
}

impl Default for NearestMetar {
    fn default() -> Self {
        Self {
            url: AWC_METAR_URL.into(),
        }
    }
}

/// The search box around `location` (`lat0,lon0,lat1,lon1`, the order the
/// API takes), widened in longitude away from the equator.
pub fn bbox(location: &Location, half_lat: f64) -> String {
    let lat = location.latitude;
    let cos = lat.to_radians().cos().max(0.2);
    let half_lon = (half_lat / cos).min(30.0);
    let lat0 = (lat - half_lat).max(-90.0);
    let lat1 = (lat + half_lat).min(90.0);
    let lon0 = (location.longitude - half_lon).max(-180.0);
    let lon1 = (location.longitude + half_lon).min(180.0);
    format!("{lat0:.2},{lon0:.2},{lat1:.2},{lon1:.2}")
}

impl RegionalSource for NearestMetar {
    fn name(&self) -> &'static str {
        SOURCE_NAME
    }

    fn covers(&self, _location: &Location) -> bool {
        true
    }

    fn fetch(
        &self,
        http: &dyn HttpClient,
        location: &Location,
    ) -> Result<Vec<LocalReading>, RegionalError> {
        self.fetch_at(http, location, Utc::now())
    }
}

impl NearestMetar {
    /// [`RegionalSource::fetch`] with an explicit "now" for staleness.
    pub fn fetch_at(
        &self,
        http: &dyn HttpClient,
        location: &Location,
        now: DateTime<Utc>,
    ) -> Result<Vec<LocalReading>, RegionalError> {
        for half in SEARCH_RADII_DEG {
            let url = build_url(
                &self.url,
                &[
                    ("bbox", bbox(location, half)),
                    ("format", "json".to_string()),
                ],
            );
            let body = http.get_json(&url)?;
            let reports = match &body {
                Value::Array(reports) => reports.as_slice(),
                // An empty result can come back as an empty body or object.
                Value::Null | Value::Object(_) => &[],
                _ => return Err(RegionalError::Data("unexpected METAR response".into())),
            };
            if let Some(report) = pick_report(reports, location, now) {
                return Ok(readings(report.0, report.1));
            }
        }
        Ok(Vec::new())
    }
}

fn observed_at(report: &Value) -> Option<DateTime<FixedOffset>> {
    if let Some(epoch) = report.get("obsTime").and_then(Value::as_i64) {
        return DateTime::from_timestamp(epoch, 0).map(|t| t.fixed_offset());
    }
    let text = report.get("reportTime").and_then(Value::as_str)?;
    parse_time(text).or_else(|| {
        NaiveDateTime::parse_from_str(text.trim(), "%Y-%m-%d %H:%M:%S")
            .ok()
            .map(|n| n.and_utc().fixed_offset())
    })
}

/// The nearest station's newest report, preferring stations that reported
/// within the last few hours.
fn pick_report<'a>(
    reports: &'a [Value],
    location: &Location,
    now: DateTime<Utc>,
) -> Option<(&'a Value, f64)> {
    let mut newest: Vec<&Value> = Vec::new();
    for report in reports.iter().filter(|r| r.get("icaoId").is_some()) {
        let id = report.get("icaoId");
        match newest.iter_mut().find(|r| r.get("icaoId") == id) {
            Some(existing) if observed_at(report) > observed_at(existing) => *existing = report,
            Some(_) => {}
            None => newest.push(report),
        }
    }
    let coords = |r: &&Value| Some((r.get("lat")?.as_f64()?, r.get("lon")?.as_f64()?));
    let fresh = |r: &&&Value| {
        observed_at(r).is_some_and(|t| now.signed_duration_since(t).num_hours() < STALE_AFTER_HOURS)
    };
    nearest(location, newest.iter().filter(fresh).copied(), coords)
        .or_else(|| nearest(location, newest.iter().copied(), coords))
}

/// Drop the decoders' trailing " (CODE)": the plain words read better.
fn plain(decoded: String) -> String {
    match decoded.rsplit_once(" (") {
        Some((words, code)) if code.ends_with(')') => words.to_string(),
        _ => decoded,
    }
}

fn conditions(report: &Value) -> Option<String> {
    let weather: Vec<String> = report
        .get("wxString")
        .and_then(Value::as_str)
        .unwrap_or("")
        .split_whitespace()
        .filter_map(decode_weather)
        .map(plain)
        .collect();
    let clouds: Vec<String> = report
        .get("clouds")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|c| {
            let cover = c.get("cover")?.as_str()?;
            let mut token = match c.get("base").and_then(Value::as_i64) {
                Some(base) => format!("{cover}{:03}", base / 100),
                None => cover.to_string(),
            };
            if let Some(kind @ ("CB" | "TCU")) = c.get("type").and_then(Value::as_str) {
                token.push_str(kind);
            }
            decode_cloud(&token)
                .or_else(|| (cover == "CAVOK").then(|| "Ceiling and visibility OK".into()))
        })
        .map(plain)
        .collect();
    let all: Vec<String> = weather.into_iter().chain(clouds).collect();
    let text = all.join("; ");
    let mut chars = text.chars();
    let first = chars.next()?;
    Some(first.to_uppercase().chain(chars).collect())
}

fn wind(report: &Value) -> Option<String> {
    let speed = report.get("wspd")?.as_f64()?;
    if speed == 0.0 {
        return Some("Calm".into());
    }
    let to_kmh = |kt: f64| kt * 1.852;
    let to_mph = |kt: f64| kt * 1.150_779;
    let direction = match report.get("wdir") {
        Some(Value::String(s)) if s.eq_ignore_ascii_case("VRB") => "Variable".to_string(),
        Some(v) => v
            .as_f64()
            .and_then(|d| degrees_to_cardinal(Some(d)))
            .unwrap_or_else(|| "Unknown direction".into()),
        None => "Unknown direction".into(),
    };
    let mut text = format!(
        "{direction} at {speed:.0} knots ({:.0} km/h, {:.0} mph)",
        to_kmh(speed),
        to_mph(speed)
    );
    if let Some(gust) = report
        .get("wgst")
        .and_then(Value::as_f64)
        .filter(|g| *g > 0.0)
    {
        text.push_str(&format!(
            ", gusting {gust:.0} knots ({:.0} km/h)",
            to_kmh(gust)
        ));
    }
    Some(text)
}

fn visibility(report: &Value) -> Option<String> {
    let (miles, or_more) = match report.get("visib")? {
        Value::String(s) => {
            let trimmed = s.trim().trim_end_matches('+');
            (trimmed.parse::<f64>().ok()?, s.trim().ends_with('+'))
        }
        v => (v.as_f64()?, false),
    };
    let more = if or_more { " or more" } else { "" };
    Some(format!(
        "{} miles{more} ({:.0} km{more})",
        format!("{miles:.1}").trim_end_matches(".0"),
        miles * 1.609_344
    ))
}

fn readings(report: &Value, km: f64) -> Vec<LocalReading> {
    let icao = report
        .get("icaoId")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim();
    let name = report
        .get("name")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|n| !n.is_empty())
        .unwrap_or(icao);
    let coverage = Coverage::new(format!("{name} ({icao}) airport station"), Some(km));
    let time = observed_at(report).map_or(ReadingTime::Unknown, ReadingTime::Observed);
    // US stations report 2-minute mean wind; elsewhere WMO's 10 minutes.
    let us = icao.starts_with('K') || icao.starts_with("PA") || icao.starts_with("PH");
    let wind_period = if us {
        "2-minute average"
    } else {
        "10-minute average"
    };
    let number = |key: &str| report.get(key).and_then(Value::as_f64);

    let rows: [(ReadingKind, &str, Option<String>, Option<&str>); 6] = [
        (
            ReadingKind::Conditions,
            "Conditions",
            conditions(report),
            None,
        ),
        (
            ReadingKind::Temperature,
            "Temperature",
            number("temp").map(celsius),
            None,
        ),
        (
            ReadingKind::DewPoint,
            "Dew point",
            number("dewp").map(celsius),
            None,
        ),
        (ReadingKind::Wind, "Wind", wind(report), Some(wind_period)),
        (
            ReadingKind::Visibility,
            "Visibility",
            visibility(report),
            None,
        ),
        (
            ReadingKind::Pressure,
            "Pressure",
            number("altim").map(|hpa| format!("{hpa:.0} hPa ({:.2} inHg)", hpa / 33.8639)),
            None,
        ),
    ];
    rows.into_iter()
        .filter_map(|(kind, label, value, period)| {
            Some(LocalReading {
                kind,
                label: label.into(),
                value: value?,
                detail: None,
                period: period.map(String::from),
                coverage: coverage.clone(),
                time: time.clone(),
                source: READING_SOURCE.into(),
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use chrono::TimeZone;

    use super::*;
    use crate::http::FixtureClient;

    fn reports() -> Value {
        serde_json::from_str(include_str!(
            "../../../../testdata/regional/metar/bbox.json"
        ))
        .unwrap()
    }

    fn now() -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 10, 20, 7, 20, 0).unwrap()
    }

    fn bishan() -> Location {
        Location::new("Bishan", 1.3526, 103.8352).with_country("SG")
    }

    #[test]
    fn bbox_is_lat_lon_ordered_and_clamped() {
        assert_eq!(bbox(&bishan(), 1.0), "0.35,102.83,2.35,104.84");
        let pole = Location::new("Alert", 82.5, -62.3);
        let b = bbox(&pole, 3.0);
        assert!(b.starts_with("79.50,-77.30,85.50,"), "{b}");
        let dateline = Location::new("Fiji", -17.7, 179.5);
        assert!(bbox(&dateline, 1.0).ends_with(",180.00"));
    }

    #[test]
    fn nearest_fresh_station_wins() {
        let http = FixtureClient::new().with(AWC_METAR_URL, reports());
        let readings = NearestMetar::default()
            .fetch_at(&http, &bishan(), now())
            .unwrap();
        // WSAP (Paya Lebar) is nearer but its report is a day old.
        let first = &readings[0];
        assert_eq!(
            first.coverage.name,
            "Singapore/Changi Intl, SG (WSSS) airport station"
        );
        let km = first.coverage.distance_km.unwrap();
        assert!((17.0..19.5).contains(&km), "{km}");
        assert_eq!(
            first.time,
            ReadingTime::Observed(
                Utc.with_ymd_and_hms(2026, 10, 20, 7, 0, 0)
                    .unwrap()
                    .fixed_offset()
            )
        );
        let line = |kind| {
            readings
                .iter()
                .find(|r| r.kind == kind)
                .map(|r| r.value.clone())
                .unwrap()
        };
        assert_eq!(
            line(ReadingKind::Conditions),
            "Light showers of rain; A few clouds at 1,800 feet with cumulonimbus; Broken clouds at 30,000 feet"
        );
        assert_eq!(line(ReadingKind::Temperature), "31.0°C (87.8°F)");
        assert_eq!(
            line(ReadingKind::Wind),
            "SSW at 8 knots (15 km/h, 9 mph), gusting 20 knots (37 km/h)"
        );
        assert_eq!(
            line(ReadingKind::Visibility),
            "6 miles or more (10 km or more)"
        );
        assert_eq!(line(ReadingKind::Pressure), "1009 hPa (29.80 inHg)");
        let wind = readings
            .iter()
            .find(|r| r.kind == ReadingKind::Wind)
            .unwrap();
        assert_eq!(wind.period.as_deref(), Some("10-minute average"));
        assert!(http.request_log()[0].contains("bbox=0.35%2C102.83%2C2.35%2C104.84"));
    }

    #[test]
    fn widens_the_search_when_nothing_is_near() {
        let remote = Location::new("Remote", -40.0, -120.0);
        let narrow = build_url(
            AWC_METAR_URL,
            &[("bbox", bbox(&remote, 1.0)), ("format", "json".into())],
        );
        let http = FixtureClient::new()
            .with(&narrow, Value::Array(vec![]))
            .with(AWC_METAR_URL, reports());
        let readings = NearestMetar::default()
            .fetch_at(&http, &remote, now())
            .unwrap();
        assert_eq!(http.request_log().len(), 2);
        assert!(!readings.is_empty());
    }

    #[test]
    fn empty_everywhere_is_no_readings_and_errors_propagate() {
        let http = FixtureClient::new().with(AWC_METAR_URL, Value::Null);
        assert!(NearestMetar::default()
            .fetch_at(&http, &bishan(), now())
            .unwrap()
            .is_empty());
        let http = FixtureClient::new().with_status(AWC_METAR_URL, 429);
        assert!(NearestMetar::default()
            .fetch_at(&http, &bishan(), now())
            .is_err());
    }

    #[test]
    fn us_wind_is_two_minute_and_calm_and_variable_read_well() {
        let report = serde_json::json!({
            "icaoId": "KDEN", "name": "Denver Intl, CO, US", "lat": 39.85, "lon": -104.66,
            "obsTime": 1792479600, "wdir": "VRB", "wspd": 3, "visib": 10, "temp": -2.5
        });
        let readings = readings(&report, 30.0);
        let wind = readings
            .iter()
            .find(|r| r.kind == ReadingKind::Wind)
            .unwrap();
        assert_eq!(wind.value, "Variable at 3 knots (6 km/h, 3 mph)");
        assert_eq!(wind.period.as_deref(), Some("2-minute average"));
        let vis = readings
            .iter()
            .find(|r| r.kind == ReadingKind::Visibility)
            .unwrap();
        assert_eq!(vis.value, "10 miles (16 km)");
        let calm = serde_json::json!({"icaoId": "EGLL", "wspd": 0, "wdir": 0});
        assert_eq!(wind_text(&calm), Some("Calm".into()));
    }

    fn wind_text(report: &Value) -> Option<String> {
        wind(report)
    }
}
