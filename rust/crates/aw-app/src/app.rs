//! Application wiring: config, weather client, speech and the Slint UI.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::Arc;
use std::time::Duration;

use aw_core::presenter::{WeatherPresentation, WeatherPresenter};
use aw_core::settings::AppConfig;
use aw_core::weather::WeatherData;
use aw_core::Location;
use aw_providers::geocoding::Geocoder;
use aw_providers::{HttpClient, ReqwestClient, WeatherClient};
use aw_speech::Speaker;
use aw_store::Paths;
use slint::{ComponentHandle, ModelRc, SharedString, StandardListViewItem, VecModel};

use crate::cli::Args;

slint::include_modules!();

const SMOKE_DURATION: Duration = Duration::from_millis(2500);

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error(transparent)]
    Store(#[from] aw_store::StoreError),
    #[error(transparent)]
    Http(#[from] aw_providers::HttpError),
    #[error("UI error: {0}")]
    Ui(String),
    #[error("self-check failed: {0}")]
    Check(String),
}

impl From<slint::PlatformError> for AppError {
    fn from(e: slint::PlatformError) -> Self {
        AppError::Ui(e.to_string())
    }
}

/// Everything the UI callbacks need, shared on the main thread.
struct State {
    paths: Paths,
    config: AppConfig,
    client: WeatherClient,
    speaker: Speaker,
    last_data: Option<WeatherData>,
    last_presentation: Option<WeatherPresentation>,
    dialogs: Vec<Box<dyn std::any::Any>>,
    refresh_timer: slint::Timer,
    smoke: bool,
}

type Shared = Rc<RefCell<State>>;

thread_local! {
    /// Main-thread handle to the app state for closures posted from worker threads.
    static APP_STATE: RefCell<Option<Shared>> = const { RefCell::new(None) };
    /// Locations behind the rows currently shown in the Add Location dialog.
    static SEARCH_RESULTS: RefCell<Vec<Location>> = const { RefCell::new(Vec::new()) };
}

fn with_state() -> Option<Shared> {
    APP_STATE.with(|s| s.borrow().clone())
}

pub fn run(args: Args) -> Result<(), AppError> {
    let paths = Paths::resolve(args.config_dir.clone(), args.portable)?;
    if args.print_paths {
        println!("config_dir: {}", paths.config_dir.display());
        println!("config_file: {}", paths.config_file().display());
        println!("state_dir: {}", paths.state_dir().display());
        println!("cache_dir: {}", paths.cache_dir().display());
        println!("portable: {}", paths.portable);
        return Ok(());
    }

    let mut config = aw_store::load_config(&paths.config_file())?;
    config.normalize();
    tracing::info!(
        "loaded {} saved location(s) from {}",
        config.locations.len(),
        paths.config_file().display()
    );

    let offline = args.offline || args.smoke || args.check;
    let http: Arc<dyn HttpClient> = if offline {
        crate::fixtures::offline_client()
    } else {
        Arc::new(ReqwestClient::new()?)
    };
    let client = WeatherClient::new(http);

    if args.check {
        return self_check(&config, &client);
    }

    if (args.smoke || args.offline) && config.locations.is_empty() {
        config.upsert_location(
            Location::new("Philadelphia, Pennsylvania", 39.9526, -75.1652).with_country("US"),
        );
    }

    let speaker = if args.smoke {
        Speaker::null()
    } else {
        Speaker::native_or_null()
    };

    let ui = MainWindow::new()?;
    let state: Shared = Rc::new(RefCell::new(State {
        paths,
        config,
        client,
        speaker,
        last_data: None,
        last_presentation: None,
        dialogs: Vec::new(),
        refresh_timer: slint::Timer::default(),
        smoke: args.smoke,
    }));

    APP_STATE.with(|s| *s.borrow_mut() = Some(state.clone()));
    wire_main_window(&ui, &state);
    sync_locations(&ui, &state.borrow());
    schedule_refresh_timer(&ui, &state);

    if state.borrow().config.current_location.is_some() {
        start_refresh(&ui, &state);
    } else {
        set_status(
            &ui,
            "No saved locations. Press Alt+A or use Add to search for one.",
        );
    }

    let smoke_timer = slint::Timer::default();
    if args.smoke {
        smoke_timer.start(slint::TimerMode::SingleShot, SMOKE_DURATION, || {
            tracing::info!("smoke run complete");
            let _ = slint::quit_event_loop();
        });
    }

    ui.run()?;
    let speaker = state.borrow().speaker.clone();
    speaker.shutdown();
    if state.borrow().smoke {
        let st = state.borrow();
        if st.last_data.is_none() {
            return Err(AppError::Check(
                "smoke run never received weather data".into(),
            ));
        }
    }
    Ok(())
}

fn self_check(config: &AppConfig, client: &WeatherClient) -> Result<(), AppError> {
    let location = config
        .current_location
        .clone()
        .unwrap_or_else(|| Location::new("Philadelphia", 39.9526, -75.1652).with_country("US"));
    let data = client.fetch(&config.settings, &location);
    if !data.has_any_data() {
        return Err(AppError::Check(format!(
            "no weather data from fixtures: {:?}",
            data.failed_sources
        )));
    }
    let presentation = WeatherPresenter::new(&config.settings).present(&data);
    println!("{}", presentation.summary_text);
    println!("{}", presentation.current_text);
    println!("sources: {}", data.sources.join(", "));
    Ok(())
}

// ---------------------------------------------------------------------------
// Main window
// ---------------------------------------------------------------------------

fn wire_main_window(ui: &MainWindow, state: &Shared) {
    let weak = ui.as_weak();

    {
        let (weak, state) = (weak.clone(), state.clone());
        ui.on_refresh(move || {
            if let Some(ui) = weak.upgrade() {
                start_refresh(&ui, &state);
            }
        });
    }
    {
        let (weak, state) = (weak.clone(), state.clone());
        ui.on_location_changed(move |index| {
            let Some(ui) = weak.upgrade() else { return };
            let name = {
                let mut st = state.borrow_mut();
                let Some(loc) = st.config.locations.get(index.max(0) as usize).cloned() else {
                    return;
                };
                st.config.set_current_location(&loc.name);
                if let Err(e) = aw_store::save_config(&st.paths.config_file(), &st.config) {
                    tracing::error!("saving config: {e}");
                }
                loc.name
            };
            set_status(&ui, &format!("Selected {name}. Refreshing…"));
            start_refresh(&ui, &state);
        });
    }
    {
        let (weak, state) = (weak.clone(), state.clone());
        ui.on_add_location(move || {
            if let Some(ui) = weak.upgrade() {
                open_add_location(&ui, &state);
            }
        });
    }
    {
        let (weak, state) = (weak.clone(), state.clone());
        ui.on_remove_location(move || {
            let Some(ui) = weak.upgrade() else { return };
            let removed = {
                let mut st = state.borrow_mut();
                let Some(current) = st.config.current_location.clone() else {
                    return;
                };
                st.config.remove_location(&current.name);
                st.config.normalize();
                if let Err(e) = aw_store::save_config(&st.paths.config_file(), &st.config) {
                    tracing::error!("saving config: {e}");
                }
                st.last_data = None;
                st.last_presentation = None;
                current.name
            };
            sync_locations(&ui, &state.borrow());
            clear_weather(&ui);
            announce(&ui, &state, &format!("Removed {removed}."));
            if state.borrow().config.current_location.is_some() {
                start_refresh(&ui, &state);
            }
        });
    }
    {
        let (weak, state) = (weak.clone(), state.clone());
        ui.on_open_settings(move || {
            if let Some(ui) = weak.upgrade() {
                open_settings(&ui, &state);
            }
        });
    }
    {
        let state = state.clone();
        ui.on_speak_current(move || {
            let st = state.borrow();
            let text = st
                .last_presentation
                .as_ref()
                .map(|p| format!("{}\n{}", p.summary_text, p.current_text))
                .unwrap_or_else(|| "No weather data loaded yet.".to_string());
            st.speaker.speak(text, true);
        });
    }
    {
        let state = state.clone();
        ui.on_stop_speech(move || state.borrow().speaker.stop());
    }
    {
        let (weak, state) = (weak.clone(), state.clone());
        ui.on_show_alert_details(move |index| {
            let Some(ui) = weak.upgrade() else { return };
            let (label, detail) = {
                let st = state.borrow();
                let Some(p) = &st.last_presentation else {
                    return;
                };
                let idx = index.max(0) as usize;
                match (p.alert_labels.get(idx), p.alert_details.get(idx)) {
                    (Some(l), Some(d)) => (l.clone(), d.clone()),
                    _ => return,
                }
            };
            open_text_dialog(&ui, &state, &label, &detail, "Alert details");
        });
    }
    {
        let (weak, state) = (weak.clone(), state.clone());
        ui.on_show_discussion(move || {
            let Some(ui) = weak.upgrade() else { return };
            let text = state
                .borrow()
                .last_data
                .as_ref()
                .and_then(|d| d.discussion.clone());
            match text {
                Some(t) => open_text_dialog(
                    &ui,
                    &state,
                    "Area Forecast Discussion",
                    &t,
                    "Forecast discussion text",
                ),
                None => set_status(
                    &ui,
                    "No forecast discussion is available for this location.",
                ),
            }
        });
    }
    ui.on_quit(|| {
        let _ = slint::quit_event_loop();
    });
}

fn sync_locations(ui: &MainWindow, st: &State) {
    let names: Vec<SharedString> = st
        .config
        .locations
        .iter()
        .map(|l| SharedString::from(l.name.as_str()))
        .collect();
    let current = st
        .config
        .current_location
        .as_ref()
        .and_then(|c| st.config.locations.iter().position(|l| l.name == c.name))
        .map_or(-1, |i| i as i32);
    let app = ui.global::<AppState>();
    app.set_location_names(ModelRc::new(VecModel::from(names)));
    app.set_current_location_index(current);
}

fn clear_weather(ui: &MainWindow) {
    let app = ui.global::<AppState>();
    app.set_summary_text("No location selected. Press Alt+A to add a location.".into());
    app.set_current_text("".into());
    app.set_hourly_text("".into());
    app.set_daily_text("".into());
    app.set_alerts(ModelRc::new(VecModel::from(vec![
        StandardListViewItem::from("No active alerts"),
    ])));
    app.set_alert_count(0);
    app.set_selected_alert_index(-1);
    app.set_has_discussion(false);
}

fn set_status(ui: &MainWindow, text: &str) {
    ui.global::<AppState>().set_status_text(text.into());
}

/// Update the status line and, if enabled, speak it.
fn announce(ui: &MainWindow, state: &Shared, text: &str) {
    set_status(ui, text);
    let st = state.borrow();
    if st.config.settings.speech_announcements {
        st.speaker.speak(text, true);
    }
}

fn schedule_refresh_timer(ui: &MainWindow, state: &Shared) {
    let minutes = state.borrow().config.settings.update_interval_minutes();
    let weak = ui.as_weak();
    let state_for_timer = state.clone();
    state.borrow().refresh_timer.start(
        slint::TimerMode::Repeated,
        Duration::from_secs(minutes * 60),
        move || {
            if let Some(ui) = weak.upgrade() {
                start_refresh(&ui, &state_for_timer);
            }
        },
    );
}

fn start_refresh(ui: &MainWindow, state: &Shared) {
    let (location, settings, client) = {
        let st = state.borrow();
        let Some(loc) = st.config.current_location.clone() else {
            set_status(ui, "Add a location first.");
            return;
        };
        (loc, st.config.settings.clone(), st.client.clone())
    };
    let app = ui.global::<AppState>();
    if app.get_busy() {
        return;
    }
    app.set_busy(true);
    set_status(ui, &format!("Refreshing weather for {}…", location.name));

    let weak = ui.as_weak();
    std::thread::Builder::new()
        .name("aw-refresh".into())
        .spawn(move || {
            let data = client.fetch(&settings, &location);
            let presentation = WeatherPresenter::new(&settings).present(&data);
            let _ = slint::invoke_from_event_loop(move || {
                let Some(ui) = weak.upgrade() else { return };
                let Some(state) = with_state() else { return };
                apply_weather(&ui, &state, data, presentation);
            });
        })
        .expect("spawn refresh thread");
}

fn apply_weather(
    ui: &MainWindow,
    state: &Shared,
    data: WeatherData,
    presentation: WeatherPresentation,
) {
    let app = ui.global::<AppState>();
    app.set_busy(false);
    app.set_summary_text(presentation.summary_text.as_str().into());
    app.set_current_text(presentation.current_text.as_str().into());
    app.set_hourly_text(presentation.hourly_text.as_str().into());
    app.set_daily_text(presentation.daily_text.as_str().into());
    let alert_items: Vec<StandardListViewItem> = if presentation.alert_labels.is_empty() {
        vec![StandardListViewItem::from("No active alerts")]
    } else {
        presentation
            .alert_labels
            .iter()
            .map(|l| StandardListViewItem::from(l.as_str()))
            .collect()
    };
    app.set_alerts(ModelRc::new(VecModel::from(alert_items)));
    app.set_alert_count(presentation.alert_labels.len() as i32);
    app.set_selected_alert_index(if presentation.alert_labels.is_empty() {
        -1
    } else {
        0
    });
    app.set_has_discussion(data.discussion.is_some());

    let mut status = presentation.summary_text.clone();
    if !presentation.status_messages.is_empty() {
        status.push_str(" — ");
        status.push_str(&presentation.status_messages.join("; "));
    }
    if !data.has_any_data() {
        status = format!(
            "Could not load weather for {}. {}",
            data.location.name,
            data.failed_sources
                .iter()
                .map(|(s, e)| format!("{s}: {e}"))
                .collect::<Vec<_>>()
                .join("; ")
        );
    }

    {
        let mut st = state.borrow_mut();
        // Persist NWS metadata (zones, office) learned during the fetch.
        if let Some(saved) = st
            .config
            .locations
            .iter_mut()
            .find(|l| l.name == data.location.name)
        {
            if saved.forecast_zone_id.is_none() && data.location.forecast_zone_id.is_some() {
                *saved = data.location.clone();
                st.config.current_location = Some(data.location.clone());
                if let Err(e) = aw_store::save_config(&st.paths.config_file(), &st.config) {
                    tracing::warn!("saving location metadata: {e}");
                }
            }
        }
        st.last_data = Some(data);
        st.last_presentation = Some(presentation);
    }
    announce(ui, state, &status);
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

fn open_text_dialog(ui: &MainWindow, state: &Shared, heading: &str, body: &str, label: &str) {
    let Ok(dlg) = TextDialog::new() else {
        set_status(ui, "Could not open dialog.");
        return;
    };
    dlg.set_heading(heading.into());
    dlg.set_body(body.into());
    dlg.set_body_label(label.into());
    {
        let weak = dlg.as_weak();
        dlg.on_close_dialog(move || {
            if let Some(d) = weak.upgrade() {
                let _ = d.hide();
            }
        });
    }
    {
        let state = state.clone();
        let text = format!("{heading}. {body}");
        dlg.on_speak(move || state.borrow().speaker.speak(text.clone(), true));
    }
    if dlg.show().is_ok() {
        state.borrow_mut().dialogs.push(Box::new(dlg));
    }
}

fn open_add_location(ui: &MainWindow, state: &Shared) {
    let Ok(dlg) = AddLocationDialog::new() else {
        set_status(ui, "Could not open the Add Location dialog.");
        return;
    };
    SEARCH_RESULTS.with(|r| r.borrow_mut().clear());

    {
        let weak = dlg.as_weak();
        let state = state.clone();
        dlg.on_search(move |query| {
            let Some(d) = weak.upgrade() else { return };
            let query = query.to_string();
            if query.trim().is_empty() {
                d.set_status("Enter a place name, address or coordinates first.".into());
                return;
            }
            d.set_searching(true);
            d.set_status(format!("Searching for \"{query}\"…").into());
            let client = state.borrow().client.clone();
            let weak = weak.clone();
            std::thread::Builder::new()
                .name("aw-geocode".into())
                .spawn(move || {
                    let outcome = Geocoder::new(client.http()).search(&query, 8);
                    let _ = slint::invoke_from_event_loop(move || {
                        let Some(d) = weak.upgrade() else { return };
                        d.set_searching(false);
                        match outcome {
                            Ok(found) if found.is_empty() => {
                                d.set_status(format!("No matches for \"{query}\".").into());
                                d.set_results(ModelRc::new(VecModel::from(Vec::<
                                    StandardListViewItem,
                                >::new(
                                ))));
                                d.set_selected_index(-1);
                            }
                            Ok(found) => {
                                let items: Vec<StandardListViewItem> = found
                                    .iter()
                                    .map(|r| StandardListViewItem::from(r.display_name.as_str()))
                                    .collect();
                                d.set_status(
                                    format!(
                                        "{} result{} found. Use the arrow keys to choose one, then press Enter.",
                                        found.len(),
                                        if found.len() == 1 { "" } else { "s" }
                                    )
                                    .into(),
                                );
                                d.set_results(ModelRc::new(VecModel::from(items)));
                                d.set_selected_index(0);
                                SEARCH_RESULTS.with(|r| {
                                    *r.borrow_mut() =
                                        found.into_iter().map(|r| r.location).collect()
                                });
                            }
                            Err(e) => d.set_status(format!("Search failed: {e}").into()),
                        }
                    });
                })
                .expect("spawn geocode thread");
        });
    }
    {
        let weak = dlg.as_weak();
        let ui_weak = ui.as_weak();
        let state = state.clone();
        dlg.on_accept_selection(move |index, custom_name| {
            let Some(d) = weak.upgrade() else { return };
            let Some(ui) = ui_weak.upgrade() else { return };
            let picked = SEARCH_RESULTS.with(|r| r.borrow().get(index.max(0) as usize).cloned());
            let Some(mut loc) = picked else {
                d.set_status("Choose a search result first.".into());
                return;
            };
            let custom = custom_name.trim();
            if !custom.is_empty() {
                loc.name = custom.to_string();
            }
            {
                let mut st = state.borrow_mut();
                st.config.upsert_location(loc.clone());
                st.config.set_current_location(&loc.name);
                if let Err(e) = aw_store::save_config(&st.paths.config_file(), &st.config) {
                    tracing::error!("saving config: {e}");
                    d.set_status(format!("Could not save location: {e}").into());
                    return;
                }
            }
            let _ = d.hide();
            sync_locations(&ui, &state.borrow());
            announce(&ui, &state, &format!("Added {}. Refreshing…", loc.name));
            start_refresh(&ui, &state);
        });
    }
    {
        let weak = dlg.as_weak();
        dlg.on_cancel(move || {
            if let Some(d) = weak.upgrade() {
                let _ = d.hide();
            }
        });
    }
    if dlg.show().is_ok() {
        state.borrow_mut().dialogs.push(Box::new(dlg));
    }
}

const TEMP_UNITS: [&str; 3] = ["f", "c", "both"];
const SOURCES: [&str; 4] = ["auto", "nws", "openmeteo", "pirateweather"];
const VERBOSITY: [&str; 3] = ["minimal", "standard", "detailed"];
const BUDGETS: [&str; 3] = ["economy", "balanced", "max_coverage"];

fn index_of(options: &[&str], value: &str, default: i32) -> i32 {
    options
        .iter()
        .position(|o| o.eq_ignore_ascii_case(value.trim()))
        .map_or(default, |i| i as i32)
}

fn pick<'a>(options: &[&'a str], index: i32) -> &'a str {
    options[(index.max(0) as usize).min(options.len() - 1)]
}

fn open_settings(ui: &MainWindow, state: &Shared) {
    let Ok(dlg) = SettingsDialog::new() else {
        set_status(ui, "Could not open the Settings dialog.");
        return;
    };
    {
        let s = &state.borrow().config.settings;
        dlg.set_temperature_unit_index(index_of(&TEMP_UNITS, &s.temperature_unit, 2));
        dlg.set_data_source_index(index_of(&SOURCES, &s.data_source, 0));
        dlg.set_update_interval(s.update_interval_minutes() as i32);
        dlg.set_forecast_days(s.forecast_days() as i32);
        dlg.set_hourly_hours(s.hourly_hours().min(48) as i32);
        dlg.set_verbosity_index(index_of(&VERBOSITY, &s.verbosity_level, 1));
        dlg.set_enable_alerts(s.enable_alerts);
        dlg.set_speech_announcements(s.speech_announcements);
        dlg.set_show_dewpoint(s.show_dewpoint);
        dlg.set_show_pressure(s.show_pressure_trend);
        dlg.set_show_visibility(s.show_visibility);
        dlg.set_show_uv(s.show_uv_index);
        dlg.set_minimize_to_tray(s.minimize_to_tray);
        dlg.set_pirate_key(s.pirate_weather_api_key.as_str().into());
        dlg.set_budget_index(index_of(&BUDGETS, &s.auto_mode_api_budget, 2));
    }
    {
        let weak = dlg.as_weak();
        let ui_weak = ui.as_weak();
        let state = state.clone();
        dlg.on_save(move || {
            let Some(d) = weak.upgrade() else { return };
            let Some(ui) = ui_weak.upgrade() else { return };
            let interval_changed;
            {
                let mut st = state.borrow_mut();
                let s = &mut st.config.settings;
                let old_interval = s.update_interval_minutes;
                s.temperature_unit = pick(&TEMP_UNITS, d.get_temperature_unit_index()).into();
                s.data_source = pick(&SOURCES, d.get_data_source_index()).into();
                s.update_interval_minutes = d.get_update_interval() as i64;
                s.forecast_duration_days = d.get_forecast_days() as i64;
                s.hourly_forecast_hours = d.get_hourly_hours() as i64;
                s.verbosity_level = pick(&VERBOSITY, d.get_verbosity_index()).into();
                s.enable_alerts = d.get_enable_alerts();
                s.speech_announcements = d.get_speech_announcements();
                s.show_dewpoint = d.get_show_dewpoint();
                s.show_pressure_trend = d.get_show_pressure();
                s.show_visibility = d.get_show_visibility();
                s.show_uv_index = d.get_show_uv();
                s.minimize_to_tray = d.get_minimize_to_tray();
                s.pirate_weather_api_key = d.get_pirate_key().trim().to_string();
                s.auto_mode_api_budget = pick(&BUDGETS, d.get_budget_index()).into();
                interval_changed = old_interval != s.update_interval_minutes;
                if let Err(e) = aw_store::save_config(&st.paths.config_file(), &st.config) {
                    tracing::error!("saving settings: {e}");
                    set_status(&ui, &format!("Could not save settings: {e}"));
                    return;
                }
            }
            let _ = d.hide();
            if interval_changed {
                schedule_refresh_timer(&ui, &state);
            }
            announce(&ui, &state, "Settings saved. Refreshing…");
            start_refresh(&ui, &state);
        });
    }
    {
        let weak = dlg.as_weak();
        dlg.on_cancel(move || {
            if let Some(d) = weak.upgrade() {
                let _ = d.hide();
            }
        });
    }
    if dlg.show().is_ok() {
        state.borrow_mut().dialogs.push(Box::new(dlg));
    }
}
