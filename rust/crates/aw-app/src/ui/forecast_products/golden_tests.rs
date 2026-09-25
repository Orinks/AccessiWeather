//! Golden parity for Forecaster Notes, generated from the Python panel and
//! dialogs by `rust/tools/golden/notesui.py`.

use aw_core::model::{TextProduct, Timestamp};
use aw_providers::products::py::isoformat;
use aw_providers::products::tabs::{FORECASTER_TABS, NATIONAL_TABS};
use chrono::{DateTime, FixedOffset, Utc};
use serde_json::Value;

use super::ai_summary::Summary;
use super::state::{self, Formatters, PanelState, PanelView};
use super::WidgetSpec;

fn golden() -> Value {
    serde_json::from_str(include_str!(
        "../../../../../testdata/golden/notesui/cases.json"
    ))
    .unwrap()
}

fn from<T: serde::de::DeserializeOwned>(v: &Value) -> T {
    serde_json::from_value(v.clone()).unwrap()
}

/// The generator pins these the same way; the real formatters depend on the
/// machine's time zone and are checked separately.
const PINNED: Formatters = Formatters {
    issuance: |t| format!("Issued: {}", t.map_or("unknown".into(), isoformat)),
    sps_entry: |p| format!("{}: {}", p.product_id, p.headline.as_deref().unwrap_or("")),
};

fn products(result: &Value) -> Vec<TextProduct> {
    match result {
        Value::Null => Vec::new(),
        Value::Array(_) => from(result),
        _ => vec![from(result)],
    }
}

#[test]
fn panel_state_machine_matches_python() {
    for scenario in golden()["scenarios"].as_array().unwrap() {
        let name = scenario["name"].as_str().unwrap();
        let mut has_key = scenario["has_key"].as_bool().unwrap();
        let mut state = PanelState::new(
            scenario["product_type"].as_str().unwrap(),
            from(&scenario["cwa_office"]),
            PINNED,
        );
        assert_eq!(
            state.view,
            from::<PanelView>(&scenario["initial"]),
            "{name}: initial"
        );
        for (i, entry) in scenario["steps"].as_array().unwrap().iter().enumerate() {
            let step = &entry["step"];
            let mut events: Vec<String> = Vec::new();
            match step["op"].as_str().unwrap() {
                "ensure_loaded" => {
                    if state.ensure_loaded() {
                        events.push("load".into());
                    }
                }
                "trigger_load" => {
                    if state.trigger_load() {
                        events.push("load".into());
                    }
                }
                "load_complete" => {
                    let has = state.on_load_complete(products(&step["result"]), has_key);
                    events.push(format!("availability:{has}"));
                }
                "load_error" => {
                    state.on_load_error();
                    events.push("availability:true".into());
                }
                "sps_choice" => {
                    let index = step["index"].as_u64().unwrap() as usize;
                    state.on_sps_choice_changed(index, has_key);
                }
                "explain" | "regenerate" => {
                    if let Some(text) = state.on_explain() {
                        events.push(format!("explain:{text}"));
                    }
                }
                "explain_status" => {
                    let message = step["message"].as_str().unwrap();
                    if let Some(text) = state.on_explain_status(message) {
                        events.push(format!("announce:{text}"));
                    }
                }
                "explain_complete" => {
                    let summary: Summary = from(&step["summary"]);
                    let had_focus = step["explain_had_focus"].as_bool().unwrap();
                    let (focus, announcement) = state.on_explain_complete(&summary, had_focus);
                    if focus {
                        events.push("focus:ai_summary".into());
                    }
                    events.push(format!("announce:{announcement}"));
                }
                "explain_error" => {
                    let announcement = state.on_explain_error(step["message"].as_str().unwrap());
                    events.push("focus:ai_summary".into());
                    events.push(format!("announce:{announcement}"));
                }
                "set_key" => has_key = step["has_key"].as_bool().unwrap(),
                other => panic!("unknown op {other}"),
            }
            assert_eq!(
                events,
                from::<Vec<String>>(&entry["events"]),
                "{name} step {i}: events"
            );
            assert_eq!(
                state.view,
                from::<PanelView>(&entry["view"]),
                "{name} step {i}: view"
            );
        }
    }
}

thread_local! {
    static ZONE: std::cell::RefCell<(FixedOffset, String)> =
        const { std::cell::RefCell::new((FixedOffset::east_opt(0).unwrap(), String::new())) };
}

fn pinned_zone(_: DateTime<Utc>) -> (FixedOffset, String) {
    ZONE.with(|z| z.borrow().clone())
}

#[test]
fn issuance_matches_python_in_a_given_zone() {
    for case in golden()["issuance"].as_array().unwrap() {
        let minutes = case["offset_minutes"].as_i64().unwrap() as i32;
        let zone = (
            FixedOffset::east_opt(minutes * 60).unwrap(),
            case["zone_name"].as_str().unwrap().to_string(),
        );
        ZONE.with(|z| *z.borrow_mut() = zone);
        let time: Option<Timestamp> = from(&case["time"]);
        assert_eq!(
            state::format_issuance_in(time.as_ref(), pinned_zone),
            case["text"].as_str().unwrap()
        );
    }
}

/// On a machine in the zone the golden data was generated in, the real
/// formatter reproduces Python, Windows full zone names included.
#[test]
fn issuance_matches_python_in_the_host_zone() {
    let g = &golden()["host_issuance"];
    let cases = g["cases"].as_array().unwrap();
    let winter: Timestamp = from(&cases[1]["time"]);
    let python_standard = g["tzname"][0].as_str().unwrap();
    if !state::format_issuance(Some(&winter)).ends_with(python_standard) {
        eprintln!("skipping: host zone differs from the golden data's {python_standard}");
        return;
    }
    for case in cases {
        let time: Timestamp = from(&case["time"]);
        assert_eq!(
            state::format_issuance(Some(&time)),
            case["text"].as_str().unwrap()
        );
    }
}

#[test]
fn model_info_matches_python() {
    for case in golden()["model_info"].as_array().unwrap() {
        let summary: Summary = from(&case["summary"]);
        assert_eq!(
            state::build_model_info(&summary),
            case["text"].as_str().unwrap()
        );
    }
}

#[test]
fn tab_labels_match_python() {
    let g = golden();
    let rust: Vec<(String, String)> = FORECASTER_TABS
        .iter()
        .map(|t| (t.product_type.to_string(), t.label.to_string()))
        .collect();
    assert_eq!(rust, from::<Vec<(String, String)>>(&g["forecaster_tabs"]));
    let rust: Vec<(String, String)> = NATIONAL_TABS
        .iter()
        .map(|(id, label)| (id.to_string(), label.to_string()))
        .collect();
    assert_eq!(rust, from::<Vec<(String, String)>>(&g["national_tabs"]));
}

fn assert_widgets(spec: WidgetSpec, python: &[(String, String)], what: &str) {
    assert_eq!(spec.len(), python.len(), "{what}: widget count");
    for ((kind, text), (py_kind, py_text)) in spec.iter().zip(python) {
        assert_eq!(kind, py_kind, "{what}");
        if *text != "*" {
            assert_eq!(text, py_text, "{what}");
        }
    }
}

#[test]
fn widget_labels_match_python() {
    let g = golden();
    for (product_type, widgets) in g["panel_widgets"].as_object().unwrap() {
        let widgets: Vec<(String, String)> = from(widgets);
        let header = (
            "StaticText".to_string(),
            state::header_text(product_type).to_string(),
        );
        assert_eq!(widgets[0], header, "{product_type} header");
        let rest = if product_type == "SPS" {
            let chooser = (
                "StaticText".to_string(),
                super::panel::SPS_CHOICE_LABEL.to_string(),
            );
            assert_eq!(widgets[1], chooser);
            &widgets[2..]
        } else {
            &widgets[1..]
        };
        assert_widgets(super::panel::WIDGETS, rest, product_type);
    }
    let python: Vec<(String, String)> = from(&g["notes_dialog_widgets"]);
    assert_widgets(super::WIDGETS, &python, "notes");
    let python: Vec<(String, String)> = from(&g["national_dialog_widgets"]);
    assert_widgets(super::national::WIDGETS, &python, "national");
    let advanced = &g["advanced_dialog"];
    let python: Vec<(String, String)> = from(&advanced["widgets"]);
    assert_widgets(super::advanced::WIDGETS, &python, "advanced");
    let rust: Vec<(String, String)> = super::advanced::ACCESSIBILITY
        .iter()
        .map(|(name, tooltip)| (name.to_string(), tooltip.to_string()))
        .collect();
    assert_eq!(
        rust,
        from::<Vec<(String, String)>>(&advanced["accessibility"])
    );
}
