//! Offline data for `--offline`, `--smoke` and `--check`: the recorded NWS
//! and Open-Meteo responses `rust/tools/golden/datapath.py` serves the
//! Python weather client (New York for US locations, London elsewhere),
//! answered by URL prefix as the golden tests answer them.

use std::sync::Arc;

use aw_core::display::{Clock, WeatherPresenter};
use aw_core::is_us_location;
use aw_core::model::{Location, WeatherData};
use aw_core::py;
use aw_core::settings::AppSettings;
use aw_providers::client::live::Live;
use aw_providers::client::WeatherClient;
use aw_providers::http::{FixtureClient, HttpClient, HttpError, HttpRequest, HttpResponse};
use chrono::{DateTime, Duration, NaiveDate, NaiveDateTime, SecondsFormat, Utc};
use chrono_tz::Tz;
use serde_json::Value;

use crate::ui::display::{panel_texts, PanelTexts};

/// Recorded runs of the Python client: New York in automatic mode, London.
pub(crate) const CASES: [&str; 2] = [
    include_str!("../../../testdata/golden/datapath/us_auto.json"),
    include_str!("../../../testdata/golden/datapath/intl_auto.json"),
];

const NWS_POINTS: &str = "https://api.weather.gov/points/";

pub(crate) fn case(text: &str) -> Value {
    serde_json::from_str(text).expect("embedded fixture is valid JSON")
}

fn location_of(case: &Value) -> Location {
    serde_json::from_value(case["location"].clone()).expect("fixture location")
}

/// A timestamp-like string moved by `by` in its own format, or `None`.
fn shifted(text: &str, by: Duration) -> Option<String> {
    if let Ok(t) = DateTime::parse_from_rfc3339(text) {
        return Some((t + by).to_rfc3339_opts(SecondsFormat::AutoSi, false));
    }
    for format in ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"] {
        if let Ok(t) = NaiveDateTime::parse_from_str(text, format) {
            return Some((t + by).format(format).to_string());
        }
    }
    NaiveDate::parse_from_str(text, "%Y-%m-%d")
        .ok()
        .map(|d| (d + by).format("%Y-%m-%d").to_string())
}

fn shift(value: &mut Value, by: Duration) {
    match value {
        Value::String(text) => {
            if let Some(moved) = shifted(text, by) {
                *text = moved;
            }
        }
        Value::Array(items) => items.iter_mut().for_each(|v| shift(v, by)),
        Value::Object(map) => map.values_mut().for_each(|v| shift(v, by)),
        _ => {}
    }
}

/// A `FixtureClient` answering the case's routes. With `today`, each body
/// moves forward by the whole days between its recording and today, so the
/// sample weather is current while times of day (sunrise, forecast periods)
/// stay realistic.
pub(crate) fn routes_client(case: &Value, today: Option<DateTime<Utc>>) -> FixtureClient {
    let mut http = FixtureClient::new();
    for route in case["routes"].as_array().expect("fixture routes") {
        let prefix = route["prefix"].as_str().unwrap_or_default();
        let status = route["status"].as_u64().unwrap_or(404) as u16;
        let mut body = route["body"].as_str().unwrap_or_default().to_string();
        let recorded = route["recorded_at"]
            .as_str()
            .and_then(|t| DateTime::parse_from_rfc3339(t).ok());
        if let (Some(today), Some(recorded)) = (today, recorded) {
            let days = ((today - recorded.with_timezone(&Utc)).num_seconds() as f64 / 86_400.0)
                .round() as i64;
            if let Ok(mut json) = serde_json::from_str::<Value>(&body) {
                shift(&mut json, Duration::days(days));
                body = json.to_string();
            }
        }
        http = if body.is_empty() && status >= 400 {
            http.with_status(prefix, status)
        } else {
            http.with_response(prefix, status, &body)
        };
    }
    http
}

/// `--offline`: any location gets the sample weather. NWS `/points` and
/// Open-Meteo requests are pointed at the recorded coordinates (New York for
/// US coordinates, London otherwise); everything else is answered as-is.
pub(crate) struct OfflineHttp {
    us: FixtureClient,
    us_location: Location,
    intl: FixtureClient,
    intl_location: Location,
}

pub(crate) fn offline_client(today: DateTime<Utc>) -> Arc<OfflineHttp> {
    let [us, intl] = CASES.map(case);
    Arc::new(OfflineHttp {
        us: routes_client(&us, Some(today)),
        us_location: location_of(&us),
        intl: routes_client(&intl, Some(today)),
        intl_location: location_of(&intl),
    })
}

impl OfflineHttp {
    fn coordinates(location: &Location) -> (String, String) {
        (
            py::float_repr(location.latitude),
            py::float_repr(location.longitude),
        )
    }

    fn route(&self, url: &str) -> (&FixtureClient, String) {
        if let Some(rest) = url.strip_prefix(NWS_POINTS) {
            let tail = rest.find(['/', '?']).map_or("", |i| &rest[i..]);
            let (lat, lon) = Self::coordinates(&self.us_location);
            return (&self.us, format!("{NWS_POINTS}{lat},{lon}{tail}"));
        }
        let Some((base, query)) = url.split_once('?') else {
            return (&self.us, url.to_string());
        };
        let param = |name: &str| {
            query
                .split('&')
                .find_map(|p| p.strip_prefix(name))
                .and_then(|v| v.parse::<f64>().ok())
        };
        let (Some(lat), Some(lon)) = (param("latitude="), param("longitude=")) else {
            return (&self.us, url.to_string());
        };
        let (client, location) = if is_us_location(&Location::new("", lat, lon)) {
            (&self.us, &self.us_location)
        } else {
            (&self.intl, &self.intl_location)
        };
        let (lat, lon) = Self::coordinates(location);
        let query: Vec<String> = query
            .split('&')
            .map(|p| {
                if p.starts_with("latitude=") {
                    format!("latitude={lat}")
                } else if p.starts_with("longitude=") {
                    format!("longitude={lon}")
                } else {
                    p.to_string()
                }
            })
            .collect();
        (client, format!("{base}?{}", query.join("&")))
    }
}

impl HttpClient for OfflineHttp {
    fn get_json(&self, url: &str) -> Result<Value, HttpError> {
        let (client, url) = self.route(url);
        client.get_json(&url)
    }

    fn get_json_with_headers(
        &self,
        url: &str,
        headers: &[(&str, &str)],
    ) -> Result<Value, HttpError> {
        let (client, url) = self.route(url);
        client.get_json_with_headers(&url, headers)
    }

    fn get_text(&self, url: &str) -> Result<String, HttpError> {
        let (client, url) = self.route(url);
        client.get_text(&url)
    }

    fn send(&self, req: &HttpRequest) -> Result<HttpResponse, HttpError> {
        let (client, url) = self.route(&req.url);
        client.send(&HttpRequest { url, ..req.clone() })
    }
}

/// The settings the case ran with: defaults plus its overrides.
fn case_settings(case: &Value) -> AppSettings {
    let mut value = serde_json::to_value(AppSettings::default()).expect("settings serialize");
    for (key, v) in case["settings"].as_object().into_iter().flatten() {
        value[key] = v.clone();
    }
    serde_json::from_value(value).expect("fixture settings")
}

/// Run a recorded case the way the Python golden did (frozen clock and
/// zone, recorded bodies): the weather data and the main window's panels.
pub(crate) fn replay(case: &Value) -> (WeatherData, PanelTexts) {
    let now: DateTime<Utc> = case["now"]
        .as_str()
        .and_then(|t| DateTime::parse_from_rfc3339(t).ok())
        .expect("fixture now")
        .with_timezone(&Utc);
    let tz: Tz = case["local_tz"]
        .as_str()
        .and_then(|t| t.parse().ok())
        .expect("fixture zone");
    let mut live = Live::new(Arc::new(routes_client(case, None)));
    live.local_now = Arc::new(move || now.with_timezone(&tz).fixed_offset());
    let settings = case_settings(case);
    let client = WeatherClient::new(
        live.sources(&settings),
        settings.clone(),
        &settings.data_source,
        None,
    )
    .with_clock(Arc::new(move || now));
    let weather = client.get_weather_data(&location_of(case), false);
    let presentation =
        WeatherPresenter::with_clock(&settings, Clock::fixed(now, tz)).present(&weather);
    (weather, panel_texts(&presentation))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recorded_cases_replay_to_the_python_panels() {
        for text in CASES {
            let case = case(text);
            let (weather, panels) = replay(&case);
            assert!(weather.has_any_data());
            let expected = &case["panels"];
            assert_eq!(panels.current, expected["current"].as_str().unwrap());
            assert_eq!(panels.daily, expected["daily"].as_str().unwrap());
            assert_eq!(panels.hourly, expected["hourly"].as_str().unwrap());
            assert_eq!(
                panels.stale_warning,
                expected["stale_warning"].as_str().unwrap()
            );
            assert_eq!(panels.briefing.as_deref(), expected["briefing"].as_str());
        }
    }

    #[test]
    fn offline_client_serves_any_location_today() {
        let today = Utc::now();
        let http = offline_client(today);
        let points = http
            .get_json("https://api.weather.gov/points/35.1,-90.05")
            .unwrap();
        assert!(points["properties"]["forecast"].is_string());
        let paris = http
            .get_json(
                "https://api.open-meteo.com/v1/forecast?latitude=48.85&longitude=2.35&current=x",
            )
            .unwrap();
        assert_eq!(paris["timezone"], "Europe/London");
        let observation = http
            .get_json("https://api.weather.gov/stations/KNYC/observations/latest")
            .unwrap();
        let observed =
            DateTime::parse_from_rfc3339(observation["properties"]["timestamp"].as_str().unwrap())
                .unwrap();
        assert!((today - observed.with_timezone(&Utc)).num_hours().abs() <= 13);
    }

    #[test]
    fn timestamps_shift_in_their_own_format() {
        let day = Duration::days(1);
        assert_eq!(
            shifted("2026-01-20T17:51:00+00:00", day).as_deref(),
            Some("2026-01-21T17:51:00+00:00")
        );
        assert_eq!(
            shifted("2026-05-11T23:00", day).as_deref(),
            Some("2026-05-12T23:00")
        );
        assert_eq!(shifted("2026-05-11", day).as_deref(), Some("2026-05-12"));
        assert_eq!(shifted("Tonight", day), None);
    }
}
