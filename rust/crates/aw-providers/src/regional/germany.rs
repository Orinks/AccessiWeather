//! Germany: Deutscher Wetterdienst (DWD) station observations through the
//! keyless Bright Sky API (`api.brightsky.dev`), which republishes DWD's
//! open data. `current_weather` returns the latest observation from the
//! nearest DWD station, filling gaps from other nearby stations; each
//! reading names the station it actually came from.

use aw_core::weather_client_parsers::degrees_to_cardinal;
use aw_core::Location;
use serde_json::Value;

use super::{
    celsius, in_country, kmh, parse_time, Coverage, LocalReading, ReadingKind, ReadingTime,
    RegionalError, RegionalSource,
};
use crate::http::{build_url, HttpClient};

pub const BASE_URL: &str = "https://api.brightsky.dev";
pub const SOURCE_NAME: &str = "Germany DWD";
const READING_SOURCE: &str = "Deutscher Wetterdienst (DWD) via Bright Sky";

/// Germany (min lat, min lon, max lat, max lon), used only when a location
/// has no country code.
const BBOX: [f64; 4] = [47.27, 5.87, 55.06, 15.04];

#[derive(Debug, Clone)]
pub struct BrightSkyDwd {
    pub base_url: String,
}

impl Default for BrightSkyDwd {
    fn default() -> Self {
        Self {
            base_url: BASE_URL.into(),
        }
    }
}

pub fn is_germany(location: &Location) -> bool {
    in_country(location, "DE", BBOX)
}

impl RegionalSource for BrightSkyDwd {
    fn name(&self) -> &'static str {
        SOURCE_NAME
    }

    fn covers(&self, location: &Location) -> bool {
        is_germany(location)
    }

    fn fetch(
        &self,
        http: &dyn HttpClient,
        location: &Location,
    ) -> Result<Vec<LocalReading>, RegionalError> {
        let mut params = vec![
            ("lat", format!("{:.4}", location.latitude)),
            ("lon", format!("{:.4}", location.longitude)),
        ];
        if let Some(tz) = location.timezone.as_deref().filter(|t| !t.is_empty()) {
            params.push(("tz", tz.to_string()));
        }
        let url = build_url(&format!("{}/current_weather", self.base_url), &params);
        let body = http.get_json(&url)?;
        parse_current_weather(&body)
            .ok_or_else(|| RegionalError::Data("Bright Sky response has no weather".into()))
    }
}

/// The station a field came from: its fallback source if it has one,
/// otherwise the main source.
fn station_for(body: &Value, field: &str) -> Option<Coverage> {
    let weather = body.get("weather")?;
    let id = weather
        .get("fallback_source_ids")
        .and_then(|f| f.get(field))
        .or_else(|| weather.get("source_id"))?
        .as_i64()?;
    let source = body
        .get("sources")?
        .as_array()?
        .iter()
        .find(|s| s.get("id").and_then(Value::as_i64) == Some(id))?;
    let name = source
        .get("station_name")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|n| !n.is_empty())?;
    let km = source
        .get("distance")
        .and_then(Value::as_f64)
        .map(|m| m / 1000.0);
    Some(Coverage::new(format!("{name} station"), km))
}

/// "partly-cloudy-day" -> "Partly cloudy".
fn icon_words(icon: &str) -> Option<String> {
    let words: Vec<&str> = icon
        .split('-')
        .filter(|w| !w.is_empty() && *w != "day" && *w != "night")
        .collect();
    let text = words.join(" ");
    let mut chars = text.chars();
    let first = chars.next()?;
    Some(first.to_uppercase().chain(chars).collect())
}

/// (kind, label, field naming the station, value, period).
type Row<'a> = (
    ReadingKind,
    &'a str,
    &'a str,
    Option<String>,
    Option<&'a str>,
);

fn parse_current_weather(body: &Value) -> Option<Vec<LocalReading>> {
    let weather = body.get("weather").filter(|w| w.is_object())?;
    let time = weather
        .get("timestamp")
        .and_then(Value::as_str)
        .and_then(parse_time)
        .map_or(ReadingTime::Unknown, ReadingTime::Observed);
    let number = |key: &str| weather.get(key).and_then(Value::as_f64);

    let conditions = weather
        .get("icon")
        .and_then(Value::as_str)
        .and_then(icon_words)
        .map(
            |words| match weather.get("condition").and_then(Value::as_str) {
                Some("thunderstorm") if !words.contains("Thunderstorm") => {
                    format!("{words}, thunderstorm")
                }
                _ => words,
            },
        );
    let wind = number("wind_speed_10").map(|speed| {
        let direction = number("wind_direction_10")
            .and_then(|d| degrees_to_cardinal(Some(d)))
            .map(|d| format!("{d} at "))
            .unwrap_or_default();
        let mut text = format!("{direction}{}", kmh(speed));
        if let Some(gust) = number("wind_gust_speed_10").filter(|g| *g > speed) {
            text.push_str(&format!(", gusting {}", kmh(gust)));
        }
        text
    });

    let rows: [Row; 8] = [
        (
            ReadingKind::Conditions,
            "Conditions",
            "icon",
            conditions,
            None,
        ),
        (
            ReadingKind::Temperature,
            "Temperature",
            "temperature",
            number("temperature").map(celsius),
            None,
        ),
        (
            ReadingKind::DewPoint,
            "Dew point",
            "dew_point",
            number("dew_point").map(celsius),
            None,
        ),
        (
            ReadingKind::Humidity,
            "Humidity",
            "relative_humidity",
            number("relative_humidity").map(|h| format!("{h:.0}%")),
            None,
        ),
        (
            ReadingKind::Rainfall,
            "Precipitation",
            "precipitation_60",
            number("precipitation_60").map(|mm| format!("{mm:.1} mm")),
            Some("past-hour total"),
        ),
        (
            ReadingKind::Wind,
            "Wind",
            "wind_speed_10",
            wind,
            Some("10-minute average"),
        ),
        (
            ReadingKind::Pressure,
            "Pressure",
            "pressure_msl",
            number("pressure_msl").map(|hpa| format!("{hpa:.0} hPa ({:.2} inHg)", hpa / 33.8639)),
            None,
        ),
        (
            ReadingKind::Visibility,
            "Visibility",
            "visibility",
            number("visibility")
                .map(|m| format!("{:.1} km ({:.1} miles)", m / 1000.0, m / 1609.344)),
            None,
        ),
    ];
    Some(
        rows.into_iter()
            .filter_map(|(kind, label, field, value, period)| {
                Some(LocalReading {
                    kind,
                    label: label.into(),
                    value: value?,
                    detail: None,
                    period: period.map(String::from),
                    coverage: station_for(body, field)?,
                    time: time.clone(),
                    source: READING_SOURCE.into(),
                })
            })
            .collect(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use crate::regional::{fetch_local_readings, metar, offset_hours};
    use chrono::TimeZone;

    fn fixture() -> Value {
        serde_json::from_str(include_str!(
            "../../../../testdata/regional/germany/current_weather.json"
        ))
        .unwrap()
    }

    fn berlin() -> Location {
        let mut l = Location::new("Berlin", 52.52, 13.405).with_country("DE");
        l.timezone = Some("Europe/Berlin".into());
        l
    }

    #[test]
    fn covers_germany_only() {
        assert!(is_germany(&berlin()));
        assert!(is_germany(&Location::new("Munich", 48.137, 11.575)));
        assert!(!is_germany(&Location::new("Paris", 48.857, 2.352)));
        // Strasbourg sits inside Germany's box but France's country code wins.
        assert!(!is_germany(
            &Location::new("Strasbourg", 48.573, 7.752).with_country("FR")
        ));
    }

    #[test]
    fn readings_name_their_own_station() {
        let http = FixtureClient::new().with(&format!("{BASE_URL}/current_weather"), fixture());
        let readings = BrightSkyDwd::default().fetch(&http, &berlin()).unwrap();
        assert_eq!(
            http.request_log(),
            vec![format!(
                "{BASE_URL}/current_weather?lat=52.5200&lon=13.4050&tz=Europe%2FBerlin"
            )]
        );
        let by_kind = |k| readings.iter().find(|r| r.kind == k).unwrap();

        let temp = by_kind(ReadingKind::Temperature);
        assert_eq!(temp.value, "16.7°C (62.1°F)");
        assert_eq!(temp.coverage.name, "Berlin-Tempelhof station");
        let km = temp.coverage.distance_km.unwrap();
        assert!((4.0..5.0).contains(&km), "{km}");
        assert_eq!(
            temp.time,
            ReadingTime::Observed(
                offset_hours(2)
                    .with_ymd_and_hms(2026, 10, 20, 9, 30, 0)
                    .unwrap()
            )
        );

        // Visibility is filled from another station.
        let vis = by_kind(ReadingKind::Visibility);
        assert_eq!(vis.coverage.name, "Berlin-Schoenefeld station");
        assert_eq!(vis.value, "35.0 km (21.7 miles)");

        assert_eq!(by_kind(ReadingKind::Conditions).value, "Partly cloudy");
        let rain = by_kind(ReadingKind::Rainfall);
        assert_eq!(rain.value, "0.3 mm");
        assert_eq!(rain.period.as_deref(), Some("past-hour total"));
        let wind = by_kind(ReadingKind::Wind);
        assert_eq!(
            wind.value,
            "WSW at 13 km/h (8 mph), gusting 29 km/h (18 mph)"
        );
        assert_eq!(wind.period.as_deref(), Some("10-minute average"));
        assert_eq!(by_kind(ReadingKind::Humidity).value, "67%");
        assert_eq!(
            by_kind(ReadingKind::Pressure).value,
            "1013 hPa (29.91 inHg)"
        );
    }

    #[test]
    fn germany_gets_dwd_then_the_airport_baseline() {
        let http = FixtureClient::new()
            .with(&format!("{BASE_URL}/current_weather"), fixture())
            .with(metar::AWC_METAR_URL, Value::Array(vec![]));
        let report = fetch_local_readings(&http, &berlin(), &crate::regional::default_sources());
        assert_eq!(report.sources, vec![SOURCE_NAME, metar::SOURCE_NAME]);
        assert!(report.failures.is_empty());
        assert!(report.readings.iter().all(|r| r.source == READING_SOURCE));
        assert!(!http.request_log().iter().any(|u| u.contains("data.gov.sg")));
    }

    #[test]
    fn missing_station_or_404_is_an_error() {
        let http = FixtureClient::new().with_status(BASE_URL, 404);
        assert!(BrightSkyDwd::default().fetch(&http, &berlin()).is_err());
        let http = FixtureClient::new().with(BASE_URL, serde_json::json!({"weather": null}));
        assert!(BrightSkyDwd::default().fetch(&http, &berlin()).is_err());
    }

    #[test]
    fn icons_read_as_words() {
        assert_eq!(
            icon_words("partly-cloudy-night").as_deref(),
            Some("Partly cloudy")
        );
        assert_eq!(icon_words("clear-day").as_deref(), Some("Clear"));
        assert_eq!(icon_words("thunderstorm").as_deref(), Some("Thunderstorm"));
        assert_eq!(icon_words(""), None);
    }
}
