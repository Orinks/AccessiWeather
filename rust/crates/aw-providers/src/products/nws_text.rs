//! NWS `/products` text-product fetchers. Port of the text-product half of
//! `weather_client_nws_forecast.py` (`get_nws_text_product`, history, daily
//! climate report helpers and the `get_nws_discussion` wrapper).

use std::collections::BTreeSet;

use aw_core::model::{TextProduct, Timestamp};
use serde_json::Value;

use super::py::{self, py_str, quote};
use super::{transport_message, ProductError, ProductResult};
use crate::http::{HttpClient, HttpError};

pub const NWS_BASE_URL: &str = "https://api.weather.gov";

/// NWS `/products` endpoints bound to an HTTP client and base URL.
pub struct NwsText<'a> {
    pub http: &'a dyn HttpClient,
    pub base: &'a str,
}

impl NwsText<'_> {
    /// Latest product of `product_type` for an office (`get_nws_text_product`).
    ///
    /// No office → `One(None)` without any request. SPS → every listed
    /// statement, newest first. Anything else → the newest listing entry, or
    /// `One(None)` when the listing is empty.
    pub fn text_product(
        &self,
        product_type: &str,
        cwa_office: Option<&str>,
    ) -> Result<ProductResult, ProductError> {
        let Some(office) = cwa_office.filter(|o| !o.is_empty()) else {
            return Ok(ProductResult::One(None));
        };
        let url = format!(
            "{}/products/types/{product_type}/locations/{office}",
            self.base
        );
        let listing = self
            .http
            .get_json(&url)
            .map_err(|err| listing_error(&err, product_type, "listing", office))?;
        let graph = graph(&listing);

        if product_type == "SPS" {
            let mut products = Vec::new();
            for entry in graph.iter().filter(|e| e.is_object()) {
                let fetched = self.product_by_id(product_type, office, entry);
                if let Some(product) = fetched.map_err(|err| match err {
                    FetchErr::Status(msg) => ProductError(msg),
                    FetchErr::Transport(msg) => ProductError(format!(
                        "Request failed fetching SPS product for {office}: {msg}"
                    )),
                })? {
                    products.push(product);
                }
            }
            sort_newest_first(&mut products);
            return Ok(ProductResult::Many(products));
        }

        // The API is usually newest-first but live listings can be out of
        // order, so pick by issuanceTime (first entry wins ties, like max()).
        let mut latest: Option<&Value> = None;
        for entry in graph.iter().filter(|e| e.is_object()) {
            if latest.is_none_or(|best| entry_time(entry) > entry_time(best)) {
                latest = Some(entry);
            }
        }
        let Some(latest) = latest else {
            return Ok(ProductResult::One(None));
        };
        self.product_by_id(product_type, office, latest)
            .map(ProductResult::One)
            .map_err(|err| match err {
                FetchErr::Status(msg) => ProductError(msg),
                FetchErr::Transport(msg) => ProductError(format!(
                    "Request failed fetching {product_type} product for {office}: {msg}"
                )),
            })
    }

    /// Product history for an office, newest first (`get_nws_text_product_history`).
    pub fn history(
        &self,
        product_type: &str,
        cwa_office: Option<&str>,
        limit: i64,
        start: Option<&Timestamp>,
        end: Option<&Timestamp>,
    ) -> Result<Vec<TextProduct>, ProductError> {
        let Some(office) = cwa_office.filter(|o| !o.is_empty()) else {
            return Ok(Vec::new());
        };
        let mut query = vec![
            ("location", office.to_string()),
            ("type", product_type.to_string()),
            ("limit", limit.to_string()),
        ];
        if let Some(start) = start {
            query.push(("start", py::isoformat(start)));
        }
        if let Some(end) = end {
            query.push(("end", py::isoformat(end)));
        }
        let encoded: Vec<String> = query
            .iter()
            .map(|(k, v)| format!("{}={}", quote(k, true), quote(v, true)))
            .collect();
        let url = format!("{}/products?{}", self.base, encoded.join("&"));
        let listing = self
            .http
            .get_json(&url)
            .map_err(|err| listing_error(&err, product_type, "history", office))?;

        let mut products = Vec::new();
        for entry in graph(&listing).iter().filter(|e| e.is_object()) {
            let fetched = self.product_by_id(product_type, office, entry);
            if let Some(product) = fetched.map_err(|err| match err {
                FetchErr::Status(msg) => ProductError(msg),
                FetchErr::Transport(msg) => ProductError(format!(
                    "Request failed fetching {product_type} history product for {office}: {msg}"
                )),
            })? {
                products.push(product);
            }
        }
        sort_newest_first(&mut products);
        Ok(products)
    }

    /// Latest daily climate report (CLI) for a climate station.
    pub fn daily_climate_report(
        &self,
        station_id: Option<&str>,
    ) -> Result<Option<TextProduct>, ProductError> {
        let station = normalize_climate_station(station_id);
        if station.is_empty() {
            return Ok(None);
        }
        Ok(self
            .history("CLI", Some(&station), 1, None, None)?
            .into_iter()
            .next())
    }

    /// Location identifiers that currently issue CLI products. Any failure
    /// yields an empty set.
    pub fn daily_climate_locations(&self) -> BTreeSet<String> {
        let url = format!("{}/products/types/CLI/locations", self.base);
        let Ok(body) = self.http.get_json(&url) else {
            return BTreeSet::new();
        };
        match body.get("locations") {
            Some(Value::Object(locations)) => locations
                .keys()
                .map(|station| station.trim().to_uppercase())
                .filter(|station| !station.is_empty())
                .collect(),
            _ => BTreeSet::new(),
        }
    }

    /// Nearby observation station identifiers for a point (at most `limit`).
    pub fn observation_station_ids_for_point(
        &self,
        latitude: f64,
        longitude: f64,
        limit: usize,
    ) -> Vec<String> {
        let point_url = format!("{}/points/{latitude:.4},{longitude:.4}", self.base);
        let Ok(point) = self.http.get_json(&point_url) else {
            return Vec::new();
        };
        let Some(stations_url) = point
            .get("properties")
            .and_then(|p| p.get("observationStations"))
            .and_then(Value::as_str)
            .filter(|u| !u.is_empty())
        else {
            return Vec::new();
        };
        let Ok(stations) = self.http.get_json(stations_url) else {
            return Vec::new();
        };
        let mut candidates: Vec<String> = Vec::new();
        let urls = stations
            .get("observationStations")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        for station_url in urls.iter().filter_map(Value::as_str) {
            let station_id = station_url
                .trim_end_matches('/')
                .rsplit('/')
                .next()
                .unwrap_or_default()
                .trim()
                .to_uppercase();
            if !station_id.is_empty() && !candidates.contains(&station_id) {
                candidates.push(station_id);
            }
            if candidates.len() >= limit {
                break;
            }
        }
        candidates
    }

    /// AFD text and issuance time for `/points` grid data (`get_nws_discussion`),
    /// with Python's fallback strings when no discussion can be read.
    pub fn discussion(&self, grid_data: &Value) -> (String, Option<Timestamp>) {
        let Some(forecast_url) = grid_data
            .get("properties")
            .and_then(|p| p.get("forecast"))
            .and_then(Value::as_str)
            .filter(|u| !u.is_empty())
        else {
            return ("Forecast discussion not available.".into(), None);
        };
        let parts: Vec<&str> = forecast_url.split('/').collect();
        if parts.len() < 6 {
            return ("Forecast discussion not available.".into(), None);
        }
        let office = parts[parts.len() - 3];
        match self.text_product("AFD", Some(office)) {
            Err(_) => ("Forecast discussion not available.".into(), None),
            Ok(result) => match result.first() {
                None => (
                    "Forecast discussion not available for this location.".into(),
                    None,
                ),
                Some(product) => (product.product_text.clone(), product.issuance_time),
            },
        }
    }

    fn product_by_id(
        &self,
        product_type: &str,
        office: &str,
        entry: &Value,
    ) -> Result<Option<TextProduct>, FetchErr> {
        let Some(id) = entry.get("id").filter(|v| py::truthy(v)) else {
            tracing::warn!("No product ID in {product_type} @graph entry for office {office}");
            return Ok(None);
        };
        let product_id = py_str(id);
        let url = format!("{}/products/{product_id}", self.base);
        let data = self.http.get_json(&url).map_err(|err| match err {
            HttpError::Status { status, .. } => FetchErr::Status(format!(
                "HTTP {status} fetching {product_type} product {product_id}"
            )),
            other => FetchErr::Transport(transport_message(&other)),
        })?;
        let Some(text) = data
            .get("productText")
            .filter(|v| py::truthy(v))
            .map(py_str)
        else {
            tracing::warn!("No productText in {product_type} product {product_id}");
            return Ok(None);
        };
        let issuance_time = data
            .get("issuanceTime")
            .and_then(parse_iso_datetime)
            .or_else(|| entry.get("issuanceTime").and_then(parse_iso_datetime));
        let headline = data
            .get("headline")
            .filter(|v| py::truthy(v))
            .or_else(|| entry.get("headline"))
            .filter(|v| !v.is_null())
            .map(py_str);
        Ok(Some(TextProduct {
            product_type: product_type.to_string(),
            product_id,
            cwa_office: office.to_string(),
            issuance_time,
            product_text: text,
            headline,
        }))
    }
}

enum FetchErr {
    Status(String),
    Transport(String),
}

fn listing_error(err: &HttpError, product_type: &str, what: &str, office: &str) -> ProductError {
    match err {
        HttpError::Status { status, .. } => ProductError(format!(
            "HTTP {status} fetching {product_type} {what} for {office}"
        )),
        other => ProductError(format!(
            "Request failed fetching {product_type} {what} for {office}: {}",
            transport_message(other)
        )),
    }
}

fn graph(listing: &Value) -> Vec<Value> {
    listing
        .get("@graph")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
}

fn entry_time(entry: &Value) -> Option<Timestamp> {
    entry.get("issuanceTime").and_then(parse_iso_datetime)
}

/// Newest first; undated products sort last. Stable, like Python's sort.
fn sort_newest_first(products: &mut [TextProduct]) {
    products.sort_by_key(|p| std::cmp::Reverse(p.issuance_time));
}

/// `_parse_iso_datetime`: ISO strings only, naive values taken as UTC.
fn parse_iso_datetime(value: &Value) -> Option<Timestamp> {
    let text = value.as_str()?.trim();
    if text.is_empty() {
        return None;
    }
    py::parse_iso_utc(text)
}

/// CLI stations drop the ICAO `K` prefix: `KRDU` → `RDU`.
pub fn normalize_climate_station(station_id: Option<&str>) -> String {
    let station = station_id.unwrap_or_default().trim().to_uppercase();
    if station.starts_with('K') && station.chars().count() == 4 {
        station[1..].to_string()
    } else {
        station
    }
}
