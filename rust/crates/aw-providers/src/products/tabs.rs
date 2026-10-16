//! Which Forecaster Notes and National Products tabs exist, how each one
//! loads, and when an empty tab is dropped. Pure logic from
//! `ui/dialogs/forecast_products_dialog.py`, `national_products_dialog.py`,
//! `forecast_product_panel.py` and `forecast_product_formatting.py`; the
//! dialogs themselves are UI work.

use aw_core::model::{Location, TextProduct};
use chrono::Local;

use super::iem::AfosQuery;
use super::py::splitlines;
use super::service::{ForecastProductService, PiratePayload};
use super::{ProductError, ProductResult};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum LoaderKind {
    /// `service.get(product_type, cwa_office)`.
    Current,
    SurfConditions,
    DailyClimate,
    SpcOutlook,
    SpcMcd,
    SpcWatchesCurrent,
    WpcEro,
    WpcMpd,
}

impl LoaderKind {
    /// Optional point-based IEM tabs, added only when a product is active.
    pub fn is_active_iem(self) -> bool {
        matches!(
            self,
            LoaderKind::SpcOutlook
                | LoaderKind::SpcMcd
                | LoaderKind::SpcWatchesCurrent
                | LoaderKind::WpcEro
                | LoaderKind::WpcMpd
        )
    }
}

/// One Forecaster Notes tab (`TextProductTab`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProductTab {
    pub product_type: &'static str,
    pub label: &'static str,
    pub loader_kind: LoaderKind,
    pub requires_cwa: bool,
}

const fn tab(
    product_type: &'static str,
    label: &'static str,
    loader_kind: LoaderKind,
) -> ProductTab {
    ProductTab {
        product_type,
        label,
        loader_kind,
        requires_cwa: false,
    }
}

const fn office_tab(product_type: &'static str, label: &'static str) -> ProductTab {
    ProductTab {
        product_type,
        label,
        loader_kind: LoaderKind::Current,
        requires_cwa: true,
    }
}

/// `ForecastProductsDialog._TABS`, in notebook order.
pub const FORECASTER_TABS: [ProductTab; 10] = [
    office_tab("AFD", "Area Forecast Discussion"),
    office_tab("HWO", "Hazardous Weather Outlook"),
    office_tab("SPS", "Special Weather Statement"),
    tab("SURF", "Surf/Beach Conditions", LoaderKind::SurfConditions),
    tab("CLI", "Daily Climate Report", LoaderKind::DailyClimate),
    tab(
        "SPC_OUTLOOK",
        "SPC Outlook (Storm Prediction Center)",
        LoaderKind::SpcOutlook,
    ),
    tab(
        "SPC_MCD",
        "SPC MCD (Mesoscale Discussion)",
        LoaderKind::SpcMcd,
    ),
    tab(
        "SPC_WATCHES",
        "SPC Watches (Storm Prediction Center)",
        LoaderKind::SpcWatchesCurrent,
    ),
    tab(
        "WPC_ERO",
        "WPC ERO (Excessive Rainfall Outlook)",
        LoaderKind::WpcEro,
    ),
    tab(
        "WPC_MPD",
        "WPC MPD (Mesoscale Precipitation Discussion)",
        LoaderKind::WpcMpd,
    ),
];

/// `NationalProductsDialog._TABS`: AFOS product id and tab label. Every
/// national tab uses `cwa_office = "IEM"`, location name "National", and
/// only the first autoloads.
pub const NATIONAL_TABS: [(&str, &str); 10] = [
    ("PMDSPD", "WPC Short Range"),
    ("PMDEPD", "WPC Medium Range"),
    ("PMDET4", "WPC Extended"),
    ("QPFPFD", "WPC QPF Discussion"),
    ("PMDMRD", "CPC Outlook"),
    ("TWOAT", "NHC Atlantic Outlook"),
    ("TWOEP", "NHC East Pacific Outlook"),
    ("SWODY1", "SPC Day 1 Outlook"),
    ("SWODY2", "SPC Day 2 Outlook"),
    ("SWODY3", "SPC Day 3 Outlook"),
];

/// Load the latest national AFOS product for a National Products tab.
pub fn load_national_tab(
    service: &ForecastProductService,
    product_id: &str,
) -> Result<TextProduct, ProductError> {
    service.get_iem_afos(product_id, &AfosQuery::default())
}

/// A tab to create when the dialog opens.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TabPlan {
    pub tab: ProductTab,
    pub autoload: bool,
    /// Office passed to the panel; `None` makes the panel show
    /// [`NO_CWA_COPY`] instead of loading (except surf tabs).
    pub panel_cwa: Option<String>,
}

/// Tabs for a location: the ones created immediately, and the point-based
/// IEM tabs to check in the background (added only if active).
pub fn forecaster_tabs(location: &Location) -> (Vec<TabPlan>, Vec<ProductTab>) {
    let has_cwa = location
        .cwa_office
        .as_deref()
        .is_some_and(|c| !c.is_empty());
    let mut initial: Vec<TabPlan> = Vec::new();
    let mut pending = Vec::new();
    for tab in FORECASTER_TABS {
        if tab.requires_cwa && !has_cwa {
            continue;
        }
        if tab.loader_kind.is_active_iem() {
            pending.push(tab);
            continue;
        }
        initial.push(TabPlan {
            tab,
            autoload: should_autoload_tab(&tab, initial.is_empty()),
            panel_cwa: panel_cwa(&tab, location),
        });
    }
    (initial, pending)
}

/// The first tab and the daily climate report load when the dialog opens;
/// the rest load when selected.
pub fn should_autoload_tab(tab: &ProductTab, is_first_tab: bool) -> bool {
    is_first_tab || tab.loader_kind == LoaderKind::DailyClimate
}

/// Office shown by a tab's panel: the location's office for office, surf and
/// climate tabs, `"IEM"` for point-based IEM tabs.
pub fn panel_cwa(tab: &ProductTab, location: &Location) -> Option<String> {
    if tab.requires_cwa
        || matches!(
            tab.loader_kind,
            LoaderKind::DailyClimate | LoaderKind::SurfConditions
        )
    {
        location.cwa_office.clone()
    } else {
        Some("IEM".into())
    }
}

/// Run a tab's loader (`_make_loader`). Point-based IEM tabs yield
/// `One(None)` when nothing is active or IEM fails.
pub fn load_tab(
    service: &ForecastProductService,
    location: &Location,
    tab: &ProductTab,
    pirate_payload: Option<PiratePayload>,
) -> Result<ProductResult, ProductError> {
    let cwa_office = location.cwa_office.as_deref();
    if tab.requires_cwa && cwa_office.is_none() {
        return Ok(ProductResult::One(None));
    }
    let (lat, lon) = (location.latitude, location.longitude);
    let active = |result: Result<TextProduct, ProductError>| {
        Ok(ProductResult::One(match result {
            Ok(product) => active_iem_product_or_none(product),
            Err(err) => {
                tracing::info!("Optional active IEM tab lookup failed: {err}");
                None
            }
        }))
    };
    match tab.loader_kind {
        LoaderKind::Current => service.get(tab.product_type, cwa_office.unwrap_or("None")),
        LoaderKind::SurfConditions => Ok(ProductResult::One(
            service.get_surf_conditions_for_location(location, pirate_payload),
        )),
        LoaderKind::DailyClimate => service
            .get_daily_climate_report_for_location(location)
            .map(ProductResult::One),
        LoaderKind::SpcOutlook => {
            active(service.get_iem_spc_outlook(lat, lon, 1, true, None, Some(3)))
        }
        LoaderKind::SpcMcd => active(service.get_iem_spc_mcds(lat, lon, true, None, None, Some(3))),
        LoaderKind::SpcWatchesCurrent => {
            active(service.get_iem_spc_watches(lat, lon, None, Some(3)))
        }
        LoaderKind::WpcEro => active(service.get_iem_wpc_outlook(lat, lon, 1, None, 1, Some(3))),
        LoaderKind::WpcMpd => active(service.get_iem_wpc_mpds(lat, lon, true, None, None, Some(3))),
    }
}

/// Check the pending point-based tabs concurrently; returns the active ones
/// in tab order with the product to show.
pub fn resolve_active_iem_tabs(
    service: &ForecastProductService,
    location: &Location,
    pending: &[ProductTab],
) -> Vec<(ProductTab, TextProduct)> {
    std::thread::scope(|scope| {
        let handles: Vec<_> = pending
            .iter()
            .map(|tab| scope.spawn(move || (*tab, load_tab(service, location, tab, None))))
            .collect();
        handles
            .into_iter()
            .filter_map(|handle| match handle.join().ok()? {
                (tab, Ok(result)) => result.first().cloned().map(|product| (tab, product)),
                (_, Err(err)) => {
                    tracing::info!("Optional active IEM tab check failed: {err}");
                    None
                }
            })
            .collect()
    })
}

const INACTIVE_IEM_SUMMARY_PREFIXES: [&str; 3] =
    ["No active ", "No matching ", "No structured data returned."];

/// `None` when an IEM summary reports nothing active or matching.
pub fn active_iem_product_or_none(product: TextProduct) -> Option<TextProduct> {
    let inactive = splitlines(&product.product_text)
        .into_iter()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with("Generated:"))
        .any(|line| {
            INACTIVE_IEM_SUMMARY_PREFIXES
                .iter()
                .any(|prefix| line.starts_with(prefix))
        });
    (!inactive).then_some(product)
}

/// Whether a tab stays after its load finished (`_on_panel_availability_resolved`).
/// `has_product` is false only for a successful fetch with nothing in it;
/// fetch errors count as available so the retry button stays reachable.
/// AFD always stays, and the last remaining tab is never removed.
pub fn keeps_tab(product_type: &str, has_product: bool, tab_count: usize) -> bool {
    has_product || product_type == "AFD" || tab_count <= 1
}

/// Product the Advanced Lookup button prefills for a tab.
pub fn advanced_lookup_product_type(product_type: &str) -> &str {
    if product_type == "SURF" {
        "SRF"
    } else {
        product_type
    }
}

/// Shown instead of loading when a tab's panel has no office.
pub const NO_CWA_COPY: &str = "NWS text products will populate after the next weather refresh.";

/// `PRODUCT_FULL_NAMES` (used in "Failed to fetch {name} — try again.").
pub fn product_full_name(product_type: &str) -> Option<&'static str> {
    Some(match product_type {
        "AFD" => "Area Forecast Discussion",
        "HWO" => "Hazardous Weather Outlook",
        "SPS" => "Special Weather Statement",
        "SRF" => "Official NWS Surf Zone Forecast",
        "SURF" | "SURF_CONDITIONS" => "Surf/Beach Conditions",
        "LSR" => "Local Storm Report",
        "PNS" => "Public Information Statement",
        "CLI" => "Daily Climate Report",
        "SPC_OUTLOOK" | "SWODY1" => "SPC Day 1 Convective Outlook (Storm Prediction Center)",
        "SPC_MCD" => "SPC Mesoscale Discussions (Storm Prediction Center)",
        "SPC_WATCHES" => "SPC Watches (Storm Prediction Center)",
        "WPC_ERO" => "WPC Day 1 Excessive Rainfall Outlook (Weather Prediction Center)",
        "WPC_MPD" => "WPC Mesoscale Precipitation Discussions (Weather Prediction Center)",
        "PMDSPD" => "WPC Short Range Discussion (Weather Prediction Center)",
        "PMDEPD" => "WPC Medium Range Discussion (Weather Prediction Center)",
        "PMDET4" => "WPC Extended Discussion (Weather Prediction Center)",
        "QPFPFD" => "WPC Quantitative Precipitation Discussion (Weather Prediction Center)",
        "PMDMRD" => "CPC 6-10 and 8-14 Day Outlook (Climate Prediction Center)",
        "TWOAT" => "NHC Atlantic Tropical Weather Outlook (National Hurricane Center)",
        "TWOEP" => "NHC East Pacific Tropical Weather Outlook (National Hurricane Center)",
        "SWODY2" => "SPC Day 2 Convective Outlook (Storm Prediction Center)",
        "SWODY3" => "SPC Day 3 Convective Outlook (Storm Prediction Center)",
        _ => return None,
    })
}

/// Empty-state text for a tab (`EMPTY_COPY` formatted with the panel office;
/// Python formats a missing office as "None").
pub fn empty_copy(product_type: &str, cwa_office: Option<&str>) -> String {
    let office = cwa_office.unwrap_or("None");
    match product_type {
        "AFD" => format!("Area Forecast Discussion not currently available for {office}."),
        "HWO" => format!("Hazardous Weather Outlook not currently available for {office}."),
        "SPS" => format!("No recent Special Weather Statements for {office}."),
        "SRF" => format!(
            "Surf Zone Forecast issued by NWS {office} for regional beaches is not currently \
             available."
        ),
        "SURF" => "No official NWS Surf Zone Forecast or derived surf/beach conditions are \
                   currently available for this location."
            .into(),
        "SURF_CONDITIONS" => {
            "No derived surf/beach conditions are currently available for this location.".into()
        }
        "LSR" => format!("No recent Local Storm Reports for {office}."),
        "PNS" => format!("No recent Public Information Statements for {office}."),
        "CLI" => format!("Daily Climate Report not currently available for {office}."),
        "SPC_OUTLOOK" => "No matching SPC (Storm Prediction Center) Day 1 Convective Outlook for \
                          this location."
            .into(),
        "SPC_MCD" => {
            "No matching SPC (Storm Prediction Center) Mesoscale Discussions for this location."
                .into()
        }
        "SPC_WATCHES" => {
            "No matching SPC (Storm Prediction Center) Watches for this location.".into()
        }
        "WPC_ERO" => "No matching WPC (Weather Prediction Center) Excessive Rainfall Outlook for \
                      this location."
            .into(),
        "WPC_MPD" => "No matching WPC (Weather Prediction Center) Mesoscale Precipitation \
                      Discussions for this location."
            .into(),
        "PMDSPD" => "WPC Short Range Discussion is not currently available.".into(),
        "PMDEPD" => "WPC Medium Range Discussion is not currently available.".into(),
        "PMDET4" => "WPC Extended Discussion is not currently available.".into(),
        "QPFPFD" => "WPC Quantitative Precipitation Discussion is not currently available.".into(),
        "PMDMRD" => "CPC 6-10 and 8-14 Day Outlook is not currently available.".into(),
        "TWOAT" => "NHC Atlantic Tropical Weather Outlook is not currently available.".into(),
        "TWOEP" => "NHC East Pacific Tropical Weather Outlook is not currently available.".into(),
        "SWODY1" => "SPC Day 1 Convective Outlook is not currently available.".into(),
        "SWODY2" => "SPC Day 2 Convective Outlook is not currently available.".into(),
        "SWODY3" => "SPC Day 3 Convective Outlook is not currently available.".into(),
        other => format!("{other} not currently available for {office}."),
    }
}

/// Official-vs-derived context line shown above surf products.
pub fn regional_product_intro(product_type: &str, cwa_office: Option<&str>) -> String {
    match product_type {
        "SRF" => {
            let office = cwa_office.unwrap_or_default().trim().to_uppercase();
            let office = if office.is_empty() {
                "the selected office".to_string()
            } else {
                office
            };
            format!("Surf Zone Forecast issued by NWS {office} for regional beaches.")
        }
        "SURF_CONDITIONS" => "Marine/surf conditions from a supported source; not an official \
                              NWS Surf Zone Forecast."
            .into(),
        _ => String::new(),
    }
}

/// Text a panel shows for a single product: the intro line is prepended
/// unless the product text already contains it.
pub fn display_text(product: &TextProduct, panel_cwa: Option<&str>) -> String {
    let intro = regional_product_intro(&product.product_type, panel_cwa);
    if !intro.is_empty() && !product.product_text.contains(&intro) {
        format!("{intro}\n\n{}", product.product_text)
    } else {
        product.product_text.clone()
    }
}

/// SPS chooser entry: "Issued 2026-04-16 10:32 — headline" in local time.
pub fn format_sps_choice_entry(product: &TextProduct) -> String {
    let when = product.issuance_time.map_or("unknown".to_string(), |t| {
        t.with_timezone(&Local).format("%Y-%m-%d %H:%M").to_string()
    });
    let headline = product
        .headline
        .clone()
        .filter(|h| !h.is_empty())
        .or_else(|| {
            splitlines(&product.product_text)
                .into_iter()
                .map(str::trim)
                .find(|line| !line.is_empty())
                .map(str::to_string)
        })
        .unwrap_or_else(|| "Special Weather Statement".into());
    format!("Issued {when} \u{2014} {headline}")
}
