//! App-wide NOAA Weather Radio wiring (Python: `app_initialization.py`,
//! `noaa_radio_clients.get_clients`, `app_shortcuts._on_noaa_radio_hotkey`
//! and the dialog constructor).

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use aw_core::Location;
use aw_providers::{HttpClient, ReqwestClient};

use crate::audio::RodioBackend;
use crate::auto_tune::{
    monotonic, AlertRadioAutoTuner, AutoTunerDeps, LocationProvider, SettingsProvider,
    StatusCallback, WeatherIndexAlertStationResolver,
};
use crate::availability::{
    StationAvailabilityCache, StationAvailabilityService, AVAILABILITY_FILE_NAME,
};
use crate::dialog::{DialogDeps, DialogEventHandler, RadioDialog};
use crate::player::AudioBackend;
use crate::preferences::{RadioPreferences, SharedPreferences};
use crate::session::RadioSession;
use crate::stations::StationDatabase;
use crate::stream_url::StreamUrlProvider;
use crate::thread_spawner;
use crate::toggle::{NotifyCallback, RadioToggleController};
use crate::weatherindex::WeatherIndexClient;
use crate::wxradio::WxRadioClient;

/// Create once at startup and keep for the life of the app.
pub struct RadioContext {
    /// The shared playback session (outlives the dialog).
    pub session: Arc<RadioSession>,
    /// The one preferences object everything shares.
    pub preferences: SharedPreferences,
    pub stations: Arc<StationDatabase>,
    /// Cached clients reused across dialog opens.
    pub weatherindex: Arc<WeatherIndexClient>,
    pub wxradio: Arc<WxRadioClient>,
    config_dir: PathBuf,
}

impl RadioContext {
    pub fn new(
        config_dir: &Path,
        http: Arc<dyn HttpClient>,
        backend: Arc<dyn AudioBackend>,
    ) -> Self {
        let preferences = RadioPreferences::in_config_dir(config_dir).shared();
        Self {
            session: RadioSession::new(backend, Some(preferences.clone())),
            preferences,
            stations: Arc::new(StationDatabase::new()),
            weatherindex: Arc::new(WeatherIndexClient::new(http.clone())),
            wxradio: Arc::new(WxRadioClient::new(http)),
            config_dir: config_dir.to_path_buf(),
        }
    }

    /// Real network client and audio output.
    pub fn with_defaults(config_dir: &Path) -> Result<Self, String> {
        let http = ReqwestClient::new().map_err(|e| e.to_string())?;
        Ok(Self::new(
            config_dir,
            Arc::new(http),
            Arc::new(RodioBackend::new()?),
        ))
    }

    /// Open the NOAA Weather Radio dialog model (Ctrl+N). `lat`/`lon` put it
    /// in nearest-station mode for that point; `saved_locations` are in the
    /// main window's display order.
    pub fn open_dialog(
        &self,
        lat: Option<f64>,
        lon: Option<f64>,
        saved_locations: Vec<Location>,
        on_event: DialogEventHandler,
    ) -> Arc<RadioDialog> {
        let availability_cache = Arc::new(Mutex::new(StationAvailabilityCache::new(
            self.config_dir.join(AVAILABILITY_FILE_NAME),
        )));
        let deps = DialogDeps {
            session: self.session.clone(),
            preferences: self.preferences.clone(),
            url_provider: Arc::new(StreamUrlProvider::new(
                HashMap::new(),
                false,
                Some(self.wxradio.clone()),
                Some(self.weatherindex.clone()),
            )),
            availability: Arc::new(StationAvailabilityService::new(
                self.weatherindex.clone(),
                availability_cache.clone(),
            )),
            availability_cache,
            station_database: self.stations.clone(),
        };
        RadioDialog::open(deps, lat, lon, saved_locations, on_event)
    }

    /// Alert auto-tune. `status_callback` gets status-bar messages from a
    /// worker thread.
    pub fn auto_tuner(
        &self,
        settings_provider: SettingsProvider,
        location_provider: LocationProvider,
        status_callback: Option<StatusCallback>,
    ) -> Arc<AlertRadioAutoTuner> {
        AlertRadioAutoTuner::new(AutoTunerDeps {
            settings_provider,
            location_provider,
            status_callback,
            session: self.session.clone(),
            preferences: self.preferences.clone(),
            station_resolver: Arc::new(WeatherIndexAlertStationResolver::new(
                self.stations.clone(),
                self.weatherindex.clone(),
            )),
            // Python: StreamURLProvider(use_fallback=False, weatherindex_client=...).
            url_provider: Arc::new(StreamUrlProvider::new(
                HashMap::new(),
                false,
                None,
                Some(self.weatherindex.clone()),
            )),
            spawn: thread_spawner("AlertRadioAutoTune"),
            monotonic: Arc::new(monotonic),
        })
    }

    /// The global play/stop hotkey. `notify` shows a desktop notification
    /// titled "NOAA Weather Radio".
    pub fn toggle_controller(
        &self,
        notify: Option<NotifyCallback>,
        auto_tuner: Option<Arc<AlertRadioAutoTuner>>,
    ) -> Arc<RadioToggleController> {
        RadioToggleController::new(
            self.session.clone(),
            self.preferences.clone(),
            self.stations.clone(),
            // Python's toggle uses a bare StreamURLProvider(): bundled URLs
            // plus the Broadcastify fallback.
            Arc::new(StreamUrlProvider::default()),
            notify,
            auto_tuner,
            thread_spawner("RadioHotkeyToggle"),
        )
    }

    /// App shutdown: stop the radio (after `auto_tuner.stop()`).
    pub fn shutdown(&self) {
        self.session.stop(true);
    }
}
