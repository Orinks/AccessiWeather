use serde::{Deserialize, Serialize};

/// A saved or searched location. Mirrors the Python `Location` dataclass and
/// its JSON shape in `accessiweather.json`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Location {
    pub name: String,
    pub latitude: f64,
    pub longitude: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timezone: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub country_code: Option<String>,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub marine_mode: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub forecast_zone_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cwa_office: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub county_zone_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fire_zone_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub radar_station: Option<String>,
}

impl Location {
    pub fn new(name: impl Into<String>, latitude: f64, longitude: f64) -> Self {
        Self {
            name: name.into(),
            latitude,
            longitude,
            timezone: None,
            country_code: None,
            marine_mode: false,
            forecast_zone_id: None,
            cwa_office: None,
            county_zone_id: None,
            fire_zone_id: None,
            radar_station: None,
        }
    }

    pub fn with_country(mut self, code: impl Into<String>) -> Self {
        self.country_code = Some(code.into().to_uppercase());
        self
    }

    /// Normalise fields loaded from disk (uppercase country code, as Python does).
    pub fn normalize(&mut self) {
        if let Some(code) = self.country_code.as_mut() {
            *code = code.to_uppercase();
        }
    }

    pub fn valid_coordinates(&self) -> bool {
        (-90.0..=90.0).contains(&self.latitude) && (-180.0..=180.0).contains(&self.longitude)
    }
}

/// Whether a location should use US/NWS weather surfaces.
///
/// Country codes are authoritative. The coordinate fallback is intentionally
/// conservative near the Canadian border. Ported 1:1 from
/// `accessiweather.location_classification.is_us_location`.
pub fn is_us_location(location: &Location) -> bool {
    if let Some(code) = location.country_code.as_deref().filter(|c| !c.is_empty()) {
        return code.eq_ignore_ascii_case("US");
    }
    let lat = location.latitude;
    let lon = location.longitude;

    let in_alaska = (51.0..=71.5).contains(&lat) && (-172.0..=-130.0).contains(&lon);
    let in_hawaii = (18.0..=23.0).contains(&lat) && (-161.0..=-154.0).contains(&lon);
    if in_alaska || in_hawaii {
        return true;
    }
    let in_continental = (24.0..=49.0).contains(&lat) && (-125.0..=-66.0).contains(&lon);
    if !in_continental {
        return false;
    }
    let western_canada_strip = lat >= 48.0 && (-125.0..=-122.0).contains(&lon);
    if western_canada_strip {
        return false;
    }
    let eastern_canada_strip = lat >= 43.0 && lon > -95.0 && lon < -70.0;
    !eastern_canada_strip
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn country_code_is_authoritative() {
        assert!(is_us_location(
            &Location::new("x", 45.0, -75.0).with_country("us")
        ));
        assert!(!is_us_location(
            &Location::new("x", 40.0, -100.0).with_country("CA")
        ));
    }

    #[test]
    fn border_strips_fall_back_to_non_us_without_country() {
        assert!(!is_us_location(&Location::new("Victoria", 48.43, -123.37)));
        assert!(!is_us_location(&Location::new("Toronto", 43.65, -79.38)));
        assert!(is_us_location(&Location::new("Denver", 39.74, -104.99)));
        assert!(is_us_location(&Location::new("Anchorage", 61.2, -149.9)));
        assert!(!is_us_location(&Location::new("London", 51.5, -0.12)));
    }

    #[test]
    fn json_round_trip_matches_python_shape() {
        let loc = Location::new("Home", 1.5, -2.5).with_country("us");
        let json = serde_json::to_value(&loc).unwrap();
        assert_eq!(
            json,
            serde_json::json!({"name":"Home","latitude":1.5,"longitude":-2.5,"country_code":"US"})
        );
    }
}
