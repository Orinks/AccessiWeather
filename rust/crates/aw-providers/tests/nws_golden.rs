//! Golden parity tests for the NWS client: every file under
//! `testdata/golden/nws` (written by `tools/golden/nws.py`) holds the HTTP
//! responses the Python client was served, the requests it made and what it
//! returned. The Rust client is replayed against the same responses and must
//! make the same requests and produce the same model objects.

use std::collections::BTreeSet;
use std::fs;
use std::path::PathBuf;
use std::time::Duration;

use aw_core::model::{
    AviationData, CurrentConditions, Forecast, HourlyForecast, Location, MarineForecast,
    TextProduct, Timestamp, WeatherAlerts, WeatherData,
};
use aw_providers::http::{FixtureClient, HttpError, HttpRequest};
use aw_providers::nws::{
    self, AlertAggregator, AviationError, AviationOptions, NwsClient, TextProductError,
    TextProducts, ZoneFields,
};
use chrono::DateTime;
use serde::de::DeserializeOwned;
use serde::Serialize;
use serde_json::{json, Value};

fn golden_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../testdata/golden/nws")
}

fn ts(v: &Value) -> Timestamp {
    DateTime::parse_from_rfc3339(v.as_str().expect("timestamp string")).expect("RFC 3339")
}

fn typed<T: DeserializeOwned>(v: &Value) -> T {
    serde_json::from_value(v.clone())
        .unwrap_or_else(|e| panic!("golden does not fit the model: {e}\n{v}"))
}

/// Normalise `expected` through the Rust model, then compare as JSON.
fn same_as<T: Serialize + DeserializeOwned>(actual: &T, expected: &Value) -> Result<(), String> {
    let want = serde_json::to_value(typed::<T>(expected)).unwrap();
    let got = serde_json::to_value(actual).unwrap();
    first_difference("$", &got, &want).map_or(Ok(()), Err)
}

fn first_difference(path: &str, got: &Value, want: &Value) -> Option<String> {
    match (got, want) {
        (Value::Object(g), Value::Object(w)) => {
            let keys: BTreeSet<&String> = g.keys().chain(w.keys()).collect();
            keys.into_iter().find_map(|k| {
                let null = Value::Null;
                first_difference(
                    &format!("{path}.{k}"),
                    g.get(k).unwrap_or(&null),
                    w.get(k).unwrap_or(&null),
                )
            })
        }
        (Value::Array(g), Value::Array(w)) if g.len() == w.len() => g
            .iter()
            .zip(w)
            .enumerate()
            .find_map(|(i, (g, w))| first_difference(&format!("{path}[{i}]"), g, w)),
        _ if got == want => None,
        // The goldens freeze an aware UTC `now()`; the parsers stamp the
        // app's naive `datetime.now()`, so only the wall time can match.
        (Value::String(g), Value::String(w))
            if path.ends_with(".generated_at") && w.strip_suffix('Z') == Some(g.as_str()) =>
        {
            None
        }
        _ => Some(format!("{path}: got {got}, want {want}")),
    }
}

struct Scenario {
    name: String,
    doc: Value,
    http: FixtureClient,
}

impl Scenario {
    fn load(path: PathBuf) -> Self {
        let name = path.file_stem().unwrap().to_string_lossy().into_owned();
        let doc: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        let mut http = FixtureClient::new();
        for r in doc["responses"]
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or_default()
        {
            http = http.with_response(
                r["url"].as_str().unwrap(),
                r["status"].as_u64().unwrap() as u16,
                r["body"].as_str().unwrap(),
            );
        }
        Self { name, doc, http }
    }

    fn client(&self) -> NwsClient<'_> {
        let mut client = NwsClient::new(&self.http);
        client.retry_delay = Duration::ZERO;
        client.now = Some(ts(&self.doc["now"]));
        client
    }

    fn location(&self) -> Location {
        typed(&self.doc["location"])
    }

    fn result(&self) -> &Value {
        &self.doc["result"]
    }

    fn check_requests(&self, sort: bool) -> Result<(), String> {
        let Some(want) = self.doc.get("requests") else {
            return Ok(());
        };
        let mut want: Vec<HttpRequest> = typed(want);
        let mut got = self.http.sent_requests();
        if sort {
            let key = |r: &HttpRequest| format!("{r:?}");
            want.sort_by_key(key);
            got.sort_by_key(key);
        }
        if got == want {
            Ok(())
        } else {
            Err(format!("requests differ:\n got: {got:#?}\nwant: {want:#?}"))
        }
    }
}

fn http_error(result: Result<impl Serialize, HttpError>, expected: &Value) -> Result<(), String> {
    match (result, expected.get("error")) {
        (Err(HttpError::Status { status, .. }), Some(_)) if json!(status) == expected["status"] => {
            Ok(())
        }
        (Err(e), _) => Err(format!("unexpected error {e}, want {expected}")),
        (Ok(v), Some(_)) => Err(format!(
            "got {}, want error {expected}",
            serde_json::to_string(&v).unwrap()
        )),
        (Ok(_), None) => unreachable!("handled by callers"),
    }
}

fn run(s: &Scenario) -> Result<(), String> {
    let expected = s.result();
    let is_error = expected.get("error").is_some();
    let mut sort_requests = false;
    match s.doc["call"].as_str().unwrap() {
        "current_conditions" => {
            let mut location = s.location();
            let result = s.client().current_conditions(&mut location);
            match result {
                Ok(current) if !is_error => same_as(&current, expected)?,
                other => http_error(other, expected)?,
            }
            same_as(&location, &s.doc["location_after"])?;
        }
        "forecast_and_discussion" => {
            match s.client().forecast_and_discussion(&s.location(), None) {
                Ok(r) if !is_error => {
                    same_as(&r.forecast, &expected["forecast"])?;
                    same_as(&r.discussion, &expected["discussion"])?;
                    same_as(
                        &r.discussion_issuance_time,
                        &expected["discussion_issuance_time"],
                    )?;
                }
                other => http_error(other.map(|r| r.discussion), expected)?,
            }
        }
        "discussion_only" => {
            let (text, issued) = s
                .client()
                .discussion_only(&s.location())
                .map_err(|e| e.to_string())?;
            same_as(&text, &expected[0])?;
            same_as(&issued, &expected[1])?;
        }
        "hourly_forecast" => {
            let hourly = s
                .client()
                .hourly_forecast(&s.location(), None)
                .map_err(|e| e.to_string())?;
            same_as::<Option<HourlyForecast>>(&hourly, expected)?;
        }
        "alerts" => {
            let radius = s.doc["radius"].as_str().unwrap();
            let alerts = s
                .client()
                .alerts(&s.location(), radius)
                .map_err(|e| e.to_string())?;
            same_as::<WeatherAlerts>(&alerts, expected)?;
        }
        "cancel_references" => {
            same_as(&s.client().cancel_references(15), expected)?;
        }
        "all_data_parallel" => {
            sort_requests = true;
            let drift = std::sync::Arc::new(std::sync::Mutex::new(Vec::<Value>::new()));
            let sink_log = drift.clone();
            let mut client = s.client();
            client.zone_drift_sink = Some(std::sync::Arc::new(
                move |name: &str, fields: &ZoneFields| {
                    sink_log.lock().unwrap().push(json!([name, fields]));
                },
            ));
            let mut location = s.location();
            let data = client
                .all_data_parallel(&mut location, s.doc["radius"].as_str().unwrap())
                .map_err(|e| e.to_string())?;
            same_as::<Option<CurrentConditions>>(&data.current, &expected["current"])?;
            same_as::<Option<Forecast>>(&data.forecast, &expected["forecast"])?;
            same_as(&data.discussion, &expected["discussion"])?;
            same_as(
                &data.discussion_issuance_time,
                &expected["discussion_issuance_time"],
            )?;
            same_as(&data.alerts, &expected["alerts"])?;
            same_as(&data.hourly_forecast, &expected["hourly_forecast"])?;
            same_as(&location, &s.doc["location_after"])?;
            let drift = drift.lock().unwrap().clone();
            let want: Vec<Value> = typed::<Vec<(String, ZoneFields)>>(&s.doc["zone_drift"])
                .into_iter()
                .map(|(n, f)| json!([n, f]))
                .collect();
            if drift != want {
                return Err(format!("zone drift {drift:?}, want {want:?}"));
            }
        }
        "primary_station_info" => {
            let (id, name) = s.client().primary_station_info(&s.location());
            same_as(&id, &expected[0])?;
            same_as(&name, &expected[1])?;
        }
        "observation_station_ids_for_point" => {
            let ids = s.client().observation_station_ids_for_point(
                s.doc["latitude"].as_f64().unwrap(),
                s.doc["longitude"].as_f64().unwrap(),
                s.doc["limit"].as_u64().unwrap() as usize,
            );
            same_as(&ids, expected)?;
        }
        "text_product" => {
            let office = s.doc["office"].as_str();
            let result = s
                .client()
                .text_product(s.doc["product_type"].as_str().unwrap(), office);
            text_result(result, expected)?;
        }
        "text_product_history" => {
            let result = s.client().text_product_history(
                s.doc["product_type"].as_str().unwrap(),
                s.doc["office"].as_str(),
                s.doc["limit"].as_u64().unwrap() as u32,
                Some(ts(&s.doc["start"])),
                Some(ts(&s.doc["end"])),
            );
            same_as::<Vec<TextProduct>>(&result.map_err(|e| e.to_string())?, expected)?;
        }
        "daily_climate_report" => {
            let result = s.client().daily_climate_report(s.doc["station"].as_str());
            same_as::<Option<TextProduct>>(&result.map_err(|e| e.to_string())?, expected)?;
        }
        "daily_climate_locations" => same_as(&s.client().daily_climate_locations(), expected)?,
        "aviation_weather" => {
            let options = AviationOptions {
                include_sigmets: s.doc["include_sigmets"].as_bool().unwrap(),
                include_cwas: s.doc["include_cwas"].as_bool().unwrap(),
                ..Default::default()
            };
            let result = s.client().aviation_weather(
                s.doc["station"].as_str().unwrap(),
                &options,
                s.doc["avwx_api_key"].as_str().unwrap_or(""),
            );
            match (result, is_error) {
                (Ok(aviation), false) => same_as::<AviationData>(&aviation, expected)?,
                (Err(AviationError::Http(e)), true) => http_error(Err::<(), _>(e), expected)?,
                (Err(e), true) if json!(e.to_string()) == expected["message"] => {}
                (other, _) => return Err(format!("got {other:?}, want {expected}")),
            }
        }
        "enrich_with_aviation_data" => {
            let location = s.location();
            let mut data = WeatherData::new(location.clone());
            s.client()
                .enrich_with_aviation_data(&mut data, &location, "");
            same_as(&data.aviation, expected)?;
        }
        "enrich_with_marine_data" => {
            let location = s.location();
            let mut data = WeatherData::new(location.clone());
            data.alerts = typed(&s.doc["existing_alerts"]);
            s.client().enrich_with_marine_data(&mut data, &location);
            same_as::<Option<MarineForecast>>(&data.marine, &expected["marine"])?;
            same_as::<Option<WeatherAlerts>>(&data.alerts, &expected["alerts"])?;
        }
        "taf" => {
            for pair in expected["decoded"].as_array().unwrap() {
                same_as(&nws::decode_taf_text(pair[0].as_str().unwrap()), &pair[1])?;
            }
            for pair in expected["no_data"].as_array().unwrap() {
                same_as(
                    &nws::taf_indicates_no_data(pair[0].as_str().unwrap()),
                    &pair[1],
                )?;
            }
        }
        "zone_fields" => {
            for case in expected.as_array().unwrap() {
                let fresh = nws::extract_zone_fields(&case["properties"]);
                same_as(&fresh, &case["fields"])?;
                for pair in case["diffs"].as_array().unwrap() {
                    let stored: Location = typed(&pair[0]);
                    same_as(&nws::diff_zone_fields(&stored, &fresh), &pair[1])?;
                }
            }
        }
        "parsers" => {
            for pair in expected["current"].as_array().unwrap() {
                same_as(&nws::parsers::parse_current_conditions(&pair[0]), &pair[1])?;
            }
            let alerts = &expected["alerts"];
            let parsed = nws::parsers::parse_alerts(&alerts[0]).map_err(|e| e.to_string())?;
            same_as(&parsed, &alerts[1])?;
        }
        "aggregator" => {
            let mut merged = AlertAggregator::default()
                .aggregate_alerts(typed(&expected["nws"]), typed(&expected["secondary"]));
            for alert in &mut merged.alerts {
                alert.areas.sort();
            }
            same_as(&merged, &expected["merged"])?;
        }
        other => return Err(format!("unknown call {other}")),
    }
    s.check_requests(sort_requests)
}

fn text_result(
    result: Result<Option<TextProducts>, TextProductError>,
    expected: &Value,
) -> Result<(), String> {
    match (result, expected) {
        (Ok(None), Value::Null) => Ok(()),
        (Ok(Some(TextProducts::One(p))), Value::Object(_)) if expected.get("error").is_none() => {
            same_as(&p, expected)
        }
        (Ok(Some(TextProducts::Many(list))), Value::Array(_)) => same_as(&list, expected),
        (Err(TextProductError::Fetch(msg)), _) if expected["error"] == "TextProductFetchError" => {
            same_as(&msg, &expected["message"])
        }
        (Err(TextProductError::Other(_)), _)
            if expected["error"]
                .as_str()
                .is_some_and(|e| e != "TextProductFetchError") =>
        {
            Ok(())
        }
        (other, _) => Err(format!("got {other:?}, want {expected}")),
    }
}

#[test]
fn nws_matches_python_goldens() {
    let mut paths: Vec<PathBuf> = fs::read_dir(golden_dir())
        .expect("golden dir")
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|x| x == "json"))
        .collect();
    paths.sort();
    assert!(paths.len() > 40, "goldens missing: run tools/golden/nws.py");
    let failures: Vec<String> = paths
        .into_iter()
        .map(Scenario::load)
        .filter_map(|s| run(&s).err().map(|e| format!("{}: {e}", s.name)))
        .collect();
    assert!(
        failures.is_empty(),
        "{} golden mismatches:\n{}",
        failures.len(),
        failures.join("\n\n")
    );
}
