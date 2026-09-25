//! NWS and IEM text products behind Forecaster Notes, National Products and
//! Advanced Text Product Lookup.
//!
//! | Python | Rust |
//! |---|---|
//! | `weather_client_nws_forecast.py` (text-product half) | [`nws_text`] |
//! | `iem_client.py` | [`iem`] |
//! | `surf_conditions.py` | [`surf`] |
//! | `services/forecast_product_service.py` (+ the pre-warm in `ui/main_window_refresh.py`) | [`service`] |
//! | `services/national_discussion_*.py` | [`national`] |
//! | tab rules of `ui/dialogs/forecast_products_dialog.py`, `national_products_dialog.py`, `forecast_product_formatting.py` | [`tabs`] |
//! | lookup logic of `ui/dialogs/advanced_text_product_dialog.py` | [`advanced`] |

pub mod advanced;
pub mod iem;
pub mod national;
pub mod nws_text;
pub mod py;
pub mod service;
pub mod surf;
pub mod tabs;

use aw_core::model::TextProduct;

use crate::http::HttpError;

pub use service::ForecastProductService;

/// A text-product fetch failed (Python's `TextProductFetchError` /
/// `IemProductFetchError`). The message is what the user sees.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("{0}")]
pub struct ProductError(pub String);

/// What the current-product endpoint yields: one product (AFD, HWO, SRF, ...)
/// or a newest-first list (SPS). Python's `TextProduct | list | None`.
#[derive(Debug, Clone, PartialEq)]
pub enum ProductResult {
    One(Option<TextProduct>),
    Many(Vec<TextProduct>),
}

impl ProductResult {
    /// The panel's normalisation: `None` → `[]`, single → `[single]`.
    pub fn into_products(self) -> Vec<TextProduct> {
        match self {
            ProductResult::One(product) => product.into_iter().collect(),
            ProductResult::Many(products) => products,
        }
    }

    /// First product, the way AFD/HWO readers unwrap the cache.
    pub fn first(&self) -> Option<&TextProduct> {
        match self {
            ProductResult::One(product) => product.as_ref(),
            ProductResult::Many(products) => products.first(),
        }
    }
}

/// Message of an httpx-style transport failure (`str(exc)`).
fn transport_message(err: &HttpError) -> String {
    match err {
        HttpError::Transport { message, .. } | HttpError::Json { message, .. } => message.clone(),
        other => other.to_string(),
    }
}
