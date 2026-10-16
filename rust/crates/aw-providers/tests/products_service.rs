//! Behaviour tests for the text-product services, ported from
//! `test_forecast_product_service.py`, `test_daily_climate_reports.py`,
//! `test_main_window_product_prewarm.py`, `test_national_discussion_service.py`
//! and the Forecaster Notes availability tests.

use std::sync::{Arc, Mutex};

use aw_core::model::{Location, TextProduct};
use aw_providers::http::FixtureClient;
use aw_providers::products::iem::{AfosQuery, DEFAULT_IEM_BASE_URL};
use aw_providers::products::national::{is_hurricane_season, text_for, NationalDiscussionService};
use aw_providers::products::tabs::{self, FORECASTER_TABS};
use aw_providers::products::{ForecastProductService, ProductResult};
use chrono::{DateTime, Duration, TimeZone, Utc};
use serde_json::{json, Value};

const NWS: &str = "https://api.weather.gov";
const MARINE: &str = "https://marine-api.open-meteo.com/v1/marine";

fn start() -> DateTime<Utc> {
    Utc.with_ymd_and_hms(2026, 5, 1, 18, 0, 0).unwrap()
}

/// A service over `http` with a clock the test can advance.
fn clocked(http: Arc<FixtureClient>) -> (ForecastProductService, Arc<Mutex<DateTime<Utc>>>) {
    let now = Arc::new(Mutex::new(start()));
    let clock = now.clone();
    let service = ForecastProductService::new(http).with_clock(move || *clock.lock().unwrap());
    (service, now)
}

fn count(http: &FixtureClient, prefix: &str) -> usize {
    http.request_log()
        .iter()
        .filter(|u| u.starts_with(prefix))
        .count()
}

fn listing(ids: &[&str]) -> Value {
    json!({"@graph": ids.iter().map(|id| json!({"id": id})).collect::<Vec<_>>()})
}

fn body(text: &str) -> Value {
    json!({"productText": text, "issuanceTime": "2026-04-16T14:32:00+00:00"})
}

fn office_products(http: FixtureClient, product_type: &str, office: &str) -> FixtureClient {
    let id = format!("{}-{office}", product_type.to_lowercase());
    http.with(
        &format!("{NWS}/products/types/{product_type}/locations/{office}"),
        listing(&[&id]),
    )
    .with(
        &format!("{NWS}/products/{id}"),
        body(&format!("{product_type} {office} TEXT")),
    )
}

fn raleigh() -> Location {
    let mut loc = Location::new("Raleigh", 35.78, -78.64).with_country("US");
    loc.cwa_office = Some("RAH".into());
    loc
}

#[test]
fn repeat_calls_within_ttl_hit_cache() {
    let http = Arc::new(office_products(FixtureClient::new(), "AFD", "PHI"));
    let (service, _) = clocked(http.clone());
    let first = service.get("AFD", "PHI").unwrap();
    let second = service.get("AFD", "PHI").unwrap();
    assert_eq!(first, second);
    assert_eq!(count(&http, &format!("{NWS}/products/types/AFD")), 1);
}

#[test]
fn per_type_ttl_keeps_afd_but_refetches_sps() {
    let http = FixtureClient::new();
    let http = Arc::new(office_products(
        office_products(http, "AFD", "PHI"),
        "SPS",
        "PHI",
    ));
    let (service, now) = clocked(http.clone());
    service.get("AFD", "PHI").unwrap();
    service.get("SPS", "PHI").unwrap();
    *now.lock().unwrap() += Duration::seconds(1000);
    service.get("AFD", "PHI").unwrap();
    service.get("SPS", "PHI").unwrap();
    assert_eq!(count(&http, &format!("{NWS}/products/types/AFD")), 1);
    assert_eq!(count(&http, &format!("{NWS}/products/types/SPS")), 2);
}

#[test]
fn offices_and_product_types_do_not_collide() {
    let mut http = FixtureClient::new();
    for (product_type, office) in [
        ("AFD", "PHI"),
        ("AFD", "OKX"),
        ("HWO", "PHI"),
        ("SRF", "PHI"),
    ] {
        http = office_products(http, product_type, office);
    }
    let http = Arc::new(http.with(
        &format!("{NWS}/products/types/SPS/locations/PHI"),
        json!({"@graph": []}),
    ));
    let (service, _) = clocked(http.clone());
    let phi = service.get("AFD", "PHI").unwrap();
    let okx = service.get("AFD", "OKX").unwrap();
    assert_eq!(phi.first().unwrap().cwa_office, "PHI");
    assert_eq!(okx.first().unwrap().cwa_office, "OKX");
    assert_eq!(
        service
            .get("HWO", "PHI")
            .unwrap()
            .first()
            .unwrap()
            .product_type,
        "HWO"
    );
    assert_eq!(
        service
            .get("SRF", "PHI")
            .unwrap()
            .first()
            .unwrap()
            .product_type,
        "SRF"
    );
    // Empty SPS is an empty list, cached like any other result.
    assert_eq!(
        service.get("SPS", "PHI").unwrap(),
        ProductResult::Many(vec![])
    );
    assert_eq!(
        service.get("SPS", "PHI").unwrap(),
        ProductResult::Many(vec![])
    );
    assert_eq!(count(&http, &format!("{NWS}/products/types/SPS")), 1);
    assert_eq!(
        service.peek("SPS", "PHI"),
        Some(ProductResult::Many(vec![]))
    );
    assert_eq!(service.peek("HWO", "OKX"), None);
}

#[test]
fn fetch_errors_propagate_and_are_not_cached() {
    let http = Arc::new(FixtureClient::new());
    let (service, _) = clocked(http.clone());
    assert!(service.get("AFD", "PHI").is_err());
    assert!(service.get("AFD", "PHI").is_err());
    assert_eq!(count(&http, &format!("{NWS}/products/types/AFD")), 2);
}

#[test]
fn history_uses_its_own_cache_namespace() {
    let http = Arc::new(
        office_products(FixtureClient::new(), "AFD", "PHI")
            .with(&format!("{NWS}/products?"), listing(&["old"]))
            .with(&format!("{NWS}/products/old"), body("OLD")),
    );
    let (service, _) = clocked(http.clone());
    let current = service.get("AFD", "PHI").unwrap();
    let history = service.get_history("AFD", "PHI", 10, None, None).unwrap();
    assert_eq!(current.first().unwrap().product_id, "afd-PHI");
    assert_eq!(history[0].product_id, "old");
    assert_eq!(
        service.get_history("AFD", "PHI", 10, None, None).unwrap(),
        history
    );
    assert_eq!(
        http.request_log()
            .iter()
            .filter(|u| u.starts_with(&format!("{NWS}/products?")))
            .collect::<Vec<_>>(),
        vec![&format!("{NWS}/products?location=PHI&type=AFD&limit=10")]
    );
}

fn surf_location(cwa: Option<&str>) -> Location {
    let mut loc = Location::new("Lumberton", 39.96, -74.8);
    loc.cwa_office = cwa.map(str::to_string);
    loc
}

fn marine_ok() -> Value {
    json!({"current": {"time": "2026-06-07T12:00:00Z", "wave_height": 1.2}, "current_units": {"wave_height": "m"}})
}

#[test]
fn official_srf_is_preferred_over_derived_conditions() {
    let http =
        Arc::new(office_products(FixtureClient::new(), "SRF", "PHI").with(MARINE, marine_ok()));
    let (service, _) = clocked(http.clone());
    let pirate_called = Mutex::new(false);
    let pirate = |_: &Location| {
        *pirate_called.lock().unwrap() = true;
        None
    };
    let result = service
        .get_surf_conditions_for_location(&surf_location(Some(" phi ")), Some(&pirate))
        .unwrap();
    assert_eq!(result.product_type, "SRF");
    assert_eq!(count(&http, MARINE), 0);
    assert!(!*pirate_called.lock().unwrap());
}

#[test]
fn derived_conditions_fall_back_open_meteo_then_pirate() {
    // No office: straight to Open-Meteo Marine.
    let http = Arc::new(FixtureClient::new().with(MARINE, marine_ok()));
    let (svc, _) = clocked(http.clone());
    let porto = surf_location(Some(""));
    let result = svc.get_surf_conditions_for_location(&porto, None).unwrap();
    assert_eq!(result.product_type, "SURF_CONDITIONS");
    assert!(result
        .product_text
        .contains("not an official NWS Surf Zone Forecast"));
    assert_eq!(count(&http, &format!("{NWS}/products")), 0);

    // SRF fetch error and no marine data: Pirate Weather context.
    let http = Arc::new(FixtureClient::new().with(MARINE, json!({"current": {}})));
    let (svc, _) = clocked(http.clone());
    let pirate = |_: &Location| Some(json!({"currently": {"summary": "Clear", "windSpeed": 8}}));
    let result = svc
        .get_surf_conditions_for_location(&surf_location(Some("PHI")), Some(&pirate))
        .unwrap();
    assert_eq!(result.cwa_office, "Pirate Weather");
    assert!(result.product_text.contains("Wind speed: 8 mph."));
    assert_eq!(count(&http, &format!("{NWS}/products/types/SRF")), 1);
}

#[test]
fn missing_surf_conditions_are_cached_as_none() {
    let http = Arc::new(FixtureClient::new());
    let (service, _) = clocked(http.clone());
    let nowhere = surf_location(None);
    assert!(service
        .get_surf_conditions_for_location(&nowhere, None)
        .is_none());
    assert!(service
        .get_surf_conditions_for_location(&nowhere, None)
        .is_none());
    assert_eq!(count(&http, MARINE), 1);
}

fn cli_product(station: &str) -> (String, Value) {
    (
        format!("{NWS}/products?location={station}&type=CLI&limit=1"),
        listing(&[&format!("cli-{station}")]),
    )
}

fn lumberton() -> Location {
    let mut loc = Location::new("Lumberton, NJ", 39.965, -74.805).with_country("US");
    loc.cwa_office = Some("PHI".into());
    loc.radar_station = Some("KDIX".into());
    loc
}

fn stations_fixture(http: FixtureClient, stations: &[&str]) -> FixtureClient {
    let stations_url = format!("{NWS}/gridpoints/PHI/1,1/stations");
    http.with(
        &format!("{NWS}/points/"),
        json!({"properties": {"observationStations": stations_url}}),
    )
    .with(
        &stations_url,
        json!({"observationStations": stations.iter().map(|s| format!("{NWS}/stations/{s}")).collect::<Vec<_>>()}),
    )
}

#[test]
fn daily_climate_report_is_cached_by_station() {
    let (url, list) = cli_product("RDU");
    let http = Arc::new(
        FixtureClient::new()
            .with(&url, list)
            .with(&format!("{NWS}/products/cli-RDU"), body("CLIMATE REPORT")),
    );
    let (service, _) = clocked(http.clone());
    let first = service.get_daily_climate_report("KRDU").unwrap();
    let second = service.get_daily_climate_report("krdu").unwrap();
    assert_eq!(first, second);
    assert_eq!(first.unwrap().cwa_office, "RDU");
    assert_eq!(count(&http, &url), 1);
    assert_eq!(
        service.peek_daily_climate_report("RDU").unwrap().cwa_office,
        "RDU"
    );
}

#[test]
fn daily_climate_for_location_falls_back_to_observation_stations() {
    let mut http = stations_fixture(FixtureClient::new(), &["KVAY", "KTTN", "KPHL"])
        .with(
            &format!("{NWS}/products/types/CLI/locations"),
            json!({"locations": {}}),
        )
        .with(
            &format!("{NWS}/products/cli-TTN"),
            body("CLIMATE REPORT FOR TRENTON"),
        );
    for station in ["DIX", "PHI", "VAY"] {
        http = http.with(&cli_product(station).0, json!({"@graph": []}));
    }
    let (ttn_url, ttn_list) = cli_product("TTN");
    let http = Arc::new(http.with(&ttn_url, ttn_list));
    let (service, _) = clocked(http.clone());

    let result = service
        .get_daily_climate_report_for_location(&lumberton())
        .unwrap()
        .unwrap();
    assert_eq!(result.product_id, "cli-TTN");
    let cli_requests: Vec<String> = http
        .request_log()
        .into_iter()
        .filter(|u| u.contains("type=CLI"))
        .collect();
    assert_eq!(
        cli_requests,
        ["DIX", "PHI", "VAY", "TTN"]
            .map(|s| cli_product(s).0)
            .to_vec()
    );
    assert!(http
        .request_log()
        .contains(&format!("{NWS}/points/39.9650,-74.8050")));
    // Stored under the location's primary candidates too.
    assert_eq!(service.peek_daily_climate_report("DIX"), Some(result));
}

#[test]
fn daily_climate_uses_cli_index_and_caches_resolved_station() {
    let (ttn_url, ttn_list) = cli_product("TTN");
    let http = Arc::new(
        stations_fixture(
            FixtureClient::new(),
            &["KVAY", "KWRI", "KPNE", "KTTN", "KPHL"],
        )
        .with(
            &format!("{NWS}/products/types/CLI/locations"),
            json!({"locations": {"TTN": null, "PHL": null, "ACY": null}}),
        )
        .with(&ttn_url, ttn_list)
        .with(&format!("{NWS}/products/cli-TTN"), body("TRENTON")),
    );
    let (service, _) = clocked(http.clone());
    let first = service
        .get_daily_climate_report_for_location(&lumberton())
        .unwrap();
    let second = service
        .get_daily_climate_report_for_location(&lumberton())
        .unwrap();
    assert_eq!(first, second);
    assert_eq!(first.unwrap().product_id, "cli-TTN");
    assert_eq!(count(&http, &ttn_url), 1);
    assert_eq!(count(&http, &format!("{NWS}/products?")), 1);
    assert_eq!(count(&http, &format!("{NWS}/points/")), 1);
    assert_eq!(
        count(&http, &format!("{NWS}/products/types/CLI/locations")),
        1
    );
}

#[test]
fn climate_station_candidates_prefer_radar_then_office() {
    let mut loc = raleigh();
    loc.radar_station = Some("KRDU".into());
    assert_eq!(
        ForecastProductService::daily_climate_station_candidates(&loc),
        vec!["RDU", "RAH"]
    );
    loc.radar_station = Some("krah".into());
    assert_eq!(
        ForecastProductService::daily_climate_station_candidates(&loc),
        vec!["RAH"]
    );
}

#[test]
fn iem_lookups_are_cached_per_filter_set() {
    let afos = format!("{DEFAULT_IEM_BASE_URL}/cgi-bin/afos/retrieve.py");
    let http = Arc::new(FixtureClient::new().with(&afos, json!("AFD TEXT")));
    let (service, _) = clocked(http.clone());
    let plain = AfosQuery::default();
    let filtered = AfosQuery {
        center: Some("KRAH".into()),
        wmo_id: Some("FXUS62".into()),
        aviation_afd: true,
        ..AfosQuery::default()
    };
    let first = service.get_iem_afos("afdrah", &plain).unwrap();
    assert_eq!(service.get_iem_afos("AFDRAH", &plain).unwrap(), first);
    assert_eq!(
        service
            .get_iem_afos("AFDRAH", &filtered)
            .unwrap()
            .cwa_office,
        "KRAH"
    );
    let log = http.request_log();
    assert_eq!(log.len(), 2);
    assert!(log[1].ends_with("&center=KRAH&ttaaii=FXUS62&aviation_afd=1"));

    let mcd = format!("{DEFAULT_IEM_BASE_URL}/json/spcmcd.py");
    let http = Arc::new(FixtureClient::new().with(&mcd, json!({"mcds": []})));
    let (service, _) = clocked(http.clone());
    service
        .get_iem_spc_mcds(35.78, -78.64, true, None, None, Some(3))
        .unwrap();
    service
        .get_iem_spc_mcds(35.78, -78.64, true, None, None, Some(3))
        .unwrap();
    assert_eq!(count(&http, &mcd), 1);
}

#[test]
fn spc_outlook_errors_do_not_fall_back_to_afos() {
    let http = Arc::new(FixtureClient::new());
    let (service, _) = clocked(http.clone());
    assert!(service
        .get_iem_spc_outlook(35.78, -78.64, 1, true, None, Some(3))
        .is_err());
    assert_eq!(http.request_log().len(), 1);
    assert!(!http.request_log()[0].contains("afos"));
}

#[test]
fn pre_warm_covers_text_products_and_climate_for_us_offices_only() {
    let mut http = stations_fixture(FixtureClient::new(), &[])
        .with(
            &format!("{NWS}/products/types/CLI/locations"),
            json!({"locations": {}}),
        )
        .with(&format!("{NWS}/products?"), json!({"@graph": []}));
    for product_type in ["AFD", "SPS", "SRF"] {
        http = office_products(http, product_type, "RAH");
    }
    // HWO has no fixture: its failure must not stop the others.
    let http = Arc::new(http);
    let (service, _) = clocked(http.clone());
    service.pre_warm_location(&raleigh());
    for product_type in ["AFD", "HWO", "SPS", "SRF"] {
        assert_eq!(
            count(
                &http,
                &format!("{NWS}/products/types/{product_type}/locations/RAH")
            ),
            1,
            "{product_type}"
        );
    }
    assert!(service.peek("AFD", "RAH").is_some());
    assert!(service.peek("HWO", "RAH").is_none());
    assert_eq!(
        count(&http, &format!("{NWS}/products?location=RAH&type=CLI")),
        1
    );

    let http = Arc::new(FixtureClient::new());
    let (service, _) = clocked(http.clone());
    let mut porto = Location::new("Porto", 41.15, -8.63).with_country("PT");
    porto.cwa_office = Some("XXX".into());
    service.pre_warm_location(&porto);
    let mut no_office = raleigh();
    no_office.cwa_office = None;
    service.pre_warm_location(&no_office);
    assert!(http.request_log().is_empty());
}

#[test]
fn forecaster_tab_availability_rules() {
    assert!(!tabs::keeps_tab("HWO", false, 3));
    assert!(tabs::keeps_tab("AFD", false, 3));
    assert!(tabs::keeps_tab("SPS", true, 3));
    assert!(tabs::keeps_tab("SURF", false, 1));
    let cli = FORECASTER_TABS
        .iter()
        .find(|t| t.product_type == "CLI")
        .unwrap();
    let hwo = FORECASTER_TABS
        .iter()
        .find(|t| t.product_type == "HWO")
        .unwrap();
    assert!(tabs::should_autoload_tab(hwo, true));
    assert!(tabs::should_autoload_tab(cli, false));
    assert!(!tabs::should_autoload_tab(hwo, false));
}

#[test]
fn surf_intro_is_prepended_once() {
    let product = |product_type: &str, text: &str| TextProduct {
        product_type: product_type.into(),
        product_id: "p".into(),
        cwa_office: "PHI".into(),
        issuance_time: None,
        product_text: text.into(),
        headline: None,
    };
    assert_eq!(
        tabs::display_text(&product("SRF", "SURF ZONE FORECAST"), Some("phi")),
        "Surf Zone Forecast issued by NWS PHI for regional beaches.\n\nSURF ZONE FORECAST"
    );
    let already = "Surf Zone Forecast issued by NWS PHI for regional beaches.\nbody";
    assert_eq!(
        tabs::display_text(&product("SRF", already), Some("PHI")),
        already
    );
    assert_eq!(
        tabs::display_text(&product("AFD", "AFD"), Some("PHI")),
        "AFD"
    );
}

#[test]
fn sps_choice_entries_use_local_time_and_headline_fallbacks() {
    let issued = Utc
        .with_ymd_and_hms(2026, 4, 16, 14, 32, 0)
        .unwrap()
        .fixed_offset();
    let local = issued
        .with_timezone(&chrono::Local)
        .format("%Y-%m-%d %H:%M")
        .to_string();
    let mut sps = TextProduct {
        product_type: "SPS".into(),
        product_id: "s".into(),
        cwa_office: "PHI".into(),
        issuance_time: Some(issued),
        product_text: "\n  First line\nSecond".into(),
        headline: Some("Dense fog".into()),
    };
    assert_eq!(
        tabs::format_sps_choice_entry(&sps),
        format!("Issued {local} \u{2014} Dense fog")
    );
    sps.headline = Some(String::new());
    sps.issuance_time = None;
    assert_eq!(
        tabs::format_sps_choice_entry(&sps),
        "Issued unknown \u{2014} First line"
    );
    sps.product_text = " \n ".into();
    assert_eq!(
        tabs::format_sps_choice_entry(&sps),
        "Issued unknown \u{2014} Special Weather Statement"
    );
}

#[test]
fn national_discussions_cache_force_refresh_and_season() {
    let afos = format!("{DEFAULT_IEM_BASE_URL}/cgi-bin/afos/retrieve.py");
    let http = Arc::new(FixtureClient::new().with(&afos, json!("TEXT")));
    let mut service = NationalDiscussionService::new(http.clone());
    service.request_delay = std::time::Duration::ZERO;
    let june = Utc.with_ymd_and_hms(2026, 6, 1, 0, 0, 0).unwrap();

    let first = service.fetch_all_discussions_at(false, june);
    assert_eq!(text_for(&first.nhc, "atlantic_outlook"), Some("TEXT"));
    assert_eq!(text_for(&first.wpc, "short_range"), Some("TEXT"));
    assert_eq!(http.request_log().len(), 10);
    assert_eq!(service.fetch_all_discussions_at(false, june), first);
    assert_eq!(http.request_log().len(), 10);
    service.fetch_all_discussions_at(true, june);
    assert_eq!(http.request_log().len(), 20);
    service.cache_ttl = std::time::Duration::ZERO;
    service.fetch_all_discussions_at(false, june);
    assert_eq!(http.request_log().len(), 30);

    for month in 1..=12 {
        let at = Utc.with_ymd_and_hms(2026, month, 15, 0, 0, 0).unwrap();
        assert_eq!(
            is_hurricane_season(at),
            (6..=11).contains(&month),
            "{month}"
        );
    }
}
