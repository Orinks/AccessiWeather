//! Open-Meteo forecast API (api.open-meteo.com), ported from
//! `accessiweather.openmeteo_client` (the dict-returning client used by the
//! weather service) and `accessiweather.weather_client_openmeteo` (the
//! model-returning fetchers used by the weather client).
//!
//! Open-Meteo has no alerts; only current, daily and hourly data.

pub mod current;
pub mod legacy;
pub mod mapper;
pub mod parse;
pub mod units;

use aw_core::model::{CurrentConditions, Forecast, HourlyForecast, Location};
use aw_core::py;
use chrono::Local;
use serde_json::Value;

use crate::http::{build_url, HttpClient, HttpError};

pub use current::{
    parse_iso_datetime, parse_openmeteo_current_conditions, pick_precipitation_type,
    resolve_current_condition_description,
};
// The legacy orchestrator (`weather_client.rs`) still uses these.
pub use legacy::{parse_bundle, Bundle, OpenMeteoClient};
pub use parse::{format_wind_speed_mph, parse_openmeteo_forecast, parse_openmeteo_hourly_forecast};

pub const BASE_URL: &str = "https://api.open-meteo.com/v1";
pub const ARCHIVE_BASE_URL: &str = "https://archive-api.open-meteo.com/v1";

#[derive(Debug, thiserror::Error)]
pub enum OpenMeteoError {
    #[error("{0}")]
    Api(String),
    #[error("{0}")]
    Network(String),
}

/// Dict-returning client (`OpenMeteoApiClient`). Responses are raw JSON for
/// the NWS-shaped mapper in [`mapper`].
pub struct OpenMeteoApiClient<'a> {
    http: &'a dyn HttpClient,
    pub user_agent: String,
}

fn common_units(
    temperature_unit: &str,
    wind_speed_unit: &str,
    precipitation_unit: &str,
) -> [(&'static str, String); 4] {
    [
        ("temperature_unit", temperature_unit.to_string()),
        ("wind_speed_unit", wind_speed_unit.to_string()),
        ("precipitation_unit", precipitation_unit.to_string()),
        ("timezone", "auto".to_string()),
    ]
}

fn list_param(name: &'static str, values: &[&str]) -> Vec<(&'static str, String)> {
    values.iter().map(|v| (name, v.to_string())).collect()
}

fn with_model(mut params: Vec<(&'static str, String)>, model: &str) -> Vec<(&'static str, String)> {
    if !model.is_empty() && model != "best_match" {
        params.push(("models", model.to_string()));
    }
    params
}

impl<'a> OpenMeteoApiClient<'a> {
    pub fn new(http: &'a dyn HttpClient) -> Self {
        Self {
            http,
            user_agent: "AccessiWeather".into(),
        }
    }

    fn make_request(
        &self,
        endpoint: &str,
        params: &[(&'static str, String)],
        use_archive: bool,
    ) -> Result<Value, OpenMeteoError> {
        let base = if use_archive {
            ARCHIVE_BASE_URL
        } else {
            BASE_URL
        };
        let url = build_url(&format!("{base}/{endpoint}"), params);
        self.http
            .get_json_with_headers(&url, &[("User-Agent", &self.user_agent)])
            .map_err(|e| match e {
                HttpError::Status { status: 400, .. } => {
                    OpenMeteoError::Api("API error: Bad request".into())
                }
                HttpError::Status { status: 429, .. } => {
                    OpenMeteoError::Api("Rate limit exceeded".into())
                }
                HttpError::Status { status, .. } if status >= 500 => {
                    OpenMeteoError::Api(format!("Server error: {status}"))
                }
                HttpError::Transport { .. } if e.is_timeout() => {
                    OpenMeteoError::Network(format!("Request timeout after 3 retries: {e}"))
                }
                HttpError::Transport { .. } => {
                    OpenMeteoError::Network(format!("Network error after 3 retries: {e}"))
                }
                other => OpenMeteoError::Api(format!("Unexpected error: {other}")),
            })
    }

    pub fn get_current_weather(
        &self,
        latitude: f64,
        longitude: f64,
        temperature_unit: &str,
        wind_speed_unit: &str,
        precipitation_unit: &str,
        model: &str,
    ) -> Result<Value, OpenMeteoError> {
        let mut params = vec![
            ("latitude", py::float_repr(latitude)),
            ("longitude", py::float_repr(longitude)),
        ];
        params.extend(list_param(
            "current",
            &[
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
            ],
        ));
        params.extend(list_param("daily", &["sunrise", "sunset", "uv_index_max"]));
        params.extend(common_units(
            temperature_unit,
            wind_speed_unit,
            precipitation_unit,
        ));
        params.push(("forecast_days", "1".into()));
        self.make_request("forecast", &with_model(params, model), false)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn get_forecast(
        &self,
        latitude: f64,
        longitude: f64,
        days: u32,
        temperature_unit: &str,
        wind_speed_unit: &str,
        precipitation_unit: &str,
        model: &str,
    ) -> Result<Value, OpenMeteoError> {
        let mut params = vec![
            ("latitude", py::float_repr(latitude)),
            ("longitude", py::float_repr(longitude)),
        ];
        params.extend(list_param(
            "daily",
            &[
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
            ],
        ));
        params.extend(common_units(
            temperature_unit,
            wind_speed_unit,
            precipitation_unit,
        ));
        params.push(("forecast_days", days.min(16).to_string()));
        self.make_request("forecast", &with_model(params, model), false)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn get_hourly_forecast(
        &self,
        latitude: f64,
        longitude: f64,
        hours: u32,
        temperature_unit: &str,
        wind_speed_unit: &str,
        precipitation_unit: &str,
        model: &str,
    ) -> Result<Value, OpenMeteoError> {
        let mut params = vec![
            ("latitude", py::float_repr(latitude)),
            ("longitude", py::float_repr(longitude)),
        ];
        params.extend(list_param(
            "hourly",
            &[
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
            ],
        ));
        params.extend(common_units(
            temperature_unit,
            wind_speed_unit,
            precipitation_unit,
        ));
        params.push(("forecast_hours", hours.min(384).to_string()));
        self.make_request("forecast", &with_model(params, model), false)
    }

    /// Weather description for a code, "Unknown weather code: X" otherwise.
    pub fn get_weather_description(weather_code: &Value) -> String {
        let code = (!weather_code.is_null()).then_some(weather_code);
        match aw_core::weather_client_parsers::weather_code_to_description(code) {
            None => format!("Unknown weather code: {}", py::value_str(weather_code)),
            Some(d) => match d.strip_prefix("Weather code ") {
                Some(suffix) => format!("Unknown weather code: {suffix}"),
                None => d,
            },
        }
    }
}

fn location_params(location: &Location) -> Vec<(&'static str, String)> {
    vec![
        ("latitude", py::float_repr(location.latitude)),
        ("longitude", py::float_repr(location.longitude)),
    ]
}

fn us_units() -> [(&'static str, String); 4] {
    common_units("fahrenheit", "mph", "inch")
}

/// Python swallows non-retryable failures (→ `None`) and re-raises
/// retryable ones after its retry decorator gives up.
fn fetch<T>(
    http: &dyn HttpClient,
    url: &str,
    what: &str,
    parse: impl FnOnce(&Value) -> T,
) -> Result<Option<T>, HttpError> {
    match http.get_json(url) {
        Ok(data) => Ok(Some(parse(&data))),
        Err(e) => {
            tracing::error!("Failed to get OpenMeteo {what}: {e}");
            if e.is_retryable() {
                Err(e)
            } else {
                Ok(None)
            }
        }
    }
}

/// URL for [`get_openmeteo_current_conditions`].
pub fn current_conditions_url(location: &Location, base_url: &str, model: &str) -> String {
    let mut params = location_params(location);
    params.push((
        "current",
        "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,\
         wind_direction_10m,pressure_msl,precipitation,rain,showers,snowfall,snow_depth,\
         visibility,uv_index"
            .into(),
    ));
    params.push(("daily", "sunrise,sunset,uv_index_max".into()));
    params.extend(us_units());
    params.push(("forecast_days", "1".into()));
    build_url(&format!("{base_url}/forecast"), &with_model(params, model))
}

/// URL for [`get_openmeteo_forecast`].
pub fn forecast_url(location: &Location, base_url: &str, days: i64, model: &str) -> String {
    let mut params = location_params(location);
    params.push((
        "daily",
        "temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,\
         wind_direction_10m_dominant,precipitation_probability_max,snowfall_sum,uv_index_max"
            .into(),
    ));
    params.extend(us_units());
    params.push(("forecast_days", days.clamp(1, 16).to_string()));
    build_url(&format!("{base_url}/forecast"), &with_model(params, model))
}

/// URL for [`get_openmeteo_hourly_forecast`].
pub fn hourly_forecast_url(location: &Location, base_url: &str, hours: i64, model: &str) -> String {
    let mut params = location_params(location);
    params.push((
        "hourly",
        "temperature_2m,relative_humidity_2m,dew_point_2m,weather_code,wind_speed_10m,\
         wind_direction_10m,pressure_msl,precipitation_probability,snowfall,uv_index,snow_depth,\
         freezing_level_height,visibility,apparent_temperature"
            .into(),
    ));
    params.extend(us_units());
    params.push(("forecast_hours", hours.clamp(1, 384).to_string()));
    build_url(&format!("{base_url}/forecast"), &with_model(params, model))
}

/// Current conditions in US units (`get_openmeteo_current_conditions`).
pub fn get_openmeteo_current_conditions(
    http: &dyn HttpClient,
    location: &Location,
    base_url: &str,
    model: &str,
) -> Result<Option<CurrentConditions>, HttpError> {
    let url = current_conditions_url(location, base_url, model);
    fetch(
        http,
        &url,
        "current conditions",
        parse_openmeteo_current_conditions,
    )
}

/// Daily forecast (`get_openmeteo_forecast`), clamped to 1-16 days.
pub fn get_openmeteo_forecast(
    http: &dyn HttpClient,
    location: &Location,
    base_url: &str,
    days: i64,
    model: &str,
) -> Result<Option<Forecast>, HttpError> {
    let url = forecast_url(location, base_url, days, model);
    fetch(http, &url, "forecast", |d| {
        parse_openmeteo_forecast(d, Local::now().fixed_offset())
    })
}

/// Hourly forecast (`get_openmeteo_hourly_forecast`), clamped to 1-384 hours.
pub fn get_openmeteo_hourly_forecast(
    http: &dyn HttpClient,
    location: &Location,
    base_url: &str,
    hours: i64,
    model: &str,
) -> Result<Option<HourlyForecast>, HttpError> {
    let url = hourly_forecast_url(location, base_url, hours, model);
    fetch(http, &url, "hourly forecast", |d| {
        parse_openmeteo_hourly_forecast(d, Local::now().fixed_offset())
    })
}

pub type OpenMeteoBundle = (
    Option<CurrentConditions>,
    Option<Forecast>,
    Option<HourlyForecast>,
);

/// All three sections fetched in parallel (`get_openmeteo_all_data_parallel`).
pub fn get_openmeteo_all_data_parallel(
    http: &dyn HttpClient,
    location: &Location,
    base_url: &str,
    forecast_days: i64,
    model: &str,
    hourly_hours: i64,
) -> Result<OpenMeteoBundle, HttpError> {
    std::thread::scope(|s| {
        let current = s.spawn(|| get_openmeteo_current_conditions(http, location, base_url, model));
        let forecast =
            s.spawn(|| get_openmeteo_forecast(http, location, base_url, forecast_days, model));
        let hourly = s
            .spawn(|| get_openmeteo_hourly_forecast(http, location, base_url, hourly_hours, model));
        let current = current.join().expect("Open-Meteo current thread")?;
        let forecast = forecast.join().expect("Open-Meteo forecast thread")?;
        let hourly = hourly.join().expect("Open-Meteo hourly thread")?;
        Ok((current, forecast, hourly))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use serde_json::json;

    fn nyc() -> Location {
        Location::new("New York", 40.7128, -74.006)
    }

    #[test]
    fn weather_descriptions() {
        assert_eq!(
            OpenMeteoApiClient::get_weather_description(&json!(0)),
            "Clear sky"
        );
        assert_eq!(
            OpenMeteoApiClient::get_weather_description(&json!(999)),
            "Unknown weather code: 999"
        );
        assert_eq!(
            OpenMeteoApiClient::get_weather_description(&json!(null)),
            "Unknown weather code: None"
        );
    }

    #[test]
    fn fetch_urls_match_python_params() {
        assert_eq!(
            current_conditions_url(&nyc(), BASE_URL, "best_match"),
            "https://api.open-meteo.com/v1/forecast?latitude=40.7128&longitude=-74.006&current=temperature_2m%2Crelative_humidity_2m%2Capparent_temperature%2Cweather_code%2Cwind_speed_10m%2Cwind_direction_10m%2Cpressure_msl%2Cprecipitation%2Crain%2Cshowers%2Csnowfall%2Csnow_depth%2Cvisibility%2Cuv_index&daily=sunrise%2Csunset%2Cuv_index_max&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto&forecast_days=1"
        );
        assert!(forecast_url(&nyc(), BASE_URL, 30, "gfs_seamless")
            .ends_with("&forecast_days=16&models=gfs_seamless"));
        assert!(
            hourly_forecast_url(&nyc(), BASE_URL, 0, "best_match").ends_with("&forecast_hours=1")
        );
    }

    #[test]
    fn dict_client_repeats_list_params() {
        let http = FixtureClient::new().with(BASE_URL, json!({"ok": 1}));
        let client = OpenMeteoApiClient::new(&http);
        client
            .get_forecast(40.0, -74.0, 7, "fahrenheit", "mph", "inch", "icon_seamless")
            .unwrap();
        let url = &http.request_log()[0];
        assert!(url.starts_with("https://api.open-meteo.com/v1/forecast?latitude=40.0&longitude=-74.0&daily=weather_code&daily=temperature_2m_max"));
        assert!(url.ends_with("&forecast_days=7&models=icon_seamless"));
        let http = FixtureClient::new().with_status(BASE_URL, 429);
        let err = OpenMeteoApiClient::new(&http)
            .get_current_weather(1.0, 2.0, "celsius", "kmh", "mm", "best_match")
            .unwrap_err();
        assert_eq!(err.to_string(), "Rate limit exceeded");
    }

    #[test]
    fn non_retryable_failures_become_none() {
        let http = FixtureClient::new().with_status(BASE_URL, 404);
        assert!(
            get_openmeteo_forecast(&http, &nyc(), BASE_URL, 7, "best_match")
                .unwrap()
                .is_none()
        );
        let http = FixtureClient::new().with_status(BASE_URL, 503);
        assert!(get_openmeteo_forecast(&http, &nyc(), BASE_URL, 7, "best_match").is_err());
    }
}
