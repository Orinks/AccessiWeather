//! The app as the Weather Assistant's tools see it: the `_CombinedWeatherClient`
//! adapter and services built by `WeatherAssistantDialog._get_tool_executor`
//! (`ui/dialogs/weather_assistant_dialog.py`). Weather comes from NWS
//! (`NoaaApiClient`) with an Open-Meteo fallback (`OpenMeteoApiClient`),
//! both as raw JSON; saved locations are read and changed on the UI thread.

use std::sync::{mpsc, Arc};
use std::time::Duration;

use aw_ai::tools::AssistantHost;
use aw_core::Location;
use aw_providers::geocoding::GeocodingService;
use aw_providers::http::{HttpRequest, HttpResponse};
use aw_providers::nws::py_float_repr;
use aw_providers::products::national::{text_for, NationalDiscussionService};
use aw_providers::{HttpClient, HttpError};
use serde_json::Value;

use crate::app::{post_to_ui, save, with_state, State};

const NWS_BASE: &str = "https://api.weather.gov";
const OPEN_METEO_FORECAST: &str = "https://api.open-meteo.com/v1/forecast";
/// `NoaaApiClient`'s "{user_agent} ({contact_info})".
const NWS_USER_AGENT: &str = "AccessiWeather (AccessiWeather)";
const USER_AGENT: &str = "AccessiWeather";
/// `OpenMeteoApiClient(max_retries=3, retry_delay=1.0)`.
const OPEN_METEO_RETRIES: u32 = 3;

const CURRENT_VARIABLES: [&str; 17] = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "uv_index",
    "snowfall",
    "snow_depth",
    "visibility",
];
const CURRENT_DAILY_VARIABLES: [&str; 3] = ["sunrise", "sunset", "uv_index_max"];
const DAILY_VARIABLES: [&str; 14] = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "sunrise",
    "sunset",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "uv_index_max",
    "snowfall_sum",
];
const HOURLY_VARIABLES: [&str; 18] = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation_probability",
    "precipitation",
    "weather_code",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "is_day",
    "snowfall",
    "uv_index",
    "snow_depth",
    "freezing_level_height",
    "visibility",
];

type Params = Vec<(&'static str, String)>;

pub(crate) struct AppAssistantHost {
    http: Arc<dyn HttpClient>,
}

impl AppAssistantHost {
    pub(crate) fn new(http: Arc<dyn HttpClient>) -> Self {
        Self { http }
    }

    fn send(
        &self,
        url: &str,
        params: &[(&str, String)],
        headers: &[(&str, &str)],
    ) -> Result<HttpResponse, HttpError> {
        let mut request = HttpRequest::new(url);
        for (name, value) in headers {
            request = request.header(name, *value);
        }
        for (name, value) in params {
            request = request.param(name, value.clone());
        }
        self.http.send(&request)
    }

    /// `NoaaApiClient._make_request`: one GET with the NWS headers.
    fn nws(&self, url: &str, params: &[(&str, String)]) -> Result<Value, String> {
        let headers = [
            ("User-Agent", NWS_USER_AGENT),
            ("Accept", "application/geo+json"),
        ];
        self.send(url, params, &headers)
            .and_then(|response| {
                response.error_for_status()?;
                response.json()
            })
            .map_err(|e| e.to_string())
    }

    fn point(&self, lat: f64, lon: f64) -> Result<Value, String> {
        let url = format!(
            "{NWS_BASE}/points/{},{}",
            py_float_repr(lat),
            py_float_repr(lon)
        );
        self.nws(&url, &[])
    }

    /// A URL from the point's properties (`forecast`, `forecastHourly`, ...).
    fn point_url(&self, lat: f64, lon: f64, key: &str) -> Result<String, String> {
        self.point(lat, lon)?["properties"][key]
            .as_str()
            .filter(|u| !u.is_empty())
            .map(str::to_string)
            .ok_or_else(|| format!("Could not find {key} URL in point data"))
    }

    /// `NoaaApiClient.get_current_conditions`: the first station's latest observation.
    fn nws_current(&self, lat: f64, lon: f64) -> Result<Value, String> {
        let stations = self.nws(&self.point_url(lat, lon, "observationStations")?, &[])?;
        let station = stations["features"][0]["properties"]["stationIdentifier"]
            .as_str()
            .ok_or("No observation stations found for the given coordinates")?;
        self.nws(
            &format!("{NWS_BASE}/stations/{station}/observations/latest"),
            &[],
        )
    }

    /// `NoaaApiClient.get_discussion`: the office's latest AFD text.
    fn nws_discussion(&self, lat: f64, lon: f64) -> Result<Option<String>, String> {
        let point = self.point(lat, lon)?;
        let office = point["properties"]["gridId"]
            .as_str()
            .filter(|o| !o.is_empty())
            .ok_or("Could not find office ID in point data")?;
        let products = self.nws(
            &format!("{NWS_BASE}/products/types/AFD/locations/{office}"),
            &[],
        )?;
        let Some(id) = products["@graph"][0]["id"]
            .as_str()
            .filter(|i| !i.is_empty())
        else {
            return Ok(None);
        };
        let product = self.nws(&format!("{NWS_BASE}/products/{id}"), &[])?;
        Ok(product["productText"]
            .as_str()
            .filter(|t| !t.is_empty())
            .map(str::to_string))
    }

    /// `OpenMeteoApiClient._make_request("forecast", params)`: transport
    /// failures are retried three times, a second apart.
    fn open_meteo(&self, params: &[(&str, String)]) -> Result<Value, String> {
        let mut attempt = 0;
        let response = loop {
            match self.send(OPEN_METEO_FORECAST, params, &[("User-Agent", USER_AGENT)]) {
                Ok(response) => break response,
                Err(_) if attempt < OPEN_METEO_RETRIES => {
                    attempt += 1;
                    std::thread::sleep(Duration::from_secs(1));
                }
                Err(e) if e.is_timeout() => {
                    return Err(format!(
                        "Request timeout after {OPEN_METEO_RETRIES} retries: {e}"
                    ))
                }
                Err(e) => {
                    return Err(format!(
                        "Network error after {OPEN_METEO_RETRIES} retries: {e}"
                    ))
                }
            }
        };
        match response.status {
            400 => Err(format!(
                "API error: {}",
                response
                    .json()
                    .ok()
                    .and_then(|v| v["reason"].as_str().map(str::to_string))
                    .unwrap_or_else(|| "Bad request".into())
            )),
            429 => Err("Rate limit exceeded".into()),
            status if status >= 500 => Err(format!("Server error: {status}")),
            status if status >= 400 => Err(format!("Unexpected error: HTTP {status}")),
            _ => response
                .json()
                .map_err(|e| format!("Unexpected error: {e}")),
        }
    }

    fn geocoding(&self) -> GeocodingService<'_> {
        GeocodingService::new(self.http.as_ref(), USER_AGENT, "auto")
    }
}

/// httpx sends a list parameter as one `key=value` pair per item.
fn open_meteo_params(
    lat: f64,
    lon: f64,
    lists: &[(&'static str, &[&str])],
    tail: Params,
) -> Params {
    let mut params = vec![
        ("latitude", py_float_repr(lat)),
        ("longitude", py_float_repr(lon)),
    ];
    for (key, variables) in lists {
        params.extend(variables.iter().map(|v| (*key, v.to_string())));
    }
    params.extend([
        ("temperature_unit", "fahrenheit".to_string()),
        ("wind_speed_unit", "mph".into()),
        ("precipitation_unit", "inch".into()),
        ("timezone", "auto".into()),
    ]);
    params.extend(tail);
    params
}

/// Run `f` on the UI thread with the app state and wait for its result;
/// `None` when the app is gone or the state is busy.
fn on_ui<R: Send + 'static>(f: impl FnOnce(&mut State) -> R + Send + 'static) -> Option<R> {
    let (tx, rx) = mpsc::channel();
    post_to_ui(move || {
        let Some(state) = with_state() else { return };
        let Ok(mut st) = state.try_borrow_mut() else {
            return;
        };
        let _ = tx.send(f(&mut st));
    });
    rx.recv().ok()
}

impl AssistantHost for AppAssistantHost {
    fn geocode(&self, query: &str) -> Option<(f64, f64, String)> {
        self.geocoding().geocode_address(query)
    }

    fn suggest_locations(&self, query: &str, limit: usize) -> Vec<String> {
        self.geocoding().suggest_locations(query, limit)
    }

    fn current_conditions(&self, lat: f64, lon: f64) -> Result<Value, String> {
        self.nws_current(lat, lon).or_else(|_| {
            self.open_meteo(&open_meteo_params(
                lat,
                lon,
                &[
                    ("current", &CURRENT_VARIABLES),
                    ("daily", &CURRENT_DAILY_VARIABLES),
                ],
                vec![("forecast_days", "1".into())],
            ))
        })
    }

    fn forecast(&self, lat: f64, lon: f64, days: u32) -> Result<Value, String> {
        self.point_url(lat, lon, "forecast")
            .and_then(|url| self.nws(&url, &[]))
            .or_else(|_| {
                self.open_meteo(&open_meteo_params(
                    lat,
                    lon,
                    &[("daily", &DAILY_VARIABLES)],
                    vec![("forecast_days", days.min(16).to_string())],
                ))
            })
    }

    fn hourly_forecast(&self, lat: f64, lon: f64) -> Result<Value, String> {
        self.point_url(lat, lon, "forecastHourly")
            .and_then(|url| self.nws(&url, &[]))
            .or_else(|_| {
                self.open_meteo(&open_meteo_params(
                    lat,
                    lon,
                    &[("hourly", &HOURLY_VARIABLES)],
                    vec![("forecast_hours", "48".into())],
                ))
            })
    }

    fn alerts(&self, lat: f64, lon: f64) -> Result<Value, String> {
        self.nws(
            &format!("{NWS_BASE}/alerts/active"),
            &[(
                "point",
                format!("{},{}", py_float_repr(lat), py_float_repr(lon)),
            )],
        )
    }

    fn discussion(&self, lat: f64, lon: f64) -> Result<Option<String>, String> {
        // `get_discussion` reports every failure as "no discussion".
        Ok(self.nws_discussion(lat, lon).unwrap_or_else(|e| {
            tracing::error!("Error getting discussion: {e}");
            None
        }))
    }

    fn wpc_short_range_discussion(&self) -> Result<String, String> {
        let group = NationalDiscussionService::new(self.http.clone()).fetch_wpc_discussions();
        Ok(text_for(&group, "short_range").unwrap_or("").to_string())
    }

    fn spc_day1_outlook(&self) -> Result<String, String> {
        let group = NationalDiscussionService::new(self.http.clone()).fetch_spc_discussions();
        Ok(text_for(&group, "day1").unwrap_or("").to_string())
    }

    fn open_meteo_forecast(&self, params: &[(&'static str, String)]) -> Result<Value, String> {
        self.open_meteo(params)
    }

    fn location_names(&self) -> Vec<String> {
        on_ui(|st| st.config.location_names()).unwrap_or_default()
    }

    fn add_location(&self, name: &str, latitude: f64, longitude: f64) -> bool {
        let location = Location::new(name, latitude, longitude);
        on_ui(move |st| st.config.add_location(location) && save(st).is_ok()).unwrap_or(false)
    }

    fn saved_locations(&self) -> Vec<Location> {
        on_ui(|st| st.config.locations.clone()).unwrap_or_default()
    }

    fn current_location_name(&self) -> Option<String> {
        on_ui(|st| st.config.current_location.as_ref().map(|l| l.name.clone())).flatten()
    }
}

#[cfg(test)]
mod tests {
    use aw_providers::http::FixtureClient;
    use serde_json::json;

    use super::*;

    const POINT: &str = "https://api.weather.gov/points/39.97,-74.8";

    fn fixture_host(client: FixtureClient) -> (AppAssistantHost, Arc<FixtureClient>) {
        let client = Arc::new(client);
        (AppAssistantHost::new(client.clone()), client)
    }

    #[test]
    fn nws_current_conditions_use_the_first_station() {
        let (host, client) = fixture_host(
            FixtureClient::new()
                .with(POINT, json!({"properties": {"observationStations": "https://api.weather.gov/gridpoints/PHI/1,2/stations"}}))
                .with(
                    "https://api.weather.gov/gridpoints/PHI/1,2/stations",
                    json!({"features": [{"properties": {"stationIdentifier": "KPHL"}}, {"properties": {"stationIdentifier": "KPNE"}}]}),
                )
                .with(
                    "https://api.weather.gov/stations/KPHL/observations/latest",
                    json!({"properties": {"timestamp": "now"}}),
                ),
        );
        assert_eq!(
            host.current_conditions(39.97, -74.8).unwrap(),
            json!({"properties": {"timestamp": "now"}})
        );
        let sent = client.sent_requests();
        assert_eq!(sent.len(), 3);
        assert_eq!(
            sent[0].headers,
            [
                ("User-Agent".to_string(), NWS_USER_AGENT.to_string()),
                ("Accept".to_string(), "application/geo+json".to_string())
            ]
        );
    }

    #[test]
    fn open_meteo_fallback_sends_python_parameters() {
        let (host, client) = fixture_host(
            FixtureClient::new()
                .with_status(POINT, 500)
                .with(OPEN_METEO_FORECAST, json!({"daily": {}})),
        );
        assert_eq!(
            host.forecast(39.97, -74.8, 20).unwrap(),
            json!({"daily": {}})
        );
        let sent = client.sent_requests();
        let request = sent.last().unwrap();
        assert_eq!(request.url, OPEN_METEO_FORECAST);
        let params: Vec<(&str, &str)> = request
            .params
            .iter()
            .map(|(k, v)| (k.as_str(), v.as_str()))
            .collect();
        assert_eq!(
            params[..3],
            [
                ("latitude", "39.97"),
                ("longitude", "-74.8"),
                ("daily", "weather_code")
            ]
        );
        assert_eq!(
            params[params.len() - 5..],
            [
                ("temperature_unit", "fahrenheit"),
                ("wind_speed_unit", "mph"),
                ("precipitation_unit", "inch"),
                ("timezone", "auto"),
                ("forecast_days", "16")
            ]
        );
        assert_eq!(params.iter().filter(|(k, _)| *k == "daily").count(), 14);
    }

    #[test]
    fn open_meteo_errors_read_like_python() {
        let (host, _) = fixture_host(FixtureClient::new().with_response(
            OPEN_METEO_FORECAST,
            400,
            r#"{"error": true, "reason": "Cannot initialize WeatherVariable from invalid String value x"}"#,
        ));
        assert_eq!(
            host.open_meteo_forecast(&[("current", "x".into())])
                .unwrap_err(),
            "API error: Cannot initialize WeatherVariable from invalid String value x"
        );
        let (host, _) = fixture_host(FixtureClient::new().with_status(OPEN_METEO_FORECAST, 429));
        assert_eq!(
            host.open_meteo_forecast(&[]).unwrap_err(),
            "Rate limit exceeded"
        );
        let (host, _) = fixture_host(FixtureClient::new().with_status(OPEN_METEO_FORECAST, 503));
        assert_eq!(
            host.open_meteo_forecast(&[]).unwrap_err(),
            "Server error: 503"
        );
    }

    #[test]
    fn alerts_and_discussion_follow_the_point() {
        let (host, client) = fixture_host(
            FixtureClient::new()
                .with(
                    "https://api.weather.gov/alerts/active",
                    json!({"features": []}),
                )
                .with(POINT, json!({"properties": {"gridId": "PHI"}}))
                .with(
                    "https://api.weather.gov/products/types/AFD/locations/PHI",
                    json!({"@graph": [{"id": "abc"}, {"id": "older"}]}),
                )
                .with(
                    "https://api.weather.gov/products/abc",
                    json!({"productText": "AFD text"}),
                ),
        );
        assert_eq!(host.alerts(39.97, -74.8).unwrap(), json!({"features": []}));
        assert_eq!(
            client.sent_requests()[0].params,
            [("point".to_string(), "39.97,-74.8".to_string())]
        );
        assert_eq!(
            host.discussion(39.97, -74.8).unwrap().as_deref(),
            Some("AFD text")
        );
        let (host, _) = fixture_host(FixtureClient::new().with_status(POINT, 404));
        assert_eq!(host.discussion(39.97, -74.8).unwrap(), None);
    }
}
