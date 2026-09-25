//! Air quality, pollen and hourly UV data, ported from
//! `accessiweather.services.environmental_client` (Open-Meteo air-quality,
//! pollen and forecast APIs plus AirNow for current U.S. AQI).

pub mod airnow;

use std::sync::{Arc, RwLock};

use aw_core::model::{EnvironmentalConditions, HourlyAirQuality, HourlyUVIndex, Location, Timestamp};
use aw_core::py;
use chrono::{Duration, FixedOffset, NaiveDateTime, TimeZone, Timelike};
use serde_json::Value;

use crate::http::{build_url, HttpClient};
use crate::openmeteo::mapper::map_hourly_uv_index;

pub use airnow::{AirNowClient, AirNowObservation};

pub const AIR_QUALITY_ENDPOINT: &str = "https://air-quality-api.open-meteo.com/v1/air-quality";
pub const POLLEN_ENDPOINT: &str = "https://pollen-api.open-meteo.com/v1/pollen";
pub const FORECAST_ENDPOINT: &str = "https://api.open-meteo.com/v1/forecast";
const AIRNOW_SOURCE: &str = "EPA AirNow and participating agencies";
const OPENMETEO_AQ_SOURCE: &str = "Open-Meteo Air Quality";

/// What `fetch` should include (Python keyword arguments and defaults).
#[derive(Debug, Clone, Copy)]
pub struct FetchOptions {
    pub include_air_quality: bool,
    pub include_pollen: bool,
    pub include_hourly_air_quality: bool,
    pub include_hourly_uv: bool,
    pub hourly_hours: usize,
    pub prefer_airnow: bool,
}

impl Default for FetchOptions {
    fn default() -> Self {
        Self {
            include_air_quality: true,
            include_pollen: true,
            include_hourly_air_quality: true,
            include_hourly_uv: true,
            hourly_hours: 48,
            prefer_airnow: false,
        }
    }
}

pub struct EnvironmentalDataClient {
    http: Arc<dyn HttpClient>,
    pub user_agent: String,
    airnow: RwLock<Arc<AirNowClient>>,
}

fn is_sequence(value: Option<&Value>) -> bool {
    value.and_then(Value::as_array).is_some_and(|a| !a.is_empty())
}

fn coerce_float(value: Option<&Value>) -> Option<f64> {
    py::as_float(value)
}

/// Open-Meteo local wall-clock timestamp, naive.
fn parse_naive(value: Option<&Value>) -> Option<NaiveDateTime> {
    let text = value?.as_str()?.trim();
    let text = text.strip_suffix('Z').unwrap_or(text);
    if text.is_empty() {
        return None;
    }
    py::fromisoformat(text).map(|(naive, _)| naive)
}

fn offset_seconds(value: Option<&Value>) -> i64 {
    py::number(value).map_or(0, |v| v as i64)
}

/// Local timestamp tagged with the location's real offset.
fn parse_local_aware(value: Option<&Value>, utc_offset: Option<&Value>) -> Option<Timestamp> {
    let naive = parse_naive(value)?;
    FixedOffset::east_opt(offset_seconds(utc_offset) as i32)?
        .from_local_datetime(&naive)
        .single()
}

/// Index of the current local hour: the last entry at or before now.
pub fn current_hour_index(times: Option<&Value>, utc_offset: Option<&Value>, now: Timestamp) -> usize {
    let Some(times) = times.and_then(Value::as_array).filter(|t| !t.is_empty()) else {
        return 0;
    };
    let now_local = now.naive_utc() + Duration::seconds(offset_seconds(utc_offset));
    let mut best = None;
    for (i, time) in times.iter().enumerate() {
        let Some(parsed) = parse_naive(Some(time)) else {
            continue;
        };
        if parsed <= now_local {
            best = Some(i);
        } else {
            break;
        }
    }
    best.unwrap_or(0)
}

/// Drop entries before the start of the current UTC hour (all kept if every
/// entry is in the past).
pub fn drop_past_hours(entries: Vec<HourlyUVIndex>, now: Timestamp) -> Vec<HourlyUVIndex> {
    let now_hour = now
        .to_utc()
        .with_minute(0)
        .and_then(|t| t.with_second(0))
        .and_then(|t| t.with_nanosecond(0))
        .unwrap_or_else(|| now.to_utc());
    let upcoming: Vec<HourlyUVIndex> = entries
        .iter()
        .filter(|e| e.timestamp >= now_hour)
        .cloned()
        .collect();
    if upcoming.is_empty() {
        entries
    } else {
        upcoming
    }
}

/// The value at `index`, or the nearest non-null value scanning outward.
pub fn value_near(series: Option<&Value>, index: usize) -> Option<f64> {
    let series = series?.as_array().filter(|s| !s.is_empty())?;
    let index = index.min(series.len() - 1);
    if let Some(v) = coerce_float(series.get(index)) {
        return Some(v);
    }
    for step in 1..series.len() {
        if let Some(v) = series.get(index + step).and_then(|v| coerce_float(Some(v))) {
            return Some(v);
        }
        if let Some(v) = index.checked_sub(step).and_then(|i| coerce_float(series.get(i))) {
            return Some(v);
        }
    }
    None
}

/// Pollen category by grains/m³.
pub fn pollen_category(value: f64) -> &'static str {
    if value < 30.0 {
        "Low"
    } else if value < 60.0 {
        "Moderate"
    } else if value < 120.0 {
        "High"
    } else {
        "Very High"
    }
}

fn append_source(environmental: &mut EnvironmentalConditions, source: &str) {
    if !environmental.sources.iter().any(|s| s == source) {
        environmental.sources.push(source.to_string());
    }
}

impl EnvironmentalDataClient {
    pub fn new(http: Arc<dyn HttpClient>, user_agent: &str, airnow_api_key: &str) -> Self {
        let airnow = Arc::new(AirNowClient::new(http.clone(), airnow_api_key, user_agent));
        Self {
            http,
            user_agent: user_agent.to_string(),
            airnow: RwLock::new(airnow),
        }
    }

    /// Replace the AirNow client so a changed key takes effect immediately.
    pub fn set_airnow_api_key(&self, api_key: &str) {
        *self.airnow.write().unwrap() =
            Arc::new(AirNowClient::new(self.http.clone(), api_key, &self.user_agent));
    }

    pub fn airnow(&self) -> Arc<AirNowClient> {
        self.airnow.read().unwrap().clone()
    }

    fn get(&self, url: &str) -> Option<Value> {
        match self
            .http
            .get_json_with_headers(url, &[("User-Agent", &self.user_agent)])
        {
            Ok(v) => Some(v),
            Err(e) => {
                tracing::debug!("Environmental request failed: {e}");
                None
            }
        }
    }

    fn base_params(location: &Location) -> Vec<(&'static str, String)> {
        vec![
            ("latitude", py::float_repr(location.latitude)),
            ("longitude", py::float_repr(location.longitude)),
            ("timezone", "auto".into()),
        ]
    }

    /// Hourly air quality from the current hour on, at most `hours` entries.
    pub fn fetch_hourly_air_quality(
        &self,
        location: &Location,
        hours: usize,
        now: Timestamp,
    ) -> Option<Vec<HourlyAirQuality>> {
        let url = build_url(
            AIR_QUALITY_ENDPOINT,
            &[
                ("latitude", py::float_repr(location.latitude)),
                ("longitude", py::float_repr(location.longitude)),
                (
                    "hourly",
                    "us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide".into(),
                ),
                ("timezone", "auto".into()),
            ],
        );
        let payload = self.get(&url)?;
        let hourly = payload.get("hourly").filter(|h| h.is_object())?;
        let (times, aqi_values) = (hourly.get("time"), hourly.get("us_aqi"));
        if !is_sequence(times) || !is_sequence(aqi_values) {
            return None;
        }
        let offset = payload.get("utc_offset_seconds");
        let start = current_hour_index(times, offset, now);
        let times = times?.as_array()?;
        let aqi_values = aqi_values?.as_array()?;

        let mut result = Vec::new();
        for (count, i) in (start..times.len()).enumerate() {
            if count >= hours || i >= aqi_values.len() {
                break;
            }
            let (Some(timestamp), Some(aqi)) =
                (parse_local_aware(times.get(i), offset), coerce_float(aqi_values.get(i)))
            else {
                continue;
            };
            let mut entry = HourlyAirQuality {
                timestamp,
                aqi: py::round(aqi) as i64,
                category: airnow::air_quality_category(aqi).into(),
                pm2_5: None,
                pm10: None,
                ozone: None,
                nitrogen_dioxide: None,
                sulphur_dioxide: None,
                carbon_monoxide: None,
            };
            for (key, slot) in [
                ("pm2_5", &mut entry.pm2_5),
                ("pm10", &mut entry.pm10),
                ("ozone", &mut entry.ozone),
                ("nitrogen_dioxide", &mut entry.nitrogen_dioxide),
                ("sulphur_dioxide", &mut entry.sulphur_dioxide),
                ("carbon_monoxide", &mut entry.carbon_monoxide),
            ] {
                if is_sequence(hourly.get(key)) {
                    // Python indexes the series directly; a short one raises
                    // and the whole request is treated as failed.
                    let value = hourly[key].as_array()?.get(i)?;
                    *slot = coerce_float(Some(value)).map(|v| py::round_to(v, 1));
                }
            }
            result.push(entry);
        }
        (!result.is_empty()).then_some(result)
    }

    /// Hourly UV index from the current hour on, at most `hours` entries.
    pub fn fetch_hourly_uv_index(
        &self,
        location: &Location,
        hours: usize,
        now: Timestamp,
    ) -> Option<Vec<HourlyUVIndex>> {
        let url = build_url(
            FORECAST_ENDPOINT,
            &[
                ("latitude", py::float_repr(location.latitude)),
                ("longitude", py::float_repr(location.longitude)),
                ("hourly", "uv_index".into()),
                ("timezone", "auto".into()),
                ("forecast_days", (hours / 24 + 1).min(7).to_string()),
            ],
        );
        let payload = self.get(&url)?;
        let mut list = drop_past_hours(map_hourly_uv_index(&payload), now);
        list.truncate(hours);
        (!list.is_empty()).then_some(list)
    }

    /// Supplemental environmental metrics; `None` when nothing was found.
    pub fn fetch(
        &self,
        location: &Location,
        options: FetchOptions,
        now: Timestamp,
    ) -> Option<EnvironmentalConditions> {
        if !options.include_air_quality
            && !options.include_pollen
            && !options.include_hourly_air_quality
            && !options.include_hourly_uv
        {
            return None;
        }
        let mut environmental = EnvironmentalConditions::default();
        let mut airnow_supplied_current = false;
        if options.include_air_quality && options.prefer_airnow {
            airnow_supplied_current = self.populate_airnow_air_quality(location, &mut environmental);
        }
        if options.include_air_quality && !airnow_supplied_current {
            self.populate_air_quality(location, &mut environmental, now);
        }
        if options.include_pollen {
            self.populate_pollen(location, &mut environmental, now);
        }
        if options.include_hourly_air_quality {
            if let Some(hourly) = self.fetch_hourly_air_quality(location, options.hourly_hours, now) {
                append_source(&mut environmental, OPENMETEO_AQ_SOURCE);
                environmental.hourly_air_quality = hourly;
            }
        }
        if options.include_hourly_uv {
            if let Some(uv) = self.fetch_hourly_uv_index(location, options.hourly_hours, now) {
                environmental.hourly_uv_index = uv;
            }
        }
        environmental.has_data().then_some(environmental)
    }

    fn populate_airnow_air_quality(&self, location: &Location, environmental: &mut EnvironmentalConditions) -> bool {
        let observation = match self.airnow().fetch_current_air_quality(location) {
            Ok(Some(o)) => o,
            Ok(None) => return false,
            Err(_) => {
                tracing::debug!("AirNow current AQI unavailable (ValueError)");
                return false;
            }
        };
        environmental.air_quality_index = Some(observation.aqi as f64);
        environmental.air_quality_category = Some(observation.category);
        environmental.air_quality_pollutant = Some(observation.pollutant);
        environmental.air_quality_updated_at = observation.observed_at;
        environmental.air_quality_reporting_area = observation.reporting_area;
        environmental.air_quality_source = Some(AIRNOW_SOURCE.into());
        if observation.observed_at.is_some() {
            environmental.updated_at = observation.observed_at;
        }
        append_source(environmental, AIRNOW_SOURCE);
        true
    }

    fn populate_air_quality(&self, location: &Location, environmental: &mut EnvironmentalConditions, now: Timestamp) {
        let mut params = Self::base_params(location);
        params.push(("hourly", "us_aqi,us_aqi_pm2_5,us_aqi_pm10".into()));
        let Some(payload) = self.get(&build_url(AIR_QUALITY_ENDPOINT, &params)) else {
            return;
        };
        let Some(hourly) = payload.get("hourly").filter(|h| h.is_object()) else {
            return;
        };
        let times = hourly.get("time");
        if !is_sequence(times) || !is_sequence(hourly.get("us_aqi")) {
            return;
        }
        let offset = payload.get("utc_offset_seconds");
        let current = current_hour_index(times, offset, now);
        let Some(index) = value_near(hourly.get("us_aqi"), current) else {
            return;
        };
        environmental.air_quality_index = Some(index);
        environmental.air_quality_category = Some(airnow::air_quality_category(index).into());
        let timestamp = parse_local_aware(times.and_then(|t| t.get(current)), offset);
        environmental.air_quality_updated_at = timestamp;
        environmental.air_quality_source = Some(OPENMETEO_AQ_SOURCE.into());
        environmental.updated_at = timestamp.or(environmental.updated_at);
        append_source(environmental, OPENMETEO_AQ_SOURCE);

        let mut dominant: Option<&str> = None;
        let mut dominant_value = -1.0;
        for (name, key) in [("pm2_5", "us_aqi_pm2_5"), ("pm10", "us_aqi_pm10")] {
            if let Some(value) = value_near(hourly.get(key), current) {
                if value > dominant_value {
                    dominant_value = value;
                    dominant = Some(name);
                }
            }
        }
        if let Some(name) = dominant {
            environmental.air_quality_pollutant = Some(name.to_uppercase());
        }
    }

    fn populate_pollen(&self, location: &Location, environmental: &mut EnvironmentalConditions, now: Timestamp) {
        let mut params = Self::base_params(location);
        params.push(("hourly", "tree_pollen,grass_pollen,weed_pollen".into()));
        let Some(payload) = self.get(&build_url(POLLEN_ENDPOINT, &params)) else {
            return;
        };
        let Some(hourly) = payload.get("hourly").filter(|h| h.is_object()) else {
            return;
        };
        let times = hourly.get("time");
        if !is_sequence(times) {
            return;
        }
        let offset = payload.get("utc_offset_seconds");
        let current = current_hour_index(times, offset, now);
        let timestamp = parse_local_aware(times.and_then(|t| t.get(current)), offset);

        let mut primary: Option<&str> = None;
        let mut primary_value = -1.0;
        for (label, key) in [("Tree", "tree_pollen"), ("Grass", "grass_pollen"), ("Weed", "weed_pollen")] {
            let Some(value) = value_near(hourly.get(key), current) else {
                continue;
            };
            match label {
                "Tree" => environmental.pollen_tree_index = Some(value),
                "Grass" => environmental.pollen_grass_index = Some(value),
                _ => environmental.pollen_weed_index = Some(value),
            }
            if let Some(ts) = timestamp {
                if environmental.updated_at.is_none_or(|u| ts > u) {
                    environmental.updated_at = Some(ts);
                }
            }
            if value > primary_value {
                primary_value = value;
                primary = Some(label);
            }
        }
        if primary_value >= 0.0 {
            environmental.pollen_index = Some(primary_value);
            environmental.pollen_category = Some(pollen_category(primary_value).into());
            environmental.pollen_primary_allergen = primary.map(str::to_string);
            environmental.sources.push("Open-Meteo Pollen".into());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::FixtureClient;
    use chrono::Utc;
    use serde_json::json;

    fn now() -> Timestamp {
        chrono::DateTime::parse_from_rfc3339("2025-06-01T14:20:00+00:00").unwrap()
    }

    fn times(start_hour: i64, count: i64) -> Value {
        json!((0..count)
            .map(|h| format!("2025-06-01T{:02}:00", start_hour + h))
            .collect::<Vec<_>>())
    }

    #[test]
    fn current_hour_index_respects_offset() {
        assert_eq!(current_hour_index(Some(&times(11, 7)), Some(&json!(0)), now()), 3);
        assert_eq!(current_hour_index(Some(&times(8, 6)), Some(&json!(-4 * 3600)), now()), 2);
        assert_eq!(current_hour_index(Some(&json!([])), Some(&json!(0)), now()), 0);
        assert_eq!(current_hour_index(Some(&times(20, 3)), Some(&json!(0)), now()), 0);
    }

    #[test]
    fn value_near_scans_outward() {
        assert_eq!(value_near(Some(&json!([10, 20, 30])), 1), Some(20.0));
        assert_eq!(value_near(Some(&json!([10, null, 30])), 1), Some(30.0));
        assert_eq!(value_near(Some(&json!([10, 20, null])), 2), Some(20.0));
        assert_eq!(value_near(Some(&json!([null, null])), 0), None);
        assert_eq!(value_near(Some(&json!([])), 0), None);
    }

    #[test]
    fn drop_past_hours_keeps_current_hour() {
        let at = |h: u32| HourlyUVIndex {
            timestamp: Utc.with_ymd_and_hms(2025, 6, 1, h, 0, 0).unwrap().fixed_offset(),
            uv_index: 1.0,
            category: "Low".into(),
        };
        let kept = drop_past_hours(vec![at(12), at(13), at(14), at(15)], now());
        assert_eq!(kept.len(), 2);
        let past = drop_past_hours(vec![at(10)], now());
        assert_eq!(past.len(), 1);
    }

    #[test]
    fn fetch_combines_air_quality_pollen_and_hourly() {
        let aq = json!({"utc_offset_seconds": 0, "hourly": {"time": times(12, 4),
            "us_aqi": [10, 20, 55.4, 70], "us_aqi_pm2_5": [1, 2, 55, 3], "us_aqi_pm10": [1, 2, 30, 3],
            "pm2_5": [1.04, 2.05, 3.15, 4.0], "ozone": [50, 60, 70, 80]}});
        let pollen = json!({"utc_offset_seconds": 0, "hourly": {"time": times(12, 4),
            "tree_pollen": [0, 0, 12.0, 0], "grass_pollen": [0, 0, 45.5, 0], "weed_pollen": [null, null, null, null]}});
        let uv = json!({"utc_offset_seconds": 0, "hourly": {"time": times(12, 4), "uv_index": [1, 2, 3, 4]}});
        let http = Arc::new(
            FixtureClient::new()
                .with(AIR_QUALITY_ENDPOINT, aq)
                .with(POLLEN_ENDPOINT, pollen)
                .with(FORECAST_ENDPOINT, uv),
        );
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "");
        let env = client
            .fetch(&Location::new("x", 40.0, -74.0), FetchOptions::default(), now())
            .unwrap();
        assert_eq!(env.air_quality_index, Some(55.4));
        assert_eq!(env.air_quality_category.as_deref(), Some("Moderate"));
        assert_eq!(env.air_quality_pollutant.as_deref(), Some("PM2_5"));
        assert_eq!(env.pollen_index, Some(45.5));
        assert_eq!(env.pollen_primary_allergen.as_deref(), Some("Grass"));
        assert_eq!(env.pollen_category.as_deref(), Some("Moderate"));
        assert_eq!(env.sources, vec!["Open-Meteo Air Quality", "Open-Meteo Pollen"]);
        assert_eq!(env.hourly_air_quality.len(), 2);
        assert_eq!(env.hourly_air_quality[0].aqi, 55);
        assert_eq!(env.hourly_air_quality[0].pm2_5, Some(3.1));
        assert_eq!(env.hourly_uv_index.len(), 2);
        assert!(http.request_log()[3].ends_with("hourly=uv_index&timezone=auto&forecast_days=3"));
    }
}
