//! Client behaviour ported from tests/test_nws_afd_notification.py,
//! test_weather_client_nws_alerts_zone_reuse.py, test_zone_enrichment_drift.py,
//! test_weather_client_nws_text_product.py, test_nws_cancel_references.py and
//! test_nws_high_low.py. Payload-level parity lives in tests/nws_golden.rs.

use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::{json, Value};

use super::*;
use crate::http::FixtureClient;

const POINTS: &str = "https://api.weather.gov/points/40.0,-75.0";
const FORECAST: &str = "https://api.weather.gov/gridpoints/PHI/1,2/forecast";
const AFD_LIST: &str = "https://api.weather.gov/products/types/AFD/locations/PHI";
const ALERTS: &str = "https://api.weather.gov/alerts/active";

fn client(http: &FixtureClient) -> NwsClient<'_> {
    let mut c = NwsClient::new(http);
    c.retry_delay = Duration::ZERO;
    c.now = Some(chrono::DateTime::parse_from_rfc3339("2026-01-20T19:30:00+00:00").unwrap());
    c
}

fn location() -> Location {
    Location::new("Philadelphia, PA", 40.0, -75.0)
}

fn points() -> Value {
    json!({"properties": {
        "forecast": FORECAST,
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/1,2/forecast/hourly",
        "forecastGridData": "https://api.weather.gov/gridpoints/PHI/1,2",
        "observationStations": "https://api.weather.gov/gridpoints/PHI/1,2/stations",
        "timeZone": "America/New_York", "cwa": "PHI", "radarStation": "KDIX",
        "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
        "county": "https://api.weather.gov/zones/county/PAC101",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
    }})
}

fn afd(http: FixtureClient) -> FixtureClient {
    http.with(
        AFD_LIST,
        json!({"@graph": [{"id": "afd-1", "issuanceTime": "2026-01-20T19:01:00+00:00"}]}),
    )
    .with(
        "https://api.weather.gov/products/afd-1",
        json!({"productText": "AFD text", "issuanceTime": "2026-01-20T19:01:00+00:00"}),
    )
}

fn urls(http: &FixtureClient) -> Vec<String> {
    http.request_log()
}

#[test]
fn forecast_failure_still_returns_discussion() {
    let http = afd(FixtureClient::new()
        .with(POINTS, points())
        .with_response(FORECAST, 503, "busy"));
    let r = client(&http)
        .forecast_and_discussion(&location(), None)
        .unwrap();
    assert_eq!(r.forecast, None, "a 503 forecast is dropped, not retried");
    assert_eq!(r.discussion.as_deref(), Some("AFD text"));
    assert_eq!(
        r.discussion_issuance_time.unwrap().to_rfc3339(),
        "2026-01-20T19:01:00+00:00"
    );
    assert_eq!(
        urls(&http)
            .iter()
            .filter(|u| u.as_str() == FORECAST)
            .count(),
        1
    );
    let forecast_req = http
        .sent_requests()
        .into_iter()
        .find(|r| r.url == FORECAST)
        .unwrap();
    assert_eq!(
        forecast_req.headers[1],
        ("Feature-Flags".into(), FEATURE_FLAGS.into())
    );
}

#[test]
fn points_503_is_retried_then_raised() {
    let http = FixtureClient::new().with_response(POINTS, 503, "busy");
    let err = client(&http)
        .forecast_and_discussion(&location(), None)
        .unwrap_err();
    assert!(matches!(err, HttpError::Status { status: 503, .. }));
    assert_eq!(urls(&http).len(), 3);

    let http = FixtureClient::new().with_transport_error(POINTS, "simulated connection failure");
    assert!(client(&http).discussion_only(&location()).is_err());
    assert_eq!(urls(&http).len(), 3);
}

#[test]
fn non_retryable_failures_fall_back_without_retrying() {
    let http = FixtureClient::new().with_response(POINTS, 404, "");
    assert_eq!(
        client(&http).discussion_only(&location()).unwrap(),
        (None, None)
    );
    assert_eq!(
        client(&http).current_conditions(&mut location()).unwrap(),
        None
    );
    assert_eq!(
        client(&http).hourly_forecast(&location(), None).unwrap(),
        None
    );
    assert_eq!(urls(&http).len(), 3);
}

#[test]
fn discussion_only_never_requests_the_forecast() {
    let http = afd(FixtureClient::new().with(POINTS, points()));
    let (text, issued) = client(&http).discussion_only(&location()).unwrap();
    assert_eq!(text.as_deref(), Some("AFD text"));
    assert!(issued.is_some());
    assert!(!urls(&http).iter().any(|u| u.ends_with("/forecast")));
}

#[test]
fn discussion_fallback_sentences() {
    let http = FixtureClient::new().with(AFD_LIST, json!({"@graph": []}));
    let c = client(&http);
    assert_eq!(
        c.discussion(&json!({"properties": {}})),
        ("Forecast discussion not available.".into(), None)
    );
    assert_eq!(
        c.discussion(&json!({"properties": {"forecast": "https://x/short"}})),
        ("Forecast discussion not available.".into(), None)
    );
    assert_eq!(
        c.discussion(&points()),
        (
            "Forecast discussion not available for this location.".into(),
            None
        )
    );
    let http = FixtureClient::new().with_response(AFD_LIST, 200, "not json");
    assert_eq!(
        client(&http).discussion(&points()).0,
        "Forecast discussion not available due to error."
    );
}

#[test]
fn text_products_without_office_or_station_skip_http() {
    let http = FixtureClient::new();
    let c = client(&http);
    assert_eq!(c.text_product("AFD", None).unwrap(), None);
    assert_eq!(c.text_product("SPS", Some("")).unwrap(), None);
    assert_eq!(c.daily_climate_report(Some("  ")).unwrap(), None);
    assert!(c
        .text_product_history("AFD", None, 5, None, None)
        .unwrap()
        .is_empty());
    assert!(urls(&http).is_empty());
}

#[test]
fn text_product_transport_error_is_a_fetch_error() {
    let http = FixtureClient::new().with_transport_error(AFD_LIST, "simulated connection failure");
    assert!(matches!(
        client(&http).text_product("AFD", Some("PHI")),
        Err(TextProductError::Fetch(_))
    ));
    assert_eq!(urls(&http).len(), 1, "text products are not retried");
}

#[test]
fn daily_climate_report_drops_k_prefix() {
    let http = FixtureClient::new();
    let _ = client(&http).daily_climate_report(Some("KTTN"));
    assert_eq!(
        urls(&http),
        ["https://api.weather.gov/products?location=TTN&type=CLI&limit=1"]
    );
}

#[test]
fn climate_and_station_lookups_degrade_to_empty() {
    let http = FixtureClient::new()
        .with_response(
            "https://api.weather.gov/products/types/CLI/locations",
            500,
            "",
        )
        .with(
            "https://api.weather.gov/points/40.0000,-75.0000",
            json!({"properties": {}}),
        );
    let c = client(&http);
    assert!(c.daily_climate_locations().is_empty());
    assert!(c
        .observation_station_ids_for_point(40.0, -75.0, 12)
        .is_empty());
}

// tests/test_weather_client_nws_alerts_zone_reuse.py
#[test]
fn stored_county_zone_skips_points() {
    let http = FixtureClient::new().with(ALERTS, json!({"features": []}));
    let mut loc = location();
    loc.county_zone_id = Some("PAC101".into());
    client(&http).alerts(&loc, "county").unwrap();
    assert_eq!(urls(&http), [format!("{ALERTS}?zone=PAC101&status=actual")]);
}

#[test]
fn zone_radius_queries_county_and_forecast_zones_and_dedupes() {
    let alert = json!({"id": "urn:dup", "properties": {"event": "Severe Thunderstorm Watch"}});
    let http = FixtureClient::new()
        .with(
            &format!("{ALERTS}?zone=PAC101"),
            json!({"features": [alert]}),
        )
        .with(
            &format!("{ALERTS}?zone=PAZ106"),
            json!({"features": [alert]}),
        );
    let mut loc = location();
    loc.county_zone_id = Some("PAC101".into());
    loc.forecast_zone_id = Some("PAZ106".into());
    let alerts = client(&http).alerts(&loc, "zone").unwrap();
    assert_eq!(alerts.alerts.len(), 1);
    assert_eq!(urls(&http).len(), 2);

    // A failing zone is skipped, not retried, and the other zone still counts.
    let http = FixtureClient::new()
        .with_response(&format!("{ALERTS}?zone=PAC101"), 500, "")
        .with(
            &format!("{ALERTS}?zone=PAZ106"),
            json!({"features": [alert]}),
        );
    let alerts = client(&http).alerts(&loc, "zone").unwrap();
    assert_eq!(alerts.alerts[0].id.as_deref(), Some("urn:dup"));
    assert_eq!(urls(&http).len(), 2);
}

#[test]
fn alert_failures() {
    // 404 on the stored zone: not retryable, empty alerts.
    let http = FixtureClient::new().with_response(ALERTS, 404, "");
    let mut loc = location();
    loc.county_zone_id = Some("PAC101".into());
    assert!(client(&http)
        .alerts(&loc, "county")
        .unwrap()
        .alerts
        .is_empty());
    assert_eq!(urls(&http).len(), 1);
    // A dropped connection is retried and then surfaces.
    let http = FixtureClient::new().with_transport_error(ALERTS, "simulated connection failure");
    assert!(client(&http).alerts(&loc, "point").is_err());
    assert_eq!(urls(&http).len(), 3);
}

// tests/test_zone_enrichment_drift.py: once drift is persisted the next
// refresh needs one request fewer (alerts reuse the stored county zone).
#[test]
fn drift_correction_reports_changes_once_persisted() {
    let http = FixtureClient::new()
        .with(POINTS, points())
        .with(ALERTS, json!({"features": []}))
        .with(
            "https://api.weather.gov/gridpoints/PHI/1,2/stations",
            json!({"features": []}),
        )
        .with(FORECAST, json!({"properties": {"periods": []}}))
        .with(
            "https://api.weather.gov/gridpoints/PHI/1,2/forecast/hourly",
            json!({"properties": {"periods": []}}),
        )
        .with(
            "https://api.weather.gov/gridpoints/PHI/1,2",
            json!({"properties": {}}),
        )
        .with(AFD_LIST, json!({"@graph": []}));
    let persisted: Arc<Mutex<Vec<(String, ZoneFields)>>> = Arc::default();
    let log = persisted.clone();
    let mut c = client(&http);
    c.zone_drift_sink = Some(Arc::new(move |name: &str, fields: &ZoneFields| {
        log.lock().unwrap().push((name.to_string(), fields.clone()));
    }));

    let mut loc = location();
    let data = c.all_data_parallel(&mut loc, "county").unwrap();
    assert_eq!(data.alerts, Some(WeatherAlerts::default()));
    assert_eq!(loc.timezone.as_deref(), Some("America/New_York"));
    let first = http.request_log().len();
    let (name, fields) = persisted.lock().unwrap()[0].clone();
    assert_eq!(name, "Philadelphia, PA");
    assert_eq!(fields.county_zone_id.as_deref(), Some("PAC101"));

    fields.apply_to(&mut loc);
    c.all_data_parallel(&mut loc, "county").unwrap();
    assert_eq!(http.request_log().len() - first, first - 1);
    assert_eq!(persisted.lock().unwrap().len(), 1, "no drift, no persist");
}

#[test]
fn parallel_fetch_falls_back_to_nothing_on_bad_points() {
    let http = FixtureClient::new().with_response(POINTS, 404, "");
    let called = Arc::new(Mutex::new(false));
    let flag = called.clone();
    let mut c = client(&http);
    c.zone_drift_sink = Some(Arc::new(move |_: &str, _: &ZoneFields| {
        *flag.lock().unwrap() = true
    }));
    let data = c.all_data_parallel(&mut location(), "county").unwrap();
    assert_eq!(data, NwsData::default());
    assert!(!*called.lock().unwrap());
}

#[test]
fn current_conditions_updates_timezone_even_without_stations() {
    let http = FixtureClient::new().with(POINTS, points()).with(
        "https://api.weather.gov/gridpoints/PHI/1,2/stations",
        json!({"features": []}),
    );
    let mut loc = location();
    assert_eq!(client(&http).current_conditions(&mut loc).unwrap(), None);
    assert_eq!(loc.timezone.as_deref(), Some("America/New_York"));
}

// tests/test_nws_cancel_references.py
#[test]
fn cancel_references_query_and_failure() {
    let http = FixtureClient::new().with(
        "https://api.weather.gov/alerts",
        json!({"features": [{"properties": {"references": [{"identifier": "NWS-IDP-1"}, {"@id": "NWS-IDP-2"}]}}]}),
    );
    let ids = client(&http).cancel_references(15);
    assert_eq!(
        ids.into_iter().collect::<Vec<_>>(),
        ["NWS-IDP-1", "NWS-IDP-2"]
    );
    assert_eq!(
        urls(&http),
        ["https://api.weather.gov/alerts?message_type=cancel&start=2026-01-20T19%3A15%3A00Z&end=2026-01-20T19%3A30%3A00Z"]
    );
    let http = FixtureClient::new().with_transport_error(
        "https://api.weather.gov/alerts",
        "simulated connection failure",
    );
    assert!(client(&http).cancel_references(15).is_empty());
    assert_eq!(urls(&http).len(), 1, "cancel lookups are not retried");
}

// tests/test_nws_high_low.py
#[test]
fn gridpoint_pressure_errors() {
    let hourly_url = "https://api.weather.gov/gridpoints/PHI/1,2/forecast/hourly";
    let grid_url = "https://api.weather.gov/gridpoints/PHI/1,2";
    let http = FixtureClient::new()
        .with(POINTS, points())
        .with(
            hourly_url,
            json!({"properties": {"periods": [{"startTime": "2026-01-20T13:00:00-05:00", "temperature": 30}]}}),
        )
        .with_response(grid_url, 404, "");
    let hourly = client(&http)
        .hourly_forecast(&location(), None)
        .unwrap()
        .unwrap();
    assert_eq!(
        hourly.periods[0].pressure_mb, None,
        "a 404 pressure layer is ignored"
    );

    let http = FixtureClient::new()
        .with(POINTS, points())
        .with(hourly_url, json!({"properties": {"periods": []}}))
        .with_response(grid_url, 503, "");
    assert!(client(&http).hourly_forecast(&location(), None).is_err());
    assert_eq!(
        urls(&http).len(),
        9,
        "a retryable pressure failure retries the hourly fetch"
    );
}

#[test]
fn international_station_without_avwx_key_uses_nws_path() {
    let http = FixtureClient::new().with(
        "https://api.weather.gov/stations/EGLL/tafs",
        json!({"features": [{"properties": {"rawMessage": "TAF EGLL 201700Z 2018/2124 24010KT 9999 SCT030"}}]}),
    );
    let a = client(&http)
        .aviation_weather("egll", &AviationOptions::default(), "")
        .unwrap();
    assert_eq!(
        a.raw_taf.as_deref(),
        Some("TAF EGLL 201700Z 2018/2124 24010KT 9999 SCT030")
    );
    assert!(!urls(&http).iter().any(|u| u.starts_with(AVWX_BASE_URL)));
    assert!(matches!(
        client(&http).aviation_weather(" ", &AviationOptions::default(), ""),
        Err(AviationError::EmptyStation)
    ));
}
