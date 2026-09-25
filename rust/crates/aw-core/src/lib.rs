//! Core domain layer for the native AccessiWeather port.
//!
//! Everything here is pure Rust with no I/O so it can be unit tested and
//! shared by the providers, the storage layer and the UI.

pub mod alerts;
pub mod display;
pub mod location;
pub mod model;
pub mod presenter;
pub mod settings;
pub mod sources;
pub mod units;
pub mod weather;

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
