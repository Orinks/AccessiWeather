//! Aviation products: TAFs (NWS, then aviationweather.gov), SIGMETs,
//! Center Weather Advisories and marine zone forecasts
//! (`weather_client_nws_aviation.py`) and `get_aviation_weather`
//! (`weather_client_aviation.py`).

use std::collections::BTreeSet;

use aw_core::model::AviationData;
use serde_json::Value;

use super::avwx::{fetch_avwx_taf, is_us_station};
use super::common::{get_truthy, py_str};
use super::taf::decode_taf_text;
use super::NwsClient;
use crate::http::HttpError;

/// aviationweather.gov's JSON TAF feed, the fallback when NWS has no TAF.
pub const AWC_TAF_URL: &str = "https://aviationweather.gov/api/data/taf";

#[derive(Debug, Clone, thiserror::Error)]
pub enum AviationError {
    #[error("station_id must be a non-empty ICAO identifier.")]
    EmptyStation,
    #[error(transparent)]
    Http(#[from] HttpError),
}

/// Optional extras for [`NwsClient::aviation_weather`]
/// (`include_sigmets`, `atsu`, `include_cwas`, `cwsu_id`).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct AviationOptions {
    pub include_sigmets: bool,
    pub atsu: Option<String>,
    pub include_cwas: bool,
    pub cwsu_id: Option<String>,
}

/// `_normalize_token`.
fn normalize_token(value: Option<&Value>) -> Option<String> {
    let token = match value? {
        Value::Null => return None,
        v => py_str(v).trim().to_uppercase(),
    };
    (!token.is_empty()).then_some(token)
}

fn normalize_str(value: Option<&str>) -> Option<String> {
    normalize_token(value.map(|s| Value::String(s.to_string())).as_ref())
}

/// `_taf_indicates_no_data`: a NIL / "NO TAF" / "NO DATA" report.
pub fn taf_indicates_no_data(raw_taf: &str) -> bool {
    if raw_taf.is_empty() {
        return true;
    }
    let tokens: Vec<String> = raw_taf
        .split_whitespace()
        .map(|t| t.trim_end_matches('=').to_uppercase())
        .collect();
    let mut i = 0;
    while i < tokens.len() && matches!(tokens[i].as_str(), "TAF" | "AMD" | "COR") {
        i += 1;
    }
    if tokens
        .get(i)
        .is_some_and(|t| t.chars().count() == 4 && t.chars().all(char::is_alphabetic))
    {
        i += 1;
    }
    if tokens
        .get(i)
        .is_some_and(|t| t.ends_with('Z') && t.chars().count() == 7)
    {
        i += 1;
    }
    if tokens.get(i).is_some_and(|t| t.matches('/').count() == 1) {
        i += 1;
    }
    if tokens.get(i).is_some_and(|t| t == "NIL") {
        return true;
    }
    let remaining = tokens.get(i..).unwrap_or_default().join(" ");
    remaining.contains("NO TAF") || remaining.contains("NO DATA")
}

/// `_extract_strings`: every string inside a value, trimmed and upper-cased.
fn extract_strings(value: &Value, out: &mut Vec<String>) {
    match value {
        Value::Null => {}
        Value::String(s) => {
            let s = s.trim().to_uppercase();
            if !s.is_empty() {
                out.push(s);
            }
        }
        Value::Array(items) => items.iter().for_each(|v| extract_strings(v, out)),
        Value::Object(map) => map.values().for_each(|v| extract_strings(v, out)),
        other => extract_strings(&Value::String(py_str(other)), out),
    }
}

/// `_filter_advisories`: advisories mentioning any of `tokens`.
pub fn filter_advisories(entries: Vec<Value>, tokens: &BTreeSet<String>) -> Vec<Value> {
    let tokens: Vec<&String> = tokens.iter().filter(|t| !t.is_empty()).collect();
    if entries.is_empty() || tokens.is_empty() {
        return entries;
    }
    const KEYS: [&str; 15] = [
        "fir",
        "area",
        "regions",
        "airspace",
        "name",
        "event",
        "hazard",
        "description",
        "summary",
        "text",
        "issuingOffice",
        "cwsu",
        "cwsuId",
        "stationId",
        "stations",
    ];
    entries
        .into_iter()
        .filter(|entry| {
            let mut candidates = Vec::new();
            for key in KEYS {
                if let Some(v) = entry.get(key) {
                    extract_strings(v, &mut candidates);
                }
            }
            if candidates.is_empty() {
                extract_strings(entry, &mut candidates);
            }
            tokens
                .iter()
                .any(|t| candidates.iter().any(|c| c.contains(t.as_str())))
        })
        .collect()
}

/// `_build_station_tokens`: words an advisory may use for this station.
fn station_tokens(
    station: &str,
    metadata: &Value,
    airport_name: Option<&str>,
    cwsu_id: Option<&str>,
) -> BTreeSet<String> {
    let mut tokens = BTreeSet::from([station.to_string()]);
    if let Some(cwsu) = normalize_str(cwsu_id).or_else(|| normalize_token(metadata.get("cwa"))) {
        tokens.insert(cwsu);
    }
    tokens.extend(normalize_token(metadata.get("wfo")));
    tokens.extend(normalize_token(metadata.get("state")));
    if let Some(name) = airport_name.filter(|n| !n.is_empty()) {
        for part in name.replace('-', " ").split_whitespace() {
            if let Some(t) = normalize_str(Some(part)).filter(|t| t.chars().count() > 2) {
                tokens.insert(t);
            }
        }
    }
    tokens
}

/// `features[*].properties` (or the feature itself) of an advisory listing.
fn feature_properties(data: &Value) -> Vec<Value> {
    data["features"]
        .as_array()
        .map(|features| {
            features
                .iter()
                .map(|f| f.get("properties").unwrap_or(f).clone())
                .collect()
        })
        .unwrap_or_default()
}

impl NwsClient<'_> {
    /// `get_nws_tafs`: the station's latest raw TAF from NWS, falling back to
    /// aviationweather.gov.
    pub fn tafs(&self, station_id: &str) -> Result<Option<String>, HttpError> {
        self.retry(|| self.tafs_once(station_id))
    }

    fn tafs_once(&self, station_id: &str) -> Result<Option<String>, HttpError> {
        let url = format!("{}/stations/{station_id}/tafs", self.base_url);
        match self
            .send(&self.request(url))
            .and_then(|r| r.error_for_status().cloned())
        {
            Ok(resp) => {
                if let Ok(Value::Object(data)) = resp.json() {
                    if let Some(Value::Array(features)) = data.get("features") {
                        for feature in features {
                            if !feature.is_object() {
                                return Err(HttpError::Json {
                                    url: resp.url.clone(),
                                    message: "TAF feature is not an object".into(),
                                });
                            }
                            let props = &feature["properties"];
                            let raw = get_truthy(props, "rawMessage")
                                .or_else(|| get_truthy(props, "rawTAF"));
                            if let Some(raw) = raw {
                                let raw = py_str(raw).trim().to_string();
                                if !raw.is_empty() {
                                    return Ok(Some(raw));
                                }
                            }
                        }
                    }
                }
                tracing::debug!(
                    "NWS TAF response for {station_id} did not include a raw message. Falling back to AviationWeather.gov."
                );
            }
            Err(e) => tracing::debug!("NWS TAF request failed for {station_id}: {e}"),
        }

        let req = self
            .request(AWC_TAF_URL)
            .header("Accept", "application/json")
            .param("ids", station_id)
            .param("format", "json");
        let resp = match self.send(&req).and_then(|r| r.error_for_status().cloned()) {
            Ok(resp) => resp,
            Err(e) => {
                tracing::error!("Failed to fetch TAF from AviationWeather for {station_id}: {e}");
                return if e.is_retryable() { Err(e) } else { Ok(None) };
            }
        };
        if resp.body.trim().is_empty() {
            tracing::debug!("AviationWeather returned empty response for {station_id}");
            return Ok(None);
        }
        let data = match resp.json() {
            Ok(data) => data,
            Err(e) => {
                let preview: String = resp.body.chars().take(200).collect();
                tracing::error!(
                    "Failed to decode AviationWeather TAF JSON for {station_id}: {e}. Response preview: {preview}"
                );
                return Ok(None);
            }
        };
        let entries: &[Value] = match &data {
            Value::Array(entries) => entries,
            Value::Object(_) => match ["data", "results", "tafs"]
                .iter()
                .find_map(|k| get_truthy(&data, k))
            {
                Some(Value::Array(entries)) => entries,
                _ => &[],
            },
            _ => &[],
        };
        for entry in entries.iter().filter(|e| e.is_object()) {
            if let Some(raw) = get_truthy(entry, "rawTAF").or_else(|| get_truthy(entry, "raw_taf"))
            {
                let cleaned = py_str(raw).trim().to_string();
                if !cleaned.is_empty() {
                    return Ok(Some(cleaned));
                }
            }
        }
        tracing::debug!("AviationWeather API returned no usable TAF data for {station_id}");
        Ok(None)
    }

    /// `get_nws_sigmets`: active SIGMET/AIRMET advisories, optionally for one ATSU.
    pub fn sigmets(&self, atsu: Option<&str>) -> Result<Vec<Value>, HttpError> {
        self.retry(|| {
            let mut req = self.request(format!("{}/aviation/sigmets", self.base_url));
            if let Some(atsu) = atsu.filter(|a| !a.is_empty()) {
                req = req.param("atsu", atsu);
            }
            self.advisories(&req, "Failed to fetch SIGMET data")
        })
    }

    /// `get_nws_cwas`: Center Weather Advisories for a CWSU.
    pub fn cwas(&self, cwsu_id: &str) -> Result<Vec<Value>, HttpError> {
        self.retry(|| {
            let req = self.request(format!("{}/aviation/cwsus/{cwsu_id}/cwas", self.base_url));
            self.advisories(&req, &format!("Failed to fetch CWA data for {cwsu_id}"))
        })
    }

    fn advisories(
        &self,
        req: &crate::http::HttpRequest,
        what: &str,
    ) -> Result<Vec<Value>, HttpError> {
        let resp = match self.send(req).and_then(|r| r.error_for_status().cloned()) {
            Ok(resp) => resp,
            Err(e) => {
                tracing::error!("{what}: {e}");
                return if e.is_retryable() {
                    Err(e)
                } else {
                    Ok(Vec::new())
                };
            }
        };
        // A body that is not JSON escapes as an error, as in Python.
        Ok(feature_properties(&resp.json()?))
    }

    /// `get_nws_marine_forecast`: the raw `/zones/{type}/{id}/forecast` document.
    pub fn marine_forecast(
        &self,
        zone_type: &str,
        zone_id: &str,
    ) -> Result<Option<Value>, HttpError> {
        self.retry(|| {
            let url = format!("{}/zones/{zone_type}/{zone_id}/forecast", self.base_url);
            let resp = match self
                .send(&self.request(url))
                .and_then(|r| r.error_for_status().cloned())
            {
                Ok(resp) => resp,
                Err(e) => {
                    tracing::error!(
                        "Failed to fetch marine forecast for {zone_type}/{zone_id}: {e}"
                    );
                    return if e.is_retryable() { Err(e) } else { Ok(None) };
                }
            };
            resp.json().map(Some)
        })
    }

    /// `get_aviation_weather`: TAF (decoded) plus optional advisories for an
    /// ICAO station. International stations go through AVWX first when an
    /// `avwx_api_key` is set, falling back to the NWS/AWC path.
    pub fn aviation_weather(
        &self,
        station_id: &str,
        options: &AviationOptions,
        avwx_api_key: &str,
    ) -> Result<AviationData, AviationError> {
        let station = station_id.trim().to_uppercase();
        if station.is_empty() {
            return Err(AviationError::EmptyStation);
        }
        if !is_us_station(&station) && !avwx_api_key.is_empty() {
            tracing::debug!("Routing international station {station} through AVWX");
            match fetch_avwx_taf(self.http, &station, avwx_api_key) {
                Ok(aviation) => return Ok(aviation),
                Err(e) => {
                    tracing::warn!(
                        "AVWX fetch failed for {station} ({e}); falling back to AWC path"
                    )
                }
            }
        }

        let mut aviation = AviationData {
            station_id: Some(station.clone()),
            airport_name: Some(station.clone()),
            ..Default::default()
        };
        let metadata = self.station_metadata(&station);
        let props = metadata
            .as_ref()
            .and_then(|m| m.get("properties"))
            .cloned()
            .unwrap_or(Value::Null);
        if let Some(name) = get_truthy(&props, "name") {
            aviation.airport_name = Some(py_str(name));
        }

        self.populate_taf(&mut aviation, &station)?;
        let tokens = station_tokens(
            &station,
            &props,
            aviation.airport_name.as_deref(),
            options.cwsu_id.as_deref(),
        );
        let sigmet_atsu = normalize_str(options.atsu.as_deref()).or_else(|| {
            matches!(
                normalize_token(props.get("country")).as_deref(),
                Some("US" | "USA")
            )
            .then(|| "KKCI".to_string())
        });

        if options.include_sigmets {
            match self.sigmets(sigmet_atsu.as_deref()) {
                Ok(sigmets) => aviation.active_sigmets = filter_advisories(sigmets, &tokens),
                Err(e) => tracing::debug!("Failed to fetch SIGMET data: {e}"),
            }
        }
        if options.include_cwas {
            match normalize_str(options.cwsu_id.as_deref())
                .or_else(|| normalize_token(props.get("cwa")))
            {
                None => aviation.active_cwas = Vec::new(),
                Some(cwsu) => match self.cwas(&cwsu) {
                    Ok(cwas) => aviation.active_cwas = filter_advisories(cwas, &tokens),
                    Err(e) => tracing::debug!("Failed to fetch CWA data for {cwsu}: {e}"),
                },
            }
        }
        Ok(aviation)
    }

    /// `_populate_taf`: NIL reports and undecodable TAFs clear the fields.
    fn populate_taf(&self, aviation: &mut AviationData, station: &str) -> Result<(), HttpError> {
        let raw = self.tafs(station).inspect_err(|e| {
            tracing::error!("Failed to fetch TAF for {station}: {e}");
        })?;
        let Some(raw) = raw.filter(|r| !r.is_empty()) else {
            return Ok(());
        };
        let cleaned = raw.trim();
        if cleaned.is_empty() || taf_indicates_no_data(cleaned) {
            aviation.raw_taf = None;
            aviation.decoded_taf = None;
            return Ok(());
        }
        let decoded = decode_taf_text(cleaned);
        if decoded.to_lowercase().starts_with("no taf available") {
            aviation.raw_taf = None;
            aviation.decoded_taf = None;
            return Ok(());
        }
        aviation.raw_taf = Some(cleaned.to_string());
        aviation.decoded_taf = Some(decoded);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn no_data_tafs_are_detected() {
        assert!(taf_indicates_no_data(""));
        assert!(taf_indicates_no_data("TAF KXYZ 121130Z NIL="));
        assert!(taf_indicates_no_data("TAF AMD KXYZ 121130Z 1212/1318 NIL"));
        assert!(taf_indicates_no_data("KXYZ NO TAF AVAILABLE"));
        assert!(!taf_indicates_no_data(
            "TAF KXYZ 121130Z 1212/1318 27015KT P6SM SKC"
        ));
    }

    #[test]
    fn advisories_filter_on_station_tokens() {
        let entries = vec![
            json!({"name": "SIGMET for ZNY", "hazard": "turbulence"}),
            json!({"text": "Chicago area"}),
            json!({"other": ["mentions kjfk here"]}),
        ];
        let tokens = BTreeSet::from(["ZNY".to_string(), "KJFK".to_string()]);
        let kept = filter_advisories(entries.clone(), &tokens);
        assert_eq!(kept, vec![entries[0].clone(), entries[2].clone()]);
        assert_eq!(
            filter_advisories(entries.clone(), &BTreeSet::new()),
            entries
        );
    }

    #[test]
    fn station_tokens_include_metadata_and_airport_words() {
        let meta = json!({"cwa": "zny", "wfo": "OKX", "state": "NY"});
        let tokens = station_tokens(
            "KJFK",
            &meta,
            Some("John F Kennedy-International Airport"),
            None,
        );
        let expected: BTreeSet<String> = [
            "KJFK",
            "ZNY",
            "OKX",
            "NY",
            "JOHN",
            "KENNEDY",
            "INTERNATIONAL",
            "AIRPORT",
        ]
        .iter()
        .map(|s| s.to_string())
        .collect();
        assert_eq!(tokens, expected);
    }
}
