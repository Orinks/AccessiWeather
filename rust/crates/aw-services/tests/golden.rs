//! Parity with the Python app: outputs recorded by `rust/tools/golden/services.py`.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use aw_core::settings::AppConfig;
use aw_core::Location;
use aw_services::activation::ActivationRequest;
use aw_services::import_export;
use aw_services::onboarding::{self, Buttons, Facts, Icon, Onboarding, Response, Step};
use aw_services::report_issue;
use aw_services::startup::{self, Platform, StartupManager};
use aw_services::update::{self, format_release_notes};
use aw_services::update_integrity::{find_checksum_asset, parse_checksum_file};
use aw_services::update_restart;
use serde_json::{json, Value};

fn golden(name: &str) -> Value {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/golden/services")
        .join(name);
    serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap()
}

fn releases() -> Vec<Value> {
    let path =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../testdata/services/github_releases.json");
    serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap()
}

fn s(v: &Value) -> &str {
    v.as_str().unwrap()
}

fn opt(v: &Value) -> Option<&str> {
    v.as_str()
}

#[test]
fn version_comparison_and_tags() {
    let g = golden("updates.json");
    for case in g["versions"].as_array().unwrap() {
        let release = json!({"tag_name": case["tag"]});
        assert_eq!(
            update::is_update_available(
                &release,
                s(&case["current_version"]),
                opt(&case["current_nightly_date"])
            ),
            case["available"].as_bool().unwrap(),
            "{case}"
        );
    }
    for (tag, info) in g["tags"].as_object().unwrap() {
        let release = json!({"tag_name": tag});
        assert_eq!(
            update::parse_nightly_date(tag).as_deref(),
            opt(&info["nightly_date"]),
            "{tag}"
        );
        assert_eq!(
            update::is_nightly_release(&release),
            info["is_nightly"].as_bool().unwrap()
        );
        let (identifier, nightly) = update::release_identifier(&release);
        assert_eq!(identifier, s(&info["identifier"]), "{tag}");
        assert_eq!(nightly, info["type"] == "nightly");
    }
    for case in g["commit_hashes"].as_array().unwrap() {
        assert_eq!(
            update::parse_commit_hash(s(&case["notes"])).as_deref(),
            opt(&case["hash"]),
            "{}",
            case["notes"]
        );
    }
}

#[test]
fn channel_selection_on_recorded_releases() {
    let g = golden("updates.json");
    let recorded = releases();
    // The recorded releases predate the Rust artifacts; give every release
    // one so the Python-side choice can be compared field by field.
    let with_rust_assets: Vec<Value> = recorded
        .iter()
        .map(|r| {
            let mut r = r.clone();
            let tag = r["tag_name"].as_str().unwrap().to_string();
            r["assets"].as_array_mut().unwrap().push(json!({
                "name": "accessiweather-windows-x86_64.zip",
                "browser_download_url": format!("https://example.test/{tag}/accessiweather-windows-x86_64.zip"),
            }));
            r
        })
        .collect();
    for case in g["selection"].as_array().unwrap() {
        let channel = s(&case["channel"]);
        let current = s(&case["current_version"]);
        let nightly = opt(&case["current_nightly_date"]);
        let selected = update::select_latest_release(&recorded, channel)
            .map(|r| r["tag_name"].as_str().unwrap());
        assert_eq!(selected, opt(&case["selected_tag"]), "{case}");
        assert!(update::update_from_releases(
            &recorded, current, nightly, channel, "windows", "x86_64"
        )
        .is_none());

        let info = update::update_from_releases(
            &with_rust_assets,
            current,
            nightly,
            channel,
            "windows",
            "x86_64",
        );
        let expected = &case["update"];
        match info {
            None => assert!(expected.is_null(), "{case}"),
            Some(info) => {
                assert_eq!(info.version, s(&expected["version"]));
                assert_eq!(info.is_nightly, expected["is_nightly"].as_bool().unwrap());
                assert_eq!(
                    info.is_prerelease,
                    expected["is_prerelease"].as_bool().unwrap()
                );
                assert_eq!(info.commit_hash.as_deref(), opt(&expected["commit_hash"]));
                assert_eq!(info.release_notes, s(&expected["release_notes"]));
                assert_eq!(info.artifact_name, "accessiweather-windows-x86_64.zip");
                assert!(info.download_url.contains(selected.unwrap()));
                assert!(info.release.is_some());
            }
        }
    }
    let synthetic = g["synthetic_releases"].as_array().unwrap();
    for (channel, tag) in g["synthetic_selection"].as_object().unwrap() {
        let selected =
            update::select_latest_release(synthetic, channel).map(|r| r["tag_name"].clone());
        assert_eq!(selected.as_ref(), Some(tag), "{channel}");
    }
}

#[test]
fn release_notes_and_checksums() {
    let g = golden("updates.json");
    for case in g["release_notes"].as_array().unwrap() {
        assert_eq!(
            format_release_notes(s(&case["raw"])),
            s(&case["formatted"]),
            "{}",
            case["raw"]
        );
    }
    for case in g["checksum_parse"].as_array().unwrap() {
        let parsed = parse_checksum_file(s(&case["content"]), s(&case["artifact"]))
            .map(|(algo, hash)| json!([algo, hash]));
        assert_eq!(parsed.unwrap_or(Value::Null), case["result"], "{case}");
    }
    for case in g["checksum_find"].as_array().unwrap() {
        let assets: Vec<Value> = case["assets"]
            .as_array()
            .unwrap()
            .iter()
            .map(|n| json!({"name": n}))
            .collect();
        let found = find_checksum_asset(&json!({"assets": assets}), s(&case["artifact"]))
            .map(|a| a["name"].clone());
        assert_eq!(found.unwrap_or(Value::Null), case["found"], "{case}");
    }
}

#[test]
fn restart_scripts() {
    let g = golden("updates.json");
    for case in g["macos_scripts"].as_array().unwrap() {
        assert_eq!(
            update_restart::build_macos_update_script(
                Path::new(s(&case["update_path"])),
                Path::new(s(&case["app_path"]))
            ),
            s(&case["text"])
        );
    }
    // Windows paths only render with backslashes on Windows.
    if cfg!(windows) {
        let p = &g["portable_script"];
        assert_eq!(
            update_restart::build_portable_update_script(
                Path::new(s(&p["zip_path"])),
                Path::new(s(&p["target_dir"])),
                Path::new(s(&p["exe_path"])),
                p["pid"].as_u64().unwrap() as u32,
            ),
            s(&p["text"])
        );
    }
}

fn manager(exe: &str, platform: Platform) -> StartupManager {
    StartupManager {
        platform,
        executable: PathBuf::from(exe),
        ..StartupManager::new()
    }
}

#[test]
fn startup_entries() {
    let g = golden("startup.json");
    for case in g["list2cmdline"].as_array().unwrap() {
        let args: Vec<String> = serde_json::from_value(case["args"].clone()).unwrap();
        assert_eq!(startup::list2cmdline(&args), s(&case["command"]));
    }
    for case in g["desktop_entries"].as_array().unwrap() {
        let m = manager(s(&case["executable"]), Platform::Linux);
        assert_eq!(m.linux_desktop_entry(), s(&case["text"]));
    }
    for case in g["plists"].as_array().unwrap() {
        let m = manager(s(&case["executable"]), Platform::MacOs);
        assert_eq!(m.macos_plist(), s(&case["text"]));
    }
    for case in g["windows_run_commands"].as_array().unwrap() {
        let m = manager(s(&case["executable"]), Platform::Windows);
        assert_eq!(m.windows_run_command(), s(&case["command"]));
    }
}

#[test]
fn activation_tokens_and_handoff() {
    let g = golden("activation.json");
    for case in g["tokens"].as_array().unwrap() {
        let req =
            ActivationRequest::new(s(&case["kind"]), opt(&case["alert_id"]).map(String::from))
                .unwrap();
        assert_eq!(req.to_token(), s(&case["token"]));
        assert_eq!(req.to_json(), s(&case["handoff"]));
        assert_eq!(
            ActivationRequest::from_json(s(&case["handoff"])),
            Some(req.clone())
        );
        assert_eq!(ActivationRequest::from_argv(&[req.to_token()]), Some(req));
    }
    for case in g["argv"].as_array().unwrap() {
        let argv: Vec<String> = serde_json::from_value(case["argv"].clone()).unwrap();
        let got = ActivationRequest::from_argv(&argv)
            .map(|r| json!({"kind": r.kind.as_str(), "alert_id": r.alert_id}));
        assert_eq!(got.unwrap_or(Value::Null), case["request"], "{case}");
    }
    for case in g["window_titles"].as_array().unwrap() {
        assert_eq!(
            aw_services::single_instance::is_accessiweather_window_title(s(&case["title"])),
            case["match"].as_bool().unwrap(),
            "{case}"
        );
    }
}

fn location_state(config: &AppConfig) -> Value {
    Value::Array(
        config
            .locations
            .iter()
            .map(|l| json!({"name": l.name, "latitude": l.latitude, "longitude": l.longitude, "country_code": l.country_code}))
            .collect(),
    )
}

fn assert_json_eq(a: &Value, b: &Value, context: &str) {
    // Numbers compare by value (Python writes 40.0, serde may read 40).
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => assert_eq!(x.as_f64(), y.as_f64(), "{context}"),
        (Value::Array(x), Value::Array(y)) => {
            assert_eq!(x.len(), y.len(), "{context}: {a} vs {b}");
            for (x, y) in x.iter().zip(y) {
                assert_json_eq(x, y, context);
            }
        }
        (Value::Object(x), Value::Object(y)) => {
            let xk: Vec<_> = x.keys().collect();
            let mut yk: Vec<_> = y.keys().collect();
            let mut xs = xk.clone();
            xs.sort();
            yk.sort();
            assert_eq!(xs, yk, "{context}");
            for k in xk {
                assert_json_eq(&x[k], &y[k], &format!("{context}.{k}"));
            }
        }
        _ => assert_eq!(a, b, "{context}"),
    }
}

#[test]
fn settings_and_locations_export_documents() {
    let g = golden("import_export.json");
    let config = AppConfig::from_json(&g["config"].to_string()).unwrap();
    let mut doc = import_export::settings_export(&config, "now");
    assert_eq!(doc["exported_at"], "now");
    doc.as_object_mut().unwrap().remove("exported_at");
    assert_json_eq(&doc, &g["settings_export"], "settings export");
    let mut doc = import_export::locations_export(&config, "now");
    doc.as_object_mut().unwrap().remove("exported_at");
    assert_json_eq(&doc, &g["locations_export"], "locations export");
}

#[test]
fn imports_match_python() {
    let g = golden("import_export.json");
    let dir = tempfile::tempdir().unwrap();
    let config_file = dir.path().join("accessiweather.json");
    for method in ["import_locations", "import_settings"] {
        for (i, case) in g[method].as_array().unwrap().iter().enumerate() {
            let mut config = AppConfig::default();
            config
                .locations
                .push(Location::new("Existing Location", 30.0, -90.0));
            let path = dir.path().join(format!("{method}{i}.json"));
            let text = if case["input"] == "<invalid json>" {
                "invalid json content".to_string()
            } else {
                case["input"].to_string()
            };
            std::fs::write(&path, text).unwrap();
            let ok = if method == "import_locations" {
                import_export::import_locations(&mut config, &path, &config_file)
            } else {
                import_export::import_settings(&mut config, &path, &config_file)
            };
            let context = format!("{method} {}", case["input"]);
            assert_eq!(ok, case["result"].as_bool().unwrap(), "{context}");
            assert_json_eq(&location_state(&config), &case["locations"], &context);
            if let Some(expected) = case["settings"].as_object() {
                let settings = serde_json::to_value(&config.settings).unwrap();
                for (key, value) in expected {
                    assert_json_eq(&settings[key], value, &format!("{context} {key}"));
                }
            }
        }
    }
}

#[test]
fn portable_copy_checks() {
    let g = golden("portable_copy.json");
    let dir = tempfile::tempdir().unwrap();
    for case in g["precheck"].as_array().unwrap() {
        let installed = dir.path().join("installed").join(s(&case["installed"]));
        if let Some(files) = case["files"].as_object() {
            std::fs::create_dir_all(&installed).unwrap();
            for (name, content) in files {
                std::fs::write(installed.join(name), s(content)).unwrap();
            }
        }
        let got = import_export::check_installed_config(&installed);
        assert_eq!(got.is_ok(), case["ok"].as_bool().unwrap(), "{case}");
        assert_eq!(got.err(), opt(&case["reason"]), "{case}");
    }
    let installed = dir.path().join("installed").join("ok");
    for (i, case) in g["validation"].as_array().unwrap().iter().enumerate() {
        let portable = dir.path().join(format!("portable{i}"));
        std::fs::create_dir_all(&portable).unwrap();
        std::fs::write(
            portable.join("accessiweather.json"),
            case["portable"].to_string(),
        )
        .unwrap();
        let got = import_export::validate_portable_copy(&installed, &portable);
        assert_eq!(got.is_ok(), case["valid"].as_bool().unwrap(), "{case}");
        let messages = got.err().unwrap_or_default();
        assert_eq!(json!(messages), case["messages"], "{case}");
        let summary = import_export::portable_copy_summary(&portable).unwrap();
        assert_eq!(json!(summary), case["summary"], "{case}");
    }
    let copy_to = dir.path().join("copy");
    assert_eq!(
        import_export::copy_installed_config(&installed, &copy_to).unwrap(),
        ["accessiweather.json"]
    );
    assert!(import_export::validate_portable_copy(&installed, &copy_to).is_ok());
}

#[test]
fn report_issue_url_and_system_info() {
    let g = golden("report_issue.json");
    let info = &g["system_info"];
    let text = report_issue::format_system_info(
        s(&info["app_version"]),
        s(&info["os_system"]),
        s(&info["os_release"]),
        ("Python", s(&info["python"])),
    );
    assert_eq!(text, s(&info["text"]));
    assert_eq!(report_issue::ISSUE_URL, s(&g["issue_url"]));
    for case in g["urls"].as_array().unwrap() {
        let got = report_issue::build_issue_url(
            case["issue_type"].as_u64().unwrap() as usize,
            s(&case["title"]),
            s(&case["description"]),
            &text,
        );
        match got {
            Ok(url) => assert_eq!(url, s(&case["url"])),
            Err(message) => assert_eq!(
                case["message_box"],
                json!([report_issue::TITLE_REQUIRED_TITLE, message])
            ),
        }
    }
}

/// Plays a recorded scenario against the state machine, performing each
/// step the way its documentation says the UI must, and logs the same
/// events the Python fakes recorded.
struct Driver<'a> {
    scenario: &'a Value,
    portable: bool,
    script: Vec<Value>,
    events: Vec<Value>,
    locations: usize,
    keyring: BTreeMap<String, String>,
    memory: BTreeMap<String, String>,
    imported_this_session: bool,
}

impl<'a> Driver<'a> {
    fn new(scenario: &'a Value) -> Self {
        let keyring = scenario
            .get("keyring")
            .and_then(Value::as_object)
            .map(|m| {
                m.iter()
                    .map(|(k, v)| (k.clone(), s(v).to_string()))
                    .collect()
            })
            .unwrap_or_default();
        Self {
            scenario,
            portable: scenario["portable"].as_bool().unwrap(),
            script: scenario["script"].as_array().unwrap().clone(),
            events: Vec::new(),
            locations: 0,
            keyring,
            memory: BTreeMap::new(),
            imported_this_session: false,
        }
    }

    fn result(&self, name: &str) -> bool {
        self.scenario
            .get("results")
            .and_then(|r| r.get(name))
            .and_then(Value::as_bool)
            .unwrap_or(true)
    }

    fn has_key(&self, name: &str) -> bool {
        let store = if self.portable {
            &self.memory
        } else {
            &self.keyring
        };
        store.get(name).is_some_and(|v| !v.is_empty())
    }

    fn facts(&self) -> Facts {
        Facts {
            has_locations: self.locations > 0,
            keyring_available: self
                .scenario
                .get("keyring_available")
                .and_then(Value::as_bool)
                .unwrap_or(true),
            has_openrouter_key: self.has_key("openrouter_api_key"),
            has_pirate_weather_key: self.has_key("pirate_weather_api_key"),
            portable_keys_imported_this_session: self.imported_this_session,
        }
    }

    fn next_answer(&mut self) -> Value {
        assert!(!self.script.is_empty(), "script ran out: {:?}", self.events);
        self.script.remove(0)
    }

    fn perform(&mut self, step: Step) -> Response {
        match step {
            Step::Dialog(d) => {
                let labels = match d.buttons {
                    Buttons::Ok => json!([]),
                    Buttons::YesNo(a, b) => json!([a, b]),
                    Buttons::YesNoCancel(a, b, c) => json!([a, b, c]),
                };
                let icon = match d.icon {
                    Icon::Information => "information",
                    Icon::Warning => "warning",
                    Icon::Error => "error",
                };
                self.events
                    .push(json!(["dialog", d.title, d.message, labels, icon]));
                if d.buttons == Buttons::Ok {
                    return Response::Ok;
                }
                match s(&self.next_answer()) {
                    "yes" => Response::Yes,
                    "no" => Response::No,
                    _ => Response::Cancel,
                }
            }
            Step::Secret { title, message } => {
                self.events.push(json!(["text", title, message]));
                match self.next_answer() {
                    Value::Object(m) => Response::Text(s(&m["text"]).to_string()),
                    _ => Response::Cancel,
                }
            }
            Step::ChooseFile { title, wildcard } => {
                self.events.push(json!(["file", title, wildcard]));
                match self.next_answer() {
                    Value::Object(m) => Response::File(Some(PathBuf::from(s(&m["file"])))),
                    _ => Response::File(None),
                }
            }
            Step::AddLocation => {
                self.events.push(json!(["add_location"]));
                self.locations += 1;
                Response::Done
            }
            Step::ImportSettings(path) => {
                self.events
                    .push(json!(["import_settings", path.to_str().unwrap()]));
                let ok = self.result("import_settings");
                if ok && self.scenario.get("settings_adds_location").is_some() {
                    self.locations += 1;
                }
                Response::Success(ok)
            }
            Step::ImportApiKeys { path, passphrase } => {
                self.events.push(json!([
                    "import_api_keys",
                    path.to_str().unwrap(),
                    passphrase
                ]));
                let ok = self.result("import_api_keys");
                if ok {
                    if let Some(keys) = self.scenario.get("bundle_keys").and_then(Value::as_object)
                    {
                        for (k, v) in keys {
                            let store = if self.portable {
                                &mut self.memory
                            } else {
                                &mut self.keyring
                            };
                            store.insert(k.clone(), s(v).to_string());
                        }
                    }
                    if self.portable {
                        self.imported_this_session = true;
                        self.events.push(json!([
                            "set_password",
                            "portable_bundle_passphrase",
                            passphrase
                        ]));
                        self.keyring
                            .insert("portable_bundle_passphrase".into(), passphrase.clone());
                        self.events
                            .push(json!(["export", "<config>/api-keys.keys", passphrase]));
                    }
                }
                Response::Success(ok)
            }
            Step::OpenUrl(url) => {
                self.events.push(json!(["open_url", url]));
                Response::Done
            }
            Step::SaveApiKey { name, value } => {
                self.events.push(json!(["update_settings", {name: value}]));
                self.keyring.insert(name.into(), value);
                Response::Done
            }
            Step::OpenSettings { tab } => {
                self.events.push(json!(["open_settings", tab]));
                Response::Done
            }
            Step::WriteKeyBundle { keys, passphrase } => {
                for (k, v) in keys {
                    self.memory.insert(k.into(), v);
                }
                self.events
                    .push(json!(["export", "<config>/api-keys.keys", passphrase]));
                let ok = self.result("export");
                if ok {
                    self.imported_this_session = true;
                    self.events.push(json!([
                        "set_password",
                        "portable_bundle_passphrase",
                        passphrase
                    ]));
                }
                Response::Success(ok)
            }
            Step::Finished => unreachable!(),
        }
    }
}

#[test]
fn onboarding_scenarios_replay_like_python() {
    let g = golden("onboarding.json");
    for scenario in g["scenarios"].as_array().unwrap() {
        let mut driver = Driver::new(scenario);
        let mut wizard = Onboarding::new(driver.portable);
        let mut step = wizard.start(&driver.facts());
        while step != Step::Finished {
            let response = driver.perform(step);
            step = wizard.advance(response, &driver.facts());
        }
        driver
            .events
            .push(json!(["update_settings", {"onboarding_wizard_shown": true}]));
        driver.events.push(json!(["deferred_update_check"]));
        assert!(
            driver.script.is_empty(),
            "{}: unused answers",
            scenario["name"]
        );
        let expected = scenario["events"].as_array().unwrap();
        for (i, (got, want)) in driver.events.iter().zip(expected).enumerate() {
            assert_eq!(got, want, "{} event {i}", scenario["name"]);
        }
        assert_eq!(driver.events.len(), expected.len(), "{}", scenario["name"]);
    }
    for case in g["decisions"].as_array().unwrap() {
        assert_eq!(
            onboarding::should_show_onboarding(
                case["force_wizard"].as_bool().unwrap(),
                case["onboarding_wizard_shown"].as_bool().unwrap(),
                case["has_locations"].as_bool().unwrap(),
            ),
            case["show"].as_bool().unwrap(),
            "{case}"
        );
    }
    let hint = onboarding::portable_missing_keys_hint();
    for case in g["portable_hint"].as_array().unwrap() {
        let show = onboarding::should_show_portable_missing_keys_hint(
            case["portable"].as_bool().unwrap(),
            case["hint_shown"].as_bool().unwrap(),
            case["onboarding_will_show"].as_bool().unwrap(),
            case["bundle_exists"].as_bool().unwrap(),
            case["keys_imported_this_session"].as_bool().unwrap(),
        );
        assert_eq!(show, !case["dialog"].is_null(), "{case}");
        if show {
            let Buttons::YesNoCancel(a, b, c) = hint.buttons else {
                panic!()
            };
            assert_eq!(
                case["dialog"],
                json!([hint.title, hint.message, [a, b, c], "information"])
            );
        }
    }
}
