//! Forecast, Area Forecast Discussion and other text products
//! (`weather_client_nws_forecast.py`).

use std::collections::BTreeSet;

use aw_core::model::{Forecast, Location, TextProduct, Timestamp};
use serde_json::Value;

use super::common::{get_truthy, parse_iso_datetime, py_str};
use super::parsers::parse_forecast;
use super::{or_fallback, NwsClient, FEATURE_FLAGS};
use crate::http::{HttpError, HttpRequest};

const DISCUSSION_UNAVAILABLE: &str = "Forecast discussion not available.";
const DISCUSSION_UNAVAILABLE_HERE: &str = "Forecast discussion not available for this location.";
const DISCUSSION_ERROR: &str = "Forecast discussion not available due to error.";

/// `(forecast, discussion, discussion_issuance_time)`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ForecastAndDiscussion {
    pub forecast: Option<Forecast>,
    pub discussion: Option<String>,
    pub discussion_issuance_time: Option<Timestamp>,
}

/// What `get_nws_text_product` returns for a CWA office: SPS listings are
/// lists, every other product type the newest single product.
#[derive(Debug, Clone, PartialEq)]
pub enum TextProducts {
    One(TextProduct),
    Many(Vec<TextProduct>),
}

#[derive(Debug, Clone, PartialEq, thiserror::Error)]
pub enum TextProductError {
    /// `TextProductFetchError`: network failure or a non-200 response.
    #[error("{0}")]
    Fetch(String),
    /// Anything else (e.g. an unparsable body), which Python lets escape.
    #[error("{0}")]
    Other(String),
}

impl TextProductError {
    fn from_http(e: HttpError, context: impl FnOnce() -> String) -> Self {
        match e {
            HttpError::Transport { .. } | HttpError::MissingFixture(_) => {
                TextProductError::Fetch(format!("{}: {e}", context()))
            }
            other => TextProductError::Other(other.to_string()),
        }
    }
}

fn newest_first(products: &mut [TextProduct]) {
    // Stable, so equal issuance times keep listing order (Python's
    // `sort(reverse=True)` does the same).
    products.sort_by_key(|p| std::cmp::Reverse(p.issuance_time));
}

impl NwsClient<'_> {
    /// `get_nws_forecast_and_discussion`. The forecast and discussion are
    /// independent: a failed forecast still returns the discussion.
    /// `grid_data` is a `/points` document already in hand.
    pub fn forecast_and_discussion(
        &self,
        location: &Location,
        grid_data: Option<&Value>,
    ) -> Result<ForecastAndDiscussion, HttpError> {
        self.retry(|| {
            let attempt = self.forecast_and_discussion_once(location, grid_data);
            or_fallback(
                attempt,
                ForecastAndDiscussion::default(),
                "Failed to get NWS forecast and discussion",
            )
        })
    }

    fn forecast_and_discussion_once(
        &self,
        location: &Location,
        grid_data: Option<&Value>,
    ) -> Result<ForecastAndDiscussion, HttpError> {
        let fetched;
        let grid = match grid_data {
            Some(g) => g,
            None => {
                fetched = self.fetch_json(&self.request(self.points_url(location)))?;
                &fetched
            }
        };

        let forecast = (|| -> Result<Forecast, HttpError> {
            let url = grid["properties"]["forecast"]
                .as_str()
                .ok_or(HttpError::Json {
                    url: String::new(),
                    message: "missing forecast URL".into(),
                })?;
            let req = self.request(url).header("Feature-Flags", FEATURE_FLAGS);
            Ok(parse_forecast(&self.fetch_json(&req)?, self.now()))
        })()
        .inspect_err(|e| {
            tracing::warn!("Forecast fetch failed (discussion will still be returned): {e}")
        })
        .ok();

        let (discussion, issuance) = self.discussion(grid);
        Ok(ForecastAndDiscussion {
            forecast,
            discussion: Some(discussion),
            discussion_issuance_time: issuance,
        })
    }

    /// `get_nws_discussion_only`: the AFD without the forecast request, for
    /// the notification path.
    pub fn discussion_only(
        &self,
        location: &Location,
    ) -> Result<(Option<String>, Option<Timestamp>), HttpError> {
        self.retry(|| {
            let attempt = self
                .fetch_json(&self.request(self.points_url(location)))
                .map(|grid| {
                    let (text, issued) = self.discussion(&grid);
                    (Some(text), issued)
                });
            or_fallback(attempt, (None, None), "Failed to fetch NWS discussion only")
        })
    }

    /// `get_nws_discussion`: the AFD text and issuance time for the office
    /// in a `/points` document, or a fallback sentence.
    pub fn discussion(&self, grid_data: &Value) -> (String, Option<Timestamp>) {
        let Some(forecast_url) = get_truthy(&grid_data["properties"], "forecast") else {
            tracing::warn!("No forecast URL found in grid data");
            return (DISCUSSION_UNAVAILABLE.into(), None);
        };
        let Some(forecast_url) = forecast_url.as_str() else {
            return (DISCUSSION_ERROR.into(), None);
        };
        let parts: Vec<&str> = forecast_url.split('/').collect();
        if parts.len() < 6 {
            tracing::warn!("Unexpected forecast URL format: {forecast_url}");
            return (DISCUSSION_UNAVAILABLE.into(), None);
        }
        let office = parts[parts.len() - 3];
        match self.text_product("AFD", Some(office)) {
            Ok(Some(TextProducts::One(product))) => (product.product_text, product.issuance_time),
            Ok(_) => {
                tracing::warn!("No AFD products found for office {office}");
                (DISCUSSION_UNAVAILABLE_HERE.into(), None)
            }
            Err(TextProductError::Fetch(e)) => {
                tracing::warn!("Failed to fetch AFD via text-product path: {e}");
                (DISCUSSION_UNAVAILABLE.into(), None)
            }
            Err(TextProductError::Other(e)) => {
                tracing::error!("Failed to get NWS discussion: {e}");
                (DISCUSSION_ERROR.into(), None)
            }
        }
    }

    /// `get_nws_text_product`: `None` without an office or when an AFD/HWO/
    /// SRF-style listing is empty; SPS always yields a (possibly empty) list.
    pub fn text_product(
        &self,
        product_type: &str,
        cwa_office: Option<&str>,
    ) -> Result<Option<TextProducts>, TextProductError> {
        let Some(office) = cwa_office.filter(|o| !o.is_empty()) else {
            return Ok(None);
        };
        let url = format!(
            "{}/products/types/{product_type}/locations/{office}",
            self.base_url
        );
        let graph = self.product_listing(
            &self.request(url),
            || format!("Request failed fetching {product_type} listing for {office}"),
            || format!("{product_type} listing for {office}"),
        )?;

        if product_type == "SPS" {
            let mut products = Vec::new();
            for entry in graph.iter().filter(|e| e.is_object()) {
                let product = self
                    .product_by_id(product_type, office, entry)
                    .map_err(|e| {
                        e.with_context(|| {
                            format!("Request failed fetching SPS product for {office}")
                        })
                    })?;
                products.extend(product);
            }
            newest_first(&mut products);
            return Ok(Some(TextProducts::Many(products)));
        }

        // Newest by issuanceTime; the first entry wins ties, like max().
        let mut latest: Option<(&Value, Option<Timestamp>)> = None;
        for entry in graph.iter().filter(|e| e.is_object()) {
            let issued = parse_iso_datetime(&entry["issuanceTime"]);
            if latest.as_ref().is_none_or(|(_, best)| issued > *best) {
                latest = Some((entry, issued));
            }
        }
        let Some((entry, _)) = latest else {
            return Ok(None);
        };
        let product = self
            .product_by_id(product_type, office, entry)
            .map_err(|e| {
                e.with_context(|| {
                    format!("Request failed fetching {product_type} product for {office}")
                })
            })?;
        Ok(product.map(TextProducts::One))
    }

    /// `get_nws_text_product_history`: newest-first products from
    /// `/products?location=..&type=..&limit=..[&start=..][&end=..]`.
    pub fn text_product_history(
        &self,
        product_type: &str,
        cwa_office: Option<&str>,
        limit: u32,
        start: Option<Timestamp>,
        end: Option<Timestamp>,
    ) -> Result<Vec<TextProduct>, TextProductError> {
        let Some(office) = cwa_office.filter(|o| !o.is_empty()) else {
            return Ok(Vec::new());
        };
        let mut query = url::form_urlencoded::Serializer::new(String::new());
        query
            .append_pair("location", office)
            .append_pair("type", product_type)
            .append_pair("limit", &limit.to_string());
        if let Some(start) = start {
            query.append_pair("start", &py_isoformat(start));
        }
        if let Some(end) = end {
            query.append_pair("end", &py_isoformat(end));
        }
        let url = format!("{}/products?{}", self.base_url, query.finish());
        let graph = self.product_listing(
            &self.request(url),
            || format!("Request failed fetching {product_type} history for {office}"),
            || format!("{product_type} history for {office}"),
        )?;

        let mut products = Vec::new();
        for entry in graph.iter().filter(|e| e.is_object()) {
            let product =
                self.product_by_id(product_type, office, entry)
                    .map_err(|e| {
                        e.with_context(|| {
                    format!("Request failed fetching {product_type} history product for {office}")
                })
                    })?;
            products.extend(product);
        }
        newest_first(&mut products);
        Ok(products)
    }

    /// `get_nws_daily_climate_report`: the latest CLI product for a climate
    /// station (a leading `K` on four-letter identifiers is dropped).
    pub fn daily_climate_report(
        &self,
        station_id: Option<&str>,
    ) -> Result<Option<TextProduct>, TextProductError> {
        let mut station = station_id.unwrap_or("").trim().to_uppercase();
        if station.starts_with('K') && station.chars().count() == 4 {
            station.remove(0);
        }
        if station.is_empty() {
            return Ok(None);
        }
        let products = self.text_product_history("CLI", Some(&station), 1, None, None)?;
        Ok(products.into_iter().next())
    }

    /// `get_nws_daily_climate_locations`: stations that publish CLI products.
    pub fn daily_climate_locations(&self) -> BTreeSet<String> {
        let url = format!("{}/products/types/CLI/locations", self.base_url);
        let Ok(resp) = self.send(&self.request(url)) else {
            return BTreeSet::new();
        };
        if resp.status != 200 {
            return BTreeSet::new();
        }
        let Ok(body) = resp.json() else {
            return BTreeSet::new();
        };
        match get_truthy(&body, "locations") {
            Some(Value::Object(locations)) => locations
                .keys()
                .map(|k| k.trim().to_uppercase())
                .filter(|k| !k.is_empty())
                .collect(),
            _ => BTreeSet::new(),
        }
    }

    /// `get_nws_observation_station_ids_for_point`: up to `limit` nearby
    /// station identifiers, nearest first.
    pub fn observation_station_ids_for_point(
        &self,
        latitude: f64,
        longitude: f64,
        limit: usize,
    ) -> Vec<String> {
        let url = format!("{}/points/{latitude:.4},{longitude:.4}", self.base_url);
        let stations = (|| {
            let point = self.send(&self.request(url)).ok()?;
            if point.status != 200 {
                return None;
            }
            let stations_url = point.json().ok()?["properties"]["observationStations"]
                .as_str()
                .filter(|s| !s.is_empty())?
                .to_string();
            let stations = self.send(&self.request(stations_url)).ok()?;
            (stations.status == 200).then_some(stations)
        })();
        let Some(stations) = stations.and_then(|s| s.json().ok()) else {
            return Vec::new();
        };
        let mut candidates: Vec<String> = Vec::new();
        for url in stations["observationStations"]
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or_default()
        {
            let Some(url) = url.as_str() else {
                continue;
            };
            let id = url
                .trim_end_matches('/')
                .rsplit('/')
                .next()
                .unwrap_or("")
                .trim()
                .to_uppercase();
            if !id.is_empty() && !candidates.contains(&id) {
                candidates.push(id);
            }
            if candidates.len() >= limit {
                break;
            }
        }
        candidates
    }

    /// A `/products` listing's `@graph` (non-200 is a fetch error).
    fn product_listing(
        &self,
        req: &HttpRequest,
        transport_context: impl FnOnce() -> String,
        status_context: impl FnOnce() -> String,
    ) -> Result<Vec<Value>, TextProductError> {
        let resp = self
            .send(req)
            .map_err(|e| TextProductError::from_http(e, transport_context))?;
        if resp.status != 200 {
            return Err(TextProductError::Fetch(format!(
                "HTTP {} fetching {}",
                resp.status,
                status_context()
            )));
        }
        let body = resp
            .json()
            .map_err(|e| TextProductError::Other(e.to_string()))?;
        // A non-list @graph has no dict entries, so it lists nothing.
        match get_truthy(&body, "@graph") {
            Some(Value::Array(graph)) => Ok(graph.clone()),
            _ => Ok(Vec::new()),
        }
    }

    /// `_fetch_text_product_by_id`: `None` for entries without an id or
    /// products without text.
    fn product_by_id(
        &self,
        product_type: &str,
        office: &str,
        entry: &Value,
    ) -> Result<Option<TextProduct>, ProductFetch> {
        let Some(product_id) = get_truthy(entry, "id") else {
            tracing::warn!("No product ID in {product_type} @graph entry for office {office}");
            return Ok(None);
        };
        let product_id = py_str(product_id);
        let mut issuance_time = parse_iso_datetime(&entry["issuanceTime"]);

        let url = format!("{}/products/{product_id}", self.base_url);
        let resp = self.send(&self.request(url)).map_err(ProductFetch::Http)?;
        if resp.status != 200 {
            tracing::warn!(
                "Failed to get {product_type} product text ({product_id}): HTTP {}",
                resp.status
            );
            return Err(ProductFetch::Status(format!(
                "HTTP {} fetching {product_type} product {product_id}",
                resp.status
            )));
        }
        let data = resp.json().map_err(ProductFetch::Http)?;
        let Some(text) = get_truthy(&data, "productText") else {
            tracing::warn!("No productText in {product_type} product {product_id}");
            return Ok(None);
        };
        if let Some(body_issuance) = parse_iso_datetime(&data["issuanceTime"]) {
            issuance_time = Some(body_issuance);
        }
        let headline = get_truthy(&data, "headline")
            .or_else(|| entry.get("headline").filter(|h| !h.is_null()))
            .map(py_str);
        Ok(Some(TextProduct {
            product_type: product_type.to_string(),
            product_id,
            cwa_office: office.to_string(),
            issuance_time,
            product_text: py_str(text),
            headline,
        }))
    }
}

/// Failure inside `_fetch_text_product_by_id`, before the caller wraps it.
enum ProductFetch {
    Http(HttpError),
    Status(String),
}

impl ProductFetch {
    fn with_context(self, context: impl FnOnce() -> String) -> TextProductError {
        match self {
            ProductFetch::Status(msg) => TextProductError::Fetch(msg),
            ProductFetch::Http(e) => TextProductError::from_http(e, context),
        }
    }
}

/// `datetime.isoformat()`: microseconds only when non-zero.
fn py_isoformat(t: Timestamp) -> String {
    if t.timestamp_subsec_micros() == 0 {
        t.format("%Y-%m-%dT%H:%M:%S%:z").to_string()
    } else {
        t.format("%Y-%m-%dT%H:%M:%S%.6f%:z").to_string()
    }
}
