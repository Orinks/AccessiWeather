//! The Aviation Weather dialog, ported from `ui/dialogs/aviation_dialog.py`:
//! the TAF (raw and decoded) and SIGMET/CWA advisories for an ICAO code.

use std::cell::{Cell, RefCell};
use std::rc::Rc;

use aw_core::model::AviationData;
use aw_core::py::{truthy, value_str};
use aw_providers::nws::{AviationOptions, NwsClient};
use serde_json::Value;
use wxdragon::prelude::*;

use super::location_dialog::{in_background, set_hint, text_colour};
use super::main_window::window;
use crate::app::{save, save_api_key, with_state};

const AVWX_SIGNUP_URL: &str = "https://account.avwx.rest";
const NO_ADVISORIES: &str = "No advisories available.";

/// `_on_fetch` validation: the upper-cased code, or the status to show.
fn validate_code(input: &str) -> Result<String, &'static str> {
    let code = input.trim().to_uppercase();
    if code.is_empty() {
        return Err("Please enter a four-letter ICAO airport code.");
    }
    if code.len() != 4 || !code.bytes().all(|b| b.is_ascii_uppercase()) {
        return Err("Airport codes must be exactly four letters (e.g., KJFK).");
    }
    Ok(code)
}

/// The first truthy value among `keys` (`entry.get(a) or entry.get(b) ...`).
fn first<'a>(entry: &'a Value, keys: &[&str]) -> Option<&'a Value> {
    keys.iter()
        .filter_map(|k| entry.get(k))
        .find(|v| truthy(Some(v)))
}

/// `_format_advisory_window`.
fn advisory_window(entry: &Value) -> String {
    let start = first(
        entry,
        &["startTime", "beginTime", "validTimeStart", "issueTime"],
    );
    let end = first(entry, &["endTime", "expires", "validTimeEnd", "validUntil"]);
    match (start, end) {
        (Some(start), Some(end)) => format!("{} → {}", value_str(start), value_str(end)),
        (None, Some(end)) => format!("Until {}", value_str(end)),
        (Some(start), None) => value_str(start),
        (None, None) => "--".into(),
    }
}

/// `_build_advisory_row`: Type, Event, Valid, Summary.
fn advisory_row(kind: &str, entry: &Value) -> [String; 4] {
    let event =
        first(entry, &["event", "name", "hazard"]).map_or_else(|| kind.to_string(), value_str);
    let summary: String = first(entry, &["description", "summary", "text"])
        .map(value_str)
        .unwrap_or_default()
        .trim()
        .chars()
        .take(200)
        .collect();
    let summary = if summary.is_empty() {
        "No description provided.".into()
    } else {
        summary
    };
    [kind.to_string(), event, advisory_window(entry), summary]
}

/// What the dialog shows after a fetch (`_on_fetch_complete`).
#[derive(Debug, PartialEq)]
struct FetchView {
    status: String,
    is_error: bool,
    raw: String,
    decoded: String,
    rows: Vec<[String; 4]>,
    info: String,
}

fn fetch_complete_view(code: &str, aviation: Option<&AviationData>) -> FetchView {
    let Some(aviation) = aviation.filter(|a| a.has_taf()) else {
        return FetchView {
            status: format!("No TAF available for {code}. The station may not publish TAF data."),
            is_error: true,
            raw: "No TAF available.".into(),
            decoded: "No decoded TAF available.".into(),
            rows: Vec::new(),
            info: NO_ADVISORIES.into(),
        };
    };
    let non_empty = |s: &Option<String>| s.clone().filter(|s| !s.is_empty());
    let airport = non_empty(&aviation.airport_name)
        .or_else(|| non_empty(&aviation.station_id))
        .unwrap_or_else(|| code.to_string());
    let rows: Vec<[String; 4]> = aviation
        .active_sigmets
        .iter()
        .take(10)
        .map(|s| advisory_row("SIGMET", s))
        .chain(
            aviation
                .active_cwas
                .iter()
                .take(10)
                .map(|c| advisory_row("CWA", c)),
        )
        .collect();
    FetchView {
        status: format!("Latest TAF loaded for {airport}."),
        is_error: false,
        raw: non_empty(&aviation.raw_taf).unwrap_or_else(|| "No TAF available.".into()),
        decoded: non_empty(&aviation.decoded_taf).unwrap_or_else(|| "Unable to decode TAF.".into()),
        info: if rows.is_empty() {
            NO_ADVISORIES.into()
        } else {
            format!("{} advisories loaded.", rows.len())
        },
        rows,
    }
}

/// `_on_fetch_error`.
fn fetch_error_status(error: &str) -> String {
    format!("Failed to retrieve aviation weather: {error}")
}

// ---------------------------------------------------------------------------
// Dialog
// ---------------------------------------------------------------------------

struct AviationDialog {
    station_input: TextCtrl,
    fetch_button: Button,
    avwx_key_input: TextCtrl,
    status_label: StaticText,
    raw_taf_display: TextCtrl,
    decoded_taf_display: TextCtrl,
    advisories_list: ListCtrl,
    advisories_info: StaticText,
    is_fetching: Cell<bool>,
}

thread_local! {
    /// The open dialog; results for a closed one are dropped.
    static OPEN: RefCell<Option<Rc<AviationDialog>>> = const { RefCell::new(None) };
}

fn open_dialog() -> Option<Rc<AviationDialog>> {
    OPEN.with(|d| d.borrow().clone())
}

fn gray_label(panel: &Panel, text: &str) -> StaticText {
    let label = StaticText::builder(panel).with_label(text).build();
    text_colour(&label, true);
    label
}

fn bold_label(panel: &Panel, text: &str) -> StaticText {
    let label = StaticText::builder(panel).with_label(text).build();
    if let Some(mut font) = label.get_font() {
        font.make_bold();
        label.set_font(&font);
    }
    label
}

fn read_only(panel: &Panel, value: &str) -> TextCtrl {
    TextCtrl::builder(panel)
        .with_value(value)
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly)
        .build()
}

/// View > Aviation Weather: `show_aviation_dialog`.
pub(crate) fn show_aviation_dialog() {
    let (Some(w), Some(state)) = (window(), with_state()) else {
        return;
    };
    let current_key = state.borrow().config.settings.avwx_api_key.clone();

    let dialog = Dialog::builder(&w.frame, "Aviation Weather")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(900, 620)
        .build();
    let panel = Panel::builder(&dialog).build();
    let main_sizer = BoxSizer::builder(Orientation::Vertical).build();

    let header = gray_label(
        &panel,
        "Fetch decoded aviation weather by entering a four-letter ICAO airport code.",
    );
    main_sizer.add(&header, 0, SizerFlag::All, 15);

    let input_row = BoxSizer::builder(Orientation::Horizontal).build();
    let code_label = bold_label(&panel, "Airport code:");
    input_row.add(
        &code_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        10,
    );
    let station_input = TextCtrl::builder(&panel)
        .with_size(Size::new(100, -1))
        .with_style(TextCtrlStyle::ProcessEnter)
        .build();
    set_hint(&station_input, "e.g., KJFK");
    input_row.add(&station_input, 0, SizerFlag::Right, 10);
    let fetch_button = Button::builder(&panel)
        .with_label("Get Aviation Data")
        .build();
    input_row.add(&fetch_button, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(
        &input_row,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        15,
    );

    let avwx_row = BoxSizer::builder(Orientation::Horizontal).build();
    let avwx_label = StaticText::builder(&panel)
        .with_label("AVWX API Key (optional):")
        .build();
    avwx_row.add(
        &avwx_label,
        0,
        SizerFlag::AlignCenterVertical | SizerFlag::Right,
        10,
    );
    let avwx_key_input = TextCtrl::builder(&panel)
        .with_value(&current_key)
        .with_size(Size::new(250, -1))
        .with_style(TextCtrlStyle::Password)
        .build();
    avwx_row.add(&avwx_key_input, 0, SizerFlag::Right, 10);
    let avwx_signup_btn = Button::builder(&panel).with_label("Get Free Key").build();
    avwx_signup_btn.on_click(|_| {
        launch_default_browser(AVWX_SIGNUP_URL, BrowserLaunchFlags::Default);
    });
    avwx_row.add(&avwx_signup_btn, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(
        &avwx_row,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        15,
    );

    let avwx_hint = gray_label(
        &panel,
        "Enables enhanced translations, flight rules, and screen-reader speech \
         for international airports. US airports use NWS by default.",
    );
    main_sizer.add(
        &avwx_hint,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        15,
    );

    let status_label = gray_label(
        &panel,
        "Enter a code and press Enter to fetch the latest TAF.",
    );
    main_sizer.add(
        &status_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        15,
    );

    let content_row = BoxSizer::builder(Orientation::Horizontal).build();
    let raw_sizer = BoxSizer::builder(Orientation::Vertical).build();
    raw_sizer.add(&bold_label(&panel, "Raw TAF"), 0, SizerFlag::Bottom, 5);
    let raw_taf_display = read_only(&panel, "No TAF loaded.");
    let mono = Font::new_with_details(
        9,
        FontFamily::Teletype.as_i32(),
        FontStyle::Normal.as_i32(),
        FontWeight::Normal.as_i32(),
        false,
        "",
    );
    if let Some(font) = mono {
        raw_taf_display.set_font(&font);
    }
    raw_sizer.add(&raw_taf_display, 1, SizerFlag::Expand, 0);
    content_row.add_sizer(&raw_sizer, 1, SizerFlag::Expand | SizerFlag::Right, 10);
    let decoded_sizer = BoxSizer::builder(Orientation::Vertical).build();
    decoded_sizer.add(&bold_label(&panel, "Decoded TAF"), 0, SizerFlag::Bottom, 5);
    let decoded_taf_display = read_only(&panel, "Decoded TAF will appear here.");
    decoded_sizer.add(&decoded_taf_display, 1, SizerFlag::Expand, 0);
    content_row.add_sizer(&decoded_sizer, 1, SizerFlag::Expand, 0);
    main_sizer.add_sizer(
        &content_row,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right,
        15,
    );

    main_sizer.add(
        &bold_label(&panel, "Advisories"),
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        15,
    );
    let advisories_list = ListCtrl::builder(&panel)
        .with_style(ListCtrlStyle::Report | ListCtrlStyle::SingleSel)
        .with_size(Size::new(-1, 150))
        .build();
    for (col, (heading, width)) in [
        ("Type", 80),
        ("Event", 150),
        ("Valid", 200),
        ("Summary", 350),
    ]
    .into_iter()
    .enumerate()
    {
        advisories_list.insert_column(col as i64, heading, ListColumnFormat::Left, width);
    }
    main_sizer.add(
        &advisories_list,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        15,
    );
    let advisories_info = gray_label(&panel, NO_ADVISORIES);
    main_sizer.add(
        &advisories_info,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        15,
    );

    let button_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    button_sizer.add_stretch_spacer(1);
    let close = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label("Close")
        .build();
    close.on_click(move |_| dialog.end_modal(ID_CLOSE));
    button_sizer.add(&close, 0, SizerFlag::empty(), 0);
    main_sizer.add_sizer(&button_sizer, 0, SizerFlag::Expand | SizerFlag::All, 15);
    panel.set_sizer(main_sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);
    station_input.set_focus();

    // `_setup_accessibility`.
    station_input.set_name("ICAO airport code input");
    avwx_key_input.set_name("AVWX API Key (optional)");
    avwx_signup_btn.set_name("Get free AVWX API key, opens browser");
    raw_taf_display.set_name("Raw TAF display");
    decoded_taf_display.set_name("Decoded TAF display");
    advisories_list.set_name("Aviation advisories list");

    let d = Rc::new(AviationDialog {
        station_input,
        fetch_button,
        avwx_key_input,
        status_label,
        raw_taf_display,
        decoded_taf_display,
        advisories_list,
        advisories_info,
        is_fetching: Cell::new(false),
    });
    let d2 = d.clone();
    station_input.on_text_enter(move |_| d2.on_fetch());
    let d2 = d.clone();
    fetch_button.on_click(move |_| d2.on_fetch());
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.close(false);
        } else {
            e.skip(true);
        }
    });

    OPEN.with(|slot| *slot.borrow_mut() = Some(d));
    dialog.show_modal();
    OPEN.with(|slot| slot.borrow_mut().take());
    dialog.destroy();
}

impl AviationDialog {
    /// `_set_status`: errors in gray, progress in the normal text colour.
    fn set_status(&self, message: &str, is_error: bool) {
        self.status_label.set_label(message);
        text_colour(&self.status_label, is_error);
    }

    /// `_on_fetch` (Enter in the code field or Get Aviation Data).
    fn on_fetch(&self) {
        let code = match validate_code(&self.station_input.get_value()) {
            Ok(code) => code,
            Err(message) => {
                self.set_status(message, true);
                return;
            }
        };
        if self.is_fetching.get() {
            return;
        }
        let Some(state) = with_state() else { return };
        self.is_fetching.set(true);
        self.fetch_button.enable(false);
        self.set_status(&format!("Fetching aviation weather for {code}..."), false);

        // The key typed here is used for this fetch and saved like Python's
        // `update_settings(avwx_api_key=...)`.
        let avwx_key = self.avwx_key_input.get_value().trim().to_string();
        {
            let mut st = state.borrow_mut();
            if avwx_key != st.config.settings.avwx_api_key {
                save_api_key(&mut st, "avwx_api_key", &avwx_key);
                let _ = save(&st);
            }
        }

        let options = AviationOptions {
            include_sigmets: true,
            include_cwas: true,
            ..Default::default()
        };
        let station = code.clone();
        in_background(
            move |http| {
                NwsClient::new(http)
                    .aviation_weather(&station, &options, &avwx_key)
                    .map_err(|e| {
                        tracing::error!("Aviation fetch failed: {e}");
                        e.to_string()
                    })
            },
            move |result| {
                let Some(d) = open_dialog() else { return };
                d.is_fetching.set(false);
                d.fetch_button.enable(true);
                match result {
                    Ok(aviation) => d.show_result(&fetch_complete_view(&code, Some(&aviation))),
                    // `_on_fetch_error`: the previous result stays on screen.
                    Err(error) => d.set_status(&fetch_error_status(&error), true),
                }
            },
        );
    }

    fn show_result(&self, view: &FetchView) {
        self.set_status(&view.status, view.is_error);
        self.raw_taf_display.set_value(&view.raw);
        self.decoded_taf_display.set_value(&view.decoded);
        self.advisories_list.delete_all_items();
        for row in &view.rows {
            let index = self.advisories_list.insert_item(
                self.advisories_list.get_item_count() as i64,
                &row[0],
                None,
            );
            for (col, text) in row.iter().enumerate().skip(1) {
                self.advisories_list
                    .set_item_text_by_column(index as i64, col as i32, text);
            }
        }
        self.advisories_info.set_label(&view.info);
    }
}

#[cfg(test)]
mod tests {
    //! Golden parity with the Python dialog driven by
    //! `rust/tools/golden/dataui.py`.

    use serde_json::Value;

    use super::*;

    fn golden() -> Value {
        let all: Value = serde_json::from_str(include_str!(
            "../../../../testdata/golden/dataui/cases.json"
        ))
        .unwrap();
        all["aviation"].clone()
    }

    fn assert_view(view: &FetchView, expected: &Value, case: &str) {
        assert_eq!(view.status, expected["status"], "{case}");
        assert_eq!(view.is_error, expected["status_gray"], "{case}");
        assert_eq!(view.raw, expected["raw"], "{case}");
        assert_eq!(view.decoded, expected["decoded"], "{case}");
        let rows: Vec<[String; 4]> = serde_json::from_value(expected["rows"].clone()).unwrap();
        assert_eq!(view.rows, rows, "{case}");
        assert_eq!(view.info, expected["info"], "{case}");
    }

    #[test]
    fn code_validation_matches_python() {
        for case in golden()["validation"].as_array().unwrap() {
            let input = case["input"].as_str().unwrap();
            match validate_code(input) {
                Ok(code) => {
                    assert!(case["valid"].as_bool().unwrap(), "{input:?}");
                    assert_eq!(code, input.trim().to_uppercase());
                }
                Err(status) => assert_eq!(status, case["status"], "{input:?}"),
            }
        }
    }

    #[test]
    fn fetch_results_match_python() {
        let g = golden();
        for case in g["fetches"].as_array().unwrap() {
            let name = case["name"].as_str().unwrap();
            let aviation: Option<AviationData> =
                serde_json::from_value(case["aviation"].clone()).unwrap();
            let view = fetch_complete_view(case["code"].as_str().unwrap(), aviation.as_ref());
            assert_view(&view, case, name);
        }
        assert_eq!(fetch_error_status("boom"), g["error"]["status"]);
        assert_eq!(g["error"]["status_gray"], true);
    }
}
