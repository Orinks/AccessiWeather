//! Toolkit-independent presentation: turns weather models into the plain
//! text blocks shown in the main window (and spoken by screen readers).
//! Ported from `accessiweather.display.presentation`.

use chrono::{DateTime, Local, TimeZone, Utc};
use chrono_tz::Tz;

use crate::alerts::{WeatherAlert, WeatherAlerts};
use crate::location::Location;
use crate::settings::AppSettings;
use crate::units::{
    calculate_dewpoint_f, format_precipitation, format_pressure, format_temperature,
    format_visibility, format_wind_speed, resolve_display_unit_system,
    resolve_temperature_unit_preference, resolve_wind_display_unit_system, uv_description,
    wind_direction_to_cardinal, DisplayUnitSystem, TemperatureUnit,
};
use crate::weather::{CurrentConditions, Forecast, ForecastPeriod, HourlyForecast, WeatherData};

/// Text ready to be placed into the four main read-only panes.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct WeatherPresentation {
    pub location_name: String,
    pub summary_text: String,
    pub current_text: String,
    pub hourly_text: String,
    pub daily_text: String,
    pub alert_labels: Vec<String>,
    pub alert_details: Vec<String>,
    pub status_messages: Vec<String>,
}

#[derive(Debug, Clone, Copy)]
pub struct UnitContext {
    unit: TemperatureUnit,
    system: Option<DisplayUnitSystem>,
    wind_system: Option<DisplayUnitSystem>,
    precision: usize,
}

pub struct WeatherPresenter<'a> {
    pub settings: &'a AppSettings,
    pub now: DateTime<Utc>,
}

impl<'a> WeatherPresenter<'a> {
    pub fn new(settings: &'a AppSettings) -> Self {
        Self {
            settings,
            now: Utc::now(),
        }
    }

    fn units(&self, location: &Location) -> UnitContext {
        let pref = self.settings.temperature_unit.as_str();
        let unit = resolve_temperature_unit_preference(pref, Some(location));
        UnitContext {
            unit,
            system: resolve_display_unit_system(pref, Some(location)),
            wind_system: resolve_wind_display_unit_system(
                &self.settings.wind_speed_unit,
                pref,
                Some(location),
            ),
            precision: if self.settings.round_values { 0 } else { 1 },
        }
    }

    pub fn present(&self, data: &WeatherData) -> WeatherPresentation {
        let ctx = self.units(&data.location);
        let tz = location_tz(&data.location);
        let mut presentation = WeatherPresentation {
            location_name: data.location.name.clone(),
            ..Default::default()
        };

        presentation.current_text = match &data.current {
            Some(c) if c.has_data() => self.current_text(c, &data.location, ctx, tz),
            _ => format!(
                "No current conditions available for {}.",
                data.location.name
            ),
        };
        presentation.hourly_text = match &data.hourly_forecast {
            Some(h) if h.has_data() => self.hourly_text(h, ctx, tz),
            _ => "Hourly forecast not available.".to_string(),
        };
        presentation.daily_text = match &data.forecast {
            Some(f) if f.has_data() => self.daily_text(f, &data.location, ctx, tz),
            _ => format!("No forecast available for {}.", data.location.name),
        };
        if let Some(alerts) = &data.alerts {
            let (labels, details) = self.alerts(alerts, tz);
            presentation.alert_labels = labels;
            presentation.alert_details = details;
        }
        presentation.summary_text = self.summary(data, ctx);
        presentation.status_messages = self.status_messages(data, tz);
        presentation
    }

    pub fn summary(&self, data: &WeatherData, ctx: UnitContext) -> String {
        if !data.has_any_data() {
            return format!("No weather data available for {}", data.location.name);
        }
        let mut parts = vec![data.location.name.clone()];
        if let Some(c) = data.current.as_ref().filter(|c| c.has_data()) {
            if c.temperature_f.is_some() || c.temperature_c.is_some() {
                parts.push(format_temperature(
                    c.temperature_f,
                    c.temperature_c,
                    ctx.unit,
                    0,
                ));
            }
            if let Some(cond) = &c.condition {
                parts.push(cond.clone());
            }
        }
        if let Some(alerts) = &data.alerts {
            let active = alerts.active(self.now).len();
            if active > 0 {
                parts.push(format!(
                    "{active} alert{}",
                    if active == 1 { "" } else { "s" }
                ));
            }
        }
        if data.stale {
            parts.push("Cached data".into());
        }
        parts.join(" - ")
    }

    fn status_messages(&self, data: &WeatherData, tz: Option<Tz>) -> Vec<String> {
        let mut messages = Vec::new();
        if data.stale {
            let reason = data
                .stale_reason
                .clone()
                .unwrap_or_else(|| "cached data".into());
            match data.stale_since {
                Some(ts) => messages.push(format!(
                    "Showing cached data from {} ({reason}).",
                    self.format_datetime(ts, tz)
                )),
                None => messages.push(format!("Showing cached weather data ({reason}).")),
            }
        }
        for (source, reason) in &data.failed_sources {
            messages.push(format!("{source} unavailable: {reason}"));
        }
        messages
    }

    pub fn current_text(
        &self,
        current: &CurrentConditions,
        location: &Location,
        ctx: UnitContext,
        tz: Option<Tz>,
    ) -> String {
        let mut lines = vec![format!("Current conditions for {}:", location.name)];
        if let Some(cond) = &current.condition {
            lines.push(format!("Conditions: {cond}"));
        }
        for (label, value) in self.current_metrics(current, ctx) {
            lines.push(format!("{label}: {value}"));
        }
        if let Some(rise) = current.sunrise_time {
            lines.push(format!("Sunrise: {}", self.format_time(rise, tz)));
        }
        if let Some(set) = current.sunset_time {
            lines.push(format!("Sunset: {}", self.format_time(set, tz)));
        }
        if let Some(obs) = current.observed_at {
            let mut line = format!("Observed: {}", self.format_datetime(obs, tz));
            if let Some(station) = &current.station_id {
                line.push_str(&format!(" at {station}"));
            }
            lines.push(line);
        }
        if let Some(source) = &current.source {
            lines.push(format!("Source: {source}"));
        }
        lines.join("\n")
    }

    fn current_metrics(&self, c: &CurrentConditions, ctx: UnitContext) -> Vec<(String, String)> {
        let mut metrics: Vec<(String, String)> = Vec::new();
        let (temp, reason) = self.temperature_with_feels_like(c, ctx);
        metrics.push(("Temperature".into(), temp));
        if let Some(reason) = reason {
            metrics.push(("Feels different".into(), capitalize(&reason)));
        }
        if let Some(h) = c.humidity {
            metrics.push(("Humidity".into(), format!("{h:.0}%")));
        }
        let wind_system = ctx.wind_system.or(ctx.system);
        let wind = self.wind_text(c, ctx, wind_system);
        let gust = c
            .wind_gust_mph
            .map(|g| format_wind_speed(Some(g), c.wind_gust_kph, ctx.unit, 0, wind_system));
        match (wind, gust) {
            (Some(w), Some(g)) => metrics.push(("Wind".into(), format!("{w}, gusting to {g}"))),
            (Some(w), None) => metrics.push(("Wind".into(), w)),
            (None, Some(g)) => metrics.push(("Wind gusts".into(), g)),
            (None, None) => {}
        }
        if self.settings.show_dewpoint {
            if let Some(d) = self.dewpoint_text(c, ctx) {
                metrics.push(("Dewpoint".into(), d));
            }
        }
        if c.pressure_in.is_some() || c.pressure_mb.is_some() {
            metrics.push((
                "Pressure".into(),
                format_pressure(c.pressure_in, c.pressure_mb, ctx.unit, 2, ctx.system),
            ));
        }
        if self.settings.show_visibility
            && (c.visibility_miles.is_some() || c.visibility_km.is_some())
        {
            metrics.push((
                "Visibility".into(),
                format_visibility(
                    c.visibility_miles,
                    c.visibility_km,
                    ctx.unit,
                    ctx.precision,
                    ctx.system,
                ),
            ));
        }
        if self.settings.show_uv_index {
            if let Some(uv) = c.uv_index {
                metrics.push(("UV Index".into(), format!("{uv} ({})", uv_description(uv))));
            }
        }
        if let Some(cc) = c.cloud_cover {
            metrics.push(("Cloud cover".into(), format!("{cc:.0}%")));
        }
        if let Some(p) = c.precipitation_in.filter(|p| *p > 0.0) {
            metrics.push((
                "Precipitation".into(),
                format_precipitation(Some(p), c.precipitation_mm, ctx.unit, 2, ctx.system),
            ));
        }
        if self.settings.show_seasonal_data {
            if let Some(s) = c.snow_depth_in.filter(|s| *s > 0.0) {
                let cm = c.snow_depth_cm.unwrap_or(s * 2.54);
                let text = match ctx.unit {
                    TemperatureUnit::Celsius => format!("{cm:.1} cm"),
                    TemperatureUnit::Both => format!("{s:.1} in ({cm:.1} cm)"),
                    TemperatureUnit::Fahrenheit => format!("{s:.1} in"),
                };
                metrics.push(("Snow depth".into(), text));
            }
        }
        metrics
    }

    fn temperature_with_feels_like(
        &self,
        c: &CurrentConditions,
        ctx: UnitContext,
    ) -> (String, Option<String>) {
        if c.temperature_f.is_none() && c.temperature_c.is_none() {
            return ("N/A".into(), None);
        }
        let temp_str =
            format_temperature(c.temperature_f, c.temperature_c, ctx.unit, ctx.precision);
        let actual_f = c
            .temperature_f
            .or_else(|| c.temperature_c.map(crate::units::c_to_f));
        let wind_mph = c
            .wind_speed_mph
            .or_else(|| c.wind_speed_kph.map(|k| k * 0.621371));

        let (feels_f, feels_c, selection_reason): (Option<f64>, Option<f64>, Option<&str>) =
            match actual_f {
                Some(t)
                    if t < 50.0
                        && wind_mph.is_some_and(|w| w > 3.0)
                        && c.wind_chill_f.is_some() =>
                {
                    (c.wind_chill_f, c.wind_chill_c, Some("wind chill"))
                }
                Some(t)
                    if t > 80.0
                        && c.humidity.is_some_and(|h| h > 40.0)
                        && c.heat_index_f.is_some() =>
                {
                    (c.heat_index_f, c.heat_index_c, Some("heat index"))
                }
                _ if c.feels_like_f.is_some() || c.feels_like_c.is_some() => {
                    (c.feels_like_f, c.feels_like_c, None)
                }
                _ => (None, None, None),
            };

        let feels_f = feels_f.or_else(|| feels_c.map(crate::units::c_to_f));
        let (Some(actual_f), Some(feels_f)) = (actual_f, feels_f) else {
            return (temp_str, None);
        };
        let diff = feels_f - actual_f;
        if diff.abs() < 3.0 {
            return (temp_str, None);
        }
        let feels_str = format_temperature(Some(feels_f), feels_c, ctx.unit, ctx.precision);
        let combined = format!("{temp_str} (feels like {feels_str})");
        let reason = match selection_reason {
            Some(r) => Some(format!("due to {r}")),
            None => feels_like_reason(c, diff),
        };
        (combined, reason)
    }

    fn wind_text(
        &self,
        c: &CurrentConditions,
        ctx: UnitContext,
        system: Option<DisplayUnitSystem>,
    ) -> Option<String> {
        if c.wind_speed_mph.is_none() && c.wind_speed_kph.is_none() && c.wind_direction.is_none() {
            return None;
        }
        let mph = c
            .wind_speed_mph
            .or_else(|| c.wind_speed_kph.map(|k| k * 0.621371));
        if mph.is_some_and(|m| m.abs() < 0.5) {
            return Some("Calm".into());
        }
        let direction = c.wind_direction.as_deref().map(|d| match d.parse::<f64>() {
            Ok(deg) => wind_direction_to_cardinal(Some(deg)),
            Err(_) => d.to_string(),
        });
        let speed = if mph.is_some() {
            Some(format_wind_speed(
                c.wind_speed_mph,
                c.wind_speed_kph,
                ctx.unit,
                ctx.precision,
                system,
            ))
        } else {
            None
        };
        match (direction, speed) {
            (Some(d), Some(s)) => Some(format!("{d} at {s}")),
            (None, Some(s)) => Some(s),
            (d, None) => d,
        }
    }

    fn dewpoint_text(&self, c: &CurrentConditions, ctx: UnitContext) -> Option<String> {
        let (f, cc) = if c.dewpoint_f.is_some() || c.dewpoint_c.is_some() {
            (c.dewpoint_f, c.dewpoint_c)
        } else {
            let dew_f = calculate_dewpoint_f(c.temperature_f?, c.humidity?)?;
            (Some(dew_f), Some(crate::units::f_to_c(dew_f)))
        };
        Some(format_temperature(f, cc, ctx.unit, ctx.precision))
    }

    pub fn hourly_text(&self, hourly: &HourlyForecast, ctx: UnitContext, tz: Option<Tz>) -> String {
        let hours = self.settings.hourly_hours().min(168);
        let verbosity = self.settings.verbosity_level.as_str();
        let include_extras = verbosity != "minimal";
        let mut lines = vec![format!("Next {hours} Hours:")];
        for period in hourly.next_hours(hours, self.now) {
            let mut parts = vec![self.format_time(period.start_time, tz)];
            if let Some(t) = period.temperature {
                parts.push(temp_from_unit(t, &period.temperature_unit, ctx));
            }
            if let Some(cond) = &period.short_forecast {
                parts.push(cond.clone());
            }
            if include_extras {
                if let Some(dir) = &period.wind_direction {
                    let speed = match (period.wind_speed_mph, &period.wind_speed) {
                        (Some(m), _) => Some(format_wind_speed(
                            Some(m),
                            None,
                            ctx.unit,
                            0,
                            ctx.wind_system.or(ctx.system),
                        )),
                        (None, Some(s)) => Some(s.clone()),
                        _ => None,
                    };
                    if let Some(speed) = speed {
                        parts.push(format!("Wind {dir} at {speed}"));
                    }
                }
                if let Some(h) = period.humidity {
                    parts.push(format!("Humidity {h:.0}%"));
                }
                if let Some(p) = period.precipitation_probability {
                    if p > 0.0 {
                        parts.push(format!("Precip {}% chance", p as i64));
                    }
                }
            }
            lines.push(format!("  {}", parts.join(" - ")));
        }
        if let Some(source) = &hourly.source {
            lines.push(format!("Source: {source}"));
        }
        lines.join("\n")
    }

    pub fn daily_text(
        &self,
        forecast: &Forecast,
        location: &Location,
        ctx: UnitContext,
        tz: Option<Tz>,
    ) -> String {
        let verbosity = self.settings.verbosity_level.as_str();
        let include_wind = verbosity != "minimal";
        let include_precip = verbosity != "minimal";
        let include_details = verbosity == "detailed";
        let mut lines = vec![format!("Daily forecast for {}:", location.name)];
        for period in select_periods(forecast, self.settings.forecast_days() as usize, tz) {
            let mut head = if period.name.is_empty() {
                "Unknown".to_string()
            } else {
                period.name.clone()
            };
            if let Some(t) = period.temperature {
                let mut temp = temp_from_unit(t, &period.temperature_unit, ctx);
                if let Some(low) = period.temperature_low {
                    temp = format!(
                        "{temp} / {}",
                        temp_from_unit(low, &period.temperature_unit, ctx)
                    );
                }
                head.push_str(&format!(": {temp}"));
            }
            lines.push(head);
            if let Some(cond) = &period.short_forecast {
                lines.push(format!("  Conditions: {cond}"));
            }
            if include_wind {
                let mut parts = Vec::new();
                if let Some(d) = &period.wind_direction {
                    parts.push(d.clone());
                }
                if let Some(m) = period.wind_speed_mph {
                    parts.push(format_wind_speed(
                        Some(m),
                        None,
                        ctx.unit,
                        0,
                        ctx.wind_system.or(ctx.system),
                    ));
                } else if let Some(s) = &period.wind_speed {
                    parts.push(s.clone());
                }
                if !parts.is_empty() {
                    lines.push(format!("  Wind: {}", parts.join(" ")));
                }
            }
            if include_precip {
                if let Some(p) = period.precipitation_probability {
                    lines.push(format!("  Precipitation chance: {}%", p as i64));
                }
                if let Some(a) = period.precipitation_amount_in.filter(|a| *a > 0.0) {
                    lines.push(format!(
                        "  Precipitation: {}",
                        format_precipitation(Some(a), None, ctx.unit, 2, ctx.system)
                    ));
                }
            }
            if include_details {
                if let Some(d) = period
                    .detailed_forecast
                    .as_ref()
                    .filter(|d| Some(*d) != period.short_forecast.as_ref())
                {
                    lines.push(format!("  Details: {d}"));
                }
            }
        }
        if let Some(source) = &forecast.source {
            lines.push(format!("Source: {source}"));
        }
        lines.join("\n")
    }

    fn alerts(&self, alerts: &WeatherAlerts, tz: Option<Tz>) -> (Vec<String>, Vec<String>) {
        let mut labels = Vec::new();
        let mut details = Vec::new();
        for alert in alerts.active(self.now) {
            labels.push(alert.list_label());
            details.push(self.alert_detail(alert, tz));
        }
        (labels, details)
    }

    pub fn alert_detail(&self, alert: &WeatherAlert, tz: Option<Tz>) -> String {
        let mut lines = Vec::new();
        lines.push(
            alert
                .headline
                .clone()
                .unwrap_or_else(|| alert.title.clone()),
        );
        if let Some(event) = &alert.event {
            lines.push(format!("Event: {event}"));
        }
        lines.push(format!(
            "Severity: {}. Urgency: {}. Certainty: {}.",
            alert.severity, alert.urgency, alert.certainty
        ));
        if !alert.areas.is_empty() {
            lines.push(format!("Areas: {}", alert.areas.join("; ")));
        }
        if let Some(onset) = alert.onset {
            lines.push(format!("Starts: {}", self.format_datetime(onset, tz)));
        }
        if let Some(expires) = alert.expires {
            lines.push(format!("Expires: {}", self.format_datetime(expires, tz)));
        }
        if !alert.description.is_empty() {
            lines.push(String::new());
            lines.push(alert.description.clone());
        }
        if let Some(instr) = alert.instruction.as_ref().filter(|i| !i.is_empty()) {
            lines.push(String::new());
            lines.push(format!("Instructions: {instr}"));
        }
        if let Some(src) = &alert.source {
            lines.push(String::new());
            lines.push(format!("Source: {src}"));
        }
        lines.join("\n")
    }

    fn format_time(&self, ts: DateTime<Utc>, tz: Option<Tz>) -> String {
        let pattern = if self.settings.time_format_12hour {
            "%-I:%M %p"
        } else {
            "%H:%M"
        };
        self.format_with(ts, tz, pattern)
    }

    fn format_datetime(&self, ts: DateTime<Utc>, tz: Option<Tz>) -> String {
        let time = if self.settings.time_format_12hour {
            "%-I:%M %p"
        } else {
            "%H:%M"
        };
        let date = match self.settings.date_format.as_str() {
            "us_short" => "%m/%d/%Y",
            "us_long" => "%B %-d, %Y",
            "eu" => "%d/%m/%Y",
            _ => "%Y-%m-%d",
        };
        self.format_with(ts, tz, &format!("{date} {time}"))
    }

    fn format_with(&self, ts: DateTime<Utc>, tz: Option<Tz>, pattern: &str) -> String {
        let use_location_tz = self.settings.forecast_time_reference == "location"
            && self.settings.time_display_mode != "utc";
        let suffix = self.settings.show_timezone_suffix;
        match (
            self.settings.time_display_mode.as_str(),
            tz,
            use_location_tz,
        ) {
            ("utc", _, _) => {
                let s = ts.format(pattern).to_string();
                if suffix {
                    format!("{s} UTC")
                } else {
                    s
                }
            }
            (_, Some(tz), true) => {
                let local = ts.with_timezone(&tz);
                let s = local.format(pattern).to_string();
                if suffix {
                    format!("{s} {}", local.format("%Z"))
                } else {
                    s
                }
            }
            _ => {
                let local = ts.with_timezone(&Local);
                let s = local.format(pattern).to_string();
                if suffix {
                    format!("{s} {}", local.format("%Z"))
                } else {
                    s
                }
            }
        }
    }
}

fn location_tz(location: &Location) -> Option<Tz> {
    location
        .timezone
        .as_deref()
        .and_then(|t| t.parse::<Tz>().ok())
}

fn temp_from_unit(value: f64, unit: &str, ctx: UnitContext) -> String {
    if unit.eq_ignore_ascii_case("C") {
        format_temperature(None, Some(value), ctx.unit, ctx.precision)
    } else {
        format_temperature(Some(value), None, ctx.unit, ctx.precision)
    }
}

fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().collect::<String>() + chars.as_str(),
        None => String::new(),
    }
}

fn feels_like_reason(c: &CurrentConditions, diff_f: f64) -> Option<String> {
    if diff_f > 0.0 {
        return match c.humidity {
            Some(h) if h >= 70.0 => Some("due to high humidity".into()),
            Some(h) if h >= 40.0 => Some("due to humidity".into()),
            _ => None,
        };
    }
    match c.wind_speed_mph {
        Some(w) if w >= 15.0 => return Some("due to strong wind".into()),
        Some(w) if w >= 3.0 => return Some("due to wind".into()),
        _ => {}
    }
    if c.temperature_f.is_some_and(|t| t < 50.0) && c.humidity.is_some_and(|h| h < 30.0) {
        return Some("due to dry air".into());
    }
    None
}

/// Keep only periods that fall within the configured number of calendar
/// days (in the location's timezone), so a 7-day setting yields 7 days of
/// half-day NWS periods rather than 7 periods.
fn select_periods(forecast: &Forecast, days: usize, tz: Option<Tz>) -> Vec<&ForecastPeriod> {
    let mut dates: Vec<chrono::NaiveDate> = Vec::new();
    let mut out = Vec::new();
    for period in &forecast.periods {
        match period.start_time {
            Some(start) => {
                let date = match tz {
                    Some(tz) => start.with_timezone(&tz).date_naive(),
                    None => Local.from_utc_datetime(&start.naive_utc()).date_naive(),
                };
                if !dates.contains(&date) {
                    if dates.len() >= days {
                        break;
                    }
                    dates.push(date);
                }
                out.push(period);
            }
            None => {
                if out.len() < days * 2 {
                    out.push(period);
                }
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn settings() -> AppSettings {
        AppSettings {
            time_display_mode: "utc".into(),
            ..Default::default()
        }
    }

    #[test]
    fn current_text_includes_core_metrics() {
        let s = settings();
        let presenter = WeatherPresenter::new(&s);
        let loc = Location::new("Denver, CO", 39.7, -104.9).with_country("US");
        let current = CurrentConditions {
            temperature_f: Some(72.0),
            temperature_c: Some(22.2),
            condition: Some("Sunny".into()),
            humidity: Some(30.0),
            wind_speed_mph: Some(10.0),
            wind_direction: Some("270".into()),
            pressure_in: Some(29.92),
            ..Default::default()
        };
        let text = presenter.current_text(&current, &loc, presenter.units(&loc), None);
        assert!(text.contains("Current conditions for Denver, CO:"));
        assert!(text.contains("Temperature: 72°F (22.2°C)"));
        assert!(text.contains("Wind: W at 10.0 mph (16.1 km/h)"));
        assert!(text.contains("Pressure: 29.92 inHg (1013.21 hPa)"));
        assert!(text.contains("Dewpoint:"));
    }

    #[test]
    fn heat_index_feels_like_is_reported() {
        let s = settings();
        let presenter = WeatherPresenter::new(&s);
        let loc = Location::new("x", 0.0, 0.0);
        let current = CurrentConditions {
            temperature_f: Some(90.0),
            humidity: Some(70.0),
            heat_index_f: Some(101.0),
            ..Default::default()
        };
        let (temp, reason) = presenter.temperature_with_feels_like(&current, presenter.units(&loc));
        assert!(temp.contains("feels like 101°F"), "{temp}");
        assert_eq!(reason.as_deref(), Some("due to heat index"));
    }

    #[test]
    fn daily_text_limits_to_configured_days() {
        let s = AppSettings {
            forecast_duration_days: 3,
            ..settings()
        };
        let presenter = WeatherPresenter::new(&s);
        let loc = Location::new("x", 0.0, 0.0);
        let periods = (0..14)
            .map(|i| ForecastPeriod {
                name: format!("P{i}"),
                temperature: Some(60.0 + i as f64),
                temperature_unit: "F".into(),
                start_time: Some(
                    Utc.with_ymd_and_hms(
                        2026,
                        1,
                        1 + (i / 2) as u32,
                        if i % 2 == 0 { 6 } else { 18 },
                        0,
                        0,
                    )
                    .unwrap(),
                ),
                ..Default::default()
            })
            .collect();
        let forecast = Forecast {
            periods,
            ..Default::default()
        };
        let text =
            presenter.daily_text(&forecast, &loc, presenter.units(&loc), Some(chrono_tz::UTC));
        assert!(text.contains("P5:"));
        assert!(!text.contains("P6:"));
    }

    #[test]
    fn summary_counts_active_alerts() {
        let s = settings();
        let presenter = WeatherPresenter::new(&s);
        let mut data = WeatherData::new(Location::new("Here", 0.0, 0.0));
        data.current = Some(CurrentConditions {
            temperature_f: Some(50.0),
            condition: Some("Rain".into()),
            ..Default::default()
        });
        data.alerts = Some(WeatherAlerts {
            alerts: vec![WeatherAlert {
                severity: "Severe".into(),
                ..Default::default()
            }],
        });
        let text = presenter.summary(&data, presenter.units(&data.location));
        assert_eq!(text, "Here - 50°F (10°C) - Rain - 1 alert");
    }
}
