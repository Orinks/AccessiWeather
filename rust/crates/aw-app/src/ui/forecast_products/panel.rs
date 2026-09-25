//! One notebook tab of Forecaster Notes or National Products. Port of
//! `ui/dialogs/forecast_product_panel.py` (the wx half; the state machine is
//! [`super::state`]) and `forecast_product_widgets.py`.
//!
//! Every empty/error state renders inside the content area because a
//! `wx.Notebook` tab cannot be disabled on Windows.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::Arc;

use aw_ai::CancelToken;
use aw_providers::products::{ProductError, ProductResult};
use wxdragon::prelude::*;

use super::ai_summary::{self, Summary};
use super::state::{self, PanelState, PanelView, LOCAL_FORMATTERS};
use super::{in_background, next_id, post_to, register, unregister, Texts, WidgetSpec};
use crate::app::with_state;
use crate::screen_reader::announce;

/// Fetches a tab's product(s); runs on a worker thread.
pub(crate) type Loader = Arc<dyn Fn() -> Result<ProductResult, ProductError> + Send + Sync>;

pub(crate) struct PanelOptions {
    pub product_type: String,
    pub loader: Loader,
    /// `None` shows "populate after the next weather refresh" instead of
    /// loading (surf tabs load anyway).
    pub cwa_office: Option<String>,
    pub location_name: String,
    /// Called with the panel id and whether a finished load found content
    /// (errors count as content so Try again stays reachable).
    pub on_availability: Option<Box<dyn Fn(u64, bool)>>,
    pub advanced_lookup: Option<Box<dyn Fn()>>,
    /// Load now; otherwise the dialog loads the tab when it is selected.
    pub autoload: bool,
}

/// `create_product_panel_widgets`, after the header (the product's full
/// name) and, on SPS tabs, the chooser label.
pub(crate) const WIDGETS: WidgetSpec = &[
    ("TextCtrl", state::LOADING),
    ("StaticText", ""),
    ("StaticText", "Plain Language Summary:"),
    ("TextCtrl", ""),
    ("StaticText", "Model Information:"),
    ("TextCtrl", ""),
    ("Button", "Plain Language Summary"),
    ("Button", "Regenerate Summary"),
    ("Button", "Advanced Lookup"),
    ("Button", "Try again"),
];

pub(crate) const SPS_CHOICE_LABEL: &str = "Recent Special Weather Statements:";

pub(crate) struct ProductPanel {
    pub id: u64,
    pub panel: Panel,
    product_textctrl: TextCtrl,
    issuance_label: StaticText,
    sps_choice_label: Option<StaticText>,
    sps_choice: Option<Choice>,
    ai_summary_header: StaticText,
    ai_summary_display: TextCtrl,
    model_info_label: StaticText,
    model_info: TextCtrl,
    explain_button: Button,
    regenerate_button: Button,
    retry_button: Button,
    state: RefCell<PanelState>,
    /// What the widgets currently show.
    shown: RefCell<PanelView>,
    loader: Loader,
    location_name: String,
    on_availability: Option<Box<dyn Fn(u64, bool)>>,
    /// Stops a running summary once the panel closes.
    cancel: CancelToken,
}

/// Whether the selected AI provider has a key, read at the moment it matters.
fn has_key() -> bool {
    with_state().is_some_and(|s| ai_summary::has_selected_key(&s.borrow().config.settings))
}

impl ProductPanel {
    pub fn new(notebook: &Notebook, options: PanelOptions) -> Rc<Self> {
        let product_type = options.product_type.as_str();
        let panel = Panel::builder(notebook).build();
        let sizer = BoxSizer::builder(Orientation::Vertical).build();
        let label = |text: &str| StaticText::builder(&panel).with_label(text).build();
        let read_only = TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly;

        let header_label = label(state::header_text(product_type));
        sizer.add(&header_label, 0, SizerFlag::All | SizerFlag::Expand, 8);

        let (sps_choice_label, sps_choice) = if product_type == "SPS" {
            let choice_label = label(SPS_CHOICE_LABEL);
            sizer.add(&choice_label, 0, SizerFlag::Left | SizerFlag::Right, 8);
            let choice = Choice::builder(&panel).build();
            sizer.add(&choice, 0, SizerFlag::All | SizerFlag::Expand, 8);
            choice_label.show(false);
            choice.show(false);
            (Some(choice_label), Some(choice))
        } else {
            (None, None)
        };

        let mut texts = Texts::new(WIDGETS);
        let product_textctrl = TextCtrl::builder(&panel)
            .with_style(read_only | TextCtrlStyle::DontWrap)
            .with_value(texts.next("TextCtrl"))
            .build();
        sizer.add(&product_textctrl, 1, SizerFlag::All | SizerFlag::Expand, 8);

        let issuance_label = label(texts.next("StaticText"));
        sizer.add(
            &issuance_label,
            0,
            SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
            8,
        );

        let ai_summary_header = label(texts.next("StaticText"));
        sizer.add(&ai_summary_header, 0, SizerFlag::Left | SizerFlag::Right, 8);
        let ai_summary_display = TextCtrl::builder(&panel)
            .with_style(read_only)
            .with_value(texts.next("TextCtrl"))
            .build();
        sizer.add(
            &ai_summary_display,
            0,
            SizerFlag::All | SizerFlag::Expand,
            8,
        );
        ai_summary_header.show(false);
        ai_summary_display.show(false);

        let model_info_label = label(texts.next("StaticText"));
        sizer.add(
            &model_info_label,
            0,
            SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
            8,
        );
        let model_info = TextCtrl::builder(&panel)
            .with_value(texts.next("TextCtrl"))
            .with_style(read_only)
            .with_size(Size::new(-1, 80))
            .build();
        sizer.add(
            &model_info,
            0,
            SizerFlag::Left | SizerFlag::Right | SizerFlag::Expand,
            8,
        );
        model_info_label.show(false);
        model_info.show(false);

        let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
        let button = |text: &str| Button::builder(&panel).with_label(text).build();
        let explain_button = button(texts.next("Button"));
        let regenerate_button = button(texts.next("Button"));
        let advanced_lookup_button = button(texts.next("Button"));
        let retry_button = button(texts.next("Button"));
        button_sizer.add(&explain_button, 0, SizerFlag::Right, 5);
        button_sizer.add(&regenerate_button, 0, SizerFlag::Right, 5);
        button_sizer.add(&advanced_lookup_button, 0, SizerFlag::Right, 5);
        button_sizer.add(&retry_button, 0, SizerFlag::empty(), 0);
        sizer.add_sizer(&button_sizer, 0, SizerFlag::All, 8);

        regenerate_button.show(false);
        retry_button.show(false);
        explain_button.enable(false);
        panel.set_sizer(sizer, true);

        let state = PanelState::new(product_type, options.cwa_office, LOCAL_FORMATTERS);
        let shown = state.view.clone();
        let p = Rc::new(Self {
            id: next_id(),
            panel,
            product_textctrl,
            issuance_label,
            sps_choice_label,
            sps_choice,
            ai_summary_header,
            ai_summary_display,
            model_info_label,
            model_info,
            explain_button,
            regenerate_button,
            retry_button,
            state: RefCell::new(state),
            shown: RefCell::new(shown),
            loader: options.loader,
            location_name: options.location_name,
            on_availability: options.on_availability,
            cancel: CancelToken::new(),
        });
        register(p.id, p.clone());

        let id = p.id;
        explain_button.on_click(move |_| on(id, |p| p.on_explain(false)));
        // Python's Regenerate also clears the injected explainer's cache,
        // but no explainer is ever injected; each click builds a fresh one.
        regenerate_button.on_click(move |_| on(id, |p| p.on_explain(true)));
        retry_button.on_click(move |_| on(id, |p| p.trigger_load()));
        let advanced_lookup = options.advanced_lookup;
        advanced_lookup_button.on_click(move |_| {
            if let Some(open) = &advanced_lookup {
                open();
            }
        });
        if let Some(choice) = sps_choice {
            choice.on_selection_changed(move |_| on(id, |p| p.on_sps_choice_changed()));
        }

        if options.autoload {
            p.ensure_loaded();
        }
        p
    }

    pub fn product_type(&self) -> String {
        self.state.borrow().product_type.clone()
    }

    /// Stop delivering background results to this panel.
    pub fn close(&self) {
        self.cancel.cancel();
        unregister(self.id);
    }

    /// Load once, on construction or first selection of the tab.
    pub fn ensure_loaded(&self) {
        let start = self.state.borrow_mut().ensure_loaded();
        self.render();
        if start {
            self.schedule_load();
        }
    }

    fn trigger_load(&self) {
        let start = self.state.borrow_mut().trigger_load();
        self.render();
        if start {
            self.schedule_load();
        }
    }

    fn schedule_load(&self) {
        let loader = self.loader.clone();
        in_background(
            self.id,
            move || loader(),
            |p: &Rc<ProductPanel>, result| match result {
                Ok(result) => p.on_load_complete(result),
                Err(err) => {
                    tracing::warn!(
                        "ForecastProductPanel({}) load failed: {err}",
                        p.product_type()
                    );
                    p.on_load_error();
                }
            },
        );
    }

    fn on_load_complete(&self, result: ProductResult) {
        let has_product = self
            .state
            .borrow_mut()
            .on_load_complete(result.into_products(), has_key());
        self.render();
        self.notify_availability(has_product);
    }

    fn on_load_error(&self) {
        self.state.borrow_mut().on_load_error();
        self.render();
        self.notify_availability(true);
    }

    fn notify_availability(&self, has_product: bool) {
        if let Some(callback) = &self.on_availability {
            callback(self.id, has_product);
        }
    }

    fn on_sps_choice_changed(&self) {
        let Some(index) = self.sps_choice.and_then(|c| c.get_selection()) else {
            return;
        };
        self.state
            .borrow_mut()
            .on_sps_choice_changed(index as usize, has_key());
        self.render();
    }

    /// Plain Language Summary / Regenerate Summary (`regenerate`).
    fn on_explain(&self, regenerate: bool) {
        let Some(text) = self.state.borrow_mut().on_explain() else {
            return;
        };
        self.render();
        let Some((settings, cache)) = with_state().map(|s| {
            let st = s.borrow();
            (st.config.settings.clone(), st.ai_explanation_cache.clone())
        }) else {
            return;
        };
        let product_type = self.product_type();
        let location_name = self.location_name.clone();
        let cancel = self.cancel.clone();
        let id = self.id;
        in_background(
            id,
            move || {
                let status = |message: String| {
                    post_to(id, move |p: &Rc<ProductPanel>| {
                        p.on_explain_status(&message)
                    })
                };
                ai_summary::explain_text_product(
                    &settings,
                    cache,
                    regenerate,
                    &text,
                    &product_type,
                    &location_name,
                    &status,
                    &cancel,
                )
            },
            |p: &Rc<ProductPanel>, result| match result {
                Ok(summary) => p.on_explain_complete(&summary),
                Err(message) => p.on_explain_error(&message),
            },
        );
    }

    fn on_explain_status(&self, message: &str) {
        let announcement = self.state.borrow_mut().on_explain_status(message);
        self.render();
        if let Some(text) = announcement {
            announce(&text);
        }
    }

    fn on_explain_complete(&self, summary: &Summary) {
        let explain_had_focus = self.explain_button.has_focus();
        let (focus, announcement) = self
            .state
            .borrow_mut()
            .on_explain_complete(summary, explain_had_focus);
        self.render();
        if focus {
            self.ai_summary_display.set_focus();
        }
        announce(&announcement);
    }

    fn on_explain_error(&self, message: &str) {
        let announcement = self.state.borrow_mut().on_explain_error(message);
        self.render();
        self.ai_summary_display.set_focus();
        announce(&announcement);
    }

    /// Push state changes to the widgets.
    fn render(&self) {
        let view = self.state.borrow().view.clone();
        let mut shown = self.shown.borrow_mut();
        if view.product_text != shown.product_text {
            self.product_textctrl.set_value(&view.product_text);
        }
        if view.issuance != shown.issuance {
            self.issuance_label.set_label(&view.issuance);
        }
        if let Some(choice) = self.sps_choice {
            let refilled = view.sps_entries != shown.sps_entries;
            if refilled {
                choice.clear();
                for entry in &view.sps_entries {
                    choice.append(entry);
                }
            }
            if let Some(index) = view.sps_selection {
                if refilled || view.sps_selection != shown.sps_selection {
                    choice.set_selection(index as u32);
                }
            }
        }
        if view.ai_text != shown.ai_text {
            self.ai_summary_display.set_value(&view.ai_text);
        }
        if view.model_info != shown.model_info {
            self.model_info.set_value(&view.model_info);
        }
        if view.explain_enabled != shown.explain_enabled {
            self.explain_button.enable(view.explain_enabled);
        }

        let mut relayout = false;
        let mut show = |widgets: &[&dyn WxWidget], now: bool, before: bool| {
            if now != before {
                for widget in widgets {
                    widget.show(now);
                }
                relayout = true;
            }
        };
        if let (Some(label), Some(choice)) = (self.sps_choice_label, self.sps_choice) {
            show(&[&label, &choice], view.sps_visible, shown.sps_visible);
        }
        show(
            &[&self.ai_summary_header, &self.ai_summary_display],
            view.ai_visible,
            shown.ai_visible,
        );
        show(
            &[&self.model_info_label, &self.model_info],
            view.model_info_visible,
            shown.model_info_visible,
        );
        show(
            &[&self.explain_button],
            view.explain_visible,
            shown.explain_visible,
        );
        show(
            &[&self.regenerate_button],
            view.regenerate_visible,
            shown.regenerate_visible,
        );
        show(
            &[&self.retry_button],
            view.retry_visible,
            shown.retry_visible,
        );
        if relayout {
            self.panel.layout();
        }
        *shown = view;
    }
}

/// Run a handler on the panel registered as `id`.
fn on(id: u64, f: impl FnOnce(&ProductPanel)) {
    if let Some(p) = super::lookup::<ProductPanel>(id) {
        f(&p);
    }
}
