//! Legacy National Weather Service client against the old `aw_core::weather`
//! model, kept only for `weather_client.rs` until the orchestration rewrite
//! lands. New code uses [`crate::nws`].

use aw_core::alerts::{WeatherAlert, WeatherAlerts};
use aw_core::units::wind_direction_to_cardinal;
use aw_core::weather::{
    CurrentConditions, Forecast, ForecastPeriod, HourlyForecast, HourlyForecastPeriod,
};
use aw_core::Location;
use chrono::{DateTime, Utc};
use serde_json::Value;

use crate::http::{HttpClient, HttpError};

pub const BASE_URL: &str = "https://api.weather.gov";
pub const SOURCE: &str = "nws";

/// Metadata returned by `/points/{lat},{lon}`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct PointInfo {
    pub forecast_url: Option<String>,
    pub forecast_hourly_url: Option<String>,
    pub stations_url: Option<String>,
    pub forecast_zone_id: Option<String>,
    pub county_zone_id: Option<String>,
    pub fire_zone_id: Option<String>,
    pub cwa_office: Option<String>,
    pub radar_station: Option<String>,
    pub timezone: Option<String>,
}

pub struct NwsClient<'a> {
    http: &'a dyn HttpClient,
    base: String,
}

fn str_at<'v>(v: &'v Value, path: &[&str]) -> Option<&'v str> {
    let mut cur = v;
    for key in path {
        cur = cur.get(key)?;
    }
    cur.as_str()
}

fn f64_at(v: &Value, path: &[&str]) -> Option<f64> {
    let mut cur = v;
    for key in path {
        cur = cur.get(key)?;
    }
    cur.as_f64()
}

fn zone_id(url: Option<&str>) -> Option<String> {
    url.and_then(|u| u.rsplit('/').next())
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn parse_time(s: Option<&str>) -> Option<DateTime<Utc>> {
    s.and_then(|t| DateTime::parse_from_rfc3339(t).ok())
        .map(|t| t.with_timezone(&Utc))
}

/// Convert an NWS quantitative value into the requested unit.
fn quantity_in(v: &Value, key: &str, to: Unit) -> Option<f64> {
    let q = v.get(key)?;
    let value = q.get("value")?.as_f64()?;
    let code = q.get("unitCode").and_then(Value::as_str).unwrap_or("");
    Some(match (code.rsplit(':').next().unwrap_or(code), to) {
        ("degC", Unit::F) => value * 9.0 / 5.0 + 32.0,
        ("degF", Unit::F) => value,
        ("degC", Unit::C) => value,
        ("degF", Unit::C) => (value - 32.0) * 5.0 / 9.0,
        ("m_s-1", Unit::Mph) => value * 2.23694,
        ("km_h-1", Unit::Mph) => value * 0.621371,
        ("mi_h-1", Unit::Mph) => value,
        ("m_s-1", Unit::Kph) => value * 3.6,
        ("km_h-1", Unit::Kph) => value,
        ("mi_h-1", Unit::Kph) => value * 1.609344,
        ("Pa", Unit::Mb) => value / 100.0,
        ("Pa", Unit::InHg) => value / 3386.389,
        ("m", Unit::Miles) => value / 1609.344,
        ("m", Unit::Km) => value / 1000.0,
        ("m", Unit::Inches) => value * 39.3701,
        ("m", Unit::Mm) => value * 1000.0,
        ("mm", Unit::Inches) => value / 25.4,
        ("mm", Unit::Mm) => value,
        ("percent", Unit::Percent) => value,
        ("degree_(angle)", Unit::Degrees) => value,
        _ => value,
    })
}

#[derive(Clone, Copy)]
enum Unit {
    F,
    C,
    Mph,
    Kph,
    Mb,
    InHg,
    Miles,
    Km,
    Inches,
    Mm,
    Percent,
    Degrees,
}

impl<'a> NwsClient<'a> {
    pub fn new(http: &'a dyn HttpClient) -> Self {
        Self {
            http,
            base: BASE_URL.to_string(),
        }
    }

    pub fn with_base(mut self, base: &str) -> Self {
        self.base = base.trim_end_matches('/').to_string();
        self
    }

    pub fn points(&self, location: &Location) -> Result<PointInfo, HttpError> {
        let url = format!(
            "{}/points/{:.4},{:.4}",
            self.base, location.latitude, location.longitude
        );
        let v = self.http.get_json(&url)?;
        let p = v.get("properties").unwrap_or(&Value::Null);
        Ok(PointInfo {
            forecast_url: str_at(p, &["forecast"]).map(str::to_string),
            forecast_hourly_url: str_at(p, &["forecastHourly"]).map(str::to_string),
            stations_url: str_at(p, &["observationStations"]).map(str::to_string),
            forecast_zone_id: zone_id(str_at(p, &["forecastZone"])),
            county_zone_id: zone_id(str_at(p, &["county"])),
            fire_zone_id: zone_id(str_at(p, &["fireWeatherZone"])),
            cwa_office: str_at(p, &["cwa"]).map(str::to_string),
            radar_station: str_at(p, &["radarStation"]).map(str::to_string),
            timezone: str_at(p, &["timeZone"]).map(str::to_string),
        })
    }

    pub fn current_conditions(
        &self,
        point: &PointInfo,
    ) -> Result<Option<CurrentConditions>, HttpError> {
        let Some(stations_url) = &point.stations_url else {
            return Ok(None);
        };
        let stations = self.http.get_json(stations_url)?;
        let Some(features) = stations.get("features").and_then(Value::as_array) else {
            return Ok(None);
        };
        // Try the nearest few stations until one has a usable observation.
        for feature in features.iter().take(3) {
            let Some(station_id) = str_at(feature, &["properties", "stationIdentifier"]) else {
                continue;
            };
            let url = format!("{}/stations/{}/observations/latest", self.base, station_id);
            match self.http.get_json(&url) {
                Ok(obs) => {
                    let mut current = parse_observation(&obs);
                    if current.has_data() {
                        current.station_id = Some(station_id.to_string());
                        current.source = Some(SOURCE.into());
                        current.fill_unit_pairs();
                        return Ok(Some(current));
                    }
                }
                Err(e) => tracing::warn!("NWS observation for {station_id} failed: {e}"),
            }
        }
        Ok(None)
    }

    pub fn forecast(&self, point: &PointInfo) -> Result<Option<Forecast>, HttpError> {
        let Some(url) = &point.forecast_url else {
            return Ok(None);
        };
        let v = self.http.get_json(url)?;
        Ok(Some(parse_forecast(&v)))
    }

    pub fn hourly_forecast(&self, point: &PointInfo) -> Result<Option<HourlyForecast>, HttpError> {
        let Some(url) = &point.forecast_hourly_url else {
            return Ok(None);
        };
        let v = self.http.get_json(url)?;
        Ok(Some(parse_hourly(&v)))
    }

    pub fn alerts(&self, location: &Location) -> Result<WeatherAlerts, HttpError> {
        let url = format!(
            "{}/alerts/active?point={:.4},{:.4}",
            self.base, location.latitude, location.longitude
        );
        let v = self.http.get_json(&url)?;
        Ok(parse_alerts(&v))
    }

    /// Area Forecast Discussion text for the office, if any.
    pub fn discussion(&self, point: &PointInfo) -> Result<Option<String>, HttpError> {
        let Some(office) = &point.cwa_office else {
            return Ok(None);
        };
        let list = self.http.get_json(&format!(
            "{}/products/types/AFD/locations/{}",
            self.base, office
        ))?;
        let Some(id) = list
            .get("@graph")
            .and_then(Value::as_array)
            .and_then(|g| g.first())
            .and_then(|p| p.get("id"))
            .and_then(Value::as_str)
        else {
            return Ok(None);
        };
        let product = self
            .http
            .get_json(&format!("{}/products/{}", self.base, id))?;
        Ok(product
            .get("productText")
            .and_then(Value::as_str)
            .map(str::to_string))
    }
}

pub fn parse_observation(obs: &Value) -> CurrentConditions {
    let p = obs.get("properties").unwrap_or(obs);
    let wind_dir = quantity_in(p, "windDirection", Unit::Degrees);
    CurrentConditions {
        temperature_f: quantity_in(p, "temperature", Unit::F),
        temperature_c: quantity_in(p, "temperature", Unit::C),
        condition: str_at(p, &["textDescription"])
            .filter(|s| !s.is_empty())
            .map(str::to_string),
        humidity: quantity_in(p, "relativeHumidity", Unit::Percent),
        dewpoint_f: quantity_in(p, "dewpoint", Unit::F),
        dewpoint_c: quantity_in(p, "dewpoint", Unit::C),
        wind_speed_mph: quantity_in(p, "windSpeed", Unit::Mph),
        wind_speed_kph: quantity_in(p, "windSpeed", Unit::Kph),
        wind_direction: wind_dir.map(|d| wind_direction_to_cardinal(Some(d))),
        wind_gust_mph: quantity_in(p, "windGust", Unit::Mph),
        wind_gust_kph: quantity_in(p, "windGust", Unit::Kph),
        pressure_in: quantity_in(p, "barometricPressure", Unit::InHg),
        pressure_mb: quantity_in(p, "barometricPressure", Unit::Mb),
        wind_chill_f: quantity_in(p, "windChill", Unit::F),
        wind_chill_c: quantity_in(p, "windChill", Unit::C),
        heat_index_f: quantity_in(p, "heatIndex", Unit::F),
        heat_index_c: quantity_in(p, "heatIndex", Unit::C),
        visibility_miles: quantity_in(p, "visibility", Unit::Miles),
        visibility_km: quantity_in(p, "visibility", Unit::Km),
        precipitation_in: quantity_in(p, "precipitationLastHour", Unit::Inches),
        precipitation_mm: quantity_in(p, "precipitationLastHour", Unit::Mm),
        observed_at: parse_time(str_at(p, &["timestamp"])),
        ..Default::default()
    }
}

fn parse_period(p: &Value) -> ForecastPeriod {
    let temp = f64_at(p, &["temperature"]).or_else(|| f64_at(p, &["temperature", "value"]));
    let unit = str_at(p, &["temperatureUnit"]).unwrap_or("F").to_string();
    let wind_speed = str_at(p, &["windSpeed"]).map(str::to_string);
    let wind_speed_mph = wind_speed.as_deref().and_then(parse_wind_speed_text);
    ForecastPeriod {
        name: str_at(p, &["name"]).unwrap_or("").to_string(),
        temperature: temp,
        temperature_low: None,
        temperature_unit: unit,
        short_forecast: str_at(p, &["shortForecast"]).map(str::to_string),
        detailed_forecast: str_at(p, &["detailedForecast"]).map(str::to_string),
        wind_speed,
        wind_speed_mph,
        wind_direction: str_at(p, &["windDirection"]).map(str::to_string),
        start_time: parse_time(str_at(p, &["startTime"])),
        end_time: parse_time(str_at(p, &["endTime"])),
        precipitation_probability: f64_at(p, &["probabilityOfPrecipitation", "value"]),
        precipitation_amount_in: None,
        uv_index_max: None,
        is_daytime: p.get("isDaytime").and_then(Value::as_bool),
    }
}

/// "10 to 15 mph" -> 15, "5 mph" -> 5.
fn parse_wind_speed_text(text: &str) -> Option<f64> {
    text.split_whitespace()
        .filter_map(|tok| tok.parse::<f64>().ok())
        .fold(None, |acc, v| Some(acc.map_or(v, |a: f64| a.max(v))))
}

pub fn parse_forecast(v: &Value) -> Forecast {
    let p = v.get("properties").unwrap_or(v);
    let periods = p
        .get("periods")
        .and_then(Value::as_array)
        .map(|arr| arr.iter().map(parse_period).collect())
        .unwrap_or_default();
    Forecast {
        periods,
        generated_at: parse_time(str_at(p, &["generatedAt"])),
        source: Some(SOURCE.into()),
    }
}

pub fn parse_hourly(v: &Value) -> HourlyForecast {
    let p = v.get("properties").unwrap_or(v);
    let periods = p
        .get("periods")
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(|per| {
                    let start = parse_time(str_at(per, &["startTime"]))?;
                    let wind_speed = str_at(per, &["windSpeed"]).map(str::to_string);
                    Some(HourlyForecastPeriod {
                        start_time: start,
                        temperature: f64_at(per, &["temperature"]),
                        temperature_unit: str_at(per, &["temperatureUnit"])
                            .unwrap_or("F")
                            .to_string(),
                        short_forecast: str_at(per, &["shortForecast"]).map(str::to_string),
                        wind_speed_mph: wind_speed.as_deref().and_then(parse_wind_speed_text),
                        wind_speed,
                        wind_direction: str_at(per, &["windDirection"]).map(str::to_string),
                        humidity: f64_at(per, &["relativeHumidity", "value"]),
                        precipitation_probability: f64_at(
                            per,
                            &["probabilityOfPrecipitation", "value"],
                        ),
                        pressure_mb: None,
                        pressure_in: None,
                    })
                })
                .collect()
        })
        .unwrap_or_default();
    HourlyForecast {
        periods,
        generated_at: parse_time(str_at(p, &["generatedAt"])),
        source: Some(SOURCE.into()),
    }
}

fn string_list(v: Option<&Value>) -> Vec<String> {
    v.and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

pub fn parse_alerts(v: &Value) -> WeatherAlerts {
    let mut alerts = WeatherAlerts::default();
    let Some(features) = v.get("features").and_then(Value::as_array) else {
        return alerts;
    };
    for f in features {
        let p = f.get("properties").unwrap_or(f);
        let params = p.get("parameters").unwrap_or(&Value::Null);
        let event = str_at(p, &["event"]).map(str::to_string);
        let headline = str_at(p, &["headline"]).map(str::to_string);
        alerts.alerts.push(WeatherAlert {
            id: str_at(p, &["id"])
                .or_else(|| str_at(f, &["id"]))
                .map(str::to_string),
            title: headline
                .clone()
                .or_else(|| event.clone())
                .unwrap_or_else(|| "Weather alert".into()),
            description: str_at(p, &["description"]).unwrap_or("").to_string(),
            severity: str_at(p, &["severity"]).unwrap_or("Unknown").to_string(),
            urgency: str_at(p, &["urgency"]).unwrap_or("Unknown").to_string(),
            certainty: str_at(p, &["certainty"]).unwrap_or("Unknown").to_string(),
            event,
            headline,
            instruction: str_at(p, &["instruction"]).map(str::to_string),
            onset: parse_time(str_at(p, &["onset"])),
            expires: parse_time(str_at(p, &["expires"])).or(parse_time(str_at(p, &["ends"]))),
            sent: parse_time(str_at(p, &["sent"])),
            effective: parse_time(str_at(p, &["effective"])),
            areas: str_at(p, &["areaDesc"])
                .map(|a| a.split(';').map(|s| s.trim().to_string()).collect())
                .unwrap_or_default(),
            references: p
                .get("references")
                .and_then(Value::as_array)
                .map(|r| {
                    r.iter()
                        .filter_map(|x| x.get("@id").and_then(Value::as_str))
                        .map(str::to_string)
                        .collect()
                })
                .unwrap_or_default(),
            source: Some(SOURCE.into()),
            message_type: str_at(p, &["messageType"]).map(str::to_string),
            affected_zones: string_list(p.get("affectedZones")),
            same_codes: string_list(params.get("SAME")),
            same_event_codes: string_list(params.get("eventCode")),
        });
    }
    alerts.dedupe_and_sort();
    alerts
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn observation_converts_units() {
        let obs = json!({"properties": {
            "textDescription": "Cloudy",
            "temperature": {"value": 20.0, "unitCode": "wmoUnit:degC"},
            "windSpeed": {"value": 10.0, "unitCode": "wmoUnit:km_h-1"},
            "windDirection": {"value": 270, "unitCode": "wmoUnit:degree_(angle)"},
            "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
            "visibility": {"value": 16093, "unitCode": "wmoUnit:m"},
            "timestamp": "2026-01-01T12:00:00+00:00"
        }});
        let c = parse_observation(&obs);
        assert!((c.temperature_f.unwrap() - 68.0).abs() < 0.01);
        assert!((c.wind_speed_mph.unwrap() - 6.21).abs() < 0.01);
        assert_eq!(c.wind_direction.as_deref(), Some("W"));
        assert!((c.pressure_in.unwrap() - 29.92).abs() < 0.01);
        assert!((c.visibility_miles.unwrap() - 10.0).abs() < 0.01);
        assert_eq!(c.condition.as_deref(), Some("Cloudy"));
    }

    #[test]
    fn wind_text_takes_upper_bound() {
        assert_eq!(parse_wind_speed_text("10 to 15 mph"), Some(15.0));
        assert_eq!(parse_wind_speed_text("5 mph"), Some(5.0));
        assert_eq!(parse_wind_speed_text("calm"), None);
    }

    #[test]
    fn alerts_parse_areas_and_codes() {
        let v = json!({"features": [{"id": "urn:1", "properties": {
            "event": "Wind Advisory", "headline": "Wind Advisory until 6 PM",
            "severity": "Moderate", "urgency": "Expected", "certainty": "Likely",
            "areaDesc": "Bucks; Montgomery", "description": "Windy.",
            "expires": "2030-01-01T00:00:00+00:00",
            "parameters": {"SAME": ["042017"]}
        }}]});
        let a = parse_alerts(&v);
        assert_eq!(a.alerts.len(), 1);
        assert_eq!(a.alerts[0].areas, vec!["Bucks", "Montgomery"]);
        assert_eq!(a.alerts[0].same_codes, vec!["042017"]);
        assert_eq!(a.alerts[0].id.as_deref(), Some("urn:1"));
    }
}
