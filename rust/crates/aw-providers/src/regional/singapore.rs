//! Singapore: National Environment Agency (NEA) real-time readings from
//! data.gov.sg. Rainfall and air temperature come from the nearest
//! station, the 2-hour forecast (which carries thundery showers) from the
//! nearest forecast area, and PM2.5 and PSI (haze) from the nearest region.
//!
//! API generation: the v2 real-time API at
//! `api-open.data.gov.sg/v2/real-time/api/...`. data.gov.sg's developer
//! guide documents only v2 for real-time data; the older
//! `api.data.gov.sg/v1/environment/...` endpoints are legacy. v2 needs no
//! key for basic use (an optional `x-api-key` only raises rate limits).
//! Responses are wrapped as `{"code": 0, "errorMsg": "", "data": {...}}`.

use aw_core::Location;
use serde_json::Value;

use super::{
    celsius, in_country, nearest, parse_time, Coverage, LocalReading, ReadingKind, ReadingTime,
    RegionalError, RegionalSource,
};
use crate::http::HttpClient;

pub const BASE_URL: &str = "https://api-open.data.gov.sg/v2/real-time/api";
pub const SOURCE_NAME: &str = "Singapore NEA";

/// Singapore's main island and outlying islands (min lat, min lon, max lat,
/// max lon), used only when a location has no country code.
const BBOX: [f64; 4] = [1.15, 103.59, 1.48, 104.10];

/// The NEA real-time source.
#[derive(Debug, Clone)]
pub struct SingaporeNea {
    pub base_url: String,
}

impl Default for SingaporeNea {
    fn default() -> Self {
        Self {
            base_url: BASE_URL.into(),
        }
    }
}

/// Whether a location is in Singapore: country code SG, or inside
/// Singapore's bounding box when no country code is set.
pub fn is_singapore(location: &Location) -> bool {
    in_country(location, "SG", BBOX)
}

impl RegionalSource for SingaporeNea {
    fn name(&self) -> &'static str {
        SOURCE_NAME
    }

    fn covers(&self, location: &Location) -> bool {
        is_singapore(location)
    }

    fn fetch(
        &self,
        http: &dyn HttpClient,
        location: &Location,
    ) -> Result<Vec<LocalReading>, RegionalError> {
        type Parser = fn(&Value, &Location) -> Option<LocalReading>;
        let endpoints: [(&str, Parser); 5] = [
            ("two-hr-forecast", parse_area_forecast),
            ("air-temperature", parse_air_temperature),
            ("rainfall", parse_rainfall),
            ("pm25", parse_pm25),
            ("psi", parse_psi),
        ];
        let mut readings = Vec::new();
        let mut first_error = None;
        for (path, parse) in endpoints {
            let url = format!("{}/{path}", self.base_url);
            match http
                .get_json(&url)
                .map_err(RegionalError::from)
                .and_then(unwrap)
            {
                Ok(data) => readings.extend(parse(&data, location)),
                Err(e) => {
                    tracing::debug!("Singapore NEA {path} failed: {e}");
                    first_error.get_or_insert(e);
                }
            }
        }
        match first_error {
            Some(e) if readings.is_empty() => Err(e),
            _ => Ok(readings),
        }
    }
}

/// The `data` object of a successful response.
fn unwrap(body: Value) -> Result<Value, RegionalError> {
    let code = body.get("code").and_then(Value::as_i64).unwrap_or(0);
    if code != 0 {
        let message = body
            .get("errorMsg")
            .and_then(Value::as_str)
            .filter(|m| !m.is_empty())
            .unwrap_or("request failed");
        return Err(RegionalError::Data(format!(
            "data.gov.sg error {code}: {message}"
        )));
    }
    match body.get("data") {
        Some(data @ Value::Object(_)) => Ok(data.clone()),
        _ => Err(RegionalError::Data(
            "data.gov.sg response has no data".into(),
        )),
    }
}

fn lat_lon(location: Option<&Value>) -> Option<(f64, f64)> {
    let location = location?;
    let lat = location.get("latitude")?.as_f64()?;
    let lon = location.get("longitude")?.as_f64()?;
    // Region metadata uses 0,0 for "national", which has no place.
    (lat != 0.0 || lon != 0.0).then_some((lat, lon))
}

fn str_field<'a>(value: &'a Value, keys: &[&str]) -> Option<&'a str> {
    keys.iter()
        .find_map(|k| value.get(*k).and_then(Value::as_str))
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

/// A station network reading (rainfall, air temperature): the nearest
/// station with a value in the latest reading set.
fn nearest_station_value(
    data: &Value,
    location: &Location,
) -> Option<(String, f64, f64, ReadingTime)> {
    let latest = data.get("readings")?.as_array()?.first()?;
    let time = str_field(latest, &["timestamp"])
        .and_then(parse_time)
        .map_or(ReadingTime::Unknown, ReadingTime::Observed);
    let values: Vec<(&str, f64)> = latest
        .get("data")?
        .as_array()?
        .iter()
        .filter_map(|d| {
            let id = str_field(d, &["stationId", "station_id"])?;
            Some((id, d.get("value")?.as_f64()?))
        })
        .collect();
    let stations = data.get("stations")?.as_array()?;
    let (station, value, km) = nearest(
        location,
        stations.iter().filter_map(|s| {
            let id = str_field(s, &["id"])?;
            let value = values.iter().find(|(v, _)| *v == id)?.1;
            Some((s, value))
        }),
        |(s, _)| lat_lon(s.get("location")),
    )
    .map(|((s, v), km)| (s, v, km))?;
    let name = str_field(station, &["name"])
        .unwrap_or("Unnamed")
        .to_string();
    Some((name, value, km, time))
}

fn parse_rainfall(data: &Value, location: &Location) -> Option<LocalReading> {
    let (name, value, km, time) = nearest_station_value(data, location)?;
    Some(LocalReading {
        kind: ReadingKind::Rainfall,
        label: "Rainfall".into(),
        value: format!("{value:.1} mm"),
        detail: None,
        period: Some("5-minute total".into()),
        coverage: Coverage::new(format!("{name} station"), Some(km)),
        time,
        source: SOURCE_NAME.into(),
    })
}

fn parse_air_temperature(data: &Value, location: &Location) -> Option<LocalReading> {
    let (name, value, km, time) = nearest_station_value(data, location)?;
    Some(LocalReading {
        kind: ReadingKind::Temperature,
        label: "Air temperature".into(),
        value: celsius(value),
        detail: None,
        period: Some("1-minute average".into()),
        coverage: Coverage::new(format!("{name} station"), Some(km)),
        time,
        source: SOURCE_NAME.into(),
    })
}

fn parse_area_forecast(data: &Value, location: &Location) -> Option<LocalReading> {
    let item = data.get("items")?.as_array()?.first()?;
    let forecasts = item.get("forecasts")?.as_array()?;
    let forecast_for = |area: &str| {
        forecasts.iter().find_map(|f| {
            (str_field(f, &["area"])? == area).then(|| match f.get("forecast") {
                Some(Value::String(text)) => Some(text.trim().to_string()),
                Some(obj @ Value::Object(_)) => {
                    str_field(obj, &["text", "summary"]).map(String::from)
                }
                _ => None,
            })?
        })
    };
    let areas = data.get("area_metadata")?.as_array()?;
    let ((area, text), km) = nearest(
        location,
        areas.iter().filter_map(|a| {
            let name = str_field(a, &["name"])?;
            Some(((a, name), forecast_for(name)?))
        }),
        |((a, _), _)| lat_lon(a.get("label_location").or_else(|| a.get("labelLocation"))),
    )?;
    let period = item.get("valid_period").or_else(|| item.get("validPeriod"));
    let start = period
        .and_then(|p| str_field(p, &["start"]))
        .and_then(parse_time);
    let end = period
        .and_then(|p| str_field(p, &["end"]))
        .and_then(parse_time);
    let time = match (start, end) {
        (Some(start), Some(end)) => ReadingTime::Valid { start, end },
        _ => ReadingTime::Unknown,
    };
    Some(LocalReading {
        kind: ReadingKind::Forecast,
        label: "2-hour forecast".into(),
        value: text,
        detail: None,
        period: None,
        coverage: Coverage::new(format!("{} forecast area", area.1), Some(km)),
        time,
        source: SOURCE_NAME.into(),
    })
}

/// The nearest region's value under `readings.<key>`, with the item's time.
fn nearest_region_value(
    data: &Value,
    location: &Location,
    key: &str,
) -> Option<(String, f64, ReadingTime)> {
    let item = data.get("items")?.as_array()?.first()?;
    let values = item.get("readings")?.get(key)?.as_object()?;
    let regions = data
        .get("regionMetadata")
        .or_else(|| data.get("region_metadata"))?
        .as_array()?;
    let ((name, value), _) = nearest(
        location,
        regions.iter().filter_map(|r| {
            let name = str_field(r, &["name"])?;
            Some(((r, name), values.get(name)?.as_f64()?))
        }),
        |((r, _), _)| lat_lon(r.get("labelLocation").or_else(|| r.get("label_location"))),
    )
    .map(|(((_, name), value), km)| ((name, value), km))?;
    let time = str_field(item, &["timestamp", "updatedTimestamp", "update_timestamp"])
        .and_then(parse_time)
        .map_or(ReadingTime::Unknown, ReadingTime::Observed);
    let mut region = name.to_string();
    if let Some(first) = region.get_mut(0..1) {
        first.make_ascii_uppercase();
    }
    Some((format!("{region} region"), value, time))
}

/// NEA's 1-hour PM2.5 bands.
fn pm25_band(value: f64) -> &'static str {
    match value {
        v if v <= 55.0 => "Band I, normal",
        v if v <= 150.0 => "Band II, elevated",
        v if v <= 250.0 => "Band III, high",
        _ => "Band IV, very high",
    }
}

/// PSI descriptors.
fn psi_band(value: f64) -> &'static str {
    match value {
        v if v <= 50.0 => "good",
        v if v <= 100.0 => "moderate",
        v if v <= 200.0 => "unhealthy",
        v if v <= 300.0 => "very unhealthy",
        _ => "hazardous",
    }
}

fn parse_pm25(data: &Value, location: &Location) -> Option<LocalReading> {
    let (region, value, time) = nearest_region_value(data, location, "pm25_one_hourly")?;
    Some(LocalReading {
        kind: ReadingKind::Pm25,
        label: "PM2.5".into(),
        value: format!("{value:.0} µg/m³"),
        detail: Some(pm25_band(value).into()),
        period: Some("1-hour average".into()),
        coverage: Coverage::new(region, None),
        time,
        source: SOURCE_NAME.into(),
    })
}

fn parse_psi(data: &Value, location: &Location) -> Option<LocalReading> {
    let (region, value, time) = nearest_region_value(data, location, "psi_twenty_four_hourly")?;
    Some(LocalReading {
        kind: ReadingKind::Psi,
        label: "PSI".into(),
        value: format!("{value:.0}"),
        detail: Some(psi_band(value).into()),
        period: Some("24-hour average".into()),
        coverage: Coverage::new(region, None),
        time,
        source: SOURCE_NAME.into(),
    })
}

#[cfg(test)]
mod tests {
    use chrono::{TimeZone, Utc};
    use serde_json::Value;

    use super::*;
    use crate::http::FixtureClient;
    use crate::regional::{fetch_local_readings, offset_hours, TimeStyle};

    fn fixture(name: &str) -> Value {
        let text = match name {
            "rainfall" => include_str!("../../../../testdata/regional/singapore/rainfall.json"),
            "air-temperature" => {
                include_str!("../../../../testdata/regional/singapore/air-temperature.json")
            }
            "two-hr-forecast" => {
                include_str!("../../../../testdata/regional/singapore/two-hr-forecast.json")
            }
            "pm25" => include_str!("../../../../testdata/regional/singapore/pm25.json"),
            "psi" => include_str!("../../../../testdata/regional/singapore/psi.json"),
            _ => unreachable!(),
        };
        serde_json::from_str(text).unwrap()
    }

    fn all_fixtures() -> FixtureClient {
        [
            "rainfall",
            "air-temperature",
            "two-hr-forecast",
            "pm25",
            "psi",
        ]
        .into_iter()
        .fold(FixtureClient::new(), |c, name| {
            c.with(&format!("{BASE_URL}/{name}"), fixture(name))
        })
    }

    /// Bishan, between the Ang Mo Kio and Toa Payoh stations.
    fn bishan() -> Location {
        Location::new("Bishan", 1.3526, 103.8352).with_country("SG")
    }

    #[test]
    fn covers_singapore_only() {
        assert!(is_singapore(&bishan()));
        assert!(is_singapore(&Location::new("Changi", 1.3644, 103.9915)));
        assert!(!is_singapore(&Location::new(
            "Kuala Lumpur",
            3.139,
            101.6869
        )));
        assert!(!is_singapore(
            &Location::new("Johor Bahru", 1.4655, 103.7578).with_country("MY")
        ));
        assert!(!is_singapore(
            &Location::new("London", 51.5, -0.12).with_country("GB")
        ));
    }

    #[test]
    fn picks_nearest_station_area_and_region() {
        let http = all_fixtures();
        let readings = SingaporeNea::default().fetch(&http, &bishan()).unwrap();
        let by_kind = |k| readings.iter().find(|r| r.kind == k).unwrap();

        let rain = by_kind(ReadingKind::Rainfall);
        assert_eq!(rain.coverage.name, "Ang Mo Kio Avenue 5 station");
        let km = rain.coverage.distance_km.unwrap();
        assert!((3.0..3.5).contains(&km), "{km}");
        assert_eq!(rain.value, "0.4 mm");
        assert_eq!(rain.period.as_deref(), Some("5-minute total"));
        assert_eq!(
            rain.time,
            ReadingTime::Observed(
                offset_hours(8)
                    .with_ymd_and_hms(2026, 10, 20, 15, 5, 0)
                    .unwrap()
            )
        );

        // S109 (the nearest temperature station) has no value, so the next
        // nearest station with a reading is used.
        let temp = by_kind(ReadingKind::Temperature);
        assert_eq!(temp.coverage.name, "Scotts Road station");
        assert_eq!(temp.value, "30.2°C (86.4°F)");

        let forecast = by_kind(ReadingKind::Forecast);
        assert_eq!(forecast.value, "Thundery Showers");
        assert_eq!(forecast.coverage.name, "Bishan forecast area");
        assert!(matches!(forecast.time, ReadingTime::Valid { .. }));

        let pm25 = by_kind(ReadingKind::Pm25);
        assert_eq!(pm25.coverage.name, "Central region");
        assert_eq!(pm25.value, "18 µg/m³");
        assert_eq!(pm25.detail.as_deref(), Some("Band I, normal"));
        assert_eq!(pm25.period.as_deref(), Some("1-hour average"));

        let psi = by_kind(ReadingKind::Psi);
        assert_eq!(psi.value, "57");
        assert_eq!(psi.detail.as_deref(), Some("moderate"));
        assert_eq!(psi.period.as_deref(), Some("24-hour average"));
        assert_eq!(psi.coverage.name, "Central region");
    }

    #[test]
    fn east_coast_gets_east_region_and_changi_area() {
        let http = all_fixtures();
        let changi = Location::new("Changi", 1.3644, 103.9915).with_country("SG");
        let readings = SingaporeNea::default().fetch(&http, &changi).unwrap();
        let by_kind = |k| readings.iter().find(|r| r.kind == k).unwrap();
        assert_eq!(by_kind(ReadingKind::Pm25).coverage.name, "East region");
        assert_eq!(
            by_kind(ReadingKind::Forecast).coverage.name,
            "Changi forecast area"
        );
        assert_eq!(
            by_kind(ReadingKind::Rainfall).coverage.name,
            "Upper Changi Road North station"
        );
    }

    #[test]
    fn full_lines_read_well() {
        let http = all_fixtures();
        let readings = SingaporeNea::default().fetch(&http, &bishan()).unwrap();
        let style = TimeStyle {
            timezone: Some("Asia/Singapore"),
            twelve_hour: true,
            now: Utc.with_ymd_and_hms(2026, 10, 20, 7, 10, 0).unwrap(),
        };
        let lines: Vec<String> = readings.iter().map(|r| r.to_line(&style)).collect();
        assert!(
            lines.contains(
                &"2-hour forecast: Thundery Showers. Bishan forecast area, 470 m away. \
              Valid 3:00 PM to 5:00 PM. Source: Singapore NEA."
                    .to_string()
            ),
            "{lines:#?}"
        );
        assert!(
            lines.contains(
                &"PSI: 57 (moderate), 24-hour average. Central region. \
              Observed 3:00 PM, 10 minutes ago. Source: Singapore NEA."
                    .to_string()
            ),
            "{lines:#?}"
        );
    }

    #[test]
    fn partial_failure_keeps_the_other_readings() {
        let http = all_fixtures()
            .with_status(&format!("{BASE_URL}/pm25"), 500)
            .with_response(
                &format!("{BASE_URL}/psi"),
                200,
                r#"{"code":17,"errorMsg":"Rate limit exceeded","data":null}"#,
            );
        let readings = SingaporeNea::default().fetch(&http, &bishan()).unwrap();
        assert!(readings
            .iter()
            .all(|r| !matches!(r.kind, ReadingKind::Pm25 | ReadingKind::Psi)));
        assert_eq!(readings.len(), 3);
    }

    #[test]
    fn total_failure_is_an_error_the_registry_absorbs() {
        let http = FixtureClient::new().with_transport_error(BASE_URL, "timed out");
        assert!(SingaporeNea::default().fetch(&http, &bishan()).is_err());
        let sources: Vec<Box<dyn RegionalSource>> = vec![Box::new(SingaporeNea::default())];
        let report = fetch_local_readings(&http, &bishan(), &sources);
        assert!(report.readings.is_empty());
        assert_eq!(report.failures.len(), 1);
        assert_eq!(report.failures[0].source, SOURCE_NAME);
    }

    #[test]
    fn malformed_bodies_yield_nothing_not_panics() {
        let http = [
            "rainfall",
            "air-temperature",
            "two-hr-forecast",
            "pm25",
            "psi",
        ]
        .into_iter()
        .fold(FixtureClient::new(), |c, name| {
            c.with(
                &format!("{BASE_URL}/{name}"),
                serde_json::json!({"code": 0, "data": {"items": [{}], "readings": "x"}}),
            )
        });
        assert_eq!(
            SingaporeNea::default().fetch(&http, &bishan()).unwrap(),
            vec![]
        );
    }

    #[test]
    fn never_fetched_outside_singapore() {
        let http = FixtureClient::new();
        let sources: Vec<Box<dyn RegionalSource>> = vec![Box::new(SingaporeNea::default())];
        let tokyo = Location::new("Tokyo", 35.68, 139.69).with_country("JP");
        let report = fetch_local_readings(&http, &tokyo, &sources);
        assert!(http.request_log().is_empty());
        assert!(report.sources.is_empty());
    }

    #[test]
    fn bands() {
        assert_eq!(pm25_band(55.0), "Band I, normal");
        assert_eq!(pm25_band(56.0), "Band II, elevated");
        assert_eq!(pm25_band(251.0), "Band IV, very high");
        assert_eq!(psi_band(50.0), "good");
        assert_eq!(psi_band(301.0), "hazardous");
    }
}
