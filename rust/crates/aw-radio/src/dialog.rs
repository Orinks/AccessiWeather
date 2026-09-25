//! Headless model of the NOAA Weather Radio dialog.
//!
//! Ports the logic of `ui/dialogs/noaa_radio_dialog.py`; the widget facts
//! (labels, choices, initial states) come from `noaa_radio_widgets.py`. The
//! UI builds the widgets, renders [`DialogView`] after every
//! [`DialogEvent::Changed`], and forwards user input to the methods here.
//!
//! Threading mirrors the Python dialog, whose handlers all ran on the wx
//! thread: playback actions and session callbacks run one at a time on a
//! private worker thread (so connecting never blocks the UI), station
//! lookups run on their own threads, and results come back through the
//! worker. `on_event` is called from those threads; the UI must hop to its
//! own thread (`post_to_ui`) before touching widgets.

use std::sync::mpsc::{self, Sender};
use std::sync::{Arc, Mutex, MutexGuard, OnceLock, Weak};
use std::thread::ThreadId;
use std::time::Duration;

use aw_core::Location;

use crate::availability::{StationAvailabilityCache, StationAvailabilityService};
use crate::player::PlayerEvent;
use crate::preferences::{SharedPreferences, DEFAULT_STATION_LIMIT};
use crate::session::RadioSession;
use crate::stations::{Station, StationDatabase};
use crate::stream_url::{StreamUrlProvider, StreamUrls};

pub const DIALOG_TITLE: &str = "NOAA Weather Radio";
pub const SUPPRESSION_TTL_SECONDS: u64 = 1800;
pub const HEALTH_CHECK_INTERVAL: Duration = Duration::from_millis(5000);

pub const STATION_LIMIT_PRESETS: [Option<usize>; 5] =
    [Some(10), Some(25), Some(50), Some(100), None];
pub const STATION_LIMIT_LABELS: [&str; 5] = ["10", "25", "50", "100", "All"];

pub const FINDER_MODE_SEARCH_ALL: &str = "Search all stations";
pub const FINDER_MODE_FAVORITES: &str = "Favorites";
pub const FINDER_MODE_BROWSE_STATE: &str = "Browse by state";
pub const FINDER_MODE_NEAREST: &str = "Nearest by coordinates";
pub const FINDER_MODE_SAVED_LOCATION: &str = "Nearby saved location";
pub const FINDER_MODE_LABELS: [&str; 5] = [
    FINDER_MODE_SEARCH_ALL,
    FINDER_MODE_FAVORITES,
    FINDER_MODE_BROWSE_STATE,
    FINDER_MODE_NEAREST,
    FINDER_MODE_SAVED_LOCATION,
];
pub const STATE_ALL_CHOICE: &str = "All states and territories";

/// Static text of the dialog's labels and buttons, in creation (tab)
/// order, for the UI to build widgets from.
pub mod labels {
    pub const FINDER_HEADING: &str = "Station Finder";
    pub const SEARCH_MODE: &str = "Search mode:";
    pub const SEARCH_TEXT: &str = "Search text (call sign, city, or state):";
    pub const COORDINATES: &str = "Coordinates (latitude, longitude):";
    /// `name=` of the search TextCtrl.
    pub const SEARCH_CTRL_NAME: &str = "NOAA radio station finder text";
    /// Hint set when the control is created, before the mode-specific one.
    pub const SEARCH_INITIAL_HINT: &str = "Call sign, city, state, or latitude, longitude";
    pub const SEARCH_HINT: &str = "Call sign, city, or state";
    pub const COORDINATES_HINT: &str = "Example: 30.2672, -97.7431";
    pub const FIND: &str = "Find";
    pub const CLEAR: &str = "Clear";
    pub const STATE: &str = "State or territory:";
    pub const SAVED_LOCATION: &str = "Saved location:";
    pub const STATION_RESULTS: &str = "Station results:";
    pub const MAXIMUM_RESULTS: &str = "Maximum results:";
    pub const SHOW_UNAVAILABLE: &str = "Show unavailable stations";
    pub const PLAY: &str = "Play";
    pub const STOP: &str = "Stop";
    pub const SWITCH: &str = "Switch";
    pub const TRY_NEXT_STREAM: &str = "Try Next Stream";
    pub const SET_AS_PREFERRED: &str = "Set as Preferred";
    pub const FAVORITE: &str = "Favorite";
    pub const REMOVE_FAVORITE: &str = "Remove Favorite";
    pub const VOLUME: &str = "Volume:";
    /// The Close button (`wx.ID_CLOSE`).
    pub const CLOSE: &str = "Close";
    pub const LOADING_STATIONS: &str = "Loading stations...";
    pub const STREAM_NOT_AVAILABLE_TITLE: &str = "Stream Not Available";
}

const STATE_TERRITORY_NAMES: &[(&str, &str)] = &[
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
    ("AS", "American Samoa"),
    ("GU", "Guam"),
    ("MP", "Northern Mariana Islands"),
    ("PR", "Puerto Rico"),
    ("VI", "U.S. Virgin Islands"),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FinderMode {
    SearchAll,
    Favorites,
    BrowseState,
    Nearest,
    SavedLocation,
}

impl FinderMode {
    /// The mode at a "Search mode" choice index (out of range → search all).
    pub fn from_index(index: usize) -> Self {
        match index {
            1 => Self::Favorites,
            2 => Self::BrowseState,
            3 => Self::Nearest,
            4 => Self::SavedLocation,
            _ => Self::SearchAll,
        }
    }

    pub fn index(self) -> usize {
        self as usize
    }

    pub fn label(self) -> &'static str {
        FINDER_MODE_LABELS[self.index()]
    }
}

/// "State or territory" choices: the "all" entry, then every state in the
/// station list as `"Texas (TX)"` (or the bare code when unnamed).
pub fn state_choices(db: &StationDatabase) -> Vec<String> {
    let mut states: Vec<String> = db.get_all_stations().into_iter().map(|s| s.state).collect();
    states.sort();
    states.dedup();
    std::iter::once(STATE_ALL_CHOICE.to_string())
        .chain(states.iter().map(|s| format_state_choice(s)))
        .collect()
}

pub fn format_state_choice(state_code: &str) -> String {
    match STATE_TERRITORY_NAMES
        .iter()
        .find(|(code, _)| *code == state_code)
    {
        Some((_, name)) => format!("{name} ({state_code})"),
        None => state_code.to_string(),
    }
}

/// The station database code from a state choice label.
pub fn state_choice_code(choice_label: &str) -> String {
    if choice_label.ends_with(')') {
        if let Some((_, code)) = choice_label.rsplit_once('(') {
            return code.trim_end_matches(')').to_string();
        }
    }
    choice_label.to_string()
}

/// `"lat, lon"` for nearest-station mode, range-checked.
pub fn parse_coordinate_query(query: &str) -> Option<(f64, f64)> {
    let (lat, lon) = query.split_once(',')?;
    let lat: f64 = lat.trim().parse().ok()?;
    let lon: f64 = lon.trim().parse().ok()?;
    ((-90.0..=90.0).contains(&lat) && (-180.0..=180.0).contains(&lon)).then_some((lat, lon))
}

/// The "Maximum results" index for a saved limit (unknown → 10).
pub fn station_limit_choice_index(limit: Option<usize>) -> usize {
    STATION_LIMIT_PRESETS
        .iter()
        .position(|p| *p == limit)
        .unwrap_or_else(|| {
            STATION_LIMIT_PRESETS
                .iter()
                .position(|p| *p == Some(DEFAULT_STATION_LIMIT))
                .unwrap_or(0)
        })
}

/// Result label with favorite context for screen readers.
pub fn format_station_choice_label(is_favorite: bool, label: &str) -> String {
    if is_favorite && !label.starts_with("Favorite - ") {
        format!("Favorite - {label}")
    } else {
        label.to_string()
    }
}

/// Status shown when a finder mode has no results.
pub fn empty_station_status(
    mode: FinderMode,
    has_favorites: bool,
    has_saved_locations: bool,
) -> &'static str {
    match mode {
        FinderMode::Favorites if has_favorites => "No favorite stations with streams available",
        FinderMode::Favorites => "No favorite stations yet",
        FinderMode::SavedLocation if has_saved_locations => {
            "No stations with streams available near that saved location"
        }
        FinderMode::SavedLocation => "No saved locations available",
        _ => "No stations with streams available",
    }
}

/// Everything a station lookup depends on.
#[derive(Debug, Clone, PartialEq)]
pub struct FinderQuery {
    pub mode: FinderMode,
    pub search_query: String,
    pub state_code: String,
    pub saved_location: Option<Location>,
    pub station_limit: Option<usize>,
    pub favorites: Vec<String>,
    /// The point the dialog was opened for, used when nearest-mode text is
    /// not a coordinate.
    pub origin: Option<(f64, f64)>,
}

/// Candidate stations for a finder query (before availability filtering).
pub fn find_candidates(db: &StationDatabase, query: &FinderQuery) -> Vec<Station> {
    let limited = |stations: Vec<Station>| match query.station_limit {
        Some(n) => stations.into_iter().take(n).collect(),
        None => stations,
    };
    let nearest = |lat, lon| -> Vec<Station> {
        db.find_nearest(lat, lon, query.station_limit)
            .into_iter()
            .map(|r| r.station)
            .collect()
    };
    match query.mode {
        FinderMode::Favorites if query.favorites.is_empty() => Vec::new(),
        FinderMode::Favorites => db.get_stations_by_call_signs(&query.favorites),
        FinderMode::BrowseState if !query.state_code.is_empty() => {
            limited(db.get_stations_by_state(&query.state_code))
        }
        FinderMode::BrowseState => db.search("", query.station_limit),
        FinderMode::Nearest => match parse_coordinate_query(&query.search_query).or(query.origin) {
            Some((lat, lon)) => nearest(lat, lon),
            None => Vec::new(),
        },
        FinderMode::SavedLocation => match &query.saved_location {
            Some(location) => nearest(location.latitude, location.longitude),
            None => Vec::new(),
        },
        FinderMode::SearchAll => db.search(&query.search_query, query.station_limit),
    }
}

/// Notifications to the UI.
#[derive(Debug, Clone, PartialEq)]
pub enum DialogEvent {
    /// Re-render from [`RadioDialog::view`].
    Changed,
    /// Show an information message box (`wx.OK | wx.ICON_INFORMATION`).
    ShowMessage { title: String, message: String },
}

/// The dialog's widget state, in creation order.
#[derive(Debug, Clone, PartialEq)]
pub struct DialogView {
    pub finder_mode: usize,
    pub search_label: String,
    pub search_hint: String,
    pub search_text: String,
    /// Search label and text box shown (search-all and coordinate modes).
    pub search_visible: bool,
    pub state_choices: Vec<String>,
    pub state_selection: usize,
    pub state_visible: bool,
    pub saved_location_choices: Vec<String>,
    pub saved_location_selection: Option<usize>,
    pub saved_location_visible: bool,
    pub station_choices: Vec<String>,
    pub station_selection: Option<usize>,
    pub station_limit_selection: usize,
    pub show_unavailable: bool,
    pub play_label: String,
    pub play_enabled: bool,
    pub next_stream_enabled: bool,
    pub prefer_enabled: bool,
    pub favorite_label: String,
    pub favorite_enabled: bool,
    /// Volume slider, 0–100.
    pub volume: u32,
    pub status: String,
}

struct Inner {
    view: DialogView,
    stations: Vec<Station>,
    base_labels: Vec<String>,
    current_urls: Vec<String>,
    current_url_index: usize,
    playing_station: Option<Station>,
    load_generation: u64,
    health_generation: u64,
    closed: bool,
}

impl Inner {
    fn selected_station(&self) -> Option<Station> {
        self.view
            .station_selection
            .and_then(|i| self.stations.get(i))
            .cloned()
    }

    /// `wx.Choice.Set`: new items, no selection.
    fn set_station_choices(&mut self, choices: Vec<String>) {
        self.view.station_choices = choices;
        self.view.station_selection = None;
    }
}

type Job = Box<dyn FnOnce(&RadioDialog) + Send>;
pub type DialogEventHandler = Arc<dyn Fn(DialogEvent) + Send + Sync>;

/// Everything the dialog needs from the app.
pub struct DialogDeps {
    pub session: Arc<RadioSession>,
    pub preferences: SharedPreferences,
    pub url_provider: Arc<StreamUrlProvider>,
    pub availability_cache: Arc<Mutex<StationAvailabilityCache>>,
    pub availability: Arc<StationAvailabilityService>,
    pub station_database: Arc<StationDatabase>,
}

pub struct RadioDialog {
    deps: DialogDeps,
    origin: Option<(f64, f64)>,
    saved_locations: Vec<Location>,
    inner: Mutex<Inner>,
    jobs: Mutex<Option<Sender<Job>>>,
    worker: OnceLock<ThreadId>,
    on_event: DialogEventHandler,
    this: Weak<RadioDialog>,
}

impl RadioDialog {
    /// Build the dialog model for an optional point (`lat`, `lon`) and the
    /// saved locations in display order, then start the first station
    /// lookup.
    pub fn open(
        deps: DialogDeps,
        lat: Option<f64>,
        lon: Option<f64>,
        saved_locations: Vec<Location>,
        on_event: DialogEventHandler,
    ) -> Arc<Self> {
        let origin = lat.zip(lon);
        let state_choices = state_choices(&deps.station_database);
        let limit = deps.preferences.lock().unwrap().get_station_limit();
        let session_state = deps.session.state();
        let view = DialogView {
            finder_mode: if origin.is_some() {
                FinderMode::Nearest
            } else {
                FinderMode::SearchAll
            }
            .index(),
            search_label: labels::SEARCH_TEXT.into(),
            search_hint: labels::SEARCH_INITIAL_HINT.into(),
            search_text: origin
                .map_or_else(String::new, |(lat, lon)| format!("{lat:.4}, {lon:.4}")),
            search_visible: true,
            state_choices,
            state_selection: 0,
            state_visible: true,
            saved_location_choices: saved_locations.iter().map(|l| l.name.clone()).collect(),
            saved_location_selection: (!saved_locations.is_empty()).then_some(0),
            saved_location_visible: true,
            station_choices: Vec::new(),
            station_selection: None,
            station_limit_selection: station_limit_choice_index(limit),
            show_unavailable: false,
            play_label: labels::PLAY.into(),
            play_enabled: true,
            next_stream_enabled: false,
            prefer_enabled: false,
            favorite_label: labels::FAVORITE.into(),
            favorite_enabled: false,
            volume: 100,
            status: "Ready".into(),
        };
        let (tx, rx) = mpsc::channel::<Job>();
        let dialog = Arc::new_cyclic(|this| Self {
            deps,
            origin,
            saved_locations,
            inner: Mutex::new(Inner {
                view,
                stations: Vec::new(),
                base_labels: Vec::new(),
                current_urls: session_state.current_urls,
                current_url_index: session_state.current_url_index,
                playing_station: session_state.playing_station,
                load_generation: 0,
                health_generation: 0,
                closed: false,
            }),
            jobs: Mutex::new(Some(tx)),
            worker: OnceLock::new(),
            on_event,
            this: this.clone(),
        });

        let weak = Arc::downgrade(&dialog);
        let worker = std::thread::Builder::new()
            .name("NoaaRadioDialog".into())
            .spawn(move || {
                for job in rx {
                    match weak.upgrade() {
                        Some(dialog) => job(&dialog),
                        None => break,
                    }
                }
            });
        match worker {
            Ok(handle) => {
                let _ = dialog.worker.set(handle.thread().id());
            }
            Err(e) => tracing::error!("could not start the NOAA radio dialog worker: {e}"),
        }

        let weak = Arc::downgrade(&dialog);
        dialog.deps.session.bind_callbacks(Arc::new(move |event| {
            if let Some(dialog) = weak.upgrade() {
                dialog.dispatch_session_event(event);
            }
        }));
        dialog.update_finder_mode_controls();
        dialog.sync_playback_state_from_session();
        dialog.load_stations_async();
        dialog
    }

    /// Current widget state.
    pub fn view(&self) -> DialogView {
        self.lock().view.clone()
    }

    // ----- user input ---------------------------------------------------

    /// "Search mode" choice changed.
    pub fn set_finder_mode(&self, index: usize) {
        self.lock().view.finder_mode = index;
        self.update_finder_mode_controls();
        self.load_stations_async();
    }

    /// Text typed in the search box (no lookup until Find / Enter).
    pub fn set_search_text(&self, text: &str) {
        self.lock().view.search_text = text.to_string();
    }

    /// "State or territory" choice (applied on Find).
    pub fn set_state_selection(&self, index: usize) {
        self.lock().view.state_selection = index;
    }

    /// "Saved location" choice (applied on Find).
    pub fn set_saved_location_selection(&self, index: Option<usize>) {
        self.lock().view.saved_location_selection = index;
    }

    /// Find button or Enter in the search box.
    pub fn find(&self) {
        self.load_stations_async();
    }

    /// Clear button: back to searching all stations.
    pub fn clear_search(&self) {
        {
            let mut inner = self.lock();
            inner.view.finder_mode = FinderMode::SearchAll.index();
            inner.view.state_selection = 0;
            if !self.saved_locations.is_empty() {
                inner.view.saved_location_selection = Some(0);
            }
            inner.view.search_text.clear();
        }
        self.update_finder_mode_controls();
        self.load_stations_async();
    }

    /// "Station results" choice changed.
    pub fn select_station(&self, index: Option<usize>) {
        {
            let mut inner = self.lock();
            inner.view.station_selection = index.filter(|i| *i < inner.view.station_choices.len());
        }
        self.update_play_btn_label();
        self.update_favorite_button_state();
        self.changed();
    }

    /// "Maximum results" changed: persist and reload.
    pub fn set_station_limit_selection(&self, index: usize) {
        self.lock().view.station_limit_selection = index;
        let limit = self.selected_station_limit();
        self.deps
            .preferences
            .lock()
            .unwrap()
            .set_station_limit(limit);
        self.load_stations_async();
    }

    /// "Show unavailable stations" toggled.
    pub fn set_show_unavailable(&self, show: bool) {
        self.lock().view.show_unavailable = show;
        self.load_stations_async();
    }

    /// Volume slider moved (0–100).
    pub fn set_volume(&self, value: u32) {
        let value = value.min(100);
        self.lock().view.volume = value;
        self.deps.session.player.set_volume(value as f64 / 100.0);
    }

    /// Play/Stop/Switch button, or Enter on the station results choice.
    pub fn play_stop(&self) {
        self.enqueue(Box::new(|d| d.on_play_stop()));
    }

    /// "Try Next Stream".
    pub fn next_stream(&self) {
        self.enqueue(Box::new(|d| d.on_next_stream()));
    }

    /// "Set as Preferred".
    pub fn set_preferred(&self) {
        self.enqueue(Box::new(|d| d.on_set_preferred()));
    }

    /// "Favorite" / "Remove Favorite".
    pub fn toggle_favorite(&self) {
        let selected = self.lock().selected_station();
        let Some(station) = selected else {
            self.set_status("No station selected");
            return;
        };
        let call_sign = &station.call_sign;
        let was_favorite = self
            .deps
            .preferences
            .lock()
            .unwrap()
            .is_favorite_station(call_sign);
        if was_favorite {
            self.deps
                .preferences
                .lock()
                .unwrap()
                .remove_favorite_station(call_sign);
            self.set_status(&format!("{call_sign} removed from favorites"));
            if self.finder_mode() == FinderMode::Favorites {
                self.load_stations_async();
            }
        } else {
            self.deps
                .preferences
                .lock()
                .unwrap()
                .add_favorite_station(call_sign);
            self.set_status(&format!("{call_sign} added to favorites"));
        }
        self.refresh_station_choice_labels();
        self.update_favorite_button_state();
        self.changed();
    }

    /// Close button, Escape or the window closing. Playback continues.
    pub fn close(&self) {
        {
            let mut inner = self.lock();
            inner.closed = true;
            inner.health_generation += 1;
        }
        self.deps.session.unbind_callbacks();
        self.jobs.lock().unwrap().take();
    }

    // ----- plumbing -----------------------------------------------------

    fn lock(&self) -> MutexGuard<'_, Inner> {
        self.inner.lock().unwrap()
    }

    fn changed(&self) {
        if !self.lock().closed {
            (self.on_event)(DialogEvent::Changed);
        }
    }

    fn enqueue(&self, job: Job) {
        if let Some(jobs) = self.jobs.lock().unwrap().as_ref() {
            let _ = jobs.send(job);
        }
    }

    fn on_worker(&self) -> bool {
        self.worker.get() == Some(&std::thread::current().id())
    }

    /// Session callbacks run inline when they come from our own actions
    /// and are queued otherwise (Python: direct call vs `wx.CallAfter`).
    fn dispatch_session_event(&self, event: PlayerEvent) {
        if self.on_worker() {
            self.handle_session_event(event);
        } else {
            self.enqueue(Box::new(move |d| d.handle_session_event(event)));
        }
    }

    fn handle_session_event(&self, event: PlayerEvent) {
        match event {
            PlayerEvent::Playing => self.on_playing(),
            PlayerEvent::Stopped => self.on_stopped(),
            PlayerEvent::Error(message) => self.on_error(&message),
            PlayerEvent::Stalled => self.set_status("Stream stalled, reconnecting..."),
            PlayerEvent::Reconnecting(attempt) => {
                self.set_status(&format!("Reconnecting (attempt {attempt})..."))
            }
        }
    }

    fn set_status(&self, text: &str) {
        {
            let mut inner = self.lock();
            if inner.closed {
                return;
            }
            inner.view.status = text.to_string();
        }
        self.changed();
    }

    fn finder_mode(&self) -> FinderMode {
        FinderMode::from_index(self.lock().view.finder_mode)
    }

    fn selected_station_limit(&self) -> Option<usize> {
        let index = self.lock().view.station_limit_selection;
        match STATION_LIMIT_PRESETS.get(index) {
            Some(limit) => *limit,
            None => self.deps.preferences.lock().unwrap().get_station_limit(),
        }
    }

    fn start_health_timer(&self) {
        let generation = {
            let mut inner = self.lock();
            inner.health_generation += 1;
            inner.health_generation
        };
        let weak = self.this.clone();
        let spawned = std::thread::Builder::new()
            .name("NoaaRadioHealth".into())
            .spawn(move || loop {
                std::thread::sleep(HEALTH_CHECK_INTERVAL);
                let Some(dialog) = weak.upgrade() else { return };
                let inner = dialog.lock();
                if inner.closed || inner.health_generation != generation {
                    return;
                }
                drop(inner);
                dialog.enqueue(Box::new(move |d| {
                    if d.lock().health_generation == generation {
                        d.on_health_check();
                    }
                }));
            });
        if let Err(e) = spawned {
            tracing::error!("could not start the NOAA radio health timer: {e}");
        }
    }

    fn stop_health_timer(&self) {
        self.lock().health_generation += 1;
    }

    // ----- station finder -----------------------------------------------

    fn update_finder_mode_controls(&self) {
        {
            let mut inner = self.lock();
            let mode = FinderMode::from_index(inner.view.finder_mode);
            let coordinate_mode = mode == FinderMode::Nearest;
            let view = &mut inner.view;
            view.search_label = if coordinate_mode {
                labels::COORDINATES
            } else {
                labels::SEARCH_TEXT
            }
            .into();
            view.search_hint = if coordinate_mode {
                labels::COORDINATES_HINT
            } else {
                labels::SEARCH_HINT
            }
            .into();
            view.search_visible = matches!(mode, FinderMode::SearchAll | FinderMode::Nearest);
            view.state_visible = mode == FinderMode::BrowseState;
            view.saved_location_visible = mode == FinderMode::SavedLocation;
        }
        self.changed();
    }

    fn load_stations_async(&self) {
        let has_favorites = !self
            .deps
            .preferences
            .lock()
            .unwrap()
            .get_favorite_stations()
            .is_empty();
        let (generation, mut query, show_unavailable, empty_status) = {
            let mut inner = self.lock();
            inner.load_generation += 1;
            inner.set_station_choices(vec![labels::LOADING_STATIONS.into()]);
            inner.view.status = "Finding stations...".into();
            let view = &inner.view;
            let mode = FinderMode::from_index(view.finder_mode);
            let state_code = match view.state_selection {
                0 => String::new(),
                i => view
                    .state_choices
                    .get(i)
                    .map(|c| state_choice_code(c))
                    .unwrap_or_default(),
            };
            let saved_location = view
                .saved_location_selection
                .and_then(|i| self.saved_locations.get(i))
                .cloned();
            let query = FinderQuery {
                mode,
                search_query: view.search_text.trim().to_string(),
                state_code,
                saved_location,
                station_limit: None,
                favorites: Vec::new(),
                origin: self.origin,
            };
            let empty = empty_station_status(mode, has_favorites, !self.saved_locations.is_empty());
            (inner.load_generation, query, view.show_unavailable, empty)
        };
        query.station_limit = self.selected_station_limit();
        self.changed();

        let weak = self.this.clone();
        let spawned = std::thread::Builder::new()
            .name("NoaaRadioStations".into())
            .spawn(move || {
                let Some(dialog) = weak.upgrade() else { return };
                query.favorites = dialog
                    .deps
                    .preferences
                    .lock()
                    .unwrap()
                    .get_favorite_stations();
                let candidates = find_candidates(&dialog.deps.station_database, &query);
                let entries = dialog
                    .deps
                    .availability
                    .build_entries(&candidates, show_unavailable);
                let stations: Vec<Station> = entries.iter().map(|e| e.station.clone()).collect();
                let choices: Vec<String> = entries.into_iter().map(|e| e.label).collect();
                let call_signs: Vec<String> =
                    stations.iter().map(|s| s.call_sign.clone()).collect();
                dialog.enqueue(Box::new(move |d| {
                    d.on_stations_loaded(stations, choices, empty_status, generation)
                }));
                // Warm stream lookups so pressing Play does not wait on HTTP.
                let provider = dialog.deps.url_provider.clone();
                drop(dialog);
                provider.prewarm_cache();
                provider.prewarm_stations(&call_signs);
            });
        if let Err(e) = spawned {
            self.set_status(&format!("Error loading stations: {e}"));
        }
    }

    fn on_stations_loaded(
        &self,
        stations: Vec<Station>,
        choices: Vec<String>,
        empty_status: &str,
        generation: u64,
    ) {
        let favorites = self
            .deps
            .preferences
            .lock()
            .unwrap()
            .get_favorite_stations();
        let session_playing = self.deps.session.playing_station();
        {
            let mut inner = self.lock();
            if inner.closed || inner.load_generation != generation {
                return;
            }
            let previous = inner.selected_station().map(|s| s.call_sign);
            let display: Vec<String> = stations
                .iter()
                .zip(&choices)
                .map(|(s, label)| {
                    format_station_choice_label(favorites.contains(&s.call_sign), label)
                })
                .collect();
            inner.set_station_choices(display);
            if !choices.is_empty() {
                let target = previous.or(session_playing.map(|s| s.call_sign));
                let selection = target
                    .and_then(|cs| stations.iter().position(|s| s.call_sign == cs))
                    .unwrap_or(0);
                inner.view.station_selection = Some(selection);
            }
            inner.stations = stations;
            inner.base_labels = choices;
        }
        self.sync_playback_state_from_session();
        self.update_favorite_button_state();
        if !self.deps.session.is_playing() {
            let has_results = !self.lock().stations.is_empty();
            self.set_status(if has_results { "Ready" } else { empty_status });
        }
        self.changed();
    }

    fn refresh_station_choice_labels(&self) {
        let favorites = self
            .deps
            .preferences
            .lock()
            .unwrap()
            .get_favorite_stations();
        let mut inner = self.lock();
        if inner.base_labels.len() != inner.stations.len() {
            return;
        }
        let selection = inner.view.station_selection;
        let labels: Vec<String> = inner
            .stations
            .iter()
            .zip(&inner.base_labels)
            .map(|(s, label)| format_station_choice_label(favorites.contains(&s.call_sign), label))
            .collect();
        let count = labels.len();
        inner.set_station_choices(labels);
        inner.view.station_selection = selection.filter(|i| *i < count);
    }

    fn update_favorite_button_state(&self) {
        let station = self.lock().selected_station();
        let favorite = station.as_ref().is_some_and(|s| {
            self.deps
                .preferences
                .lock()
                .unwrap()
                .is_favorite_station(&s.call_sign)
        });
        let mut inner = self.lock();
        inner.view.favorite_enabled = station.is_some();
        inner.view.favorite_label = if favorite {
            labels::REMOVE_FAVORITE
        } else {
            labels::FAVORITE
        }
        .into();
    }

    // ----- playback -----------------------------------------------------

    fn update_play_btn_label(&self) {
        let playing = self.deps.session.player.is_playing();
        let mut inner = self.lock();
        let label = if !playing {
            labels::PLAY
        } else {
            match (inner.selected_station(), &inner.playing_station) {
                (Some(selected), Some(on_air)) if selected.call_sign != on_air.call_sign => {
                    labels::SWITCH
                }
                (Some(_), None) => labels::SWITCH,
                _ => labels::STOP,
            }
        };
        inner.view.play_label = label.into();
    }

    fn sync_playback_state_from_session(&self) {
        let session = self.deps.session.state();
        let volume = (self.deps.session.player.get_volume() * 100.0).round_ties_even() as u32;
        let playing = self.deps.session.is_playing();
        let on_air = {
            let mut inner = self.lock();
            inner.current_urls = session.current_urls.clone();
            inner.current_url_index = session.current_url_index;
            inner.playing_station = session.playing_station.clone();
            inner.view.volume = volume;
            inner.playing_station.clone()
        };
        match on_air.filter(|_| playing) {
            Some(station) => {
                let status = playing_status(&station.call_sign, &session);
                self.set_status(&status);
                self.lock().view.play_enabled = true;
                self.update_play_btn_label();
                {
                    let mut inner = self.lock();
                    inner.view.next_stream_enabled = session.current_urls.len() > 1;
                    inner.view.prefer_enabled = !session.current_urls.is_empty();
                }
                self.update_favorite_button_state();
                self.start_health_timer();
            }
            None => {
                {
                    let mut inner = self.lock();
                    inner.view.play_label = labels::PLAY.into();
                    inner.view.next_stream_enabled = false;
                    inner.view.prefer_enabled = false;
                }
                self.update_favorite_button_state();
            }
        }
        self.changed();
    }

    fn on_play_stop(&self) {
        if !self.deps.session.player.is_playing() {
            return self.on_play();
        }
        let (selected, on_air) = {
            let inner = self.lock();
            (inner.selected_station(), inner.playing_station.clone())
        };
        match (selected, on_air) {
            (None, _) => self.on_stop(),
            (Some(s), Some(p)) if s.call_sign == p.call_sign => self.on_stop(),
            _ => self.on_play(),
        }
    }

    fn on_play(&self) {
        let player = &self.deps.session.player;
        if player.is_playing() {
            self.stop_health_timer();
            player.stop(false);
        }
        let selected = self.lock().selected_station();
        let Some(station) = selected else {
            self.set_status("No station selected");
            return;
        };
        let call_sign = station.call_sign.clone();
        let urls = self.deps.url_provider.get_stream_urls(&call_sign);
        if urls.is_empty() {
            self.set_status(&format!("No stream available for {call_sign}"));
            (self.on_event)(DialogEvent::ShowMessage {
                title: labels::STREAM_NOT_AVAILABLE_TITLE.into(),
                message: format!(
                    "No online stream is available for station {call_sign} ({}).\n\nNot all \
                     NOAA Weather Radio stations have online streams.",
                    station.name
                ),
            });
            return;
        }
        let urls = self
            .deps
            .preferences
            .lock()
            .unwrap()
            .reorder_urls(&call_sign, &urls);
        self.deps.session.update(|s| {
            s.playing_station = Some(station.clone());
            s.current_urls = urls.clone();
            s.current_url_index = 0;
        });
        {
            let mut inner = self.lock();
            inner.playing_station = Some(station);
            inner.current_urls = urls;
            inner.current_url_index = 0;
        }
        self.try_play_current(&call_sign);
    }

    /// Try the current URL, advancing through the rest on failure.
    fn try_play_current(&self, call_sign: &str) {
        loop {
            let (total, index, url) = {
                let inner = self.lock();
                let index = inner.current_url_index;
                (
                    inner.current_urls.len(),
                    index,
                    inner.current_urls[index].clone(),
                )
            };
            self.set_status(&format!(
                "Connecting to {call_sign} (stream {} of {total})...",
                index + 1
            ));
            if self.deps.session.player.play(&url) {
                self.clear_station_suppression(None);
                self.start_health_timer();
                {
                    let mut inner = self.lock();
                    inner.view.next_stream_enabled = total > 1;
                    inner.view.prefer_enabled = true;
                }
                self.changed();
                return;
            }
            if total <= 1 {
                self.mark_current_station_unavailable();
                self.set_status(&format!("Stream failed for {call_sign}"));
                return;
            }
            let next = (index + 1) % total;
            self.deps.session.update(|s| s.current_url_index = next);
            self.lock().current_url_index = next;
            if next == 0 {
                self.mark_current_station_unavailable();
                self.set_status(&format!("All streams failed for {call_sign}"));
                return;
            }
        }
    }

    fn on_stop(&self) {
        self.stop_health_timer();
        self.deps.session.stop(true);
        self.lock().view.play_label = labels::PLAY.into();
        self.changed();
    }

    fn on_playing(&self) {
        let session = self.deps.session.state();
        let station = {
            let mut inner = self.lock();
            inner.current_urls = session.current_urls.clone();
            inner.current_url_index = session.current_url_index;
            inner.playing_station = session
                .playing_station
                .clone()
                .or_else(|| inner.selected_station());
            inner.playing_station.clone()
        };
        self.clear_station_suppression(station.clone());
        let name = station.map_or_else(|| "Unknown".to_string(), |s| s.call_sign);
        self.set_status(&playing_status(&name, &session));
        {
            let mut inner = self.lock();
            inner.view.play_enabled = true;
            inner.view.play_label = labels::STOP.into();
            inner.view.next_stream_enabled = session.current_urls.len() > 1;
        }
        self.changed();
    }

    fn on_stopped(&self) {
        self.lock().playing_station = None;
        self.deps.session.update(|s| s.playing_station = None);
        self.set_status("Stopped");
        {
            let mut inner = self.lock();
            inner.view.play_enabled = true;
            inner.view.play_label = labels::PLAY.into();
            inner.view.next_stream_enabled = false;
            inner.view.prefer_enabled = false;
        }
        self.update_favorite_button_state();
        self.changed();
    }

    fn on_error(&self, message: &str) {
        self.lock().playing_station = None;
        self.deps.session.update(|s| s.playing_station = None);
        self.stop_health_timer();
        self.set_status(&format!("Error: {message}"));
        {
            let mut inner = self.lock();
            inner.view.play_enabled = true;
            inner.view.play_label = labels::PLAY.into();
            inner.view.next_stream_enabled = inner.current_urls.len() > 1;
            inner.view.prefer_enabled = false;
        }
        self.update_favorite_button_state();
        self.changed();
    }

    fn on_set_preferred(&self) {
        let (station, urls, index) = {
            let inner = self.lock();
            (
                inner.selected_station(),
                inner.current_urls.clone(),
                inner.current_url_index,
            )
        };
        let Some(station) = station.filter(|_| !urls.is_empty()) else {
            return;
        };
        self.deps
            .preferences
            .lock()
            .unwrap()
            .set_preferred_url(&station.call_sign, &urls[index]);
        self.set_status(&format!(
            "Preferred stream {} of {} saved for {}",
            index + 1,
            urls.len(),
            station.call_sign
        ));
    }

    /// Advance the stream index; returns `(url, name, position, total)`.
    fn advance_stream(&self) -> (String, String, usize, usize) {
        let (url, station, index, total) = {
            let mut inner = self.lock();
            let total = inner.current_urls.len();
            let index = (inner.current_url_index + 1) % total;
            inner.current_url_index = index;
            (
                inner.current_urls[index].clone(),
                inner.selected_station(),
                index,
                total,
            )
        };
        self.deps.session.update(|s| s.current_url_index = index);
        let name = station.map_or_else(|| "Unknown".to_string(), |s| s.call_sign);
        (url, name, index + 1, total)
    }

    fn on_next_stream(&self) {
        if self.lock().current_urls.is_empty() {
            return;
        }
        self.stop_health_timer();
        self.deps.session.player.stop(false); // no button flicker mid-switch
        let (url, name, position, total) = self.advance_stream();
        self.set_status(&format!(
            "Switching {name} to stream {position} of {total}..."
        ));
        if self.deps.session.player.play(&url) {
            self.start_health_timer();
        }
    }

    fn on_health_check(&self) {
        self.deps
            .session
            .player
            .check_health(|| self.auto_advance_stream());
    }

    /// The stream has been silent for three checks: try the next one.
    fn auto_advance_stream(&self) {
        if self.lock().current_urls.len() <= 1 {
            self.set_status("Stream has no audio");
            return;
        }
        let (url, name, position, total) = self.advance_stream();
        self.set_status(&format!(
            "No audio detected, trying {name} stream {position} of {total}..."
        ));
        self.deps.session.player.stop(false);
        if !self.deps.session.player.play(&url) {
            self.set_status("All streams failed");
            self.stop_health_timer();
        }
    }

    fn mark_current_station_unavailable(&self) {
        let station = {
            let inner = self.lock();
            inner
                .playing_station
                .clone()
                .or_else(|| inner.selected_station())
        };
        if let Some(station) = station {
            self.deps.availability_cache.lock().unwrap().suppress(
                &station.call_sign,
                SUPPRESSION_TTL_SECONDS,
                "all_streams_failed",
            );
        }
    }

    fn clear_station_suppression(&self, station: Option<Station>) {
        let station = station.or_else(|| {
            let inner = self.lock();
            inner
                .playing_station
                .clone()
                .or_else(|| inner.selected_station())
        });
        if let Some(station) = station {
            self.deps
                .availability_cache
                .lock()
                .unwrap()
                .clear(&station.call_sign);
        }
    }
}

/// `"Playing: KEC49 (stream 2 of 3)"`; the stream part only with several.
fn playing_status(name: &str, session: &crate::session::SessionState) -> String {
    let total = session.current_urls.len();
    if total > 1 {
        format!(
            "Playing: {name} (stream {} of {total})",
            session.current_url_index + 1
        )
    } else {
        format!("Playing: {name}")
    }
}

#[cfg(test)]
mod tests;
