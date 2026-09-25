//! Weather-change event notifications, ported from
//! `notifications/notification_event_manager.py`,
//! `notification_event_state.py` and `notification_event_products.py`.
//!
//! The manager keeps its baselines in the `notification_events` section of
//! the runtime-state file. Checks never notify the first time they see a
//! value; they store it as the baseline.

pub mod minutely;
pub mod text;
pub mod window;

use std::collections::{BTreeSet, HashMap, HashSet};

use aw_core::model::{
    CurrentConditions, Location, MinutelyPrecipitationForecast, TextProduct, Timestamp,
    WeatherAlert, WeatherData,
};
use aw_core::settings::AppSettings;
use chrono::{DateTime, Duration, FixedOffset, Utc};
use serde_json::{json, Map, Value};

use crate::py::{self, PyDateTime};
use crate::runtime_state::{RuntimeState, Section};

/// Python keeps one HWO and one SPS toast per location per 30 minutes.
pub const PRODUCT_RATE_LIMIT_WINDOW_MINUTES: i64 = 30;

/// `NotificationEvent`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotificationEvent {
    pub event_type: String,
    pub title: String,
    pub message: String,
    pub sound_event: String,
}

impl NotificationEvent {
    fn new(
        event_type: &str,
        title: impl Into<String>,
        message: impl Into<String>,
        sound_event: &str,
    ) -> Self {
        Self {
            event_type: event_type.into(),
            title: title.into(),
            message: message.into(),
            sound_event: sound_event.into(),
        }
    }
}

/// `NotificationState`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct NotificationState {
    pub last_discussion_issuance_time: Option<Timestamp>,
    pub last_discussion_text: Option<String>,
    pub last_daily_climate_report_issuance_time: Option<Timestamp>,
    pub last_daily_climate_report_text: Option<String>,
    pub last_daily_climate_report_station: Option<String>,
    pub last_severe_risk: Option<i64>,
    pub last_minutely_transition_signature: Option<String>,
    pub last_minutely_likelihood_signature: Option<String>,
    /// Python stores `datetime.now()` here: a naive local time.
    pub last_check_time: Option<PyDateTime>,
    pub last_hwo_issuance_time: Option<Timestamp>,
    pub last_hwo_text: Option<String>,
    pub last_hwo_summary_signature: Option<String>,
    pub last_sps_product_ids: BTreeSet<String>,
}

fn iso(t: &Option<Timestamp>) -> Value {
    t.as_ref().map(py::isoformat).into()
}

impl NotificationState {
    /// `to_dict` (the legacy flat shape).
    pub fn to_legacy(&self) -> Map<String, Value> {
        let v = json!({
            "last_discussion_issuance_time": iso(&self.last_discussion_issuance_time),
            "last_discussion_text": self.last_discussion_text,
            "last_daily_climate_report_issuance_time": iso(&self.last_daily_climate_report_issuance_time),
            "last_daily_climate_report_text": self.last_daily_climate_report_text,
            "last_daily_climate_report_station": self.last_daily_climate_report_station,
            "last_severe_risk": self.last_severe_risk,
            "last_minutely_transition_signature": self.last_minutely_transition_signature,
            "last_minutely_likelihood_signature": self.last_minutely_likelihood_signature,
            "last_check_time": self.last_check_time.as_ref().map(PyDateTime::isoformat),
            "last_hwo_issuance_time": iso(&self.last_hwo_issuance_time),
            "last_hwo_text": self.last_hwo_text,
            "last_hwo_summary_signature": self.last_hwo_summary_signature,
            "last_sps_product_ids": self.last_sps_product_ids,
        });
        match v {
            Value::Object(m) => m,
            _ => unreachable!("json! object literal"),
        }
    }

    /// `from_dict`; `None` where Python would raise (the caller then keeps
    /// the default state).
    pub fn from_legacy(data: &Map<String, Value>) -> Option<Self> {
        let text = |k: &str| -> Option<Option<String>> {
            match data.get(k) {
                None | Some(Value::Null) => Some(None),
                Some(Value::String(s)) => Some(Some(s.clone())),
                Some(_) => None,
            }
        };
        let time = |k: &str| -> Option<Option<PyDateTime>> {
            match text(k)? {
                Some(s) if !s.is_empty() => py::fromisoformat(&s).map(Some),
                _ => Some(None),
            }
        };
        let aware = |k: &str| time(k).map(|t| t.map(PyDateTime::aware));
        let severe = match data.get("last_severe_risk") {
            None | Some(Value::Null) => None,
            Some(v) => Some(v.as_i64().or_else(|| v.as_f64().map(|f| f as i64))?),
        };
        let ids = match data.get("last_sps_product_ids") {
            None | Some(Value::Null) => BTreeSet::new(),
            Some(Value::Array(a)) => a
                .iter()
                .map(|v| v.as_str().map(str::to_string))
                .collect::<Option<_>>()?,
            Some(_) => return None,
        };
        Some(Self {
            last_discussion_issuance_time: aware("last_discussion_issuance_time")?,
            last_discussion_text: text("last_discussion_text")?,
            last_daily_climate_report_issuance_time: aware(
                "last_daily_climate_report_issuance_time",
            )?,
            last_daily_climate_report_text: text("last_daily_climate_report_text")?,
            last_daily_climate_report_station: text("last_daily_climate_report_station")?,
            last_severe_risk: severe,
            last_minutely_transition_signature: text("last_minutely_transition_signature")?,
            last_minutely_likelihood_signature: text("last_minutely_likelihood_signature")?,
            last_check_time: time("last_check_time")?,
            last_hwo_issuance_time: aware("last_hwo_issuance_time")?,
            last_hwo_text: text("last_hwo_text")?,
            last_hwo_summary_signature: text("last_hwo_summary_signature")?,
            last_sps_product_ids: ids,
        })
    }
}

fn truthy(v: Option<&Value>) -> Option<&Value> {
    v.filter(|v| match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
        Value::Number(n) => n.as_f64() != Some(0.0),
    })
}

/// `runtime_section_to_legacy_shape`.
pub fn runtime_section_to_legacy_shape(section: &Map<String, Value>) -> Option<Map<String, Value>> {
    let sub = |k: &str| -> Option<Map<String, Value>> {
        match section.get(k) {
            None => Some(Map::new()),
            Some(Value::Object(m)) => Some(m.clone()),
            Some(_) => None,
        }
    };
    let (discussion, climate, severe, minutely, hwo, sps) = (
        sub("discussion")?,
        sub("daily_climate_report")?,
        sub("severe_risk")?,
        sub("minutely_precipitation")?,
        sub("hwo")?,
        sub("sps")?,
    );
    let g = |m: &Map<String, Value>, k: &str| m.get(k).cloned().unwrap_or(Value::Null);
    let last_check = truthy(discussion.get("last_check_time"))
        .or_else(|| truthy(severe.get("last_check_time")))
        .or_else(|| minutely.get("last_check_time"))
        .cloned()
        .unwrap_or(Value::Null);
    let sps_ids = truthy(sps.get("last_product_ids"))
        .cloned()
        .unwrap_or_else(|| json!([]));
    let v = json!({
        "last_discussion_issuance_time": g(&discussion, "last_issuance_time"),
        "last_discussion_text": g(&discussion, "last_text"),
        "last_daily_climate_report_issuance_time": g(&climate, "last_issuance_time"),
        "last_daily_climate_report_text": g(&climate, "last_text"),
        "last_daily_climate_report_station": g(&climate, "last_station"),
        "last_severe_risk": g(&severe, "last_value"),
        "last_minutely_transition_signature": g(&minutely, "last_transition_signature"),
        "last_minutely_likelihood_signature": g(&minutely, "last_likelihood_signature"),
        "last_check_time": last_check,
        "last_hwo_issuance_time": g(&hwo, "last_issuance_time"),
        "last_hwo_text": g(&hwo, "last_text"),
        "last_hwo_summary_signature": g(&hwo, "last_summary_signature"),
        "last_sps_product_ids": sps_ids,
    });
    match v {
        Value::Object(m) => Some(m),
        _ => None,
    }
}

/// `legacy_shape_to_runtime_section`.
pub fn legacy_shape_to_runtime_section(data: &Map<String, Value>) -> Map<String, Value> {
    let g = |k: &str| data.get(k).cloned().unwrap_or(Value::Null);
    let last_check = g("last_check_time");
    let mut ids: Vec<String> = truthy(data.get("last_sps_product_ids"))
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();
    ids.sort();
    let v = json!({
        "discussion": {
            "last_issuance_time": g("last_discussion_issuance_time"),
            "last_text": g("last_discussion_text"),
            "last_check_time": last_check,
        },
        "daily_climate_report": {
            "last_issuance_time": g("last_daily_climate_report_issuance_time"),
            "last_text": g("last_daily_climate_report_text"),
            "last_station": g("last_daily_climate_report_station"),
            "last_check_time": last_check,
        },
        "severe_risk": {
            "last_value": g("last_severe_risk"),
            "last_check_time": last_check,
        },
        "minutely_precipitation": {
            "last_transition_signature": g("last_minutely_transition_signature"),
            "last_likelihood_signature": g("last_minutely_likelihood_signature"),
            "last_check_time": last_check,
        },
        "hwo": {
            "last_issuance_time": g("last_hwo_issuance_time"),
            "last_text": g("last_hwo_text"),
            "last_summary_signature": g("last_hwo_summary_signature"),
            "last_check_time": last_check,
        },
        "sps": {
            "last_product_ids": ids,
            "last_check_time": last_check,
        },
    });
    match v {
        Value::Object(m) => m,
        _ => unreachable!("json! object literal"),
    }
}

/// `NotificationEventManager`.
pub struct NotificationEventManager {
    store: Option<RuntimeState>,
    pub state: NotificationState,
    /// In-memory only, like Python: a restart re-evaluates against content.
    last_product_notified_at: HashMap<(&'static str, String), DateTime<Utc>>,
    sps_cold_started: HashSet<String>,
}

impl NotificationEventManager {
    /// `store: None` keeps state in memory only (`state_file=None`).
    pub fn new(store: Option<RuntimeState>, now: DateTime<Utc>) -> Self {
        let mut state = NotificationState::default();
        if let Some(store) = &store {
            let section = store.load_section(Section::NotificationEvents, now);
            match runtime_section_to_legacy_shape(&section)
                .and_then(|d| NotificationState::from_legacy(&d))
            {
                Some(s) => state = s,
                None => tracing::warn!("Failed to load notification state"),
            }
        }
        Self {
            store,
            state,
            last_product_notified_at: HashMap::new(),
            sps_cold_started: HashSet::new(),
        }
    }

    fn save_state(&self, now: DateTime<Utc>) {
        if let Some(store) = &self.store {
            let section = legacy_shape_to_runtime_section(&self.state.to_legacy());
            store.save_section(Section::NotificationEvents, &section, None, now);
        }
    }

    /// `check_for_events`: discussion, severe risk and minutely checks.
    /// `now` is the local wall-clock time (stored as Python's naive
    /// `datetime.now()`).
    pub fn check_for_events(
        &mut self,
        data: &WeatherData,
        settings: &AppSettings,
        location_name: &str,
        now: DateTime<FixedOffset>,
    ) -> Vec<NotificationEvent> {
        let mut events = Vec::new();
        if settings.notify_discussion_update {
            events.extend(self.check_discussion_update(
                data.discussion_issuance_time,
                data.discussion.as_deref(),
                location_name,
            ));
        }
        if settings.notify_severe_risk_change {
            if let Some(current) = &data.current {
                events.extend(self.check_severe_risk_change(current, location_name));
            }
        }
        if settings.notify_minutely_precipitation_start
            || settings.notify_minutely_precipitation_stop
        {
            events.extend(self.check_minutely_transition(
                data.minutely_precipitation.as_ref(),
                settings,
                location_name,
            ));
        }
        if settings.notify_precipitation_likelihood {
            events.extend(self.check_minutely_likelihood(
                data.minutely_precipitation.as_ref(),
                settings,
                location_name,
            ));
        }
        self.state.last_check_time = Some(PyDateTime::Naive(now.naive_local()));
        self.save_state(now.with_timezone(&Utc));
        events
    }

    fn check_discussion_update(
        &mut self,
        issuance_time: Option<Timestamp>,
        text: Option<&str>,
        location_name: &str,
    ) -> Option<NotificationEvent> {
        let issuance_time = issuance_time?;
        let Some(last) = self.state.last_discussion_issuance_time else {
            self.state.last_discussion_issuance_time = Some(issuance_time);
            self.state.last_discussion_text = text.map(str::to_string);
            return None;
        };
        if issuance_time <= last {
            self.state.last_discussion_text = text.map(str::to_string);
            return None;
        }
        let summary =
            text::summarize_discussion_change(self.state.last_discussion_text.as_deref(), text);
        self.state.last_discussion_issuance_time = Some(issuance_time);
        self.state.last_discussion_text = text.map(str::to_string);
        if summary.is_none()
            && text::is_no_change_summary(
                text::what_has_changed_section(text.unwrap_or("")).as_deref(),
            )
        {
            tracing::info!(
                "Discussion issuance advanced for {location_name}, but AFD says no changes; state updated without notification"
            );
            return None;
        }
        let issued = text::extract_discussion_issued_time_label(text)
            .unwrap_or_else(|| text::format_issuance_time_label(&issuance_time));
        let mut message = format!(
            "The Area Forecast Discussion for {location_name} was updated by the National Weather Service at {issued}."
        );
        if let Some(summary) = summary.filter(|s| !s.is_empty()) {
            message.push(' ');
            message.push_str(&summary);
        }
        Some(NotificationEvent::new(
            "discussion_update",
            "Forecast Discussion Updated",
            message,
            "discussion_update",
        ))
    }

    fn check_severe_risk_change(
        &mut self,
        current: &CurrentConditions,
        location_name: &str,
    ) -> Option<NotificationEvent> {
        let risk = current.severe_weather_risk?;
        let category = text::get_risk_category(risk);
        let Some(last) = self.state.last_severe_risk else {
            self.state.last_severe_risk = Some(risk);
            return None;
        };
        let previous = text::get_risk_category(last);
        self.state.last_severe_risk = Some(risk);
        if category == previous {
            return None;
        }
        let (verb, direction) = if text::risk_increased(previous, category) {
            ("Increased", "increased")
        } else {
            ("Decreased", "decreased")
        };
        Some(NotificationEvent::new(
            "severe_risk",
            format!("Severe Weather Risk {verb} to {}", title_case(category)),
            format!(
                "Severe weather risk for {location_name} has {direction} from {previous} to {category} (risk index: {risk})."
            ),
            "severe_risk",
        ))
    }

    fn check_minutely_transition(
        &mut self,
        forecast: Option<&MinutelyPrecipitationForecast>,
        settings: &AppSettings,
        location_name: &str,
    ) -> Option<NotificationEvent> {
        let threshold = minutely::sensitivity_threshold(&settings.precipitation_sensitivity);
        let mut signature = minutely::transition_signature(forecast, threshold)?;
        let transition = minutely::detect_transition(forecast, threshold);
        if transition
            .as_ref()
            .is_some_and(|t| t.minutes_until > minutely::TRANSITION_NOTICE_LEAD_MINUTES)
        {
            let pending = format!("pending:{signature}");
            let last = self.state.last_minutely_transition_signature.as_deref();
            if last != Some(pending.as_str()) && last != Some(signature.as_str()) {
                self.state.last_minutely_transition_signature = Some(pending);
            }
            return None;
        }
        let Some(last) = self.state.last_minutely_transition_signature.as_deref() else {
            self.state.last_minutely_transition_signature = Some(signature);
            return None;
        };
        if last == signature {
            return None;
        }
        self.state.last_minutely_transition_signature = Some(std::mem::take(&mut signature));
        let transition = transition?;
        let enabled = match transition.transition_type {
            "starting" => settings.notify_minutely_precipitation_start,
            _ => settings.notify_minutely_precipitation_stop,
        };
        if !enabled {
            return None;
        }
        let title = transition.title();
        Some(NotificationEvent::new(
            transition.event_type(),
            title.clone(),
            format!("{title} for {location_name}."),
            "notify",
        ))
    }

    fn check_minutely_likelihood(
        &mut self,
        forecast: Option<&MinutelyPrecipitationForecast>,
        settings: &AppSettings,
        location_name: &str,
    ) -> Option<NotificationEvent> {
        let threshold = settings.precipitation_likelihood_threshold;
        let signature = minutely::likelihood_signature(forecast, threshold)?;
        match self.state.last_minutely_likelihood_signature.as_deref() {
            None => {
                self.state.last_minutely_likelihood_signature = Some(signature);
                return None;
            }
            Some(last) if last == signature => return None,
            Some(_) => {}
        }
        self.state.last_minutely_likelihood_signature = Some(signature);
        let likelihood = minutely::detect_likelihood(forecast, threshold)?;
        let title = likelihood.title();
        Some(NotificationEvent::new(
            minutely::Likelihood::EVENT_TYPE,
            title.clone(),
            format!("{title} for {location_name}."),
            "notify",
        ))
    }

    /// `check_daily_climate_report`: notify only on a newer report from the
    /// same station.
    pub fn check_daily_climate_report(
        &mut self,
        product: Option<&TextProduct>,
        settings: &AppSettings,
        location_name: &str,
        now: DateTime<Utc>,
    ) -> Option<NotificationEvent> {
        let product = product?;
        if !settings.notify_daily_climate_report_update {
            return None;
        }
        let issuance = product.issuance_time?;
        if product.product_text.is_empty() {
            return None;
        }
        let station = product.cwa_office.clone();
        let same_station =
            self.state.last_daily_climate_report_station.as_deref() == Some(station.as_str());
        let last = match self.state.last_daily_climate_report_issuance_time {
            Some(last) if same_station => last,
            _ => {
                self.state.last_daily_climate_report_issuance_time = Some(issuance);
                self.state.last_daily_climate_report_text = Some(product.product_text.clone());
                self.state.last_daily_climate_report_station = Some(station);
                self.save_state(now);
                return None;
            }
        };
        if issuance <= last {
            self.state.last_daily_climate_report_text = Some(product.product_text.clone());
            self.save_state(now);
            return None;
        }
        let previous = self.state.last_daily_climate_report_text.clone();
        let summary =
            summarize_daily_climate_change(previous.as_deref(), Some(&product.product_text))
                .or_else(|| {
                    text::summarize_discussion_change(
                        previous.as_deref(),
                        Some(&product.product_text),
                    )
                });
        self.state.last_daily_climate_report_issuance_time = Some(issuance);
        self.state.last_daily_climate_report_text = Some(product.product_text.clone());
        self.state.last_daily_climate_report_station = Some(station.clone());
        self.save_state(now);
        let mut message = format!(
            "The Daily Climate Report for {location_name} ({station}) was updated by the National Weather Service."
        );
        if let Some(summary) = summary.filter(|s| !s.is_empty()) {
            message.push_str(" Change summary: ");
            message.push_str(&summary);
        }
        Some(NotificationEvent::new(
            "daily_climate_report_update",
            "Daily Climate Report Updated",
            message,
            "discussion_update",
        ))
    }

    fn rate_limited(&mut self, product: &'static str, location: &str, now: DateTime<Utc>) -> bool {
        let key = (product, location.to_string());
        if let Some(last) = self.last_product_notified_at.get(&key) {
            if now - *last < Duration::minutes(PRODUCT_RATE_LIMIT_WINDOW_MINUTES) {
                return true;
            }
        }
        self.last_product_notified_at.insert(key, now);
        false
    }

    /// `check_hwo_update`: returns the notification to dispatch, if any.
    /// State and the per-location rate limit advance even when the caller
    /// decides not to show it (startup suppression).
    pub fn check_hwo_update(
        &mut self,
        location: &Location,
        product: Option<&TextProduct>,
        settings: &AppSettings,
        now: DateTime<Utc>,
    ) -> Option<NotificationEvent> {
        let product = product?;
        location.cwa_office.as_deref().filter(|c| !c.is_empty())?;
        let signature = text::hash_product_text(&product.product_text);
        let stored_issuance = self.state.last_hwo_issuance_time;
        let stored_text = self.state.last_hwo_text.clone();
        if stored_issuance.is_none() && self.state.last_hwo_summary_signature.is_none() {
            self.state.last_hwo_issuance_time = product.issuance_time;
            self.state.last_hwo_text = Some(product.product_text.clone());
            self.state.last_hwo_summary_signature = Some(signature);
            self.save_state(now);
            return None;
        }
        if stored_issuance == product.issuance_time
            && self.state.last_hwo_summary_signature.as_deref() == Some(signature.as_str())
        {
            return None;
        }
        self.state.last_hwo_issuance_time = product.issuance_time;
        self.state.last_hwo_text = Some(product.product_text.clone());
        self.state.last_hwo_summary_signature = Some(signature);
        self.save_state(now);
        if !settings.notify_hwo_update || self.rate_limited("HWO", &location.name, now) {
            return None;
        }
        Some(NotificationEvent::new(
            "hwo_update",
            "Hazardous Weather Outlook Updated",
            text::format_hwo_body(stored_text.as_deref(), product),
            "notify",
        ))
    }

    /// `check_sps_new`: informational Special Weather Statements only
    /// (statements an active SPS alert already covers are skipped), at most
    /// one per call and one per location per 30 minutes.
    pub fn check_sps_new(
        &mut self,
        location: &Location,
        products: &[TextProduct],
        alerts: &[WeatherAlert],
        settings: &AppSettings,
        now: DateTime<Utc>,
    ) -> Option<NotificationEvent> {
        let current_ids: BTreeSet<String> = products.iter().map(|p| p.product_id.clone()).collect();
        let cold_start = !self.sps_cold_started.contains(&location.name)
            && self.state.last_sps_product_ids.is_empty();
        if cold_start {
            if !current_ids.is_empty() {
                self.state.last_sps_product_ids.extend(current_ids);
                self.save_state(now);
            }
            self.sps_cold_started.insert(location.name.clone());
            return None;
        }
        let before = self.state.last_sps_product_ids.len();
        self.state
            .last_sps_product_ids
            .retain(|id| current_ids.contains(id));
        if self.state.last_sps_product_ids.len() != before {
            self.save_state(now);
        }
        let new_products: Vec<&TextProduct> = products
            .iter()
            .filter(|p| !self.state.last_sps_product_ids.contains(&p.product_id))
            .collect();
        if new_products.is_empty() {
            return None;
        }
        let signatures = text::sps_alert_signatures(alerts);
        let mut dispatched = None;
        for product in new_products {
            self.state
                .last_sps_product_ids
                .insert(product.product_id.clone());
            if text::sps_is_case_a(product, &signatures) || !settings.notify_sps_issued {
                continue;
            }
            let key = ("SPS", location.name.clone());
            let recently = self.last_product_notified_at.get(&key).is_some_and(|last| {
                now - *last < Duration::minutes(PRODUCT_RATE_LIMIT_WINDOW_MINUTES)
            });
            if recently || dispatched.is_some() {
                continue;
            }
            self.last_product_notified_at.insert(key, now);
            dispatched = Some(NotificationEvent::new(
                "sps_issued",
                "Special Weather Statement",
                text::format_sps_body(product),
                "notify",
            ));
        }
        self.save_state(now);
        dispatched
    }

    /// `reset_state`.
    pub fn reset_state(&mut self, now: DateTime<Utc>) {
        self.state = NotificationState::default();
        self.save_state(now);
    }
}

/// `_summarize_daily_climate_change`: up to three new temperature,
/// precipitation or snowfall lines.
fn summarize_daily_climate_change(previous: Option<&str>, current: Option<&str>) -> Option<String> {
    let previous_lines: HashSet<String> = py::splitlines(previous.unwrap_or(""))
        .into_iter()
        .filter(|l| !l.trim().is_empty())
        .map(py::collapse_whitespace)
        .collect();
    const INTERESTING: &[&str] = &["MAXIMUM", "MINIMUM", "AVERAGE", "PRECIPITATION", "SNOWFALL"];
    let mut changed = Vec::new();
    for raw in py::splitlines(current.unwrap_or("")) {
        let line = py::collapse_whitespace(raw);
        if line.is_empty() || previous_lines.contains(&line) {
            continue;
        }
        let upper = line.to_uppercase();
        if INTERESTING.iter().any(|t| upper.contains(t)) {
            changed.push(line);
        }
        if changed.len() == 3 {
            break;
        }
    }
    if changed.is_empty() {
        text::summarize_discussion_change(previous, current)
    } else {
        Some(changed.join("; "))
    }
}

/// `str.title()` for a single lowercase word.
fn title_case(word: &str) -> String {
    let mut c = word.chars();
    c.next()
        .map(|f| f.to_uppercase().chain(c).collect())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn local(s: &str) -> DateTime<FixedOffset> {
        DateTime::parse_from_rfc3339(s).unwrap()
    }

    fn settings(f: impl FnOnce(&mut AppSettings)) -> AppSettings {
        let mut s = AppSettings {
            notify_discussion_update: false,
            notify_hwo_update: false,
            notify_sps_issued: false,
            notify_minutely_precipitation_start: false,
            notify_minutely_precipitation_stop: false,
            ..AppSettings::default()
        };
        f(&mut s);
        s
    }

    #[test]
    fn discussion_baseline_then_update() {
        let mut m = NotificationEventManager::new(None, Utc::now());
        let s = settings(|s| s.notify_discussion_update = true);
        let mut data = WeatherData {
            discussion: Some("Discussion text without an issued header".into()),
            discussion_issuance_time: Some(local("2026-01-20T14:35:00+00:00")),
            ..WeatherData::default()
        };
        let now = local("2026-01-20T10:00:00-05:00");
        assert!(m.check_for_events(&data, &s, "Test", now).is_empty());
        assert!(m.check_for_events(&data, &s, "Test", now).is_empty());
        data.discussion_issuance_time = Some(local("2026-01-20T17:35:00+00:00"));
        let events = m.check_for_events(&data, &s, "Test", now);
        assert_eq!(events.len(), 1);
        assert_eq!(
            events[0].message,
            "The Area Forecast Discussion for Test was updated by the National Weather Service at 5:35 PM UTC."
        );
        assert_eq!(
            m.state.last_check_time.unwrap().isoformat(),
            "2026-01-20T10:00:00"
        );
    }

    #[test]
    fn severe_risk_bands() {
        let mut m = NotificationEventManager::new(None, Utc::now());
        let s = settings(|s| s.notify_severe_risk_change = true);
        let now = local("2026-01-20T10:00:00-05:00");
        let mut data = WeatherData::default();
        let risk = |v| CurrentConditions {
            severe_weather_risk: Some(v),
            ..Default::default()
        };
        data.current = Some(risk(25));
        assert!(m.check_for_events(&data, &s, "Home", now).is_empty());
        data.current = Some(risk(35));
        assert!(m.check_for_events(&data, &s, "Home", now).is_empty());
        data.current = Some(risk(65));
        let e = m.check_for_events(&data, &s, "Home", now);
        assert_eq!(e[0].title, "Severe Weather Risk Increased to High");
        assert_eq!(
            e[0].message,
            "Severe weather risk for Home has increased from low to high (risk index: 65)."
        );
    }

    #[test]
    fn state_shapes_round_trip() {
        let state = NotificationState {
            last_severe_risk: Some(35),
            last_sps_product_ids: ["b".to_string(), "a".to_string()].into(),
            last_check_time: py::fromisoformat("2026-03-16T14:31:00"),
            ..NotificationState::default()
        };
        let section = legacy_shape_to_runtime_section(&state.to_legacy());
        assert_eq!(section["sps"]["last_product_ids"], json!(["a", "b"]));
        let back =
            NotificationState::from_legacy(&runtime_section_to_legacy_shape(&section).unwrap())
                .unwrap();
        assert_eq!(back, state);
    }
}
