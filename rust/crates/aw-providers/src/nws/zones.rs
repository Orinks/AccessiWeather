//! NWS zone metadata on a location (`services/zone_enrichment_service.py`):
//! mapping `/points` properties onto the six stored fields and working out
//! which ones drifted. The refresh path ([`super::NwsClient::all_data_parallel`])
//! reports drift through [`super::ZoneDriftSink`].

use aw_core::model::Location;
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// The zone fields of a [`Location`]; `None` means "no value / no change".
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ZoneFields {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timezone: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cwa_office: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub forecast_zone_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub county_zone_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fire_zone_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub radar_station: Option<String>,
}

impl ZoneFields {
    fn slots(&self) -> [&Option<String>; 6] {
        [
            &self.timezone,
            &self.cwa_office,
            &self.forecast_zone_id,
            &self.county_zone_id,
            &self.fire_zone_id,
            &self.radar_station,
        ]
    }

    pub fn is_empty(&self) -> bool {
        self.slots().iter().all(|s| s.is_none())
    }

    /// `dataclasses.replace(location, **fields)` for the fields that are set
    /// (`LocationOperations.update_zone_metadata`).
    pub fn apply_to(&self, location: &mut Location) {
        let targets = [
            (&mut location.timezone, &self.timezone),
            (&mut location.cwa_office, &self.cwa_office),
            (&mut location.forecast_zone_id, &self.forecast_zone_id),
            (&mut location.county_zone_id, &self.county_zone_id),
            (&mut location.fire_zone_id, &self.fire_zone_id),
            (&mut location.radar_station, &self.radar_station),
        ];
        for (slot, value) in targets {
            if let Some(v) = value {
                *slot = Some(v.clone());
            }
        }
    }
}

/// `_last_path_segment`: "https://api.weather.gov/zones/forecast/PAZ106" -> "PAZ106".
pub fn last_path_segment(url: &Value) -> Option<String> {
    let trimmed = url.as_str()?.trim_end_matches('/');
    let segment = trimmed.rsplit('/').next().unwrap_or(trimmed);
    (!segment.is_empty()).then(|| segment.to_string())
}

fn non_empty_str(v: &Value) -> Option<String> {
    v.as_str().filter(|s| !s.is_empty()).map(str::to_string)
}

/// `_extract_zone_fields`: map `/points` `properties` onto the zone fields.
pub fn extract_zone_fields(properties: &Value) -> ZoneFields {
    ZoneFields {
        timezone: non_empty_str(&properties["timeZone"]),
        cwa_office: non_empty_str(&properties["cwa"]),
        forecast_zone_id: last_path_segment(&properties["forecastZone"]),
        county_zone_id: last_path_segment(&properties["county"]),
        fire_zone_id: last_path_segment(&properties["fireWeatherZone"]),
        radar_station: non_empty_str(&properties["radarStation"]),
    }
}

/// `diff_zone_fields`: the fresh values that differ from what is stored.
/// A missing fresh value never clears a stored one.
pub fn diff_zone_fields(stored: &Location, fresh: &ZoneFields) -> ZoneFields {
    let changed = |stored: &Option<String>, fresh: &Option<String>| match fresh {
        Some(f) if stored.as_ref() != Some(f) => Some(f.clone()),
        _ => None,
    };
    ZoneFields {
        timezone: changed(&stored.timezone, &fresh.timezone),
        cwa_office: changed(&stored.cwa_office, &fresh.cwa_office),
        forecast_zone_id: changed(&stored.forecast_zone_id, &fresh.forecast_zone_id),
        county_zone_id: changed(&stored.county_zone_id, &fresh.county_zone_id),
        fire_zone_id: changed(&stored.fire_zone_id, &fresh.fire_zone_id),
        radar_station: changed(&stored.radar_station, &fresh.radar_station),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn full() -> ZoneFields {
        ZoneFields {
            timezone: Some("America/New_York".into()),
            cwa_office: Some("PHI".into()),
            forecast_zone_id: Some("PAZ106".into()),
            county_zone_id: Some("PAC091".into()),
            fire_zone_id: Some("PAZ106".into()),
            radar_station: Some("KDIX".into()),
        }
    }

    // tests/test_zone_enrichment_service.py
    #[test]
    fn last_segment_handles_slashes_and_junk() {
        let seg = |v: Value| last_path_segment(&v);
        assert_eq!(
            seg(json!("https://api.weather.gov/zones/forecast/PAZ106")).as_deref(),
            Some("PAZ106")
        );
        assert_eq!(
            seg(json!("https://api.weather.gov/zones/county/PAC091/")).as_deref(),
            Some("PAC091")
        );
        assert_eq!(seg(json!(null)), None);
        assert_eq!(seg(json!("")), None);
        assert_eq!(seg(json!(12345)), None);
    }

    #[test]
    fn extract_maps_points_properties() {
        let props = json!({
            "timeZone": "America/New_York", "cwa": "PHI", "radarStation": "KDIX",
            "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
            "county": "https://api.weather.gov/zones/county/PAC091",
            "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
        });
        assert_eq!(extract_zone_fields(&props), full());
        let partial = extract_zone_fields(
            &json!({"cwa": "PHI", "timeZone": "America/New_York", "radarStation": ""}),
        );
        assert_eq!(partial.cwa_office.as_deref(), Some("PHI"));
        assert_eq!(partial.forecast_zone_id, None);
        assert_eq!(partial.radar_station, None);
    }

    // tests/test_zone_enrichment_drift.py
    #[test]
    fn diff_populates_overwrites_and_never_clears() {
        let mut stored = Location::new("Philadelphia, PA", 39.95, -75.16);
        assert_eq!(
            diff_zone_fields(&stored, &full()),
            full(),
            "legacy location gets everything"
        );

        full().apply_to(&mut stored);
        assert!(diff_zone_fields(&stored, &full()).is_empty());

        let fresh = ZoneFields {
            cwa_office: Some("LWX".into()),
            ..full()
        };
        assert_eq!(
            diff_zone_fields(&stored, &fresh),
            ZoneFields {
                cwa_office: Some("LWX".into()),
                ..Default::default()
            }
        );
        assert!(diff_zone_fields(&stored, &ZoneFields::default()).is_empty());

        stored.timezone = None;
        let only_tz = diff_zone_fields(&stored, &full());
        assert_eq!(
            only_tz,
            ZoneFields {
                timezone: Some("America/New_York".into()),
                ..Default::default()
            }
        );
        only_tz.apply_to(&mut stored);
        assert_eq!(stored.timezone.as_deref(), Some("America/New_York"));
        assert_eq!(stored.cwa_office.as_deref(), Some("PHI"));
    }
}
