//! Forecaster Notes and the dialogs it opens.
//!
//! | Python (`ui/dialogs/`) | Rust |
//! |---|---|
//! | `forecast_products_dialog.py` | this module |
//! | `forecast_product_panel.py`, `forecast_product_widgets.py` | [`panel`] |
//! | panel state machine, `forecast_product_formatting.py` (`format_issuance`) | [`state`] |
//! | `forecast_product_ai.py` | [`ai_summary`] |
//! | `national_products_dialog.py` | [`national`] |
//! | `advanced_text_product_dialog.py` | [`advanced`] |
//!
//! Tab switches deliberately do not move focus: the tab strip stays the
//! active focus level until the user tabs into the content.

mod advanced;
mod ai_summary;
mod national;
mod panel;
mod state;

#[cfg(test)]
mod golden_tests;

use std::any::Any;
use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::rc::Rc;
use std::sync::Arc;

use aw_core::model::{Location, TextProduct};
use aw_providers::products::tabs::{self, ProductTab};
use aw_providers::products::{ForecastProductService, ProductResult};
use wxdragon::prelude::*;

use crate::app::{post_to_ui, with_state};
use panel::{Loader, PanelOptions, ProductPanel};

// ---------------------------------------------------------------------------
// Background work
// ---------------------------------------------------------------------------

thread_local! {
    /// Open panels and dialogs that background results are delivered to. A
    /// result for one that has closed finds nothing and is dropped, like
    /// Python's `guard_destroyed`.
    static OPEN: RefCell<HashMap<u64, Rc<dyn Any>>> = RefCell::new(HashMap::new());
    static NEXT_ID: Cell<u64> = const { Cell::new(1) };
}

fn next_id() -> u64 {
    NEXT_ID.with(|n| {
        let id = n.get();
        n.set(id + 1);
        id
    })
}

fn register(id: u64, object: Rc<dyn Any>) {
    OPEN.with(|o| o.borrow_mut().insert(id, object));
}

fn unregister(id: u64) {
    OPEN.with(|o| o.borrow_mut().remove(&id));
}

fn lookup<T: 'static>(id: u64) -> Option<Rc<T>> {
    let object = OPEN.with(|o| o.borrow().get(&id).cloned())?;
    object.downcast().ok()
}

/// Run `work` on a worker thread, then `done` on the UI thread with the
/// object registered as `id`, if it is still open.
fn in_background<T: 'static, R: Send + 'static>(
    id: u64,
    work: impl FnOnce() -> R + Send + 'static,
    done: impl FnOnce(&Rc<T>, R) + Send + 'static,
) {
    std::thread::Builder::new()
        .name("aw-text-products".into())
        .spawn(move || {
            let result = work();
            post_to_ui(move || {
                if let Some(object) = lookup::<T>(id) {
                    done(&object, result);
                }
            });
        })
        .expect("spawn text products thread");
}

/// Posts a closure to the UI thread for the object registered as `id`.
fn post_to<T: 'static>(id: u64, f: impl FnOnce(&Rc<T>) + Send + 'static) {
    post_to_ui(move || {
        if let Some(object) = lookup::<T>(id) {
            f(&object);
        }
    });
}

/// Widgets a dialog creates, in order: kind and label (or a text control's
/// initial value; `*` when it is computed). Golden-tested against the
/// Python constructors so labels and their order cannot drift.
type WidgetSpec = &'static [(&'static str, &'static str)];

struct Texts(std::slice::Iter<'static, (&'static str, &'static str)>);

impl Texts {
    fn new(spec: WidgetSpec) -> Self {
        Self(spec.iter())
    }

    /// The text of the next widget, which must be a `kind`.
    fn next(&mut self, kind: &str) -> &'static str {
        let (spec_kind, text) = self.0.next().expect("widget spec is too short");
        debug_assert_eq!(*spec_kind, kind);
        text
    }
}

/// The app's shared text-product service (`_get_forecast_product_service`).
fn service() -> Option<Arc<ForecastProductService>> {
    with_state().map(|s| s.borrow().products.clone())
}

/// Take panel `index` out of `panels`, then drop its page with
/// `remove_page`; put it back when the notebook refuses.
///
/// Deliberate divergence: Python updates its panel list only after the
/// notebook has removed the page, so the page change the removal reports
/// looks up the stale list and loads the wrong tab (or none) when the
/// removed tab was selected.
fn detach_panel<T>(
    panels: &RefCell<Vec<T>>,
    index: usize,
    remove_page: impl FnOnce() -> bool,
) -> Option<T> {
    let panel = panels.borrow_mut().remove(index);
    if remove_page() {
        Some(panel)
    } else {
        panels.borrow_mut().insert(index, panel);
        None
    }
}

// ---------------------------------------------------------------------------
// Forecaster Notes
// ---------------------------------------------------------------------------

const TITLE: &str = "Forecaster Notes";
const CHECKING_ACTIVE: &str = "Checking active SPC and WPC products...";

const WIDGETS: WidgetSpec = &[
    ("StaticText", CHECKING_ACTIVE),
    ("Button", "&National Products"),
    ("Button#CLOSE", "&Close"),
];

struct NotesDialog {
    id: u64,
    dialog: Dialog,
    notebook: Notebook,
    active_iem_status: StaticText,
    location: Location,
    service: Arc<ForecastProductService>,
    panels: RefCell<Vec<Rc<ProductPanel>>>,
}

/// Open Forecaster Notes for `location` over the main window. Python's
/// `discussion` toast activation goes through `_on_discussion`
/// ([`super::commands::on_discussion`]), which passes the current location.
pub(crate) fn open_forecaster_notes(location: &Location) {
    if let Some(frame) = super::main_frame() {
        show_forecast_products_dialog(&frame, location);
    }
}

/// `show_forecast_products_dialog`: modal, destroyed on close.
fn show_forecast_products_dialog(parent: &dyn WxWidget, location: &Location) {
    let Some(service) = service() else { return };
    let dialog = Dialog::builder(parent, TITLE)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let mut texts = Texts::new(WIDGETS);
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let notebook = Notebook::builder(&dialog).build();
    main_sizer.add(&notebook, 1, SizerFlag::All | SizerFlag::Expand, 8);
    let active_iem_status = StaticText::builder(&dialog)
        .with_label(texts.next("StaticText"))
        .build();
    main_sizer.add(
        &active_iem_status,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Expand,
        8,
    );
    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let national_button = Button::builder(&dialog)
        .with_label(texts.next("Button"))
        .build();
    button_sizer.add(&national_button, 0, SizerFlag::empty(), 0);
    let close_button = Button::builder(&dialog)
        .with_id(ID_CLOSE)
        .with_label(texts.next("Button#CLOSE"))
        .build();
    button_sizer.add_stretch_spacer(1);
    button_sizer.add(&close_button, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&button_sizer, 0, SizerFlag::All | SizerFlag::Expand, 8);
    dialog.set_sizer(main_sizer, true);

    let d = Rc::new(NotesDialog {
        id: next_id(),
        dialog,
        notebook,
        active_iem_status,
        location: location.clone(),
        service,
        panels: RefCell::new(Vec::new()),
    });
    register(d.id, d.clone());

    let (initial, pending) = tabs::forecaster_tabs(location);
    for plan in initial {
        d.add_tab_panel(plan.tab, plan.autoload, None);
    }

    {
        let weak = Rc::downgrade(&d);
        close_button.on_click(move |e| {
            e.event.skip(false);
            if let Some(d) = weak.upgrade() {
                d.dialog.end_modal(ID_CLOSE);
            }
        });
        let weak = Rc::downgrade(&d);
        national_button.on_click(move |_| {
            if let Some(d) = weak.upgrade() {
                national::show_national_products_dialog(&d.dialog, d.service.clone());
            }
        });
        let weak = Rc::downgrade(&d);
        notebook.on_page_changed(move |_| {
            if let Some(d) = weak.upgrade() {
                d.on_page_changed();
            }
        });
        dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
            if e.get_key_code() == Some(WXK_ESCAPE) {
                e.skip(false);
                dialog.close(false);
            } else {
                e.skip(true);
            }
        });
    }
    d.schedule_active_iem_tab_check(pending);

    dialog.set_size(Size::new(700, 600));
    dialog.centre();
    // Land on the tab strip so the user hears which tab is selected;
    // landing in the content would read the whole product first.
    post_to_ui(move || notebook.set_focus());
    dialog.show_modal();

    unregister(d.id);
    for panel in d.panels.borrow().iter() {
        panel.close();
    }
    dialog.destroy();
}

impl NotesDialog {
    /// `_add_tab_panel`: a notebook page for a resolved tab, loading from
    /// the tab's loader or showing an already-fetched product.
    fn add_tab_panel(
        self: &Rc<Self>,
        tab: ProductTab,
        autoload: bool,
        product: Option<TextProduct>,
    ) {
        let loader: Loader = match product {
            Some(product) => Arc::new(move || Ok(ProductResult::One(Some(product.clone())))),
            None => self.make_loader(tab),
        };
        let weak = Rc::downgrade(self);
        let on_availability = move |panel_id: u64, has_product: bool| {
            if let Some(d) = weak.upgrade() {
                d.on_panel_availability_resolved(panel_id, has_product);
            }
        };
        let lookup_product = tabs::advanced_lookup_product_type(tab.product_type).to_string();
        let weak = Rc::downgrade(self);
        let open_advanced_lookup = move || {
            if let Some(d) = weak.upgrade() {
                advanced::show_advanced_text_product_dialog(
                    &d.dialog,
                    &d.location,
                    d.service.clone(),
                    &lookup_product,
                );
            }
        };
        let panel = ProductPanel::new(
            &self.notebook,
            PanelOptions {
                product_type: tab.product_type.to_string(),
                loader,
                cwa_office: tabs::panel_cwa(&tab, &self.location),
                location_name: self.location.name.clone(),
                on_availability: Some(Box::new(on_availability)),
                advanced_lookup: Some(Box::new(open_advanced_lookup)),
                autoload,
            },
        );
        self.notebook.add_page(&panel.panel, tab.label, false, None);
        self.panels.borrow_mut().push(panel);
    }

    /// `_make_loader`: fetch a tab's product on a worker thread.
    fn make_loader(&self, tab: ProductTab) -> Loader {
        let service = self.service.clone();
        let location = self.location.clone();
        // Python also passes the weather client for the Pirate Weather
        // beach fallback, which needs a port not in this workstream.
        Arc::new(move || {
            let result = tabs::load_tab(&service, &location, &tab, None);
            // `_check_daily_climate_notification`.
            if let (tabs::LoaderKind::DailyClimate, Ok(ProductResult::One(Some(product)))) =
                (tab.loader_kind, &result)
            {
                super::weather_events::on_daily_climate_report_loaded(
                    product.clone(),
                    location.name.clone(),
                );
            }
            result
        })
    }

    /// Check the optional SPC/WPC tabs in the background and add only the
    /// active ones.
    fn schedule_active_iem_tab_check(self: &Rc<Self>, pending: Vec<ProductTab>) {
        if pending.is_empty() {
            self.finish_active_iem_tab_check();
            return;
        }
        let service = self.service.clone();
        let location = self.location.clone();
        in_background(
            self.id,
            move || tabs::resolve_active_iem_tabs(&service, &location, &pending),
            |d: &Rc<NotesDialog>, resolved| {
                for (tab, product) in resolved {
                    d.add_tab_panel(tab, false, Some(product));
                }
                d.finish_active_iem_tab_check();
            },
        );
    }

    fn finish_active_iem_tab_check(&self) {
        self.active_iem_status.set_label("");
        self.active_iem_status.show(false);
        self.dialog.layout();
    }

    /// Remove a supplemental tab whose lookup finished with no content.
    fn on_panel_availability_resolved(&self, panel_id: u64, has_product: bool) {
        let (index, product_type, count) = {
            let panels = self.panels.borrow();
            let Some(index) = panels.iter().position(|p| p.id == panel_id) else {
                return;
            };
            (
                index,
                panels[index].product_type().to_string(),
                panels.len(),
            )
        };
        if tabs::keeps_tab(&product_type, has_product, count) {
            return;
        }
        let Some(panel) = detach_panel(&self.panels, index, || self.notebook.remove_page(index))
        else {
            tracing::debug!("Notebook refused to remove empty {product_type} page");
            return;
        };
        panel.close();
        panel.panel.destroy();
        // The page the notebook moved to may not have been loaded yet.
        self.on_page_changed();
    }

    /// Lazy-load a tab when the user selects it.
    fn on_page_changed(&self) {
        let selection = self.notebook.selection();
        let panel = usize::try_from(selection)
            .ok()
            .and_then(|i| self.panels.borrow().get(i).cloned());
        if let Some(panel) = panel {
            panel.ensure_loaded();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The page change reported while the notebook drops a page must see
    /// the panel list without the removed panel.
    #[test]
    fn removed_panel_is_gone_before_the_notebook_reselects() {
        let panels = RefCell::new(vec!["AFD", "HWO", "SPS"]);
        let removed = detach_panel(&panels, 1, || {
            // wxNotebook selects the next page and reports it here.
            assert_eq!(panels.borrow().get(1), Some(&"SPS"));
            true
        });
        assert_eq!(removed, Some("HWO"));
        assert_eq!(*panels.borrow(), ["AFD", "SPS"]);
        assert_eq!(detach_panel(&panels, 0, || false), None);
        assert_eq!(*panels.borrow(), ["AFD", "SPS"]);
    }
}
