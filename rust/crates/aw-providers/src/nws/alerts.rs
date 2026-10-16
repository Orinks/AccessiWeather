//! Active alerts for every alert radius and recent cancel messages
//! (`weather_client_nws_alerts.py`).

use std::collections::BTreeSet;

use aw_core::model::{Location, WeatherAlerts};
use chrono::{Duration, Utc};
use serde_json::{json, Value};

use super::common::{py_float_repr, py_str, truthy};
use super::parsers::parse_alerts;
use super::{or_fallback, NwsClient};
use crate::http::HttpError;

impl NwsClient<'_> {
    fn point_param(location: &Location) -> String {
        format!(
            "{},{}",
            py_float_repr(location.latitude),
            py_float_repr(location.longitude)
        )
    }

    /// `get_nws_alerts` for `alert_radius_type` "county", "zone", "state" or
    /// "point" (anything else is treated as "point"). Every message type
    /// (Alert, Update, Cancel) is kept.
    pub fn alerts(
        &self,
        location: &Location,
        alert_radius_type: &str,
    ) -> Result<WeatherAlerts, HttpError> {
        self.retry(|| {
            let attempt = self.alerts_once(location, alert_radius_type);
            or_fallback(
                attempt,
                WeatherAlerts::default(),
                "Failed to get NWS alerts",
            )
        })
    }

    fn alerts_once(&self, location: &Location, radius: &str) -> Result<WeatherAlerts, HttpError> {
        let alerts_url = format!("{}/alerts/active", self.base_url);
        let point = |_: ()| vec![("point", Self::point_param(location))];
        let params: Vec<(&str, String)> = match radius {
            "county" => match location.county_zone_id.as_deref().filter(|z| !z.is_empty()) {
                // The stored zone (kept fresh by drift correction) saves a
                // /points round-trip on every refresh.
                Some(zone) => vec![("zone", zone.to_string())],
                None => match self.county_zone(&self.point_data(location)?) {
                    Some(zone) => vec![("zone", zone)],
                    None => {
                        tracing::warn!(
                            "Could not determine county zone, falling back to point query"
                        );
                        point(())
                    }
                },
            },
            "state" => {
                let point_data = self.point_data(location)?;
                let state = &point_data["properties"]["relativeLocation"]["properties"]["state"];
                if truthy(state) {
                    vec![("area", py_str(state))]
                } else {
                    tracing::warn!("Could not determine state, falling back to point query");
                    point(())
                }
            }
            "zone" => {
                // Many products (severe thunderstorm watches among them) are
                // county-zone products, so query county and forecast zones.
                let mut zone_ids: Vec<String> = Vec::new();
                if let Some(z) = location.county_zone_id.as_deref().filter(|z| !z.is_empty()) {
                    zone_ids.push(z.to_string());
                }
                if let Some(z) = location
                    .forecast_zone_id
                    .as_deref()
                    .filter(|z| !z.is_empty())
                {
                    if !zone_ids.iter().any(|x| x == z) {
                        zone_ids.push(z.to_string());
                    }
                }
                if zone_ids.is_empty() {
                    let point_data = self.point_data(location)?;
                    zone_ids.extend(self.county_zone(&point_data));
                    if let Some(z) =
                        split_after(&point_data["properties"]["forecastZone"], "/forecast/")
                    {
                        if !zone_ids.contains(&z) {
                            zone_ids.push(z);
                        }
                    }
                }
                if !zone_ids.is_empty() {
                    let mut features = Vec::new();
                    for zone in &zone_ids {
                        let req = self
                            .request(&alerts_url)
                            .param("zone", zone.as_str())
                            .param("status", "actual");
                        match self.fetch_json(&req) {
                            Ok(data) => features
                                .extend(data["features"].as_array().cloned().unwrap_or_default()),
                            Err(e) => tracing::warn!("Failed getting alerts for zone {zone}: {e}"),
                        }
                    }
                    return Ok(parse_alerts(&json!({ "features": features }))?);
                }
                tracing::warn!("Could not determine zone, falling back to point query");
                point(())
            }
            _ => point(()),
        };

        let mut req = self.request(&alerts_url);
        for (name, value) in params {
            req = req.param(name, value);
        }
        // No message_type filter: it would drop "Update" messages.
        let req = req.param("status", "actual");
        Ok(parse_alerts(&self.fetch_json(&req)?)?)
    }

    fn point_data(&self, location: &Location) -> Result<Value, HttpError> {
        self.fetch_json(&self.request(self.points_url(location)))
    }

    fn county_zone(&self, point_data: &Value) -> Option<String> {
        split_after(&point_data["properties"]["county"], "/county/")
    }

    /// `fetch_nws_cancel_references`: IDs referenced by NWS Cancel messages
    /// sent in the last `lookback_minutes`. Any failure yields an empty set,
    /// which makes callers treat ambiguous cancellations conservatively.
    pub fn cancel_references(&self, lookback_minutes: i64) -> BTreeSet<String> {
        let now = self.now().with_timezone(&Utc);
        let start = now - Duration::minutes(lookback_minutes);
        let fmt = "%Y-%m-%dT%H:%M:%SZ";
        let req = self
            .request(format!("{}/alerts", self.base_url))
            .param("message_type", "cancel")
            .param("start", start.format(fmt).to_string())
            .param("end", now.format(fmt).to_string());
        // Malformed entries abort the whole lookup, as the Python
        // AttributeError would.
        let collect = |data: &Value| -> Option<BTreeSet<String>> {
            let mut ids = BTreeSet::new();
            let features = match data.get("features") {
                None => return Some(ids),
                Some(f) => f.as_array()?,
            };
            for feature in features {
                let refs = match feature.as_object()?.get("properties") {
                    None => continue,
                    Some(props) => match props.as_object()?.get("references") {
                        None => continue,
                        Some(refs) => refs.as_array()?,
                    },
                };
                for r in refs {
                    let r = r.as_object()?;
                    if let Some(id) = ["identifier", "@id", "id"]
                        .iter()
                        .find_map(|k| r.get(*k).filter(|v| truthy(v)))
                    {
                        ids.insert(py_str(id));
                    }
                }
            }
            Some(ids)
        };
        match self.fetch_json(&req) {
            Ok(data) => collect(&data).unwrap_or_default(),
            Err(e) => {
                tracing::warn!("Failed to fetch NWS cancel references: {e}");
                BTreeSet::new()
            }
        }
    }
}

/// `url.split(marker)[1]` when `url` is a string containing `marker`.
fn split_after(url: &Value, marker: &str) -> Option<String> {
    let url = url.as_str()?;
    url.contains(marker)
        .then(|| url.split(marker).nth(1).unwrap_or("").to_string())
}
