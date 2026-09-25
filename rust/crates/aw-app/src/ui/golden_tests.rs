//! Golden parity for the main window's text logic, generated from the Python
//! mixins by `rust/tools/golden/mainwin.py`.

use std::collections::{BTreeMap, HashMap};

use aw_core::alert_lifecycle::compute_lifecycle_labels;
use aw_core::display::{
    CurrentConditionsPresentation, ForecastPresentation, SourceAttributionPresentation,
    WeatherPresentation,
};
use aw_providers::geocoding::LocationManager;

use aw_core::model::{WeatherAlerts, WeatherData};
use aw_core::settings::AppSettings;
use aw_core::Location;
use chrono::{NaiveTime, Utc};
use serde_json::Value;

use super::display::*;
use super::location_dialog::edit_location_is_us;
use super::location_dialog::format_coordinates;
use super::locations::*;

fn golden() -> Value {
    serde_json::from_str(include_str!(
        "../../../../testdata/golden/mainwin/cases.json"
    ))
    .unwrap()
}

fn from<T: serde::de::DeserializeOwned>(v: &Value) -> T {
    serde_json::from_value(v.clone()).unwrap()
}

#[test]
fn alert_items_and_lifecycle_labels() {
    let g = &golden()["alert_items"];
    let alerts = WeatherAlerts {
        alerts: from(&g["alerts"]),
    };
    let active = alerts.active(Utc::now());
    let owned: Vec<_> = active.iter().map(|a| (*a).clone()).collect();
    let labels = compute_lifecycle_labels(&owned);
    let expected: BTreeMap<String, String> = from(&g["labels"]);
    assert_eq!(labels, expected);
    for case in g["cases"].as_array().unwrap() {
        let items = if case.get("empty").is_some() {
            alert_list_items(&[], &BTreeMap::new())
        } else if case["use_labels"].as_bool().unwrap() {
            alert_list_items(&active, &labels)
        } else {
            alert_list_items(&active, &BTreeMap::new())
        };
        assert_eq!(items, from::<Vec<String>>(&case["items"]));
        assert_eq!(!items.is_empty(), case["button_enabled"].as_bool().unwrap());
    }
}

#[test]
fn all_locations_summary_matches_python() {
    let g = &golden()["all_locations"];
    let locations: Vec<Location> = from(&g["locations"]);
    let current: Location = from(&g["current"]);
    let cached: HashMap<String, WeatherData> = from(&g["cached"]);
    for case in g["cases"].as_array().unwrap() {
        let settings = AppSettings {
            temperature_unit: from(&case["temperature_unit"]),
            round_values: from(&case["round_values"]),
            ..Default::default()
        };
        let order: String = from(&case["location_sort_order"]);
        let ordered = aw_core::location_sorting::sort_locations_for_display(
            &locations,
            &order,
            Some(&current),
        );
        let (text, alerts) = all_locations_summary(
            &ordered,
            |l| cached.get(&l.name).cloned(),
            &settings,
            Utc::now(),
        );
        assert_eq!(text, case["text"].as_str().unwrap(), "{case}");
        assert_eq!(
            all_locations_alert_items(&alerts),
            from::<Vec<String>>(&case["alert_items"])
        );
    }
    assert_eq!(NO_LOCATIONS_TEXT, g["empty_text"].as_str().unwrap());
}

/// The golden cases only give the fields the window reads.
fn partial_presentation(p: &Value) -> WeatherPresentation {
    let text = |v: &Value, key: &str| v[key].as_str().unwrap_or_default().to_string();
    WeatherPresentation {
        current_conditions: p["current_conditions"].as_object().map(|_| {
            CurrentConditionsPresentation {
                fallback_text: text(&p["current_conditions"], "fallback_text"),
                ..Default::default()
            }
        }),
        source_attribution: p["source_attribution"].as_object().map(|_| {
            SourceAttributionPresentation {
                summary_text: text(&p["source_attribution"], "summary_text"),
                ..Default::default()
            }
        }),
        status_messages: from(&p["status_messages"]),
        forecast: p["forecast"].as_object().map(|_| {
            let f = &p["forecast"];
            ForecastPresentation {
                daily_section_text: text(f, "daily_section_text"),
                hourly_section_text: text(f, "hourly_section_text"),
                marine_section_text: text(f, "marine_section_text"),
                mobility_briefing: f["mobility_briefing"].as_str().map(str::to_string),
                ..Default::default()
            }
        }),
        ..Default::default()
    }
}

#[test]
fn panels_match_python() {
    for case in golden()["panels"].as_array().unwrap() {
        let presentation = partial_presentation(&case["presentation"]);
        let texts = panel_texts(&presentation);
        assert_eq!(texts.current, case["current"].as_str().unwrap());
        assert_eq!(texts.stale_warning, case["stale_warning"].as_str().unwrap());
        assert_eq!(texts.daily, case["daily"].as_str().unwrap());
        assert_eq!(texts.hourly, case["hourly"].as_str().unwrap());
        let events: Vec<String> = from(&case["event_center"]);
        let at_5_04_pm = NaiveTime::from_hms_opt(17, 4, 0).unwrap();
        let entries: Vec<String> = texts
            .briefing
            .iter()
            .filter_map(|b| event_center_entry(b, Some("Briefing"), at_5_04_pm))
            .collect();
        assert_eq!(entries, events);
    }
}

#[test]
fn section_focus_matches_python() {
    for case in golden()["sections"].as_array().unwrap() {
        let visible = case["event_center_visible"].as_bool().unwrap();
        let count = if visible { 6 } else { 5 };
        let sections: Vec<String> = from(&case["sections"]);
        assert_eq!(sections, SECTION_LABELS[..count]);
        for n in 1..=5usize {
            let expected = case["numbers"][n.to_string()].as_str();
            assert_eq!(
                section_for_number(n, visible).map(|i| SECTION_LABELS[i]),
                expected
            );
        }
        let mut previous = None;
        let cycle: Vec<&str> = (0..8)
            .map(|_| {
                let next = next_section(previous, visible);
                previous = Some(next);
                SECTION_LABELS[next]
            })
            .collect();
        assert_eq!(cycle, from::<Vec<String>>(&case["cycle"]));
    }
}

#[test]
fn clock_entries_match_python() {
    for case in golden()["clock"].as_array().unwrap() {
        let time = NaiveTime::from_hms_opt(from(&case["hour"]), from(&case["minute"]), 0).unwrap();
        for entry in case["entries"].as_array().unwrap() {
            let got = event_center_entry(
                entry["text"].as_str().unwrap(),
                entry["category"].as_str(),
                time,
            );
            assert_eq!(got.as_deref(), entry["entry"].as_str());
        }
        assert_eq!(
            last_updated_status(time),
            case["last_updated"].as_str().unwrap()
        );
    }
}

#[test]
fn titles_match_python() {
    for case in golden()["titles"].as_array().unwrap() {
        assert_eq!(
            window_title(case["name"].as_str()),
            case["title"].as_str().unwrap()
        );
    }
}

#[test]
fn location_manager_helpers_match_python() {
    let g = &golden()["location_manager"];
    for case in g["formatted"].as_array().unwrap() {
        let text = format_coordinates(from(&case["lat"]), from(&case["lon"]));
        assert_eq!(text, case["text"].as_str().unwrap());
    }
    for case in g["distances"].as_array().unwrap() {
        let miles = LocationManager::calculate_distance(&from(&case["a"]), &from(&case["b"]));
        assert_eq!(format!("{miles:.2}"), case["miles"].as_str().unwrap());
    }
    for case in g["is_us"].as_array().unwrap() {
        let mut location: Location = from(&case["location"]);
        location.normalize();
        assert_eq!(
            edit_location_is_us(&location),
            case["is_us"].as_bool().unwrap(),
            "{case}"
        );
    }
}

#[test]
fn message_boxes_match_python() {
    let g = &golden()["messages"];
    let version = g["version"].as_str().unwrap();
    let expected: Vec<(String, String)> = g["boxes"]
        .as_array()
        .unwrap()
        .iter()
        .map(|b| (from(&b["message"]), from(&b["caption"])))
        .collect();
    let ours: Vec<(String, String)> = [
        (MSG_SELECT_TO_EDIT.to_string(), CAPTION_NO_LOCATION),
        (MSG_SELECT_TO_REMOVE.to_string(), CAPTION_NO_LOCATION),
        (MSG_LAST_LOCATION.to_string(), CAPTION_CANNOT_REMOVE),
        (confirm_removal_message("Work"), CAPTION_CONFIRM_REMOVAL),
        (
            MSG_NOT_ENOUGH_LOCATIONS.to_string(),
            CAPTION_NOT_ENOUGH_LOCATIONS,
        ),
        (
            super::commands::MSG_SELECT_LOCATION_FIRST.to_string(),
            CAPTION_NO_LOCATION,
        ),
        (
            about_text(version, true, "C:\\Config"),
            "About AccessiWeather",
        ),
        (
            about_text(version, false, "C:\\Config"),
            "About AccessiWeather",
        ),
    ]
    .into_iter()
    // The only intended difference: the About box names wxWidgets.
    .map(|(m, c)| (m.replace("wxWidgets", "wxPython"), c.to_string()))
    .collect();
    assert_eq!(ours, expected);
}

#[test]
fn check_updates_label_matches_python() {
    for case in golden()["check_updates"].as_array().unwrap() {
        assert_eq!(
            check_updates_label(case["channel"].as_str().unwrap()),
            case["label"].as_str().unwrap()
        );
    }
}
