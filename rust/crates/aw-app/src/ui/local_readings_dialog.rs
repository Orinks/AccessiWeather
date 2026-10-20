//! View > Local Readings: official readings from the stations and areas
//! nearest the current location, one self-contained line per reading
//! (value, period, station or area and distance, time, source).
//!
//! Readings are fetched when the dialog opens (and on Refresh), on a worker
//! thread, from every [`aw_providers::regional`] source covering the
//! location. Nothing is fetched while the setting is off.

use std::cell::{Cell, RefCell};
use std::rc::Rc;

use aw_core::Location;
use aw_providers::regional::{
    default_sources, fetch_local_readings, LocalReadingsReport, TimeStyle,
};
use chrono::{DateTime, Utc};
use wxdragon::prelude::*;

use super::commands::MSG_SELECT_LOCATION_FIRST;
use super::location_dialog::{in_background, text_colour};
use super::locations::CAPTION_NO_LOCATION;
use super::main_window::{message_box, window};
use crate::app::with_state;

const CAPTION: &str = "Local Readings";
pub(crate) const MSG_TURNED_OFF: &str = "Local official readings are turned off. You can turn \
     them on in Settings, on the Display tab, under Extra weather details.";

/// The status line and the readings text for a finished fetch.
#[derive(Debug, PartialEq)]
struct ReportView {
    status: String,
    text: String,
}

fn join_names(names: &[String]) -> String {
    match names {
        [] => String::new(),
        [one] => one.clone(),
        [rest @ .., last] => format!("{} and {last}", rest.join(", ")),
    }
}

fn report_view(report: &LocalReadingsReport, style: &TimeStyle<'_>) -> ReportView {
    let mut status = if report.readings.is_empty() {
        "No local official readings are available for this location right now.".to_string()
    } else {
        let count = report.readings.len();
        let sources: Vec<String> = report
            .sources
            .iter()
            .filter(|s| !report.failures.iter().any(|f| &f.source == *s))
            .cloned()
            .collect();
        format!(
            "{count} reading{} from {}.",
            if count == 1 { "" } else { "s" },
            join_names(&sources)
        )
    };
    if !report.failures.is_empty() {
        let failed: Vec<String> = report.failures.iter().map(|f| f.source.clone()).collect();
        status.push_str(&format!(
            " Couldn't reach {} right now.",
            join_names(&failed)
        ));
    }
    let text = if report.readings.is_empty() {
        "No readings.".to_string()
    } else {
        report
            .readings
            .iter()
            .map(|r| r.to_line(style))
            .collect::<Vec<_>>()
            .join("\n")
    };
    ReportView { status, text }
}

struct LocalReadingsDialog {
    location: Location,
    status_label: StaticText,
    readings_text: TextCtrl,
    refresh_button: Button,
    is_fetching: Cell<bool>,
}

thread_local! {
    /// The open dialog; results for a closed one are dropped.
    static OPEN: RefCell<Option<Rc<LocalReadingsDialog>>> = const { RefCell::new(None) };
}

fn open_dialog() -> Option<Rc<LocalReadingsDialog>> {
    OPEN.with(|d| d.borrow().clone())
}

/// View > Local Readings.
pub(crate) fn show_local_readings_dialog() {
    let (Some(w), Some(state)) = (window(), with_state()) else {
        return;
    };
    let (location, enabled) = {
        let st = state.borrow();
        (
            st.config.current_location.clone(),
            st.config.settings.show_local_official_readings,
        )
    };
    let Some(location) = location else {
        message_box(
            &w.frame,
            MSG_SELECT_LOCATION_FIRST,
            CAPTION_NO_LOCATION,
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
        return;
    };
    if !enabled {
        message_box(
            &w.frame,
            MSG_TURNED_OFF,
            CAPTION,
            MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
        );
        return;
    }

    let dialog = Dialog::builder(&w.frame, &format!("Local Readings - {}", location.name))
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(760, 520)
        .build();
    let panel = Panel::builder(&dialog).build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();

    let intro = StaticText::builder(&panel)
        .with_label(
            "Official readings from the weather stations and forecast areas nearest this \
             location. Each line gives the value, the station or area it covers and how far \
             away it is, when it was observed, and its source.",
        )
        .build();
    intro.wrap(700);
    intro.set_name("About local readings");
    sizer.add(&intro, 0, SizerFlag::All, 15);

    let status_label = StaticText::builder(&panel)
        .with_label("Loading local readings...")
        .build();
    status_label.set_name("Local readings status");
    sizer.add(
        &status_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom,
        15,
    );

    let list_label = StaticText::builder(&panel)
        .with_label("Readings, one per line:")
        .build();
    sizer.add(&list_label, 0, SizerFlag::Left | SizerFlag::Right, 15);
    let readings_text = TextCtrl::builder(&panel)
        .with_value("Loading...")
        .with_style(TextCtrlStyle::MultiLine | TextCtrlStyle::ReadOnly | TextCtrlStyle::Rich2)
        .build();
    readings_text.set_name("Local readings, one per line");
    sizer.add(
        &readings_text,
        1,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        15,
    );

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let refresh_button = Button::builder(&panel)
        .with_label("&Refresh Readings")
        .build();
    refresh_button.set_name("Refresh local readings");
    buttons.add(&refresh_button, 0, SizerFlag::empty(), 0);
    buttons.add_stretch_spacer(1);
    let close = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label("Close")
        .build();
    close.set_name("Close local readings");
    close.on_click(move |_| dialog.end_modal(ID_CLOSE));
    buttons.add(&close, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 15);

    panel.set_sizer(sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);
    readings_text.set_focus();

    let d = Rc::new(LocalReadingsDialog {
        location,
        status_label,
        readings_text,
        refresh_button,
        is_fetching: Cell::new(false),
    });
    let d2 = d.clone();
    refresh_button.on_click(move |_| d2.fetch());
    dialog.bind_internal(EventType::CHAR_HOOK, move |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            dialog.end_modal(ID_CLOSE);
        } else {
            e.skip(true);
        }
    });

    d.fetch();
    OPEN.with(|slot| *slot.borrow_mut() = Some(d));
    dialog.show_modal();
    OPEN.with(|slot| slot.borrow_mut().take());
    dialog.destroy();
}

impl LocalReadingsDialog {
    fn fetch(&self) {
        if self.is_fetching.replace(true) {
            return;
        }
        self.refresh_button.enable(false);
        self.status_label.set_label("Loading local readings...");
        text_colour(&self.status_label, false);
        let location = self.location.clone();
        in_background(
            move |http| fetch_local_readings(http, &location, &default_sources()),
            |report| {
                let Some(d) = open_dialog() else { return };
                d.show(&report, Utc::now());
            },
        );
    }

    fn show(&self, report: &LocalReadingsReport, now: DateTime<Utc>) {
        let twelve_hour = with_state()
            .map(|s| s.borrow().config.settings.time_format_12hour)
            .unwrap_or(true);
        let style = TimeStyle {
            timezone: self.location.timezone.as_deref(),
            twelve_hour,
            now,
        };
        let view = report_view(report, &style);
        self.is_fetching.set(false);
        self.refresh_button.enable(true);
        self.status_label.set_label(&view.status);
        text_colour(&self.status_label, report.readings.is_empty());
        self.readings_text.set_value(&view.text);
        self.readings_text.set_insertion_point(0);
    }
}

#[cfg(test)]
mod tests {
    use aw_providers::regional::{Coverage, LocalReading, ReadingKind, ReadingTime, SourceFailure};

    use super::*;

    fn style() -> TimeStyle<'static> {
        TimeStyle {
            timezone: Some("Asia/Singapore"),
            twelve_hour: true,
            now: Utc::now(),
        }
    }

    fn reading(source: &str) -> LocalReading {
        LocalReading {
            kind: ReadingKind::Rainfall,
            label: "Rainfall".into(),
            value: "0.2 mm".into(),
            detail: None,
            period: Some("5-minute total".into()),
            coverage: Coverage::new("Changi station", Some(1.0)),
            time: ReadingTime::Unknown,
            source: source.into(),
        }
    }

    #[test]
    fn status_names_sources_and_failures() {
        let report = LocalReadingsReport {
            readings: vec![reading("Singapore NEA"), reading("Singapore NEA")],
            sources: vec!["Singapore NEA".into(), "Nearest airport (METAR)".into()],
            failures: vec![SourceFailure {
                source: "Nearest airport (METAR)".into(),
                message: "HTTP 429".into(),
            }],
        };
        let view = report_view(&report, &style());
        assert_eq!(
            view.status,
            "2 readings from Singapore NEA. Couldn't reach Nearest airport (METAR) right now."
        );
        assert_eq!(view.text.lines().count(), 2);
        assert!(view.text.starts_with(
            "Rainfall: 0.2 mm, 5-minute total. Changi station, 1.0 km away. Source: Singapore NEA."
        ));
    }

    #[test]
    fn empty_report_says_so() {
        let view = report_view(&LocalReadingsReport::default(), &style());
        assert_eq!(
            view.status,
            "No local official readings are available for this location right now."
        );
        assert_eq!(view.text, "No readings.");
    }

    #[test]
    fn names_join_naturally() {
        let names = |v: &[&str]| join_names(&v.iter().map(|s| s.to_string()).collect::<Vec<_>>());
        assert_eq!(names(&["A"]), "A");
        assert_eq!(names(&["A", "B"]), "A and B");
        assert_eq!(names(&["A", "B", "C"]), "A, B and C");
    }
}
