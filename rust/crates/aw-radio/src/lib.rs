//! NOAA Weather Radio for the native AccessiWeather port: the station
//! directory, stream URL resolution, network playback, the shared playback
//! session, the global-hotkey toggle, alert auto-tune and the headless model
//! behind the NOAA Weather Radio dialog.
//!
//! Ports `accessiweather/noaa_radio/*` and the non-widget logic of
//! `ui/dialogs/noaa_radio_dialog.py`. Everything the UI needs hangs off
//! [`RadioContext`].

pub mod audio;
pub mod auto_tune;
pub mod availability;
mod data;
pub mod player;
pub mod preferences;
pub mod session;
pub mod stations;
pub mod stream_url;
pub mod toggle;
pub mod weatherindex;
pub mod wxradio;

pub use audio::RodioBackend;
pub use auto_tune::AlertRadioAutoTuner;
pub use player::{AudioBackend, AudioStream, PlayerEvent, RadioPlayer};
pub use preferences::{RadioPreferences, SharedPreferences};
pub use session::RadioSession;
pub use stations::{Station, StationDatabase};
pub use stream_url::{StreamUrlProvider, StreamUrls};
pub use toggle::RadioToggleController;

use serde_json::Value;

/// A unit of background work.
pub type Work = Box<dyn FnOnce() + Send>;

/// Runs work on a new thread; injectable so tests can run it inline or hold
/// it back (Python's `thread_factory`).
pub type Spawner = std::sync::Arc<dyn Fn(Work) + Send + Sync>;

/// A spawner that starts a named background thread.
pub fn thread_spawner(name: &'static str) -> Spawner {
    std::sync::Arc::new(move |work| {
        if let Err(e) = std::thread::Builder::new().name(name.into()).spawn(work) {
            tracing::error!("could not start {name} thread: {e}");
        }
    })
}

/// Text of Python's `json.dumps(value, indent=2)` (ASCII-only output), so
/// files the Rust app writes are byte-identical to the Python app's.
pub(crate) fn python_json(value: &Value) -> String {
    let pretty = serde_json::to_string_pretty(value).unwrap_or_default();
    let mut out = String::with_capacity(pretty.len());
    for c in pretty.chars() {
        if c.is_ascii() {
            out.push(c);
        } else {
            let mut units = [0u16; 2];
            for unit in c.encode_utf16(&mut units) {
                out.push_str(&format!("\\u{unit:04x}"));
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn python_json_matches_json_dumps_indent_2() {
        let value = json!({"b": [], "a": {}, "c": ["x", null, 1.5], "d": "é😀"});
        assert_eq!(
            python_json(&value),
            "{\n  \"b\": [],\n  \"a\": {},\n  \"c\": [\n    \"x\",\n    null,\n    1.5\n  ],\n  \"d\": \"\\u00e9\\ud83d\\ude00\"\n}"
        );
    }
}
