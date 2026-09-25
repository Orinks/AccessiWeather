//! Current conditions presentation.
//!
//! Ports `display/presentation/current_conditions.py`,
//! `current_condition_seasonal.py` and `current_condition_trends.py`.

use chrono::{DateTime, Utc};

use crate::display::impact::build_impact_summary;
use crate::display::measurement::{
    format_dewpoint, format_pressure_value, format_temperature_with_feels_like,
    format_visibility_value, format_wind, get_temperature_precision, get_uv_description,
};
use crate::display::models::{
    AirQualityPresentation, CurrentConditionsPresentation, ImpactSummary, Metric,
};
use crate::display::priority::{PriorityEngine, WeatherCategory};
use crate::display::pyfmt::{capitalize, fixed, repr_f64, title};
use crate::display::time::{format_sun_time, PyDateTime};
use crate::display::units::{
    format_precipitation, format_wind_speed, DisplayUnitSystem, TemperatureUnit,
};
use crate::model::{
    AnomalyCallout, CurrentConditions, EnvironmentalConditions, HourlyForecast,
    MinutelyPrecipitationForecast, TrendInsight, WeatherAlerts,
};
use crate::settings::AppSettings;

const MAX_LEGACY_PRESSURE_TREND_IN: f64 = 0.30;
const MAX_LEGACY_PRESSURE_TREND_MB: f64 = 10.0;

/// Everything `build_current_conditions` reads besides the conditions.
#[derive(Debug, Clone, Copy)]
pub struct CurrentContext<'a> {
    pub location_name: &'a str,
    pub location_zone: Option<chrono_tz::Tz>,
    pub unit_pref: TemperatureUnit,
    pub settings: &'a AppSettings,
    pub environmental: Option<&'a EnvironmentalConditions>,
    pub trends: &'a [TrendInsight],
    pub hourly_forecast: Option<&'a HourlyForecast>,
    pub minutely_precipitation: Option<&'a MinutelyPrecipitationForecast>,
    pub air_quality: Option<&'a AirQualityPresentation>,
    pub alerts: Option<&'a WeatherAlerts>,
    pub unit_system: Option<DisplayUnitSystem>,
    pub wind_unit_system: Option<DisplayUnitSystem>,
    pub anomaly_callout: Option<&'a AnomalyCallout>,
    pub now: DateTime<Utc>,
}

/// `_normalize_metric_wind_units`.
fn normalize_metric_wind_units(value: String, unit_system: Option<DisplayUnitSystem>) -> String {
    if unit_system.is_none() {
        value.replace("km/h", "kph")
    } else {
        value
    }
}

/// `_build_basic_metrics`.
fn build_basic_metrics(
    current: &CurrentConditions,
    ctx: &CurrentContext,
    precision: usize,
) -> Vec<Metric> {
    let s = ctx.settings;
    let unit_pref = ctx.unit_pref;
    let (temperature_value, feels_like_reason) =
        format_temperature_with_feels_like(current, unit_pref, precision);
    let mut metrics = vec![Metric::new("Temperature", temperature_value)];
    if let Some(reason) = feels_like_reason.filter(|r| !r.is_empty()) {
        metrics.push(Metric::new("Feels different", capitalize(&reason)));
    }
    if let Some(h) = current.humidity {
        metrics.push(Metric::new("Humidity", format!("{h}%")));
    }

    let wind_system = ctx.wind_unit_system.or(ctx.unit_system);
    let wind_value = format_wind(current, unit_pref, precision, wind_system)
        .filter(|w| !w.is_empty())
        .map(|w| normalize_metric_wind_units(w, wind_system));
    let gust_value = current.wind_gust_mph.map(|gust| {
        normalize_metric_wind_units(
            format_wind_speed(Some(gust), unit_pref, current.wind_gust_kph, 0, wind_system),
            wind_system,
        )
    });
    match (wind_value, gust_value) {
        (Some(w), Some(g)) => metrics.push(Metric::new("Wind", format!("{w}, gusting to {g}"))),
        (Some(w), None) => metrics.push(Metric::new("Wind", w)),
        (None, Some(g)) => metrics.push(Metric::new("Wind gusts", g)),
        (None, None) => {}
    }

    if let Some(dp) = format_dewpoint(current, unit_pref, precision) {
        if s.show_dewpoint {
            metrics.push(Metric::new("Dewpoint", dp));
        }
    }
    if let Some(p) = format_pressure_value(current, unit_pref, precision, ctx.unit_system) {
        metrics.push(Metric::new("Pressure", p));
    }
    if let Some(v) = format_visibility_value(current, unit_pref, precision, ctx.unit_system) {
        if s.show_visibility {
            metrics.push(Metric::new("Visibility", v));
        }
    }
    if s.show_uv_index {
        if let Some(uv) = current.uv_index {
            metrics.push(Metric::new(
                "UV Index",
                format!("{} ({})", repr_f64(uv), get_uv_description(uv)),
            ));
        }
    }
    if let Some(cc) = current.cloud_cover {
        metrics.push(Metric::new("Cloud cover", format!("{}%", fixed(cc, 0))));
    }
    if let Some(p) = current.precipitation_in.filter(|p| *p > 0.0) {
        metrics.push(Metric::new(
            "Precipitation",
            format_precipitation(
                Some(p),
                unit_pref,
                current.precipitation_mm,
                precision,
                ctx.unit_system,
            ),
        ));
    }
    metrics
}

/// `_build_astronomical_metrics`.
fn build_astronomical_metrics(current: &CurrentConditions, ctx: &CurrentContext) -> Vec<Metric> {
    let s = ctx.settings;
    let fmt = |t: &Option<crate::model::Timestamp>| {
        let t = t.map(|dt| PyDateTime::aware(dt, ctx.location_zone));
        format_sun_time(
            t.as_ref(),
            &s.time_display_mode,
            s.time_format_12hour,
            s.show_timezone_suffix,
        )
        .filter(|v| !v.is_empty())
    };
    let mut metrics = Vec::new();
    if let Some(v) = fmt(&current.sunrise_time) {
        metrics.push(Metric::new("Sunrise", v));
    }
    if let Some(v) = fmt(&current.sunset_time) {
        metrics.push(Metric::new("Sunset", v));
    }
    if let Some(phase) = current.moon_phase.as_deref().filter(|p| !p.is_empty()) {
        metrics.push(Metric::new("Moon phase", phase));
    }
    if let Some(v) = fmt(&current.moonrise_time) {
        metrics.push(Metric::new("Moonrise", v));
    }
    if let Some(v) = fmt(&current.moonset_time) {
        metrics.push(Metric::new("Moonset", v));
    }
    metrics
}

/// `_build_environmental_metrics`.
fn build_environmental_metrics(
    environmental: Option<&EnvironmentalConditions>,
    air_quality: Option<&AirQualityPresentation>,
) -> Vec<Metric> {
    let mut metrics = Vec::new();
    let Some(env) = environmental else {
        return metrics;
    };
    let nonempty = |s: &Option<String>| s.clone().filter(|s| !s.is_empty());

    let mut aq_parts: Vec<String> = Vec::new();
    let summary = if let Some(aq) = air_quality.filter(|aq| !aq.summary.is_empty()) {
        Some(aq.summary.clone())
    } else if let Some(index) = env.air_quality_index {
        let mut label = fixed(index, 0);
        if let Some(cat) = nonempty(&env.air_quality_category) {
            label = format!("{label} ({cat})");
        }
        if let Some(pollutant) = nonempty(&env.air_quality_pollutant) {
            label = format!("{label} – {pollutant}");
        }
        Some(label)
    } else {
        None
    };
    if let Some(s) = summary.filter(|s| !s.is_empty()) {
        aq_parts.push(s);
    }
    if let Some(guidance) = air_quality.and_then(|aq| nonempty(&aq.guidance)) {
        aq_parts.push(format!("Advice: {guidance}"));
    }
    if !aq_parts.is_empty() {
        metrics.push(Metric::new("Air Quality", aq_parts.join(" | ")));
    }

    let allergen = nonempty(&env.pollen_primary_allergen);
    if env.pollen_index.is_some() || allergen.is_some() {
        let mut value = env.pollen_index.map(|i| fixed(i, 0)).unwrap_or_default();
        if let Some(cat) = nonempty(&env.pollen_category) {
            value = if value.is_empty() {
                cat
            } else {
                format!("{value} ({cat})")
            };
        }
        if let Some(a) = allergen {
            value = if value.is_empty() {
                a
            } else {
                format!("{value} – {a}")
            };
        }
        if !value.is_empty() {
            metrics.push(Metric::new("Pollen", value));
        }
    }
    metrics
}

/// `_build_trend_metrics`.
fn build_trend_metrics(
    trends: &[TrendInsight],
    current: &CurrentConditions,
    hourly_forecast: Option<&HourlyForecast>,
    show_pressure_trend: bool,
    unit_pref: TemperatureUnit,
    now: DateTime<Utc>,
) -> Vec<Metric> {
    let mut metrics = Vec::new();
    let mut pressure_present = false;
    for trend in trends {
        let metric = trend.metric.to_lowercase();
        if metric == "daily_trend" {
            continue;
        }
        let is_pressure = metric == "pressure";
        if is_pressure && !show_pressure_trend {
            continue;
        }
        let summary = trend_summary(trend, metric == "temperature", unit_pref);
        let label = if is_pressure {
            "Pressure outlook".to_string()
        } else {
            format!("{} trend", title(&trend.metric.replace('_', " ")))
        };
        metrics.push(Metric::new(label, summary));
        if is_pressure {
            pressure_present = true;
        }
    }
    if show_pressure_trend && !pressure_present {
        if let Some((_, value)) = compute_pressure_trend_from_hourly(current, hourly_forecast, now)
        {
            metrics.push(Metric::new("Pressure trend", value));
        }
    }
    metrics
}

/// Summary text for one trend, sparkline appended.
fn trend_summary(trend: &TrendInsight, is_temperature: bool, unit_pref: TemperatureUnit) -> String {
    let summary = if is_temperature {
        adapt_temperature_trend_summary(trend, unit_pref)
    } else {
        trend
            .summary
            .clone()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| describe_trend(trend))
    };
    match trend.sparkline.as_deref().filter(|s| !s.is_empty()) {
        Some(spark) => format!("{summary} {spark}").trim().to_string(),
        None => summary,
    }
}

/// `_categorize_metric`.
fn categorize_metric(label: &str) -> WeatherCategory {
    let l = label.to_lowercase();
    let any = |kws: &[&str]| kws.iter().any(|k| l.contains(k));
    if any(&[
        "temperature",
        "feels",
        "dewpoint",
        "heat index",
        "wind chill",
    ]) {
        WeatherCategory::Temperature
    } else if l.contains("wind") && !l.contains("chill") {
        WeatherCategory::Wind
    } else if any(&["precipitation", "snow", "rain"]) {
        WeatherCategory::Precipitation
    } else if any(&["humidity", "pressure"]) {
        WeatherCategory::HumidityPressure
    } else if any(&["visibility", "cloud"]) {
        WeatherCategory::VisibilityClouds
    } else if l.contains("uv") {
        WeatherCategory::UvIndex
    } else {
        WeatherCategory::Temperature
    }
}

/// `_order_metrics_by_priority`.
fn order_metrics_by_priority(metrics: Vec<Metric>, order: &[WeatherCategory]) -> Vec<Metric> {
    let mut buckets: Vec<(WeatherCategory, Vec<Metric>)> = WeatherCategory::ALL
        .iter()
        .map(|c| (*c, Vec::new()))
        .collect();
    for m in metrics {
        let cat = categorize_metric(&m.label);
        if let Some((_, bucket)) = buckets.iter_mut().find(|(c, _)| *c == cat) {
            bucket.push(m);
        }
    }
    let mut ordered = Vec::new();
    for cat in order {
        if let Some((_, bucket)) = buckets.iter_mut().find(|(c, _)| c == cat) {
            ordered.append(bucket);
        }
    }
    ordered
}

/// `build_current_conditions`.
pub fn build_current_conditions(
    current: &CurrentConditions,
    ctx: &CurrentContext,
) -> CurrentConditionsPresentation {
    let s = ctx.settings;
    let title = format!("Current conditions for {}", ctx.location_name);
    let description = current
        .condition
        .clone()
        .filter(|c| !c.is_empty())
        .unwrap_or_else(|| "Unknown".into());
    let precision = if s.round_values {
        0
    } else {
        get_temperature_precision(ctx.unit_pref)
    };

    let engine = PriorityEngine::new(
        &s.verbosity_level,
        &s.category_order,
        s.severe_weather_override,
    );
    let order = engine.get_category_order(ctx.alerts, ctx.now);

    let mut metrics = build_basic_metrics(current, ctx, precision);
    if s.show_seasonal_data {
        metrics.extend(build_seasonal_metrics(current, ctx.unit_pref, precision));
    }
    let mut metrics = order_metrics_by_priority(metrics, &order);

    if let Some(summary) = ctx
        .minutely_precipitation
        .and_then(|m| m.summary.clone())
        .filter(|s| !s.is_empty())
    {
        metrics.insert(0, Metric::new("Precipitation outlook", summary));
    }
    metrics.extend(build_astronomical_metrics(current, ctx));
    metrics.extend(build_environmental_metrics(
        ctx.environmental,
        ctx.air_quality,
    ));
    metrics.extend(build_trend_metrics(
        ctx.trends,
        current,
        ctx.hourly_forecast,
        s.show_pressure_trend,
        ctx.unit_pref,
        ctx.now,
    ));
    if let Some(anomaly) = ctx.anomaly_callout {
        metrics.push(Metric::new(
            "Historical context",
            anomaly.temp_anomaly_description.clone(),
        ));
    }

    let impact = if s.show_impact_summaries {
        build_impact_summary(Some(current), ctx.environmental)
    } else {
        ImpactSummary::default()
    };
    if s.show_impact_summaries {
        if let Some(v) = &impact.outdoor {
            metrics.push(Metric::new("Impact: Outdoor", v.clone()));
        }
        if let Some(v) = &impact.driving {
            metrics.push(Metric::new("Impact: Driving", v.clone()));
        }
        if let Some(v) = &impact.allergy {
            metrics.push(Metric::new("Impact: Allergy", v.clone()));
        }
    }

    let mut lines = vec![format!(
        "Current conditions for {}: {description}",
        ctx.location_name
    )];
    lines.extend(metrics.iter().map(|m| format!("{}: {}", m.label, m.value)));

    let trends = format_trend_lines(
        ctx.trends,
        Some(current),
        ctx.hourly_forecast,
        s.show_pressure_trend,
        ctx.unit_pref,
        ctx.now,
    );

    CurrentConditionsPresentation {
        title,
        description,
        metrics,
        fallback_text: lines.join("\n"),
        trends,
        impact_summary: Some(impact),
    }
}

// ---------------------------------------------------------------------------
// current_condition_seasonal
// ---------------------------------------------------------------------------

/// `_build_seasonal_metrics`.
pub fn build_seasonal_metrics(
    current: &CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> Vec<Metric> {
    let mut metrics = Vec::new();
    // `x or fallback`: a zero stored value falls back to the conversion.
    let or_else = |v: Option<f64>, fallback: f64| v.filter(|v| *v != 0.0).unwrap_or(fallback);

    if let Some(depth_in) = current.snow_depth_in.filter(|d| *d > 0.0) {
        let depth_cm = or_else(current.snow_depth_cm, depth_in * 2.54);
        let value = match unit_pref {
            TemperatureUnit::Celsius => format!("{} cm", fixed(depth_cm, precision)),
            TemperatureUnit::Fahrenheit => format!("{} in", fixed(depth_in, precision)),
            TemperatureUnit::Both => format!(
                "{} in ({} cm)",
                fixed(depth_in, precision),
                fixed(depth_cm, precision)
            ),
        };
        metrics.push(Metric::new("Snow on ground", value));
    }

    if let Some(chill_f) = current.wind_chill_f {
        if current
            .temperature_f
            .is_none_or(|t| (chill_f - t).abs() >= 3.0)
        {
            let chill_c = current.wind_chill_c.unwrap_or((chill_f - 32.0) * 5.0 / 9.0);
            if let Some(v) =
                format_temperature_value(Some(chill_f), Some(chill_c), unit_pref, precision)
            {
                metrics.push(Metric::new("Wind chill", v));
            }
        }
    }

    if let Some(level_ft) = current.freezing_level_ft {
        let level_m = or_else(current.freezing_level_m, level_ft * 0.3048);
        let value = match unit_pref {
            TemperatureUnit::Celsius => format!("{} m", fixed(level_m, 0)),
            TemperatureUnit::Fahrenheit => format!("{} ft", fixed(level_ft, 0)),
            TemperatureUnit::Both => {
                format!("{} ft ({} m)", fixed(level_ft, 0), fixed(level_m, 0))
            }
        };
        metrics.push(Metric::new("Freezing level", value));
    }

    if let Some(heat_f) = current.heat_index_f {
        if current
            .temperature_f
            .is_none_or(|t| (heat_f - t).abs() >= 3.0)
        {
            let heat_c = current.heat_index_c.unwrap_or((heat_f - 32.0) * 5.0 / 9.0);
            if let Some(v) =
                format_temperature_value(Some(heat_f), Some(heat_c), unit_pref, precision)
            {
                metrics.push(Metric::new("Heat index", v));
            }
        }
    }

    if let Some(risk) = current
        .frost_risk
        .as_deref()
        .filter(|r| r.to_lowercase() != "none")
    {
        metrics.push(Metric::new("Frost risk", risk));
    }

    if let Some(types) = current
        .precipitation_type
        .as_ref()
        .filter(|t| !t.is_empty())
    {
        let condition = current.condition.as_deref().unwrap_or("").to_lowercase();
        let active = [
            "rain", "snow", "drizzle", "shower", "storm", "sleet", "hail", "precip",
        ]
        .iter()
        .any(|k| condition.contains(k));
        if active {
            metrics.push(Metric::new("Precipitation type", title(&types.join(", "))));
        }
    }

    if let Some(risk) = current.severe_weather_risk.filter(|r| *r > 0) {
        metrics.push(Metric::new(
            "Severe weather risk",
            format!("{risk}% ({})", severe_risk_description(risk)),
        ));
    }
    metrics
}

/// `format_temperature_value` (seasonal metrics; no smart precision).
pub fn format_temperature_value(
    temp_f: Option<f64>,
    temp_c: Option<f64>,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> Option<String> {
    let to_c = |f: f64| (f - 32.0) * 5.0 / 9.0;
    match unit_pref {
        TemperatureUnit::Fahrenheit => temp_f.map(|f| format!("{}°F", fixed(f, precision))),
        TemperatureUnit::Celsius => temp_c
            .or(temp_f.map(to_c))
            .map(|c| format!("{}°C", fixed(c, precision))),
        TemperatureUnit::Both => temp_f.map(|f| {
            let c = temp_c.unwrap_or(to_c(f));
            format!("{}°F ({}°C)", fixed(f, precision), fixed(c, precision))
        }),
    }
}

/// `_get_severe_risk_description`.
pub fn severe_risk_description(risk: i64) -> &'static str {
    match risk {
        r if r >= 80 => "Extreme",
        r if r >= 60 => "High",
        r if r >= 40 => "Moderate",
        r if r >= 20 => "Low",
        _ => "Minimal",
    }
}

// ---------------------------------------------------------------------------
// current_condition_trends
// ---------------------------------------------------------------------------

/// `_adapt_temperature_trend_summary`.
fn adapt_temperature_trend_summary(trend: &TrendInsight, unit_pref: TemperatureUnit) -> String {
    let fallback = || {
        trend
            .summary
            .clone()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| describe_trend(trend))
    };
    let (Some(change), Some(unit)) = (trend.change, trend.unit.as_deref()) else {
        return fallback();
    };
    if unit != "°F" && unit != "°C" {
        return fallback();
    }
    let direction = if trend.direction.is_empty() {
        "steady"
    } else {
        &trend.direction
    };
    let hours = if trend.timeframe_hours == 0 {
        24
    } else {
        trend.timeframe_hours
    };
    let (change_f, change_c) = if unit == "°F" {
        (change, change * 5.0 / 9.0)
    } else {
        (change * 9.0 / 5.0, change)
    };
    let both =
        || format!("Temperature {direction} {change_f:+.1}°F ({change_c:+.1}°C) over {hours}h");
    match (unit, unit_pref) {
        ("°F", TemperatureUnit::Celsius) => {
            format!("Temperature {direction} {change_c:+.1}°C over {hours}h")
        }
        ("°C", TemperatureUnit::Fahrenheit) => {
            format!("Temperature {direction} {change_f:+.1}°F over {hours}h")
        }
        (_, TemperatureUnit::Both) => both(),
        _ => fallback(),
    }
}

/// `format_trend_lines`.
pub fn format_trend_lines(
    trends: &[TrendInsight],
    current: Option<&CurrentConditions>,
    hourly_forecast: Option<&HourlyForecast>,
    include_pressure: bool,
    unit_pref: TemperatureUnit,
    now: DateTime<Utc>,
) -> Vec<String> {
    let mut lines = Vec::new();
    let mut pressure_present = false;
    for trend in trends {
        let metric = trend.metric.to_lowercase();
        if metric == "daily_trend" {
            continue;
        }
        let is_pressure = metric == "pressure";
        if is_pressure && !include_pressure {
            continue;
        }
        let summary = trend_summary(trend, metric == "temperature", unit_pref);
        if !summary.is_empty() {
            lines.push(summary);
        }
        if is_pressure {
            pressure_present = true;
        }
    }
    if include_pressure && !pressure_present {
        if let (Some(current), Some(hourly)) = (current, hourly_forecast) {
            if let Some((summary, _)) =
                compute_pressure_trend_from_hourly(current, Some(hourly), now)
            {
                if !summary.is_empty() && !lines.contains(&summary) {
                    lines.push(summary);
                }
            }
        }
    }
    lines
}

/// `describe_trend`.
pub fn describe_trend(trend: &TrendInsight) -> String {
    let direction = capitalize(if trend.direction.is_empty() {
        "steady"
    } else {
        &trend.direction
    });
    let timeframe = if trend.timeframe_hours == 0 {
        24
    } else {
        trend.timeframe_hours
    };
    let change_text = match (trend.change, trend.unit.as_deref()) {
        (None, _) => String::new(),
        (Some(c), Some(u)) if u == "°F" || u == "°C" => format!("{c:+.1}{u}"),
        (Some(c), Some(u)) if !u.is_empty() => format!("{c:+.2}{u}"),
        (Some(c), _) => format!("{c:+.1}"),
    };
    let mut pieces = vec![direction];
    if !change_text.is_empty() {
        pieces.push(change_text);
    }
    pieces.push(format!("over {timeframe}h"));
    pieces.join(" ")
}

/// `compute_pressure_trend_from_hourly`: `(summary, value)` from the next
/// six hours, or `None` when the data is missing or implausible.
pub fn compute_pressure_trend_from_hourly(
    current: &CurrentConditions,
    hourly_forecast: Option<&HourlyForecast>,
    now: DateTime<Utc>,
) -> Option<(String, String)> {
    let hourly = hourly_forecast.filter(|h| h.has_data())?;
    let next = hourly.next_hours(6, now);
    let target = next
        .iter()
        .rev()
        .find(|p| p.pressure_in.is_some() || p.pressure_mb.is_some())?;

    let (descriptor, magnitude) = match (
        current.pressure_in,
        target.pressure_in,
        current.pressure_mb,
        target.pressure_mb,
    ) {
        (Some(base), Some(future), _, _) => {
            let change = future - base;
            if change.abs() > MAX_LEGACY_PRESSURE_TREND_IN {
                return None;
            }
            (
                direction_descriptor(change, 0.02, 0.05),
                format!("{change:+.2} inHg"),
            )
        }
        (_, _, Some(base), Some(future)) => {
            let change = future - base;
            if change.abs() > MAX_LEGACY_PRESSURE_TREND_MB {
                return None;
            }
            (
                direction_descriptor(change, 0.5, 1.5),
                format!("{change:+.1} mb"),
            )
        }
        _ => return None,
    };
    let (word, arrow) = split_direction_descriptor(descriptor);
    let arrow_part = if arrow.is_empty() {
        String::new()
    } else {
        format!(" {arrow}")
    };
    let value = format!("{}{arrow_part} {magnitude} over next 6h", title(word))
        .trim()
        .to_string();
    let summary = format!("Pressure {descriptor} {magnitude} over next 6h")
        .trim()
        .to_string();
    Some((summary, value))
}

/// `direction_descriptor`.
pub fn direction_descriptor(change: f64, minor: f64, strong: f64) -> &'static str {
    if change >= strong {
        "rising ⬆⬆"
    } else if change >= minor {
        "rising ⬆"
    } else if change <= -strong {
        "falling ⬇⬇"
    } else if change <= -minor {
        "falling ⬇"
    } else {
        "steady →"
    }
}

/// `split_direction_descriptor`.
pub fn split_direction_descriptor(descriptor: &str) -> (&str, &str) {
    if descriptor.is_empty() {
        return ("steady", "");
    }
    match descriptor.split_once(' ') {
        Some((word, arrow)) => (word, arrow.trim()),
        None => (descriptor, ""),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn trend(metric: &str, change: Option<f64>, unit: Option<&str>) -> TrendInsight {
        TrendInsight {
            metric: metric.into(),
            direction: "rising".into(),
            change,
            unit: unit.map(str::to_string),
            timeframe_hours: 24,
            summary: None,
            sparkline: None,
        }
    }

    #[test]
    fn describe_trend_formats_by_unit() {
        assert_eq!(
            describe_trend(&trend("temperature", Some(4.0), Some("°F"))),
            "Rising +4.0°F over 24h"
        );
        assert_eq!(
            describe_trend(&trend("pressure", Some(-0.056), Some("inHg"))),
            "Rising -0.06inHg over 24h"
        );
        assert_eq!(describe_trend(&trend("x", None, None)), "Rising over 24h");
    }

    #[test]
    fn temperature_trend_adapts_to_units() {
        let t = trend("temperature", Some(9.0), Some("°F"));
        assert_eq!(
            adapt_temperature_trend_summary(&t, TemperatureUnit::Celsius),
            "Temperature rising +5.0°C over 24h"
        );
        assert_eq!(
            adapt_temperature_trend_summary(&t, TemperatureUnit::Both),
            "Temperature rising +9.0°F (+5.0°C) over 24h"
        );
        assert_eq!(
            adapt_temperature_trend_summary(&t, TemperatureUnit::Fahrenheit),
            "Rising +9.0°F over 24h"
        );
    }

    #[test]
    fn seasonal_metrics() {
        let c = CurrentConditions {
            temperature_f: Some(20.0),
            wind_chill_f: Some(10.0),
            snow_depth_in: Some(4.0),
            freezing_level_ft: Some(1000.0),
            frost_risk: Some("None".into()),
            precipitation_type: Some(vec!["snow".into(), "freezing rain".into()]),
            condition: Some("Light Snow".into()),
            severe_weather_risk: Some(45),
            ..Default::default()
        };
        let m = build_seasonal_metrics(&c, TemperatureUnit::Both, 1);
        let text: Vec<String> = m
            .iter()
            .map(|m| format!("{}: {}", m.label, m.value))
            .collect();
        assert_eq!(
            text,
            [
                "Snow on ground: 4.0 in (10.2 cm)",
                "Wind chill: 10.0°F (-12.2°C)",
                "Freezing level: 1000 ft (305 m)",
                "Precipitation type: Snow, Freezing Rain",
                "Severe weather risk: 45% (Moderate)",
            ]
        );
    }

    #[test]
    fn metric_categories() {
        assert_eq!(
            categorize_metric("Wind chill"),
            WeatherCategory::Temperature
        );
        assert_eq!(categorize_metric("Wind gusts"), WeatherCategory::Wind);
        assert_eq!(
            categorize_metric("Snow on ground"),
            WeatherCategory::Precipitation
        );
        assert_eq!(
            categorize_metric("Freezing level"),
            WeatherCategory::Temperature
        );
        assert_eq!(categorize_metric("UV Index"), WeatherCategory::UvIndex);
    }
}
