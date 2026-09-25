//! Live checks against the real NWS, Open-Meteo and IEM services: the Rust
//! side of the Python `tests/integration` suite, catching API changes the
//! recorded fixtures can't. Ignored by default; `rust-integration.yml` runs
//! them on a schedule:
//!
//!     cargo test -p aw-providers --test live -- --ignored

use aw_core::model::Location;
use aw_providers::nws::NwsClient;
use aw_providers::openmeteo::{get_openmeteo_all_data_parallel, BASE_URL};
use aw_providers::products::iem::{AfosQuery, Iem, DEFAULT_IEM_BASE_URL};
use aw_providers::ReqwestClient;

fn place(name: &str, latitude: f64, longitude: f64, country: &str) -> Location {
    let mut location = Location::new(name, latitude, longitude);
    location.country_code = Some(country.into());
    location
}

fn nws_data_for(mut location: Location) {
    let http = ReqwestClient::new().unwrap();
    let data = NwsClient::new(&http)
        .all_data_parallel(&mut location, "county")
        .unwrap();
    assert!(location.timezone.is_some(), "points gave no time zone");
    assert!(data.current.is_some(), "no current conditions");
    let forecast = data.forecast.expect("no forecast");
    assert!(!forecast.periods.is_empty(), "empty forecast");
    let hourly = data.hourly_forecast.expect("no hourly forecast");
    assert!(!hourly.periods.is_empty(), "empty hourly forecast");
    assert!(data.alerts.is_some(), "no alerts response");
    assert!(
        data.discussion.is_some_and(|d| !d.trim().is_empty()),
        "no forecast discussion"
    );
}

#[test]
#[ignore = "live network"]
fn nws_serves_new_york() {
    nws_data_for(place("New York, NY", 40.7128, -74.006, "US"));
}

#[test]
#[ignore = "live network"]
fn nws_serves_anchorage() {
    nws_data_for(place("Anchorage, AK", 61.2181, -149.9003, "US"));
}

#[test]
#[ignore = "live network"]
fn open_meteo_serves_london() {
    let http = ReqwestClient::new().unwrap();
    let london = place("London, UK", 51.5074, -0.1278, "GB");
    let now = chrono::Utc::now().fixed_offset();
    let (current, forecast, hourly) =
        get_openmeteo_all_data_parallel(&http, &london, BASE_URL, 7, "best_match", 48, now)
            .unwrap();
    let current = current.expect("no current conditions");
    assert!(current.temperature.is_some(), "no temperature");
    assert!(!forecast.expect("no forecast").periods.is_empty());
    assert!(!hourly.expect("no hourly forecast").periods.is_empty());
}

#[test]
#[ignore = "live network"]
fn iem_serves_the_latest_area_forecast_discussion() {
    let http = ReqwestClient::new().unwrap();
    let iem = Iem {
        http: &http,
        base: DEFAULT_IEM_BASE_URL,
    };
    let product = iem.afos_text("AFDOKX", &AfosQuery::default()).unwrap();
    assert!(
        product.product_text.contains("Area Forecast Discussion"),
        "unexpected AFDOKX text: {}",
        &product.product_text[..product.product_text.len().min(200)]
    );
}
