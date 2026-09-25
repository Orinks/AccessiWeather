//! Core domain layer for the native AccessiWeather port.
//!
//! Everything here is pure Rust with no I/O so it can be unit tested and
//! shared by the providers, the storage layer and the UI.

pub mod alert_aggregator;
pub mod alert_lifecycle;
pub mod alerts;
pub mod display;
pub mod forecast_confidence;
pub mod fusion;
#[cfg(any(test, feature = "golden"))]
pub mod golden;
pub mod location;
pub mod location_sorting;
pub mod model;
pub mod presenter;
pub mod provider_normalization;
pub mod py;
pub mod settings;
pub mod shortcut_preferences;
pub mod shortcuts;
pub mod sound_events;
pub mod source_selection;
pub mod sources;
pub mod thermal_comfort;
pub mod trends;
pub mod ttl_cache;
pub mod units;
pub mod weather;
pub mod weather_anomaly;
pub mod weather_client_parsers;
pub mod weather_history;

pub use alerts::{WeatherAlert, WeatherAlerts};
pub use location::{is_us_location, Location};
pub use settings::{AppConfig, AppSettings};
pub use sources::{DataSource, SourcePlan};
pub use weather::{
    CurrentConditions, Forecast, ForecastPeriod, HourlyForecast, HourlyForecastPeriod, WeatherData,
};

/// Application name used for paths, user agents and window titles.
pub const APP_NAME: &str = "AccessiWeather";
/// Vendor/author folder used on Windows.
pub const APP_AUTHOR: &str = "Orinks";
/// Semantic version of the Rust port.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
