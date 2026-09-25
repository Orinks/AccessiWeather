//! Main-window event notification flow, ported from
//! `ui/main_window_notification_events.py` (minus the wx plumbing): which
//! checks run after a full refresh, in what order, what reaches the Event
//! Center, and how SPS products are narrowed to the location's zones.

use std::collections::BTreeSet;
use std::sync::LazyLock;

use aw_core::model::{Location, TextProduct, WeatherAlert, WeatherData};
use aw_core::settings::AppSettings;
use chrono::{DateTime, FixedOffset, Utc};
use regex::Regex;

use super::NotificationEventManager;
use crate::activation::ActivationRequest;
use crate::py;
use crate::Toast;

/// Event toasts use Python's 10 s timeout.
pub const EVENT_TOAST_TIMEOUT_SECONDS: u32 = 10;

/// A reviewable line for the Event Center (`append_event_center_entry`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EventCenterEntry {
    pub category: String,
    pub text: String,
}

impl EventCenterEntry {
    /// `"[3:05 PM] Category: text\n"` at the given local time.
    pub fn format(&self, now_local: &DateTime<FixedOffset>) -> String {
        format_event_center_entry(now_local, Some(&self.category), &self.text)
    }
}

/// `append_event_center_entry`'s line format (empty text yields nothing).
pub fn format_event_center_entry(
    now_local: &DateTime<FixedOffset>,
    category: Option<&str>,
    text: &str,
) -> String {
    if text.is_empty() {
        return String::new();
    }
    let prefix = category
        .filter(|c| !c.is_empty())
        .map(|c| format!("{c}: "))
        .unwrap_or_default();
    format!("[{}] {prefix}{text}\n", py::clock_12h(now_local))
}

/// Text products already in the forecast-product cache for the location.
/// `None` means "not cached" (the check is skipped); `Some(&[])` for SPS
/// means the office currently has no statements (old ids expire).
#[derive(Debug, Clone, Copy, Default)]
pub struct CachedProducts<'a> {
    /// `nws_text_product:HWO:{cwa}`.
    pub hwo: Option<&'a TextProduct>,
    /// `nws_text_product:SPS:{cwa}`.
    pub sps: Option<&'a [TextProduct]>,
    /// The first cached `iem_text_product:CLI:{station}:latest` among the
    /// location's daily-climate station candidates.
    pub daily_climate: Option<&'a TextProduct>,
}

/// What `process_notification_events` produced, in Python's order.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct EventDispatch {
    pub toasts: Vec<Toast>,
    pub event_center: Vec<EventCenterEntry>,
}

impl EventDispatch {
    fn push(
        &mut self,
        title: &str,
        message: &str,
        sound_event: &str,
        play_sound: bool,
        activation: ActivationRequest,
    ) {
        if !message.is_empty() {
            self.event_center.push(EventCenterEntry {
                category: title.into(),
                text: message.into(),
            });
        }
        self.toasts.push(Toast {
            title: title.into(),
            message: message.into(),
            timeout: EVENT_TOAST_TIMEOUT_SECONDS,
            sound_event: Some(sound_event.into()),
            sound_candidates: None,
            play_sound,
            activation: Some(activation),
        });
    }
}

/// `process_notification_events`, run after each full weather refresh.
/// `suppress_startup` is the window's `_suppress_startup_text_product_notifications`
/// flag (true until the first run): the first discussion/HWO/SPS/CLI
/// results only set baselines. `now` is local wall-clock time.
#[allow(clippy::too_many_arguments)]
pub fn process_notification_events(
    manager: &mut NotificationEventManager,
    weather_data: &WeatherData,
    settings: &AppSettings,
    location: Option<&Location>,
    products: CachedProducts<'_>,
    active_alerts: &[WeatherAlert],
    suppress_startup: &mut bool,
    now: DateTime<FixedOffset>,
) -> EventDispatch {
    let mut out = EventDispatch::default();
    let any_enabled = settings.notify_discussion_update
        || settings.notify_severe_risk_change
        || settings.notify_minutely_precipitation_start
        || settings.notify_minutely_precipitation_stop
        || settings.notify_precipitation_likelihood
        || settings.notify_hwo_update
        || settings.notify_sps_issued
        || settings.notify_daily_climate_report_update;
    if !any_enabled {
        return out;
    }
    let Some(location) = location else {
        tracing::warn!("[events] _process_notification_events: no current location");
        return out;
    };
    let now_utc = now.with_timezone(&Utc);
    let suppress = *suppress_startup;

    let mut events = manager.check_for_events(weather_data, settings, &location.name, now);
    if suppress {
        events.retain(|e| e.event_type != "discussion_update");
    }

    let has_cwa = location
        .cwa_office
        .as_deref()
        .is_some_and(|c| !c.is_empty());
    if has_cwa {
        if let Some(product) = products.hwo {
            if let Some(event) =
                manager.check_hwo_update(location, Some(product), settings, now_utc)
            {
                if !suppress {
                    out.push(
                        &event.title,
                        &event.message,
                        "notify",
                        settings.sound_enabled,
                        ActivationRequest::generic_fallback(),
                    );
                }
            }
        }
        if let Some(sps) = products.sps {
            let filtered = filter_sps_products_for_location(sps, location);
            if let Some(event) =
                manager.check_sps_new(location, &filtered, active_alerts, settings, now_utc)
            {
                if !suppress {
                    out.push(
                        &event.title,
                        &event.message,
                        "notify",
                        settings.sound_enabled,
                        ActivationRequest::generic_fallback(),
                    );
                }
            }
        }
    }
    if settings.notify_daily_climate_report_update {
        if let Some(event) = manager.check_daily_climate_report(
            products.daily_climate,
            settings,
            &location.name,
            now_utc,
        ) {
            if !suppress {
                out.push(
                    &event.title,
                    &event.message,
                    &event.sound_event,
                    settings.sound_enabled,
                    ActivationRequest::generic_fallback(),
                );
            }
        }
    }
    if suppress {
        *suppress_startup = false;
    }

    for event in events {
        let activation = if event.event_type == "discussion_update" {
            ActivationRequest::discussion()
        } else {
            ActivationRequest::generic_fallback()
        };
        out.push(
            &event.title,
            &event.message,
            &event.sound_event,
            settings.sound_enabled,
            activation,
        );
    }
    out
}

static UGC_LINE_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^\s*([A-Z]{2}[CZ])(\d{3}(?:[->]\d{3})?(?:-\d{3}(?:[->]\d{3})?)*)-\d{6}-?\s*$")
        .expect("static regex")
});

/// `_filter_sps_products_for_location`: keep office-wide SPS products whose
/// UGC line names one of the location's zones (or has no UGC line at all).
pub fn filter_sps_products_for_location(
    products: &[TextProduct],
    location: &Location,
) -> Vec<TextProduct> {
    let zones = location_zone_ids(location);
    if zones.is_empty() {
        return products.to_vec();
    }
    products
        .iter()
        .filter(|p| {
            let ids = sps_product_zone_ids(&p.product_text);
            ids.is_empty() || !ids.is_disjoint(&zones)
        })
        .cloned()
        .collect()
}

fn location_zone_ids(location: &Location) -> BTreeSet<String> {
    [
        &location.forecast_zone_id,
        &location.fire_zone_id,
        &location.county_zone_id,
    ]
    .into_iter()
    .filter_map(|z| zone_id_tail(z.as_deref()))
    .collect()
}

fn zone_id_tail(value: Option<&str>) -> Option<String> {
    let value = value.filter(|v| !v.is_empty())?;
    let trimmed = value.trim_end_matches('/');
    let tail = trimmed.rsplit('/').next().unwrap_or(trimmed).to_uppercase();
    (!tail.is_empty()).then_some(tail)
}

/// `_sps_product_zone_ids`: UGC codes such as `TXZ118` or `TXZ105>107`
/// from the first 20 lines.
pub fn sps_product_zone_ids(product_text: &str) -> BTreeSet<String> {
    let mut ids = BTreeSet::new();
    for line in py::splitlines(product_text).into_iter().take(20) {
        let Some(c) = UGC_LINE_RE.captures(line) else {
            continue;
        };
        let prefix = &c[1];
        for token in c[2].split('-').filter(|t| !t.is_empty()) {
            if let Some((start, end)) = token.split_once('>') {
                let (Ok(start), Ok(end)) = (start.parse::<i32>(), end.parse::<i32>()) else {
                    continue;
                };
                let (lo, hi) = (start.min(end), start.max(end));
                ids.extend((lo..=hi).map(|v| format!("{prefix}{v:03}")));
            } else if let Ok(v) = token.parse::<i32>() {
                ids.insert(format!("{prefix}{v:03}"));
            }
        }
    }
    ids
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sps(text: &str) -> TextProduct {
        TextProduct {
            product_type: "SPS".into(),
            product_id: "SPS-FWD".into(),
            cwa_office: "FWD".into(),
            issuance_time: None,
            product_text: text.into(),
            headline: Some("Special Weather Statement".into()),
        }
    }

    #[test]
    fn sps_zone_filtering() {
        let mut loc = Location::new("Copperas Cove", 31.1241, -97.9031);
        loc.forecast_zone_id = Some("TXZ157".into());
        loc.county_zone_id = Some("https://api.weather.gov/zones/county/TXC099/".into());
        let dallas = sps("\nTXZ118-119-291900-\nTarrant TX-Dallas TX-\n");
        let local = sps("\nTXZ105>107-157-291900-\nCoryell TX-\n");
        assert!(filter_sps_products_for_location(&[dallas], &loc).is_empty());
        assert_eq!(
            filter_sps_products_for_location(std::slice::from_ref(&local), &loc).len(),
            1
        );
        let ids: Vec<_> = sps_product_zone_ids(&local.product_text)
            .into_iter()
            .collect();
        assert_eq!(ids, ["TXZ105", "TXZ106", "TXZ107", "TXZ157"]);
    }

    #[test]
    fn event_center_line() {
        let now = DateTime::parse_from_rfc3339("2026-09-25T15:05:00-04:00").unwrap();
        assert_eq!(
            format_event_center_entry(&now, Some("Special Weather Statement"), "Body"),
            "[3:05 PM] Special Weather Statement: Body\n"
        );
        assert_eq!(format_event_center_entry(&now, None, "x"), "[3:05 PM] x\n");
    }
}
