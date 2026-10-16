//! Golden parity tests for `aw_providers::products`: every case replays the
//! canned responses recorded by `rust/tools/golden/products.py`, then checks
//! the parsed result and the exact request URLs against what Python produced.

use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};

use aw_core::model::{Location, TextProduct, Timestamp};
use aw_providers::http::{HttpClient, HttpError};
use aw_providers::products::advanced::{self, LookupForm};
use aw_providers::products::iem::{AfosQuery, Iem, Order, DEFAULT_IEM_BASE_URL};
use aw_providers::products::national::{NationalDiscussion, NationalDiscussionService};
use aw_providers::products::nws_text::{NwsText, NWS_BASE_URL};
use aw_providers::products::py;
use aw_providers::products::surf::{
    fetch_openmeteo_marine_surf_conditions, format_openmeteo_marine_report,
    format_pirate_weather_beach_conditions, OPENMETEO_MARINE_BASE_URL,
};
use aw_providers::products::tabs::{self, LoaderKind, FORECASTER_TABS};
use aw_providers::products::{ForecastProductService, ProductError, ProductResult};
use chrono::{DateTime, NaiveDateTime, Utc};
use serde_json::{json, Value};

fn golden(name: &str) -> Value {
    let path = format!(
        "{}/../../testdata/golden/products/{name}.json",
        env!("CARGO_MANIFEST_DIR")
    );
    serde_json::from_str(&std::fs::read_to_string(path).expect("golden file")).expect("json")
}

/// Serves a case's canned responses by longest URL prefix and records requests.
struct GoldenClient {
    responses: Vec<Value>,
    requests: Mutex<Vec<String>>,
}

impl GoldenClient {
    fn new(case: &Value) -> Arc<Self> {
        Arc::new(Self {
            responses: case["responses"].as_array().cloned().unwrap_or_default(),
            requests: Mutex::new(Vec::new()),
        })
    }

    fn requests(&self) -> Vec<String> {
        self.requests.lock().unwrap().clone()
    }

    fn respond(&self, url: &str) -> Result<&Value, HttpError> {
        self.requests.lock().unwrap().push(url.to_string());
        let spec = self
            .responses
            .iter()
            .filter(|r| url.starts_with(r["url"].as_str().unwrap()))
            .max_by_key(|r| r["url"].as_str().unwrap().len())
            .ok_or_else(|| HttpError::MissingFixture(url.to_string()))?;
        if let Some(message) = spec.get("error").and_then(Value::as_str) {
            return Err(HttpError::Transport {
                url: url.into(),
                message: message.into(),
            });
        }
        let status = spec.get("status").and_then(Value::as_u64).unwrap_or(200) as u16;
        if status >= 400 {
            return Err(HttpError::Status {
                url: url.into(),
                status,
            });
        }
        Ok(spec)
    }
}

impl HttpClient for GoldenClient {
    fn get_json(&self, url: &str) -> Result<Value, HttpError> {
        let spec = self.respond(url)?;
        match spec.get("text").and_then(Value::as_str) {
            Some(text) => serde_json::from_str(text).map_err(|e| HttpError::Json {
                url: url.into(),
                message: e.to_string(),
            }),
            None => Ok(spec["json"].clone()),
        }
    }

    fn get_text(&self, url: &str) -> Result<String, HttpError> {
        let spec = self.respond(url)?;
        Ok(match spec.get("text").and_then(Value::as_str) {
            Some(text) => text.to_string(),
            None => spec["json"].to_string(),
        })
    }
}

fn ts(value: &Value) -> Option<Timestamp> {
    value
        .as_str()
        .map(|s| DateTime::parse_from_rfc3339(s).unwrap_or_else(|e| panic!("{s}: {e}")))
}

fn utc(value: &Value) -> Option<DateTime<Utc>> {
    ts(value).map(|t| t.with_timezone(&Utc))
}

fn opt_str(value: &Value) -> Option<String> {
    value.as_str().map(str::to_string)
}

fn opt_i64(value: &Value) -> Option<i64> {
    value.as_i64()
}

fn f(value: &Value) -> f64 {
    value.as_f64().unwrap()
}

fn location(value: &Value) -> Location {
    serde_json::from_value(value.clone()).unwrap()
}

fn naive_iso(naive: NaiveDateTime) -> String {
    let micros = naive.and_utc().timestamp_subsec_micros();
    let mut out = naive.format("%Y-%m-%dT%H:%M:%S").to_string();
    if micros != 0 {
        out.push_str(&format!(".{micros:06}"));
    }
    out
}

/// Serialise like the golden script; Python-naive times compare by wall time.
fn product_json(p: &TextProduct, expected: &Value) -> Value {
    let naive = expected["issuance_time"]
        .as_str()
        .is_some_and(|s| s.starts_with("naive:"));
    let issuance = p.issuance_time.as_ref().map(|t| {
        if naive {
            format!("naive:{}", naive_iso(t.naive_local()))
        } else {
            py::isoformat(t)
        }
    });
    json!({
        "product_type": p.product_type,
        "product_id": p.product_id,
        "cwa_office": p.cwa_office,
        "issuance_time": issuance,
        "product_text": p.product_text,
        "headline": p.headline,
    })
}

fn opt_product_json(p: Option<&TextProduct>, expected: &Value) -> Value {
    p.map_or(Value::Null, |p| product_json(p, expected))
}

fn products_json(products: &[TextProduct], expected: &Value) -> Value {
    Value::Array(
        products
            .iter()
            .enumerate()
            .map(|(i, p)| product_json(p, &expected[i]))
            .collect(),
    )
}

fn result_json(result: &ProductResult, expected: &Value) -> Value {
    match result {
        ProductResult::One(p) => json!({"one": opt_product_json(p.as_ref(), &expected["one"])}),
        ProductResult::Many(ps) => json!({"many": products_json(ps, &expected["many"])}),
    }
}

fn outcome<T>(result: Result<T, ProductError>, ok: impl FnOnce(&T) -> Value) -> Value {
    match result {
        Ok(value) => json!({ "ok": ok(&value) }),
        Err(err) => json!({ "error": err.0 }),
    }
}

fn check(case: &Value, actual: Value, requests: Vec<String>) {
    let name = case["name"].as_str().unwrap();
    assert_eq!(actual, case["expect"], "result mismatch for {name}");
    let expected: Vec<String> = serde_json::from_value(case["requests"].clone()).unwrap();
    assert_eq!(requests, expected, "request mismatch for {name}");
}

#[test]
fn iem_client_matches_python() {
    for case in golden("iem").as_array().unwrap() {
        let client = GoldenClient::new(case);
        let iem = Iem {
            http: client.as_ref(),
            base: DEFAULT_IEM_BASE_URL,
        };
        let call = &case["call"];
        let expected = &case["expect"]["ok"];
        let result = match call["fn"].as_str().unwrap() {
            "afos" => {
                let q = &call["query"];
                iem.afos_text(
                    call["pil"].as_str().unwrap(),
                    &AfosQuery {
                        limit: q["limit"].as_i64().unwrap(),
                        start: ts(&q["start"]),
                        end: ts(&q["end"]),
                        order: if q["order"] == "asc" {
                            Order::Asc
                        } else {
                            Order::Desc
                        },
                        center: opt_str(&q["center"]),
                        wmo_id: opt_str(&q["wmo_id"]),
                        matches: opt_str(&q["matches"]),
                        aviation_afd: q["aviation_afd"].as_bool().unwrap(),
                    },
                )
            }
            "spc_outlook" => iem.spc_outlook(
                f(&call["lat"]),
                f(&call["lon"]),
                call["day"].as_i64().unwrap(),
                call["current"].as_bool().unwrap(),
                ts(&call["valid_at"]).as_ref(),
                opt_i64(&call["max_items"]),
            ),
            "spc_mcds" => iem.spc_mcds(
                f(&call["lat"]),
                f(&call["lon"]),
                utc(&call["active_at"]),
                ts(&call["start"]).as_ref(),
                ts(&call["end"]).as_ref(),
                opt_i64(&call["max_items"]),
            ),
            "spc_watches" => iem.spc_watches(
                f(&call["lat"]),
                f(&call["lon"]),
                utc(&call["active_at"]).unwrap(),
                opt_i64(&call["max_items"]),
            ),
            "wpc_outlook" => iem.wpc_outlook(
                f(&call["lat"]),
                f(&call["lon"]),
                call["day"].as_i64().unwrap(),
                ts(&call["valid_at"]).as_ref(),
                utc(&call["now"]).unwrap(),
                call["limit"].as_i64().unwrap(),
                opt_i64(&call["max_items"]),
            ),
            "wpc_mpds" => iem.wpc_mpds(
                f(&call["lat"]),
                f(&call["lon"]),
                utc(&call["active_at"]),
                ts(&call["start"]).as_ref(),
                ts(&call["end"]).as_ref(),
                opt_i64(&call["max_items"]),
            ),
            other => panic!("unknown fn {other}"),
        };
        check(
            case,
            outcome(result, |p| product_json(p, expected)),
            client.requests(),
        );
    }
}

#[test]
fn nws_text_products_match_python() {
    for case in golden("nws").as_array().unwrap() {
        let client = GoldenClient::new(case);
        let nws = NwsText {
            http: client.as_ref(),
            base: NWS_BASE_URL,
        };
        let call = &case["call"];
        let expected = &case["expect"]["ok"];
        let office = call["office"].as_str();
        let actual = match call["fn"].as_str().unwrap() {
            "text_product" => outcome(
                nws.text_product(call["product_type"].as_str().unwrap(), office),
                |r| result_json(r, expected),
            ),
            "history" => outcome(
                nws.history(
                    call["product_type"].as_str().unwrap(),
                    office,
                    call["limit"].as_i64().unwrap(),
                    ts(&call["start"]).as_ref(),
                    ts(&call["end"]).as_ref(),
                ),
                |ps| products_json(ps, expected),
            ),
            "daily_climate_report" => {
                outcome(nws.daily_climate_report(call["station"].as_str()), |p| {
                    opt_product_json(p.as_ref(), expected)
                })
            }
            "daily_climate_locations" => json!({"ok": nws.daily_climate_locations()}),
            "observation_stations" => json!({"ok": nws.observation_station_ids_for_point(
                f(&call["lat"]),
                f(&call["lon"]),
                call["limit"].as_u64().unwrap() as usize,
            )}),
            "discussion" => {
                let (text, issued) = nws.discussion(&call["grid"]);
                json!({"ok": [text, issued.as_ref().map(py::isoformat)]})
            }
            other => panic!("unknown fn {other}"),
        };
        check(case, actual, client.requests());
    }
}

#[test]
fn surf_conditions_match_python() {
    for case in golden("surf").as_array().unwrap() {
        let client = GoldenClient::new(case);
        let call = &case["call"];
        let expected = &case["expect"]["ok"];
        let loc = location(&call["location"]);
        let now = ts(&call["now"]).unwrap();
        let product = match call["fn"].as_str().unwrap() {
            "marine_format" => format_openmeteo_marine_report(&call["data"], &loc, now),
            "marine_fetch" => fetch_openmeteo_marine_surf_conditions(
                client.as_ref(),
                OPENMETEO_MARINE_BASE_URL,
                &loc,
                now,
            ),
            "pirate" => format_pirate_weather_beach_conditions(&call["payload"], &loc, now),
            other => panic!("unknown fn {other}"),
        };
        check(
            case,
            json!({"ok": opt_product_json(product.as_ref(), expected)}),
            client.requests(),
        );
    }
}

fn group_json(group: &[NationalDiscussion]) -> Value {
    let mut map = serde_json::Map::new();
    for d in group {
        map.insert(d.key.into(), json!({"title": d.title, "text": d.text}));
    }
    Value::Object(map)
}

#[test]
fn national_discussions_match_python() {
    for case in golden("national").as_array().unwrap() {
        let client = GoldenClient::new(case);
        let mut service = NationalDiscussionService::new(client.clone());
        service.request_delay = std::time::Duration::ZERO;
        let result = service.fetch_all_discussions_at(false, utc(&case["call"]["now"]).unwrap());
        let actual = json!({"ok": {
            "wpc": group_json(&result.wpc),
            "spc": group_json(&result.spc),
            "qpf": group_json(&result.qpf),
            "nhc": group_json(&result.nhc),
            "cpc": group_json(&result.cpc),
        }});
        check(case, actual, client.requests());
        // A second call inside the TTL is served from the cache.
        assert_eq!(service.fetch_all_discussions_at(false, Utc::now()), result);
        assert_eq!(
            client.requests().len(),
            case["requests"].as_array().unwrap().len()
        );
    }
}

fn loader_kind_name(kind: LoaderKind) -> &'static str {
    match kind {
        LoaderKind::Current => "current",
        LoaderKind::SurfConditions => "surf_conditions",
        LoaderKind::DailyClimate => "daily_climate",
        LoaderKind::SpcOutlook => "spc_outlook",
        LoaderKind::SpcMcd => "spc_mcd",
        LoaderKind::SpcWatchesCurrent => "spc_watches_current",
        LoaderKind::WpcEro => "wpc_ero",
        LoaderKind::WpcMpd => "wpc_mpd",
    }
}

fn service_at(client: Arc<GoldenClient>, now: DateTime<Utc>) -> ForecastProductService {
    ForecastProductService::new(client).with_clock(move || now)
}

#[test]
fn forecaster_tabs_match_python() {
    let data = golden("tabs");

    let table: Vec<Value> = FORECASTER_TABS
        .iter()
        .map(|t| {
            json!({
                "product_type": t.product_type,
                "label": t.label,
                "loader_kind": loader_kind_name(t.loader_kind),
                "requires_cwa": t.requires_cwa,
            })
        })
        .collect();
    assert_eq!(Value::Array(table), data["forecaster_tabs"]);
    let national: Vec<Value> = tabs::NATIONAL_TABS
        .iter()
        .map(|(id, label)| json!([id, label]))
        .collect();
    assert_eq!(Value::Array(national), data["national_tabs"]);

    for plan in data["plans"].as_array().unwrap() {
        let loc = location(&plan["location"]);
        let (initial, pending) = tabs::forecaster_tabs(&loc);
        let actual: Vec<Value> = initial
            .iter()
            .map(|p| {
                json!({
                    "product_type": p.tab.product_type,
                    "label": p.tab.label,
                    "autoload": p.autoload,
                    "panel_cwa": p.panel_cwa,
                })
            })
            .collect();
        assert_eq!(Value::Array(actual), plan["tabs"], "{loc:?}");
        let pending: Vec<&str> = pending.iter().map(|t| t.product_type).collect();
        assert_eq!(json!(pending), plan["pending"]);
    }

    let now = DateTime::parse_from_rfc3339("2026-05-01T18:00:00Z")
        .unwrap()
        .with_timezone(&Utc);
    for case in data["loaders"].as_array().unwrap() {
        let client = GoldenClient::new(case);
        let service = service_at(client.clone(), now);
        let call = &case["call"];
        let loc = location(&call["location"]);
        let tab = FORECASTER_TABS
            .iter()
            .find(|t| t.product_type == call["product_type"])
            .unwrap();
        let expected = &case["expect"]["ok"];
        let actual = outcome(tabs::load_tab(&service, &loc, tab, None), |r| {
            result_json(r, expected)
        });
        check(case, actual, client.requests());
    }

    for entry in data["active"].as_array().unwrap() {
        let text = entry["text"].as_str().unwrap();
        let product = TextProduct {
            product_type: "X".into(),
            product_id: "X".into(),
            cwa_office: "IEM".into(),
            issuance_time: None,
            product_text: text.into(),
            headline: None,
        };
        assert_eq!(
            tabs::active_iem_product_or_none(product).is_some(),
            entry["active"].as_bool().unwrap(),
            "{text:?}"
        );
    }

    for entry in data["availability"].as_array().unwrap() {
        let types = entry["types"].as_array().unwrap();
        let index = entry["index"].as_u64().unwrap() as usize;
        assert_eq!(
            tabs::keeps_tab(
                types[index].as_str().unwrap(),
                entry["has_product"].as_bool().unwrap(),
                types.len()
            ),
            entry["kept"].as_bool().unwrap(),
            "{entry}"
        );
    }

    for (product_type, initial) in data["advanced_lookup_product"].as_object().unwrap() {
        assert_eq!(tabs::advanced_lookup_product_type(product_type), initial);
    }

    let formatting = &data["formatting"];
    for (product_type, name) in formatting["full_names"].as_object().unwrap() {
        assert_eq!(
            tabs::product_full_name(product_type),
            name.as_str(),
            "{product_type}"
        );
    }
    for entry in formatting["empty_copy"].as_array().unwrap() {
        assert_eq!(
            tabs::empty_copy(
                entry["product_type"].as_str().unwrap(),
                entry["cwa"].as_str()
            ),
            entry["text"].as_str().unwrap()
        );
    }
    for entry in formatting["intro"].as_array().unwrap() {
        assert_eq!(
            tabs::regional_product_intro(
                entry["product_type"].as_str().unwrap(),
                entry["cwa"].as_str()
            ),
            entry["text"].as_str().unwrap()
        );
    }
    assert_eq!(tabs::NO_CWA_COPY, formatting["no_cwa"]);
}

fn form(value: &Value) -> LookupForm {
    let s = |key: &str| value[key].as_str().unwrap().to_string();
    let parts = |key: &str| -> [String; 3] {
        let v: Vec<String> = serde_json::from_value(value[key].clone()).unwrap();
        [v[0].clone(), v[1].clone(), v[2].clone()]
    };
    LookupForm {
        product: s("product"),
        office_choice: s("office_choice"),
        custom_office: s("custom_office"),
        limit: s("limit"),
        source: s("source"),
        order: s("order"),
        aviation_afd: value["aviation_afd"].as_bool().unwrap(),
        center: s("center"),
        wmo_id: s("wmo_id"),
        start_parts: parts("start_parts"),
        end_parts: parts("end_parts"),
        start_text: s("start_text"),
        end_text: s("end_text"),
    }
}

fn ok_or_error(result: Result<Option<Timestamp>, String>) -> Value {
    match result {
        Ok(value) => json!({"ok": value.as_ref().map(py::isoformat)}),
        Err(message) => json!({"error": message}),
    }
}

#[test]
fn advanced_lookup_matches_python() {
    let data = golden("advanced");

    for case in data["lookups"].as_array().unwrap() {
        let client = GoldenClient::new(case);
        let call = &case["call"];
        let service = service_at(client.clone(), utc(&call["now"]).unwrap());
        let text = advanced::lookup(&service, &location(&call["location"]), &form(&call["form"]));
        check(case, json!({ "ok": text }), client.requests());
    }

    for entry in data["parse_optional_datetime"].as_array().unwrap() {
        let mut expected = entry.clone();
        expected.as_object_mut().unwrap().remove("input");
        let input = entry["input"].as_str().unwrap();
        assert_eq!(
            ok_or_error(advanced::parse_optional_datetime(input)),
            expected,
            "{input:?}"
        );
    }

    for entry in data["date_from_choice_parts"].as_array().unwrap() {
        let parts: Vec<String> = serde_json::from_value(entry["input"].clone()).unwrap();
        let mut expected = entry.clone();
        expected.as_object_mut().unwrap().remove("input");
        assert_eq!(
            ok_or_error(advanced::date_from_choice_parts(
                &parts[0], &parts[1], &parts[2]
            )),
            expected,
            "{parts:?}"
        );
    }

    for entry in data["outlook_days"].as_array().unwrap() {
        let input = entry["input"].as_str().unwrap();
        assert_eq!(
            json!(advanced::spc_outlook_day(input)),
            entry["spc"],
            "{input}"
        );
        assert_eq!(
            json!(advanced::wpc_outlook_day(input)),
            entry["wpc"],
            "{input}"
        );
    }

    for entry in data["parse_limit"].as_array().unwrap() {
        let input = entry["input"].as_str().unwrap();
        assert_eq!(
            json!(advanced::parse_limit(input)),
            entry["limit"],
            "{input:?}"
        );
    }

    for entry in data["validate"].as_array().unwrap() {
        let a = entry["args"].as_array().unwrap();
        let s = |i: usize| a[i].as_str().unwrap();
        assert_eq!(
            json!(advanced::validate_iem_afos_lookup(
                s(0),
                s(1),
                s(2),
                a[3].as_bool().unwrap(),
                s(4),
                s(5)
            )),
            entry["message"],
            "{a:?}"
        );
    }

    let presets = &data["date_presets"];
    let now = utc(&presets["now"]).unwrap();
    for entry in presets["ranges"].as_array().unwrap() {
        let (start, end) = advanced::date_range_for_preset(entry["preset"].as_str().unwrap(), now);
        assert_eq!(json!(start.as_ref().map(py::isoformat)), entry["start"]);
        assert_eq!(json!(end.as_ref().map(py::isoformat)), entry["end"]);
    }

    assert_eq!(json!(advanced::product_categories()), data["categories"]);
    let labels: BTreeMap<&str, Vec<&str>> = advanced::product_categories()
        .into_iter()
        .map(|c| (c, advanced::preset_labels_for_category(c)))
        .collect();
    let expected: BTreeMap<String, Vec<String>> =
        serde_json::from_value(data["labels_by_category"].clone()).unwrap();
    assert_eq!(json!(labels), json!(expected));

    for entry in data["preset_changes"].as_array().unwrap() {
        let label = entry["label"].as_str().unwrap();
        let change = advanced::apply_product_preset(label);
        let actual = json!({
            "label": label,
            "product": change.as_ref().map_or("", |c| c.product),
            "source_index": change.as_ref().and_then(|c| c.source_index),
            "office_choice": change.as_ref().and_then(|c| c.office_choice),
        });
        assert_eq!(&actual, entry, "{label}");
    }

    let formatted = advanced::format_products(
        "IEM",
        &[
            TextProduct {
                product_type: "SRF".into(),
                product_id: "srf-1".into(),
                cwa_office: "PHI".into(),
                issuance_time: ts(&json!("2026-06-07T10:00:00.000500+00:00")),
                product_text: "SURF".into(),
                headline: Some("Surf Zone Forecast".into()),
            },
            TextProduct {
                product_type: "AFDRAH".into(),
                product_id: "AFDRAH".into(),
                cwa_office: "IEM".into(),
                issuance_time: None,
                product_text: String::new(),
                headline: Some(String::new()),
            },
        ],
    );
    assert_eq!(formatted, data["format_products"]);
    assert_eq!(
        advanced::format_products("NWS", &[]),
        data["format_products_empty"]
    );
    assert_eq!(
        advanced::format_form_datetime(&ts(&json!("2026-07-04T08:00:00.000005-04:00")).unwrap()),
        data["form_datetime"]
    );
}

#[test]
fn python_helpers_match_python() {
    let data = golden("py");
    for entry in data["fromisoformat"].as_array().unwrap() {
        let input = entry["input"].as_str().unwrap();
        let actual = py::fromisoformat(input).map(|(naive, offset)| match offset {
            Some(offset) => py::isoformat(&naive.and_local_timezone(offset).unwrap()),
            None => format!("naive:{}", naive_iso(naive)),
        });
        assert_eq!(json!(actual), entry["ok"], "{input:?}");
    }
    for entry in data["float_repr"].as_array().unwrap() {
        assert_eq!(
            py::py_float(entry["value"].as_f64().unwrap()),
            entry["repr"].as_str().unwrap()
        );
    }
}
