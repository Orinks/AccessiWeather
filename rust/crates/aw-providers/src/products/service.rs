//! Cache-fronted text-product service shared by Forecaster Notes, National
//! Products, Advanced Lookup, notifications and the refresh pre-warm. Port of
//! `services/forecast_product_service.py` (plus
//! `_pre_warm_products_for_location` from `ui/main_window_refresh.py`).
//!
//! Failed fetches are never cached; empty results (no AFD, no SPS, no CLI
//! for a station) are, with the same per-type TTLs as Python.

use std::collections::{BTreeSet, HashMap};
use std::sync::{Arc, Mutex};

use aw_core::location::is_us_location;
use aw_core::model::{Location, TextProduct, Timestamp};
use chrono::{DateTime, Duration, Utc};
use serde_json::Value;

use super::iem::{AfosQuery, Iem, DEFAULT_IEM_BASE_URL};
use super::nws_text::{normalize_climate_station, NwsText, NWS_BASE_URL};
use super::py::{isoformat, py_float};
use super::surf::{
    fetch_openmeteo_marine_surf_conditions, format_pirate_weather_beach_conditions,
    OPENMETEO_MARINE_BASE_URL,
};
use super::{ProductError, ProductResult};
use crate::http::HttpClient;

/// `Cache()`'s default TTL, used for product types without their own.
const DEFAULT_TTL: i64 = 300;
const CLI_TTL: i64 = 3600;
const DAY: i64 = 86400;

/// Per-type TTLs in seconds (`_PRODUCT_TTLS`).
fn product_ttl(product_type: &str) -> i64 {
    match product_type {
        "AFD" | "SRF" | "SURF_CONDITIONS" => 3600,
        "HWO" => 7200,
        "SPS" => 900,
        _ => DEFAULT_TTL,
    }
}

/// Everything the service caches; each key namespace holds one variant.
#[derive(Clone)]
enum Cached {
    Current(ProductResult),
    History(Vec<TextProduct>),
    Product(Option<TextProduct>),
    Station(String),
    Stations(BTreeSet<String>),
}

type Clock = Box<dyn Fn() -> DateTime<Utc> + Send + Sync>;

/// Supplies the raw Pirate Weather forecast payload for a location, or `None`
/// when no API key is configured or the request fails.
pub type PiratePayload<'a> = &'a dyn Fn(&Location) -> Option<Value>;

pub struct ForecastProductService {
    http: Arc<dyn HttpClient>,
    pub nws_base: String,
    pub iem_base: String,
    pub marine_base: String,
    cache: Mutex<HashMap<String, (DateTime<Utc>, Cached)>>,
    clock: Clock,
}

impl ForecastProductService {
    pub fn new(http: Arc<dyn HttpClient>) -> Self {
        Self {
            http,
            nws_base: NWS_BASE_URL.into(),
            iem_base: DEFAULT_IEM_BASE_URL.into(),
            marine_base: OPENMETEO_MARINE_BASE_URL.into(),
            cache: Mutex::new(HashMap::new()),
            clock: Box::new(Utc::now),
        }
    }

    /// Replace the wall clock (cache expiry and "active now" filtering).
    pub fn with_clock(mut self, clock: impl Fn() -> DateTime<Utc> + Send + Sync + 'static) -> Self {
        self.clock = Box::new(clock);
        self
    }

    fn now(&self) -> DateTime<Utc> {
        (self.clock)()
    }

    fn nws(&self) -> NwsText<'_> {
        NwsText {
            http: self.http.as_ref(),
            base: &self.nws_base,
        }
    }

    fn iem(&self) -> Iem<'_> {
        Iem {
            http: self.http.as_ref(),
            base: &self.iem_base,
        }
    }

    fn cached(&self, key: &str) -> Option<Cached> {
        let now = self.now();
        let mut cache = self.cache.lock().unwrap();
        match cache.get(key) {
            Some((expires, _)) if *expires < now => {
                cache.remove(key);
                None
            }
            Some((_, value)) => Some(value.clone()),
            None => None,
        }
    }

    fn store(&self, key: String, value: Cached, ttl: i64) {
        let expires = self.now() + Duration::seconds(ttl);
        self.cache.lock().unwrap().insert(key, (expires, value));
    }

    fn current_key(product_type: &str, cwa_office: &str) -> String {
        format!("nws_text_product:{product_type}:{cwa_office}")
    }

    fn cli_key(station: &str) -> String {
        format!("iem_text_product:CLI:{station}:latest")
    }

    /// Cached or freshly fetched current product (`get`).
    pub fn get(&self, product_type: &str, cwa_office: &str) -> Result<ProductResult, ProductError> {
        if let Some(result) = self.peek(product_type, cwa_office) {
            return Ok(result);
        }
        let result = self.nws().text_product(product_type, Some(cwa_office))?;
        self.store(
            Self::current_key(product_type, cwa_office),
            Cached::Current(result.clone()),
            product_ttl(product_type),
        );
        Ok(result)
    }

    /// The cached current product without fetching; the notification checks
    /// read HWO and SPS this way.
    pub fn peek(&self, product_type: &str, cwa_office: &str) -> Option<ProductResult> {
        match self.cached(&Self::current_key(product_type, cwa_office))? {
            Cached::Current(result) => Some(result),
            _ => None,
        }
    }

    /// Cached or freshly fetched product history (`get_history`); a separate
    /// namespace from current products.
    pub fn get_history(
        &self,
        product_type: &str,
        cwa_office: &str,
        limit: i64,
        start: Option<&Timestamp>,
        end: Option<&Timestamp>,
    ) -> Result<Vec<TextProduct>, ProductError> {
        let key = format!(
            "nws_text_product_history:{product_type}:{cwa_office}:{limit}:{}:{}",
            start.map(isoformat).unwrap_or_default(),
            end.map(isoformat).unwrap_or_default()
        );
        if let Some(Cached::History(products)) = self.cached(&key) {
            return Ok(products);
        }
        let products = self
            .nws()
            .history(product_type, Some(cwa_office), limit, start, end)?;
        self.store(
            key,
            Cached::History(products.clone()),
            product_ttl(product_type),
        );
        Ok(products)
    }

    /// Likely CLI stations for a location: radar station, then office.
    pub fn daily_climate_station_candidates(location: &Location) -> Vec<String> {
        let mut candidates = Vec::new();
        for value in [&location.radar_station, &location.cwa_office] {
            let station = normalize_climate_station(value.as_deref());
            if !station.is_empty() && !candidates.contains(&station) {
                candidates.push(station);
            }
        }
        candidates
    }

    /// Cached or freshly fetched latest CLI for a station (a missing report
    /// is cached too).
    pub fn get_daily_climate_report(
        &self,
        station_id: &str,
    ) -> Result<Option<TextProduct>, ProductError> {
        let station = normalize_climate_station(Some(station_id));
        if station.is_empty() {
            return Ok(None);
        }
        let key = Self::cli_key(&station);
        if let Some(Cached::Product(product)) = self.cached(&key) {
            return Ok(product);
        }
        let product = self.nws().daily_climate_report(Some(&station))?;
        self.store(key, Cached::Product(product.clone()), CLI_TTL);
        Ok(product)
    }

    /// The cached CLI for a station, if one was found (notification check).
    pub fn peek_daily_climate_report(&self, station: &str) -> Option<TextProduct> {
        match self.cached(&Self::cli_key(station))? {
            Cached::Product(product) => product,
            _ => None,
        }
    }

    fn daily_climate_locations(&self) -> BTreeSet<String> {
        let key = "iem_text_product:CLI:locations";
        if let Some(Cached::Stations(stations)) = self.cached(key) {
            return stations;
        }
        let stations = self.nws().daily_climate_locations();
        self.store(key.into(), Cached::Stations(stations.clone()), DAY);
        stations
    }

    /// Try likely CLI stations for a location until a report is found.
    pub fn get_daily_climate_report_for_location(
        &self,
        location: &Location,
    ) -> Result<Option<TextProduct>, ProductError> {
        let primary = Self::daily_climate_station_candidates(location);
        let mut candidates = primary.clone();
        let location_key = format!(
            "daily_climate_location_station:{}:{}:{}",
            location.name,
            py_float(location.latitude),
            py_float(location.longitude)
        );
        if let Some(Cached::Station(station)) = self.cached(&location_key) {
            if !station.is_empty() {
                if let Some(product) = self.get_daily_climate_report(&station)? {
                    return Ok(Some(product));
                }
            }
        }
        for station in
            self.nws()
                .observation_station_ids_for_point(location.latitude, location.longitude, 12)
        {
            let station = normalize_climate_station(Some(&station));
            if !station.is_empty() && !candidates.contains(&station) {
                candidates.push(station);
            }
        }
        let cli_locations = self.daily_climate_locations();
        if !cli_locations.is_empty() {
            let indexed: Vec<String> = candidates
                .iter()
                .filter(|s| cli_locations.contains(*s))
                .cloned()
                .collect();
            if !indexed.is_empty() {
                candidates = indexed;
            }
        }
        for station in candidates {
            if let Some(product) = self.get_daily_climate_report(&station)? {
                self.store(location_key, Cached::Station(station), DAY);
                for primary_station in &primary {
                    self.store(
                        Self::cli_key(primary_station),
                        Cached::Product(Some(product.clone())),
                        CLI_TTL,
                    );
                }
                return Ok(Some(product));
            }
        }
        Ok(None)
    }

    /// Official NWS SRF when the office has one, otherwise derived surf/beach
    /// conditions (Open-Meteo Marine, then Pirate Weather). Derived summaries
    /// use `product_type = "SURF_CONDITIONS"`.
    pub fn get_surf_conditions_for_location(
        &self,
        location: &Location,
        pirate_payload: Option<PiratePayload>,
    ) -> Option<TextProduct> {
        let key = format!(
            "surf_conditions:{}:{}:{}:{}",
            location.name,
            py_float(location.latitude),
            py_float(location.longitude),
            location.cwa_office.as_deref().unwrap_or("None")
        );
        if let Some(Cached::Product(product)) = self.cached(&key) {
            return product;
        }
        let cwa_office = location
            .cwa_office
            .as_deref()
            .unwrap_or_default()
            .trim()
            .to_uppercase();
        if !cwa_office.is_empty() {
            if let Ok(ProductResult::One(Some(official))) = self.get("SRF", &cwa_office) {
                self.store(
                    key,
                    Cached::Product(Some(official.clone())),
                    product_ttl("SRF"),
                );
                return Some(official);
            }
        }
        let now = self.now().fixed_offset();
        let derived = fetch_openmeteo_marine_surf_conditions(
            self.http.as_ref(),
            &self.marine_base,
            location,
            now,
        )
        .or_else(|| {
            let payload = pirate_payload?(location)?;
            format_pirate_weather_beach_conditions(&payload, location, now)
        });
        self.store(
            key,
            Cached::Product(derived.clone()),
            product_ttl("SURF_CONDITIONS"),
        );
        derived
    }

    /// Raw IEM AFOS text for national products and advanced lookup.
    pub fn get_iem_afos(
        &self,
        product_id: &str,
        query: &AfosQuery,
    ) -> Result<TextProduct, ProductError> {
        let product_key = product_id.trim().to_uppercase();
        let key = format!("iem_text_product:AFOS:{product_key}:{query:?}");
        self.iem_cached(key, || self.iem().afos_text(&product_key, query))
    }

    /// Point-based SPC convective outlook summary.
    pub fn get_iem_spc_outlook(
        &self,
        latitude: f64,
        longitude: f64,
        day: i64,
        current: bool,
        valid_at: Option<&Timestamp>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let key = format!(
            "iem_text_product:SPC_OUTLOOK:{latitude}:{longitude}:{day}:{current}:{}:{max_items:?}",
            valid_at.map(isoformat).unwrap_or_default()
        );
        self.iem_cached(key, || {
            self.iem()
                .spc_outlook(latitude, longitude, day, current, valid_at, max_items)
        })
    }

    /// SPC mesoscale discussions: active now, or within `start..end` when
    /// `active_only` is false.
    pub fn get_iem_spc_mcds(
        &self,
        latitude: f64,
        longitude: f64,
        active_only: bool,
        start: Option<&Timestamp>,
        end: Option<&Timestamp>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let key = format!(
            "iem_text_product:SPC_MCD:{latitude}:{longitude}:{active_only}:{}:{}:{max_items:?}",
            start.map(isoformat).unwrap_or_default(),
            end.map(isoformat).unwrap_or_default()
        );
        let active_at = active_only.then(|| self.now());
        self.iem_cached(key, || {
            self.iem()
                .spc_mcds(latitude, longitude, active_at, start, end, max_items)
        })
    }

    /// SPC watches valid at `valid_at` (default: now).
    pub fn get_iem_spc_watches(
        &self,
        latitude: f64,
        longitude: f64,
        valid_at: Option<&Timestamp>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let key = format!(
            "iem_text_product:SPC_WATCHES:{latitude}:{longitude}:{}:{max_items:?}",
            valid_at.map_or("latest".to_string(), isoformat)
        );
        let active_at = valid_at.map_or_else(|| self.now(), |v| v.with_timezone(&Utc));
        self.iem_cached(key, || {
            self.iem()
                .spc_watches(latitude, longitude, active_at, max_items)
        })
    }

    /// WPC excessive rainfall outlook for `day`, current or at `valid_at`.
    pub fn get_iem_wpc_outlook(
        &self,
        latitude: f64,
        longitude: f64,
        day: i64,
        valid_at: Option<&Timestamp>,
        limit: i64,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let key = format!(
            "iem_text_product:WPC_ERO:{latitude}:{longitude}:{day}:{}:{limit}:{max_items:?}",
            valid_at.map_or("latest".to_string(), isoformat)
        );
        let now = self.now();
        self.iem_cached(key, || {
            self.iem()
                .wpc_outlook(latitude, longitude, day, valid_at, now, limit, max_items)
        })
    }

    /// WPC mesoscale precipitation discussions: active now, or within
    /// `start..end` when `active_only` is false.
    pub fn get_iem_wpc_mpds(
        &self,
        latitude: f64,
        longitude: f64,
        active_only: bool,
        start: Option<&Timestamp>,
        end: Option<&Timestamp>,
        max_items: Option<i64>,
    ) -> Result<TextProduct, ProductError> {
        let key = format!(
            "iem_text_product:WPC_MPD:{latitude}:{longitude}:{active_only}:{}:{}:{max_items:?}",
            start.map(isoformat).unwrap_or_default(),
            end.map(isoformat).unwrap_or_default()
        );
        let active_at = active_only.then(|| self.now());
        self.iem_cached(key, || {
            self.iem()
                .wpc_mpds(latitude, longitude, active_at, start, end, max_items)
        })
    }

    /// IEM lookups share the AFD/SPS TTLs of the Python service.
    fn iem_cached(
        &self,
        key: String,
        fetch: impl FnOnce() -> Result<TextProduct, ProductError>,
    ) -> Result<TextProduct, ProductError> {
        if let Some(Cached::Product(Some(product))) = self.cached(&key) {
            return Ok(product);
        }
        let ttl = if key.starts_with("iem_text_product:AFOS:") {
            product_ttl("AFD")
        } else {
            product_ttl("SPS")
        };
        let product = fetch()?;
        self.store(key, Cached::Product(Some(product.clone())), ttl);
        Ok(product)
    }

    /// Warm AFD/HWO/SPS/SRF and the daily climate report for a saved
    /// location in parallel. Non-US locations and locations without an office
    /// are skipped; every failure is isolated and ignored.
    pub fn pre_warm_location(&self, location: &Location) {
        if !is_us_location(location) {
            return;
        }
        let Some(cwa_office) = location.cwa_office.as_deref().filter(|c| !c.is_empty()) else {
            return;
        };
        std::thread::scope(|scope| {
            for product_type in ["AFD", "HWO", "SPS", "SRF"] {
                scope.spawn(move || {
                    if let Err(err) = self.get(product_type, cwa_office) {
                        tracing::debug!(
                            "Pre-warm {product_type} for {} ({cwa_office}) failed: {err}",
                            location.name
                        );
                    }
                });
            }
            scope.spawn(|| {
                if let Err(err) = self.get_daily_climate_report_for_location(location) {
                    tracing::debug!(
                        "Pre-warm daily climate report for {} ({cwa_office}) failed: {err}",
                        location.name
                    );
                }
            });
        });
    }
}
