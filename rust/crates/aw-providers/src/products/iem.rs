//! IEM-backed NWS text products: AFOS archive text plus point-based SPC and
//! WPC summaries. Port of `iem_client.py`.

use aw_core::model::{TextProduct, Timestamp};
use chrono::{DateTime, Utc};
use serde_json::{Map, Value};

use super::py::{self, py_float, py_str, splitlines, with_params};
use super::{transport_message, ProductError};
use crate::http::{HttpClient, HttpError};

pub const DEFAULT_IEM_BASE_URL: &str = "https://mesonet.agron.iastate.edu";

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Hash)]
pub enum Order {
    Asc,
    #[default]
    Desc,
}

impl Order {
    pub fn as_str(self) -> &'static str {
        match self {
            Order::Asc => "asc",
            Order::Desc => "desc",
        }
    }
}

/// Filters for `/cgi-bin/afos/retrieve.py` (keyword arguments of
/// `fetch_iem_afos_text`).
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct AfosQuery {
    pub limit: i64,
    pub start: Option<Timestamp>,
    pub end: Option<Timestamp>,
    pub order: Order,
    pub center: Option<String>,
    pub wmo_id: Option<String>,
    pub matches: Option<String>,
    pub aviation_afd: bool,
}

impl Default for AfosQuery {
    fn default() -> Self {
        Self {
            limit: 1,
            start: None,
            end: None,
            order: Order::Desc,
            center: None,
            wmo_id: None,
            matches: None,
            aviation_afd: false,
        }
    }
}

/// IEM endpoints bound to an HTTP client and base URL.
pub struct Iem<'a> {
    pub http: &'a dyn HttpClient,
    pub base: &'a str,
}

fn non_empty(value: &Option<String>) -> Option<&str> {
    value.as_deref().filter(|v| !v.is_empty())
}

impl Iem<'_> {
    /// Raw NWS text by AWIPS/PIL (`fetch_iem_afos_text`).
    pub fn afos_text(&self, pil: &str, query: &AfosQuery) -> Result<TextProduct, ProductError> {
        let product_id = pil.trim().to_uppercase();
        if product_id.is_empty() {
            return Err(ProductError("A product ID is required.".into()));
        }
        let mut params = vec![
            ("pil", product_id.clone()),
            ("fmt", "text".to_string()),
            ("limit", query.limit.max(1).to_string()),
            ("order", query.order.as_str().to_string()),
        ];
        if let Some(start) = &query.start {
            params.push(("sdate", py::utc_z(start)));
        }
        if let Some(end) = &query.end {
            params.push(("edate", py::utc_z(end)));
        }
        if let Some(center) = non_empty(&query.center) {
            params.push(("center", center.trim().to_uppercase()));
        }
        if let Some(wmo_id) = non_empty(&query.wmo_id) {
            params.push(("ttaaii", wmo_id.trim().to_uppercase()));
        }
        if let Some(matches) = non_empty(&query.matches) {
            params.push(("matches", matches.trim().to_string()));
        }
        if query.aviation_afd {
            params.push(("aviation_afd", "1".to_string()));
        }
        let url = with_params(&format!("{}/cgi-bin/afos/retrieve.py", self.base), &params);
        let body = self.http.get_text(&url).map_err(|err| match err {
            HttpError::Status { status, .. } => {
                ProductError(format!("IEM AFOS returned HTTP {status} for {product_id}"))
            }
            other => ProductError(format!(
                "IEM AFOS request failed for {product_id}: {}",
                transport_message(&other)
            )),
        })?;
        let text = clean_iem_text(&body);
        if text.is_empty() {
            return Err(ProductError(format!(
                "IEM AFOS returned no text for {product_id}"
            )));
        }
        if is_iem_error_text(&text) {
            return Err(ProductError(splitlines(&text)[0].to_string()));
        }
        Ok(TextProduct {
            product_type: product_id.clone(),
            cwa_office: non_empty(&query.center)
                .unwrap_or("IEM")
                .trim()
                .to_uppercase(),
            headline: Some(format!("IEM AFOS {product_id}")),
            product_id,
            issuance_time: None,
            product_text: text,
        })
    }

    /// Point-based SPC convective outlook summary (`fetch_iem_spc_outlook`).
    pub fn spc_outlook(
        &self,
        latitude: f64,
        longitude: f64,
        day: i64,
        current: bool,
        valid_at: Option<&Timestamp>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let day = day.clamp(1, 8);
        let mut params = vec![
            ("lat", py_float(latitude)),
            ("lon", py_float(longitude)),
            ("day", day.to_string()),
            ("fmt", "json".to_string()),
            ("current", if current { "1" } else { "0" }.to_string()),
        ];
        if let Some(valid_at) = valid_at.filter(|_| !current) {
            params.push(("time", py::utc_z(valid_at)));
        }
        let data = self.json("spcoutlook.py", &params, "SPC outlook")?;
        let title = format!("SPC Day {day} Convective Outlook");
        let lines = summary_lines(
            &title,
            &data,
            &SummarySpec {
                item_keys: &["outlooks", "outlook", "features"],
                max_items,
                ..SummarySpec::default()
            },
        );
        Ok(TextProduct {
            product_type: "SPC_OUTLOOK".into(),
            product_id: format!("SPC_OUTLOOK_DAY{day}"),
            cwa_office: "SPC".into(),
            issuance_time: generated_at(&data),
            product_text: lines.join("\n"),
            headline: Some(title),
        })
    }

    /// SPC mesoscale discussions near a point (`fetch_iem_spc_mcds`).
    /// `active_at` is `None` for archive lookups (`active_only=False`).
    pub fn spc_mcds(
        &self,
        latitude: f64,
        longitude: f64,
        active_at: Option<DateTime<Utc>>,
        start: Option<&Timestamp>,
        end: Option<&Timestamp>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let params = point_params(latitude, longitude);
        let data = self.json("spcmcd.py", &params, "SPC MCD")?;
        let title = "SPC Mesoscale Discussions";
        let lines = summary_lines(
            title,
            &data,
            &SummarySpec {
                item_keys: &["mcds", "features"],
                active_at,
                start_keys: &["utc_issue", "product_issue", "issue", "valid"],
                end_keys: &["utc_expire", "product_expire", "expire", "expires"],
                window_start: start,
                window_end: end,
                window_keys: &["utc_issue", "product_issue", "issue", "valid"],
                max_items,
            },
        );
        Ok(structured("SPC_MCD", "SPC", title, lines))
    }

    /// SPC watches valid at `active_at` (`fetch_iem_spc_watches`).
    pub fn spc_watches(
        &self,
        latitude: f64,
        longitude: f64,
        active_at: DateTime<Utc>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let params = vec![
            ("lat", py_float(latitude)),
            ("lon", py_float(longitude)),
            ("ts", active_at.format("%Y%m%d%H%M").to_string()),
        ];
        let data = self.json("spcwatch.py", &params, "SPC watches")?;
        let title = "SPC Watches";
        let lines = watch_summary_lines(title, &data, active_at, max_items);
        Ok(structured("SPC_WATCHES", "SPC", title, lines))
    }

    /// WPC excessive rainfall outlook (`fetch_iem_wpc_outlook`). `valid_at`
    /// of `None` asks IEM for the current outlook, filtered at `now`.
    #[allow(clippy::too_many_arguments)]
    pub fn wpc_outlook(
        &self,
        latitude: f64,
        longitude: f64,
        day: i64,
        valid_at: Option<&Timestamp>,
        now: DateTime<Utc>,
        limit: i64,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let active_at = valid_at.map_or(now, |v| v.with_timezone(&Utc));
        let day = day.clamp(1, 8);
        let params = vec![
            ("lat", py_float(latitude)),
            ("lon", py_float(longitude)),
            ("day", day.to_string()),
            ("fmt", "json".to_string()),
            ("last", limit.max(1).to_string()),
            (
                "time",
                match valid_at {
                    None => "current".to_string(),
                    Some(_) => py::utc_z(&active_at.fixed_offset()),
                },
            ),
        ];
        let data = self.json("wpcoutlook.py", &params, "WPC outlook")?;
        let title = format!("WPC Day {day} Excessive Rainfall Outlook");
        let lines = wpc_outlook_summary_lines(&title, &data, active_at, max_items);
        Ok(TextProduct {
            product_type: "WPC_ERO".into(),
            product_id: format!("WPC_ERO_DAY{day}"),
            cwa_office: "WPC".into(),
            issuance_time: generated_at(&data),
            product_text: lines.join("\n"),
            headline: Some(title),
        })
    }

    /// WPC mesoscale precipitation discussions (`fetch_iem_wpc_mpds`).
    /// `active_at` is `None` for archive lookups (`active_only=False`).
    pub fn wpc_mpds(
        &self,
        latitude: f64,
        longitude: f64,
        active_at: Option<DateTime<Utc>>,
        start: Option<&Timestamp>,
        end: Option<&Timestamp>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let params = point_params(latitude, longitude);
        let data = self.json("wpcmpd.py", &params, "WPC MPD")?;
        let title = "WPC Mesoscale Precipitation Discussions";
        let lines = mpd_summary_lines(title, &data, active_at, start, end, max_items);
        Ok(structured("WPC_MPD", "WPC", title, lines))
    }

    fn json(
        &self,
        endpoint: &str,
        params: &[(&str, String)],
        label: &str,
    ) -> Result<Value, ProductError> {
        let url = with_params(&format!("{}/json/{endpoint}", self.base), params);
        self.http.get_json(&url).map_err(|err| match err {
            HttpError::Status { status, .. } => {
                ProductError(format!("IEM {label} returned HTTP {status}"))
            }
            // Python lets `response.json()` decode errors through unwrapped.
            HttpError::Json { message, .. } => ProductError(message),
            other => ProductError(format!(
                "IEM {label} request failed: {}",
                transport_message(&other)
            )),
        })
    }
}

fn point_params(latitude: f64, longitude: f64) -> Vec<(&'static str, String)> {
    vec![
        ("lat", py_float(latitude)),
        ("lon", py_float(longitude)),
        ("fmt", "json".to_string()),
    ]
}

fn structured(product_type: &str, center: &str, title: &str, lines: Vec<String>) -> TextProduct {
    TextProduct {
        product_type: product_type.into(),
        product_id: product_type.into(),
        cwa_office: center.into(),
        issuance_time: None,
        product_text: lines.join("\n"),
        headline: Some(title.into()),
    }
}

fn generated_at(data: &Value) -> Option<Timestamp> {
    parse_datetime(data.as_object()?.get("generated_at")?)
}

/// `_clean_iem_text`: drop control characters except line breaks and tabs.
pub fn clean_iem_text(value: &str) -> String {
    let kept: String = value
        .chars()
        .filter(|c| matches!(c, '\n' | '\r' | '\t') || *c as u32 >= 32)
        .collect();
    kept.trim().to_string()
}

/// IEM reports lookup errors inside a 200 text response.
fn is_iem_error_text(value: &str) -> bool {
    splitlines(value)
        .into_iter()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .is_some_and(|line| line.to_uppercase().starts_with("ERROR:"))
}

/// `_parse_datetime`: ISO strings only, naive values taken as UTC.
fn parse_datetime(value: &Value) -> Option<Timestamp> {
    let text = value.as_str()?.trim();
    if text.is_empty() {
        return None;
    }
    py::parse_iso_utc(text)
}

/// The dict an item's times are read from: its `properties`, else itself.
fn item_data(item: &Value) -> Option<&Map<String, Value>> {
    let map = item.as_object()?;
    Some(
        map.get("properties")
            .and_then(Value::as_object)
            .unwrap_or(map),
    )
}

fn item_datetime(item: &Map<String, Value>, keys: &[&str]) -> Option<DateTime<Utc>> {
    keys.iter()
        .find_map(|key| item.get(*key).and_then(parse_datetime))
        .map(|t| t.with_timezone(&Utc))
}

fn active_items(
    items: Vec<Value>,
    valid_at: DateTime<Utc>,
    start_keys: &[&str],
    end_keys: &[&str],
) -> Vec<Value> {
    items
        .into_iter()
        .filter(|item| match item_data(item) {
            None => true,
            Some(data) => {
                let starts = item_datetime(data, start_keys);
                let ends = item_datetime(data, end_keys);
                !(starts.is_some_and(|s| s > valid_at) || ends.is_some_and(|e| e <= valid_at))
            }
        })
        .collect()
}

fn items_in_time_window(
    items: Vec<Value>,
    start: Option<&Timestamp>,
    end: Option<&Timestamp>,
    time_keys: &[&str],
) -> Vec<Value> {
    if start.is_none() && end.is_none() {
        return items;
    }
    items
        .into_iter()
        .filter(|item| match item_data(item) {
            None => true,
            Some(data) => match item_datetime(data, time_keys) {
                None => false,
                Some(t) => start.is_none_or(|s| t >= *s) && end.is_none_or(|e| t < *e),
            },
        })
        .collect()
}

fn payload_items(payload: &Map<String, Value>, item_keys: &[&str]) -> Vec<Value> {
    for key in item_keys {
        match payload.get(*key) {
            Some(Value::Array(items)) => return items.clone(),
            Some(Value::Object(map)) if !map.is_empty() => return vec![Value::Object(map.clone())],
            _ => {}
        }
    }
    Vec::new()
}

fn limited_items(items: Vec<Value>, max_items: Option<i64>) -> (Vec<Value>, usize) {
    match max_items {
        Some(max) if max > 0 => {
            let max = max as usize;
            let omitted = items.len().saturating_sub(max);
            (items.into_iter().take(max).collect(), omitted)
        }
        _ => (items, 0),
    }
}

fn append_omitted_count(lines: &mut Vec<String>, omitted: usize) {
    if omitted > 0 {
        lines.push(format!(
            "{omitted} older matches omitted. Use Advanced Lookup for broader history."
        ));
    }
}

/// Append `label: value` for each present field (`value not in (None, "")`).
fn push_fields(lines: &mut Vec<String>, item: &Map<String, Value>, fields: &[(&str, &str)]) {
    for (label, key) in fields {
        match item.get(*key) {
            None | Some(Value::Null) => {}
            Some(Value::String(s)) if s.is_empty() => {}
            Some(value) => lines.push(format!("{label}: {}", py_str(value))),
        }
    }
}

fn generated_lines(lines: &mut Vec<String>, payload: &Map<String, Value>) {
    let generated = payload
        .get("generated_at")
        .filter(|v| py::truthy(v))
        .or_else(|| payload.get("generated"))
        .filter(|v| py::truthy(v));
    if let Some(generated) = generated {
        lines.push(format!("Generated: {}", py_str(generated)));
        lines.push(String::new());
    }
}

fn no_structured_data(title: &str) -> Vec<String> {
    vec![
        title.to_string(),
        String::new(),
        "No structured data returned.".into(),
    ]
}

fn only(title: &str, message: &str) -> Vec<String> {
    vec![title.to_string(), String::new(), message.to_string()]
}

#[derive(Default)]
struct SummarySpec<'a> {
    item_keys: &'a [&'a str],
    active_at: Option<DateTime<Utc>>,
    start_keys: &'a [&'a str],
    end_keys: &'a [&'a str],
    window_start: Option<&'a Timestamp>,
    window_end: Option<&'a Timestamp>,
    window_keys: &'a [&'a str],
    max_items: Option<i64>,
}

/// `_spc_summary_lines`.
fn summary_lines(title: &str, payload: &Value, spec: &SummarySpec) -> Vec<String> {
    let Some(payload) = payload.as_object() else {
        return no_structured_data(title);
    };
    let mut lines = vec![title.to_string(), String::new()];
    generated_lines(&mut lines, payload);

    let mut items = payload_items(payload, spec.item_keys);
    if !spec.window_keys.is_empty() {
        items = items_in_time_window(items, spec.window_start, spec.window_end, spec.window_keys);
    }
    let filters_active = !(spec.start_keys.is_empty() && spec.end_keys.is_empty());
    if let Some(active_at) = spec.active_at.filter(|_| filters_active) {
        items = active_items(items, active_at, spec.start_keys, spec.end_keys);
    }
    if items.is_empty() {
        lines.push(if spec.active_at.is_some() && filters_active {
            "No active point-based products were returned for this location.".into()
        } else {
            "No matching point-based products were returned for this location.".into()
        });
        return lines;
    }

    let (visible, omitted) = limited_items(items, spec.max_items);
    for (index, item) in visible.iter().enumerate() {
        let Some(item) = item.as_object() else {
            continue;
        };
        lines.push(format!("Product {}:", index + 1));
        push_fields(
            &mut lines,
            item,
            &[
                ("Number", "mdnum"),
                ("Category", "category"),
                ("Threshold", "threshold"),
                ("Valid", "valid"),
                ("Issued", "product_issue"),
                ("Concerning", "concerning"),
                ("Watch probability", "watch_prob"),
            ],
        );
        lines.push(String::new());
    }
    append_omitted_count(&mut lines, omitted);
    lines
}

/// `_spc_watch_summary_lines`.
fn watch_summary_lines(
    title: &str,
    payload: &Value,
    active_at: DateTime<Utc>,
    max_items: Option<i64>,
) -> Vec<String> {
    let Some(payload) = payload.as_object() else {
        return no_structured_data(title);
    };
    let features = match payload.get("features") {
        Some(Value::Array(features)) if !features.is_empty() => features.clone(),
        _ => return only(title, "No matching watches were returned."),
    };
    let features = active_items(
        features,
        active_at,
        &["issue", "utc_issue", "product_issue", "valid"],
        &["expire", "utc_expire", "product_expire", "expires"],
    );
    if features.is_empty() {
        return only(title, "No active watches were returned.");
    }

    let mut lines = vec![title.to_string(), String::new()];
    let (visible, omitted) = limited_items(features, max_items);
    for (index, feature) in visible.iter().enumerate() {
        let Some(props) = feature.get("properties").and_then(Value::as_object) else {
            continue;
        };
        lines.push(format!("Watch {}:", index + 1));
        push_fields(
            &mut lines,
            props,
            &[
                ("SEL", "sel"),
                ("Type", "type"),
                ("Number", "number"),
                ("Issued", "issue"),
                ("Expires", "expire"),
                ("PDS", "is_pds"),
                ("Max hail size", "max_hail_size"),
                ("Max wind gust knots", "max_wind_gust_knots"),
            ],
        );
        lines.push(String::new());
    }
    append_omitted_count(&mut lines, omitted);
    lines
}

/// `_wpc_outlook_summary_lines`.
fn wpc_outlook_summary_lines(
    title: &str,
    payload: &Value,
    active_at: DateTime<Utc>,
    max_items: Option<i64>,
) -> Vec<String> {
    let Some(payload) = payload.as_object() else {
        return no_structured_data(title);
    };
    let mut lines = vec![title.to_string(), String::new()];
    generated_lines(&mut lines, payload);

    let outlooks = payload_items(payload, &["outlooks", "outlook"]);
    if outlooks.is_empty() {
        return only(title, "No matching outlooks were returned.");
    }
    let outlooks = active_items(
        outlooks,
        active_at,
        &["utc_issue", "issue", "valid", "valid_begin"],
        &["utc_expire", "expire", "expires", "valid_end"],
    );
    if outlooks.is_empty() {
        return only(title, "No active outlooks were returned.");
    }

    let (visible, omitted) = limited_items(outlooks, max_items);
    for (index, outlook) in visible.iter().enumerate() {
        let Some(outlook) = outlook.as_object() else {
            continue;
        };
        lines.push(format!("Outlook {}:", index + 1));
        push_fields(
            &mut lines,
            outlook,
            &[
                ("Day", "day"),
                ("Category", "category"),
                ("Threshold", "threshold"),
                ("Product issued", "utc_product_issue"),
                ("Valid begins", "utc_issue"),
                ("Valid expires", "utc_expire"),
            ],
        );
        lines.push(String::new());
    }
    append_omitted_count(&mut lines, omitted);
    lines
}

/// `_wpc_mpd_summary_lines`.
fn mpd_summary_lines(
    title: &str,
    payload: &Value,
    active_at: Option<DateTime<Utc>>,
    window_start: Option<&Timestamp>,
    window_end: Option<&Timestamp>,
    max_items: Option<i64>,
) -> Vec<String> {
    let Some(payload) = payload.as_object() else {
        return no_structured_data(title);
    };
    let mpds = match payload.get("mpds") {
        Some(Value::Array(mpds)) if !mpds.is_empty() => mpds.clone(),
        _ => return only(title, "No matching discussions were returned."),
    };
    let mpds = items_in_time_window(
        mpds,
        window_start,
        window_end,
        &["utc_issue", "issue", "product_issue"],
    );
    if mpds.is_empty() {
        return only(title, "No matching discussions were returned.");
    }
    let mpds = match active_at {
        Some(active_at) => {
            let mpds = active_items(
                mpds,
                active_at,
                &["utc_issue", "issue", "product_issue"],
                &["utc_expire", "expire", "product_expire", "expires"],
            );
            if mpds.is_empty() {
                return only(title, "No active discussions were returned.");
            }
            mpds
        }
        None => mpds,
    };

    let mut lines = vec![title.to_string(), String::new()];
    let (visible, omitted) = limited_items(mpds, max_items);
    for (index, mpd) in visible.iter().enumerate() {
        let Some(mpd) = mpd.as_object() else {
            continue;
        };
        lines.push(format!("Discussion {}:", index + 1));
        push_fields(
            &mut lines,
            mpd,
            &[
                ("Number", "product_num"),
                ("Product ID", "product_id"),
                ("Issued", "utc_issue"),
                ("Expires", "utc_expire"),
                ("Concerning", "concerning"),
                ("Link", "product_href"),
            ],
        );
        lines.push(String::new());
    }
    append_omitted_count(&mut lines, omitted);
    lines
}
