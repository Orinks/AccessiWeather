//! Golden parity tests: replay the inputs recorded by
//! `rust/tools/golden/notify.py` and compare with what the Python app did.

use std::path::{Path, PathBuf};

use aw_core::model::{
    AlertLifecycleDiff, Location, TextProduct, WeatherAlert, WeatherAlerts, WeatherData,
};
use aw_core::settings::AppSettings;
use aw_notify::activation::{write_handoff, ActivationKind, ActivationRequest};
use aw_notify::debug::{run_notification_diagnostics, ALERT_PRESETS};
use aw_notify::events::window::{process_notification_events, CachedProducts};
use aw_notify::{
    alert_notifications, py, sound, AlertManager, AlertNotificationSystem, AlertSettings,
    NotificationEventManager, RuntimeState, Toast,
};
use chrono::{DateTime, FixedOffset, Utc};
use serde_json::{json, Value};

fn golden(name: &str) -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/golden/notify")
        .join(name);
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    serde_json::from_str(&text).unwrap()
}

fn from<T: serde::de::DeserializeOwned>(v: &Value) -> T {
    serde_json::from_value(v.clone()).unwrap_or_else(|e| panic!("{e}: {v}"))
}

fn utc(v: &Value) -> DateTime<Utc> {
    DateTime::parse_from_rfc3339(v.as_str().unwrap())
        .unwrap()
        .with_timezone(&Utc)
}

fn local(v: &Value) -> DateTime<FixedOffset> {
    DateTime::parse_from_rfc3339(v.as_str().unwrap()).unwrap()
}

fn settings(v: &Value) -> AppSettings {
    if v.is_null() {
        AppSettings::default()
    } else {
        from(v)
    }
}

fn toast_json(t: &Toast) -> Value {
    json!({
        "title": t.title,
        "message": t.message,
        "timeout": t.timeout,
        "sound_event": t.sound_event,
        "sound_candidates": t.sound_candidates,
        "play_sound": t.play_sound,
        "activation_arguments": t.activation_arguments(),
    })
}

fn toasts_json(toasts: &[Toast]) -> Value {
    Value::Array(toasts.iter().map(toast_json).collect())
}

fn ids(alerts: &[WeatherAlert]) -> Value {
    json!(alerts
        .iter()
        .map(WeatherAlert::unique_id)
        .collect::<Vec<_>>())
}

fn seed(dir: &Path, files: &Value) {
    for (rel, text) in files.as_object().unwrap() {
        let path = dir.join(rel);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, text.as_str().unwrap()).unwrap();
    }
}

fn state_text(dir: &Path) -> Value {
    std::fs::read_to_string(dir.join("state").join("runtime_state.json"))
        .map_or(Value::Null, Value::String)
}

#[test]
fn alert_scenarios_match_python() {
    for sc in golden("alerts.json").as_array().unwrap() {
        let name = sc["name"].as_str().unwrap();
        let dir = tempfile::tempdir().unwrap();
        seed(dir.path(), &sc["seed_files"]);
        let steps = sc["steps"].as_array().unwrap();
        let app_settings = settings(&sc["settings"]);
        let manager = AlertManager::new(
            RuntimeState::open(dir.path()),
            AlertSettings::from_app_settings(&app_settings),
            utc(&steps[0]["now"]),
        );
        let mut system = AlertNotificationSystem::new(manager, app_settings, None);
        for (i, (step, expected)) in steps
            .iter()
            .zip(sc["results"].as_array().unwrap())
            .enumerate()
        {
            let now = utc(&step["now"]);
            let ctx = format!("{name} step {i}");
            let (toasts, popups, radio, sent) = match step["kind"].as_str().unwrap() {
                "process" => {
                    let alerts = WeatherAlerts {
                        alerts: from(&step["alerts"]),
                    };
                    let d = system.process_and_notify(&alerts, now);
                    let sent = json!(d.toasts.len());
                    (
                        d.toasts,
                        ids(&d.popup_alerts),
                        ids(&d.radio_auto_tune_alerts),
                        sent,
                    )
                }
                "lifecycle" => {
                    let diff: AlertLifecycleDiff = from(&step["diff"]);
                    let t = system.notify_lifecycle_changes(&diff);
                    let sent = json!(t.len());
                    (t, json!([]), json!([]), sent)
                }
                "poll" => {
                    let data: WeatherData = from(&step["data"]);
                    let d = system.on_event_poll(&data, now);
                    (
                        d.toasts,
                        ids(&d.popup_alerts),
                        ids(&d.radio_auto_tune_alerts),
                        Value::Null,
                    )
                }
                "update_settings" => {
                    system.update_settings(settings(&step["settings"]));
                    (Vec::new(), json!([]), json!([]), Value::Null)
                }
                other => panic!("unknown step kind {other}"),
            };
            assert_eq!(toasts_json(&toasts), expected["toasts"], "{ctx} toasts");
            assert_eq!(sent, expected["sent"], "{ctx} sent");
            assert_eq!(popups, expected["popups"], "{ctx} popups");
            assert_eq!(radio, expected["radio"], "{ctx} radio");
            let tokens = expected["tokens"].as_f64().unwrap();
            assert!(
                (system.manager.rate_limit_tokens() - tokens).abs() < 1e-6,
                "{ctx} tokens {} != {tokens}",
                system.manager.rate_limit_tokens()
            );
            assert_eq!(
                json!(system.manager.notifications_this_hour()),
                expected["notifications_this_hour"],
                "{ctx} hourly count"
            );
            assert_eq!(
                state_text(dir.path()),
                expected["state"],
                "{ctx} state file"
            );
        }
    }
}

#[test]
fn formatting_matches_python() {
    for case in golden("formatting.json").as_array().unwrap() {
        let alert: WeatherAlert = from(&case["alert"]);
        let s = (!case["settings"].is_null()).then(|| settings(&case["settings"]));
        let (title, message) = alert_notifications::format_accessible_message(
            &alert,
            case["reason"].as_str().unwrap(),
            case["include_areas"].as_bool().unwrap(),
            case["include_expiration"].as_bool().unwrap(),
            s.as_ref(),
        );
        assert_eq!(title, case["title"].as_str().unwrap(), "{case}");
        assert_eq!(message, case["message"].as_str().unwrap(), "{case}");
    }
}

#[test]
fn sound_candidates_and_mutes_match_python() {
    let g = golden("sounds.json");
    for case in g["candidates"].as_array().unwrap() {
        let alert: WeatherAlert = from(&case["alert"]);
        let got = sound::get_candidate_sound_events(
            &alert,
            case["include_specific"].as_bool().unwrap(),
            case["reason"].as_str(),
        );
        assert_eq!(json!(got), case["candidates"], "{case}");
    }
    for case in g["mute"].as_array().unwrap() {
        let candidates: Option<Vec<String>> = from(&case["candidates"]);
        let muted: Vec<String> = from(&case["muted"]);
        let got =
            sound::sound_keys_to_try(case["sound_event"].as_str(), candidates.as_deref(), &muted);
        assert_eq!(json!(got), case["keys"], "{case}");
    }
}

fn request(v: &Value) -> ActivationRequest {
    ActivationRequest {
        kind: ActivationKind::parse(v["kind"].as_str().unwrap()).unwrap(),
        alert_id: v["alert_id"].as_str().map(str::to_string),
    }
}

#[test]
fn activation_matches_python() {
    let g = golden("activation.json");
    for case in g["serialize"].as_array().unwrap() {
        assert_eq!(
            request(&case["request"]).serialize(),
            case["token"].as_str().unwrap()
        );
    }
    for case in g["extract"].as_array().unwrap() {
        let argv: Vec<String> = from(&case["argv"]);
        let got = ActivationRequest::from_argv(&argv)
            .map(|r| json!({"kind": r.kind.as_str(), "alert_id": r.alert_id}));
        assert_eq!(got.unwrap_or(Value::Null), case["request"], "{case}");
    }
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("activation_request.json");
    for case in g["handoff"].as_array().unwrap() {
        assert!(write_handoff(&path, &request(&case["request"])));
        assert_eq!(
            std::fs::read_to_string(&path).unwrap(),
            case["text"].as_str().unwrap()
        );
    }
}

#[test]
fn event_scenarios_match_python() {
    for sc in golden("events.json").as_array().unwrap() {
        let name = sc["name"].as_str().unwrap();
        let dir = tempfile::tempdir().unwrap();
        seed(dir.path(), &sc["seed_files"]);
        let store = RuntimeState::open(dir.path());
        let mut manager: Option<NotificationEventManager> = None;
        let mut suppress = true;
        for (i, (step, expected)) in sc["steps"]
            .as_array()
            .unwrap()
            .iter()
            .zip(sc["results"].as_array().unwrap())
            .enumerate()
        {
            let ctx = format!("{name} step {i}");
            let now = local(&expected["local_now"]);
            let now_utc = now.with_timezone(&Utc);
            let s = settings(&step["settings"]);
            let location: Option<Location> = from(&step["location"]);
            let weather: WeatherData = from(&step["weather"]);
            let hwo: Option<TextProduct> = step.get("hwo").and_then(from);
            let sps: Option<Vec<TextProduct>> = step.get("sps").map(from);
            let cache = step.get("cli_cache").cloned().unwrap_or(json!({}));
            let cli: Option<TextProduct> = step
                .get("cli_stations")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .find_map(|station| {
                    cache
                        .get(station.as_str().unwrap())
                        .filter(|p| !p.is_null())
                })
                .map(from);
            let active: Vec<WeatherAlert> = match step.get("active_alerts") {
                None | Some(Value::Null) => Vec::new(),
                Some(v) => {
                    let alerts = WeatherAlerts { alerts: from(v) };
                    alerts.active(now_utc).into_iter().cloned().collect()
                }
            };
            if let Some(v) = step.get("suppress_startup") {
                suppress = v.as_bool().unwrap();
            }
            let manager = manager
                .get_or_insert_with(|| NotificationEventManager::new(Some(store.clone()), now_utc));
            let out = process_notification_events(
                manager,
                &weather,
                &s,
                location.as_ref(),
                CachedProducts {
                    hwo: hwo.as_ref(),
                    sps: sps.as_deref(),
                    daily_climate: cli.as_ref(),
                },
                &active,
                &mut suppress,
                now,
            );
            assert_eq!(toasts_json(&out.toasts), expected["toasts"], "{ctx} toasts");
            let center: Vec<Value> = out
                .event_center
                .iter()
                .map(|e| json!({"category": e.category, "text": e.text}))
                .collect();
            assert_eq!(
                json!(center),
                expected["event_center"],
                "{ctx} event center"
            );
            assert_eq!(
                json!(suppress),
                expected["suppress_after"],
                "{ctx} suppression flag"
            );
            assert_eq!(
                state_text(dir.path()),
                expected["state"],
                "{ctx} state file"
            );
        }
    }
}

#[test]
fn debug_helpers_match_python() {
    let g = golden("debug.json");
    let now = local(&g["local_now"]);
    let now_utc = now.with_timezone(&Utc);
    for (preset, expected) in ALERT_PRESETS.iter().zip(g["presets"].as_array().unwrap()) {
        let alert = preset.alert(now_utc);
        assert_eq!(preset.label, expected["label"].as_str().unwrap());
        assert_eq!(alert.id.as_deref(), expected["id"].as_str());
        assert_eq!(
            py::isoformat(&alert.expires.unwrap()),
            expected["expires"].as_str().unwrap()
        );
        assert_eq!(
            preset.sound_candidates_text(now_utc),
            expected["candidates_text"].as_str().unwrap()
        );
        let toast = preset.toast(now_utc);
        assert_eq!(toast.title, expected["title"].as_str().unwrap());
        assert_eq!(toast.message, expected["message"].as_str().unwrap());
    }
    assert_eq!(ALERT_PRESETS.len(), g["presets"].as_array().unwrap().len());
    let d = run_notification_diagnostics(&AppSettings::default(), Some("Home Town"), |_| true, now);
    assert_eq!(d.menu_report(), g["menu"]["message"].as_str().unwrap());
    assert_eq!(g["menu"]["caption"], "Notification Test Results");
    assert_eq!(d.tray_report(), g["tray"]["message"].as_str().unwrap());
}
