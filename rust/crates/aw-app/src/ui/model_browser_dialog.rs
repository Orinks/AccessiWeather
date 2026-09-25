//! Model browser for OpenRouter and Venice AI models, ported from
//! `ui/dialogs/model_browser_dialog.py` (UI only: the catalogs come from
//! `settings_actions::fetch_model_catalog`).

use std::cell::{Cell, RefCell};
use std::rc::Rc;

use wxdragon::prelude::*;

use super::settings_actions::{self, VeniceBalance};
use crate::app::post_to_ui;
use crate::screen_reader::announce;

/// `OpenRouterModel` / `VeniceModel` as the browser sees them.
#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
pub(crate) struct CatalogModel {
    pub id: String,
    pub name: String,
    pub description: String,
    pub context_length: Option<u64>,
    /// USD per million tokens; `None` when the catalog did not say.
    pub pricing_prompt: Option<f64>,
    pub pricing_completion: Option<f64>,
    pub is_free: bool,
    pub supports_function_calling: bool,
    pub offline: bool,
    /// Vendor id used by the provider filter ("openai", "meta-llama", ...).
    pub provider: String,
}

impl CatalogModel {
    pub fn display_name(&self) -> String {
        let mut name = self.name.clone();
        if self.is_free {
            name.push_str(" (Free)");
        }
        if self.offline {
            name.push_str(" (Offline)");
        }
        name
    }

    pub fn context_display(&self) -> String {
        match self.context_length {
            None => "Unknown".to_string(),
            Some(n) if n >= 1_000_000 => format!("{:.1}M", n as f64 / 1_000_000.0),
            Some(n) if n >= 1000 => format!("{:.0}K", n as f64 / 1000.0),
            Some(n) => n.to_string(),
        }
    }
}

const PROVIDER_DISPLAY_NAMES: &[(&str, &str)] = &[
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic"),
    ("google", "Google"),
    ("meta-llama", "Meta"),
    ("mistralai", "Mistral AI"),
    ("cohere", "Cohere"),
    ("perplexity", "Perplexity"),
    ("deepseek", "DeepSeek"),
    ("microsoft", "Microsoft"),
    ("amazon", "Amazon"),
    ("nvidia", "NVIDIA"),
    ("qwen", "Qwen"),
    ("x-ai", "xAI"),
    ("ai21", "AI21 Labs"),
    ("databricks", "Databricks"),
    ("inflection", "Inflection"),
    ("cognitivecomputations", "Cognitive Computations"),
    ("nousresearch", "Nous Research"),
    ("openchat", "OpenChat"),
    ("openrouter", "OpenRouter"),
    ("neversleep", "NeverSleep"),
    ("gryphe", "Gryphe"),
    ("undi95", "Undi95"),
    ("huggingfaceh4", "Hugging Face"),
    ("pygmalionai", "Pygmalion AI"),
    ("mancer", "Mancer"),
    ("lynn", "Lynn"),
    ("thedrummer", "TheDrummer"),
    ("sao10k", "Sao10k"),
    ("eva-unit-01", "Eva Unit 01"),
    ("aetherwiing", "Aetherwiing"),
    ("sophosympatheia", "Sophosympatheia"),
    ("liquid", "Liquid"),
    ("01-ai", "01.AI"),
    ("venice", "Venice"),
    ("moonshotai", "Moonshot AI"),
    ("z-ai", "Z.ai"),
    ("minimax", "MiniMax"),
    ("xiaomi", "Xiaomi"),
    ("bytedance", "ByteDance"),
    ("inception", "Inception"),
    ("aion-labs", "Aion Labs"),
];

/// Python's `str.title()`: a letter after a non-letter starts a word.
fn title_case(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut previous_cased = false;
    for c in s.chars() {
        if c.is_alphabetic() {
            if previous_cased {
                out.extend(c.to_lowercase());
            } else {
                out.extend(c.to_uppercase());
            }
            previous_cased = true;
        } else {
            out.push(c);
            previous_cased = false;
        }
    }
    out
}

/// `get_provider_display_name`.
pub(crate) fn provider_display_name(provider: &str) -> String {
    PROVIDER_DISPLAY_NAMES
        .iter()
        .find(|(id, _)| *id == provider)
        .map(|(_, name)| name.to_string())
        .unwrap_or_else(|| title_case(&provider.replace('-', " ")))
}

/// Python's `f"{x:g}"`: six significant digits, trailing zeros dropped,
/// exponent form outside 1e-4..1e6.
pub(crate) fn format_g(x: f64) -> String {
    if x == 0.0 {
        return if x.is_sign_negative() { "-0" } else { "0" }.to_string();
    }
    if !x.is_finite() {
        return if x.is_nan() {
            "nan".to_string()
        } else if x > 0.0 {
            "inf".to_string()
        } else {
            "-inf".to_string()
        };
    }
    let sci = format!("{x:.5e}");
    let (mantissa, exponent) = sci.split_once('e').expect("exponent form");
    let exponent: i32 = exponent.parse().expect("integer exponent");
    let trim = |s: &str| {
        if s.contains('.') {
            s.trim_end_matches('0').trim_end_matches('.').to_string()
        } else {
            s.to_string()
        }
    };
    if (-4..6).contains(&exponent) {
        trim(&format!("{:.*}", (5 - exponent) as usize, x))
    } else {
        let sign = if exponent < 0 { '-' } else { '+' };
        format!("{}e{sign}{:02}", trim(mantissa), exponent.abs())
    }
}

/// `_model_pricing`.
pub(crate) fn model_pricing(model: &CatalogModel) -> String {
    if model.is_free {
        return "Free".to_string();
    }
    let price = |v: Option<f64>| v.map_or("unknown".to_string(), |v| format!("${}", format_g(v)));
    format!(
        "Input: {}; output: {} per million tokens",
        price(model.pricing_prompt),
        price(model.pricing_completion)
    )
}

/// `_balance_status`: account permission, never implying a model is free.
pub(crate) fn balance_status(balance: Option<&VeniceBalance>) -> String {
    let mut amounts = Vec::new();
    if let Some(b) = balance {
        if let Some(usd) = b.usd {
            amounts.push(format!("USD: ${}", format_g(usd)));
        }
        if let Some(diem) = b.diem {
            amounts.push(format!("DIEM: {}", format_g(diem)));
        }
        if let Some(currency) = b.consumption_currency.as_deref().filter(|c| !c.is_empty()) {
            amounts.push(format!("Consumption currency: {currency}"));
        }
    }
    let prefix = if amounts.is_empty() {
        String::new()
    } else {
        format!("{}. ", amounts.join("; "))
    };
    let status = match balance.and_then(|b| b.can_consume.map(|c| (b, c))) {
        None => "Credit status unknown. Paid models remain selectable; check your Venice API account before use.",
        Some((b, false)) if b.usd == Some(0.0) && b.diem == Some(0.0) => {
            "No API credits available. Paid models remain selectable but need credits before use."
        }
        Some((_, false)) => "Account cannot currently consume API credits. Paid models remain selectable but require usable credits before use.",
        Some((_, true)) => "Account can consume API credits. Paid model charges still apply; this does not guarantee enough credit for a request.",
    };
    format!("{prefix}{status}")
}

const NO_KEY_BALANCE: &str = "Add a Venice API key to check account credits. The public model catalog is available without a key.";
const CHECKING_BALANCE: &str = "Checking Venice account credit status…";
const OFFLINE_MODEL: &str = "This model is offline and unavailable for selection.";

/// The browser's filter controls.
#[derive(Debug, Clone, Default)]
pub(crate) struct Filters {
    pub search: String,
    pub free_only: bool,
    /// Venice price filter: 0 all, 1 free, 2 paid.
    pub price: u32,
    pub function_only: bool,
    /// Provider choice index; 0 is "All Providers".
    pub provider_index: usize,
}

/// `_matches_price_and_capability`.
pub(crate) fn matches_price_and_capability(
    model: &CatalogModel,
    venice: bool,
    f: &Filters,
) -> bool {
    if !venice {
        return !f.free_only || model.is_free;
    }
    if f.price == 1 && !model.is_free {
        return false;
    }
    let paid = model.pricing_prompt.is_some_and(|p| p > 0.0)
        || model.pricing_completion.is_some_and(|p| p > 0.0);
    if f.price == 2 && !paid {
        return false;
    }
    !f.function_only || model.supports_function_calling
}

/// `_update_provider_list`: the providers of the models passing the price and
/// capability filters, sorted.
pub(crate) fn provider_list(models: &[CatalogModel], venice: bool, f: &Filters) -> Vec<String> {
    let mut providers: Vec<String> = models
        .iter()
        .filter(|m| matches_price_and_capability(m, venice, f))
        .map(|m| m.provider.clone())
        .collect();
    providers.sort();
    providers.dedup();
    providers
}

/// `_apply_filters`: the models to list, given the provider ids behind the
/// provider choice.
pub(crate) fn apply_filters<'a>(
    models: &'a [CatalogModel],
    venice: bool,
    f: &Filters,
    providers: &[String],
) -> Vec<&'a CatalogModel> {
    let search = f.search.to_lowercase();
    let search = search.trim();
    let provider = f
        .provider_index
        .checked_sub(1)
        .and_then(|i| providers.get(i));
    models
        .iter()
        .filter(|m| matches_price_and_capability(m, venice, f))
        .filter(|m| provider.is_none_or(|p| m.provider == *p))
        .filter(|m| {
            search.is_empty()
                || m.name.to_lowercase().contains(search)
                || m.id.to_lowercase().contains(search)
                || m.description.to_lowercase().contains(search)
        })
        .collect()
}

/// `_populate_list`: one screen-reader-friendly line per model.
pub(crate) fn list_item(model: &CatalogModel, venice: bool) -> String {
    let pricing = if venice {
        model_pricing(model)
    } else if model.is_free {
        "Free".to_string()
    } else {
        format!(
            "${:.6} per 1K tokens",
            model.pricing_prompt.unwrap_or(0.0) / 1000.0
        )
    };
    let mut item = format!(
        "{} - Context: {} - {pricing}",
        model.display_name(),
        model.context_display()
    );
    if venice {
        item.push_str(if model.supports_function_calling {
            " - Weather assistant compatible"
        } else {
            " - Explanations only"
        });
    }
    item
}

/// The status line after filtering.
pub(crate) fn status_text(showing: usize, total: usize) -> String {
    if showing == total {
        format!("{total} models available")
    } else {
        format!("Showing {showing} of {total} models")
    }
}

/// `_on_model_selected`: the description shown for a model.
pub(crate) fn model_description(model: &CatalogModel, venice: bool) -> String {
    let mut desc = if model.description.is_empty() {
        "No description available.".to_string()
    } else {
        model.description.clone()
    };
    if venice {
        if model.offline {
            desc.push('\n');
            desc.push_str(OFFLINE_MODEL);
        }
        desc.push('\n');
        desc.push_str(&model_pricing(model));
        desc.push_str(if model.supports_function_calling {
            "\nSupports weather assistant function calling."
        } else {
            "\nDoes not support weather assistant function calling; use for explanations only."
        });
    }
    desc
}

struct ModelBrowser {
    dialog: Dialog,
    venice: bool,
    api_key: Option<String>,
    search_box: TextCtrl,
    free_only_checkbox: CheckBox,
    price_choice: Option<Choice>,
    function_checkbox: Option<CheckBox>,
    provider_choice: Choice,
    status_label: StaticText,
    balance_label: Option<StaticText>,
    model_list: ListBox,
    description_text: TextCtrl,
    refresh_btn: Button,
    select_btn: Button,
    all_models: RefCell<Vec<CatalogModel>>,
    filtered_models: RefCell<Vec<CatalogModel>>,
    providers: RefCell<Vec<String>>,
    selected_model_id: RefCell<Option<String>>,
    load_generation: Cell<u64>,
    closed: Cell<bool>,
}

thread_local! {
    static BROWSER: RefCell<Option<Rc<ModelBrowser>>> = const { RefCell::new(None) };
}

/// `show_model_browser_dialog`: the chosen model id, or `None` if cancelled.
/// `provider` is "openrouter" or "venice".
pub(crate) fn show_model_browser_dialog(
    parent: &dyn WxWidget,
    api_key: Option<String>,
    provider: &str,
) -> Option<String> {
    let venice = provider == "venice";
    let dialog = Dialog::builder(
        parent,
        if venice {
            "Browse Venice Models"
        } else {
            "Browse AI Models"
        },
    )
    .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
    .with_size(650, 550)
    .build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();

    let search_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let search_label = StaticText::builder(&dialog)
        .with_label("Search models:")
        .build();
    search_sizer.add(
        &search_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    let search_box = TextCtrl::builder(&dialog)
        .with_size(Size::new(300, -1))
        .build();
    search_sizer.add(&search_box, 1, SizerFlag::Expand, 0);
    main_sizer.add_sizer(&search_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);

    let filter_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let free_only_checkbox = CheckBox::builder(&dialog).with_label("Free only").build();
    filter_sizer.add(
        &free_only_checkbox,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        15,
    );
    let (price_choice, function_checkbox) = if venice {
        free_only_checkbox.hide();
        let price_label = StaticText::builder(&dialog).with_label("Price:").build();
        filter_sizer.add(&price_label, 0, SizerFlag::AlignCenterVertical, 0);
        let price = Choice::builder(&dialog)
            .with_choices(vec!["All prices".into(), "Free".into(), "Paid".into()])
            .build();
        price.set_selection(0);
        price.set_name("Model price filter");
        filter_sizer.add(&price, 0, SizerFlag::Right, 10);
        let function = CheckBox::builder(&dialog)
            .with_label("Weather assistant compatible")
            .build();
        function.set_name("Weather assistant compatible models only");
        filter_sizer.add(&function, 0, SizerFlag::Right, 10);
        (Some(price), Some(function))
    } else {
        (None, None)
    };
    let provider_label = StaticText::builder(&dialog).with_label("Provider:").build();
    filter_sizer.add(
        &provider_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        5,
    );
    let provider_choice = Choice::builder(&dialog)
        .with_choices(vec!["All Providers".into()])
        .build();
    provider_choice.set_selection(0);
    filter_sizer.add(&provider_choice, 0, SizerFlag::AlignCenterVertical, 0);
    main_sizer.add_sizer(
        &filter_sizer,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );

    let status_label = StaticText::builder(&dialog)
        .with_label("Loading models...")
        .build();
    main_sizer.add(&status_label, 0, SizerFlag::Left | SizerFlag::Right, 10);
    let balance_label = venice.then(|| {
        let label = StaticText::builder(&dialog)
            .with_label(CHECKING_BALANCE)
            .build();
        label.set_name("Venice account credit status");
        main_sizer.add(
            &label,
            0,
            SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
            10,
        );
        label
    });

    let list_label = StaticText::builder(&dialog)
        .with_label("Available models:")
        .build();
    main_sizer.add(
        &list_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );
    let model_list = ListBox::builder(&dialog)
        .with_size(Size::new(-1, 200))
        .build();
    main_sizer.add(
        &model_list,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );

    let desc_label = StaticText::builder(&dialog)
        .with_label("Model description:")
        .build();
    main_sizer.add(
        &desc_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );
    let description_text = TextCtrl::builder(&dialog)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::WordWrap)
        .with_size(Size::new(-1, 80))
        .build();
    main_sizer.add(
        &description_text,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );

    let btn_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let refresh_btn = Button::builder(&dialog).with_label("&Refresh").build();
    btn_sizer.add(&refresh_btn, 0, SizerFlag::Right, 10);
    btn_sizer.add_stretch_spacer(1);
    let select_btn = Button::builder(&dialog)
        .with_id(ID_OK)
        .with_label("&Select")
        .build();
    select_btn.enable(false);
    btn_sizer.add(&select_btn, 0, SizerFlag::Right, 10);
    let cancel_btn = Button::builder(&dialog)
        .with_id(ID_CANCEL)
        .with_label("&Cancel")
        .build();
    btn_sizer.add(&cancel_btn, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&btn_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);

    dialog.set_sizer(main_sizer, true);
    search_box.set_name("Search models");
    provider_choice.set_name("Model provider filter");
    model_list.set_name("Available models");
    description_text.set_name("Model description");
    search_box.set_focus();

    let b = Rc::new(ModelBrowser {
        dialog,
        venice,
        api_key,
        search_box,
        free_only_checkbox,
        price_choice,
        function_checkbox,
        provider_choice,
        status_label,
        balance_label,
        model_list,
        description_text,
        refresh_btn,
        select_btn,
        all_models: RefCell::new(Vec::new()),
        filtered_models: RefCell::new(Vec::new()),
        providers: RefCell::new(Vec::new()),
        selected_model_id: RefCell::new(None),
        load_generation: Cell::new(0),
        closed: Cell::new(false),
    });
    b.bind(cancel_btn);
    BROWSER.with(|slot| *slot.borrow_mut() = Some(b.clone()));
    b.load_models();

    let result = b.dialog.show_modal();
    b.closed.set(true);
    BROWSER.with(|slot| slot.borrow_mut().take());
    let selected = b.selected_model_id.borrow().clone();
    b.dialog.destroy();
    (result == ID_OK).then_some(selected).flatten()
}

impl ModelBrowser {
    fn bind(self: &Rc<Self>, cancel_btn: Button) {
        let b = self.clone();
        self.search_box.on_text_changed(move |_| b.apply_filters());
        let b = self.clone();
        self.free_only_checkbox
            .on_toggled(move |_| b.on_filter_changed(true));
        if let Some(price) = self.price_choice {
            let b = self.clone();
            price.on_selection_changed(move |_| b.on_filter_changed(false));
        }
        if let Some(function) = self.function_checkbox {
            let b = self.clone();
            function.on_toggled(move |_| b.on_filter_changed(false));
        }
        let b = self.clone();
        self.provider_choice
            .on_selection_changed(move |_| b.on_filter_changed(false));
        let b = self.clone();
        self.model_list
            .on_selection_changed(move |_| b.on_model_selected());
        let b = self.clone();
        self.model_list
            .on_item_double_clicked(move |_| b.on_model_double_click());
        let b = self.clone();
        self.model_list
            .bind_internal(EventType::CHAR_HOOK, move |e: Event| {
                if matches!(e.get_key_code(), Some(WXK_RETURN | WXK_NUMPAD_ENTER)) {
                    e.skip(false);
                    b.on_select();
                } else {
                    e.skip(true);
                }
            });
        let b = self.clone();
        self.refresh_btn.on_click(move |_| b.load_models());
        let b = self.clone();
        self.select_btn.on_click(move |e| {
            e.event.skip(false);
            b.on_select();
        });
        let b = self.clone();
        cancel_btn.on_click(move |e| {
            e.event.skip(false);
            b.on_close();
        });
        let b = self.clone();
        self.dialog
            .bind_internal(EventType::CLOSE_WINDOW, move |_: Event| b.on_close());
        let b = self.clone();
        self.dialog
            .bind_internal(EventType::CHAR_HOOK, move |e: Event| {
                if e.get_key_code() == Some(WXK_ESCAPE) {
                    e.skip(false);
                    b.on_close();
                } else {
                    e.skip(true);
                }
            });
    }

    fn filters(&self) -> Filters {
        Filters {
            search: self.search_box.get_value(),
            free_only: self.free_only_checkbox.is_checked(),
            price: self
                .price_choice
                .and_then(|c| c.get_selection())
                .unwrap_or(0),
            function_only: self.function_checkbox.is_some_and(|c| c.is_checked()),
            provider_index: self
                .provider_choice
                .get_selection()
                .map_or(0, |i| i as usize),
        }
    }

    /// `_on_filter_changed`.
    fn on_filter_changed(&self, free_only_changed: bool) {
        if free_only_changed || self.venice {
            self.update_provider_list();
        }
        self.apply_filters();
        announce(&self.status_label.get_label());
    }

    /// `_update_provider_list`, keeping the chosen provider when it remains.
    fn update_provider_list(&self) {
        let providers = provider_list(&self.all_models.borrow(), self.venice, &self.filters());
        let current = self.provider_choice.get_string_selection();
        self.provider_choice.clear();
        self.provider_choice.append("All Providers");
        let names: Vec<String> = providers.iter().map(|p| provider_display_name(p)).collect();
        for name in &names {
            self.provider_choice.append(name);
        }
        let index = current
            .and_then(|c| {
                std::iter::once("All Providers".to_string())
                    .chain(names)
                    .position(|n| n == c)
            })
            .unwrap_or(0);
        self.provider_choice.set_selection(index as u32);
        *self.providers.borrow_mut() = providers;
    }

    /// `_apply_filters` + `_populate_list`.
    fn apply_filters(&self) {
        let filtered: Vec<CatalogModel> = {
            let all = self.all_models.borrow();
            apply_filters(&all, self.venice, &self.filters(), &self.providers.borrow())
                .into_iter()
                .cloned()
                .collect()
        };
        self.model_list.clear();
        for model in &filtered {
            self.model_list.append(&list_item(model, self.venice));
        }
        let total = self.all_models.borrow().len();
        self.status_label
            .set_label(&status_text(filtered.len(), total));
        *self.filtered_models.borrow_mut() = filtered;
        *self.selected_model_id.borrow_mut() = None;
        self.select_btn.enable(false);
        self.description_text.set_value("");
    }

    fn selected_model(&self) -> Option<CatalogModel> {
        let index = self.model_list.get_selection()? as usize;
        self.filtered_models.borrow().get(index).cloned()
    }

    /// `_on_model_selected`.
    fn on_model_selected(&self) {
        match self.selected_model() {
            Some(model) => {
                *self.selected_model_id.borrow_mut() = (!model.offline).then(|| model.id.clone());
                self.select_btn.enable(!model.offline);
                self.description_text
                    .set_value(&model_description(&model, self.venice));
            }
            None => {
                *self.selected_model_id.borrow_mut() = None;
                self.select_btn.enable(false);
                self.description_text.set_value("");
            }
        }
    }

    /// `_on_model_double_click`.
    fn on_model_double_click(&self) {
        let Some(model) = self.selected_model() else {
            return;
        };
        if model.offline {
            self.on_model_selected();
            announce(OFFLINE_MODEL);
            return;
        }
        *self.selected_model_id.borrow_mut() = Some(model.id);
        self.closed.set(true);
        self.dialog.end_modal(ID_OK);
    }

    /// `_on_select`.
    fn on_select(&self) {
        if self.selected_model_id.borrow().is_some() {
            self.closed.set(true);
            self.dialog.end_modal(ID_OK);
        } else if self.selected_model().is_some_and(|m| m.offline) {
            announce(OFFLINE_MODEL);
        }
    }

    /// `_on_close`.
    fn on_close(&self) {
        self.closed.set(true);
        self.dialog.end_modal(ID_CANCEL);
    }

    /// `_load_models`: fetch on a worker thread; stale or post-close results
    /// are dropped.
    fn load_models(&self) {
        let generation = self.load_generation.get() + 1;
        self.load_generation.set(generation);
        self.status_label.set_label("Loading models...");
        self.all_models.borrow_mut().clear();
        self.filtered_models.borrow_mut().clear();
        self.model_list.clear();
        self.select_btn.enable(false);
        *self.selected_model_id.borrow_mut() = None;
        self.description_text.set_value("");
        self.refresh_btn.enable(false);
        self.search_box.set_focus();
        announce("Loading models…");
        if let Some(label) = self.balance_label {
            label.set_label(if self.api_key.is_some() {
                CHECKING_BALANCE
            } else {
                NO_KEY_BALANCE
            });
        }
        let venice = self.venice;
        let api_key = self.api_key.clone();
        std::thread::Builder::new()
            .name("aw-model-catalog".into())
            .spawn(move || {
                let result = settings_actions::fetch_model_catalog(venice, api_key.as_deref());
                post_to_ui(move || {
                    if let Some(b) = BROWSER.with(|slot| slot.borrow().clone()) {
                        b.finish_load(generation, result);
                    }
                });
            })
            .expect("spawn model catalog thread");
    }

    /// `_finish_load`.
    fn finish_load(
        &self,
        generation: u64,
        result: Result<(Vec<CatalogModel>, Option<VeniceBalance>), String>,
    ) {
        if self.closed.get() || generation != self.load_generation.get() {
            return;
        }
        self.refresh_btn.enable(true);
        let (models, balance, error) = match result {
            Ok((models, balance)) => (models, balance, None),
            Err(message) => (Vec::new(), None, Some(message)),
        };
        if let Some(label) = self.balance_label {
            label.set_label(&if self.api_key.is_some() {
                balance_status(balance.as_ref())
            } else {
                NO_KEY_BALANCE.to_string()
            });
            label.wrap(610);
            self.dialog.layout();
        }
        match error {
            Some(message) => self.status_label.set_label(&format!("Error: {message}")),
            None => {
                *self.all_models.borrow_mut() = models;
                self.update_provider_list();
                self.apply_filters();
            }
        }
        let mut announcement = self.status_label.get_label();
        if let Some(label) = self.balance_label {
            announcement.push_str(". ");
            announcement.push_str(&label.get_label());
        }
        announce(&announcement);
    }
}
