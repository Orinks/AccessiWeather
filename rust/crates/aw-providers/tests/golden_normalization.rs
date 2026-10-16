//! Parity with `rust/tools/golden/normalization.py` (shared unit helpers).

mod common;

use aw_core::provider_normalization as pn;
use aw_core::thermal_comfort::{
    sanitize_thermal_comfort_readings, ThermalComfortInput, ThermalComfortReadings,
};
use aw_core::weather_client_parsers as wcp;
use aw_providers::openmeteo::units as omu;
use common::{assert_matches, cases};
use serde_json::{json, Value};

fn f(v: &Value) -> Option<f64> {
    v.as_f64()
}

fn s(v: &Value) -> Option<&str> {
    v.as_str()
}

fn readings(r: ThermalComfortReadings) -> Value {
    json!({
        "feels_like_f": r.feels_like_f, "feels_like_c": r.feels_like_c,
        "wind_chill_f": r.wind_chill_f, "wind_chill_c": r.wind_chill_c,
        "heat_index_f": r.heat_index_f, "heat_index_c": r.heat_index_c,
    })
}

fn rows<'a>(g: &'a Value, key: &str) -> &'a Vec<Value> {
    g[key].as_array().unwrap_or_else(|| panic!("missing {key}"))
}

#[test]
fn helpers_match_python() {
    let (_, g) = cases("normalization", "helpers").remove(0);
    let check = |expected: &Value, actual: Value, what: &str, row: &Value| {
        assert_matches(expected, &actual, &format!("{what} {row}"), &[]);
    };

    for row in rows(&g, "thermal") {
        let i = &row[0];
        let r = sanitize_thermal_comfort_readings(ThermalComfortInput {
            temperature_f: f(&i[0]),
            humidity: f(&i[1]),
            feels_like_f: f(&i[2]),
            wind_chill_f: f(&i[3]),
            heat_index_f: f(&i[4]),
            ..Default::default()
        });
        check(&row[1], readings(r), "thermal", row);
    }
    for row in rows(&g, "thermal_celsius") {
        let i = &row[0];
        let r = sanitize_thermal_comfort_readings(ThermalComfortInput {
            temperature_c: f(&i[0]),
            humidity: f(&i[1]),
            feels_like_c: f(&i[2]),
            ..Default::default()
        });
        check(&row[1], readings(r), "thermal_celsius", row);
    }
    for row in rows(&g, "temperature") {
        check(
            &row[2],
            json!(wcp::normalize_temperature(f(&row[0]), s(&row[1]))),
            "temperature",
            row,
        );
    }
    for row in rows(&g, "speed") {
        check(
            &row[2],
            json!(wcp::convert_wind_speed_to_mph_and_kph(
                f(&row[0]),
                s(&row[1])
            )),
            "speed",
            row,
        );
    }
    for row in rows(&g, "speed_pair") {
        let p = pn::normalize_speed_pair(f(&row[0]), s(&row[1]));
        check(
            &row[2],
            json!({"mph": p.mph, "kph": p.kph}),
            "speed_pair",
            row,
        );
    }
    for row in rows(&g, "pressure") {
        check(
            &row[2],
            json!(wcp::normalize_pressure(f(&row[0]), s(&row[1]))),
            "pressure",
            row,
        );
    }
    for row in rows(&g, "pascals") {
        check(
            &row[2],
            json!(pn::normalize_pressure_to_pascals(f(&row[0]), s(&row[1]))),
            "pascals",
            row,
        );
    }
    for row in rows(&g, "visibility") {
        let p = pn::normalize_visibility_pair(f(&row[0]), s(&row[1]), f(&row[2]));
        check(
            &row[3],
            json!({"miles": p.miles, "kilometers": p.kilometers}),
            "visibility",
            row,
        );
    }
    for row in rows(&g, "snow_depth") {
        check(
            &row[2],
            json!(omu::normalize_snow_depth_to_inches_and_cm(
                f(&row[0]),
                s(&row[1])
            )),
            "snow",
            row,
        );
    }
    for row in rows(&g, "precipitation") {
        check(
            &row[2],
            json!(omu::normalize_precipitation_to_inches_and_mm(
                f(&row[0]),
                s(&row[1])
            )),
            "precip",
            row,
        );
    }
    for row in rows(&g, "height") {
        check(
            &row[2],
            json!(omu::normalize_height_to_feet(f(&row[0]), s(&row[1]))),
            "height",
            row,
        );
    }
    for row in rows(&g, "humidity") {
        let actual = pn::normalize_humidity_percent(f(&row[0]), row[1].as_bool().unwrap());
        check(&row[2], json!(actual), "humidity", row);
    }
    for row in rows(&g, "dewpoint") {
        let p = pn::normalize_dewpoint_pair(f(&row[0]), s(&row[1]), f(&row[2]), f(&row[3]));
        check(
            &row[4],
            json!({"fahrenheit": p.fahrenheit, "celsius": p.celsius}),
            "dewpoint",
            row,
        );
    }
    for row in rows(&g, "format_speed") {
        check(
            &row[2],
            json!(pn::format_speed(f(&row[0]), s(&row[1]).unwrap())),
            "format_speed",
            row,
        );
    }
    for row in rows(&g, "cardinal") {
        check(
            &row[1],
            json!(wcp::degrees_to_cardinal(f(&row[0]))),
            "cardinal",
            row,
        );
    }
    for row in rows(&g, "weather_code") {
        check(
            &row[1],
            json!(wcp::weather_code_to_description(Some(&row[0]))),
            "weather_code",
            row,
        );
    }
    for row in rows(&g, "moon_phase") {
        check(
            &row[1],
            json!(wcp::describe_moon_phase(Some(&row[0]))),
            "moon_phase",
            row,
        );
    }
    for row in rows(&g, "date_name") {
        let name = wcp::format_date_name(s(&row[0]).unwrap(), row[1].as_u64().unwrap() as usize);
        check(&row[2], json!(name), "date_name", row);
    }
    for row in rows(&g, "apparent") {
        let c = pn::classify_apparent_temperature(f(&row[0]), f(&row[1]), f(&row[2]));
        let actual = json!({
            "wind_chill_f": c.wind_chill_f, "wind_chill_c": c.wind_chill_c,
            "heat_index_f": c.heat_index_f, "heat_index_c": c.heat_index_c,
        });
        check(&row[3], actual, "apparent", row);
    }
}
