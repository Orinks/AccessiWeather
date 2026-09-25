//! The presentation layer: every piece of weather text the user reads.
//!
//! Ports `accessiweather/display` (the presenter, `presentation/*` and the
//! priority engine) together with the formatting helpers it relies on and
//! the tray tooltip formatter. Pure logic: "now" and the system timezone
//! come in through [`Clock`].

pub mod alerts;
pub mod aviation;
pub mod current;
pub mod environmental;
pub mod forecast;
pub mod impact;
pub mod measurement;
pub mod mobility;
pub mod models;
pub mod presenter;
pub mod priority;
pub mod pyfmt;
pub mod source_attribution;
pub mod taf;
pub mod time;
pub mod tray;
pub mod units;

pub use models::*;
pub use presenter::WeatherPresenter;
pub use time::{Clock, PyDateTime};
pub use tray::TaskbarIconUpdater;
