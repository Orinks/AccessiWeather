//! Application wiring: config, weather client, screen reader and the wxDragon UI.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use aw_core::settings::AppConfig;
use aw_core::Location;
use aw_providers::client::live::Live;
use aw_providers::client::WeatherClient;
use aw_providers::nws::{ZoneDriftSink, ZoneFields};
use aw_providers::products::ForecastProductService;
use aw_providers::{HttpClient, ReqwestClient};
use aw_store::weather_cache::{WeatherDataCache, DEFAULT_MAX_AGE_MINUTES};
use aw_store::Paths;

use crate::cli::Args;
use crate::ui;

pub(crate) const SMOKE_DURATION_MS: i32 = 2500;
const SMOKE_WATCHDOG_GRACE_MS: u64 = 15_000;

/// Set by the UI once the smoke timer has fired and data was displayed.
pub(crate) static SMOKE_COMPLETED: AtomicBool = AtomicBool::new(false);

/// A modal assert dialog or a toolkit that refuses to quit would otherwise
/// leave a headless CI smoke run hanging forever.
fn spawn_smoke_watchdog() {
    std::thread::Builder::new()
        .name("aw-smoke-watchdog".into())
        .spawn(|| {
            std::thread::sleep(std::time::Duration::from_millis(
                SMOKE_DURATION_MS as u64 + SMOKE_WATCHDOG_GRACE_MS,
            ));
            if SMOKE_COMPLETED.load(Ordering::SeqCst) {
                eprintln!("smoke: window did not close after completion; forcing exit 0");
                std::process::exit(0);
            }
            eprintln!("smoke: window never reached completion (event loop blocked?); exit 1");
            std::process::exit(1);
        })
        .expect("spawn smoke watchdog");
}

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

/// Everything the UI callbacks need, shared on the main thread.
pub(crate) struct State {
    pub paths: Paths,
    pub config: AppConfig,
    /// Shared by every service (the offline fixtures in sample-data runs).
    pub http: Arc<dyn HttpClient>,
    /// Builds the weather client's sources from settings and API keys.
    pub live: Live,
    /// `app.weather_client`.
    pub client: Arc<WeatherClient>,
    /// The main window's `_forecast_product_service`: text products the
    /// refresh pre-warms for the dialogs and notification checks.
    pub products: Arc<ForecastProductService>,
    /// `app.current_weather_data`: what the main window shows.
    pub current_weather_data: Option<aw_core::model::WeatherData>,
    /// `app.is_updating`: a full refresh is in flight.
    pub is_updating: bool,
    pub smoke: bool,
    /// Sample data runs never write the user's configuration.
    pub offline: bool,
    /// `--debug`: adds the Help > Debug menu.
    pub debug: bool,
}

pub(crate) type Shared = Rc<RefCell<State>>;

thread_local! {
    /// Main-thread handle to the app state for closures posted from worker threads.
    static APP_STATE: RefCell<Option<Shared>> = const { RefCell::new(None) };
}

pub(crate) fn with_state() -> Option<Shared> {
    APP_STATE.with(|s| s.borrow().clone())
}

/// Queue `f` on the wx main thread and wake the event loop so it runs promptly,
/// even while a modal dialog is open.
pub(crate) fn post_to_ui<F: FnOnce() + Send + 'static>(f: F) {
    wxdragon::call_after(Box::new(f));
    wxdragon::wake_up_idle();
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
    let mut needs_passphrase = false;
    if !offline {
        if paths.portable {
            needs_passphrase = crate::portable_keys::import_silently(&paths, &mut config.settings);
        } else {
            aw_store::secrets::load_into(&mut config.settings);
        }
    }
    if args.check {
        return self_check();
    }
    let http: Arc<dyn HttpClient> = if offline {
        crate::fixtures::offline_client(chrono::Utc::now())
    } else {
        Arc::new(ReqwestClient::new()?)
    };

    if (args.smoke || args.offline) && config.locations.is_empty() {
        config.add_location(
            Location::new("Philadelphia, Pennsylvania", 39.9526, -75.1652).with_country("US"),
        );
    }
    // Smoke runs must show weather; a config without a current location
    // would (as in Python) start on "All Locations" and fetch nothing.
    if args.smoke && config.current_location.is_none() {
        config.current_location = config.locations.first().cloned();
    }

    // Sample-data runs keep their cache out of the user's.
    let cache_dir = if offline {
        std::env::temp_dir().join("accessiweather-offline-cache")
    } else {
        paths.cache_dir()
    };
    let offline_cache = WeatherDataCache::new(&cache_dir, DEFAULT_MAX_AGE_MINUTES)
        .inspect_err(|e| {
            tracing::error!("Weather cache unavailable at {}: {e}", cache_dir.display())
        })
        .ok();
    let mut live = Live::new(http.clone());
    live.zone_drift_sink = Some(zone_drift_sink());
    let settings = config.settings.clone();
    let client = Arc::new(WeatherClient::new(
        live.sources(&settings),
        settings.clone(),
        &settings.data_source,
        offline_cache,
    ));
    let products = Arc::new(ForecastProductService::new(http.clone()));

    let state: Shared = Rc::new(RefCell::new(State {
        paths,
        config,
        http,
        live,
        client,
        products,
        current_weather_data: None,
        is_updating: false,
        smoke: args.smoke,
        offline,
        debug: args.debug,
    }));
    APP_STATE.with(|s| *s.borrow_mut() = Some(state.clone()));

    let smoke = args.smoke;
    if smoke {
        spawn_smoke_watchdog();
    }
    wxdragon::main(move |_app| {
        let Some(state) = with_state() else { return };
        if !smoke {
            crate::screen_reader::init();
        }
        ui::build_main_window(&state, smoke);
        if needs_passphrase {
            wxdragon::call_after(Box::new(|| {
                let (Some(state), Some(frame)) = (with_state(), ui::main_frame()) else {
                    return;
                };
                if crate::portable_keys::prompt(&frame, &state) {
                    refresh_runtime_settings(&state.borrow());
                    ui::refresh_now();
                }
            }));
        }
    })
    .map_err(|e| AppError::Ui(e.to_string()))?;
    crate::screen_reader::shutdown();

    if state.borrow().smoke && state.borrow().current_weather_data.is_none() {
        return Err(AppError::Check(
            "smoke run never received weather data".into(),
        ));
    }
    Ok(())
}

/// `--check`: replay the recorded Python runs through the real data path
/// and require the main window's text Python showed.
fn self_check() -> Result<(), AppError> {
    for text in crate::fixtures::CASES {
        let case = crate::fixtures::case(text);
        let (weather, panels) = crate::fixtures::replay(&case);
        let expected = &case["panels"];
        let checks = [
            ("current conditions", &panels.current, &expected["current"]),
            ("daily forecast", &panels.daily, &expected["daily"]),
            ("hourly forecast", &panels.hourly, &expected["hourly"]),
        ];
        for (section, got, want) in checks {
            if want.as_str() != Some(got.as_str()) {
                return Err(AppError::Check(format!(
                    "{} {section} differs from the Python app:
{got}
--- expected ---
{}",
                    weather.location.name,
                    want.as_str().unwrap_or_default()
                )));
            }
        }
        println!(
            "{}
",
            panels.current
        );
    }
    Ok(())
}

/// `refresh_runtime_settings`: settings, the data source and API keys reach
/// the weather client (its sources are rebuilt from them).
pub(crate) fn refresh_runtime_settings(st: &State) {
    tracing::info!("Refreshing runtime settings");
    let settings = st.config.settings.clone();
    st.client.reconfigure(st.live.sources(&settings), settings);
}

/// `set_zone_drift_sink(config_manager._locations)`: corrections the NWS
/// client finds on a refresh are saved on the UI thread (`wx.CallAfter`).
fn zone_drift_sink() -> ZoneDriftSink {
    Arc::new(|name: &str, fields: &ZoneFields| {
        let (name, fields) = (name.to_string(), fields.clone());
        post_to_ui(move || {
            if let Some(state) = with_state() {
                update_zone_metadata(&mut state.borrow_mut(), &name, &fields);
            }
        });
    })
}

/// `LocationOperations.update_zone_metadata`.
pub(crate) fn update_zone_metadata(
    st: &mut State,
    location_name: &str,
    fields: &ZoneFields,
) -> bool {
    if fields.is_empty() {
        return false;
    }
    let Some(location) = st
        .config
        .locations
        .iter_mut()
        .find(|l| l.name == location_name)
    else {
        tracing::debug!("update_zone_metadata: location {location_name} not found (skipped)");
        return false;
    };
    fields.apply_to(location);
    let updated = location.clone();
    if let Some(current) = st
        .config
        .current_location
        .as_mut()
        .filter(|c| c.name == location_name)
    {
        *current = updated;
    }
    let mut keys: Vec<String> = serde_json::to_value(fields)
        .ok()
        .and_then(|v| v.as_object().map(|o| o.keys().cloned().collect()))
        .unwrap_or_default();
    keys.sort();
    tracing::info!("Updated zone metadata on {location_name}: {keys:?}");
    save(st).is_ok()
}

/// Persist the current config, logging (not propagating) failures.
pub(crate) fn save(st: &State) -> Result<(), aw_store::StoreError> {
    if st.offline {
        return Ok(());
    }
    aw_store::save_config(&st.paths.config_file(), &st.config).inspect_err(|e| {
        tracing::error!("saving config: {e}");
    })
}

/// Persist an API key where the Python app keeps it: the keyring, or the
/// encrypted bundle in portable mode (using the cached passphrase).
pub(crate) fn save_api_key(st: &mut State, name: &str, value: &str) -> bool {
    use aw_store::secrets;
    let value = value.trim();
    if let Some(field) = secrets::api_key_mut(&mut st.config.settings, name) {
        *field = value.to_string();
    }
    if st.offline {
        return true;
    }
    if !st.paths.portable {
        return secrets::set_password(name, value);
    }
    let passphrase = secrets::get_password(secrets::PORTABLE_PASSPHRASE_KEY).unwrap_or_default();
    if passphrase.trim().is_empty() {
        tracing::warn!(
            "No portable bundle passphrase cached; {name} is kept for this session only"
        );
        return false;
    }
    let bundle = st.paths.config_dir.join(secrets::BUNDLE_FILE_NAMES[0]);
    let keys = secrets::collect(&mut st.config.settings);
    secrets::write_bundle(&bundle, &keys, passphrase.trim())
        .inspect_err(|e| tracing::error!("Failed to update {}: {e}", bundle.display()))
        .is_ok()
}
