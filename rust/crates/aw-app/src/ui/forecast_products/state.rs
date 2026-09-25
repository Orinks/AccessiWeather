//! What a Forecaster Notes tab shows, kept free of wx so it can be
//! golden-tested: the content-state machine of `forecast_product_panel.py`
//! and `format_issuance` from `forecast_product_formatting.py` (the other
//! tables of that module live in `aw_providers::products::tabs`).

use aw_core::model::{TextProduct, Timestamp};
use aw_providers::products::tabs::{self, NO_CWA_COPY};
use chrono::{DateTime, FixedOffset, Local, Offset, Utc};

use super::ai_summary::Summary;

pub(crate) const LOADING: &str = "Loading...";
pub(crate) const GENERATING: &str =
    "Generating plain language summary. Using the selected AI provider...";

/// Panel header: the product's full name.
pub(crate) fn header_text(product_type: &str) -> &str {
    tabs::product_full_name(product_type).unwrap_or(product_type)
}

/// The OS local zone at an instant: its UTC offset and the name `%Z` prints.
pub(crate) type Zone = fn(DateTime<Utc>) -> (FixedOffset, String);

/// `format_issuance` in the user's OS local time zone.
pub(crate) fn format_issuance(issuance_time: Option<&Timestamp>) -> String {
    format_issuance_in(issuance_time, local_zone)
}

/// `"Issued: %Y-%m-%d %H:%M %Z"`, stripped, in the zone `zone` reports.
pub(crate) fn format_issuance_in(issuance_time: Option<&Timestamp>, zone: Zone) -> String {
    let Some(time) = issuance_time else {
        return "Issued: unknown".into();
    };
    let (offset, name) = zone(time.to_utc());
    let local = time.with_timezone(&offset);
    format!("Issued: {} {name}", local.format("%Y-%m-%d %H:%M"))
        .trim_end()
        .to_string()
}

/// Python's `astimezone()` zone. On Windows the C runtime names it with the
/// full `GetTimeZoneInformation` name ("Eastern Daylight Time"); elsewhere
/// with the `tm_zone` abbreviation ("EDT").
fn local_zone(at: DateTime<Utc>) -> (FixedOffset, String) {
    let offset = at.with_timezone(&Local).offset().fix();
    (offset, zone_name(at, offset))
}

#[cfg(windows)]
fn zone_name(_at: DateTime<Utc>, offset: FixedOffset) -> String {
    #[repr(C)]
    struct SystemTime([u16; 8]);
    #[repr(C)]
    struct TimeZoneInformation {
        bias: i32,
        standard_name: [u16; 32],
        standard_date: SystemTime,
        standard_bias: i32,
        daylight_name: [u16; 32],
        daylight_date: SystemTime,
        daylight_bias: i32,
    }
    #[link(name = "kernel32")]
    extern "system" {
        fn GetTimeZoneInformation(info: *mut TimeZoneInformation) -> u32;
    }
    // SAFETY: the struct matches TIME_ZONE_INFORMATION and outlives the call.
    let info = unsafe {
        let mut info: TimeZoneInformation = std::mem::zeroed();
        if GetTimeZoneInformation(&mut info) == u32::MAX {
            return String::new();
        }
        info
    };
    let minutes_east = offset.local_minus_utc() / 60;
    // wMonth == 0: the zone has no daylight saving time.
    let is_dst = info.daylight_date.0[1] != 0
        && info.daylight_bias != info.standard_bias
        && minutes_east == -(info.bias + info.daylight_bias);
    let name = if is_dst {
        &info.daylight_name
    } else {
        &info.standard_name
    };
    let len = name.iter().position(|&c| c == 0).unwrap_or(name.len());
    String::from_utf16_lossy(&name[..len])
}

#[cfg(unix)]
fn zone_name(at: DateTime<Utc>, _offset: FixedOffset) -> String {
    let time = at.timestamp() as libc::time_t;
    // SAFETY: localtime_r fills the zeroed tm; tm_zone points into static
    // storage that stays valid until the next tzset.
    unsafe {
        let mut tm: libc::tm = std::mem::zeroed();
        if libc::localtime_r(&time, &mut tm).is_null() || tm.tm_zone.is_null() {
            return String::new();
        }
        std::ffi::CStr::from_ptr(tm.tm_zone)
            .to_string_lossy()
            .into_owned()
    }
}

/// `_build_model_info`: the metadata shown after a summary finishes.
pub(crate) fn build_model_info(summary: &Summary) -> String {
    let cost_text = match summary.estimated_cost {
        None => "See provider account".to_string(),
        Some(0.0) => "No cost".to_string(),
        Some(cost) => format!("~${cost:.6}"),
    };
    let mut lines = vec![
        format!("Model: {}", summary.model_used),
        format!("Tokens: {}", summary.token_count),
        format!("Cost: {cost_text}"),
    ];
    if let Some(requested) = summary
        .requested_model
        .as_deref()
        .filter(|r| !r.is_empty() && *r != summary.model_used)
    {
        lines.push(format!("Requested: {requested}"));
    }
    if let Some(reason) = summary
        .model_selection_reason
        .as_deref()
        .filter(|r| !r.is_empty())
    {
        lines.push(format!("Selection: {reason}"));
    }
    if summary.model_attempts.len() > 1 {
        lines.push(format!("Tried: {}", summary.model_attempts.join(", ")));
    }
    if summary.cached {
        lines.push("Cached: Yes".into());
    }
    lines.join("\n")
}

/// How products are turned into text; injectable so tests can pin the
/// time zone.
#[derive(Clone, Copy)]
pub(crate) struct Formatters {
    pub issuance: fn(Option<&Timestamp>) -> String,
    pub sps_entry: fn(&TextProduct) -> String,
}

pub(crate) const LOCAL_FORMATTERS: Formatters = Formatters {
    issuance: format_issuance,
    sps_entry: tabs::format_sps_choice_entry,
};

/// Everything a panel's widgets show.
#[derive(Debug, Clone, PartialEq)]
#[cfg_attr(test, derive(serde::Deserialize))]
pub(crate) struct PanelView {
    pub product_text: String,
    pub issuance: String,
    pub sps_entries: Vec<String>,
    pub sps_selection: Option<usize>,
    /// "Recent Special Weather Statements:" and its choice (SPS tabs only).
    pub sps_visible: bool,
    pub retry_visible: bool,
    /// "Plain Language Summary:" and the summary text.
    pub ai_visible: bool,
    pub ai_text: String,
    /// "Model Information:" and the model text.
    pub model_info_visible: bool,
    pub model_info: String,
    pub explain_visible: bool,
    pub explain_enabled: bool,
    pub regenerate_visible: bool,
}

impl PanelView {
    /// As `create_product_panel_widgets` builds it.
    fn initial() -> Self {
        Self {
            product_text: LOADING.into(),
            issuance: String::new(),
            sps_entries: Vec::new(),
            sps_selection: None,
            sps_visible: false,
            retry_visible: false,
            ai_visible: false,
            ai_text: String::new(),
            model_info_visible: false,
            model_info: String::new(),
            explain_visible: true,
            explain_enabled: false,
            regenerate_visible: false,
        }
    }
}

/// One tab's content state (`ForecastProductPanel` minus the widgets).
pub(crate) struct PanelState {
    pub product_type: String,
    pub cwa_office: Option<String>,
    pub view: PanelView,
    current_text: Option<String>,
    sps_products: Vec<TextProduct>,
    is_explaining: bool,
    load_started: bool,
    fmt: Formatters,
}

impl PanelState {
    pub fn new(product_type: &str, cwa_office: Option<String>, fmt: Formatters) -> Self {
        Self {
            product_type: product_type.to_string(),
            cwa_office,
            view: PanelView::initial(),
            current_text: None,
            sps_products: Vec::new(),
            is_explaining: false,
            load_started: false,
            fmt,
        }
    }

    fn is_sps(&self) -> bool {
        self.product_type == "SPS"
    }

    fn show_sps_chooser(&mut self, visible: bool) {
        if self.is_sps() {
            self.view.sps_visible = visible;
        }
    }

    fn hide_ai_summary_section(&mut self) {
        self.view.ai_visible = false;
        self.hide_model_info();
    }

    fn hide_model_info(&mut self) {
        self.view.model_info.clear();
        self.view.model_info_visible = false;
    }

    /// Plain Language Summary and Regenerate Summary are mutually exclusive.
    fn set_post_explain_buttons(&mut self, has_attempted: bool) {
        self.view.explain_visible = !has_attempted;
        self.view.regenerate_visible = has_attempted;
    }

    /// Load once, on construction or first tab selection. True when the
    /// loader should run.
    pub fn ensure_loaded(&mut self) -> bool {
        if self.load_started {
            return false;
        }
        self.load_started = true;
        self.trigger_load()
    }

    /// Enter the loading state; true when the loader should run.
    pub fn trigger_load(&mut self) -> bool {
        if self.cwa_office.is_none()
            && !matches!(self.product_type.as_str(), "SURF" | "SURF_CONDITIONS")
        {
            self.render_no_cwa_state();
            return false;
        }
        self.view.retry_visible = false;
        self.view.product_text = LOADING.into();
        self.view.issuance.clear();
        self.hide_ai_summary_section();
        self.set_post_explain_buttons(false);
        self.view.explain_enabled = false;
        true
    }

    fn render_no_cwa_state(&mut self) {
        self.current_text = None;
        self.view.product_text = NO_CWA_COPY.into();
        self.view.issuance.clear();
        self.show_sps_chooser(false);
        self.view.retry_visible = false;
        self.hide_ai_summary_section();
        self.view.explain_enabled = false;
    }

    /// A finished load; returns whether the tab has content (the
    /// availability the dialog uses to drop empty tabs).
    pub fn on_load_complete(&mut self, products: Vec<TextProduct>, has_key: bool) -> bool {
        self.view.retry_visible = false;
        if products.is_empty() {
            self.render_empty_state();
            return false;
        }
        if self.is_sps() {
            self.render_sps_products(products, has_key);
        } else {
            self.render_single_product(&products[0], has_key);
        }
        true
    }

    fn render_empty_state(&mut self) {
        self.view.product_text = tabs::empty_copy(&self.product_type, self.cwa_office.as_deref());
        self.view.issuance.clear();
        self.show_sps_chooser(false);
        self.hide_ai_summary_section();
        self.view.explain_enabled = false;
        self.current_text = None;
    }

    fn render_single_product(&mut self, product: &TextProduct, has_key: bool) {
        let text = tabs::display_text(product, self.cwa_office.as_deref());
        self.view.product_text = text.clone();
        self.current_text = Some(text);
        self.view.issuance = (self.fmt.issuance)(product.issuance_time.as_ref());
        self.show_sps_chooser(false);
        self.update_explain_button_state(has_key);
    }

    fn render_sps_products(&mut self, products: Vec<TextProduct>, has_key: bool) {
        self.view.sps_entries = products.iter().map(self.fmt.sps_entry).collect();
        self.view.sps_selection = Some(0);
        let multiple = products.len() > 1;
        self.render_single_product(&products[0], has_key);
        self.show_sps_chooser(multiple);
        self.sps_products = products;
    }

    /// Show the SPS the user picked.
    pub fn on_sps_choice_changed(&mut self, index: usize, has_key: bool) {
        let Some(product) = self.sps_products.get(index).cloned() else {
            return;
        };
        self.view.sps_selection = Some(index);
        self.view.product_text = product.product_text.clone();
        self.current_text = Some(product.product_text);
        self.view.issuance = (self.fmt.issuance)(product.issuance_time.as_ref());
        self.update_explain_button_state(has_key);
        // A summary of the previous statement no longer applies.
        self.hide_ai_summary_section();
        self.set_post_explain_buttons(false);
    }

    /// The fetch failed; the tab stays (reported as available) with Try again.
    pub fn on_load_error(&mut self) {
        let full_name = header_text(&self.product_type);
        self.view.product_text = format!("Failed to fetch {full_name} \u{2014} try again.");
        self.view.issuance.clear();
        self.show_sps_chooser(false);
        self.hide_ai_summary_section();
        self.view.explain_enabled = false;
        self.view.retry_visible = true;
        self.current_text = None;
    }

    /// Plain Language Summary is enabled only with loaded text and a key
    /// for the selected AI provider.
    fn update_explain_button_state(&mut self, has_key: bool) {
        self.view.explain_enabled =
            self.current_text.as_deref().is_some_and(|t| !t.is_empty()) && has_key;
    }

    /// Plain Language Summary (and Regenerate Summary): the text to summarise,
    /// or `None` when there is nothing to do.
    pub fn on_explain(&mut self) -> Option<String> {
        let text = self.current_text.clone().filter(|t| !t.is_empty())?;
        if self.is_explaining {
            return None;
        }
        self.is_explaining = true;
        self.view.ai_visible = true;
        self.hide_model_info();
        self.set_post_explain_buttons(false);
        self.view.explain_enabled = false;
        self.view.ai_text = GENERATING.into();
        Some(text)
    }

    /// Model-selection progress; returns what to announce.
    pub fn on_explain_status(&mut self, message: &str) -> Option<String> {
        self.view.ai_visible = true;
        self.view.ai_text = message.to_string();
        (!message.is_empty()).then(|| message.to_string())
    }

    /// The summary arrived. Returns whether to focus the summary (the button
    /// the user pressed had focus) and what to announce.
    pub fn on_explain_complete(
        &mut self,
        summary: &Summary,
        explain_had_focus: bool,
    ) -> (bool, String) {
        self.is_explaining = false;
        self.view.ai_visible = true;
        self.set_post_explain_buttons(true);
        self.view.ai_text = summary.text.clone();
        self.view.model_info = build_model_info(summary);
        self.view.model_info_visible = true;
        let announcement = if summary.model_used.is_empty() {
            "Plain Language Summary generated.".to_string()
        } else {
            format!(
                "Plain Language Summary generated using {}.",
                summary.model_used
            )
        };
        (explain_had_focus, announcement)
    }

    /// The summary failed; the summary box takes focus. Returns what to
    /// announce.
    pub fn on_explain_error(&mut self, message: &str) -> String {
        self.is_explaining = false;
        self.view.ai_visible = true;
        self.set_post_explain_buttons(true);
        self.view.ai_text = format!(
            "Failed to generate summary: {message}\n\nCheck the selected provider and API key in Settings."
        );
        format!("Summary failed. {message}")
    }
}
