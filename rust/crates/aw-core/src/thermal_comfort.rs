//! Sanity checks for apparent temperature, wind chill and heat index readings,
//! ported from `accessiweather.thermal_comfort`.

pub const WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F: f64 = 3.0;
pub const HEAT_INDEX_COHERENCE_TOLERANCE_F: f64 = 2.5;
const SOLAR_ALLOWANCE_BASE_F: f64 = 4.0;
const SOLAR_ALLOWANCE_MAX_F: f64 = 5.5;
const SOLAR_ALLOWANCE_PER_DEGREE_F: f64 = 0.15;
pub const HEAT_INDEX_MIN_TEMP_F: f64 = 80.0;
pub const HEAT_INDEX_MIN_HUMIDITY: f64 = 40.0;
pub const WIND_CHILL_MAX_TEMP_F: f64 = 50.0;
pub const WIND_CHILL_MIN_WIND_MPH: f64 = 3.0;

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct ThermalComfortReadings {
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
}

/// Raw readings in either unit; Fahrenheit wins when both are given.
#[derive(Debug, Clone, Copy, Default)]
pub struct ThermalComfortInput {
    pub temperature_f: Option<f64>,
    pub temperature_c: Option<f64>,
    pub humidity: Option<f64>,
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
}

/// Normalize and discard internally inconsistent thermal-comfort readings.
pub fn sanitize_thermal_comfort_readings(input: ThermalComfortInput) -> ThermalComfortReadings {
    let temp_f = to_fahrenheit(input.temperature_f, input.temperature_c);
    let mut feels_f = to_fahrenheit(input.feels_like_f, input.feels_like_c);
    let mut chill_f = to_fahrenheit(input.wind_chill_f, input.wind_chill_c);
    let mut heat_f = to_fahrenheit(input.heat_index_f, input.heat_index_c);
    let humidity = input.humidity;

    if !warm_apparent_temperature_is_coherent(temp_f, humidity, feels_f) {
        feels_f = None;
    }
    if !warm_heat_index_is_coherent(temp_f, humidity, heat_f) {
        heat_f = None;
    }

    if let Some(t) = temp_f {
        if heat_f.is_some_and(|h| h <= t) {
            heat_f = None;
        }
        if chill_f.is_some_and(|c| c >= t) {
            chill_f = None;
        }
    }

    if let (Some(feels), Some(t)) = (feels_f, temp_f) {
        if feels > t && heat_f.is_none() && warm_heat_index_is_coherent(temp_f, humidity, feels_f)
        {
            heat_f = feels_f;
        } else if feels < t && chill_f.is_none() {
            chill_f = feels_f;
        }
    }

    if let (None, Some(t)) = (feels_f, temp_f) {
        if chill_f.is_some_and(|c| c < t) {
            feels_f = chill_f;
        } else if heat_f.is_some_and(|h| h > t) {
            feels_f = heat_f;
        }
    }

    ThermalComfortReadings {
        feels_like_f: feels_f,
        feels_like_c: to_celsius(feels_f),
        wind_chill_f: chill_f,
        wind_chill_c: to_celsius(chill_f),
        heat_index_f: heat_f,
        heat_index_c: to_celsius(heat_f),
    }
}

/// NOAA/NWS Rothfusz heat index, `None` outside the warm/humid range.
pub fn calculate_heat_index_f(temperature_f: f64, humidity: f64) -> Option<f64> {
    if temperature_f < HEAT_INDEX_MIN_TEMP_F || humidity < HEAT_INDEX_MIN_HUMIDITY {
        return None;
    }
    let (t, h) = (temperature_f, humidity);
    let mut heat_index = -42.379 + 2.04901523 * t + 10.14333127 * h
        - 0.22475541 * t * h
        - 0.00683783 * t * t
        - 0.05481717 * h * h
        + 0.00122874 * t * t * h
        + 0.00085282 * t * h * h
        - 0.00000199 * t * t * h * h;
    if h > 85.0 && (80.0..=87.0).contains(&t) {
        heat_index += ((h - 85.0) / 10.0) * ((87.0 - t) / 5.0);
    }
    Some(heat_index)
}

/// Standard NWS wind chill, `None` when it does not apply.
pub fn calculate_wind_chill_f(temperature_f: f64, wind_speed_mph: f64) -> Option<f64> {
    if temperature_f > WIND_CHILL_MAX_TEMP_F || wind_speed_mph <= WIND_CHILL_MIN_WIND_MPH {
        return None;
    }
    let wind_factor = wind_speed_mph.powf(0.16);
    Some(35.74 + (0.6215 * temperature_f) - (35.75 * wind_factor) + (0.4275 * temperature_f * wind_factor))
}

pub fn warm_apparent_temperature_is_coherent(
    temperature_f: Option<f64>,
    humidity: Option<f64>,
    apparent_f: Option<f64>,
) -> bool {
    let (Some(t), Some(apparent)) = (temperature_f, apparent_f) else {
        return true;
    };
    if apparent <= t || apparent - t < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F {
        return true;
    }
    let Some(h) = humidity else {
        return true;
    };
    let mut max_coherent = t + solar_allowance_f(t);
    if let Some(heat_index) = calculate_heat_index_f(t, h) {
        max_coherent = max_coherent.max(t.max(heat_index) + HEAT_INDEX_COHERENCE_TOLERANCE_F);
    }
    apparent <= max_coherent
}

pub fn warm_heat_index_is_coherent(
    temperature_f: Option<f64>,
    humidity: Option<f64>,
    heat_index_f: Option<f64>,
) -> bool {
    let (Some(t), Some(reading)) = (temperature_f, heat_index_f) else {
        return true;
    };
    if reading <= t || reading - t < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F {
        return true;
    }
    let Some(h) = humidity else {
        return true;
    };
    match calculate_heat_index_f(t, h) {
        Some(heat_index) => reading <= t.max(heat_index) + HEAT_INDEX_COHERENCE_TOLERANCE_F,
        None => false,
    }
}

fn solar_allowance_f(temperature_f: f64) -> f64 {
    let mut allowance = SOLAR_ALLOWANCE_BASE_F;
    if temperature_f > HEAT_INDEX_MIN_TEMP_F {
        allowance += (temperature_f - HEAT_INDEX_MIN_TEMP_F) * SOLAR_ALLOWANCE_PER_DEGREE_F;
    }
    allowance.min(SOLAR_ALLOWANCE_MAX_F)
}

fn to_fahrenheit(value_f: Option<f64>, value_c: Option<f64>) -> Option<f64> {
    value_f.or(value_c.map(|c| (c * 9.0 / 5.0) + 32.0))
}

fn to_celsius(value_f: Option<f64>) -> Option<f64> {
    value_f.map(|f| (f - 32.0) * 5.0 / 9.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn readings(temp: f64, humidity: f64, feels: Option<f64>, heat: Option<f64>) -> ThermalComfortReadings {
        sanitize_thermal_comfort_readings(ThermalComfortInput {
            temperature_f: Some(temp),
            humidity: Some(humidity),
            feels_like_f: feels,
            heat_index_f: heat,
            ..Default::default()
        })
    }

    #[test]
    fn drops_low_humidity_heat_index() {
        let r = readings(91.0, 19.0, None, Some(100.0));
        assert_eq!(r.heat_index_f, None);
        assert_eq!(r.feels_like_f, None);
    }

    #[test]
    fn keeps_coherent_humid_heat_index() {
        let r = readings(90.0, 70.0, None, Some(105.0));
        assert_eq!(r.heat_index_f, Some(105.0));
        assert_eq!(r.feels_like_f, Some(105.0));
    }

    #[test]
    fn drops_implausible_low_humidity_apparent_temperature() {
        let r = readings(85.0, 15.0, Some(100.0), None);
        assert_eq!(r.feels_like_f, None);
        assert_eq!(r.heat_index_f, None);
    }

    #[test]
    fn keeps_plausible_solar_apparent_temperature_without_heat_index() {
        let r = readings(85.0, 15.0, Some(89.0), None);
        assert_eq!(r.feels_like_f, Some(89.0));
        assert_eq!(r.heat_index_f, None);
    }

    #[test]
    fn cold_feels_like_becomes_wind_chill() {
        let r = readings(30.0, 50.0, Some(20.0), None);
        assert_eq!(r.wind_chill_f, Some(20.0));
        assert_eq!(r.feels_like_f, Some(20.0));
    }

    #[test]
    fn wind_chill_formula() {
        assert!(calculate_wind_chill_f(60.0, 10.0).is_none());
        assert!(calculate_wind_chill_f(30.0, 2.0).is_none());
        let wc = calculate_wind_chill_f(30.0, 10.0).unwrap();
        assert!((wc - 21.2).abs() < 0.1);
    }
}
