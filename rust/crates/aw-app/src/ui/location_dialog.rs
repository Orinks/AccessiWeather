//! Add Location, Edit Location and Reorder Saved Locations dialogs, ported
//! from `ui/dialogs/location_dialog.py`.

use std::cell::{Cell, RefCell};
use std::rc::Rc;

use aw_core::Location;
use wxdragon::prelude::*;

use super::main_window::{self as mw, message_box};
use super::weather_source::{
    calculate_distance, detect_current_location, format_coordinates, search_locations,
    validate_coordinates,
};
use crate::app::{post_to_ui, save, with_state};

const MARINE_LABEL: &str = "Enable Marine Mode for this location (coastal essentials only)";
const MARINE_TOOLTIP: &str =
    "Adds nearby NWS marine zone summary, wind and wave highlights, and marine advisories.";
const NAME_HINT: &str = "Enter a descriptive name for this location";
const ZONE_NOT_RESOLVED: &str = "Not yet resolved - will populate after next weather refresh";

/// `wx.TextCtrl.SetHint`: wxDragon lacks it, so send the cue banner the way
/// wxMSW does. Elsewhere the hint is skipped.
#[cfg(windows)]
fn set_hint(ctrl: &TextCtrl, hint: &str) {
    #[link(name = "user32")]
    extern "system" {
        fn SendMessageW(
            hwnd: *mut std::ffi::c_void,
            msg: u32,
            wparam: usize,
            lparam: isize,
        ) -> isize;
    }
    const EM_SETCUEBANNER: u32 = 0x1501;
    let wide: Vec<u16> = hint.encode_utf16().chain(Some(0)).collect();
    // SAFETY: a valid edit HWND and a NUL-terminated UTF-16 string that
    // outlives the synchronous call.
    unsafe {
        SendMessageW(
            ctrl.get_handle(),
            EM_SETCUEBANNER,
            1,
            wide.as_ptr() as isize,
        );
    }
}

#[cfg(not(windows))]
fn set_hint(_ctrl: &TextCtrl, _hint: &str) {}

fn text_colour(ctrl: &StaticText, is_error: bool) {
    ctrl.set_foreground_color(SystemSettings::get_colour(if is_error {
        SystemColour::GrayText
    } else {
        SystemColour::WindowText
    }));
}

fn label<W: WxWidget>(parent: &W, text: &str) -> StaticText {
    StaticText::builder(parent).with_label(text).build()
}

fn results_list<W: WxWidget>(parent: &W, first_column: (&str, i32), second_width: i32) -> ListCtrl {
    let list = ListCtrl::builder(parent)
        .with_style(ListCtrlStyle::Report | ListCtrlStyle::SingleSel)
        .build();
    list.insert_column(0, first_column.0, ListColumnFormat::Left, first_column.1);
    list.insert_column(1, "Coordinates", ListColumnFormat::Left, second_width);
    list
}

fn fill_results(list: &ListCtrl, locations: &[Location]) {
    for location in locations {
        let index = list.insert_item(list.get_item_count() as i64, &location.name, None);
        list.set_item_text_by_column(
            index as i64,
            1,
            &format_coordinates(location.latitude, location.longitude),
        );
    }
}

/// Runs `work` on a worker thread with the app's HTTP client, then `done`
/// with its result on the UI thread.
fn in_background<T: Send + 'static>(
    work: impl FnOnce(&dyn aw_providers::HttpClient) -> T + Send + 'static,
    done: impl FnOnce(T) + Send + 'static,
) {
    let Some(state) = with_state() else { return };
    let client = state.borrow().client.clone();
    std::thread::Builder::new()
        .name("aw-location".into())
        .spawn(move || {
            let result = work(client.http());
            post_to_ui(move || done(result));
        })
        .expect("spawn location thread");
}

fn existing_names() -> Vec<String> {
    with_state()
        .map(|s| s.borrow().config.location_names())
        .unwrap_or_default()
}

// ---------------------------------------------------------------------------
// Add Location
// ---------------------------------------------------------------------------

struct AddLocationDialog {
    dialog: Dialog,
    name_input: TextCtrl,
    marine_mode_checkbox: CheckBox,
    search_input: TextCtrl,
    search_button: Button,
    current_location_button: Button,
    results_list: ListCtrl,
    status_label: StaticText,
    search_results: RefCell<Vec<Location>>,
    selected_location: RefCell<Option<Location>>,
    is_searching: Cell<bool>,
    is_detecting_current_location: Cell<bool>,
    added_location: RefCell<Option<String>>,
}

thread_local! {
    /// The open Add dialog; background results for a closed one are dropped.
    static ADD_DIALOG: RefCell<Option<Rc<AddLocationDialog>>> = const { RefCell::new(None) };
    static EDIT_DIALOG: RefCell<Option<Rc<EditLocationDialog>>> = const { RefCell::new(None) };
}

fn open_add_dialog() -> Option<Rc<AddLocationDialog>> {
    ADD_DIALOG.with(|d| d.borrow().clone())
}

/// `show_add_location_dialog`: the name of the added location, if any.
pub(crate) fn show_add_location_dialog(parent: &Frame) -> Option<String> {
    let dialog = Dialog::builder(parent, "Add Location")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(600, 500)
        .build();
    let panel = Panel::builder(&dialog).build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();

    let title = label(&panel, "Add New Location");
    if let Some(mut font) = title.get_font() {
        font.make_bold();
        title.set_font(&font);
    }
    main_sizer.add(&title, 0, SizerFlag::All, 10);

    let name_sizer = BoxSizer::builder(Orientation::Vertical).build();
    name_sizer.add(&label(&panel, "Location Name:"), 0, SizerFlag::Bottom, 5);
    let name_input = TextCtrl::builder(&panel)
        .with_size(Size::new(400, -1))
        .build();
    set_hint(&name_input, NAME_HINT);
    name_sizer.add(&name_input, 0, SizerFlag::Expand, 0);
    let help_text = label(&panel, "This name will appear in your location list");
    text_colour(&help_text, true);
    name_sizer.add(&help_text, 0, SizerFlag::Top, 5);
    let marine_mode_checkbox = CheckBox::builder(&panel).with_label(MARINE_LABEL).build();
    marine_mode_checkbox.set_tooltip(MARINE_TOOLTIP);
    name_sizer.add(&marine_mode_checkbox, 0, SizerFlag::Top, 8);
    main_sizer.add_sizer(&name_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);

    let search_sizer = BoxSizer::builder(Orientation::Vertical).build();
    search_sizer.add(
        &label(
            &panel,
            "Search for Location (city, ZIP/postal code, or US address):",
        ),
        0,
        SizerFlag::Bottom,
        5,
    );
    let search_row = BoxSizer::builder(Orientation::Horizontal).build();
    let search_input = TextCtrl::builder(&panel)
        .with_style(TextCtrlStyle::ProcessEnter)
        .build();
    set_hint(&search_input, "City, ZIP/postal code, or US street address");
    search_row.add(&search_input, 1, SizerFlag::Right, 10);
    let search_button = Button::builder(&panel).with_label("Search").build();
    search_row.add(&search_button, 0, SizerFlag::empty(), 0);
    search_sizer.add_sizer(&search_row, 0, SizerFlag::Expand, 0);
    let current_location_button = Button::builder(&panel)
        .with_label("Use my current location")
        .build();
    current_location_button.set_tooltip(
        "Ask the operating system once for your current coordinates. \
         Manual search stays available if this is unavailable or denied.",
    );
    search_sizer.add(&current_location_button, 0, SizerFlag::Top, 8);
    let search_help = label(
        &panel,
        "Examples: 'London', 'New York', '10001', or '123 Main St, Carrollton, TX'",
    );
    text_colour(&search_help, true);
    search_sizer.add(&search_help, 0, SizerFlag::Top, 5);
    main_sizer.add_sizer(&search_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);

    main_sizer.add(
        &label(&panel, "Search Results:"),
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );
    let results = results_list(&panel, ("Location", 300), 200);
    main_sizer.add(&results, 1, SizerFlag::Expand | SizerFlag::All, 10);

    let status_label = label(&panel, "Ready to add location");
    text_colour(&status_label, true);
    main_sizer.add(&status_label, 0, SizerFlag::Left | SizerFlag::Right, 10);

    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    button_sizer.add_stretch_spacer(1);
    let save_button = Button::builder(&panel)
        .with_id(ID_OK)
        .with_label("Save Location")
        .build();
    button_sizer.add(&save_button, 0, SizerFlag::Right, 10);
    let cancel_button = Button::builder(&panel)
        .with_id(ID_CANCEL)
        .with_label("Cancel")
        .build();
    button_sizer.add(&cancel_button, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&button_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);
    panel.set_sizer(main_sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);
    name_input.set_focus();

    // `_setup_accessibility`.
    name_input.set_name("Location name input");
    search_input.set_name("Search for location");
    results.set_name("Search results");
    marine_mode_checkbox.set_name("Enable Marine Mode for this location");
    current_location_button.set_name("Use my current location");

    let d = Rc::new(AddLocationDialog {
        dialog,
        name_input,
        marine_mode_checkbox,
        search_input,
        search_button,
        current_location_button,
        results_list: results,
        status_label,
        search_results: RefCell::new(Vec::new()),
        selected_location: RefCell::new(None),
        is_searching: Cell::new(false),
        is_detecting_current_location: Cell::new(false),
        added_location: RefCell::new(None),
    });
    {
        let d2 = d.clone();
        search_input.on_text_enter(move |_| d2.on_search());
        let d2 = d.clone();
        search_button.on_click(move |_| d2.on_search());
        let d2 = d.clone();
        current_location_button.on_click(move |_| d2.on_use_current_location());
        let d2 = d.clone();
        results.on_item_selected(move |e| d2.on_result_selected(e.get_item_index()));
        let d2 = d.clone();
        results.on_item_activated(move |e| {
            d2.on_result_selected(e.get_item_index());
            d2.on_save();
        });
        let d2 = d.clone();
        save_button.on_click(move |e| {
            e.event.skip(false);
            d2.on_save();
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

    ADD_DIALOG.with(|slot| *slot.borrow_mut() = Some(d.clone()));
    let result = dialog.show_modal();
    ADD_DIALOG.with(|slot| slot.borrow_mut().take());
    let added = d.added_location.borrow_mut().take();
    dialog.destroy();
    (result == ID_OK).then_some(added).flatten()
}

impl AddLocationDialog {
    fn update_status(&self, message: &str, is_error: bool) {
        self.status_label.set_label(message);
        text_colour(&self.status_label, is_error);
        tracing::info!("Location dialog status: {message}");
    }

    fn on_search(&self) {
        let query = self.search_input.get_value().trim().to_string();
        if query.is_empty() {
            self.update_status("Please enter a search term", true);
            return;
        }
        if self.is_searching.get() {
            self.update_status("Search already in progress...", true);
            return;
        }
        self.is_searching.set(true);
        self.search_button.enable(false);
        self.update_status(&format!("Searching for '{query}'..."), false);
        self.results_list.delete_all_items();
        self.search_results.borrow_mut().clear();
        in_background(
            move |http| search_locations(http, &query, 10),
            |result| {
                if let Some(d) = open_add_dialog() {
                    d.on_search_complete(result);
                }
            },
        );
    }

    fn on_search_complete(&self, result: Result<Vec<Location>, String>) {
        self.is_searching.set(false);
        self.search_button.enable(true);
        match result {
            Err(error) => {
                tracing::error!("Search failed: {error}");
                self.update_status(&format!("Search failed: {error}"), true);
            }
            Ok(locations) if locations.is_empty() => {
                self.update_status("No locations found. Try a different search term.", true);
            }
            Ok(locations) => {
                fill_results(&self.results_list, &locations);
                self.update_status(&format!("Found {} locations", locations.len()), false);
                if self.name_input.get_value().trim().is_empty() {
                    self.name_input.set_value(&locations[0].name);
                }
                *self.search_results.borrow_mut() = locations;
            }
        }
    }

    fn on_use_current_location(&self) {
        if self.is_detecting_current_location.get() {
            self.update_status("Current location detection is already in progress.", true);
            return;
        }
        self.is_detecting_current_location.set(true);
        self.current_location_button.enable(false);
        self.update_status(
            "Requesting current location. Your system may ask for permission now...",
            false,
        );
        in_background(detect_current_location, |result| {
            let Some(d) = open_add_dialog() else { return };
            d.is_detecting_current_location.set(false);
            d.current_location_button.enable(true);
            match result {
                Ok(location) => d.apply_detected_location(location),
                Err(message) => d.update_status(&message, true),
            }
        });
    }

    fn apply_detected_location(&self, location: Location) {
        self.results_list.delete_all_items();
        fill_results(&self.results_list, std::slice::from_ref(&location));
        if self.name_input.get_value().trim().is_empty() {
            self.name_input.set_value(&location.name);
        }
        *self.search_results.borrow_mut() = vec![location.clone()];
        *self.selected_location.borrow_mut() = Some(location);
        self.update_status(
            "Detected current location. Review the editable name, then save it.",
            false,
        );
    }

    fn on_result_selected(&self, index: i32) {
        let Some(location) = usize::try_from(index)
            .ok()
            .and_then(|i| self.search_results.borrow().get(i).cloned())
        else {
            return;
        };
        self.name_input.set_value(&location.name);
        self.update_status(&format!("Selected: {}", location.name), false);
        *self.selected_location.borrow_mut() = Some(location);
    }

    fn on_save(&self) {
        let name = self.name_input.get_value().trim().to_string();
        if name.is_empty() {
            self.update_status("Please enter a location name", true);
            return;
        }
        let Some(selected) = self.selected_location.borrow().clone() else {
            self.update_status("Please search for and select a location", true);
            return;
        };
        if !validate_coordinates(selected.latitude, selected.longitude) {
            self.update_status(
                "Invalid coordinates. Latitude must be -90 to 90, longitude -180 to 180",
                true,
            );
            return;
        }
        if existing_names().contains(&name) {
            self.update_status("A location with this name already exists", true);
            return;
        }
        let mut location = Location::new(name.clone(), selected.latitude, selected.longitude);
        location.country_code = selected.country_code;
        location.marine_mode = self.marine_mode_checkbox.is_checked();
        let success = with_state().is_some_and(|state| {
            let mut st = state.borrow_mut();
            st.config.add_location(location) && save(&st).is_ok()
        });
        if success {
            *self.added_location.borrow_mut() = Some(name);
            self.update_status("Location saved successfully!", false);
            self.dialog.end_modal(ID_OK);
        } else {
            self.update_status("Failed to save location", true);
        }
    }
}

// ---------------------------------------------------------------------------
// Edit Location
// ---------------------------------------------------------------------------

/// `EditLocationResult`.
pub(crate) struct EditLocationResult {
    pub display_name: String,
    pub latitude: f64,
    pub longitude: f64,
    pub country_code: Option<String>,
    pub marine_mode: bool,
}

/// `_edit_location_is_us`: country code first, then plain US bounding boxes
/// (looser than `aw_core::is_us_location`, as in Python).
pub(crate) fn edit_location_is_us(location: &Location) -> bool {
    if let Some(code) = location.country_code.as_deref().filter(|c| !c.is_empty()) {
        return code.eq_ignore_ascii_case("US");
    }
    let (lat, lon) = (location.latitude, location.longitude);
    let continental = (24.0..=49.0).contains(&lat) && (-125.0..=-66.0).contains(&lon);
    let alaska = (51.0..=71.5).contains(&lat) && (-172.0..=-130.0).contains(&lon);
    let hawaii = (18.0..=23.0).contains(&lat) && (-161.0..=-154.0).contains(&lon);
    continental || alaska || hawaii
}

struct EditLocationDialog {
    dialog: Dialog,
    location: Location,
    name_input: TextCtrl,
    marine_checkbox: CheckBox,
    address_input: TextCtrl,
    address_search_button: Button,
    current_location_button: Button,
    address_results_list: ListCtrl,
    coordinate_comparison_label: StaticText,
    search_results: RefCell<Vec<Location>>,
    selected_location: RefCell<Option<Location>>,
    is_searching: Cell<bool>,
    is_detecting_current_location: Cell<bool>,
}

fn open_edit_dialog() -> Option<Rc<EditLocationDialog>> {
    EDIT_DIALOG.with(|d| d.borrow().clone())
}

/// `show_edit_location_dialog`.
pub(crate) fn show_edit_location_dialog(
    parent: &Frame,
    location: &Location,
) -> Option<EditLocationResult> {
    let dialog = Dialog::builder(parent, &format!("Edit Location: {}", location.name))
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();

    let name_sizer = BoxSizer::builder(Orientation::Vertical).build();
    name_sizer.add(&label(&panel, "Location Name:"), 0, SizerFlag::Bottom, 5);
    let name_input = TextCtrl::builder(&panel)
        .with_value(&location.name)
        .with_size(Size::new(400, -1))
        .build();
    set_hint(&name_input, NAME_HINT);
    name_input.set_name("Location name input");
    name_sizer.add(&name_input, 0, SizerFlag::Expand, 0);
    sizer.add_sizer(&name_sizer, 0, SizerFlag::All | SizerFlag::Expand, 10);

    let current_coordinates = label(
        &panel,
        &format!(
            "Current coordinates: {}",
            format_coordinates(location.latitude, location.longitude)
        ),
    );
    sizer.add(
        &current_coordinates,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );

    let marine_checkbox = CheckBox::builder(&panel)
        .with_label(MARINE_LABEL)
        .with_value(location.marine_mode)
        .build();
    marine_checkbox.set_tooltip(MARINE_TOOLTIP);
    marine_checkbox.set_name("Enable Marine Mode for this location");
    sizer.add(&marine_checkbox, 0, SizerFlag::All | SizerFlag::Expand, 10);

    let address_box = StaticBox::builder(&panel)
        .with_label("Update Coordinates from Address")
        .build();
    let address_sizer =
        StaticBoxSizerBuilder::new_with_box(&address_box, Orientation::Vertical).build();
    address_sizer.add(
        &label(
            &address_box,
            "Search for a US street address to update this saved location:",
        ),
        0,
        SizerFlag::All,
        5,
    );
    let search_row = BoxSizer::builder(Orientation::Horizontal).build();
    let address_input = TextCtrl::builder(&address_box)
        .with_style(TextCtrlStyle::ProcessEnter)
        .build();
    set_hint(&address_input, "Street address, city, state, and ZIP");
    address_input.set_name("Address lookup for saved location coordinates");
    search_row.add(&address_input, 1, SizerFlag::Right, 8);
    let address_search_button = Button::builder(&address_box).with_label("Search").build();
    search_row.add(&address_search_button, 0, SizerFlag::empty(), 0);
    address_sizer.add_sizer(&search_row, 0, SizerFlag::Expand | SizerFlag::All, 5);
    let current_location_button = Button::builder(&address_box)
        .with_label("Use my current location")
        .build();
    current_location_button.set_tooltip(
        "Ask the operating system once for your current coordinates. \
         The existing coordinates stay available if this is unavailable or denied.",
    );
    current_location_button.set_name("Use my current location for this saved location");
    address_sizer.add(
        &current_location_button,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        5,
    );
    let address_results_list = results_list(&address_box, ("Matched Address", 320), 180);
    address_results_list.set_min_size(Size::new(-1, 110));
    address_results_list.set_name("Address lookup results");
    address_sizer.add(
        &address_results_list,
        0,
        SizerFlag::Expand | SizerFlag::All,
        5,
    );
    let coordinate_comparison_label = label(
        &address_box,
        "No address selected. Existing coordinates will be kept.",
    );
    coordinate_comparison_label.set_name("Coordinate comparison");
    address_sizer.add(&coordinate_comparison_label, 0, SizerFlag::All, 5);
    sizer.add_sizer(&address_sizer, 0, SizerFlag::Expand | SizerFlag::All, 10);

    // NWS zone information, a snapshot taken when the dialog opens.
    let zone_box = StaticBox::builder(&panel)
        .with_label("NWS Zone Information")
        .build();
    let zone_sizer = StaticBoxSizerBuilder::new_with_box(&zone_box, Orientation::Vertical).build();
    let zone_text = |field: &Option<String>| {
        field
            .as_deref()
            .filter(|s| !s.is_empty())
            .unwrap_or(ZONE_NOT_RESOLVED)
            .to_string()
    };
    let forecast_zone = label(
        &zone_box,
        &format!("Forecast Zone: {}", zone_text(&location.forecast_zone_id)),
    );
    let office = label(
        &zone_box,
        &format!("NWS Office: {}", zone_text(&location.cwa_office)),
    );
    zone_sizer.add(&forecast_zone, 0, SizerFlag::All, 5);
    zone_sizer.add(&office, 0, SizerFlag::All, 5);
    sizer.add_sizer(&zone_sizer, 0, SizerFlag::All | SizerFlag::Expand, 10);
    if !edit_location_is_us(location) {
        zone_box.show(false);
    }

    let button_sizer = StdDialogButtonSizerBuilder::new().build();
    let ok_button = Button::builder(&panel)
        .with_id(ID_OK)
        .with_label("&Save")
        .build();
    let cancel_button = Button::builder(&panel)
        .with_id(ID_CANCEL)
        .with_label("Cancel")
        .build();
    button_sizer.add_button(&ok_button);
    button_sizer.add_button(&cancel_button);
    button_sizer.realize();
    sizer.add_sizer(&button_sizer, 0, SizerFlag::All | SizerFlag::AlignRight, 10);

    panel.set_sizer(sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);
    ok_button.set_default();
    dialog.set_min_size(Size::new(640, -1));
    dialog.fit();

    let d = Rc::new(EditLocationDialog {
        dialog,
        location: location.clone(),
        name_input,
        marine_checkbox,
        address_input,
        address_search_button,
        current_location_button,
        address_results_list,
        coordinate_comparison_label,
        search_results: RefCell::new(Vec::new()),
        selected_location: RefCell::new(None),
        is_searching: Cell::new(false),
        is_detecting_current_location: Cell::new(false),
    });
    {
        let d2 = d.clone();
        address_input.on_text_enter(move |_| d2.on_address_search());
        let d2 = d.clone();
        address_search_button.on_click(move |_| d2.on_address_search());
        let d2 = d.clone();
        current_location_button.on_click(move |_| d2.on_use_current_location());
        let d2 = d.clone();
        address_results_list.on_item_selected(move |e| d2.on_address_selected(e.get_item_index()));
        let d2 = d.clone();
        ok_button.on_click(move |e| {
            e.event.skip(false);
            d2.on_save();
        });
    }

    EDIT_DIALOG.with(|slot| *slot.borrow_mut() = Some(d.clone()));
    let result = dialog.show_modal();
    EDIT_DIALOG.with(|slot| slot.borrow_mut().take());
    let value = (result == ID_OK).then(|| d.get_result());
    dialog.destroy();
    value
}

impl EditLocationDialog {
    fn set_coordinate_comparison(&self, message: &str, is_error: bool) {
        self.coordinate_comparison_label.set_label(message);
        text_colour(&self.coordinate_comparison_label, is_error);
        self.coordinate_comparison_label.wrap(580);
        self.dialog.layout();
        self.dialog.fit();
    }

    fn on_address_search(&self) {
        let query = self.address_input.get_value().trim().to_string();
        if query.is_empty() {
            self.set_coordinate_comparison("Enter an address to search.", true);
            return;
        }
        if self.is_searching.get() {
            self.set_coordinate_comparison("Search already in progress.", true);
            return;
        }
        self.is_searching.set(true);
        self.address_search_button.enable(false);
        self.set_coordinate_comparison(&format!("Searching for '{query}'..."), false);
        self.address_results_list.delete_all_items();
        self.search_results.borrow_mut().clear();
        *self.selected_location.borrow_mut() = None;
        in_background(
            move |http| search_locations(http, &query, 5),
            |result| {
                if let Some(d) = open_edit_dialog() {
                    d.on_address_search_complete(result);
                }
            },
        );
    }

    fn on_address_search_complete(&self, result: Result<Vec<Location>, String>) {
        self.is_searching.set(false);
        self.address_search_button.enable(true);
        match result {
            Err(error) => {
                tracing::error!("Address lookup failed: {error}");
                self.set_coordinate_comparison(&format!("Address search failed: {error}"), true);
            }
            Ok(locations) if locations.is_empty() => {
                self.set_coordinate_comparison("No address matches found.", true);
            }
            Ok(locations) => {
                fill_results(&self.address_results_list, &locations);
                let count = locations.len();
                *self.search_results.borrow_mut() = locations;
                self.set_coordinate_comparison(
                    &format!("Found {count} matches. Select one to compare coordinates."),
                    false,
                );
            }
        }
    }

    fn on_use_current_location(&self) {
        if self.is_detecting_current_location.get() {
            self.set_coordinate_comparison(
                "Current location detection is already in progress.",
                true,
            );
            return;
        }
        self.is_detecting_current_location.set(true);
        self.current_location_button.enable(false);
        self.set_coordinate_comparison(
            "Requesting current location. Your system may ask for permission now...",
            false,
        );
        in_background(detect_current_location, |result| {
            let Some(d) = open_edit_dialog() else { return };
            d.is_detecting_current_location.set(false);
            d.current_location_button.enable(true);
            match result {
                Ok(location) => d.on_current_location_detected(location),
                Err(message) => d.set_coordinate_comparison(&message, true),
            }
        });
    }

    fn on_current_location_detected(&self, location: Location) {
        self.address_results_list.delete_all_items();
        fill_results(&self.address_results_list, std::slice::from_ref(&location));
        self.name_input.set_value(&location.name);
        let coords = format_coordinates(location.latitude, location.longitude);
        let distance = calculate_distance(&self.location, &location);
        self.set_coordinate_comparison(
            &format!(
                "Detected current location as {}: {coords}. \
                 Difference from saved coordinates: {distance:.2} miles. \
                 Review the editable name, then save it.",
                location.name
            ),
            false,
        );
        *self.search_results.borrow_mut() = vec![location.clone()];
        *self.selected_location.borrow_mut() = Some(location);
    }

    fn on_address_selected(&self, index: i32) {
        let Some(selected) = usize::try_from(index)
            .ok()
            .and_then(|i| self.search_results.borrow().get(i).cloned())
        else {
            return;
        };
        let distance = calculate_distance(&self.location, &selected);
        let current = format_coordinates(self.location.latitude, self.location.longitude);
        let new = format_coordinates(selected.latitude, selected.longitude);
        self.name_input.set_value(&selected.name);
        self.set_coordinate_comparison(
            &format!("Current: {current}. New: {new}. Difference: {distance:.2} miles."),
            false,
        );
        *self.selected_location.borrow_mut() = Some(selected);
    }

    /// `_on_save`: reject an empty or duplicate name out loud.
    fn on_save(&self) {
        let new_name = self.name_input.get_value().trim().to_string();
        if new_name.is_empty() {
            message_box(
                &self.dialog,
                "Please enter a location name.",
                "Location Name Required",
                MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
            );
            self.name_input.set_focus();
            return;
        }
        if new_name != self.location.name && existing_names().contains(&new_name) {
            message_box(
                &self.dialog,
                &format!(
                    "A location named '{new_name}' already exists. Please choose a different name."
                ),
                "Duplicate Location Name",
                MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
            );
            self.name_input.set_focus();
            return;
        }
        self.dialog.end_modal(ID_OK);
    }

    fn get_result(&self) -> EditLocationResult {
        let selected = self.selected_location.borrow();
        let source = selected.as_ref().unwrap_or(&self.location);
        EditLocationResult {
            display_name: self.name_input.get_value().trim().to_string(),
            latitude: source.latitude,
            longitude: source.longitude,
            country_code: source.country_code.clone(),
            marine_mode: self.marine_checkbox.is_checked(),
        }
    }
}

// ---------------------------------------------------------------------------
// Reorder Saved Locations
// ---------------------------------------------------------------------------

/// `show_reorder_locations_dialog`: the new order, or None if cancelled.
pub(crate) fn show_reorder_locations_dialog(parent: &Frame) -> Option<Vec<String>> {
    let names = Rc::new(RefCell::new(existing_names()));
    let dialog = Dialog::builder(parent, "Reorder Saved Locations")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let panel = Panel::builder(&dialog).build();
    let root = BoxSizer::builder(Orientation::Vertical).build();
    root.add(
        &label(
            &panel,
            "Choose the saved-location order you want. \
             Saving here switches Saved location order to Manual (custom).",
        ),
        0,
        SizerFlag::All | SizerFlag::Expand,
        10,
    );
    let content = BoxSizer::builder(Orientation::Horizontal).build();
    let list = ListBox::builder(&panel)
        .with_choices(names.borrow().clone())
        .build();
    list.set_name("Saved locations order");
    content.add(&list, 1, SizerFlag::All | SizerFlag::Expand, 10);
    let column = BoxSizer::builder(Orientation::Vertical).build();
    let move_up = Button::builder(&panel).with_label("Move Up").build();
    move_up.set_name("Move selected saved location up");
    column.add(&move_up, 0, SizerFlag::Bottom | SizerFlag::Expand, 8);
    let move_down = Button::builder(&panel).with_label("Move Down").build();
    move_down.set_name("Move selected saved location down");
    column.add(&move_down, 0, SizerFlag::Expand, 0);
    content.add_sizer(
        &column,
        0,
        SizerFlag::Top | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );
    root.add_sizer(&content, 1, SizerFlag::Expand, 0);
    let status_text = label(
        &panel,
        "Use Move Up and Move Down to arrange your saved locations.",
    );
    root.add(
        &status_text,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand,
        10,
    );
    panel.set_sizer(root, true);

    // `CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)`: stock "&OK" and
    // "&Cancel" on the dialog itself, OK the default.
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    let separated = BoxSizer::builder(Orientation::Vertical).build();
    let line = StaticLine::builder(&dialog).build();
    separated.add(&line, 0, SizerFlag::Expand | SizerFlag::Bottom, 5);
    let buttons = StdDialogButtonSizerBuilder::new().build();
    let ok = Button::builder(&dialog).with_id(ID_OK).build();
    let cancel = Button::builder(&dialog).with_id(ID_CANCEL).build();
    buttons.add_button(&ok);
    buttons.add_button(&cancel);
    buttons.realize();
    separated.add_sizer(&buttons, 0, SizerFlag::Expand, 0);
    dialog_sizer.add_sizer(&separated, 0, SizerFlag::All | SizerFlag::Expand, 10);
    dialog.set_sizer(dialog_sizer, true);
    ok.set_default();

    let refresh_move_buttons = {
        let names = names.clone();
        move || {
            let selection = list.get_selection().map(|s| s as usize);
            move_up.enable(selection.is_some_and(|s| s > 0));
            move_down.enable(selection.is_some_and(|s| s + 1 < names.borrow().len()));
        }
    };
    let move_selection = {
        let names = names.clone();
        let refresh = refresh_move_buttons.clone();
        move |direction: isize| {
            let Some(selection) = list.get_selection().map(|s| s as usize) else {
                return;
            };
            let Some(new_index) = selection
                .checked_add_signed(direction)
                .filter(|&i| i < names.borrow().len())
            else {
                return;
            };
            let moved = {
                let mut names = names.borrow_mut();
                names.swap(selection, new_index);
                names[new_index].clone()
            };
            list.clear();
            for name in names.borrow().iter() {
                list.append(name);
            }
            list.set_selection(new_index as u32, true);
            let message = format!("{moved} moved to position {}.", new_index + 1);
            status_text.set_label(&message);
            refresh();
            list.set_focus();
            mw::set_status(&message);
        }
    };

    if !names.borrow().is_empty() {
        list.set_selection(0, true);
    }
    {
        let refresh = refresh_move_buttons.clone();
        list.on_selection_changed(move |_| refresh());
        let m = move_selection.clone();
        move_up.on_click(move |_| m(-1));
        move_down.on_click(move |_| move_selection(1));
    }
    refresh_move_buttons();
    dialog.set_min_size(Size::new(420, 320));
    dialog.set_size(Size::new(520, 360));
    dialog.centre();
    list.set_focus();

    let result = dialog.show_modal();
    dialog.destroy();
    (result == ID_OK).then(|| names.borrow().clone())
}
