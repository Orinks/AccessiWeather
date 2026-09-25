//! Daily, hourly and marine forecast presentation.
//!
//! Ports `display/presentation/forecast.py` and `forecast_hourly.py`.

use chrono::NaiveDate;
use chrono_tz::Tz;

use crate::display::impact::build_forecast_impact_summary;
use crate::display::measurement::{
    format_forecast_temperature, format_hourly_wind, format_period_temperature, format_period_wind,
    get_temperature_precision, get_uv_description,
};
use crate::display::models::{
    ForecastPeriodPresentation, ForecastPresentation, HourlyPeriodPresentation,
};
use crate::display::pyfmt::{fixed, wrap_text};
use crate::display::time::{format_display_time, resolve_forecast_display_time, Clock, PyDateTime};
use crate::display::units::{
    calculate_dewpoint, format_precipitation, format_temperature, format_wind_speed,
    DisplayUnitSystem, TemperatureUnit,
};
use crate::model::{
    Forecast, ForecastConfidence, ForecastConfidenceLevel, ForecastPeriod, HourlyForecast,
    HourlyForecastPeriod, MarineForecast,
};
use crate::settings::AppSettings;

/// Everything `build_forecast` reads besides the forecast itself.
#[derive(Debug, Clone, Copy)]
pub struct ForecastContext<'a> {
    pub location_name: &'a str,
    pub location_zone: Option<Tz>,
    pub unit_pref: TemperatureUnit,
    pub settings: &'a AppSettings,
    pub marine: Option<&'a MarineForecast>,
    pub confidence: Option<&'a ForecastConfidence>,
    pub mobility_briefing: Option<&'a str>,
    pub wind_unit_system: Option<DisplayUnitSystem>,
    pub clock: Clock,
}

fn precision_for(settings: &AppSettings, unit_pref: TemperatureUnit) -> usize {
    if settings.round_values {
        0
    } else {
        get_temperature_precision(unit_pref)
    }
}

fn hourly_hours(settings: &AppSettings) -> usize {
    settings.hourly_forecast_hours.clamp(1, 168) as usize
}

fn configured_forecast_days(settings: &AppSettings) -> usize {
    settings.forecast_duration_days.clamp(3, 16) as usize
}

fn nonempty(s: &Option<String>) -> Option<&str> {
    s.as_deref().filter(|s| !s.is_empty())
}

/// `_looks_like_half_day_periods`: NWS-style day/night lists.
fn looks_like_half_day_periods(forecast: &Forecast) -> bool {
    let starts: Vec<_> = forecast
        .periods
        .iter()
        .filter_map(|p| p.start_time)
        .collect();
    if starts.len() >= 3 {
        let diffs: Vec<f64> = starts
            .windows(2)
            .map(|w| (w[1] - w[0]).num_milliseconds().abs() as f64 / 1000.0 / 3600.0)
            .collect();
        let avg = diffs.iter().sum::<f64>() / diffs.len() as f64;
        if avg <= 14.0 {
            return true;
        }
    }
    const TOKENS: [&str; 5] = [
        "tonight",
        "overnight",
        "this afternoon",
        "this evening",
        "night ",
    ];
    forecast.periods.iter().any(|p| {
        let name = p.name.trim().to_lowercase();
        TOKENS.iter().any(|t| name.contains(t))
    })
}

/// `_select_periods_by_day_window`: periods on the first N calendar days
/// (in each timestamp's own offset), or a count when timestamps are sparse.
pub fn select_periods_by_day_window(forecast: &Forecast, days: usize) -> Vec<&ForecastPeriod> {
    let periods = &forecast.periods;
    let mut dated: Vec<&ForecastPeriod> =
        periods.iter().filter(|p| p.start_time.is_some()).collect();
    if dated.len() < 3.max(periods.len() / 2) {
        let limit = if looks_like_half_day_periods(forecast) {
            days * 2
        } else {
            days
        };
        return periods.iter().take(limit).collect();
    }
    dated.sort_by_key(|p| p.start_time);
    let mut unique_days: Vec<NaiveDate> = Vec::new();
    for p in dated {
        let day = p.start_time.map(|t| t.date_naive());
        if let Some(day) = day.filter(|d| !unique_days.contains(d)) {
            unique_days.push(day);
        }
        if unique_days.len() >= days {
            break;
        }
    }
    if unique_days.is_empty() {
        return periods.iter().take(days).collect();
    }
    periods
        .iter()
        .filter(|p| {
            p.start_time
                .is_some_and(|t| unique_days.contains(&t.date_naive()))
        })
        .collect()
}

fn confidence_level(confidence: &ForecastConfidence) -> &'static str {
    match confidence.level {
        ForecastConfidenceLevel::High => "High",
        ForecastConfidenceLevel::Medium => "Moderate",
        ForecastConfidenceLevel::Low => "Low",
    }
}

/// `build_forecast`.
pub fn build_forecast(
    forecast: &Forecast,
    hourly_forecast: Option<&HourlyForecast>,
    ctx: &ForecastContext,
) -> ForecastPresentation {
    let s = ctx.settings;
    let unit_pref = ctx.unit_pref;
    let precision = precision_for(s, unit_pref);
    let summary_line = nonempty(&forecast.summary).map(|v| format!("Overall: {v}"));
    let hourly_summary_line = hourly_forecast
        .and_then(|h| nonempty(&h.summary))
        .map(|v| format!("Hourly outlook: {v}"));
    let mut daily_lines = vec![format!("Daily forecast for {}:", ctx.location_name)];
    if let Some(l) = &summary_line {
        daily_lines.push(l.clone());
    }

    let hours = hourly_hours(s);
    let hourly = match hourly_forecast.filter(|h| h.has_data()) {
        Some(h) => build_hourly_summary(
            h,
            unit_pref,
            s,
            ctx.location_zone,
            ctx.wind_unit_system,
            &ctx.clock,
        ),
        None => Vec::new(),
    };

    let verbosity = s.verbosity_level.as_str();
    let standard_or_more = matches!(verbosity, "standard" | "detailed");
    let detailed = verbosity == "detailed";
    let selected = select_periods_by_day_window(forecast, configured_forecast_days(s));

    let mut periods = Vec::new();
    for period in &selected {
        let temp_pair = format_forecast_temperature(period, unit_pref, precision);
        let wind = standard_or_more
            .then(|| format_period_wind(period, unit_pref, ctx.wind_unit_system))
            .flatten();
        let details = nonempty(&period.detailed_forecast)
            .filter(|d| detailed && Some(*d) != period.short_forecast.as_deref())
            .map(str::to_string);
        let precip_prob = period
            .precipitation_probability
            .filter(|_| standard_or_more)
            .map(|p| format!("{}%", p.trunc() as i64));
        let snowfall = period
            .snowfall
            .filter(|v| detailed && *v > 0.0)
            .map(|v| format!("{} in", fixed(v, precision)));
        let uv = period
            .uv_index
            .filter(|_| detailed)
            .map(|v| format!("{} ({})", fixed(v, 0), get_uv_description(v)));
        let cloud = period
            .cloud_cover
            .filter(|_| detailed)
            .map(|v| format!("{}%", fixed(v, 0)));
        let gust = nonempty(&period.wind_gust)
            .filter(|_| detailed)
            .map(str::to_string);
        let precip_amt = period
            .precipitation_amount
            .filter(|a| standard_or_more && *a > 0.0)
            .map(|a| format_precipitation(Some(a), unit_pref, Some(a * 25.4), precision, None));

        let name = if period.name.is_empty() {
            "Unknown"
        } else {
            &period.name
        };
        daily_lines.push(format!(
            "{name}: {}",
            temp_pair
                .as_deref()
                .filter(|t| !t.is_empty())
                .unwrap_or("N/A")
        ));
        if let Some(c) = nonempty(&period.short_forecast) {
            daily_lines.push(format!("  Conditions: {c}"));
        }
        match (&wind, &gust) {
            (Some(w), Some(g)) => daily_lines.push(format!("  Wind: {w}, gusting to {g}")),
            (Some(w), None) => daily_lines.push(format!("  Wind: {w}")),
            (None, Some(g)) => daily_lines.push(format!("  Wind gusts: {g}")),
            (None, None) => {}
        }
        let mut precip_parts: Vec<String> = Vec::new();
        if let Some(types) = period.precipitation_type.as_ref().filter(|t| !t.is_empty()) {
            let joined = types.join(", ");
            if !joined.is_empty() {
                precip_parts.push(joined);
            }
        }
        if let Some(a) = &precip_amt {
            precip_parts.push(a.clone());
        }
        if let Some(p) = &precip_prob {
            precip_parts.push(format!("{p} chance"));
        }
        if !precip_parts.is_empty() {
            daily_lines.push(format!("  Precipitation: {}", precip_parts.join(", ")));
        }
        if let Some(v) = &snowfall {
            daily_lines.push(format!("  Snowfall: {v}"));
        }
        if let Some(v) = &cloud {
            daily_lines.push(format!("  Cloud cover: {v}"));
        }
        if let Some(v) = &uv {
            daily_lines.push(format!("  UV Index: {v}"));
        }
        if let Some(d) = &details {
            daily_lines.push(format!("  Details: {}", wrap_text(d, 80)));
        }

        periods.push(ForecastPeriodPresentation {
            name: name.to_string(),
            temperature: temp_pair,
            conditions: period.short_forecast.clone(),
            wind,
            details,
            precipitation_probability: precip_prob,
            snowfall,
            uv_index: uv,
            cloud_cover: cloud,
            wind_gust: gust,
            precipitation_amount: precip_amt,
        });
    }

    let generated_at = forecast.generated_at.map(|g| {
        let shown = resolve_forecast_display_time(
            &PyDateTime::aware(g, ctx.location_zone),
            &s.forecast_time_reference,
            ctx.location_zone,
            &ctx.clock,
        );
        format_display_time(
            Some(&shown),
            &s.time_display_mode,
            s.time_format_12hour,
            s.show_timezone_suffix,
        )
    });
    if let Some(g) = &generated_at {
        daily_lines.push(format!("Forecast generated: {g}"));
    }

    let mut confidence_label = None;
    if let Some(conf) = ctx.confidence {
        let level = confidence_level(conf);
        daily_lines.push(format!(
            "Forecast confidence: {level}. {}.",
            conf.rationale.trim_end_matches('.')
        ));
        confidence_label = Some(format!("Confidence: {level}"));
    }

    let daily_section_text = daily_lines.join("\n").trim_end().to_string();
    let mut hourly_section_text =
        build_hourly_section_text(&hourly, hours, hourly_summary_line.as_deref());
    if let Some(briefing) = ctx.mobility_briefing.filter(|b| !b.is_empty()) {
        let line = format!("Mobility briefing: {briefing}");
        hourly_section_text = if hourly_section_text.is_empty() {
            format!("Hourly forecast:\n{line}")
        } else {
            hourly_section_text.replacen(
                "Hourly forecast:\n",
                &format!("Hourly forecast:\n{line}\n"),
                1,
            )
        };
    }

    let (marine_section_text, marine_summary, marine_highlights) = match ctx.marine {
        Some(m) if m.has_data() => build_marine(m, ctx.location_name),
        _ => (String::new(), None, Vec::new()),
    };

    let fallback_text = [
        &daily_section_text,
        &marine_section_text,
        &hourly_section_text,
    ]
    .into_iter()
    .filter(|s| !s.is_empty())
    .map(String::as_str)
    .collect::<Vec<_>>()
    .join("\n\n")
    .trim_end()
    .to_string();

    let impact_summary = selected
        .first()
        .filter(|_| s.show_impact_summaries)
        .map(|p| build_forecast_impact_summary(p));

    ForecastPresentation {
        title: format!("Forecast for {}", ctx.location_name),
        periods,
        hourly_periods: hourly,
        hourly_summary: hourly_summary_line,
        generated_at,
        fallback_text,
        daily_section_text,
        hourly_section_text,
        mobility_briefing: ctx.mobility_briefing.map(str::to_string),
        marine_section_text,
        marine_summary,
        marine_highlights,
        confidence_label,
        summary: summary_line,
        impact_summary,
    }
}

/// The marine section: (text, summary, highlights).
fn build_marine(
    marine: &MarineForecast,
    location_name: &str,
) -> (String, Option<String>, Vec<String>) {
    let mut lines = vec![format!("Marine conditions for {location_name}:")];
    if let Some(zone) = nonempty(&marine.zone_name) {
        let label = match nonempty(&marine.zone_id) {
            Some(id) => format!("{zone} ({id})"),
            None => zone.to_string(),
        };
        lines.push(format!("Marine zone: {label}"));
    }
    let summary = marine.forecast_summary.clone();
    if let Some(s) = nonempty(&summary) {
        lines.push(format!("Summary: {s}"));
    }
    let highlights: Vec<String> = marine.highlights.iter().take(4).cloned().collect();
    if !highlights.is_empty() {
        lines.push("Wind and wave highlights:".into());
        lines.extend(highlights.iter().map(|h| format!("  • {h}")));
    }
    for period in marine.periods.iter().take(3) {
        if !period.summary.is_empty() {
            lines.push(format!(
                "{}: {}",
                period.name,
                wrap_text(&period.summary, 80)
            ));
        }
    }
    (lines.join("\n").trim_end().to_string(), summary, highlights)
}

// ---------------------------------------------------------------------------
// forecast_hourly
// ---------------------------------------------------------------------------

/// `build_hourly_summary`: the next `hourly_forecast_hours` periods.
pub fn build_hourly_summary(
    hourly_forecast: &HourlyForecast,
    unit_pref: TemperatureUnit,
    settings: &AppSettings,
    location_zone: Option<Tz>,
    wind_unit_system: Option<DisplayUnitSystem>,
    clock: &Clock,
) -> Vec<HourlyPeriodPresentation> {
    let precision = precision_for(settings, unit_pref);
    let verbosity = settings.verbosity_level.as_str();
    let standard_or_more = matches!(verbosity, "standard" | "detailed");
    let detailed = verbosity == "detailed";

    let mut out = Vec::new();
    for period in hourly_forecast.next_hours(hourly_hours(settings), clock.now) {
        if !period.has_data() {
            continue;
        }
        let shown = resolve_forecast_display_time(
            &PyDateTime::aware(period.start_time, location_zone),
            &settings.forecast_time_reference,
            location_zone,
            clock,
        );
        out.push(HourlyPeriodPresentation {
            time: format_display_time(
                Some(&shown),
                &settings.time_display_mode,
                settings.time_format_12hour,
                settings.show_timezone_suffix,
            ),
            temperature: format_period_temperature(period, unit_pref, precision),
            conditions: period.short_forecast.clone(),
            wind: standard_or_more
                .then(|| format_hourly_wind(period, unit_pref, wind_unit_system))
                .flatten(),
            humidity: period
                .humidity
                .filter(|_| standard_or_more)
                .map(|h| format!("{h}%")),
            dewpoint: standard_or_more
                .then(|| format_hourly_dewpoint(period, unit_pref, precision))
                .flatten(),
            precipitation_probability: period
                .precipitation_probability
                .filter(|_| standard_or_more)
                .map(|p| format!("{}%", p.trunc() as i64)),
            snowfall: period
                .snowfall
                .filter(|v| detailed && *v > 0.0)
                .map(|v| format!("{} in", fixed(v, precision))),
            uv_index: period
                .uv_index
                .filter(|_| detailed)
                .map(|v| format!("{} ({})", fixed(v, 0), get_uv_description(v))),
            cloud_cover: period
                .cloud_cover
                .filter(|_| detailed)
                .map(|v| format!("{}%", fixed(v, 0))),
            wind_gust: period
                .wind_gust_mph
                .filter(|_| detailed)
                .map(|g| format_wind_speed(Some(g), unit_pref, None, 0, wind_unit_system)),
            precipitation_amount: period
                .precipitation_amount
                .filter(|a| standard_or_more && *a > 0.0)
                .map(|a| format_precipitation(Some(a), unit_pref, Some(a * 25.4), precision, None)),
        });
    }
    out
}

/// `_format_hourly_dewpoint`. Humidity 0 yields "N/A", as in Python.
fn format_hourly_dewpoint(
    period: &HourlyForecastPeriod,
    unit_pref: TemperatureUnit,
    precision: usize,
) -> Option<String> {
    let (mut dewpoint_f, mut dewpoint_c) = (period.dewpoint_f, period.dewpoint_c);
    if dewpoint_f.is_none() && dewpoint_c.is_none() {
        let (Some(temp), Some(h)) = (period.temperature, period.humidity) else {
            return None;
        };
        let unit = if period.temperature_unit.is_empty() {
            "F".to_string()
        } else {
            period.temperature_unit.to_uppercase()
        };
        let temp_f = if unit == "F" {
            temp
        } else {
            (temp * 9.0 / 5.0) + 32.0
        };
        dewpoint_f = calculate_dewpoint(temp_f, h as f64, false);
        dewpoint_c = dewpoint_f.map(|d| (d - 32.0) * 5.0 / 9.0);
    }
    Some(format_temperature(
        dewpoint_f, unit_pref, dewpoint_c, precision,
    ))
}

fn filled(s: &Option<String>) -> Option<&str> {
    s.as_deref().filter(|s| !s.is_empty())
}

/// `render_hourly_fallback`.
pub fn render_hourly_fallback(hourly: &[HourlyPeriodPresentation], hours: usize) -> String {
    let mut lines = vec![format!("Next {hours} Hours:")];
    for p in hourly {
        let mut parts = vec![p.time.clone()];
        if let Some(t) = filled(&p.temperature) {
            parts.push(t.into());
        }
        if let Some(c) = filled(&p.conditions) {
            parts.push(c.into());
        }
        match (filled(&p.wind), filled(&p.wind_gust)) {
            (Some(w), Some(g)) => parts.push(format!("Wind {w}, gusting to {g}")),
            (Some(w), None) => parts.push(format!("Wind {w}")),
            (None, Some(g)) => parts.push(format!("Gusts {g}")),
            (None, None) => {}
        }
        if let Some(h) = filled(&p.humidity) {
            parts.push(format!("Humidity {h}"));
        }
        if let Some(d) = filled(&p.dewpoint) {
            parts.push(format!("Dewpoint {d}"));
        }
        let mut precip: Vec<String> = Vec::new();
        if let Some(a) = filled(&p.precipitation_amount) {
            precip.push(a.into());
        }
        if let Some(pp) = filled(&p.precipitation_probability) {
            precip.push(format!("{pp} chance"));
        }
        if !precip.is_empty() {
            parts.push(format!("Precip {}", precip.join(", ")));
        }
        if let Some(sn) = filled(&p.snowfall) {
            parts.push(format!("Snow {sn}"));
        }
        if let Some(c) = filled(&p.cloud_cover) {
            parts.push(format!("Clouds {c}"));
        }
        if let Some(u) = filled(&p.uv_index) {
            parts.push(format!("UV {u}"));
        }
        lines.push(format!("  {}", parts.join(" - ")));
    }
    lines.join("\n")
}

/// `build_hourly_section_text`.
pub fn build_hourly_section_text(
    hourly: &[HourlyPeriodPresentation],
    hours: usize,
    summary_line: Option<&str>,
) -> String {
    let summary_line = summary_line.filter(|s| !s.is_empty());
    if hourly.is_empty() && summary_line.is_none() {
        return String::new();
    }
    let mut lines = vec!["Hourly forecast:".to_string()];
    if let Some(s) = summary_line {
        lines.push(s.to_string());
    }
    lines.push(render_hourly_fallback(hourly, hours));
    lines.join("\n").trim_end().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{FixedOffset, TimeZone};

    fn day_period(name: &str, day: u32, hour: u32) -> ForecastPeriod {
        let off = FixedOffset::west_opt(4 * 3600).unwrap();
        ForecastPeriod {
            name: name.into(),
            temperature: Some(70.0),
            start_time: Some(off.with_ymd_and_hms(2026, 9, day, hour, 0, 0).unwrap()),
            ..Default::default()
        }
    }

    #[test]
    fn day_window_keeps_both_halves_of_each_day() {
        let periods: Vec<ForecastPeriod> = (0..14)
            .map(|i| {
                day_period(
                    if i % 2 == 0 { "Day" } else { "Night" },
                    1 + i / 2,
                    if i % 2 == 0 { 6 } else { 18 },
                )
            })
            .collect();
        let f = Forecast {
            periods,
            ..Default::default()
        };
        assert_eq!(select_periods_by_day_window(&f, 3).len(), 6);
    }

    #[test]
    fn undated_nws_style_lists_double_the_count() {
        let periods: Vec<ForecastPeriod> = [
            "Today",
            "Tonight",
            "Friday",
            "Friday Night",
            "Saturday",
            "Saturday Night",
            "Sunday",
            "Sunday Night",
        ]
        .iter()
        .map(|n| ForecastPeriod {
            name: n.to_string(),
            ..Default::default()
        })
        .collect();
        let f = Forecast {
            periods,
            ..Default::default()
        };
        assert_eq!(select_periods_by_day_window(&f, 3).len(), 6);
        let f2 = Forecast {
            periods: f.periods[..1].to_vec(),
            ..Default::default()
        };
        assert_eq!(select_periods_by_day_window(&f2, 3).len(), 1);
    }

    #[test]
    fn hourly_section_text_layout() {
        let p = HourlyPeriodPresentation {
            time: "3:00 PM".into(),
            temperature: Some("72°F".into()),
            conditions: Some("Sunny".into()),
            wind: Some("NW at 5 mph".into()),
            wind_gust: Some("15 mph".into()),
            precipitation_probability: Some("10%".into()),
            ..Default::default()
        };
        assert_eq!(
            build_hourly_section_text(&[p], 6, Some("Hourly outlook: Dry")),
            "Hourly forecast:\nHourly outlook: Dry\nNext 6 Hours:\n  3:00 PM - 72°F - Sunny - Wind NW at 5 mph, gusting to 15 mph - Precip 10% chance"
        );
        assert_eq!(build_hourly_section_text(&[], 6, None), "");
    }
}
