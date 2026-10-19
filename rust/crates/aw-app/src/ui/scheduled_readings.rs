//! Scheduled Readings (Tools menu): the weather read aloud for up to five
//! saved locations on a schedule, through the screen reader when one is
//! running and the system voice otherwise. The schedule logic and the spoken
//! text live in `aw_core::scheduled_reading`; this module owns the timer, the
//! fetch-and-speak step and the dialogs.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};

use aw_core::display::WeatherPresenter;
use aw_core::model::WeatherData;
use aw_core::scheduled_reading::{
    compose_reading, interval_label, spoken_time, ReadingClock, ScheduledReading, INTERVAL_CHOICES,
    MAX_SCHEDULED_READINGS,
};
use chrono::{Local, NaiveDateTime};
use wxdragon::prelude::*;
use wxdragon::timer::Timer;

use super::main_window::{main_frame, message_box, set_status};
use crate::app::{post_to_ui, save, with_state};

/// How often the clock is checked; readings start within this of their time.
const CHECK_INTERVAL_MS: i32 = 15_000;

const NO_VOICE_MESSAGE: &str =
    "Couldn't read the weather aloud: no screen reader or system voice is available.";

/// Set while readings are being fetched, so a slow or stalled network can't
/// pile up fetch threads and play a burst of stale readings later.
static READING_IN_PROGRESS: AtomicBool = AtomicBool::new(false);

thread_local! {
    static CLOCK: RefCell<ReadingClock> = RefCell::new(ReadingClock::new());
    static TIMER: RefCell<Option<Timer<Frame>>> = const { RefCell::new(None) };
}

// ---------------------------------------------------------------------------
// Schedule
// ---------------------------------------------------------------------------

/// Start checking the clock for due readings. Safe to call again.
pub(crate) fn start_scheduled_readings() {
    let Some(frame) = main_frame() else { return };
    stop_scheduled_readings();
    let timer = Timer::new(&frame);
    timer.on_tick(|_| check_due_readings());
    timer.start(CHECK_INTERVAL_MS, false);
    TIMER.with(|t| *t.borrow_mut() = Some(timer));
    // Record the current slots now, so the first reading comes at the next
    // scheduled time rather than up to one check late.
    check_due_readings();
}

/// Stop the timer before the window goes away.
pub(crate) fn stop_scheduled_readings() {
    if let Some(timer) = TIMER.with(|t| t.borrow_mut().take()) {
        timer.stop();
    }
}

fn check_due_readings() {
    let Some(state) = with_state() else { return };
    let schedules = state.borrow().config.settings.scheduled_readings.clone();
    let now = Local::now().naive_local();
    let due = CLOCK.with(|c| c.borrow_mut().due(&schedules, now));
    if !due.is_empty() {
        let due: Vec<ScheduledReading> = due.into_iter().map(|i| schedules[i].clone()).collect();
        read_aloud(due, now, false);
    }
}

/// Fetch the weather for each schedule, in order, and read it aloud.
/// `manual` is Read Now: a failure to speak is shown in a message box.
fn read_aloud(schedules: Vec<ScheduledReading>, now: NaiveDateTime, manual: bool) {
    let Some(state) = with_state() else { return };
    let (client, jobs) = {
        let st = state.borrow();
        let jobs: Vec<_> = schedules
            .into_iter()
            .filter_map(|schedule| {
                let location = st.config.find_location(&schedule.location).cloned();
                if location.is_none() {
                    tracing::warn!(
                        "Scheduled reading skipped: no saved location named {}",
                        schedule.location
                    );
                }
                location.map(|location| (schedule, location))
            })
            .collect();
        (st.client.clone(), jobs)
    };
    if jobs.is_empty() {
        return;
    }
    if READING_IN_PROGRESS.swap(true, Ordering::SeqCst) {
        tracing::warn!("Skipping scheduled reading: the previous one is still fetching");
        return;
    }
    let spawned = std::thread::Builder::new()
        .name("aw-scheduled-reading".into())
        .spawn(move || {
            for (schedule, location) in jobs {
                tracing::info!("Scheduled reading for {}", location.name);
                let data = client.get_weather_data(&location, false);
                post_to_ui(move || speak_reading(&schedule, &data, now, manual));
            }
            READING_IN_PROGRESS.store(false, Ordering::SeqCst);
        });
    if let Err(e) = spawned {
        READING_IN_PROGRESS.store(false, Ordering::SeqCst);
        tracing::error!("Couldn't start the scheduled reading: {e}");
    }
}

fn speak_reading(
    schedule: &ScheduledReading,
    data: &WeatherData,
    now: NaiveDateTime,
    manual: bool,
) {
    // Nothing to do once the window has closed.
    let (Some(state), Some(frame)) = (with_state(), main_frame()) else {
        return;
    };
    let text = {
        let st = state.borrow();
        let settings = &st.config.settings;
        let presentation = WeatherPresenter::new(settings).present(data);
        compose_reading(
            schedule,
            &presentation,
            &spoken_time(now, settings.time_format_12hour),
        )
    };
    if crate::screen_reader::speak_aloud(&text) {
        return;
    }
    if manual {
        message_box(
            &frame,
            NO_VOICE_MESSAGE,
            "Read Now",
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
    } else {
        set_status(NO_VOICE_MESSAGE);
    }
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

fn text<P: WxWidget>(parent: &P, label: &str) -> StaticText {
    let t = StaticText::builder(parent).with_label(label).build();
    t.wrap(440);
    t
}

/// OK and Cancel under a line, OK the default.
fn add_ok_cancel(dialog: &Dialog, sizer: &BoxSizer) -> Button {
    let line = StaticLine::builder(dialog).build();
    sizer.add(
        &line,
        0,
        SizerFlag::Expand | SizerFlag::Left | SizerFlag::Right | SizerFlag::Top,
        10,
    );
    let buttons = StdDialogButtonSizerBuilder::new().build();
    let ok = Button::builder(dialog).with_id(ID_OK).build();
    let cancel = Button::builder(dialog).with_id(ID_CANCEL).build();
    buttons.add_button(&ok);
    buttons.add_button(&cancel);
    buttons.realize();
    sizer.add_sizer(&buttons, 0, SizerFlag::Expand | SizerFlag::All, 10);
    ok.set_default();
    ok
}

/// Tools > Scheduled Readings.
pub(crate) fn show_scheduled_readings_dialog(parent: &Frame) {
    let Some(state) = with_state() else { return };
    let (initial, names) = {
        let st = state.borrow();
        (
            st.config.settings.scheduled_readings.clone(),
            Rc::new(st.config.location_names()),
        )
    };
    let readings = Rc::new(RefCell::new(initial));

    let dialog = Dialog::builder(parent, "Scheduled Readings")
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .build();
    let root = BoxSizer::builder(Orientation::Vertical).build();
    let intro = text(
        &dialog,
        &format!(
            "AccessiWeather can read the weather aloud on a schedule for up to \
             {MAX_SCHEDULED_READINGS} saved locations. Readings use your screen reader \
             when one is running, or your computer's voice otherwise. They play \
             while AccessiWeather is running, including when it's in the tray."
        ),
    );
    root.add(&intro, 0, SizerFlag::All | SizerFlag::Expand, 10);

    let content = BoxSizer::builder(Orientation::Horizontal).build();
    let list_label = text(&dialog, "Scheduled readings:");
    root.add(
        &list_label,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Expand,
        10,
    );
    let list = ListBox::builder(&dialog).build();
    list.set_name("Scheduled readings");
    content.add(&list, 1, SizerFlag::All | SizerFlag::Expand, 10);
    let column = BoxSizer::builder(Orientation::Vertical).build();
    let make_button = |label: &str, name: &str| {
        let b = Button::builder(&dialog).with_label(label).build();
        b.set_name(name);
        column.add(&b, 0, SizerFlag::Bottom | SizerFlag::Expand, 8);
        b
    };
    let add = make_button("&Add...", "Add a scheduled reading");
    let edit = make_button("&Edit...", "Edit the selected scheduled reading");
    let remove = make_button("&Remove", "Remove the selected scheduled reading");
    let read_now = make_button("Read &Now", "Read the selected scheduled reading aloud now");
    content.add_sizer(
        &column,
        0,
        SizerFlag::Top | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );
    root.add_sizer(&content, 1, SizerFlag::Expand, 0);
    let status = text(&dialog, "");
    root.add(
        &status,
        0,
        SizerFlag::Left | SizerFlag::Right | SizerFlag::Bottom | SizerFlag::Expand,
        10,
    );
    add_ok_cancel(&dialog, &root);
    dialog.set_sizer(root, true);

    let refresh = {
        let readings = readings.clone();
        let location_names = names.clone();
        move |select: Option<usize>| {
            let readings = readings.borrow();
            list.clear();
            for reading in readings.iter() {
                list.append(&reading.summary());
            }
            let count = readings.len();
            if let Some(index) = select.filter(|_| count > 0) {
                list.set_selection(index.min(count - 1) as u32, true);
            }
            let selected = list.get_selection().is_some();
            add.enable(count < MAX_SCHEDULED_READINGS && !location_names.is_empty());
            edit.enable(selected);
            remove.enable(selected);
            read_now.enable(selected);
            status.set_label(&if location_names.is_empty() {
                "Add a location first, then come back to schedule readings for it.".to_string()
            } else if count == 0 {
                "No scheduled readings yet. Choose Add to create one.".to_string()
            } else if count >= MAX_SCHEDULED_READINGS {
                format!("You have the maximum of {MAX_SCHEDULED_READINGS} scheduled readings.")
            } else {
                format!("{count} of {MAX_SCHEDULED_READINGS} scheduled readings.")
            });
        }
    };
    // Moving through the list only updates the buttons; rebuilding it here
    // would make screen readers lose their place.
    list.on_selection_changed(move |_| {
        let selected = list.get_selection().is_some();
        edit.enable(selected);
        remove.enable(selected);
        read_now.enable(selected);
    });
    let do_edit = {
        let readings = readings.clone();
        let refresh = refresh.clone();
        let names = names.clone();
        move || {
            let Some(index) = list.get_selection().map(|s| s as usize) else {
                return;
            };
            let current = readings.borrow()[index].clone();
            if let Some(updated) = edit_reading(&dialog, "Edit Scheduled Reading", &current, &names)
            {
                readings.borrow_mut()[index] = updated;
                refresh(Some(index));
            }
            list.set_focus();
        }
    };
    {
        let readings = readings.clone();
        let refresh = refresh.clone();
        let names = names.clone();
        add.on_click(move |_| {
            if readings.borrow().len() >= MAX_SCHEDULED_READINGS {
                return;
            }
            let Some(first) = names.first() else { return };
            let fresh = ScheduledReading::new(first.clone());
            if let Some(new) = edit_reading(&dialog, "Add Scheduled Reading", &fresh, &names) {
                let index = {
                    let mut readings = readings.borrow_mut();
                    readings.push(new);
                    readings.len() - 1
                };
                refresh(Some(index));
                list.set_focus();
            }
        });
    }
    {
        let edit_clicked = do_edit.clone();
        edit.on_click(move |_| edit_clicked());
        list.on_item_double_clicked(move |_| do_edit());
    }
    {
        let readings = readings.clone();
        let refresh = refresh.clone();
        remove.on_click(move |_| {
            let Some(index) = list.get_selection().map(|s| s as usize) else {
                return;
            };
            let removed = readings.borrow_mut().remove(index);
            refresh(Some(index));
            let message = format!("Removed the reading for {}.", removed.location);
            status.set_label(&message);
            crate::screen_reader::announce(&message);
            if readings.borrow().is_empty() {
                add.set_focus();
            } else {
                list.set_focus();
            }
        });
    }
    {
        let readings = readings.clone();
        read_now.on_click(move |_| {
            let Some(index) = list.get_selection().map(|s| s as usize) else {
                return;
            };
            let reading = ScheduledReading {
                enabled: true,
                ..readings.borrow()[index].clone()
            };
            if !reading.reads_anything() {
                return;
            }
            read_aloud(vec![reading], Local::now().naive_local(), true);
        });
    }

    refresh((!readings.borrow().is_empty()).then_some(0));
    dialog.set_min_size(Size::new(480, 340));
    dialog.fit();
    dialog.centre();
    if readings.borrow().is_empty() {
        add.set_focus();
    } else {
        list.set_focus();
    }

    let accepted = dialog.show_modal() == ID_OK;
    dialog.destroy();
    if !accepted {
        return;
    }
    let saved = {
        let mut st = state.borrow_mut();
        st.config.settings.scheduled_readings = readings.borrow().clone();
        save(&st).is_ok()
    };
    if !saved {
        set_status("Couldn't save your scheduled readings.");
    }
}

/// The Add / Edit dialog: the reading, changed, on OK.
fn edit_reading(
    parent: &Dialog,
    title: &str,
    initial: &ScheduledReading,
    location_names: &[String],
) -> Option<ScheduledReading> {
    let dialog = Dialog::builder(parent, title)
        .with_style(DialogStyle::DefaultDialogStyle)
        .build();
    let root = BoxSizer::builder(Orientation::Vertical).build();
    let flags = SizerFlag::Left | SizerFlag::Right | SizerFlag::Top | SizerFlag::Expand;

    // Labels come right before their control so screen readers name it.
    root.add(&text(&dialog, "Location to read:"), 0, flags, 10);
    // A reading whose location is missing (an imported or hand-edited
    // config) keeps that name rather than silently moving to another place.
    let mut location_names = location_names.to_vec();
    if !location_names.contains(&initial.location) && !initial.location.is_empty() {
        location_names.insert(0, initial.location.clone());
    }
    let location = Choice::builder(&dialog)
        .with_choices(location_names.clone())
        .build();
    location.set_name("Location to read");
    root.add(&location, 0, flags, 10);

    root.add(&text(&dialog, "How often to read it:"), 0, flags, 10);
    let interval = Choice::builder(&dialog)
        .with_choices(
            INTERVAL_CHOICES
                .iter()
                .map(|m| interval_label(*m))
                .collect(),
        )
        .build();
    interval.set_name("How often to read it");
    root.add(&interval, 0, flags, 10);

    root.add(&text(&dialog, "What to read:"), 0, flags, 10);
    let check = |label: &str, value: bool| {
        let c = CheckBox::builder(&dialog)
            .with_label(label)
            .with_value(value)
            .build();
        root.add(&c, 0, flags, 10);
        c
    };
    let current = check("&Current conditions", initial.read_current);
    let forecast = check("&Forecast for the next two periods", initial.read_forecast);
    let alerts = check("Active &alerts", initial.read_alerts);
    let enabled = check("&Turn this reading on", initial.enabled);
    add_ok_cancel(&dialog, &root);
    dialog.set_sizer(root, true);
    dialog.fit();
    dialog.centre();

    let location_index = location_names
        .iter()
        .position(|n| *n == initial.location)
        .unwrap_or(0);
    location.set_selection(location_index as u32);
    let interval_index = INTERVAL_CHOICES
        .iter()
        .position(|m| *m == initial.interval())
        .unwrap_or(0);
    interval.set_selection(interval_index as u32);
    location.set_focus();

    let result = loop {
        if dialog.show_modal() != ID_OK {
            break None;
        }
        let reading = ScheduledReading {
            enabled: enabled.is_checked(),
            location: location
                .get_string_selection()
                .unwrap_or_else(|| initial.location.clone()),
            interval_minutes: interval
                .get_selection()
                .and_then(|i| INTERVAL_CHOICES.get(i as usize).copied())
                .unwrap_or(initial.interval_minutes),
            read_current: current.is_checked(),
            read_forecast: forecast.is_checked(),
            read_alerts: alerts.is_checked(),
        };
        if reading.reads_anything() {
            break Some(reading);
        }
        message_box(
            &dialog,
            "Choose at least one thing to read: current conditions, the forecast or alerts.",
            "Nothing to Read",
            MessageDialogStyle::OK | MessageDialogStyle::IconWarning,
        );
        current.set_focus();
    };
    dialog.destroy();
    result
}
