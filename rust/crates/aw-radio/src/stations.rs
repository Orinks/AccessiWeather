//! Station model and in-memory station directory.
//!
//! Ports `noaa_radio/stations.py` and `noaa_radio/station_db.py`.

use std::collections::HashMap;

use serde::Serialize;

use crate::data::STATIONS;

/// Earth's mean radius in kilometres.
const EARTH_RADIUS_KM: f64 = 6371.0;

/// A NOAA Weather Radio transmitter.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Station {
    pub call_sign: String,
    /// Broadcast frequency in MHz, e.g. 162.550.
    pub frequency: f64,
    pub name: String,
    pub lat: f64,
    pub lon: f64,
    pub state: String,
}

impl Station {
    pub fn new(
        call_sign: &str,
        frequency: f64,
        name: &str,
        lat: f64,
        lon: f64,
        state: &str,
    ) -> Self {
        Self {
            call_sign: call_sign.to_string(),
            frequency,
            name: name.to_string(),
            lat,
            lon,
            state: state.to_string(),
        }
    }
}

/// A station paired with its distance from a query point.
#[derive(Debug, Clone, PartialEq)]
pub struct StationResult {
    pub station: Station,
    pub distance_km: f64,
}

/// Great-circle distance in km between two points.
pub fn haversine(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let (lat1_r, lon1_r) = (lat1.to_radians(), lon1.to_radians());
    let (lat2_r, lon2_r) = (lat2.to_radians(), lon2.to_radians());
    let dlat = lat2_r - lat1_r;
    let dlon = lon2_r - lon1_r;
    let a = (dlat / 2.0).sin().powi(2) + lat1_r.cos() * lat2_r.cos() * (dlon / 2.0).sin().powi(2);
    EARTH_RADIUS_KM * 2.0 * a.sqrt().asin()
}

/// Match Python's `_COORDINATE_QUERY_RE`: `lat, lon` where each part is
/// `[+-]?\d+(\.\d+)?`, surrounded by optional whitespace.
fn parse_coordinate_search(query: &str) -> Option<(f64, f64)> {
    fn number(part: &str) -> Option<f64> {
        let part = part.trim();
        let digits = part.strip_prefix(['+', '-']).unwrap_or(part);
        let (int, frac) = match digits.split_once('.') {
            Some((int, frac)) => (int, Some(frac)),
            None => (digits, None),
        };
        let all_digits = |s: &str| !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit());
        if !all_digits(int) || frac.is_some_and(|f| !all_digits(f)) {
            return None;
        }
        part.parse().ok()
    }
    let (lat, lon) = query.split_once(',')?;
    Some((number(lat)?, number(lon)?))
}

fn take(stations: Vec<Station>, limit: Option<usize>) -> Vec<Station> {
    match limit {
        Some(n) => stations.into_iter().take(n).collect(),
        None => stations,
    }
}

/// In-memory database of NOAA Weather Radio stations.
#[derive(Debug, Clone)]
pub struct StationDatabase {
    stations: Vec<Station>,
}

impl Default for StationDatabase {
    fn default() -> Self {
        Self::new()
    }
}

impl StationDatabase {
    /// The bundled station list.
    pub fn new() -> Self {
        let stations = STATIONS
            .iter()
            .map(|&(cs, freq, name, lat, lon, state)| Station::new(cs, freq, name, lat, lon, state))
            .collect();
        Self { stations }
    }

    /// A database over a caller-supplied station list (tests, custom data).
    pub fn with_stations(stations: Vec<Station>) -> Self {
        Self { stations }
    }

    pub fn get_all_stations(&self) -> Vec<Station> {
        self.stations.clone()
    }

    /// Stations in a US state or territory (case-insensitive).
    pub fn get_stations_by_state(&self, state: &str) -> Vec<Station> {
        let state_upper = state.to_uppercase();
        self.stations
            .iter()
            .filter(|s| s.state.to_uppercase() == state_upper)
            .cloned()
            .collect()
    }

    /// Stations matching call signs, in the caller's order, skipping blanks,
    /// duplicates and unknown call signs.
    pub fn get_stations_by_call_signs<S: AsRef<str>>(&self, call_signs: &[S]) -> Vec<Station> {
        // Later entries win, like the Python dict comprehension.
        let by_call_sign: HashMap<String, &Station> = self
            .stations
            .iter()
            .map(|s| (s.call_sign.to_uppercase(), s))
            .collect();
        let mut seen = Vec::new();
        let mut stations = Vec::new();
        for call_sign in call_signs {
            let normalized = call_sign.as_ref().trim().to_uppercase();
            if normalized.is_empty() || seen.contains(&normalized) {
                continue;
            }
            if let Some(station) = by_call_sign.get(&normalized) {
                stations.push((*station).clone());
                seen.push(normalized);
            }
        }
        stations
    }

    /// Search by call sign, city/name, state, or an explicit `lat, lon`.
    pub fn search(&self, query: &str, limit: Option<usize>) -> Vec<Station> {
        let normalized = query.trim();
        if normalized.is_empty() {
            return take(self.get_all_stations(), limit);
        }

        if let Some((lat, lon)) = parse_coordinate_search(normalized) {
            if (-90.0..=90.0).contains(&lat) && (-180.0..=180.0).contains(&lon) {
                return self
                    .find_nearest(lat, lon, limit)
                    .into_iter()
                    .map(|r| r.station)
                    .collect();
            }
        }

        let upper = normalized.to_uppercase();
        let lower = normalized.to_lowercase();
        let matches = self
            .stations
            .iter()
            .filter(|s| {
                s.call_sign.to_uppercase().contains(&upper)
                    || upper == s.state.to_uppercase()
                    || s.name.to_lowercase().contains(&lower)
            })
            .cloned()
            .collect();
        take(matches, limit)
    }

    /// Nearest stations, closest first (stable for equal distances).
    pub fn find_nearest(&self, lat: f64, lon: f64, limit: Option<usize>) -> Vec<StationResult> {
        let mut results: Vec<StationResult> = self
            .stations
            .iter()
            .map(|s| StationResult {
                station: s.clone(),
                distance_km: haversine(lat, lon, s.lat, s.lon),
            })
            .collect();
        results.sort_by(|a, b| a.distance_km.total_cmp(&b.distance_km));
        if let Some(n) = limit {
            results.truncate(n);
        }
        results
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn haversine_known_distances() {
        assert_eq!(haversine(40.0, -74.0, 40.0, -74.0), 0.0);
        // New York to Los Angeles is about 3936 km.
        let d = haversine(40.7128, -74.0060, 34.0522, -118.2437);
        assert!((d - 3936.0).abs() < 50.0, "{d}");
        let d = haversine(40.7128, -74.0060, 40.7228, -74.0060);
        assert!(d > 1.0 && d < 1.2, "{d}");
    }

    #[test]
    fn default_database_matches_python_invariants() {
        let db = StationDatabase::new();
        let all = db.get_all_stations();
        assert!(all.len() >= 100);
        let mut call_signs: Vec<_> = all.iter().map(|s| s.call_sign.clone()).collect();
        call_signs.sort();
        call_signs.dedup();
        assert_eq!(call_signs.len(), all.len(), "duplicate call signs");
        for s in &all {
            assert!((162.0..=163.0).contains(&s.frequency), "{s:?}");
            assert!(!s.name.is_empty() && s.state.len() == 2);
        }
    }

    #[test]
    fn state_filter_is_case_insensitive() {
        let db = StationDatabase::new();
        let ny = db.get_stations_by_state("ny");
        assert!(!ny.is_empty());
        assert!(ny.iter().all(|s| s.state == "NY"));
        assert!(db.get_stations_by_state("ZZ").is_empty());
    }

    #[test]
    fn nearest_is_sorted_and_limited() {
        let db = StationDatabase::new();
        let results = db.find_nearest(40.7128, -74.0060, Some(5));
        assert_eq!(results.len(), 5);
        assert_eq!(results[0].station.call_sign, "KWO35");
        assert!(results
            .windows(2)
            .all(|w| w[0].distance_km <= w[1].distance_km));
        assert_eq!(
            db.find_nearest(0.0, 0.0, None).len(),
            db.get_all_stations().len()
        );
    }

    #[test]
    fn search_modes() {
        let db = StationDatabase::new();
        assert_eq!(db.search("kec49", None)[0].call_sign, "KEC49");
        assert_eq!(db.search("", Some(3)).len(), 3);
        assert!(db.search("TX", None).iter().all(|s| s.state == "TX"));
        assert!(db
            .search("austin", None)
            .iter()
            .any(|s| s.call_sign == "WXK27"));
        assert_eq!(
            db.search(" 30.2672 , -97.7431 ", Some(1))[0].call_sign,
            "WXK27"
        );
        // Out-of-range coordinates fall through to a text search.
        assert!(db.search("91, 0", None).is_empty());
    }

    #[test]
    fn call_sign_lookup_keeps_requested_order() {
        let db = StationDatabase::new();
        let found = db.get_stations_by_call_signs(&["wxk27", " ", "KEC49", "WXK27", "NOPE"]);
        let call_signs: Vec<_> = found.iter().map(|s| s.call_sign.as_str()).collect();
        assert_eq!(call_signs, ["WXK27", "KEC49"]);
    }
}
