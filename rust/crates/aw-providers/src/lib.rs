//! Weather data providers for the native AccessiWeather port.
//!
//! Every provider talks to the network through the [`HttpClient`] trait so
//! tests can replay recorded JSON fixtures without touching the network.

pub mod client;
pub mod current_location;
pub mod environmental;
pub mod geocoding;
pub mod http;
pub mod nws;
pub mod openmeteo;
pub mod pirateweather;
pub mod products;
pub mod surf_conditions;

pub use http::{HttpClient, HttpError, ReqwestClient};
