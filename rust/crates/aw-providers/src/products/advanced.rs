//! Advanced Text Product Lookup: presets, office and date rules, validation,
//! the lookup executor and result formatting. Port of the non-widget logic in
//! `ui/dialogs/advanced_text_product_dialog.py`; the dialog maps its controls
//! onto [`LookupForm`] and shows what [`lookup`] returns.

use aw_core::model::{Location, TextProduct, Timestamp};
use chrono::{DateTime, Datelike, Duration, NaiveDate, NaiveTime, SubsecRound, Utc};

use super::iem::{AfosQuery, Order};
use super::py::{self, fromisoformat, isoformat};
use super::service::ForecastProductService;
use super::ProductError;

pub const NWS_PRODUCT_TYPES: [&str; 9] = [
    "AFD", "HWO", "SPS", "SRF", "CLI", "CF6", "RER", "LSR", "PNS",
];

pub const SOURCE_PREFER_NWS: &str = "Prefer NWS when available";
pub const SOURCE_IEM_ONLY: &str = "IEM AFOS only";
pub const SOURCE_NWS_ONLY: &str = "NWS history only";
/// Lookup source choices, in order.
pub const SOURCE_CHOICES: [&str; 3] = [SOURCE_PREFER_NWS, SOURCE_IEM_ONLY, SOURCE_NWS_ONLY];

pub const OFFICE_SELECTED: &str = "Selected location office";
pub const OFFICE_NONE: &str = "No office or national product";
pub const OFFICE_CUSTOM: &str = "Custom office below";

pub const DATE_PRESETS: [&str; 7] = [
    "Latest or current",
    "Past 24 hours",
    "Past 7 days",
    "Past 30 days",
    "Past 90 days",
    "Past year",
    "Choose start and end dates",
];

pub const ARCHIVE_START_YEAR: i32 = 1983;

pub const MONTH_CHOICES: [&str; 12] = [
    "01 - January",
    "02 - February",
    "03 - March",
    "04 - April",
    "05 - May",
    "06 - June",
    "07 - July",
    "08 - August",
    "09 - September",
    "10 - October",
    "11 - November",
    "12 - December",
];

pub const ORDER_CHOICES: [&str; 2] = ["Newest first", "Oldest first"];

/// One user-facing lookup choice mapped to an API-safe product token.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProductPreset {
    pub category: &'static str,
    pub label: &'static str,
    pub value: &'static str,
    pub uses_local_office: bool,
    pub iem_only: bool,
}

const fn preset(category: &'static str, label: &'static str, value: &'static str) -> ProductPreset {
    ProductPreset {
        category,
        label,
        value,
        uses_local_office: false,
        iem_only: false,
    }
}

const fn local(label: &'static str, value: &'static str) -> ProductPreset {
    ProductPreset {
        uses_local_office: true,
        ..preset("Local office", label, value)
    }
}

const fn iem(category: &'static str, label: &'static str, value: &'static str) -> ProductPreset {
    ProductPreset {
        iem_only: true,
        ..preset(category, label, value)
    }
}

/// `_PRODUCT_PRESET_ITEMS`, in menu order.
pub const PRODUCT_PRESETS: [ProductPreset; 34] = [
    preset("Custom", "Custom AFOS product ID", ""),
    local("Local Area Forecast Discussion", "AFD"),
    local("Local Hazardous Weather Outlook", "HWO"),
    local("Local Special Weather Statement", "SPS"),
    local(
        "Official NWS Surf Zone Forecast for regional beaches",
        "SRF",
    ),
    local("Local Storm Report", "LSR"),
    local("Daily Climate Report", "CLI"),
    local("Monthly Climate Report", "CF6"),
    local("Record Event Report", "RER"),
    local("Public Information Statement", "PNS"),
    iem("Point-based SPC", "SPC Day 1 Outlook", "SPC Day 1 Outlook"),
    iem("Point-based SPC", "SPC Day 2 Outlook", "SPC Day 2 Outlook"),
    iem("Point-based SPC", "SPC Day 3 Outlook", "SPC Day 3 Outlook"),
    iem("Point-based SPC", "SPC Day 4 Outlook", "SPC Day 4 Outlook"),
    iem("Point-based SPC", "SPC Day 5 Outlook", "SPC Day 5 Outlook"),
    iem("Point-based SPC", "SPC Day 6 Outlook", "SPC Day 6 Outlook"),
    iem("Point-based SPC", "SPC Day 7 Outlook", "SPC Day 7 Outlook"),
    iem("Point-based SPC", "SPC Day 8 Outlook", "SPC Day 8 Outlook"),
    iem("Point-based SPC", "SPC MCD near location", "SPC MCD"),
    iem(
        "Point-based SPC",
        "SPC Watches near location",
        "SPC Watches",
    ),
    iem(
        "Point-based WPC",
        "WPC Day 1 ERO",
        "WPC Day 1 Excessive Rainfall Outlook",
    ),
    iem(
        "Point-based WPC",
        "WPC Day 2 ERO",
        "WPC Day 2 Excessive Rainfall Outlook",
    ),
    iem(
        "Point-based WPC",
        "WPC Day 3 ERO",
        "WPC Day 3 Excessive Rainfall Outlook",
    ),
    iem("Point-based WPC", "WPC MPD near location", "WPC MPD"),
    iem("National AFOS", "WPC Short Range Discussion", "PMDSPD"),
    iem("National AFOS", "WPC Medium Range Discussion", "PMDEPD"),
    iem("National AFOS", "WPC Extended Discussion", "PMDET4"),
    iem("National AFOS", "WPC QPF Discussion", "QPFPFD"),
    iem("National AFOS", "CPC 6-10 and 8-14 Day Outlook", "PMDMRD"),
    iem(
        "National AFOS",
        "NHC Atlantic Tropical Weather Outlook",
        "TWOAT",
    ),
    iem(
        "National AFOS",
        "NHC East Pacific Tropical Weather Outlook",
        "TWOEP",
    ),
    iem("National AFOS", "SPC Day 1 AFOS Outlook", "SWODY1"),
    iem("National AFOS", "SPC Day 2 AFOS Outlook", "SWODY2"),
    iem("National AFOS", "SPC Day 3 AFOS Outlook", "SWODY3"),
];

/// Older labels still accepted by `_PRODUCT_PRESETS` (no source/office change).
const PRESET_ALIASES: [(&str, &str); 4] = [
    ("SPC MCD (Mesoscale Discussions) near location", "SPC MCD"),
    (
        "SPC Watches (Storm Prediction Center) near location",
        "SPC Watches",
    ),
    (
        "WPC MPD (Mesoscale Precipitation Discussion) near location",
        "WPC MPD",
    ),
    (
        "CPC 6-10 and 8-14 Day Outlook (Climate Prediction Center)",
        "PMDMRD",
    ),
];

/// Product groups in first-seen order.
pub fn product_categories() -> Vec<&'static str> {
    let mut categories: Vec<&'static str> = Vec::new();
    for item in &PRODUCT_PRESETS {
        if !categories.contains(&item.category) {
            categories.push(item.category);
        }
    }
    categories
}

pub fn preset_labels_for_category(category: &str) -> Vec<&'static str> {
    PRODUCT_PRESETS
        .iter()
        .filter(|item| item.category == category)
        .map(|item| item.label)
        .collect()
}

pub fn preset_by_label(label: &str) -> Option<&'static ProductPreset> {
    PRODUCT_PRESETS.iter().find(|item| item.label == label)
}

/// Product token for a preset label (`_PRODUCT_PRESETS.get`).
pub fn preset_value(label: &str) -> Option<&'static str> {
    preset_by_label(label).map(|item| item.value).or_else(|| {
        PRESET_ALIASES
            .iter()
            .find(|(alias, _)| *alias == label)
            .map(|(_, value)| *value)
    })
}

/// Form changes when a product preset is chosen (`_apply_product_preset`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PresetChange {
    pub product: &'static str,
    /// New index into [`SOURCE_CHOICES`].
    pub source_index: Option<usize>,
    /// Office choice to select: first entry equal to or starting with this.
    pub office_choice: Option<&'static str>,
}

/// `None` leaves the form alone (the custom entry has no product).
pub fn apply_product_preset(label: &str) -> Option<PresetChange> {
    let product = preset_value(label).filter(|v| !v.is_empty())?;
    let mut change = PresetChange {
        product,
        source_index: None,
        office_choice: None,
    };
    if let Some(item) = preset_by_label(label) {
        if item.uses_local_office {
            change.source_index = Some(0);
            change.office_choice = Some(OFFICE_SELECTED);
        }
        if item.iem_only {
            change.source_index = Some(1);
            change.office_choice = Some(OFFICE_NONE);
        }
    }
    Some(change)
}

/// Preset applied when a product group is chosen (`_on_product_category`):
/// the group's first product, or the custom entry.
pub fn category_default_preset(category: &str) -> &'static str {
    let category = if category.is_empty() {
        "Custom"
    } else {
        category
    };
    preset_labels_for_category(category)
        .first()
        .copied()
        .unwrap_or("Custom AFOS product ID")
}

/// Office choices; the selected location's office comes first when known.
pub fn office_choices(location: &Location) -> Vec<String> {
    let mut choices = vec![OFFICE_NONE.to_string(), OFFICE_CUSTOM.to_string()];
    if let Some(cwa) = location.cwa_office.as_deref().filter(|c| !c.is_empty()) {
        choices.insert(0, format!("{OFFICE_SELECTED} ({})", cwa.to_uppercase()));
    }
    choices
}

/// Index of the first choice equal to or starting with `prefix_or_label`.
pub fn find_choice(choices: &[String], prefix_or_label: &str) -> Option<usize> {
    choices
        .iter()
        .position(|label| label == prefix_or_label || label.starts_with(prefix_or_label))
}

/// Year choices: blank, then this year back to 1983.
pub fn year_choices(now: DateTime<Utc>) -> Vec<String> {
    std::iter::once(String::new())
        .chain(
            (ARCHIVE_START_YEAR..=now.year())
                .rev()
                .map(|y| y.to_string()),
        )
        .collect()
}

/// Month choices: blank then [`MONTH_CHOICES`].
pub fn month_choices() -> Vec<String> {
    std::iter::once(String::new())
        .chain(MONTH_CHOICES.iter().map(|m| m.to_string()))
        .collect()
}

/// Day choices: blank then 01-31.
pub fn day_choices() -> Vec<String> {
    std::iter::once(String::new())
        .chain((1..=31).map(|d| format!("{d:02}")))
        .collect()
}

/// Start and end for a date preset (`_date_range_for_preset`).
pub fn date_range_for_preset(
    preset: &str,
    now: DateTime<Utc>,
) -> (Option<Timestamp>, Option<Timestamp>) {
    let now = now.trunc_subsecs(0).fixed_offset();
    let days = match preset {
        "Choose start and end dates" | "Past 24 hours" => 1,
        "Past 7 days" => 7,
        "Past 30 days" => 30,
        "Past 90 days" => 90,
        "Past year" => 365,
        _ => return (None, None),
    };
    (Some(now - Duration::days(days)), Some(now))
}

/// Resolved UTC field text, e.g. `2026-07-04T12:00:00Z`.
pub fn format_form_datetime(value: &Timestamp) -> String {
    py::utc_z(value)
}

/// Selections for the year, month and day choices showing `value`
/// (`_set_date_choices`); `None` entries leave that choice unchanged.
pub fn date_choice_selections(value: Option<&Timestamp>, years: &[String]) -> [Option<usize>; 3] {
    let Some(value) = value else {
        return [Some(0); 3];
    };
    let year = value.year().to_string();
    let month = format!("{:02}", value.month());
    let day = format!("{:02}", value.day());
    [
        years.iter().position(|y| *y == year),
        month_choices()
            .iter()
            .position(|m| *m == month || m.starts_with(&month)),
        day_choices().iter().position(|d| *d == day),
    ]
}

/// `_parse_limit`: 1..=25, anything unparsable is 1.
pub fn parse_limit(value: &str) -> i64 {
    let text = value.trim();
    let digits = text.strip_prefix(['+', '-']).unwrap_or(text);
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return 1;
    }
    if text.starts_with('-') {
        return 1;
    }
    digits.parse::<i64>().unwrap_or(i64::MAX).clamp(1, 25)
}

/// `_date_from_choice_parts`: all blank → `None`; partly blank is an error.
pub fn date_from_choice_parts(
    year: &str,
    month: &str,
    day: &str,
) -> Result<Option<Timestamp>, String> {
    if year.is_empty() && month.is_empty() && day.is_empty() {
        return Ok(None);
    }
    if year.is_empty() || month.is_empty() || day.is_empty() {
        return Err("Choose year, month, and day for custom archive dates.".into());
    }
    let invalid = || "Choose a valid calendar date.".to_string();
    let year: i32 = year.trim().parse().map_err(|_| invalid())?;
    let month: u32 = month
        .split(' ')
        .next()
        .unwrap_or_default()
        .parse()
        .map_err(|_| invalid())?;
    let day: u32 = day.trim().parse().map_err(|_| invalid())?;
    let date = NaiveDate::from_ymd_opt(year, month, day).ok_or_else(invalid)?;
    Ok(Some(date.and_time(NaiveTime::MIN).and_utc().fixed_offset()))
}

/// `_parse_optional_datetime`: `YYYY-MM-DD` is midnight UTC; other ISO
/// timestamps keep their offset, naive ones are UTC.
pub fn parse_optional_datetime(value: &str) -> Result<Option<Timestamp>, String> {
    let text = value.trim();
    if text.is_empty() {
        return Ok(None);
    }
    let error = || "Enter dates as YYYY-MM-DD or ISO timestamps.".to_string();
    let bytes = text.as_bytes();
    let is_plain_date = bytes.len() == 10
        && bytes[4] == b'-'
        && bytes[7] == b'-'
        && bytes
            .iter()
            .enumerate()
            .all(|(i, b)| i == 4 || i == 7 || b.is_ascii_digit());
    let (naive, offset) = if is_plain_date {
        let (naive, _) = fromisoformat(text).ok_or_else(error)?;
        (naive.date().and_time(NaiveTime::MIN), Some(py::utc()))
    } else {
        let normalized = match text.strip_suffix('Z') {
            Some(rest) => format!("{rest}+00:00"),
            None => text.to_string(),
        };
        fromisoformat(&normalized).ok_or_else(error)?
    };
    let offset = offset.unwrap_or_else(py::utc);
    Ok(Some(
        naive
            .and_local_timezone(offset)
            .single()
            .ok_or_else(error)?,
    ))
}

/// `(?:{center}\s*)?DAY\s*([1-8])\s*(?:{middle})?OUTLOOK`, matched in full,
/// ignoring case. `middle` words are each followed by optional whitespace.
fn outlook_day(product_id: &str, center: &str, middle: &[&str]) -> Option<i64> {
    let upper = product_id.to_uppercase();
    let mut rest = upper.as_str();
    if let Some(after) = rest.strip_prefix(center) {
        rest = after.trim_start();
    }
    rest = rest.strip_prefix("DAY")?.trim_start();
    let day = rest.chars().next().filter(|c| ('1'..='8').contains(c))?;
    rest = rest[1..].trim_start();
    let mut optional = rest;
    let mut matched = true;
    for word in middle {
        match optional.strip_prefix(word) {
            Some(after) => optional = after.trim_start(),
            None => {
                matched = false;
                break;
            }
        }
    }
    if matched {
        rest = optional;
    }
    (rest == "OUTLOOK").then(|| i64::from(day.to_digit(10).unwrap_or(1)))
}

/// Day number for "SPC Day N (Convective) Outlook" style product ids.
pub fn spc_outlook_day(product_id: &str) -> Option<i64> {
    outlook_day(product_id, "SPC", &["CONVECTIVE"])
}

/// Day number for "WPC Day N (Excessive Rainfall) Outlook" style product ids.
pub fn wpc_outlook_day(product_id: &str) -> Option<i64> {
    outlook_day(product_id, "WPC", &["EXCESSIVE", "RAINFALL"])
}

fn is_nws_type(product_id: &str) -> bool {
    NWS_PRODUCT_TYPES.contains(&product_id)
}

/// AFOS PIL: local products get the office appended (`AFD` + `RAH`).
pub fn iem_pil(product_id: &str, office: &str) -> String {
    if is_nws_type(product_id) && !office.is_empty() {
        format!("{product_id}{office}")
    } else {
        product_id.to_string()
    }
}

fn upper_alnum(s: &str, lens: std::ops::RangeInclusive<usize>) -> bool {
    lens.contains(&s.len())
        && s.bytes()
            .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit())
}

/// `_validate_iem_afos_lookup`: the message to show, or `None` when valid.
pub fn validate_iem_afos_lookup(
    product_id: &str,
    pil: &str,
    office: &str,
    aviation_afd: bool,
    center: &str,
    wmo_id: &str,
) -> Option<&'static str> {
    if is_nws_type(product_id) && !office.is_empty() && !upper_alnum(office, 3..=3) {
        return Some("Choose a valid 3-letter local NWS office, such as RAH.");
    }
    if !upper_alnum(pil, 3..=6) {
        return Some("Choose a preset or enter a 3-to-6 character AFOS product ID.");
    }
    if aviation_afd && !pil.starts_with("AFD") {
        return Some(
            "Aviation section lookup is only valid for Area Forecast Discussion products.",
        );
    }
    if !center.is_empty() && !upper_alnum(center, 4..=4) {
        return Some("Issuing center must be a 4-character ID, such as KDMX.");
    }
    let wmo = wmo_id.as_bytes();
    let wmo_ok = wmo.len() == 6
        && wmo[..4].iter().all(u8::is_ascii_uppercase)
        && wmo[4..].iter().all(u8::is_ascii_digit);
    if !wmo_id.is_empty() && !wmo_ok {
        return Some("WMO header must be 6 characters like FXUS63.");
    }
    None
}

/// Lookup result text (`_format_products`).
pub fn format_products(source: &str, products: &[TextProduct]) -> String {
    if products.is_empty() {
        return format!("Source: {source}\n\nNo product found.");
    }
    let mut chunks = vec![format!("Source: {source}")];
    for product in products {
        let issued = product
            .issuance_time
            .as_ref()
            .map_or("unknown".to_string(), isoformat);
        let regional_note = if product.product_type == "SRF" {
            format!(
                "Surf Zone Forecast issued by NWS {} for regional beaches.",
                product.cwa_office
            )
        } else {
            String::new()
        };
        let parts = [
            String::new(),
            format!("Product: {}", product.product_type),
            format!("Issued: {issued}"),
            product
                .headline
                .as_deref()
                .filter(|h| !h.is_empty())
                .map(|h| format!("Headline: {h}"))
                .unwrap_or_default(),
            regional_note,
            product.product_text.clone(),
        ];
        let kept: Vec<String> = parts.into_iter().filter(|p| !p.is_empty()).collect();
        chunks.push(kept.join("\n"));
    }
    chunks.join("\n\n")
}

/// Values of the dialog controls at the moment Lookup is pressed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LookupForm {
    /// Custom AFOS product ID field (presets write their token here).
    pub product: String,
    /// Selected office choice label.
    pub office_choice: String,
    /// Custom local office field.
    pub custom_office: String,
    /// Maximum products spin control value.
    pub limit: String,
    /// Selected lookup source label.
    pub source: String,
    /// Selected result order label.
    pub order: String,
    pub aviation_afd: bool,
    pub center: String,
    pub wmo_id: String,
    /// Start year, month and day choice labels.
    pub start_parts: [String; 3],
    pub end_parts: [String; 3],
    /// Resolved start / end text fields.
    pub start_text: String,
    pub end_text: String,
}

impl LookupForm {
    /// The dialog's initial control values.
    pub fn new(location: &Location, initial_product_type: &str) -> Self {
        Self {
            product: initial_product_type.to_string(),
            office_choice: office_choices(location).remove(0),
            custom_office: location.cwa_office.clone().unwrap_or_default(),
            limit: "1".into(),
            source: SOURCE_PREFER_NWS.into(),
            order: ORDER_CHOICES[0].into(),
            aviation_afd: false,
            center: String::new(),
            wmo_id: String::new(),
            start_parts: Default::default(),
            end_parts: Default::default(),
            start_text: String::new(),
            end_text: String::new(),
        }
    }

    /// Office the lookup targets (`_selected_office`).
    pub fn selected_office(&self, location: &Location) -> String {
        if self.office_choice.starts_with(OFFICE_SELECTED) {
            location
                .cwa_office
                .as_deref()
                .unwrap_or_default()
                .trim()
                .to_uppercase()
        } else if self.office_choice == OFFICE_CUSTOM {
            self.custom_office.trim().to_uppercase()
        } else {
            String::new()
        }
    }

    fn selected_datetime(&self, start: bool) -> Result<Option<Timestamp>, String> {
        let (parts, text) = if start {
            (&self.start_parts, &self.start_text)
        } else {
            (&self.end_parts, &self.end_text)
        };
        match date_from_choice_parts(&parts[0], &parts[1], &parts[2])? {
            Some(chosen) => Ok(Some(chosen)),
            None => parse_optional_datetime(text),
        }
    }
}

/// Run a lookup and return the text for the results box. Service failures
/// read "Lookup failed: ..." as in Python.
pub fn lookup(service: &ForecastProductService, location: &Location, form: &LookupForm) -> String {
    run_lookup(service, location, form).unwrap_or_else(|err| format!("Lookup failed: {err}"))
}

fn run_lookup(
    service: &ForecastProductService,
    location: &Location,
    form: &LookupForm,
) -> Result<String, ProductError> {
    let product_id = form.product.trim().to_uppercase();
    let office = form.selected_office(location);
    let limit = parse_limit(&form.limit);
    let source = if form.source.is_empty() {
        SOURCE_PREFER_NWS
    } else {
        form.source.as_str()
    };
    let order = if form.order == "Oldest first" {
        Order::Asc
    } else {
        Order::Desc
    };
    let center = form.center.trim().to_uppercase();
    let wmo_id = form.wmo_id.trim().to_uppercase();
    let (start, end) = match (form.selected_datetime(true), form.selected_datetime(false)) {
        (Err(message), _) | (Ok(_), Err(message)) => return Ok(message),
        (Ok(start), Ok(end)) => (start, end),
    };
    if product_id.is_empty() {
        return Ok("Choose a product or enter a custom AFOS product ID.".into());
    }
    let (lat, lon) = (location.latitude, location.longitude);
    let iem = |product: TextProduct| Ok(format_products("IEM", &[product]));

    if let Some(day) = spc_outlook_day(&product_id) {
        return iem(service.get_iem_spc_outlook(
            lat,
            lon,
            day,
            start.is_none(),
            start.as_ref(),
            Some(5),
        )?);
    }
    if ["SPC MCD", "MCD", "SPC MESOSCALE DISCUSSION"].contains(&product_id.as_str()) {
        return iem(service.get_iem_spc_mcds(
            lat,
            lon,
            false,
            start.as_ref(),
            end.as_ref(),
            Some(limit),
        )?);
    }
    if ["SPC WATCH", "SPC WATCHES", "WATCHES"].contains(&product_id.as_str()) {
        return iem(service.get_iem_spc_watches(lat, lon, start.as_ref(), Some(5))?);
    }
    if let Some(day) = wpc_outlook_day(&product_id) {
        return iem(service.get_iem_wpc_outlook(lat, lon, day, start.as_ref(), limit, Some(5))?);
    }
    if ["WPC MPD", "MPD", "WPC MESOSCALE PRECIPITATION DISCUSSION"].contains(&product_id.as_str()) {
        return iem(service.get_iem_wpc_mpds(
            lat,
            lon,
            false,
            start.as_ref(),
            end.as_ref(),
            Some(limit),
        )?);
    }

    if source != SOURCE_IEM_ONLY && is_nws_type(&product_id) && !office.is_empty() {
        let products =
            service.get_history(&product_id, &office, limit, start.as_ref(), end.as_ref())?;
        if !products.is_empty() {
            return Ok(format_products("NWS", &products));
        }
        if source == SOURCE_NWS_ONLY {
            return Ok(format!("No NWS {product_id} history found for {office}."));
        }
    }

    let pil = iem_pil(&product_id, &office);
    if let Some(message) = validate_iem_afos_lookup(
        &product_id,
        &pil,
        &office,
        form.aviation_afd,
        &center,
        &wmo_id,
    ) {
        return Ok(message.to_string());
    }
    let query = AfosQuery {
        limit: if form.aviation_afd { 1 } else { limit },
        start,
        end,
        order,
        center: (!center.is_empty()).then_some(center),
        wmo_id: (!wmo_id.is_empty()).then_some(wmo_id),
        matches: None,
        aviation_afd: form.aviation_afd,
    };
    iem(service.get_iem_afos(&pil, &query)?)
}
