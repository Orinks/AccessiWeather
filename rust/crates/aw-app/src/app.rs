//! Application wiring: config, weather client, speech and the wxDragon UI.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use aw_core::presenter::{WeatherPresentation, WeatherPresenter};
use aw_core::settings::AppConfig;
use aw_core::weather::WeatherData;
use aw_core::Location;
use aw_providers::{HttpClient, ReqwestClient, WeatherClient};
use aw_speech::Speaker;
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
    pub speaker: Speaker,
    pub last_data: Option<WeatherData>,
    pub last_presentation: Option<WeatherPresentation>,
    pub busy: bool,
    pub smoke: bool,
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

    let state: Shared = Rc::new(RefCell::new(State {
        paths,
        config,
        client,
        speaker,
        last_data: None,
        last_presentation: None,
        busy: false,
        smoke: args.smoke,
    }));
    APP_STATE.with(|s| *s.borrow_mut() = Some(state.clone()));

    let smoke = args.smoke;
    if smoke {
        spawn_smoke_watchdog();
    }
    wxdragon::main(move |_app| {
        let Some(state) = with_state() else { return };
        ui::build_main_window(&state, smoke);
    })
    .map_err(|e| AppError::Ui(e.to_string()))?;

    let speaker = state.borrow().speaker.clone();
    speaker.shutdown();
    if state.borrow().smoke && state.borrow().last_data.is_none() {
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
    aw_store::save_config(&st.paths.config_file(), &st.config).inspect_err(|e| {
        tracing::error!("saving config: {e}");
    })
}

/// Build the status line for a completed fetch.
pub(crate) fn status_for(data: &WeatherData, presentation: &WeatherPresentation) -> String {
    if !data.has_any_data() {
        return format!(
            "Could not load weather for {}. {}",
            data.location.name,
            data.failed_sources
                .iter()
                .map(|(s, e)| format!("{s}: {e}"))
                .collect::<Vec<_>>()
                .join("; ")
        );
    }
    let mut status = presentation.summary_text.clone();
    if !presentation.status_messages.is_empty() {
        status.push_str(" — ");
        status.push_str(&presentation.status_messages.join("; "));
    }
    status
}

/// Store fetched weather and persist NWS metadata (zones, office) learned during the fetch.
pub(crate) fn remember_weather(
    st: &mut State,
    data: WeatherData,
    presentation: WeatherPresentation,
) {
    if let Some(saved) = st
        .config
        .locations
        .iter_mut()
        .find(|l| l.name == data.location.name)
    {
        if saved.forecast_zone_id.is_none() && data.location.forecast_zone_id.is_some() {
            *saved = data.location.clone();
            st.config.current_location = Some(data.location.clone());
            let _ = save(st);
        }
    }
    st.last_data = Some(data);
    st.last_presentation = Some(presentation);
}
