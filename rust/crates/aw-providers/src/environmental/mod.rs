//! Air quality, pollen and hourly UV data, ported from
//! `accessiweather.services.environmental_client` (Open-Meteo air-quality,
//! pollen and forecast APIs plus AirNow for current U.S. AQI).

pub mod airnow;
pub mod openaq;

use std::sync::{Arc, RwLock};

use aw_core::air_quality::{self, AqiPreference, AqiStandard};
use aw_core::model::{
    AirQualityProvenance, EnvironmentalConditions, HourlyAirQuality, HourlyUVIndex, Location,
    PollutantReading, ReadingKind, Timestamp,
};
use aw_core::py;
use chrono::{Duration, FixedOffset, NaiveDateTime, TimeZone, Timelike};
use serde_json::Value;

use crate::http::{build_url, HttpClient};
use crate::openmeteo::mapper::map_hourly_uv_index;

pub use airnow::{AirNowClient, AirNowObservation};
pub use openaq::{OpenAqClient, OpenAqStation};

pub const AIR_QUALITY_ENDPOINT: &str = "https://air-quality-api.open-meteo.com/v1/air-quality";
pub const POLLEN_ENDPOINT: &str = "https://pollen-api.open-meteo.com/v1/pollen";
pub const FORECAST_ENDPOINT: &str = "https://api.open-meteo.com/v1/forecast";
const AIRNOW_SOURCE: &str = "EPA AirNow and participating agencies";
const OPENMETEO_AQ_SOURCE: &str = "Open-Meteo Air Quality";
const OPENAQ_SOURCE: &str = "OpenAQ";
/// Provider names on [`AirQualityProvenance`].
const AIRNOW_PROVIDER: &str = "AirNow";
const OPENMETEO_PROVIDER: &str = "Open-Meteo";
const OPENAQ_PROVIDER: &str = "OpenAQ";
/// Open-Meteo's documented unit for every concentration variable.
const OPENMETEO_DEFAULT_UNIT: &str = "μg/m³";

/// Reading code and Open-Meteo concentration variable, in display order.
const CONCENTRATION_VARIABLES: [(&str, &str); 6] = [
    ("pm2_5", "pm2_5"),
    ("pm10", "pm10"),
    ("o3", "ozone"),
    ("no2", "nitrogen_dioxide"),
    ("so2", "sulphur_dioxide"),
    ("co", "carbon_monoxide"),
];

/// US sub-indices beyond the particulate ones the headline request has.
const US_EXTRA_SUB_INDICES: [(&str, &str); 4] = [
    ("o3", "us_aqi_ozone"),
    ("no2", "us_aqi_nitrogen_dioxide"),
    ("so2", "us_aqi_sulphur_dioxide"),
    ("co", "us_aqi_carbon_monoxide"),
];

/// What `fetch` should include (Python keyword arguments and defaults).
#[derive(Debug, Clone, Copy)]
pub struct FetchOptions {
    pub include_air_quality: bool,
    pub include_pollen: bool,
    pub include_hourly_air_quality: bool,
    pub include_hourly_uv: bool,
    pub hourly_hours: usize,
    /// Ask AirNow first; only honoured when the resolved standard is the US
    /// AQI, so one location never mixes indexes.
    pub prefer_airnow: bool,
    /// The "Air quality index" setting.
    pub aqi_preference: AqiPreference,
    /// Ask for every pollutant's concentration and sub-index, and fill
    /// `pollutant_readings` and `air_quality_provenance`.
    pub pollutant_detail: bool,
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
            aqi_preference: AqiPreference::Auto,
            pollutant_detail: true,
        }
    }
}

pub struct EnvironmentalDataClient {
    http: Arc<dyn HttpClient>,
    pub user_agent: String,
    airnow: RwLock<Arc<AirNowClient>>,
    openaq: RwLock<Arc<OpenAqClient>>,
}

fn is_sequence(value: Option<&Value>) -> bool {
    value
        .and_then(Value::as_array)
        .is_some_and(|a| !a.is_empty())
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
pub fn current_hour_index(
    times: Option<&Value>,
    utc_offset: Option<&Value>,
    now: Timestamp,
) -> usize {
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
        if let Some(v) = index
            .checked_sub(step)
            .and_then(|i| coerce_float(series.get(i)))
        {
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

/// The Open-Meteo hourly variables for the headline index of `standard`:
/// the index, then its per-pollutant sub-indices.
fn index_variables(standard: AqiStandard) -> &'static [(&'static str, &'static str)] {
    match standard {
        AqiStandard::Us => &[
            ("", "us_aqi"),
            ("pm2_5", "us_aqi_pm2_5"),
            ("pm10", "us_aqi_pm10"),
        ],
        AqiStandard::European => &[
            ("", "european_aqi"),
            ("pm2_5", "european_aqi_pm2_5"),
            ("pm10", "european_aqi_pm10"),
            ("no2", "european_aqi_nitrogen_dioxide"),
            ("o3", "european_aqi_ozone"),
            ("so2", "european_aqi_sulphur_dioxide"),
        ],
    }
}

/// An AirNow observation's provenance: observed in its reporting area.
fn airnow_provenance(observation: &AirNowObservation) -> AirQualityProvenance {
    AirQualityProvenance {
        kind: ReadingKind::Observed,
        provider: AIRNOW_PROVIDER.into(),
        detail: None,
        station_name: observation.reporting_area.clone(),
        station_distance_km: None,
        time: observation.observed_at,
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
        let openaq = Arc::new(OpenAqClient::new(http.clone(), "", user_agent));
        Self {
            http,
            user_agent: user_agent.to_string(),
            airnow: RwLock::new(airnow),
            openaq: RwLock::new(openaq),
        }
    }

    /// Ask OpenAQ for observed station readings with `api_key`.
    pub fn with_openaq_key(self, api_key: &str) -> Self {
        self.set_openaq_api_key(api_key);
        self
    }

    /// Replace the OpenAQ client so a changed key takes effect immediately.
    pub fn set_openaq_api_key(&self, api_key: &str) {
        *self.openaq.write().unwrap() = Arc::new(OpenAqClient::new(
            self.http.clone(),
            api_key,
            &self.user_agent,
        ));
    }

    pub fn openaq(&self) -> Arc<OpenAqClient> {
        self.openaq.read().unwrap().clone()
    }

    /// Replace the AirNow client so a changed key takes effect immediately.
    pub fn set_airnow_api_key(&self, api_key: &str) {
        *self.airnow.write().unwrap() = Arc::new(AirNowClient::new(
            self.http.clone(),
            api_key,
            &self.user_agent,
        ));
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

    /// Hourly air quality on the `standard` index from the current hour on,
    /// at most `hours` entries.
    pub fn fetch_hourly_air_quality(
        &self,
        location: &Location,
        hours: usize,
        now: Timestamp,
        standard: AqiStandard,
    ) -> Option<Vec<HourlyAirQuality>> {
        let index_key = index_variables(standard)[0].1;
        let url = build_url(
            AIR_QUALITY_ENDPOINT,
            &[
                ("latitude", py::float_repr(location.latitude)),
                ("longitude", py::float_repr(location.longitude)),
                (
                    "hourly",
                    format!(
                        "{index_key},pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,\
                         carbon_monoxide"
                    ),
                ),
                ("timezone", "auto".into()),
            ],
        );
        let payload = self.get(&url)?;
        let hourly = payload.get("hourly").filter(|h| h.is_object())?;
        let (times, aqi_values) = (hourly.get("time"), hourly.get(index_key));
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
            let (Some(timestamp), Some(aqi)) = (
                parse_local_aware(times.get(i), offset),
                coerce_float(aqi_values.get(i)),
            ) else {
                continue;
            };
            let mut entry = HourlyAirQuality {
                timestamp,
                aqi: py::round(aqi) as i64,
                category: standard.category(aqi).into(),
                aqi_standard: Some(standard),
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
        let standard = options.aqi_preference.resolve(location);
        let mut environmental = EnvironmentalConditions::default();
        let mut airnow_supplied_current = false;
        // Observed pollutant levels: OpenAQ first, then AirNow, then the
        // model fills whatever is left, one row per pollutant.
        if options.include_air_quality && options.pollutant_detail {
            self.populate_openaq(location, &mut environmental, now);
        }
        // AirNow only reports the US AQI.
        if options.include_air_quality && options.prefer_airnow && standard == AqiStandard::Us {
            airnow_supplied_current = self.populate_airnow_air_quality(
                location,
                &mut environmental,
                options.pollutant_detail,
            );
        }
        // With AirNow's index in hand, Open-Meteo still fills in the
        // pollutants no station reported.
        if options.include_air_quality && (!airnow_supplied_current || options.pollutant_detail) {
            self.populate_air_quality(
                location,
                &mut environmental,
                now,
                standard,
                !airnow_supplied_current,
                options.pollutant_detail,
            );
        }
        if options.include_pollen {
            self.populate_pollen(location, &mut environmental, now);
        }
        if options.include_hourly_air_quality {
            if let Some(hourly) =
                self.fetch_hourly_air_quality(location, options.hourly_hours, now, standard)
            {
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

    /// Observed concentrations from the nearest OpenAQ station. Failures
    /// and empty answers leave `environmental` untouched.
    fn populate_openaq(
        &self,
        location: &Location,
        environmental: &mut EnvironmentalConditions,
        now: Timestamp,
    ) {
        let client = self.openaq();
        if client.api_key().is_empty() {
            return;
        }
        let station = match client.fetch_nearest(location, now) {
            Ok(Some(station)) => station,
            Ok(None) => {
                tracing::debug!("No recent OpenAQ station nearby");
                return;
            }
            Err(e) => {
                tracing::debug!("OpenAQ unavailable ({})", airnow::error_kind(&e));
                return;
            }
        };
        let station_name = station.display_name();
        let (detail, averaging) = if station.is_monitor {
            ("reference monitor", "1-hour")
        } else {
            ("low-cost sensor", "Latest sensor reading")
        };
        let mut added = false;
        for reading in &station.readings {
            if environmental
                .pollutant_readings
                .iter()
                .any(|r| r.code == reading.code)
            {
                continue;
            }
            environmental.pollutant_readings.push(PollutantReading {
                code: reading.code.into(),
                concentration: Some(reading.value),
                unit: reading.unit.clone(),
                averaging: Some(averaging.into()),
                index_value: None,
                index_category: None,
                index_standard: None,
                index_averaging: None,
                provenance: AirQualityProvenance {
                    kind: ReadingKind::Observed,
                    provider: OPENAQ_PROVIDER.into(),
                    detail: Some(detail.into()),
                    station_name: Some(station_name.clone()),
                    station_distance_km: station.distance_km,
                    time: Some(reading.time),
                },
            });
            added = true;
        }
        if added {
            append_source(environmental, OPENAQ_SOURCE);
        }
    }

    fn populate_airnow_air_quality(
        &self,
        location: &Location,
        environmental: &mut EnvironmentalConditions,
        detail: bool,
    ) -> bool {
        let airnow = self.airnow();
        let observation = match airnow.fetch_current_air_quality(location) {
            Ok(Some(o)) => o,
            Ok(None) => return false,
            Err(_) => {
                tracing::debug!("AirNow current AQI unavailable (ValueError)");
                return false;
            }
        };
        let provenance = airnow_provenance(&observation);
        environmental.air_quality_index = Some(observation.aqi as f64);
        environmental.air_quality_category = Some(observation.category);
        environmental.air_quality_index_standard = Some(AqiStandard::Us);
        environmental.air_quality_pollutant = Some(observation.pollutant);
        environmental.air_quality_updated_at = observation.observed_at;
        environmental.air_quality_reporting_area = observation.reporting_area;
        environmental.air_quality_source = Some(AIRNOW_SOURCE.into());
        if observation.observed_at.is_some() {
            environmental.updated_at = observation.observed_at;
        }
        append_source(environmental, AIRNOW_SOURCE);
        if detail {
            environmental.air_quality_provenance = Some(provenance);
            // Same cached response: no second request.
            let all = airnow
                .fetch_current_observations(location)
                .unwrap_or_default();
            for o in &all {
                let Some(code) = airnow::pollutant_code(&o.pollutant) else {
                    continue;
                };
                if environmental
                    .pollutant_readings
                    .iter()
                    .any(|r| r.code == code)
                {
                    continue;
                }
                environmental.pollutant_readings.push(PollutantReading {
                    code: code.into(),
                    concentration: None,
                    unit: None,
                    averaging: None,
                    index_value: Some(o.aqi as f64),
                    index_category: Some(o.category.clone()),
                    index_standard: Some(AqiStandard::Us),
                    // AirNow's current particulate and ozone values are NowCast.
                    index_averaging: matches!(code, "pm2_5" | "pm10" | "o3")
                        .then(|| "NowCast".to_string()),
                    provenance: airnow_provenance(o),
                });
            }
        }
        true
    }

    /// Open-Meteo current air quality. `headline` sets the index, category
    /// and dominant pollutant; `detail` adds a modelled reading for each
    /// pollutant not already in `pollutant_readings`.
    fn populate_air_quality(
        &self,
        location: &Location,
        environmental: &mut EnvironmentalConditions,
        now: Timestamp,
        standard: AqiStandard,
        headline: bool,
        detail: bool,
    ) {
        let variables = index_variables(standard);
        let index_key = variables[0].1;
        let mut sub_indices: Vec<(&str, &str)> = variables[1..].to_vec();
        if detail && standard == AqiStandard::Us {
            sub_indices.extend(US_EXTRA_SUB_INDICES);
        }
        let mut hourly_list = vec![index_key];
        hourly_list.extend(sub_indices.iter().map(|(_, key)| *key));
        if detail {
            hourly_list.extend(CONCENTRATION_VARIABLES.iter().map(|(_, key)| *key));
        }
        let mut params = Self::base_params(location);
        params.push(("hourly", hourly_list.join(",")));
        let Some(payload) = self.get(&build_url(AIR_QUALITY_ENDPOINT, &params)) else {
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
        let provenance = AirQualityProvenance {
            kind: ReadingKind::Modelled,
            provider: OPENMETEO_PROVIDER.into(),
            detail: Some(air_quality::cams_detail(
                location.latitude,
                location.longitude,
            )),
            station_name: None,
            station_distance_km: None,
            time: timestamp,
        };

        if headline && is_sequence(hourly.get(index_key)) {
            if let Some(index) = value_near(hourly.get(index_key), current) {
                environmental.air_quality_index = Some(index);
                environmental.air_quality_category = Some(standard.category(index).into());
                environmental.air_quality_index_standard = Some(standard);
                environmental.air_quality_updated_at = timestamp;
                environmental.air_quality_source = Some(OPENMETEO_AQ_SOURCE.into());
                environmental.updated_at = timestamp.or(environmental.updated_at);
                append_source(environmental, OPENMETEO_AQ_SOURCE);
                if detail {
                    environmental.air_quality_provenance = Some(provenance.clone());
                }

                let mut dominant: Option<&str> = None;
                let mut dominant_value = -1.0;
                for (name, key) in &sub_indices {
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
        }

        if detail {
            let added = self.add_modelled_readings(
                environmental,
                hourly,
                payload.get("hourly_units"),
                current,
                standard,
                &sub_indices,
                &provenance,
            );
            if added {
                append_source(environmental, OPENMETEO_AQ_SOURCE);
            }
        }
    }

    /// One modelled reading per pollutant with a value this hour, skipping
    /// pollutants an observation already covers. True when any was added.
    #[allow(clippy::too_many_arguments)]
    fn add_modelled_readings(
        &self,
        environmental: &mut EnvironmentalConditions,
        hourly: &Value,
        units: Option<&Value>,
        current: usize,
        standard: AqiStandard,
        sub_indices: &[(&str, &str)],
        provenance: &AirQualityProvenance,
    ) -> bool {
        // The exact hour only: a neighbouring hour would carry the wrong time.
        let at = |key: &str| {
            hourly
                .get(key)
                .and_then(Value::as_array)
                .and_then(|series| coerce_float(series.get(current)))
        };
        let mut added = false;
        for (code, key) in CONCENTRATION_VARIABLES {
            if environmental
                .pollutant_readings
                .iter()
                .any(|r| r.code == code)
            {
                continue;
            }
            let concentration = at(key).filter(|v| *v >= 0.0);
            let index = sub_indices
                .iter()
                .find(|(c, _)| *c == code)
                .and_then(|(_, sub_key)| at(sub_key))
                .filter(|v| *v >= 0.0);
            if concentration.is_none() && index.is_none() {
                continue;
            }
            let unit = units
                .and_then(|u| u.get(key))
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|u| !u.is_empty())
                .unwrap_or(OPENMETEO_DEFAULT_UNIT);
            environmental.pollutant_readings.push(PollutantReading {
                code: code.into(),
                concentration: concentration.map(|v| py::round_to(v, 1)),
                unit: concentration.map(|_| unit.to_string()),
                averaging: concentration.map(|_| "1-hour".to_string()),
                index_value: index,
                index_category: index.map(|v| standard.category(v).to_string()),
                index_standard: index.map(|_| standard),
                index_averaging: index
                    .and(air_quality::index_averaging(standard, code))
                    .map(str::to_string),
                provenance: provenance.clone(),
            });
            added = true;
        }
        added
    }

    fn populate_pollen(
        &self,
        location: &Location,
        environmental: &mut EnvironmentalConditions,
        now: Timestamp,
    ) {
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
        for (label, key) in [
            ("Tree", "tree_pollen"),
            ("Grass", "grass_pollen"),
            ("Weed", "weed_pollen"),
        ] {
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
        assert_eq!(
            current_hour_index(Some(&times(11, 7)), Some(&json!(0)), now()),
            3
        );
        assert_eq!(
            current_hour_index(Some(&times(8, 6)), Some(&json!(-4 * 3600)), now()),
            2
        );
        assert_eq!(
            current_hour_index(Some(&json!([])), Some(&json!(0)), now()),
            0
        );
        assert_eq!(
            current_hour_index(Some(&times(20, 3)), Some(&json!(0)), now()),
            0
        );
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
            timestamp: Utc
                .with_ymd_and_hms(2025, 6, 1, h, 0, 0)
                .unwrap()
                .fixed_offset(),
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
            .fetch(
                &Location::new("x", 40.0, -74.0),
                FetchOptions::default(),
                now(),
            )
            .unwrap();
        assert_eq!(env.air_quality_index, Some(55.4));
        assert_eq!(env.air_quality_category.as_deref(), Some("Moderate"));
        assert_eq!(env.air_quality_pollutant.as_deref(), Some("PM2_5"));
        assert_eq!(env.pollen_index, Some(45.5));
        assert_eq!(env.pollen_primary_allergen.as_deref(), Some("Grass"));
        assert_eq!(env.pollen_category.as_deref(), Some("Moderate"));
        assert_eq!(
            env.sources,
            vec!["Open-Meteo Air Quality", "Open-Meteo Pollen"]
        );
        assert_eq!(env.hourly_air_quality.len(), 2);
        assert_eq!(env.hourly_air_quality[0].aqi, 55);
        assert_eq!(env.hourly_air_quality[0].pm2_5, Some(3.1));
        assert_eq!(env.hourly_uv_index.len(), 2);
        assert!(http.request_log()[3].ends_with("hourly=uv_index&timezone=auto&forecast_days=3"));
    }

    fn aq_only() -> FetchOptions {
        FetchOptions {
            include_pollen: false,
            include_hourly_uv: false,
            hourly_hours: 2,
            ..FetchOptions::default()
        }
    }

    #[test]
    fn european_location_uses_the_european_index() {
        let aq = json!({"utc_offset_seconds": 0, "hourly": {"time": times(12, 4),
            "european_aqi": [10, 20, 35, 70], "european_aqi_pm2_5": [1, 2, 20, 3],
            "european_aqi_pm10": [1, 2, 10, 3], "european_aqi_nitrogen_dioxide": [1, 2, 35, 3],
            "european_aqi_ozone": [1, 2, 30, 3], "european_aqi_sulphur_dioxide": [1, 2, 5, 3]}});
        let http = Arc::new(FixtureClient::new().with(AIR_QUALITY_ENDPOINT, aq));
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "key");
        let paris = Location::new("Paris", 48.8566, 2.3522).with_country("FR");
        let options = FetchOptions {
            prefer_airnow: true,
            ..aq_only()
        };
        let env = client.fetch(&paris, options, now()).unwrap();
        assert_eq!(env.air_quality_index, Some(35.0));
        assert_eq!(env.air_quality_category.as_deref(), Some("Fair"));
        assert_eq!(env.air_quality_index_standard, Some(AqiStandard::European));
        assert_eq!(env.air_quality_pollutant.as_deref(), Some("NO2"));
        assert_eq!(env.hourly_air_quality[0].category, "Fair");
        assert_eq!(env.hourly_air_quality[1].category, "Poor");
        assert_eq!(
            env.hourly_air_quality[0].aqi_standard,
            Some(AqiStandard::European)
        );
        let log = http.request_log();
        assert_eq!(
            log.len(),
            2,
            "no AirNow request outside the US AQI: {log:?}"
        );
        assert!(log[0].contains(
            "hourly=european_aqi%2Ceuropean_aqi_pm2_5%2Ceuropean_aqi_pm10%2C\
             european_aqi_nitrogen_dioxide%2Ceuropean_aqi_ozone%2Ceuropean_aqi_sulphur_dioxide"
        ));
        assert!(log[1].contains(
            "hourly=european_aqi%2Cpm2_5%2Cpm10%2Cozone%2Cnitrogen_dioxide%2C\
             sulphur_dioxide%2Ccarbon_monoxide"
        ));
    }

    #[test]
    fn forced_european_index_skips_airnow_in_the_us() {
        let aq = json!({"utc_offset_seconds": 0, "hourly": {"time": times(12, 4),
            "european_aqi": [10, 20, 65, 70]}});
        let http = Arc::new(FixtureClient::new().with(AIR_QUALITY_ENDPOINT, aq));
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "key");
        let options = FetchOptions {
            prefer_airnow: true,
            aqi_preference: AqiPreference::European,
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let nyc = Location::new("NYC", 40.7, -74.0).with_country("US");
        let env = client.fetch(&nyc, options, now()).unwrap();
        assert_eq!(env.air_quality_category.as_deref(), Some("Poor"));
        assert_eq!(env.air_quality_index_standard, Some(AqiStandard::European));
        assert!(http
            .request_log()
            .iter()
            .all(|u| u.starts_with(AIR_QUALITY_ENDPOINT)));
    }

    #[test]
    fn us_location_requests_are_unchanged() {
        let aq = json!({"utc_offset_seconds": 0, "hourly": {"time": times(12, 4),
            "us_aqi": [10, 20, 55, 70]}});
        let http = Arc::new(FixtureClient::new().with(AIR_QUALITY_ENDPOINT, aq));
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "");
        let nyc = Location::new("NYC", 40.7, -74.0).with_country("US");
        let options = FetchOptions {
            pollutant_detail: false,
            ..aq_only()
        };
        let env = client.fetch(&nyc, options, now()).unwrap();
        assert_eq!(env.air_quality_index_standard, Some(AqiStandard::Us));
        assert!(env.pollutant_readings.is_empty() && env.air_quality_provenance.is_none());
        assert_eq!(
            env.hourly_air_quality[0].aqi_standard,
            Some(AqiStandard::Us)
        );
        assert_eq!(
            http.request_log(),
            vec![
                format!(
                    "{AIR_QUALITY_ENDPOINT}?latitude=40.7&longitude=-74.0&timezone=auto\
                     &hourly=us_aqi%2Cus_aqi_pm2_5%2Cus_aqi_pm10"
                ),
                format!(
                    "{AIR_QUALITY_ENDPOINT}?latitude=40.7&longitude=-74.0&hourly=us_aqi%2Cpm2_5\
                     %2Cpm10%2Cozone%2Cnitrogen_dioxide%2Csulphur_dioxide%2Ccarbon_monoxide\
                     &timezone=auto"
                ),
            ]
        );
    }

    fn european_detail_payload() -> Value {
        json!({"utc_offset_seconds": 7200, "hourly_units": {"pm2_5": "μg/m³", "pm10": "μg/m³",
            "ozone": "μg/m³", "nitrogen_dioxide": "μg/m³", "sulphur_dioxide": "μg/m³",
            "carbon_monoxide": "μg/m³", "european_aqi": "EAQI"},
            "hourly": {"time": times(14, 4),
            "european_aqi": [10, 20, 45, 70], "european_aqi_pm2_5": [1, 2, 45, 3],
            "european_aqi_pm10": [1, 2, 18, 3], "european_aqi_nitrogen_dioxide": [1, 2, 12, 3],
            "european_aqi_ozone": [1, 2, 30, 3], "european_aqi_sulphur_dioxide": [1, 2, 2, 3],
            "pm2_5": [1, 2, 21.04, 3], "pm10": [1, 2, 30.0, 3], "ozone": [1, 2, 80.5, 3],
            "nitrogen_dioxide": [1, 2, 22.0, 3], "sulphur_dioxide": [1, 2, 1.3, 3],
            "carbon_monoxide": [1, 2, 180.0, 3]}})
    }

    #[test]
    fn pollutant_detail_lists_every_modelled_pollutant() {
        let http =
            Arc::new(FixtureClient::new().with(AIR_QUALITY_ENDPOINT, european_detail_payload()));
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "");
        let paris = Location::new("Paris", 48.8566, 2.3522).with_country("FR");
        let options = FetchOptions {
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let env = client.fetch(&paris, options, now()).unwrap();
        let log = http.request_log();
        assert_eq!(log.len(), 1);
        assert!(log[0].ends_with(
            "european_aqi_sulphur_dioxide%2Cpm2_5%2Cpm10%2Cozone%2Cnitrogen_dioxide%2C\
             sulphur_dioxide%2Ccarbon_monoxide"
        ));
        assert_eq!(env.air_quality_category.as_deref(), Some("Moderate"));
        assert_eq!(env.air_quality_pollutant.as_deref(), Some("PM2_5"));
        let codes: Vec<&str> = env
            .pollutant_readings
            .iter()
            .map(|r| r.code.as_str())
            .collect();
        assert_eq!(codes, ["pm2_5", "pm10", "o3", "no2", "so2", "co"]);
        let pm = &env.pollutant_readings[0];
        assert_eq!(pm.concentration, Some(21.0));
        assert_eq!(pm.unit.as_deref(), Some("μg/m³"));
        assert_eq!(pm.averaging.as_deref(), Some("1-hour"));
        assert_eq!(pm.index_value, Some(45.0));
        assert_eq!(pm.index_category.as_deref(), Some("Moderate"));
        assert_eq!(pm.index_standard, Some(AqiStandard::European));
        assert_eq!(pm.index_averaging.as_deref(), Some("24-hour"));
        assert_eq!(pm.provenance.kind, ReadingKind::Modelled);
        assert_eq!(pm.provenance.provider, "Open-Meteo");
        assert_eq!(
            pm.provenance.detail.as_deref(),
            Some("CAMS European model, about 11 km grid")
        );
        assert_eq!(
            pm.provenance.time.unwrap().to_rfc3339(),
            "2025-06-01T16:00:00+02:00"
        );
        assert_eq!(
            env.pollutant_readings[2].index_category.as_deref(),
            Some("Fair")
        );
        // No European sub-index for carbon monoxide.
        let co = &env.pollutant_readings[5];
        assert_eq!((co.concentration, co.index_value), (Some(180.0), None));
        assert_eq!(co.index_averaging, None);
        let headline = env.air_quality_provenance.unwrap();
        assert_eq!(headline, pm.provenance);
    }

    #[test]
    fn pollutant_detail_outside_europe_uses_the_global_model() {
        let aq = json!({"utc_offset_seconds": 36000, "hourly": {"time": times(0, 2),
            "us_aqi": [30, 40], "us_aqi_pm2_5": [30, 40], "us_aqi_ozone": [20, 60],
            "pm2_5": [7.2, 8.1], "ozone": [40.0, 90.0]}});
        let http = Arc::new(FixtureClient::new().with(AIR_QUALITY_ENDPOINT, aq));
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "");
        let sydney = Location::new("Sydney", -33.8688, 151.2093).with_country("AU");
        let options = FetchOptions {
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let env = client.fetch(&sydney, options, now()).unwrap();
        assert!(http.request_log()[0].contains("us_aqi_carbon_monoxide%2Cpm2_5"));
        // All US sub-indices count towards the dominant pollutant.
        assert_eq!(env.air_quality_pollutant.as_deref(), Some("O3"));
        assert_eq!(env.pollutant_readings.len(), 2);
        let ozone = &env.pollutant_readings[1];
        assert_eq!(ozone.index_averaging.as_deref(), Some("8-hour"));
        assert_eq!(ozone.unit.as_deref(), Some("μg/m³"));
        assert_eq!(
            ozone.provenance.detail.as_deref(),
            Some("CAMS global model, about 45 km grid")
        );
    }

    #[test]
    fn airnow_readings_come_first_and_the_model_fills_the_rest() {
        let airnow = json!([
            {"AQI": 42, "ParameterName": "O3", "Category": {"Number": 1, "Name": "Good"},
             "DateObserved": "2025-06-01", "HourObserved": 9, "LocalTimeZone": "EDT",
             "ReportingArea": "Metro"},
            {"AQI": 61, "ParameterName": "PM2.5", "Category": {"Number": 2, "Name": "Moderate"},
             "DateObserved": "2025-06-01", "HourObserved": 9, "LocalTimeZone": "EDT",
             "ReportingArea": "Metro"}
        ]);
        let aq = json!({"utc_offset_seconds": -14400, "hourly": {"time": times(8, 4),
            "us_aqi": [50, 55, 60, 65], "us_aqi_pm2_5": [50, 55, 60, 65],
            "pm2_5": [10, 11, 12, 13], "pm10": [20, 21, 22, 23], "ozone": [60, 61, 62, 63],
            "nitrogen_dioxide": [5, 6, 7, 8]}});
        let http = Arc::new(
            FixtureClient::new()
                .with(airnow::ENDPOINT, airnow)
                .with(AIR_QUALITY_ENDPOINT, aq),
        );
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "key");
        let nyc = Location::new("NYC", 40.7, -74.0).with_country("US");
        let options = FetchOptions {
            prefer_airnow: true,
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let env = client.fetch(&nyc, options, now()).unwrap();
        assert_eq!(http.request_log().len(), 2, "one AirNow, one Open-Meteo");
        // The headline stays AirNow's.
        assert_eq!(env.air_quality_index, Some(61.0));
        assert_eq!(env.air_quality_source.as_deref(), Some(AIRNOW_SOURCE));
        let headline = env.air_quality_provenance.clone().unwrap();
        assert_eq!(headline.kind, ReadingKind::Observed);
        assert_eq!(headline.provider, "AirNow");
        assert_eq!(headline.station_name.as_deref(), Some("Metro"));
        let rows: Vec<(&str, ReadingKind)> = env
            .pollutant_readings
            .iter()
            .map(|r| (r.code.as_str(), r.provenance.kind))
            .collect();
        assert_eq!(
            rows,
            [
                ("o3", ReadingKind::Observed),
                ("pm2_5", ReadingKind::Observed),
                ("pm10", ReadingKind::Modelled),
                ("no2", ReadingKind::Modelled),
            ]
        );
        let o3 = &env.pollutant_readings[0];
        assert_eq!(o3.concentration, None);
        assert_eq!(o3.index_value, Some(42.0));
        assert_eq!(o3.index_category.as_deref(), Some("Good"));
        assert_eq!(o3.index_averaging.as_deref(), Some("NowCast"));
        assert_eq!(
            env.sources,
            [AIRNOW_SOURCE, OPENMETEO_AQ_SOURCE],
            "the model's concentrations are credited"
        );

        // Without pollutant detail AirNow's answer needs no Open-Meteo call.
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "key");
        let options = FetchOptions {
            pollutant_detail: false,
            ..options
        };
        let before = http.request_log().len();
        let env = client.fetch(&nyc, options, now()).unwrap();
        assert_eq!(http.request_log().len(), before + 1);
        assert!(env.pollutant_readings.is_empty());
        assert!(env.air_quality_provenance.is_none());
    }

    fn paris_station() -> Value {
        let mut station = openaq::tests::station(
            4321,
            "Paris 18e",
            2400.0,
            "2025-06-01T14:00:00Z",
            &[(51, "pm25", "µg/m³"), (52, "no2", "µg/m³")],
        );
        // The locality is already in the name, so it is not repeated.
        station["locality"] = json!("Paris");
        station
    }

    fn openaq_latest_url(id: i64) -> String {
        format!("{}/{id}/latest", openaq::LOCATIONS_ENDPOINT)
    }

    #[test]
    fn openaq_observations_come_first_and_the_model_fills_the_rest() {
        let http = Arc::new(
            FixtureClient::new()
                .with(AIR_QUALITY_ENDPOINT, european_detail_payload())
                .with(
                    openaq::LOCATIONS_ENDPOINT,
                    openaq::tests::search(vec![paris_station()]),
                )
                .with(
                    &openaq_latest_url(4321),
                    openaq::tests::latest(
                        4321,
                        &[
                            (51, 14.2, "2025-06-01T14:00:00Z"),
                            (52, 31.0, "2025-06-01T14:00:00Z"),
                        ],
                    ),
                ),
        );
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "")
            .with_openaq_key("oaq");
        let paris = Location::new("Paris", 48.8566, 2.3522).with_country("FR");
        let options = FetchOptions {
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let env = client.fetch(&paris, options, now()).unwrap();
        let rows: Vec<(&str, ReadingKind, &str)> = env
            .pollutant_readings
            .iter()
            .map(|r| {
                (
                    r.code.as_str(),
                    r.provenance.kind,
                    r.provenance.provider.as_str(),
                )
            })
            .collect();
        assert_eq!(
            rows,
            [
                ("pm2_5", ReadingKind::Observed, "OpenAQ"),
                ("no2", ReadingKind::Observed, "OpenAQ"),
                ("pm10", ReadingKind::Modelled, "Open-Meteo"),
                ("o3", ReadingKind::Modelled, "Open-Meteo"),
                ("so2", ReadingKind::Modelled, "Open-Meteo"),
                ("co", ReadingKind::Modelled, "Open-Meteo"),
            ]
        );
        let pm = &env.pollutant_readings[0];
        assert_eq!(pm.concentration, Some(14.2));
        assert_eq!(pm.unit.as_deref(), Some("µg/m³"));
        assert_eq!(pm.averaging.as_deref(), Some("1-hour"));
        assert_eq!((pm.index_value, pm.index_category.as_deref()), (None, None));
        assert_eq!(pm.provenance.detail.as_deref(), Some("reference monitor"));
        assert_eq!(pm.provenance.station_name.as_deref(), Some("Paris 18e"));
        assert_eq!(pm.provenance.station_distance_km, Some(2.4));
        assert_eq!(
            pm.provenance.time.unwrap().to_rfc3339(),
            "2025-06-01T14:00:00+00:00"
        );
        // The headline index is still the model's: OpenAQ has no index.
        assert_eq!(env.air_quality_category.as_deref(), Some("Moderate"));
        assert_eq!(
            env.air_quality_provenance.unwrap().kind,
            ReadingKind::Modelled
        );
        assert!(env.sources.iter().any(|s| s == "OpenAQ"));
        assert!(env.sources.iter().any(|s| s == OPENMETEO_AQ_SOURCE));
    }

    #[test]
    fn openaq_failure_in_the_us_falls_back_to_airnow() {
        let airnow = json!([
            {"AQI": 61, "ParameterName": "PM2.5", "Category": {"Number": 2, "Name": "Moderate"},
             "DateObserved": "2025-06-01", "HourObserved": 9, "LocalTimeZone": "EDT",
             "ReportingArea": "Metro"}
        ]);
        let aq = json!({"utc_offset_seconds": -14400, "hourly": {"time": times(8, 4),
            "us_aqi": [50, 55, 60, 65], "pm10": [20, 21, 22, 23]}});
        let http = Arc::new(
            FixtureClient::new()
                .with(airnow::ENDPOINT, airnow)
                .with(AIR_QUALITY_ENDPOINT, aq)
                .with_status(openaq::LOCATIONS_ENDPOINT, 500),
        );
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "key")
            .with_openaq_key("oaq");
        let nyc = Location::new("NYC", 40.7, -74.0).with_country("US");
        let options = FetchOptions {
            prefer_airnow: true,
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let env = client.fetch(&nyc, options, now()).unwrap();
        let rows: Vec<(&str, &str)> = env
            .pollutant_readings
            .iter()
            .map(|r| (r.code.as_str(), r.provenance.provider.as_str()))
            .collect();
        assert_eq!(rows, [("pm2_5", "AirNow"), ("pm10", "Open-Meteo")]);
        assert!(!env.sources.iter().any(|s| s == "OpenAQ"));
        assert_eq!(env.air_quality_source.as_deref(), Some(AIRNOW_SOURCE));
    }

    #[test]
    fn openaq_with_nothing_nearby_leaves_the_model_readings() {
        let http = Arc::new(
            FixtureClient::new()
                .with(AIR_QUALITY_ENDPOINT, european_detail_payload())
                .with(openaq::LOCATIONS_ENDPOINT, openaq::tests::search(vec![])),
        );
        let client = EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "")
            .with_openaq_key("oaq");
        let paris = Location::new("Paris", 48.8566, 2.3522).with_country("FR");
        let options = FetchOptions {
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let env = client.fetch(&paris, options, now()).unwrap();
        assert_eq!(env.pollutant_readings.len(), 6);
        assert!(env
            .pollutant_readings
            .iter()
            .all(|r| r.provenance.kind == ReadingKind::Modelled));
        assert!(!env.sources.iter().any(|s| s == "OpenAQ"));
    }

    #[test]
    fn openaq_is_only_asked_with_a_key_and_pollutant_detail() {
        let http = Arc::new(
            FixtureClient::new()
                .with(AIR_QUALITY_ENDPOINT, european_detail_payload())
                .with(openaq::LOCATIONS_ENDPOINT, openaq::tests::search(vec![])),
        );
        let paris = Location::new("Paris", 48.8566, 2.3522).with_country("FR");
        let options = FetchOptions {
            include_hourly_air_quality: false,
            ..aq_only()
        };
        EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "").fetch(
            &paris,
            options,
            now(),
        );
        EnvironmentalDataClient::new(http.clone(), "AccessiWeather/2.0", "")
            .with_openaq_key("oaq")
            .fetch(
                &paris,
                FetchOptions {
                    pollutant_detail: false,
                    ..options
                },
                now(),
            );
        let log = http.request_log();
        assert_eq!(log.len(), 2);
        assert!(!log.iter().any(|u| u.contains("api.openaq.org")), "{log:?}");
    }

    #[test]
    fn openaq_readings_alone_still_count_as_data() {
        let http = Arc::new(
            FixtureClient::new()
                .with_status(AIR_QUALITY_ENDPOINT, 500)
                .with(
                    openaq::LOCATIONS_ENDPOINT,
                    openaq::tests::search(vec![paris_station()]),
                )
                .with(
                    &openaq_latest_url(4321),
                    openaq::tests::latest(4321, &[(51, 14.2, "2025-06-01T14:00:00Z")]),
                ),
        );
        let client =
            EnvironmentalDataClient::new(http, "AccessiWeather/2.0", "").with_openaq_key("oaq");
        let paris = Location::new("Paris", 48.8566, 2.3522).with_country("FR");
        let options = FetchOptions {
            include_hourly_air_quality: false,
            ..aq_only()
        };
        let env = client.fetch(&paris, options, now()).unwrap();
        assert_eq!(env.air_quality_index, None);
        assert_eq!(env.pollutant_readings.len(), 1);
        assert_eq!(env.sources, ["OpenAQ"]);
    }

    #[test]
    fn environmental_json_without_readings_still_loads() {
        let env: EnvironmentalConditions =
            serde_json::from_value(json!({"air_quality_index": 40.0, "sources": []})).unwrap();
        assert!(env.pollutant_readings.is_empty() && env.air_quality_provenance.is_none());
        let value = serde_json::to_value(&env).unwrap();
        assert!(value.get("pollutant_readings").is_none());
        assert!(value.get("air_quality_provenance").is_none());
    }
}
