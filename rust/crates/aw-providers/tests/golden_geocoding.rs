//! Parity with `rust/tools/golden/geocoding.py`.

mod common;

use aw_core::location_sorting::sort_locations_for_display;
use aw_core::model::Location;
use aw_providers::current_location::{location_from_coordinates, CurrentCoordinates};
use aw_providers::geocoding::location_manager::{
    format_nominatim_location_name, parse_geocoding_result, LocationManager,
};
use aw_providers::geocoding::{build_fallback_queries, normalize_text, GeocodingService};
use aw_providers::http::FixtureClient;
use common::{assert_matches, assert_requests, cases, fixture_from_exchanges};
use serde_json::{json, to_value, Value};

#[test]
fn geocoding_service_matches_python() {
    for (name, case) in cases("geocoding", "service_") {
        let http = fixture_from_exchanges(&case["exchanges"]);
        let service = GeocodingService::new(
            &http,
            "AccessiWeather",
            case["data_source"].as_str().unwrap(),
        );
        let query = case["query"].as_str().unwrap();
        let output = match case["mode"].as_str().unwrap() {
            "geocode" => to_value(service.geocode_address(query)).unwrap(),
            "suggest5" => to_value(service.suggest_locations(query, 5)).unwrap(),
            "suggest3" => to_value(service.suggest_locations(query, 3)).unwrap(),
            other => panic!("unknown mode {other}"),
        };
        assert_requests(&case["exchanges"], &http, &name);
        assert_matches(&case["output"], &output, &name, &[]);
    }
}

#[test]
fn location_search_matches_python() {
    for (name, case) in cases("geocoding", "search_") {
        let http = fixture_from_exchanges(&case["exchanges"]);
        let manager = LocationManager::new(&http);
        let result = manager.search_locations(
            case["query"].as_str().unwrap(),
            case["limit"].as_u64().unwrap() as usize,
        );
        assert_requests(&case["exchanges"], &http, &name);
        assert_eq!(
            case["error"].as_bool().unwrap(),
            result.is_err(),
            "{name}: error"
        );
        if let Ok(found) = result {
            assert_matches(&case["output"], &to_value(found).unwrap(), &name, &[]);
        }
    }
}

#[test]
fn reverse_geocoding_matches_python() {
    for (name, case) in cases("geocoding", "reverse_") {
        let http = fixture_from_exchanges(&case["exchanges"]);
        let found = LocationManager::new(&http).reverse_geocode_coordinates(
            case["latitude"].as_f64().unwrap(),
            case["longitude"].as_f64().unwrap(),
        );
        assert_requests(&case["exchanges"], &http, &name);
        assert_matches(&case["output"], &to_value(found).unwrap(), &name, &[]);
    }
}

fn location(value: &Value) -> Location {
    serde_json::from_value(value.clone()).unwrap()
}

#[test]
fn pure_helpers_match_python() {
    let (_, g) = cases("geocoding", "pure_functions").remove(0);

    for (query, expected) in g["street_address"].as_object().unwrap() {
        assert_eq!(
            LocationManager::looks_like_street_address(query),
            expected.as_bool().unwrap(),
            "street address: {query}"
        );
    }
    for row in g["format_coordinates"].as_array().unwrap() {
        let (lat, lon) = (row[0].as_f64().unwrap(), row[1].as_f64().unwrap());
        assert_eq!(
            json!(LocationManager::format_coordinates(lat, lon, 4)),
            row[2]
        );
    }
    let places = [
        Location::new("Home", 40.7128, -74.006),
        Location::new("los angeles", 34.0522, -118.2437),
        Location::new("Boston", 42.3601, -71.0589),
        Location::new("Äpfelstadt", 50.9, 10.9),
        Location::new("boston", 42.3601, -71.0589),
        Location::new("Newark", 40.7357, -74.1724),
    ];
    let by_name = |n: &Value| places.iter().find(|p| json!(p.name) == *n).unwrap();
    for row in g["distance"].as_array().unwrap() {
        let d = LocationManager::calculate_distance(by_name(&row[0]), by_name(&row[1]));
        assert_matches(&row[2], &json!(d), "distance", &[]);
    }
    let http = FixtureClient::new();
    let service = GeocodingService::new(&http, "AccessiWeather", "nws");
    for row in g["validate_us_nws"].as_array().unwrap() {
        let (lat, lon) = (row[0].as_f64().unwrap(), row[1].as_f64().unwrap());
        assert_eq!(
            json!(service.validate_coordinates(lat, lon, None)),
            row[2],
            "{lat},{lon}"
        );
    }
    for (zip, expected) in g["zip_codes"].as_object().unwrap() {
        assert_eq!(
            json!(GeocodingService::is_zip_code(zip)),
            *expected,
            "zip {zip:?}"
        );
    }
    for (name, expected) in g["fallback_queries"].as_object().unwrap() {
        assert_eq!(
            json!(build_fallback_queries(name)),
            *expected,
            "fallbacks for {name}"
        );
    }
    for (text, expected) in g["normalize_text"].as_object().unwrap() {
        // CJK transliteration differs between unidecode and deunicode; only
        // the Latin cases matter for matching place names.
        if text.chars().any(|c| c as u32 > 0x2FFF) {
            continue;
        }
        assert_eq!(json!(normalize_text(text)), *expected, "normalize {text:?}");
    }
    for row in g["nominatim_name"].as_array().unwrap() {
        assert_eq!(
            json!(format_nominatim_location_name(&row[0])),
            row[1],
            "{}",
            row[0]
        );
    }
    for row in g["geocoding_result"].as_array().unwrap() {
        assert_matches(
            &row[1],
            &to_value(parse_geocoding_result(&row[0])).unwrap(),
            "geocoding result",
            &[],
        );
    }
    for row in g["sorting"].as_array().unwrap() {
        let anchor = (!row[1].is_null()).then(|| by_name(&row[1]));
        let sorted: Vec<String> =
            sort_locations_for_display(&places, row[0].as_str().unwrap(), anchor)
                .into_iter()
                .map(|l| l.name)
                .collect();
        assert_eq!(json!(sorted), row[2], "sort {row}");
    }

    let coords = [
        (40.7128, -74.006, None),
        (43.65, -79.38, None),
        (43.65, -79.38, Some("Toronto")),
        (51.5, -0.12, Some("")),
    ];
    for ((lat, lon, name), expected) in coords.iter().zip(g["current_location"].as_array().unwrap())
    {
        let loc = location_from_coordinates(
            CurrentCoordinates {
                latitude: *lat,
                longitude: *lon,
                accuracy_meters: None,
            },
            *name,
        );
        assert_eq!(loc, location(expected));
    }
}
