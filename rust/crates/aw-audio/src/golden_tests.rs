//! Parity with the Python app: every expectation here comes from
//! `rust/tools/golden/audio.py` (files in `rust/testdata/golden/audio/`).

use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use serde_json::{json, Map, Value};

use crate::alert_sounds::get_candidate_sound_events;
use crate::community::{self, CommunityPack, CommunitySoundPackService};
use crate::events;
use crate::http::fake::FakeHttp;
use crate::installer::install_from_zip;
use crate::manager::{self, SoundPackWizard};
use crate::pack;
use crate::submission::{self, PackSubmissionService};

fn golden(name: &str) -> Value {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/golden/audio")
        .join(name);
    serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap()
}

fn s(v: &Value) -> &str {
    v.as_str().unwrap_or_else(|| panic!("not a string: {v}"))
}

fn materialize(root: &Path, tree: &Value) {
    for (rel, text) in tree.as_object().unwrap() {
        let path = root.join(rel);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, s(text)).unwrap();
    }
}

fn rel_name(path: &Path, root: &Path) -> String {
    let rel = path.strip_prefix(root).unwrap();
    rel.components()
        .map(|c| c.as_os_str().to_string_lossy().into_owned())
        .collect::<Vec<_>>()
        .join("/")
}

fn listing(root: &Path) -> Value {
    fn walk(root: &Path, dir: &Path, out: &mut BTreeMap<String, String>) {
        for entry in fs::read_dir(dir).unwrap().flatten() {
            let path = entry.path();
            if path.is_dir() {
                walk(root, &path, out);
            } else {
                let text = String::from_utf8_lossy(&fs::read(&path).unwrap()).into_owned();
                out.insert(rel_name(&path, root), text);
            }
        }
    }
    let mut out = BTreeMap::new();
    walk(root, root, &mut out);
    json!(out)
}

fn zip_listing(bytes: Vec<u8>) -> Value {
    let mut archive = zip::ZipArchive::new(std::io::Cursor::new(bytes)).unwrap();
    let mut out = BTreeMap::new();
    for i in 0..archive.len() {
        let mut file = archive.by_index(i).unwrap();
        let mut text = String::new();
        std::io::Read::read_to_string(&mut file, &mut text).unwrap();
        out.insert(file.name().to_string(), text);
    }
    json!(out)
}

fn write_zip(path: &Path, entries: &Value) {
    let mut w = zip::ZipWriter::new(fs::File::create(path).unwrap());
    for entry in entries.as_array().unwrap() {
        w.start_file(s(&entry[0]), zip::write::SimpleFileOptions::default())
            .unwrap();
        w.write_all(s(&entry[1]).as_bytes()).unwrap();
    }
    w.finish().unwrap();
}

fn strings(v: &Value) -> Vec<String> {
    v.as_array()
        .unwrap()
        .iter()
        .map(|x| s(x).to_string())
        .collect()
}

#[test]
fn sound_event_catalog() {
    let g = golden("events.json");
    assert_eq!(
        json!(events::DEFAULT_MUTED_SOUND_EVENTS),
        g["default_muted"]
    );
    let sections: Vec<Value> = events::SOUND_EVENT_SECTIONS
        .iter()
        .map(|(t, d, e)| {
            json!([
                t,
                d,
                e.iter().map(|(k, l)| json!([k, l])).collect::<Vec<_>>()
            ])
        })
        .collect();
    assert_eq!(json!(sections), g["sections"]);
    let mut legacy = events::LEGACY_SOUND_EVENT_KEYS.to_vec();
    legacy.sort();
    assert_eq!(json!(legacy), g["legacy_keys"]);
    let mut known: Vec<&str> = events::user_mutable_sound_events()
        .map(|(k, _)| k)
        .chain(events::LEGACY_SOUND_EVENT_KEYS.iter().copied())
        .collect();
    known.sort();
    known.dedup();
    assert_eq!(json!(known), g["known_keys"]);
    for key in &known {
        assert!(events::is_known_event(key));
    }
    let friendly: Vec<Value> = events::friendly_sound_event_choices()
        .into_iter()
        .map(|(l, k)| json!([l, k]))
        .collect();
    assert_eq!(json!(friendly), g["friendly_choices"]);
    for case in g["normalize"].as_array().unwrap() {
        let input = strings(&case[0]);
        assert_eq!(json!(events::normalize_muted_sound_events(&input)), case[1]);
    }
    for case in g["normalize_known"].as_array().unwrap() {
        let input = strings(&case[0]);
        assert_eq!(
            json!(events::normalize_known_muted_sound_events(&input)),
            case[1]
        );
    }
}

#[test]
fn pack_lookup_and_validation() {
    let g = golden("packs.json");
    for case in g["parse_sound_entry"].as_array().unwrap() {
        let volumes = case[2].as_object().unwrap();
        let (file, volume) = pack::parse_sound_entry(&case[0], s(&case[1]), volumes);
        assert_eq!(json!([file, volume]), case[3], "{case}");
    }

    let tmp = tempfile::tempdir().unwrap();
    let root = tmp.path();
    materialize(root, &g["fixture"]);
    let rel = |p: Option<PathBuf>| p.map(|p| rel_name(&p, root));

    for case in g["get_sound_entry"].as_array().unwrap() {
        let (path, volume) = pack::get_sound_entry(s(&case[0]), s(&case[1]), root);
        assert_eq!(json!([case[0], case[1], rel(path), volume]), *case);
    }
    for case in g["get_sound_entry_for_candidates"].as_array().unwrap() {
        let candidates = strings(&case[0]);
        let (path, volume) = pack::get_sound_entry_for_candidates(&candidates, s(&case[1]), root);
        if case[3].is_null() {
            // Python raised: nothing plays.
            assert_eq!(path, None, "{case}");
        } else {
            assert_eq!(json!([case[0], case[1], rel(path), volume]), *case);
        }
    }

    let mut available = pack::get_available_sound_packs(root);
    available.sort_by(|a, b| a.directory.cmp(&b.directory));
    let available: Vec<Value> = available
        .iter()
        .map(|p| json!({"directory": p.directory, "path": rel_name(&p.path, root), "data": p.data}))
        .collect();
    assert_eq!(json!(available), g["available"]);

    for (dir, expected) in g["specific_alert_sounds"].as_object().unwrap() {
        assert_eq!(
            json!(pack::sound_pack_uses_specific_alert_sounds(dir, root)),
            *expected,
            "{dir}"
        );
    }
    for (dir, expected) in g["validate"].as_object().unwrap() {
        let (ok, msg) = pack::validate_sound_pack(&root.join(dir));
        let expected_msg = s(&expected[1]);
        assert_eq!(json!(ok), expected[0], "{dir}");
        // JSON parser messages differ between Python and serde_json.
        match expected_msg.strip_prefix("Invalid JSON in pack.json: ") {
            Some(_) => assert!(
                msg.starts_with("Invalid JSON in pack.json: "),
                "{dir}: {msg}"
            ),
            None => assert_eq!(msg, expected_msg, "{dir}"),
        }
    }
}

#[test]
fn alert_sound_candidates() {
    for case in golden("alert_sounds.json").as_array().unwrap() {
        let spec = &case[0];
        let mut alert =
            aw_core::model::WeatherAlert::new(s(&spec["title"]), s(&spec["description"]));
        alert.severity = spec["severity"].as_str().unwrap_or_default().to_string();
        alert.event = spec["event"].as_str().map(str::to_string);
        alert.headline = spec
            .get("headline")
            .and_then(Value::as_str)
            .map(str::to_string);
        let candidates =
            get_candidate_sound_events(&alert, case[1].as_bool().unwrap(), case[2].as_str());
        assert_eq!(json!(candidates), case[3], "{case}");
    }
}

#[test]
fn zip_install() {
    let g = golden("installer.json");
    let tmp = tempfile::tempdir().unwrap();
    let packs = tmp.path().join("soundpacks");
    let zips = tmp.path().join("zips");
    fs::create_dir_all(&zips).unwrap();
    let path_type = if cfg!(windows) {
        "WindowsPath"
    } else {
        "PosixPath"
    };
    for case in g["cases"].as_array().unwrap() {
        let zip_path = zips.join(format!("{}.zip", s(&case[0])));
        if case[1].is_null() {
            fs::write(&zip_path, "not a zip").unwrap();
        } else {
            write_zip(&zip_path, &case[1]);
        }
        let (ok, msg) = install_from_zip(&packs, &zip_path, None);
        let expected = s(&case[3]).replace("WindowsPath", path_type);
        assert_eq!((json!(ok), msg), (case[2].clone(), expected));
    }
    assert_eq!(listing(&packs), g["tree"]);

    let missing = tmp.path().join("nope.zip");
    assert_eq!(
        install_from_zip(&packs, &missing, None),
        (false, format!("ZIP file not found: {}", missing.display()))
    );
}

#[test]
fn sound_pack_manager_and_wizard() {
    let g = golden("manager.json");
    let tmp = tempfile::tempdir().unwrap();
    let root = tmp.path();
    materialize(root, &g["fixture"]);

    let mut loaded = manager::load_sound_packs(root);
    let labels: Vec<String> = manager::sorted_by_name(&loaded)
        .iter()
        .map(|p| p.list_label())
        .collect();
    assert_eq!(json!(labels), g["pack_list"]);
    loaded.sort_by(|a, b| a.pack_id.cmp(&b.pack_id));
    let loaded_json: Vec<Value> = loaded
        .iter()
        .map(|p| {
            json!({"pack_id": p.pack_id, "name": p.name, "author": p.author,
                   "description": p.description, "sounds": p.sounds})
        })
        .collect();
    assert_eq!(json!(loaded_json), g["loaded"]);

    for info in &loaded {
        let expected = &g["details"][&info.pack_id];
        let sounds: Vec<Value> = manager::sound_list_items(info)
            .into_iter()
            .map(|i| json!([i.label, [i.key, i.file, i.volume]]))
            .collect();
        assert_eq!(json!(sounds), expected["sounds"], "{}", info.pack_id);
        let categories: Vec<Value> = events::user_mutable_sound_events()
            .map(|(key, _)| {
                let (file, pct, enabled) = manager::category_mapping(info, key);
                json!([key, file, pct, enabled])
            })
            .collect();
        assert_eq!(
            json!(categories),
            expected["categories"],
            "{}",
            info.pack_id
        );
    }

    let info = |id: &str| {
        manager::load_sound_packs(root)
            .into_iter()
            .find(|p| p.pack_id == id)
            .unwrap()
    };
    let pack_json = |id: &str| fs::read_to_string(root.join(id).join("pack.json")).unwrap();
    for step in g["steps"].as_array().unwrap() {
        let id = s(&step[1]);
        match s(&step[0]) {
            "set_volume" => {
                let volume = step[4].as_f64().unwrap();
                manager::set_sound_mapping(&info(id).path, s(&step[2]), s(&step[3]), volume)
                    .unwrap();
                assert_eq!(pack_json(id), s(&step[5]), "{step}");
            }
            "apply_mapping" => {
                let src = root.join("external").join(s(&step[3]));
                let volume = step[4].as_f64().unwrap();
                let msg = manager::apply_mapping(&info(id), s(&step[2]), &src, volume).unwrap();
                assert_eq!(msg, s(&step[5]));
                assert_eq!(pack_json(id), s(&step[6]), "{step}");
            }
            "remove_mapping" => {
                let key = manager::normalize_custom_key(s(&step[2]));
                let msg = if manager::remove_mapping(&info(id), &key).unwrap() {
                    format!("Removed mapping for '{key}'.")
                } else {
                    format!("No mapping exists for '{key}'.")
                };
                assert_eq!(msg, s(&step[3]));
                assert_eq!(pack_json(id), s(&step[4]), "{step}");
            }
            other => panic!("unknown step {other}"),
        }
    }

    for dup in g["duplicate"].as_array().unwrap() {
        let source = info("unicode");
        let new_id = manager::duplicate_pack(root, &source).unwrap();
        assert_eq!(new_id, s(&dup[0]));
        assert_eq!(format!("Created '{} (Copy)'.", source.name), s(&dup[1]));
        assert_eq!(listing(&root.join(&new_id)), dup[2]);
    }

    let export = root.join("export.zip");
    manager::export_pack(&info("unicode"), &export).unwrap();
    assert_eq!(zip_listing(fs::read(&export).unwrap()), g["export"]);

    for case in g["import"].as_array().unwrap() {
        let zip_path = root.join(format!("import_{}.zip", s(&case[0])));
        write_zip(&zip_path, &case[1]);
        let mut messages = Vec::new();
        let result = manager::import_pack(root, &zip_path, |name| {
            messages.push(format!(
                "A sound pack named '{name}' already exists. Overwrite?"
            ));
            true
        });
        match result {
            Ok(Some(p)) => messages.push(format!(
                "Sound pack '{}' imported successfully.",
                p.pack_name
            )),
            Ok(None) => {}
            Err(e) => messages.push(e.to_string()),
        }
        assert_eq!(json!(messages), case[2], "{}", case[0]);
    }
    for (dir, expected) in g["import_tree"].as_object().unwrap() {
        assert_eq!(listing(&root.join(dir)), *expected, "{dir}");
    }

    let src = root.join("wizard_src");
    fs::create_dir_all(&src).unwrap();
    fs::write(src.join("one.wav"), "1").unwrap();
    fs::write(src.join("two.ogg"), "2").unwrap();
    let state = &g["wizard"]["state"];
    for created in g["wizard"]["created"].as_array().unwrap() {
        let mut wizard = SoundPackWizard::new().unwrap();
        wizard.pack_name = s(&state["pack_name"]).into();
        wizard.author = s(&state["author"]).into();
        wizard.description = s(&state["description"]).into();
        wizard.selected_alert_keys = ["startup", "alert", "exit"].map(String::from).into();
        wizard.sound_mappings = vec![
            ("exit".into(), src.join("two.ogg")),
            ("startup".into(), src.join("one.wav")),
            ("alert".into(), src.join("gone.wav")),
            ("notify".into(), src.join("one.wav")),
        ];
        let pack_id = wizard.create_pack(root).unwrap();
        assert_eq!(pack_id, s(&created[0]));
        assert_eq!(
            format!("Sound pack '{}' created successfully!", wizard.pack_name),
            s(&created[1])
        );
        assert_eq!(listing(&root.join(&pack_id)), created[2]);
        assert_eq!(
            wizard.summary(),
            "Pack: My Cool-Pack! \u{e9}  |  Author: Unknown"
        );
        // A mapping counts as assigned even when its file has gone missing.
        assert_eq!(wizard.assigned_summary(), "Sounds assigned: 3 of 3");
        assert_eq!(wizard.test_all_files().len(), 3);
    }
}

fn fake_from_routes(routes: &Value) -> FakeHttp {
    routes
        .as_object()
        .unwrap()
        .iter()
        .fold(FakeHttp::default(), |fake, (url, route)| {
            fake.route(url, route[0].as_u64().unwrap() as u16, s(&route[1]))
        })
}

fn service(fake: &Arc<FakeHttp>) -> CommunitySoundPackService {
    CommunitySoundPackService::with_http(
        fake.clone(),
        community::COMMUNITY_REPO_OWNER,
        community::COMMUNITY_REPO_NAME,
    )
}

/// serde_json parses floats to within an ulp, so percentages get a tolerance.
fn assert_progress_eq(got: &[Value], expected: &Value) {
    let expected = expected.as_array().unwrap();
    assert_eq!(got.len(), expected.len(), "{got:?} vs {expected:?}");
    for (g, e) in got.iter().zip(expected) {
        assert!((g[0].as_f64().unwrap() - e[0].as_f64().unwrap()).abs() < 1e-9);
        assert_eq!((&g[1], &g[2]), (&e[1], &e[2]));
    }
}

fn pack_from(v: &Value) -> CommunityPack {
    let opt_s = |k: &str| v[k].as_str().map(str::to_string);
    CommunityPack {
        name: s(&v["name"]).into(),
        author: s(&v["author"]).into(),
        description: s(&v["description"]).into(),
        version: s(&v["version"]).into(),
        download_url: s(&v["download_url"]).into(),
        file_size: v["file_size"].as_i64(),
        repository_url: s(&v["repository_url"]).into(),
        release_tag: s(&v["release_tag"]).into(),
        download_count: v["download_count"].as_i64(),
        created_date: opt_s("created_date"),
        preview_image_url: opt_s("preview_image_url"),
        repo_path: opt_s("repo_path"),
        tree_sha: opt_s("tree_sha"),
        git_ref: opt_s("ref"),
    }
}

#[test]
fn community_packs() {
    let g = golden("community.json");
    let mut all = Vec::new();
    for name in ["index", "releases", "repo", "empty"] {
        let scenario = &g["scenarios"][name];
        let fake = Arc::new(fake_from_routes(&scenario["routes"]));
        let packs = service(&fake).fetch_available_packs(false).unwrap();
        assert_eq!(json!(packs), scenario["packs"], "{name}");
        assert_eq!(json!(fake.urls()), scenario["requests"], "{name}");
        for record in fake.log.lock().unwrap().iter() {
            assert_eq!(record.method, "GET");
            assert!(record
                .headers
                .contains(&("User-Agent", "AccessiWeather-CommunityPacks/1.0".into())));
        }
        all.extend(packs);
    }

    let display = &g["display"];
    let keys: Vec<String> = all.iter().map(CommunityPack::key).collect();
    assert_eq!(json!(keys), display["keys"]);
    let installable: Vec<bool> = all.iter().map(CommunityPack::installable).collect();
    assert_eq!(json!(installable), display["installable"]);
    for (filter, expected) in display["filters"].as_object().unwrap() {
        let mut labels: Vec<String> = community::filter_packs(&all, filter)
            .iter()
            .map(|p| p.list_label())
            .collect();
        if labels.is_empty() {
            labels.push("No packs found".into());
        }
        assert_eq!(json!(labels), *expected, "{filter:?}");
    }
    let details: Vec<[String; 5]> = all.iter().map(CommunityPack::detail_labels).collect();
    assert_eq!(json!(details), display["details"]);
    let strs: Vec<String> = all.iter().map(ToString::to_string).collect();
    assert_eq!(json!(strs), display["str"]);
    for case in g["progress_detail"].as_array().unwrap() {
        let detail =
            community::progress_detail(case[0].as_u64().unwrap(), case[1].as_u64().unwrap());
        assert_eq!(detail, s(&case[2]));
    }

    let downloads = &g["downloads"];
    let tmp = tempfile::tempdir().unwrap();
    let dest = tmp.path().join("_downloads");
    for case in downloads["cases"].as_array().unwrap() {
        let fake = Arc::new(fake_from_routes(&downloads["routes"]));
        let pack = pack_from(&case["pack"]);
        let mut progress = Vec::new();
        let result = service(&fake).download_pack(&pack, &dest, &mut |pct, done, total| {
            progress.push(json!([pct, done, total]));
            true
        });
        let result = match result {
            Ok(path) => {
                let bytes = fs::read(&path).unwrap();
                let content = if bytes.starts_with(b"PK") {
                    zip_listing(bytes)
                } else {
                    json!(String::from_utf8(bytes).unwrap())
                };
                json!({"file": path.file_name().unwrap().to_string_lossy(), "zip": content})
            }
            Err(e) => json!({"error": e.to_string()}),
        };
        assert_eq!(result, case["result"], "{}", pack.name);
        assert_progress_eq(&progress, &case["progress"]);
        assert_eq!(json!(fake.urls()), case["requests"], "{}", pack.name);
    }
    let mut leftovers: Vec<String> = fs::read_dir(&dest)
        .unwrap()
        .flatten()
        .map(|e| e.file_name().to_string_lossy().into_owned())
        .collect();
    leftovers.sort();
    assert_eq!(json!(leftovers), downloads["leftovers"]);
}

#[test]
fn pack_submission() {
    let g = golden("submission.json");
    for case in g["derive_pack_id"].as_array().unwrap() {
        let path = Path::new("/p").join(s(&case[0]));
        let id = submission::derive_pack_id(&path, case[1].as_object().unwrap());
        assert_eq!(id, s(&case[2]), "{case}");
    }
    for case in g["validate_backend_url"].as_array().unwrap() {
        let got = match submission::validate_backend_url(s(&case[0])) {
            Ok(url) => json!([case[0], true, url]),
            Err(e) => json!([case[0], false, e.0]),
        };
        assert_eq!(got, *case);
    }

    let tmp = tempfile::tempdir().unwrap();
    let good = tmp.path().join("my_pack");
    materialize(&good, &g["pack_tree"]);
    let bad = tmp.path().join("bad_pack");
    fs::create_dir_all(&bad).unwrap();
    fs::write(
        bad.join("pack.json"),
        r#"{"name": "Bad", "sounds": {"alert": "gone.wav"}}"#,
    )
    .unwrap();
    let mut meta = Map::new();
    meta.insert("name".into(), json!("My Pack"));
    meta.insert("author".into(), json!("Jane"));
    for case in g["submissions"].as_array().unwrap() {
        let body = match &case["body"] {
            Value::String(text) => text.clone(),
            other => serde_json::to_string(other).unwrap(),
        };
        let upload = format!("{}/upload-zip", submission::DEFAULT_BACKEND_URL);
        let fake = Arc::new(FakeHttp::default().route(
            &upload,
            case["status"].as_u64().unwrap() as u16,
            body,
        ));
        let path = if s(&case["case"]) == "invalid_pack" {
            &bad
        } else {
            &good
        };
        let service =
            PackSubmissionService::with_http(submission::DEFAULT_BACKEND_URL, fake.clone());
        let mut progress = Vec::new();
        let result = service.submit_pack(
            path,
            &meta,
            &mut |pct, status| {
                progress.push(json!([pct, status]));
                true
            },
            &AtomicBool::new(false),
        );
        let result = match result {
            Ok(url) => json!({ "url": url }),
            Err(e) => {
                json!({"error": e.to_string().replace(&path.display().to_string(), "<PACK>")})
            }
        };
        assert_eq!(result, case["result"], "{}", case["case"]);
        assert_eq!(json!(progress), case["progress"], "{}", case["case"]);
        let requests: Vec<Value> = fake
            .log
            .lock()
            .unwrap()
            .iter()
            .map(|r| {
                let (field, filename, bytes, content_type) = r.multipart.clone().unwrap();
                assert!(r.headers[0].1.starts_with("AccessiWeather/"));
                json!({"url": r.url, "method": r.method, "field": field, "filename": filename,
                       "content_type": content_type, "zip": zip_listing(bytes)})
            })
            .collect();
        assert_eq!(json!(requests), case["requests"], "{}", case["case"]);
    }
}

#[test]
fn default_pack_decodes_and_covers_every_event() {
    let dir = pack::repo_soundpacks_dir().join("default");
    let (ok, msg) = pack::validate_sound_pack(&dir);
    assert!(ok, "{msg}");
    let data = pack::read_json(&dir.join("pack.json")).unwrap();
    let sounds = data["sounds"].as_object().unwrap();
    for (key, _) in events::user_mutable_sound_events() {
        assert!(sounds.contains_key(key), "default pack lacks {key}");
    }
    for key in events::LEGACY_SOUND_EVENT_KEYS {
        assert!(sounds.contains_key(*key), "default pack lacks {key}");
    }
    let mut files: Vec<PathBuf> = fs::read_dir(&dir)
        .unwrap()
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|e| e != "json"))
        .collect();
    files.sort();
    assert!(files.len() >= 9);
    for file in files {
        let decoder = rodio::Decoder::try_from(fs::File::open(&file).unwrap())
            .unwrap_or_else(|e| panic!("{}: {e}", file.display()));
        assert!(decoder.count() > 0, "{} has no samples", file.display());
    }
}
