//! Sanity checks for apparent temperature, wind chill and heat index.
//!
//! Port of `accessiweather/thermal_comfort.py`.

const WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F: f64 = 3.0;
const HEAT_INDEX_COHERENCE_TOLERANCE_F: f64 = 2.5;
const SOLAR_ALLOWANCE_BASE_F: f64 = 4.0;
const SOLAR_ALLOWANCE_MAX_F: f64 = 5.5;
const SOLAR_ALLOWANCE_PER_DEGREE_F: f64 = 0.15;
const HEAT_INDEX_MIN_TEMP_F: f64 = 80.0;
const HEAT_INDEX_MIN_HUMIDITY: f64 = 40.0;
const WIND_CHILL_MAX_TEMP_F: f64 = 50.0;
const WIND_CHILL_MIN_WIND_MPH: f64 = 3.0;

/// `ThermalComfortReadings`.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct ThermalComfortReadings {
    pub feels_like_f: Option<f64>,
    pub feels_like_c: Option<f64>,
    pub wind_chill_f: Option<f64>,
    pub wind_chill_c: Option<f64>,
    pub heat_index_f: Option<f64>,
    pub heat_index_c: Option<f64>,
}

/// Raw readings passed to [`sanitize_thermal_comfort_readings`].
#[derive(Debug, Clone, Copy, Default)]
pub struct ThermalInputs {
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

fn to_fahrenheit(f: Option<f64>, c: Option<f64>) -> Option<f64> {
    f.or_else(|| c.map(|c| (c * 9.0 / 5.0) + 32.0))
}

fn to_celsius(f: Option<f64>) -> Option<f64> {
    f.map(|f| (f - 32.0) * 5.0 / 9.0)
}

/// `sanitize_thermal_comfort_readings`.
pub fn sanitize_thermal_comfort_readings(i: ThermalInputs) -> ThermalComfortReadings {
    let temp_f = to_fahrenheit(i.temperature_f, i.temperature_c);
    let mut feels_f = to_fahrenheit(i.feels_like_f, i.feels_like_c);
    let mut chill_f = to_fahrenheit(i.wind_chill_f, i.wind_chill_c);
    let mut heat_f = to_fahrenheit(i.heat_index_f, i.heat_index_c);

    if !warm_apparent_temperature_is_coherent(temp_f, i.humidity, feels_f) {
        feels_f = None;
    }
    if !warm_heat_index_is_coherent(temp_f, i.humidity, heat_f) {
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
        if feels > t && heat_f.is_none() && warm_heat_index_is_coherent(temp_f, i.humidity, feels_f)
        {
            heat_f = feels_f;
        } else if feels < t && chill_f.is_none() {
            chill_f = feels_f;
        }
    }

    if feels_f.is_none() {
        if let Some(t) = temp_f {
            if chill_f.is_some_and(|c| c < t) {
                feels_f = chill_f;
            } else if heat_f.is_some_and(|h| h > t) {
                feels_f = heat_f;
            }
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

/// `calculate_heat_index_f` (NWS Rothfusz), `None` outside its range.
pub fn calculate_heat_index_f(t: f64, rh: f64) -> Option<f64> {
    if t < HEAT_INDEX_MIN_TEMP_F || rh < HEAT_INDEX_MIN_HUMIDITY {
        return None;
    }
    let mut hi = -42.379 + 2.04901523 * t + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh;
    if rh > 85.0 && (80.0..=87.0).contains(&t) {
        hi += ((rh - 85.0) / 10.0) * ((87.0 - t) / 5.0);
    }
    Some(hi)
}

/// `calculate_wind_chill_f` (standard NWS formula), `None` outside its range.
pub fn calculate_wind_chill_f(t: f64, wind_mph: f64) -> Option<f64> {
    if t > WIND_CHILL_MAX_TEMP_F || wind_mph <= WIND_CHILL_MIN_WIND_MPH {
        return None;
    }
    let wf = wind_mph.powf(0.16);
    Some(35.74 + (0.6215 * t) - (35.75 * wf) + (0.4275 * t * wf))
}

fn solar_allowance_f(t: f64) -> f64 {
    let mut allowance = SOLAR_ALLOWANCE_BASE_F;
    if t > HEAT_INDEX_MIN_TEMP_F {
        allowance += (t - HEAT_INDEX_MIN_TEMP_F) * SOLAR_ALLOWANCE_PER_DEGREE_F;
    }
    allowance.min(SOLAR_ALLOWANCE_MAX_F)
}

/// `warm_apparent_temperature_is_coherent`.
pub fn warm_apparent_temperature_is_coherent(
    temperature_f: Option<f64>,
    humidity: Option<f64>,
    apparent_f: Option<f64>,
) -> bool {
    let (Some(t), Some(a)) = (temperature_f, apparent_f) else {
        return true;
    };
    if a <= t || a - t < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F {
        return true;
    }
    let Some(rh) = humidity else {
        return true;
    };
    let mut max_coherent = t + solar_allowance_f(t);
    if let Some(hi) = calculate_heat_index_f(t, rh) {
        max_coherent = max_coherent.max(t.max(hi) + HEAT_INDEX_COHERENCE_TOLERANCE_F);
    }
    a <= max_coherent
}

/// `warm_heat_index_is_coherent`.
pub fn warm_heat_index_is_coherent(
    temperature_f: Option<f64>,
    humidity: Option<f64>,
    heat_index_f: Option<f64>,
) -> bool {
    let (Some(t), Some(h)) = (temperature_f, heat_index_f) else {
        return true;
    };
    if h <= t || h - t < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F {
        return true;
    }
    let Some(rh) = humidity else {
        return true;
    };
    match calculate_heat_index_f(t, rh) {
        Some(hi) => h <= t.max(hi) + HEAT_INDEX_COHERENCE_TOLERANCE_F,
        None => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn implausible_warm_feels_like_is_dropped() {
        // 70°F, dry air, feels like 85°F: no heat index envelope, beyond solar allowance.
        let r = sanitize_thermal_comfort_readings(ThermalInputs {
            temperature_f: Some(70.0),
            humidity: Some(30.0),
            feels_like_f: Some(85.0),
            ..Default::default()
        });
        assert_eq!(r.feels_like_f, None);
    }

    #[test]
    fn cold_feels_like_becomes_wind_chill() {
        let r = sanitize_thermal_comfort_readings(ThermalInputs {
            temperature_f: Some(30.0),
            humidity: Some(60.0),
            feels_like_f: Some(20.0),
            ..Default::default()
        });
        assert_eq!(r.wind_chill_f, Some(20.0));
        assert_eq!(r.feels_like_f, Some(20.0));
    }

    #[test]
    fn wind_chill_formula() {
        let wc = calculate_wind_chill_f(20.0, 15.0).unwrap();
        assert!((wc - 6.2).abs() < 0.1, "{wc}");
        assert!(calculate_wind_chill_f(60.0, 15.0).is_none());
    }
}
