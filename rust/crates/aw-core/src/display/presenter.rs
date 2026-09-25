//! The public entry point: `WeatherPresenter`.
//!
//! Port of `display/weather_presenter.py`.

use crate::display::alerts::{active_alerts, build_alerts};
use crate::display::aviation::build_aviation;
use crate::display::current::{build_current_conditions, format_trend_lines, CurrentContext};
use crate::display::environmental::build_air_quality_panel;
use crate::display::forecast::{build_forecast, ForecastContext};
use crate::display::measurement::format_temperature_pair;
use crate::display::mobility::build_mobility_briefing;
use crate::display::models::{
    AlertsPresentation, CurrentConditionsPresentation, ForecastPresentation, WeatherPresentation,
};
use crate::display::source_attribution::build_source_attribution;
use crate::display::time::{
    format_display_datetime, location_zone, Clock, PyDateTime, DEFAULT_DATE_FORMAT,
};
use crate::display::units::{
    resolve_display_unit_system, resolve_temperature_unit_preference,
    resolve_wind_display_unit_system, DisplayUnitSystem, TemperatureUnit,
};
use crate::location::Location;
use crate::model::{
    CurrentConditions, EnvironmentalConditions, Forecast, ForecastConfidence, HourlyForecast,
    MarineForecast, TrendInsight, WeatherAlerts, WeatherData,
};
use crate::settings::AppSettings;

/// Builds structured, screen-reader friendly presentations of weather data.
#[derive(Debug, Clone)]
pub struct WeatherPresenter {
    pub settings: AppSettings,
    clock: Option<Clock>,
}

struct Units {
    pref: TemperatureUnit,
    system: Option<DisplayUnitSystem>,
    wind_system: Option<DisplayUnitSystem>,
}

impl WeatherPresenter {
    /// A presenter that reads the real clock on every call.
    pub fn new(settings: &AppSettings) -> Self {
        Self {
            settings: settings.clone(),
            clock: None,
        }
    }

    /// A presenter frozen at `clock` (tests, golden files).
    pub fn with_clock(settings: &AppSettings, clock: Clock) -> Self {
        Self {
            settings: settings.clone(),
            clock: Some(clock),
        }
    }

    fn clock(&self) -> Clock {
        self.clock.unwrap_or_else(Clock::system)
    }

    fn units(&self, location: &Location) -> Units {
        let temp = &self.settings.temperature_unit;
        Units {
            pref: resolve_temperature_unit_preference(temp, Some(location)),
            system: resolve_display_unit_system(temp, Some(location)),
            wind_system: resolve_wind_display_unit_system(
                &self.settings.wind_speed_unit,
                temp,
                Some(location),
            ),
        }
    }

    /// `_format_timestamp`: "Sep 25 3:05 PM" honouring the time settings.
    pub fn format_timestamp(&self, value: &PyDateTime) -> String {
        format_display_datetime(
            value,
            &self.settings.time_display_mode,
            self.settings.time_format_12hour,
            self.settings.show_timezone_suffix,
            DEFAULT_DATE_FORMAT,
        )
    }

    /// `present`: everything shown for one location.
    pub fn present(&self, data: &WeatherData) -> WeatherPresentation {
        let clock = self.clock();
        let location = &data.location;
        let zone = location_zone(location.timezone.as_deref());
        let units = self.units(location);

        let air_quality = data
            .environmental
            .as_ref()
            .and_then(|env| build_air_quality_panel(&location.name, env, &self.settings, zone));

        let current = data.current.as_ref().map(|c| {
            build_current_conditions(
                c,
                &CurrentContext {
                    location_name: &location.name,
                    location_zone: zone,
                    unit_pref: units.pref,
                    settings: &self.settings,
                    environmental: data.environmental.as_ref(),
                    trends: &data.trend_insights,
                    hourly_forecast: data.hourly_forecast.as_ref(),
                    minutely_precipitation: data.minutely_precipitation.as_ref(),
                    air_quality: air_quality.as_ref(),
                    alerts: data.alerts.as_ref(),
                    unit_system: units.system,
                    wind_unit_system: units.wind_system,
                    anomaly_callout: data.anomaly_callout.as_ref(),
                    now: clock.now,
                },
            )
        });

        let forecast = data.forecast.as_ref().map(|f| {
            let briefing = build_mobility_briefing(data, None, clock.now);
            build_forecast(
                f,
                data.hourly_forecast.as_ref(),
                &ForecastContext {
                    location_name: &location.name,
                    location_zone: zone,
                    unit_pref: units.pref,
                    settings: &self.settings,
                    marine: data.marine.as_ref(),
                    confidence: data.forecast_confidence.as_ref(),
                    mobility_briefing: briefing.as_deref(),
                    wind_unit_system: units.wind_system,
                    clock,
                },
            )
        });

        let alerts = data.alerts.as_ref().map(|a| {
            build_alerts(
                a,
                &location.name,
                &self.settings,
                zone,
                data.alert_lifecycle_diff.as_ref(),
                None,
                clock.now,
            )
        });

        let aviation = build_aviation(data.aviation.as_ref(), &location.name, &|t| {
            self.format_timestamp(t)
        });

        WeatherPresentation {
            location_name: location.name.clone(),
            summary_text: self.build_summary(data, units.pref, &clock),
            current_conditions: current,
            forecast,
            alerts,
            air_quality,
            aviation,
            trend_summary: format_trend_lines(
                &data.trend_insights,
                data.current.as_ref(),
                data.hourly_forecast.as_ref(),
                self.settings.show_pressure_trend,
                units.pref,
                clock.now,
            ),
            status_messages: self.build_status_messages(data),
            source_attribution: build_source_attribution(data),
        }
    }

    /// `present_current`: `None` when there is nothing to show.
    pub fn present_current(
        &self,
        current: Option<&CurrentConditions>,
        location: &Location,
        environmental: Option<&EnvironmentalConditions>,
        trends: &[TrendInsight],
        hourly_forecast: Option<&HourlyForecast>,
        alerts: Option<&WeatherAlerts>,
    ) -> Option<CurrentConditionsPresentation> {
        let current = current.filter(|c| c.has_data())?;
        let clock = self.clock();
        let zone = location_zone(location.timezone.as_deref());
        let units = self.units(location);
        let air_quality = environmental
            .and_then(|env| build_air_quality_panel(&location.name, env, &self.settings, zone));
        Some(build_current_conditions(
            current,
            &CurrentContext {
                location_name: &location.name,
                location_zone: zone,
                unit_pref: units.pref,
                settings: &self.settings,
                environmental,
                trends,
                hourly_forecast,
                minutely_precipitation: None,
                air_quality: air_quality.as_ref(),
                alerts,
                unit_system: units.system,
                wind_unit_system: units.wind_system,
                anomaly_callout: None,
                now: clock.now,
            },
        ))
    }

    /// `present_forecast`: `None` without forecast periods.
    pub fn present_forecast(
        &self,
        forecast: Option<&Forecast>,
        location: &Location,
        hourly_forecast: Option<&HourlyForecast>,
        marine: Option<&MarineForecast>,
        confidence: Option<&ForecastConfidence>,
        mobility_briefing: Option<&str>,
    ) -> Option<ForecastPresentation> {
        let forecast = forecast.filter(|f| f.has_data())?;
        let units = self.units(location);
        Some(build_forecast(
            forecast,
            hourly_forecast,
            &ForecastContext {
                location_name: &location.name,
                location_zone: location_zone(location.timezone.as_deref()),
                unit_pref: units.pref,
                settings: &self.settings,
                marine,
                confidence,
                mobility_briefing,
                wind_unit_system: units.wind_system,
                clock: self.clock(),
            },
        ))
    }

    /// `present_alerts`.
    pub fn present_alerts(
        &self,
        alerts: Option<&WeatherAlerts>,
        location: &Location,
    ) -> Option<AlertsPresentation> {
        let alerts = alerts?;
        Some(build_alerts(
            alerts,
            &location.name,
            &self.settings,
            location_zone(location.timezone.as_deref()),
            None,
            None,
            self.clock().now,
        ))
    }

    /// `_build_summary`: the one-line summary.
    fn build_summary(&self, data: &WeatherData, unit_pref: TemperatureUnit, clock: &Clock) -> String {
        let name = &data.location.name;
        if !data.has_any_data() {
            return format!("No weather data available for {name}");
        }
        let mut parts = vec![name.clone()];
        if let Some(c) = data.current.as_ref().filter(|c| c.has_data()) {
            if let Some(t) = format_temperature_pair(c.temperature_f, c.temperature_c, unit_pref, 0) {
                parts.push(t);
            }
            if let Some(cond) = c.condition.as_deref().filter(|s| !s.is_empty()) {
                parts.push(cond.to_string());
            }
        }
        if let Some(alerts) = data.alerts.as_ref().filter(|a| a.has_alerts()) {
            let n = active_alerts(alerts, clock.now).len();
            if n > 0 {
                parts.push(format!("{n} alert{}", if n != 1 { "s" } else { "" }));
            }
        }
        let trends = format_trend_lines(
            &data.trend_insights,
            data.current.as_ref(),
            data.hourly_forecast.as_ref(),
            true,
            unit_pref,
            clock.now,
        );
        if let Some(first) = trends.into_iter().next() {
            parts.push(first);
        }
        if data.stale {
            parts.push(match self.stale_since(data) {
                Some(ts) => format!("Cached {ts}"),
                None => "Cached data".into(),
            });
        }
        parts.join(" - ")
    }

    fn stale_since(&self, data: &WeatherData) -> Option<String> {
        let zone = location_zone(data.location.timezone.as_deref());
        data.stale_since
            .map(|t| self.format_timestamp(&PyDateTime::aware(t, zone)))
    }

    /// `_build_status_messages`.
    fn build_status_messages(&self, data: &WeatherData) -> Vec<String> {
        if !data.stale {
            return Vec::new();
        }
        let reason = data
            .stale_reason
            .as_deref()
            .filter(|r| !r.is_empty())
            .unwrap_or("cached data");
        vec![match self.stale_since(data) {
            Some(ts) => format!("Showing cached data from {ts} ({reason})."),
            None => format!("Showing cached weather data ({reason})."),
        }]
    }
}
