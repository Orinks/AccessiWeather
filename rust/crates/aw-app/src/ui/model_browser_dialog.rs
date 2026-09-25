//! Model browser for OpenRouter and Venice AI models, ported from
//! `ui/dialogs/model_browser_dialog.py`. The catalogs, filters and texts
//! are `aw_ai::models`; this is the wx half.

use std::cell::{Cell, RefCell};
use std::rc::Rc;

use aw_ai::models::{
    self, BrowserFilter, CatalogLoad, CatalogModel, PriceFilter, OFFLINE_MODEL_MESSAGE,
    VENICE_CHECKING_STATUS, VENICE_NO_KEY_STATUS,
};
use aw_ai::Provider;
use wxdragon::prelude::*;

use crate::app::post_to_ui;
use crate::screen_reader::announce;

struct ModelBrowser {
    dialog: Dialog,
    catalog: Provider,
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
    let catalog = if venice {
        Provider::Venice
    } else {
        Provider::OpenRouter
    };
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
            .with_label(VENICE_CHECKING_STATUS)
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
        catalog,
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

    /// The filter controls; `provider` resolves the provider choice
    /// against the ids behind it.
    fn filters(&self) -> BrowserFilter {
        let provider_index = self
            .provider_choice
            .get_selection()
            .map_or(0, |i| i as usize);
        BrowserFilter {
            search: self.search_box.get_value(),
            free_only: self.free_only_checkbox.is_checked(),
            price: match self.price_choice.and_then(|c| c.get_selection()) {
                Some(1) => PriceFilter::Free,
                Some(2) => PriceFilter::Paid,
                _ => PriceFilter::All,
            },
            function_calling_only: self.function_checkbox.is_some_and(|c| c.is_checked()),
            provider: provider_index
                .checked_sub(1)
                .and_then(|i| self.providers.borrow().get(i).cloned()),
        }
    }

    /// `_on_filter_changed`.
    fn on_filter_changed(&self, free_only_changed: bool) {
        if free_only_changed || self.catalog == Provider::Venice {
            self.update_provider_list();
        }
        self.apply_filters();
        announce(&self.status_label.get_label());
    }

    /// `_update_provider_list`, keeping the chosen provider when it remains.
    fn update_provider_list(&self) {
        let providers =
            models::provider_ids(self.catalog, &self.all_models.borrow(), &self.filters());
        let current = self.provider_choice.get_string_selection();
        self.provider_choice.clear();
        self.provider_choice.append("All Providers");
        let names: Vec<String> = providers
            .iter()
            .map(|p| models::provider_display_name(p))
            .collect();
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
            models::filter_models(self.catalog, &all, &self.filters())
                .into_iter()
                .cloned()
                .collect()
        };
        self.model_list.clear();
        for model in &filtered {
            self.model_list
                .append(&models::list_item(self.catalog, model));
        }
        let total = self.all_models.borrow().len();
        self.status_label
            .set_label(&models::status_text(filtered.len(), total));
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
                    .set_value(&models::description_text(self.catalog, &model));
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
            announce(OFFLINE_MODEL_MESSAGE);
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
            announce(OFFLINE_MODEL_MESSAGE);
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
                VENICE_CHECKING_STATUS
            } else {
                VENICE_NO_KEY_STATUS
            });
        }
        let catalog = self.catalog;
        let api_key = self.api_key.clone();
        std::thread::Builder::new()
            .name("aw-model-catalog".into())
            .spawn(move || {
                let result = models::load_catalog(catalog, api_key.as_deref());
                post_to_ui(move || {
                    if let Some(b) = BROWSER.with(|slot| slot.borrow().clone()) {
                        b.finish_load(generation, result);
                    }
                });
            })
            .expect("spawn model catalog thread");
    }

    /// `_finish_load`.
    fn finish_load(&self, generation: u64, load: CatalogLoad) {
        if self.closed.get() || generation != self.load_generation.get() {
            return;
        }
        self.refresh_btn.enable(true);
        if let Some(label) = self.balance_label {
            label.set_label(&if self.api_key.is_some() {
                models::balance_status(load.balance.as_ref())
            } else {
                VENICE_NO_KEY_STATUS.to_string()
            });
            label.wrap(610);
            self.dialog.layout();
        }
        match load.models {
            Err(message) => self.status_label.set_label(&format!("Error: {message}")),
            Ok(models) => {
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
