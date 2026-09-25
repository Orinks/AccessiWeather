//! Golden parity for location sorting and the saved-location operations the
//! main window uses (`rust/tools/golden/mainwin.py`).

use aw_core::location_sorting::sort_locations_for_display;
use aw_core::settings::AppConfig;
use aw_core::Location;
use serde_json::Value;

fn golden() -> Value {
    serde_json::from_str(include_str!("../../../testdata/golden/mainwin/cases.json")).unwrap()
}

#[test]
fn sort_locations_for_display_matches_python() {
    let g = &golden()["sorting"];
    let locations: Vec<Location> = serde_json::from_value(g["locations"].clone()).unwrap();
    let anchor: Location = serde_json::from_value(g["anchor"].clone()).unwrap();
    for case in g["cases"].as_array().unwrap() {
        let order = case["order"].as_str();
        let anchor = case["anchor"].as_bool().unwrap().then_some(&anchor);
        let names: Vec<String> = sort_locations_for_display(&locations, order, anchor)
            .into_iter()
            .map(|l| l.name)
            .collect();
        let expected: Vec<String> = serde_json::from_value(case["names"].clone()).unwrap();
        assert_eq!(names, expected, "{case}");
    }
}

fn s(v: &Value) -> String {
    v.as_str().unwrap().to_string()
}

#[test]
fn location_operations_match_python() {
    let g = &golden()["location_ops"];
    let mut config: AppConfig = serde_json::from_value(g["initial"].clone()).unwrap();
    config.normalize();
    for step in g["steps"].as_array().unwrap() {
        let args = step["step"].as_array().unwrap();
        let f = |i: usize| args[i].as_f64().unwrap();
        let result = match args[0].as_str().unwrap() {
            "add_location" => {
                let mut loc = Location::new(s(&args[1]), f(2), f(3));
                loc.country_code = args[4].as_str().map(String::from);
                loc.marine_mode = args[5].as_bool().unwrap();
                config.add_location(loc)
            }
            "set_current_location" => config.set_current_location(args[1].as_str().unwrap()),
            "update_location_details" => config.update_location_details(
                args[1].as_str().unwrap(),
                f(2),
                f(3),
                args[4].as_str().map(String::from),
                args[5].as_bool().unwrap(),
                args[6].as_str(),
            ),
            "reorder_locations" => {
                let names: Vec<String> = serde_json::from_value(args[1].clone()).unwrap();
                config.reorder_locations(&names)
            }
            "remove_location" => config.remove_location(args[1].as_str().unwrap()),
            other => panic!("unknown step {other}"),
        };
        assert_eq!(result, step["result"].as_bool().unwrap(), "{step}");
        let out = serde_json::to_value(&config).unwrap();
        assert_eq!(out["locations"], step["locations"], "{step}");
        assert_eq!(out["current_location"], step["current_location"], "{step}");
    }
}
