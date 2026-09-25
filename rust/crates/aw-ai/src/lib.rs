//! AI features of AccessiWeather without any UI: weather and text-product
//! explanations, the model catalogs behind the model browser, key validation
//! and the Weather Assistant's tool-calling conversation, for OpenRouter and
//! Venice AI.
//!
//! Every network call blocks; run them on a worker thread and pass a
//! [`CancelToken`] to abandon a request early. Error messages
//! ([`AiError`]'s `Display`) are the exact texts the Python app shows.
//!
//! Entry points:
//! - explanations: [`AiExplainer`] (built with [`AiExplainer::from_settings`]),
//!   fed by [`payload::build_current_weather_payload`] and
//!   [`payload::add_location_time_context`];
//! - Settings > AI: [`provider::validate_openrouter_api_key`],
//!   [`provider::validate_venice_api_key`], [`explainer::default_system_prompt`];
//! - model browser: [`models::load_catalog`], [`models::filter_models`] and
//!   the text helpers beside it;
//! - Weather Assistant: [`assistant::prepare_request`],
//!   [`assistant::generate_response`] with a [`tools::WeatherToolExecutor`]
//!   over the app's [`tools::AssistantHost`].

pub mod assistant;
pub mod errors;
pub mod explainer;
pub mod formatters;
pub mod models;
pub mod payload;
pub mod provider;
pub mod pyfmt;
pub mod tools;
pub mod transport;

#[cfg(test)]
mod test_server;

pub use errors::{AiError, AiErrorKind};
pub use explainer::{AiExplainer, ExplanationCache, ExplanationResult, ExplanationStyle};
pub use provider::Provider;
pub use transport::{CancelToken, StreamLimits};
