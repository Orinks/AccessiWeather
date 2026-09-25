//! Advanced Text Product Lookup. Port of the widgets of
//! `ui/dialogs/advanced_text_product_dialog.py`; the lookup rules are
//! `aw_providers::products::advanced` ([`LookupForm`] + [`lookup`]).

use std::rc::Rc;
use std::sync::Arc;

use aw_core::model::Location;
use aw_providers::products::advanced::{
    self as rules, lookup, LookupForm, DATE_PRESETS, ORDER_CHOICES, SOURCE_CHOICES,
};
use aw_providers::products::ForecastProductService;
use chrono::Utc;
use wxdragon::prelude::*;

use super::{in_background, next_id, register, unregister, Texts, WidgetSpec};

const TITLE: &str = "Advanced Text Product Lookup";
const LOOKING_UP: &str = "Looking up product...";

/// Labelled widgets in creation order (`*`: the value is computed).
pub(super) const WIDGETS: WidgetSpec = &[
    ("StaticText", "Product group:"),
    ("StaticText", "Product:"),
    (
        "StaticText",
        "Custom AFOS product ID (3 to 6 letters/numbers). Only needed when the custom product \
         choice is selected:",
    ),
    ("TextCtrl", "*"),
    ("StaticText", "Office selection for local AFOS products:"),
    (
        "StaticText",
        "Custom local office (3 letters, for example RAH):",
    ),
    ("TextCtrl", "*"),
    ("StaticText", "Maximum products to retrieve:"),
    ("StaticText", "Date lookup preset:"),
    (
        "StaticText",
        "Start date for archive search (UTC). IEM text products are archive-backed, but specific \
         products and offices may start later than 1983:",
    ),
    (
        "StaticText",
        "End date for archive search (UTC). Leave blank to search through now:",
    ),
    (
        "StaticText",
        "Resolved start or valid time in UTC. For SPC/WPC outlooks and SPC watches, this is the \
         valid time:",
    ),
    ("TextCtrl", ""),
    (
        "StaticText",
        "Resolved end time for historical text products in UTC:",
    ),
    ("TextCtrl", ""),
    ("StaticText", "Result order:"),
    ("CheckBox", "Aviation section only for AFD"),
    (
        "StaticText",
        "Issuing center filter (optional 4-character ID, for ambiguous AFOS IDs):",
    ),
    ("TextCtrl", ""),
    (
        "StaticText",
        "WMO header filter (optional 6-character TTAAII, for ambiguous AFOS IDs):",
    ),
    ("TextCtrl", ""),
    ("StaticText", "Lookup source:"),
    ("StaticText", "Lookup results:"),
    ("TextCtrl", "Choose a product and press Lookup."),
    ("Button#OK", "Lookup"),
    ("Button#CLOSE", "Close"),
];

/// `_set_accessibility_metadata`: name and tooltip of each focusable control,
/// in the order of [`AdvancedDialog::focusable`].
pub(super) const ACCESSIBILITY: [(&str, &str); 23] = [
    (
        "Product group",
        "Choose local, point-based, national, or custom text products",
    ),
    (
        "Product",
        "Choose a valid text product for the selected product group",
    ),
    (
        "Custom AFOS product ID",
        "Enter a 3 to 6 character AFOS product ID only when using a custom product",
    ),
    (
        "Office selection",
        "Choose the selected location office, no office, or a custom local office",
    ),
    (
        "Custom local office",
        "Enter a 3-letter local NWS office such as RAH when custom office is selected",
    ),
    (
        "Maximum products to retrieve",
        "Choose from 1 through 25 matching products",
    ),
    (
        "Date lookup preset",
        "Choose latest, recent archive ranges, or custom start and end dates",
    ),
    ("Start year", "Choose the UTC start year for archive search"),
    (
        "Start month",
        "Choose the UTC start month for archive search",
    ),
    ("Start day", "Choose the UTC start day for archive search"),
    ("End year", "Choose the UTC end year for archive search"),
    ("End month", "Choose the UTC end month for archive search"),
    ("End day", "Choose the UTC end day for archive search"),
    (
        "Resolved start or valid time",
        "Generated UTC start time; advanced users may enter a date or ISO timestamp",
    ),
    (
        "Resolved end time",
        "Generated UTC end time; advanced users may enter a date or ISO timestamp",
    ),
    ("Result order", "Choose newest first or oldest first"),
    (
        "Aviation section only for AFD",
        "Limit Area Forecast Discussion results to the aviation section",
    ),
    (
        "Issuing center filter",
        "Optional 4-character issuing center filter, such as KDMX",
    ),
    (
        "WMO header filter",
        "Optional 6-character WMO header filter, such as FXUS63",
    ),
    (
        "Lookup source",
        "Choose NWS history, IEM AFOS, or prefer NWS",
    ),
    ("Lookup results", "Read-only lookup result text"),
    ("Lookup", "Run the selected text product lookup"),
    ("Close", "Close the advanced text product lookup dialog"),
];

struct AdvancedDialog {
    id: u64,
    location: Location,
    service: Arc<ForecastProductService>,
    office_choices: Vec<String>,
    product_category_choice: Choice,
    product_preset_choice: Choice,
    product_input: TextCtrl,
    office_choice: Choice,
    location_input: TextCtrl,
    limit_input: SpinCtrl,
    date_preset_choice: ComboBox,
    start_parts: [Choice; 3],
    end_parts: [Choice; 3],
    start_input: TextCtrl,
    end_input: TextCtrl,
    order_choice: Choice,
    afd_aviation_only: CheckBox,
    center_input: TextCtrl,
    wmo_input: TextCtrl,
    source_choice: Choice,
    result_text: TextCtrl,
    lookup_button: Button,
    close_button: Button,
}

/// `show_advanced_text_product_dialog`: modal, destroyed on close.
pub(crate) fn show_advanced_text_product_dialog(
    parent: &dyn WxWidget,
    location: &Location,
    service: Arc<ForecastProductService>,
    initial_product_type: &str,
) {
    let dialog = Dialog::builder(parent, TITLE)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let mut texts = Texts::new(WIDGETS);
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();
    let form = ScrolledWindow::builder(&dialog)
        .with_style(ScrolledWindowStyle::HScroll | ScrolledWindowStyle::VScroll)
        .build();
    form.set_scroll_rate(0, 20);
    let sizer = BoxSizer::builder(Orientation::Vertical).build();
    let label_flags = SizerFlag::Left | SizerFlag::Right | SizerFlag::Expand;
    let control_flags = SizerFlag::All | SizerFlag::Expand;
    let add_label = |flags: SizerFlag, texts: &mut Texts| {
        let label = StaticText::builder(&form)
            .with_label(texts.next("StaticText"))
            .build();
        sizer.add(&label, 0, flags, 8);
    };
    let choice = |items: Vec<String>| {
        let choice = Choice::builder(&form).with_choices(items).build();
        choice.set_selection(0);
        choice
    };
    let text_input = |value: &str| TextCtrl::builder(&form).with_value(value).build();
    let strings = |items: &[&str]| items.iter().map(|s| s.to_string()).collect::<Vec<_>>();

    add_label(label_flags | SizerFlag::Top, &mut texts);
    let product_category_choice = choice(strings(&rules::product_categories()));
    sizer.add(&product_category_choice, 0, control_flags, 8);

    add_label(label_flags | SizerFlag::Top, &mut texts);
    let product_preset_choice = choice(strings(&rules::preset_labels_for_category("Custom")));
    sizer.add(&product_preset_choice, 0, control_flags, 8);

    add_label(label_flags | SizerFlag::Top, &mut texts);
    texts.next("TextCtrl");
    let product_input = text_input(initial_product_type);
    sizer.add(&product_input, 0, control_flags, 8);

    let cwa_office = location.cwa_office.clone().unwrap_or_default();
    add_label(label_flags, &mut texts);
    let office_choices = rules::office_choices(location);
    let office_choice = choice(office_choices.clone());
    sizer.add(&office_choice, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    texts.next("TextCtrl");
    let location_input = text_input(&cwa_office);
    sizer.add(&location_input, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let limit_input = SpinCtrl::builder(&form)
        .with_range(1, 25)
        .with_initial_value(1)
        .build();
    sizer.add(&limit_input, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let date_preset_choice = ComboBox::builder(&form)
        .with_string_choices(&DATE_PRESETS)
        .with_style(ComboBoxStyle::ReadOnly)
        .build();
    date_preset_choice.set_selection(0);
    sizer.add(&date_preset_choice, 0, control_flags, 8);

    let years = rules::year_choices(Utc::now());
    let date_row = |texts: &mut Texts| {
        add_label(label_flags, texts);
        let row = BoxSizer::builder(Orientation::Horizontal).build();
        let parts = [
            choice(years.clone()),
            choice(rules::month_choices()),
            choice(rules::day_choices()),
        ];
        row.add(&parts[0], 1, SizerFlag::Right, 8);
        row.add(&parts[1], 1, SizerFlag::Right, 8);
        row.add(&parts[2], 1, SizerFlag::empty(), 0);
        sizer.add_sizer(&row, 0, control_flags, 8);
        parts
    };
    let start_parts = date_row(&mut texts);
    let end_parts = date_row(&mut texts);

    add_label(label_flags, &mut texts);
    let start_input = text_input(texts.next("TextCtrl"));
    sizer.add(&start_input, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let end_input = text_input(texts.next("TextCtrl"));
    sizer.add(&end_input, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let order_choice = choice(strings(&ORDER_CHOICES));
    sizer.add(&order_choice, 0, control_flags, 8);

    let afd_aviation_only = CheckBox::builder(&form)
        .with_label(texts.next("CheckBox"))
        .build();
    sizer.add(&afd_aviation_only, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let center_input = text_input(texts.next("TextCtrl"));
    sizer.add(&center_input, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let wmo_input = text_input(texts.next("TextCtrl"));
    sizer.add(&wmo_input, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let source_choice = choice(strings(&SOURCE_CHOICES));
    sizer.add(&source_choice, 0, control_flags, 8);

    add_label(label_flags, &mut texts);
    let result_text = TextCtrl::builder(&form)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::DontWrap)
        .with_value(texts.next("TextCtrl"))
        .build();
    sizer.add(&result_text, 1, control_flags, 8);

    form.set_sizer(sizer, true);
    main_sizer.add(&form, 1, SizerFlag::All | SizerFlag::Expand, 0);

    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let lookup_button = Button::builder(&dialog)
        .with_id(ID_OK)
        .with_label(texts.next("Button#OK"))
        .build();
    let close_button = Button::builder(&dialog)
        .with_id(ID_CLOSE)
        .with_label(texts.next("Button#CLOSE"))
        .build();
    button_sizer.add_stretch_spacer(1);
    button_sizer.add(&lookup_button, 0, SizerFlag::Right, 8);
    button_sizer.add(&close_button, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&button_sizer, 0, SizerFlag::All | SizerFlag::Expand, 8);
    dialog.set_sizer(main_sizer, true);

    let d = Rc::new(AdvancedDialog {
        id: next_id(),
        location: location.clone(),
        service,
        office_choices,
        product_category_choice,
        product_preset_choice,
        product_input,
        office_choice,
        location_input,
        limit_input,
        date_preset_choice,
        start_parts,
        end_parts,
        start_input,
        end_input,
        order_choice,
        afd_aviation_only,
        center_input,
        wmo_input,
        source_choice,
        result_text,
        lookup_button,
        close_button,
    });
    for (control, (name, tooltip)) in d.focusable().iter().zip(ACCESSIBILITY) {
        control.set_name(name);
        control.set_tooltip(tooltip);
    }
    register(d.id, d.clone());

    {
        let id = d.id;
        let with = move |f: fn(&AdvancedDialog)| {
            move || {
                if let Some(d) = super::lookup::<AdvancedDialog>(id) {
                    f(&d);
                }
            }
        };
        let handler = with(AdvancedDialog::on_product_category);
        product_category_choice.on_selection_changed(move |_| handler());
        let handler = with(AdvancedDialog::on_product_preset);
        product_preset_choice.on_selection_changed(move |_| handler());
        // Python binds the date presets with EVT_CHOICE, which a ComboBox
        // never sends, so choosing a preset changes nothing. Kept for parity.
        for part in start_parts.iter().chain(&end_parts) {
            let handler = with(AdvancedDialog::on_date_parts);
            part.on_selection_changed(move |_| handler());
        }
        let handler = with(AdvancedDialog::on_lookup);
        lookup_button.on_click(move |e| {
            e.event.skip(false);
            handler();
        });
        close_button.on_click(move |e| {
            e.event.skip(false);
            dialog.end_modal(ID_CLOSE);
        });
        dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
            if e.get_key_code() == Some(WXK_ESCAPE) {
                e.skip(false);
                dialog.end_modal(ID_CLOSE);
            } else {
                e.skip(true);
            }
        });
    }

    dialog.set_size(Size::new(760, 620));
    dialog.centre();
    dialog.show_modal();
    unregister(d.id);
    dialog.destroy();
}

fn selection(choice: &Choice) -> String {
    choice.get_string_selection().unwrap_or_default()
}

impl AdvancedDialog {
    /// `_focusable_controls`.
    fn focusable(&self) -> [&dyn WxWidget; 23] {
        [
            &self.product_category_choice,
            &self.product_preset_choice,
            &self.product_input,
            &self.office_choice,
            &self.location_input,
            &self.limit_input,
            &self.date_preset_choice,
            &self.start_parts[0],
            &self.start_parts[1],
            &self.start_parts[2],
            &self.end_parts[0],
            &self.end_parts[1],
            &self.end_parts[2],
            &self.start_input,
            &self.end_input,
            &self.order_choice,
            &self.afd_aviation_only,
            &self.center_input,
            &self.wmo_input,
            &self.source_choice,
            &self.result_text,
            &self.lookup_button,
            &self.close_button,
        ]
    }

    /// A product group was chosen: list its products and apply the first.
    fn on_product_category(&self) {
        let category = selection(&self.product_category_choice);
        let category = if category.is_empty() {
            "Custom"
        } else {
            category.as_str()
        };
        self.product_preset_choice.clear();
        for label in rules::preset_labels_for_category(category) {
            self.product_preset_choice.append(label);
        }
        self.product_preset_choice.set_selection(0);
        self.apply_product_preset(rules::category_default_preset(category));
    }

    fn on_product_preset(&self) {
        self.apply_product_preset(&selection(&self.product_preset_choice));
    }

    fn apply_product_preset(&self, label: &str) {
        let Some(change) = rules::apply_product_preset(label) else {
            return;
        };
        self.product_input.set_value(change.product);
        if let Some(index) = change.source_index {
            self.source_choice.set_selection(index as u32);
        }
        if let Some(index) = change
            .office_choice
            .and_then(|office| rules::find_choice(&self.office_choices, office))
        {
            self.office_choice.set_selection(index as u32);
        }
    }

    /// Year/month/day choices resolve into the UTC start and end fields.
    fn on_date_parts(&self) {
        let parts = |choices: &[Choice; 3]| {
            let [year, month, day] = choices.each_ref().map(selection);
            rules::date_from_choice_parts(&year, &month, &day)
        };
        let (Ok(start), Ok(end)) = (parts(&self.start_parts), parts(&self.end_parts)) else {
            return;
        };
        let text = |value: Option<_>| {
            value
                .as_ref()
                .map(rules::format_form_datetime)
                .unwrap_or_default()
        };
        self.start_input.set_value(&text(start));
        self.end_input.set_value(&text(end));
    }

    fn form(&self) -> LookupForm {
        let parts = |choices: &[Choice; 3]| choices.each_ref().map(selection);
        LookupForm {
            product: self.product_input.get_value(),
            office_choice: selection(&self.office_choice),
            custom_office: self.location_input.get_value(),
            limit: self.limit_input.value().to_string(),
            source: selection(&self.source_choice),
            order: selection(&self.order_choice),
            aviation_afd: self.afd_aviation_only.is_checked(),
            center: self.center_input.get_value(),
            wmo_id: self.wmo_input.get_value(),
            start_parts: parts(&self.start_parts),
            end_parts: parts(&self.end_parts),
            start_text: self.start_input.get_value(),
            end_text: self.end_input.get_value(),
        }
    }

    fn on_lookup(&self) {
        self.result_text.set_value(LOOKING_UP);
        let form = self.form();
        let service = self.service.clone();
        let location = self.location.clone();
        in_background(
            self.id,
            move || lookup(&service, &location, &form),
            |d: &Rc<AdvancedDialog>, text| d.result_text.set_value(&text),
        );
    }
}
