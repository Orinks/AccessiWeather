//! Application wiring: config, weather client, screen reader and the wxDragon UI.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use aw_core::presenter::WeatherPresenter;
use aw_core::settings::AppConfig;
use aw_core::Location;
use aw_providers::products::ForecastProductService;
use aw_providers::{HttpClient, ReqwestClient, WeatherClient};
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
    pub client: WeatherClient,
    /// Text products shared by Forecaster Notes, National Products and
    /// Advanced Lookup (`_get_forecast_product_service`).
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
    /// `app.ai_explanation_cache`, emptied by the explanation's Regenerate.
    pub ai_explanation_cache: Arc<aw_ai::ExplanationCache>,
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
    let http: Arc<dyn HttpClient> = if offline {
        crate::fixtures::offline_client()
    } else {
        Arc::new(ReqwestClient::new()?)
    };
    let products = Arc::new(ForecastProductService::new(http.clone()));
    let client = WeatherClient::new(http);

    if args.check {
        return self_check(&config, &client);
    }

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

    let state: Shared = Rc::new(RefCell::new(State {
        paths,
        config,
        client,
        products,
        current_weather_data: None,
        is_updating: false,
        smoke: args.smoke,
        offline,
        debug: args.debug,
        ai_explanation_cache: Arc::default(),
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
