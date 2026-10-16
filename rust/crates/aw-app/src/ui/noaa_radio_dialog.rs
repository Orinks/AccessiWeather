//! The NOAA Weather Radio dialog: `ui/dialogs/noaa_radio_dialog.py` with the
//! widgets of `noaa_radio_widgets.py`. The behaviour lives in
//! [`aw_radio::RadioDialog`]; this module builds the same widgets in the same
//! order, forwards input to it and renders its [`DialogView`]. Non-modal:
//! closing it leaves the stream playing.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;

use aw_radio::dialog::{
    labels, DialogEventHandler, DIALOG_TITLE, FINDER_MODE_LABELS, STATION_LIMIT_LABELS,
};
use aw_radio::{DialogEvent, DialogView, RadioDialog};
use wxdragon::prelude::*;

use super::location_dialog::set_hint;
use super::main_window::{self as mw, message_box};
use crate::app::post_to_ui;

/// A choice's new items and/or selection.
#[derive(Debug, PartialEq)]
enum ChoiceUpdate {
    /// Same items; move the selection (`None` clears it).
    Select(Option<usize>),
    /// New items (`wx.Choice.Set`), then the selection.
    Reset(Vec<String>, Option<usize>),
}

/// One widget change.
#[derive(Debug, PartialEq)]
enum Op {
    FinderMode(usize),
    SearchLabel(String),
    SearchHint(String),
    SearchText(String),
    ShowSearch(bool),
    State(ChoiceUpdate),
    ShowState(bool),
    SavedLocation(ChoiceUpdate),
    ShowSavedLocation(bool),
    Station(ChoiceUpdate),
    StationLimit(usize),
    ShowUnavailable(bool),
    PlayLabel(String),
    PlayEnabled(bool),
    NextStreamEnabled(bool),
    PreferEnabled(bool),
    FavoriteLabel(String),
    FavoriteEnabled(bool),
    Volume(u32),
    Status(String),
    /// Something was shown or hidden (`finder_panel.Layout()`).
    Layout,
}

fn choice_update(
    (shown_items, shown_selection): (&[String], Option<usize>),
    (items, selection): (&[String], Option<usize>),
) -> Option<ChoiceUpdate> {
    if shown_items != items {
        Some(ChoiceUpdate::Reset(items.to_vec(), selection))
    } else if shown_selection != selection {
        Some(ChoiceUpdate::Select(selection))
    } else {
        None
    }
}

/// The widget changes that take the dialog from what it `shown`s to `view`.
/// Only what differs is touched, and a choice's items are only replaced when
/// they changed, so NVDA's focus and selection are left alone.
fn plan(shown: &DialogView, view: &DialogView) -> Vec<Op> {
    let mut ops = Vec::new();
    macro_rules! diff {
        ($($field:ident => $op:path),* $(,)?) => {$(
            if shown.$field != view.$field {
                ops.push($op(view.$field.clone()));
            }
        )*};
    }
    diff!(
        finder_mode => Op::FinderMode,
        search_label => Op::SearchLabel,
        search_hint => Op::SearchHint,
        search_text => Op::SearchText,
        search_visible => Op::ShowSearch,
    );
    ops.extend(
        choice_update(
            (&shown.state_choices, Some(shown.state_selection)),
            (&view.state_choices, Some(view.state_selection)),
        )
        .map(Op::State),
    );
    diff!(state_visible => Op::ShowState);
    ops.extend(
        choice_update(
            (
                &shown.saved_location_choices,
                shown.saved_location_selection,
            ),
            (&view.saved_location_choices, view.saved_location_selection),
        )
        .map(Op::SavedLocation),
    );
    diff!(saved_location_visible => Op::ShowSavedLocation);
    ops.extend(
        choice_update(
            (&shown.station_choices, shown.station_selection),
            (&view.station_choices, view.station_selection),
        )
        .map(Op::Station),
    );
    diff!(
        station_limit_selection => Op::StationLimit,
        show_unavailable => Op::ShowUnavailable,
        play_label => Op::PlayLabel,
        play_enabled => Op::PlayEnabled,
        next_stream_enabled => Op::NextStreamEnabled,
        prefer_enabled => Op::PreferEnabled,
        favorite_label => Op::FavoriteLabel,
        favorite_enabled => Op::FavoriteEnabled,
        volume => Op::Volume,
        status => Op::Status,
    );
    if shown.search_visible != view.search_visible
        || shown.state_visible != view.state_visible
        || shown.saved_location_visible != view.saved_location_visible
    {
        ops.push(Op::Layout);
    }
    ops
}

/// The widgets as `create_noaa_radio_widgets` makes them, before the dialog
/// applies its finder mode, playback state and first station lookup.
fn created_view(view: &DialogView) -> DialogView {
    DialogView {
        search_label: labels::SEARCH_TEXT.into(),
        search_hint: labels::SEARCH_INITIAL_HINT.into(),
        search_text: String::new(),
        search_visible: true,
        state_visible: true,
        saved_location_visible: true,
        station_choices: Vec::new(),
        station_selection: None,
        show_unavailable: false,
        play_label: labels::PLAY.into(),
        play_enabled: true,
        next_stream_enabled: false,
        prefer_enabled: false,
        favorite_label: labels::FAVORITE.into(),
        favorite_enabled: false,
        volume: 100,
        status: "Ready".into(),
        ..view.clone()
    }
}

// ---------------------------------------------------------------------------
// Widgets
// ---------------------------------------------------------------------------

#[derive(Clone, Copy)]
struct Widgets {
    dialog: Dialog,
    panel: Panel,
    finder_mode: Choice,
    search_label: StaticText,
    search_ctrl: TextCtrl,
    state_label: StaticText,
    state_choice: Choice,
    saved_location_label: StaticText,
    saved_location_choice: Choice,
    station_choice: Choice,
    station_limit: Choice,
    show_unavailable: CheckBox,
    play_stop: Button,
    next_stream: Button,
    prefer: Button,
    favorite: Button,
    volume: Slider,
    status: StaticText,
}

/// The open dialog. Handlers and renders find it here, so a closed dialog's
/// late events are dropped.
struct Open {
    id: u64,
    model: Arc<RadioDialog>,
    w: Widgets,
    /// What the widgets show: the last rendered view plus user input since.
    shown: RefCell<DialogView>,
}

thread_local! {
    static OPEN: RefCell<Option<Rc<Open>>> = const { RefCell::new(None) };
}

static NEXT_ID: AtomicU64 = AtomicU64::new(1);

fn open_dialog() -> Option<Rc<Open>> {
    OPEN.with(|o| o.borrow().clone())
}

fn with_open(f: impl FnOnce(&Open)) {
    if let Some(open) = open_dialog() {
        f(&open);
    }
}

/// View > NOAA Weather Radio (Ctrl+N): `show_noaa_radio_dialog(main_window)`,
/// which opens it without a point, so it starts on "Search all stations".
/// One dialog at a time: asking again brings it forward.
pub(crate) fn show_noaa_radio_dialog() {
    if let Some(open) = open_dialog() {
        open.w.dialog.show(true);
        open.w.dialog.raise();
        return;
    }
    let (Some(frame), Some(radio)) = (mw::main_frame(), crate::radio::radio()) else {
        return;
    };
    let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
    let model = radio
        .ctx
        .open_dialog(None, None, mw::ordered_saved_locations(), event_handler(id));
    let created = created_view(&model.view());
    let w = build(&frame, &created);
    OPEN.with(|o| {
        *o.borrow_mut() = Some(Rc::new(Open {
            id,
            model,
            w,
            shown: RefCell::new(created),
        }))
    });
    render(id);
    w.dialog.show(true);
    w.finder_mode.set_focus();
}

/// Close the dialog if it is open (app exit).
pub(crate) fn close_noaa_radio_dialog() {
    let Some(open) = OPEN.with(|o| o.borrow_mut().take()) else {
        return;
    };
    open.model.close();
    open.w.dialog.destroy();
}

/// Model events arrive on worker threads. Renders are coalesced: one is
/// queued at a time and reads the latest view when it runs.
fn event_handler(id: u64) -> DialogEventHandler {
    let pending = Arc::new(AtomicBool::new(false));
    Arc::new(move |event| match event {
        DialogEvent::Changed => {
            if !pending.swap(true, Ordering::SeqCst) {
                let pending = pending.clone();
                post_to_ui(move || {
                    pending.store(false, Ordering::SeqCst);
                    render(id);
                });
            }
        }
        DialogEvent::ShowMessage { title, message } => post_to_ui(move || {
            if let Some(open) = open_dialog().filter(|o| o.id == id) {
                message_box(
                    &open.w.dialog,
                    &message,
                    &title,
                    MessageDialogStyle::OK | MessageDialogStyle::IconInformation,
                );
            }
        }),
    })
}

fn render(id: u64) {
    let Some(open) = open_dialog().filter(|o| o.id == id) else {
        return;
    };
    let view = open.model.view();
    let ops = plan(&open.shown.borrow(), &view);
    for op in ops {
        apply(&open.w, op);
    }
    *open.shown.borrow_mut() = view;
}

fn apply(w: &Widgets, op: Op) {
    match op {
        Op::FinderMode(i) => w.finder_mode.set_selection(i as u32),
        Op::SearchLabel(text) => w.search_label.set_label(&text),
        Op::SearchHint(hint) => set_hint(&w.search_ctrl, &hint),
        Op::SearchText(text) => w.search_ctrl.change_value(&text),
        Op::ShowSearch(show) => {
            w.search_label.show(show);
            w.search_ctrl.show(show);
        }
        Op::State(update) => sync_choice(&w.state_choice, update),
        Op::ShowState(show) => {
            w.state_label.show(show);
            w.state_choice.show(show);
        }
        Op::SavedLocation(update) => sync_choice(&w.saved_location_choice, update),
        Op::ShowSavedLocation(show) => {
            w.saved_location_label.show(show);
            w.saved_location_choice.show(show);
        }
        Op::Station(update) => sync_choice(&w.station_choice, update),
        Op::StationLimit(i) => w.station_limit.set_selection(i as u32),
        Op::ShowUnavailable(checked) => w.show_unavailable.set_value(checked),
        Op::PlayLabel(label) => w.play_stop.set_label(&label),
        Op::PlayEnabled(enabled) => w.play_stop.enable(enabled),
        Op::NextStreamEnabled(enabled) => w.next_stream.enable(enabled),
        Op::PreferEnabled(enabled) => w.prefer.enable(enabled),
        Op::FavoriteLabel(label) => w.favorite.set_label(&label),
        Op::FavoriteEnabled(enabled) => w.favorite.enable(enabled),
        Op::Volume(value) => w.volume.set_value(value as i32),
        Op::Status(text) => w.status.set_label(&text),
        Op::Layout => w.panel.layout(),
    }
}

fn sync_choice(choice: &Choice, update: ChoiceUpdate) {
    let selection = match update {
        ChoiceUpdate::Select(selection) => selection,
        ChoiceUpdate::Reset(items, selection) => {
            choice.clear();
            for item in &items {
                choice.append(item);
            }
            selection
        }
    };
    // wxNOT_FOUND (-1) clears the selection; wxDragon takes the index as u32.
    choice.set_selection(selection.map_or(u32::MAX, |i| i as u32));
}

fn new_choice(panel: &Panel, items: &[String], selection: Option<usize>) -> Choice {
    let choice = Choice::builder(panel).with_choices(items.to_vec()).build();
    if let Some(i) = selection {
        choice.set_selection(i as u32);
    }
    choice
}

fn strings(items: &[&str]) -> Vec<String> {
    items.iter().map(|s| s.to_string()).collect()
}

/// `create_noaa_radio_widgets`, in creation (tab) order.
fn build(parent: &Frame, v: &DialogView) -> Widgets {
    let dialog = Dialog::builder(parent, DIALOG_TITLE)
        .with_style(DialogStyle::DefaultDialogStyle | DialogStyle::ResizeBorder)
        .with_size(450, 350)
        .build();
    let panel = Panel::builder(&dialog).build();
    let sizer = BoxSizer::builder(Orientation::Vertical).build();
    let row = SizerFlag::Left | SizerFlag::Right | SizerFlag::Top;
    let wide = row | SizerFlag::Expand;
    let label = |text: &str| StaticText::builder(&panel).with_label(text).build();

    sizer.add(&label(labels::FINDER_HEADING), 0, row, 10);
    sizer.add(&label(labels::SEARCH_MODE), 0, row, 10);
    let finder_mode = new_choice(&panel, &strings(&FINDER_MODE_LABELS), Some(v.finder_mode));
    sizer.add(&finder_mode, 0, wide, 10);

    let search_label = label(&v.search_label);
    sizer.add(&search_label, 0, row, 10);
    let find_sizer = BoxSizer::builder(Orientation::Horizontal).build();
    let search_ctrl = TextCtrl::builder(&panel)
        .with_style(TextCtrlStyle::ProcessEnter)
        .build();
    search_ctrl.set_name(labels::SEARCH_CTRL_NAME);
    set_hint(&search_ctrl, &v.search_hint);
    find_sizer.add(&search_ctrl, 1, SizerFlag::Right, 5);
    let find = Button::builder(&panel).with_label(labels::FIND).build();
    find_sizer.add(&find, 0, SizerFlag::Right, 5);
    let clear = Button::builder(&panel).with_label(labels::CLEAR).build();
    find_sizer.add(&clear, 0, SizerFlag::empty(), 0);
    sizer.add_sizer(&find_sizer, 0, wide, 10);

    let state_label = label(labels::STATE);
    sizer.add(&state_label, 0, row, 10);
    let state_choice = new_choice(&panel, &v.state_choices, Some(v.state_selection));
    sizer.add(&state_choice, 0, wide, 10);

    let saved_location_label = label(labels::SAVED_LOCATION);
    sizer.add(&saved_location_label, 0, row, 10);
    let saved_location_choice = new_choice(
        &panel,
        &v.saved_location_choices,
        v.saved_location_selection,
    );
    sizer.add(&saved_location_choice, 0, wide, 10);

    sizer.add(&label(labels::STATION_RESULTS), 0, row, 10);
    let station_choice = new_choice(&panel, &v.station_choices, v.station_selection);
    sizer.add(&station_choice, 0, wide, 10);

    sizer.add(&label(labels::MAXIMUM_RESULTS), 0, row, 10);
    let station_limit = new_choice(
        &panel,
        &strings(&STATION_LIMIT_LABELS),
        Some(v.station_limit_selection),
    );
    sizer.add(&station_limit, 0, wide, 10);

    let show_unavailable = CheckBox::builder(&panel)
        .with_label(labels::SHOW_UNAVAILABLE)
        .build();
    sizer.add(&show_unavailable, 0, row, 10);

    let buttons = BoxSizer::builder(Orientation::Horizontal).build();
    let button = |text: &str, enabled: bool| {
        let b = Button::builder(&panel).with_label(text).build();
        b.enable(enabled);
        buttons.add(&b, 0, SizerFlag::Right, 5);
        b
    };
    let play_stop = button(&v.play_label, v.play_enabled);
    let next_stream = button(labels::TRY_NEXT_STREAM, v.next_stream_enabled);
    let prefer = button(labels::SET_AS_PREFERRED, v.prefer_enabled);
    let favorite = button(&v.favorite_label, v.favorite_enabled);
    sizer.add_sizer(&buttons, 0, row, 10);

    sizer.add(&label(labels::VOLUME), 0, row, 10);
    let volume = Slider::builder(&panel)
        .with_value(v.volume as i32)
        .with_min_value(0)
        .with_max_value(100)
        .build();
    sizer.add(&volume, 0, wide, 10);

    let status = label(&v.status);
    sizer.add(&status, 0, SizerFlag::All, 10);

    let close = Button::builder(&panel)
        .with_id(ID_CLOSE)
        .with_label(labels::CLOSE)
        .build();
    sizer.add(
        &close,
        0,
        SizerFlag::AlignRight | SizerFlag::Right | SizerFlag::Bottom,
        10,
    );

    panel.set_sizer(sizer, true);
    let dialog_sizer = BoxSizer::builder(Orientation::Vertical).build();
    dialog_sizer.add(&panel, 1, SizerFlag::Expand, 0);
    dialog.set_sizer(dialog_sizer, true);

    let w = Widgets {
        dialog,
        panel,
        finder_mode,
        search_label,
        search_ctrl,
        state_label,
        state_choice,
        saved_location_label,
        saved_location_choice,
        station_choice,
        station_limit,
        show_unavailable,
        play_stop,
        next_stream,
        prefer,
        favorite,
        volume,
        status,
    };
    bind(&w, find, clear, close);
    w
}

fn selection(choice: &Choice) -> Option<usize> {
    choice.get_selection().map(|i| i as usize)
}

fn bind(w: &Widgets, find: Button, clear: Button, close: Button) {
    // Each input is recorded as shown, then handed to the model, so the next
    // render does not write it back to the widget.
    w.finder_mode.on_selection_changed(|_| {
        with_open(|o| {
            let index = selection(&o.w.finder_mode).unwrap_or(0);
            o.shown.borrow_mut().finder_mode = index;
            o.model.set_finder_mode(index);
        })
    });
    w.search_ctrl.on_text_changed(|_| {
        with_open(|o| {
            let text = o.w.search_ctrl.get_value();
            o.shown.borrow_mut().search_text = text.clone();
            o.model.set_search_text(&text);
        })
    });
    w.search_ctrl
        .on_text_enter(|_| with_open(|o| o.model.find()));
    find.on_click(|_| with_open(|o| o.model.find()));
    clear.on_click(|_| with_open(|o| o.model.clear_search()));
    w.state_choice.on_selection_changed(|_| {
        with_open(|o| {
            let index = selection(&o.w.state_choice).unwrap_or(0);
            o.shown.borrow_mut().state_selection = index;
            o.model.set_state_selection(index);
        })
    });
    w.saved_location_choice.on_selection_changed(|_| {
        with_open(|o| {
            let index = selection(&o.w.saved_location_choice);
            o.shown.borrow_mut().saved_location_selection = index;
            o.model.set_saved_location_selection(index);
        })
    });
    w.station_choice.on_selection_changed(|_| {
        with_open(|o| {
            let index = selection(&o.w.station_choice);
            o.shown.borrow_mut().station_selection = index;
            o.model.select_station(index);
        })
    });
    // Enter on the station results plays (or stops, or switches).
    w.station_choice
        .bind_internal(EventType::CHAR_HOOK, |e: Event| match e.get_key_code() {
            Some(WXK_RETURN | WXK_NUMPAD_ENTER) => {
                e.skip(false);
                with_open(|o| o.model.play_stop());
            }
            _ => e.skip(true),
        });
    w.station_limit.on_selection_changed(|_| {
        with_open(|o| {
            let index = selection(&o.w.station_limit).unwrap_or(0);
            o.shown.borrow_mut().station_limit_selection = index;
            o.model.set_station_limit_selection(index);
        })
    });
    w.show_unavailable.on_toggled(|e| {
        let checked = e.is_checked();
        with_open(|o| {
            o.shown.borrow_mut().show_unavailable = checked;
            o.model.set_show_unavailable(checked);
        })
    });
    w.play_stop.on_click(|_| with_open(|o| o.model.play_stop()));
    w.next_stream
        .on_click(|_| with_open(|o| o.model.next_stream()));
    w.prefer
        .on_click(|_| with_open(|o| o.model.set_preferred()));
    w.favorite
        .on_click(|_| with_open(|o| o.model.toggle_favorite()));
    w.volume.on_slider(|e| {
        let value = e.get_value().clamp(0, 100) as u32;
        with_open(|o| {
            o.shown.borrow_mut().volume = value;
            o.model.set_volume(value);
        })
    });

    close.on_click(|_| close_noaa_radio_dialog());
    w.dialog
        .bind_internal(EventType::CLOSE_WINDOW, |_| close_noaa_radio_dialog());
    w.dialog.bind_internal(EventType::CHAR_HOOK, |e: Event| {
        if e.get_key_code() == Some(WXK_ESCAPE) {
            e.skip(false);
            close_noaa_radio_dialog();
        } else {
            e.skip(true);
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn loaded() -> DialogView {
        DialogView {
            finder_mode: 0,
            search_label: labels::SEARCH_TEXT.into(),
            search_hint: labels::SEARCH_HINT.into(),
            search_text: String::new(),
            search_visible: true,
            state_choices: strings(&["All states and territories", "Texas (TX)"]),
            state_selection: 0,
            state_visible: false,
            saved_location_choices: strings(&["Austin"]),
            saved_location_selection: Some(0),
            saved_location_visible: false,
            station_choices: strings(&["AAA11 - One", "BBB22 - Two", "CCC33 - Three"]),
            station_selection: Some(0),
            station_limit_selection: 0,
            show_unavailable: false,
            play_label: labels::PLAY.into(),
            play_enabled: true,
            next_stream_enabled: false,
            prefer_enabled: false,
            favorite_label: labels::FAVORITE.into(),
            favorite_enabled: true,
            volume: 100,
            status: "Ready".into(),
        }
    }

    #[test]
    fn unchanged_view_touches_nothing() {
        assert_eq!(plan(&loaded(), &loaded()), []);
    }

    #[test]
    fn opening_applies_mode_controls_and_the_first_lookup() {
        // What `_update_finder_mode_controls` and `_load_stations_async`
        // change on the freshly created widgets.
        let view = DialogView {
            station_choices: strings(&[labels::LOADING_STATIONS]),
            station_selection: None,
            favorite_enabled: false,
            status: "Finding stations...".into(),
            ..loaded()
        };
        assert_eq!(
            plan(&created_view(&view), &view),
            [
                Op::SearchHint(labels::SEARCH_HINT.into()),
                Op::ShowState(false),
                Op::ShowSavedLocation(false),
                Op::Station(ChoiceUpdate::Reset(
                    strings(&[labels::LOADING_STATIONS]),
                    None
                )),
                Op::Status("Finding stations...".into()),
                Op::Layout,
            ]
        );
    }

    #[test]
    fn same_items_only_move_the_selection() {
        let view = DialogView {
            station_selection: Some(2),
            ..loaded()
        };
        assert_eq!(
            plan(&loaded(), &view),
            [Op::Station(ChoiceUpdate::Select(Some(2)))]
        );
        let cleared = DialogView {
            station_selection: None,
            ..loaded()
        };
        assert_eq!(
            plan(&loaded(), &cleared),
            [Op::Station(ChoiceUpdate::Select(None))]
        );
    }

    #[test]
    fn new_items_replace_the_list_and_keep_the_selection() {
        let mut view = loaded();
        view.station_choices[1] = "Favorite - BBB22 - Two".into();
        view.station_selection = Some(1);
        view.favorite_label = labels::REMOVE_FAVORITE.into();
        view.status = "BBB22 added to favorites".into();
        assert_eq!(
            plan(&loaded(), &view),
            [
                Op::Station(ChoiceUpdate::Reset(view.station_choices.clone(), Some(1))),
                Op::FavoriteLabel(labels::REMOVE_FAVORITE.into()),
                Op::Status("BBB22 added to favorites".into()),
            ]
        );
    }

    #[test]
    fn user_input_already_shown_is_not_written_back() {
        // The handler records the pick as shown before the model's view
        // catches up, so only the knock-on changes are applied.
        let mut shown = loaded();
        shown.station_selection = Some(1);
        shown.search_text = "Austin".into();
        shown.volume = 40;
        let view = DialogView {
            station_selection: Some(1),
            search_text: "Austin".into(),
            volume: 40,
            play_label: labels::SWITCH.into(),
            ..loaded()
        };
        assert_eq!(plan(&shown, &view), [Op::PlayLabel(labels::SWITCH.into())]);
    }

    #[test]
    fn finder_modes_show_hide_relabel_and_lay_out() {
        let coordinates = DialogView {
            finder_mode: 3,
            search_label: labels::COORDINATES.into(),
            search_hint: labels::COORDINATES_HINT.into(),
            ..loaded()
        };
        assert_eq!(
            plan(&loaded(), &coordinates),
            [
                Op::FinderMode(3),
                Op::SearchLabel(labels::COORDINATES.into()),
                Op::SearchHint(labels::COORDINATES_HINT.into()),
            ]
        );
        let by_state = DialogView {
            finder_mode: 2,
            search_visible: false,
            state_visible: true,
            ..loaded()
        };
        assert_eq!(
            plan(&loaded(), &by_state),
            [
                Op::FinderMode(2),
                Op::ShowSearch(false),
                Op::ShowState(true),
                Op::Layout,
            ]
        );
    }

    #[test]
    fn playback_state_updates_buttons_volume_and_status() {
        let playing = DialogView {
            play_label: labels::STOP.into(),
            next_stream_enabled: true,
            prefer_enabled: true,
            volume: 50,
            status: "Playing: AAA11 (stream 1 of 2)".into(),
            ..loaded()
        };
        assert_eq!(
            plan(&loaded(), &playing),
            [
                Op::PlayLabel(labels::STOP.into()),
                Op::NextStreamEnabled(true),
                Op::PreferEnabled(true),
                Op::Volume(50),
                Op::Status("Playing: AAA11 (stream 1 of 2)".into()),
            ]
        );
    }

    #[test]
    fn clear_resets_mode_text_and_choices() {
        let shown = DialogView {
            finder_mode: 4,
            search_visible: false,
            saved_location_visible: true,
            saved_location_selection: None,
            search_text: "x".into(),
            state_selection: 1,
            ..loaded()
        };
        assert_eq!(
            plan(&shown, &loaded()),
            [
                Op::FinderMode(0),
                Op::SearchText(String::new()),
                Op::ShowSearch(true),
                Op::State(ChoiceUpdate::Select(Some(0))),
                Op::SavedLocation(ChoiceUpdate::Select(Some(0))),
                Op::ShowSavedLocation(false),
                Op::Layout,
            ]
        );
    }
}
