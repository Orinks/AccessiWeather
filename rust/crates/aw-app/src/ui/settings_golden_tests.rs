//! Golden parity for the Settings dialog, generated from the Python dialog by
//! `rust/tools/golden/settings.py`.

use aw_core::settings::AppSettings;
use aw_core::shortcut_preferences::{normalize_hotkey, normalize_shortcut_text};
use aw_core::sound_events::{user_mutable_sound_events, SOUND_EVENT_SECTIONS};
use serde_json::{Map, Value};

use super::model_browser_dialog::*;
use super::settings_actions::{self, VeniceBalance};
use super::settings_form::*;
use super::tray_text_format_dialog::{supported_placeholders_help, validate_format_string};

fn golden() -> Value {
    serde_json::from_str(include_str!(
        "../../../../testdata/golden/settings/cases.json"
    ))
    .unwrap()
}

fn from<T: serde::de::DeserializeOwned>(v: &Value) -> T {
    serde_json::from_value(v.clone()).unwrap()
}

fn packs(g: &Value) -> Vec<SoundPack> {
    g["sound_packs"]
        .as_object()
        .unwrap()
        .iter()
        .map(|(id, info)| SoundPack {
            id: id.clone(),
            name: info["name"].as_str().unwrap().to_string(),
            specific_alert_sounds: info["specific"].as_bool().unwrap(),
        })
        .collect()
}

fn loaded_form(g: &Value, settings: &Value, startup_actual: bool) -> SettingsForm {
    let settings: AppSettings = from(settings);
    let mut form = SettingsForm::new(packs(g));
    form.load(&settings, startup_actual);
    form
}

/// Compare the form with one Python snapshot of the dialog (`snapshot`).
fn assert_snapshot(form: &SettingsForm, snap: &Value, label: &str) {
    let exported = serde_json::to_value(form).unwrap();
    for (key, expected) in snap["controls"].as_object().unwrap() {
        let actual = match key.as_str() {
            "sound_pack" => Value::from(form.sound_pack.map_or(-1, |i| i as i64)),
            _ => exported
                .get(key)
                .unwrap_or_else(|| panic!("{label}: form has no control {key}"))
                .clone(),
        };
        assert_eq!(&actual, expected, "{label}: control {key}");
    }
    let enabled = &snap["enabled"];
    assert_eq!(
        enabled["taskbar_icon_dynamic_enabled"].as_bool().unwrap(),
        form.taskbar_icon_text_enabled,
        "{label}"
    );
    assert_eq!(
        enabled["taskbar_icon_text_format_dialog"]
            .as_bool()
            .unwrap(),
        form.taskbar_icon_text_enabled,
        "{label}"
    );
    assert_eq!(
        enabled["minimize_on_startup"].as_bool().unwrap(),
        form.minimize_tray,
        "{label}"
    );
    assert_eq!(
        enabled["specific_alert_sounds_for_pack"].as_bool().unwrap(),
        form.specific_alert_sounds_editable(),
        "{label}"
    );
    assert_eq!(
        snap["pw_section_shown"].as_bool().unwrap(),
        form.pirate_weather_section_shown(),
        "{label}"
    );
    assert_eq!(
        snap["venice_panel_shown"].as_bool().unwrap(),
        form.ai_provider == 1,
        "{label}"
    );
    assert_eq!(
        from::<Vec<String>>(&snap["ai_model_items"]),
        form.state.ai_model_items,
        "{label}"
    );
    let names: Vec<&str> = form
        .state
        .sound_packs
        .iter()
        .map(|p| p.name.as_str())
        .collect();
    assert_eq!(
        from::<Vec<String>>(&snap["sound_pack_items"]),
        names,
        "{label}"
    );
    assert_eq!(
        snap["event_sounds_summary"].as_str().unwrap(),
        form.event_sound_summary(),
        "{label}"
    );
    assert_eq!(
        snap["source_settings_summary"].as_str().unwrap(),
        form.state.source_settings.summary_text(),
        "{label}"
    );
    let (values, warning) = form.collect();
    let expected: Map<String, Value> = from(&snap["collect"]);
    for (key, value) in &expected {
        assert_eq!(values.get(key), Some(value), "{label}: collected {key}");
    }
    assert_eq!(values.len(), expected.len(), "{label}: collected keys");

    // Python shows the hotkey warning on every collect: once when the
    // snapshot was taken, once more for any collect during the step.
    let boxes = snap["boxes"].as_array().unwrap();
    if let Some(warning) = warning {
        assert!(!boxes.is_empty(), "{label}: expected a hotkey warning");
        for b in boxes {
            assert_eq!(b["message"].as_str().unwrap(), warning, "{label}");
            assert_eq!(b["caption"], "Invalid hotkey", "{label}");
        }
    } else {
        assert!(boxes.is_empty(), "{label}: unexpected boxes {boxes:?}");
    }
}

#[test]
fn defaults_match_python() {
    let g = golden();
    let python = g["defaults"].as_object().unwrap();
    let rust = serde_json::to_value(AppSettings::default()).unwrap();
    for (key, value) in rust.as_object().unwrap() {
        assert_eq!(python.get(key), Some(value), "default for {key}");
    }
    for key in python.keys() {
        let secret = aw_store::secrets::API_KEY_NAMES.contains(&key.as_str());
        assert!(
            rust.get(key).is_some() || secret || key.starts_with("github_"),
            "Rust settings lack {key}"
        );
    }
}

#[test]
fn dialog_loads_and_collects_like_python() {
    let g = golden();
    for case in g["dialog"].as_array().unwrap() {
        let label = case["name"].as_str().unwrap();
        let form = loaded_form(
            &g,
            &case["settings"],
            case["startup_actual"].as_bool().unwrap(),
        );
        assert_snapshot(&form, &case["loaded"], label);
    }
}

#[test]
fn edits_follow_python_handlers() {
    let g = golden();
    let edits = &g["edits"];
    let mut form = loaded_form(&g, &edits["settings"], false);
    for step in edits["steps"].as_array().unwrap() {
        let label = step["step"].as_str().unwrap();
        match label {
            "minimize_on" => {
                form.minimize_tray = true;
                form.update_minimize_on_startup_state();
                form.minimize_on_startup = true;
            }
            "minimize_off" => {
                form.minimize_tray = false;
                form.update_minimize_on_startup_state();
            }
            "pick_default_pack" | "pick_nature_pack" => {
                form.sound_pack = Some(if label == "pick_default_pack" { 0 } else { 2 });
                form.refresh_specific_alert_sounds_control();
            }
            "untick_specific" => form.specific_alert_sounds_for_pack = false,
            "browse_specific" => form.select_browsed_model("openai/gpt-4o-mini"),
            "browse_again" => form.select_browsed_model("google/gemini-2.0"),
            "browse_auto" => form.select_browsed_model("openrouter/auto"),
            "browse_free" => form.select_browsed_model("openrouter/free"),
            "source_modal" => {
                form.state.source_settings = SourceSettings {
                    auto_mode_api_budget: 1,
                    auto_sources_us: vec!["openmeteo".into()],
                    auto_sources_international: vec!["pirateweather".into(), "openmeteo".into()],
                    station_selection_strategy: 3,
                }
            }
            "event_sounds" => {
                for (key, on) in &mut form.state.event_sound_states {
                    match *key {
                        "startup" => *on = false,
                        "alert" => *on = true,
                        _ => {}
                    }
                }
            }
            "all_sounds_off" => {
                for (_, on) in &mut form.state.event_sound_states {
                    *on = false;
                }
            }
            "valid_hotkey" => form.noaa_radio_hotkey = "  alt + shift + f12 ".into(),
            "invalid_hotkey" => form.noaa_radio_hotkey = "Shift".into(),
            "blank_hotkey" => form.noaa_radio_hotkey = "   ".into(),
            "blank_venice_model" => form.venice_model = "  ".into(),
            "data_source_nws" => form.data_source = 1,
            "reset_prompt" => form.custom_prompt.clear(),
            other => panic!("unknown step {other}"),
        }
        assert_snapshot(&form, step, label);
    }
}

#[test]
fn save_guard_keeps_keys_unless_cleared() {
    let g = golden();
    let fields = ["pw_key", "airnow_key", "openrouter_key", "venice_key"];
    for case in g["save_guard"].as_array().unwrap() {
        let mut form = loaded_form(&g, &case["settings"], false);
        for (key, value) in case["edits"].as_object().unwrap() {
            let value = value.as_str().unwrap().to_string();
            match key.as_str() {
                "pw_key" => form.pw_key = value,
                "airnow_key" => form.airnow_key = value,
                "openrouter_key" => form.openrouter_key = value,
                _ => form.venice_key = value,
            }
        }
        let cleared = fields.map(|f| case["cleared"][f].as_bool().unwrap());
        let (mut values, _) = form.collect();
        form.guard_api_keys(&mut values, cleared);
        let expected = case["saved_keys"].as_object().unwrap();
        for (setting, _) in GUARDED_API_KEYS {
            assert_eq!(values.get(setting), expected.get(setting), "{setting}");
        }
    }
}

#[test]
fn shortcut_validation_matches_python() {
    let g = golden();
    for case in g["shortcuts"].as_array().unwrap() {
        let input: Vec<String> = from(&case["input"]);
        let settings = AppSettings {
            shortcut_show_main_window: input[0].clone(),
            shortcut_hide_main_window: input[1].clone(),
            shortcut_read_tray_info: input[2].clone(),
            noaa_radio_hotkey: input[3].clone(),
            ..AppSettings::default()
        };
        let mut form = SettingsForm::new(packs(&g));
        form.load(&settings, false);
        let result = form
            .validate_window_tray_shortcuts()
            .map(|(setting, message)| vec![setting.to_string(), message]);
        assert_eq!(
            result,
            from::<Option<Vec<String>>>(&case["result"]),
            "{input:?}"
        );
        let fields = vec![
            form.shortcut_show_main_window.clone(),
            form.shortcut_hide_main_window.clone(),
            form.shortcut_read_tray_info.clone(),
        ];
        assert_eq!(fields, from::<Vec<String>>(&case["fields"]), "{input:?}");
    }
}

fn outcome(result: Result<String, String>) -> Value {
    match result {
        Ok(v) => serde_json::json!({ "ok": v }),
        Err(e) => serde_json::json!({ "err": e }),
    }
}

#[test]
fn shortcut_and_hotkey_normalization_match_python() {
    let g = golden();
    for case in g["normalize"]["shortcuts"].as_array().unwrap() {
        let input = case["input"].as_str().unwrap();
        let mut expected = case.clone();
        expected.as_object_mut().unwrap().remove("input");
        assert_eq!(
            outcome(normalize_shortcut_text(input, true)),
            expected,
            "{input:?}"
        );
    }
    for case in g["normalize"]["hotkeys"].as_array().unwrap() {
        let input = case["input"].as_str().unwrap();
        let mut expected = case.clone();
        expected.as_object_mut().unwrap().remove("input");
        assert_eq!(outcome(normalize_hotkey(input)), expected, "{input:?}");
    }
}

#[test]
fn summaries_and_sound_sections_match_python() {
    let g = golden();
    let s = &g["summaries"];
    for case in s["sources"].as_array().unwrap() {
        let state = &case["state"];
        let settings = SourceSettings {
            auto_mode_api_budget: from(&state["auto_mode_api_budget"]),
            auto_sources_us: from(&state["auto_sources_us"]),
            auto_sources_international: from(&state["auto_sources_international"]),
            station_selection_strategy: from(&state["station_selection_strategy"]),
        };
        assert_eq!(settings.summary_text(), case["text"].as_str().unwrap());
    }
    for case in s["events"].as_array().unwrap() {
        let muted: Vec<String> = from(&case["muted"]);
        let states: Vec<(&str, bool)> = user_mutable_sound_events()
            .map(|(k, _)| (k, !muted.iter().any(|m| m == k)))
            .collect();
        assert_eq!(
            event_sound_summary_text(&states),
            case["text"].as_str().unwrap()
        );
    }
    let sections: Vec<Value> = SOUND_EVENT_SECTIONS
        .iter()
        .map(|(title, description, events)| {
            serde_json::json!({
                "title": title,
                "description": description,
                "events": events.iter().map(|(k, _)| *k).collect::<Vec<_>>(),
            })
        })
        .collect();
    assert_eq!(Value::from(sections), s["sections"]);
    let mutable: Vec<Vec<&str>> = user_mutable_sound_events()
        .map(|(k, l)| vec![k, l])
        .collect();
    assert_eq!(serde_json::to_value(mutable).unwrap(), s["mutable"]);
}

#[test]
fn source_settings_dialog_falls_back_to_open_meteo() {
    let s = SourceSettings::from_dialog(0, 2, [false; 3], [false, true]);
    assert_eq!(s.auto_sources_us, vec!["openmeteo"]);
    assert_eq!(s.auto_sources_international, vec!["pirateweather"]);
    assert_eq!(
        (s.auto_mode_api_budget, s.station_selection_strategy),
        (0, 2)
    );
    let s = SourceSettings::from_dialog(2, 0, [true, false, true], [false; 2]);
    assert_eq!(s.auto_sources_us, vec!["nws", "pirateweather"]);
    assert_eq!(s.auto_sources_international, vec!["openmeteo"]);
}

#[test]
fn applying_the_dict_keeps_unknown_keys_and_unsent_api_keys() {
    let mut settings = AppSettings {
        avwx_api_key: "avwx".into(),
        pirate_weather_api_key: "old-pw".into(),
        ..AppSettings::default()
    };
    settings
        .extra
        .insert("future_flag".into(), Value::Bool(true));
    let mut form = SettingsForm::new(Vec::new());
    form.load(&settings, false);
    form.update_interval = 42;
    form.custom_prompt = "Hi".into();
    let (mut values, _) = form.collect();
    values.remove("pirate_weather_api_key");
    values.insert("openrouter_api_key".into(), "new-or".into());
    apply_settings_dict(&mut settings, &values).unwrap();
    assert_eq!(settings.update_interval_minutes, 42);
    assert_eq!(settings.custom_system_prompt.as_deref(), Some("Hi"));
    assert_eq!(settings.pirate_weather_api_key, "old-pw");
    assert_eq!(settings.avwx_api_key, "avwx");
    assert_eq!(settings.openrouter_api_key, "new-or");
    assert_eq!(settings.extra["future_flag"], Value::Bool(true));
}

fn catalog(models: &Value) -> Vec<CatalogModel> {
    from(models)
}

#[test]
fn model_browser_text_matches_python() {
    let g = golden();
    let mb = &g["model_browser"];
    for kind in ["openrouter", "venice"] {
        for model in mb[kind]["models"].as_array().unwrap() {
            let m: CatalogModel = from(model);
            assert_eq!(m.display_name(), model["display_name"].as_str().unwrap());
            assert_eq!(
                m.context_display(),
                model["context_display"].as_str().unwrap()
            );
        }
    }
    for case in mb["lists"].as_array().unwrap() {
        let venice = case["provider"] == "venice";
        let models = catalog(&mb[if venice { "venice" } else { "openrouter" }]["models"]);
        let f = &case["filters"];
        let filters = Filters {
            search: f["search"].as_str().unwrap_or("").to_string(),
            free_only: f["free_only"].as_bool().unwrap_or(false),
            price: f["price"].as_u64().unwrap_or(0) as u32,
            function_only: f["function_only"].as_bool().unwrap_or(false),
            provider_index: f["provider_index"].as_u64().unwrap_or(0) as usize,
        };
        let providers: Vec<String> = from(&case["providers"]);
        assert_eq!(
            provider_list(&models, venice, &Filters::default()),
            providers
        );
        let shown = apply_filters(&models, venice, &filters, &providers);
        let ids: Vec<&str> = shown.iter().map(|m| m.id.as_str()).collect();
        assert_eq!(ids, from::<Vec<String>>(&case["filtered"]), "{f}");
        let items: Vec<String> = shown.iter().map(|m| list_item(m, venice)).collect();
        assert_eq!(items, from::<Vec<String>>(&case["items"]), "{f}");
        assert_eq!(
            status_text(shown.len(), models.len()),
            case["status"].as_str().unwrap()
        );
    }
    for case in mb["descriptions"].as_array().unwrap() {
        let venice = case["provider"] == "venice";
        let models = catalog(&mb[if venice { "venice" } else { "openrouter" }]["models"]);
        let m = &models[case["index"].as_u64().unwrap() as usize];
        assert_eq!(model_description(m, venice), case["text"].as_str().unwrap());
        assert_eq!(!m.offline, case["select_enabled"].as_bool().unwrap());
    }
    for case in mb["balances"].as_array().unwrap() {
        let balance: Option<VeniceBalance> = from(&case["balance"]);
        assert_eq!(
            balance_status(balance.as_ref()),
            case["text"].as_str().unwrap()
        );
    }
    for (provider, name) in mb["provider_names"].as_object().unwrap() {
        assert_eq!(provider_display_name(provider), name.as_str().unwrap());
    }
}

#[test]
fn format_g_matches_python() {
    for (value, expected) in [
        (0.0, "0"),
        (12.5, "12.5"),
        (1234567.0, "1.23457e+06"),
        (0.00001, "1e-05"),
        (0.0001, "0.0001"),
        (100000.0, "100000"),
        (0.15, "0.15"),
        (2.8, "2.8"),
    ] {
        assert_eq!(format_g(value), expected, "{value}");
    }
}

#[test]
fn tray_format_checks_match_python() {
    let g = golden();
    let t = &g["tray_format"];
    assert_eq!(supported_placeholders_help(), t["help"].as_str().unwrap());
    for case in t["validate"].as_array().unwrap() {
        let input = case["input"].as_str().unwrap();
        let expected = match case["result"][1].as_str() {
            Some(problem) => Err(problem.to_string()),
            None => Ok(()),
        };
        assert_eq!(validate_format_string(input), expected, "{input:?}");
    }
}

#[test]
fn portable_copy_checks_match_python() {
    let g = golden();
    let tmp = tempfile::tempdir().unwrap();
    let root = tmp.path();
    let write = |name: &str, data: Option<&str>| {
        let dir = root.join(name);
        std::fs::create_dir_all(&dir).unwrap();
        if let Some(data) = data {
            std::fs::write(dir.join("accessiweather.json"), data).unwrap();
        }
        dir
    };
    std::fs::create_dir(root.join("empty")).unwrap();
    let other = write("other", None);
    std::fs::write(other.join("notes.txt"), "x").unwrap();
    let good = r#"{"settings": {"data_source": "nws", "ai_model_preference": "openrouter/free", "temperature_unit": "f", "custom_instructions": "  "}, "locations": [{"name": "A"}, {"name": "B"}]}"#;
    let good_copy = r#"{"settings": {"data_source": "auto", "temperature_unit": "f"}, "locations": [{"name": "A"}]}"#;
    let cases = [
        ("missing", root.join("nope"), None),
        ("empty", root.join("empty"), None),
        ("no_config", other, None),
        ("zero_size", write("zero", Some("")), None),
        ("invalid", write("invalid", Some("{not json")), None),
        ("array", write("array", Some("[1]")), None),
        (
            "no_locations",
            write("nolocs", Some(r#"{"settings": {}, "locations": []}"#)),
            None,
        ),
        (
            "good",
            write("good", Some(good)),
            Some(write("good_copy", Some(good_copy))),
        ),
        (
            "prompt",
            write(
                "prompt",
                Some(
                    r#"{"settings": {"prompt": "hi", "data_source": "auto"}, "locations": [{"name": "A"}]}"#,
                ),
            ),
            None,
        ),
    ];
    for (expected, (name, src, dst)) in g["portable"].as_array().unwrap().iter().zip(cases) {
        assert_eq!(expected["name"], name);
        let check = settings_actions::installed_config_precheck(&src);
        assert_eq!(check.is_ok(), expected["ok"].as_bool().unwrap(), "{name}");
        if let Err(reason) = &check {
            assert_eq!(reason, expected["reason"].as_str().unwrap(), "{name}");
            continue;
        }
        let summary = settings_actions::portable_copy_summary(&src).unwrap();
        assert_eq!(summary, from::<Vec<String>>(&expected["summary"]), "{name}");
        if let Some(dst) = dst {
            let validation = settings_actions::validate_portable_copy(&src, &dst);
            let messages = validation.clone().err().unwrap_or_default();
            assert_eq!(
                serde_json::json!([validation.is_ok(), messages]),
                expected["validation"],
                "{name}"
            );
        }
    }
}

#[test]
fn settings_export_import_round_trip() {
    let tmp = tempfile::tempdir().unwrap();
    let path = tmp.path().join("export.json");
    let mut config = aw_core::settings::AppConfig::default();
    config.settings.temperature_unit = "c".into();
    config.settings.pirate_weather_api_key = "secret".into();
    config
        .locations
        .push(aw_core::Location::new("Home", 40.0, -75.0).with_country("US"));
    settings_actions::export_settings(&path, &config).unwrap();
    let text = std::fs::read_to_string(&path).unwrap();
    assert!(!text.contains("secret"));
    let data: Value = serde_json::from_str(&text).unwrap();
    assert_eq!(data["locations"][0]["country_code"], "US");
    assert!(data["exported_at"].is_string());

    let mut target = aw_core::settings::AppConfig::default();
    target
        .locations
        .push(aw_core::Location::new("Home", 1.0, 2.0));
    std::fs::write(
        &path,
        r#"{"settings": {"temperature_unit": "f", "data_source": "bogus"},
            "locations": [{"name": "Home", "latitude": 5, "longitude": 6},
                          {"name": "Work", "latitude": "7.5", "longitude": 8, "country_code": "CA"},
                          {"name": "", "latitude": 1, "longitude": 1},
                          {"name": "NoLon", "latitude": 1}]}"#,
    )
    .unwrap();
    settings_actions::import_settings(&path, &mut target).unwrap();
    assert_eq!(target.settings.temperature_unit, "f");
    assert_eq!(target.settings.data_source, "auto");
    let names: Vec<&str> = target.locations.iter().map(|l| l.name.as_str()).collect();
    assert_eq!(names, ["Home", "Work"]);
    assert_eq!(target.locations[0].latitude, 1.0);
    assert_eq!(target.locations[1].latitude, 7.5);
    assert_eq!(target.locations[1].country_code.as_deref(), Some("CA"));
}

#[test]
fn sound_packs_are_read_from_pack_json() {
    let tmp = tempfile::tempdir().unwrap();
    let pack = |id: &str, json: &str| {
        let dir = tmp.path().join(id);
        std::fs::create_dir(&dir).unwrap();
        std::fs::write(dir.join("pack.json"), json).unwrap();
    };
    pack(
        "alpha",
        r#"{"name": "Alpha", "sounds": {"tornado_warning": "t.ogg"}}"#,
    );
    pack("beta", r#"{"sounds": {"alert": "a.ogg"}}"#);
    pack(
        "gamma",
        r#"{"name": "Gamma", "specific_alert_sounds": false, "sounds": {"watch": "w.ogg"}}"#,
    );
    pack("broken", "{");
    std::fs::create_dir(tmp.path().join("no_json")).unwrap();
    let mut packs = settings_actions::available_sound_packs(tmp.path());
    packs.sort_by(|a, b| a.id.cmp(&b.id));
    let summary: Vec<(&str, &str, bool)> = packs
        .iter()
        .map(|p| (p.id.as_str(), p.name.as_str(), p.specific_alert_sounds))
        .collect();
    assert_eq!(
        summary,
        [
            ("alpha", "Alpha", true),
            ("beta", "beta", false),
            ("gamma", "Gamma", false)
        ]
    );
}

/// The Python choice lists by control name, for the Rust tables that fill them.
fn rust_choices(name: &str) -> Option<&'static [&'static str]> {
    Some(match name {
        "Temperature units" => &TEMP_UNIT_CHOICES,
        "Wind speed units" => &WIND_SPEED_UNIT_CHOICES,
        "Saved location order" => &LOCATION_SORT_CHOICES,
        "Daily forecast range" => &FORECAST_DURATION_CHOICES,
        "Forecast time reference" => &FORECAST_TIME_REF_CHOICES,
        "Time display mode" => &TIME_MODE_CHOICES,
        "Date format" => &DATE_FORMAT_CHOICES,
        "Verbosity level" => &VERBOSITY_CHOICES,
        "Alert display style" => &ALERT_DISPLAY_CHOICES,
        "Alert area" => &RADIUS_TYPE_CHOICES,
        "Notify for: precipitation sensitivity level" => &SENSITIVITY_CHOICES,
        "Precipitation likelihood threshold" => &LIKELIHOOD_THRESHOLD_CHOICES,
        "Weather source" => &DATA_SOURCE_CHOICES,
        "AI provider" => &AI_PROVIDER_CHOICES,
        "AI model preference" => &AI_MODEL_CHOICES,
        "AI explanation style" => &AI_STYLE_CHOICES,
        "Release channel" => &UPDATE_CHANNEL_CHOICES,
        _ => return None,
    })
}

/// Screen readers speak these strings, so every page must build the same
/// labels in the same order, with the same names, tooltips and choices.
#[test]
fn pages_build_python_labels_in_order() {
    let g = golden();
    let w = &g["widgets"];
    let dialog_src = include_str!("settings_dialog.rs");
    assert!(dialog_src.contains(&format!("\"{}\"", w["title"].as_str().unwrap())));
    for text in w["intro"]
        .as_array()
        .unwrap()
        .iter()
        .chain(w["buttons"].as_array().unwrap())
    {
        let text = text.as_str().unwrap().replace('\n', " ");
        assert!(dialog_src.contains(&format!("\"{text}\"")), "{text}");
    }
    let pages: Vec<&str> = w["pages"]
        .as_array()
        .unwrap()
        .iter()
        .map(|p| p["label"].as_str().unwrap())
        .collect();
    assert_eq!(pages, super::settings_tabs::TAB_LABELS);

    let src = include_str!("settings_tabs.rs");
    let default_names = [
        "staticText",
        "button",
        "panel",
        "text",
        "choice",
        "check",
        "wxSpinCtrl",
    ];
    for page in w["pages"].as_array().unwrap() {
        let mut pos = 0;
        for widget in page["widgets"].as_array().unwrap() {
            let class = widget["class"].as_str().unwrap();
            let name = widget["name"].as_str().unwrap();
            // `Wrap` breaks long labels at spaces.
            let label = widget["label"].as_str().unwrap().replace('\n', " ");
            let dynamic = name == "Event sound summary";
            // Python's hidden timing spins; their values live in the form.
            if [
                "Minimum time between any alert notifications in minutes",
                "Minutes before repeating the same alert notification",
                "Only notify for alerts issued within this many minutes",
            ]
            .contains(&name)
            {
                continue;
            }
            if matches!(class, "StaticText" | "CheckBox" | "Button")
                && !label.is_empty()
                && !dynamic
            {
                let literal = format!("\"{label}\"");
                let found = src[pos..].find(&literal).unwrap_or_else(|| {
                    panic!("{}: {label:?} missing or out of order", page["label"])
                });
                pos += found + literal.len();
            }
            if !default_names.contains(&name) && name != label {
                assert!(src.contains(&format!("\"{name}\"")), "name {name:?}");
            }
            if let Some(tip) = widget["tooltip"].as_str() {
                assert!(src.contains(&format!("\"{tip}\"")), "tooltip {tip:?}");
            }
            if let (Some(choices), Some(rust)) = (widget.get("choices"), rust_choices(name)) {
                assert_eq!(from::<Vec<String>>(choices), rust, "choices of {name}");
            }
        }
    }
}
