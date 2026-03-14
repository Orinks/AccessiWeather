# Codebase Structure

**Analysis Date:** 2026-03-14

## Directory Layout

```
src/accessiweather/
├── __init__.py                           # Package initialization
├── __main__.py                           # Entry point for python -m accessiweather
├── main.py                               # Main app launcher (also entry point)
├── app.py                                # wx.App subclass, initialization, event loop
│
├── api/                                  # External API clients (weather data sources)
│   ├── __init__.py
│   ├── nws/                              # National Weather Service (US) API
│   │   ├── __init__.py
│   │   ├── core_client.py                # NWS HTTP client and session management
│   │   ├── point_location.py             # /points/{lat,lon} endpoint → grid/forecast URLs
│   │   ├── weather_data.py               # /gridpoints/{office}/{x},{y}/forecast data
│   │   └── alerts_discussions.py         # Alerts and AFD (Area Forecast Discussion) fetching
│   ├── openmeteo_wrapper.py              # Open-Meteo API client wrapper
│   ├── base_wrapper.py                   # Abstract base for API wrappers
│   └── openrouter_models.py              # AI model configuration for explanations
│
├── api_client/                           # Legacy/alternative API client implementations
│   ├── __init__.py
│   ├── core_client.py                    # Legacy NWS core client
│   ├── alerts_and_products.py            # Legacy alerts/products handler
│   └── exceptions.py                     # API-specific exceptions
│
├── config/                               # Configuration management
│   ├── __init__.py
│   ├── config_manager.py                 # Main ConfigManager orchestrator
│   ├── settings.py                       # SettingsOperations for user preferences
│   ├── locations.py                      # LocationOperations for saved locations
│   ├── secure_storage.py                 # LazySecureStorage for keyring-based API keys
│   ├── source_priority.py                # SourcePriorityConfig for data source routing
│   ├── file_permissions.py               # Unix permissions for secure config files
│   ├── portable_secrets.py               # Portable mode secrets storage
│   ├── github_config.py                  # GitHub integration config
│   └── import_export.py                  # Config import/export operations
│
├── display/                              # Presentation layer (data → view models)
│   ├── __init__.py                       # Exports WeatherPresenter
│   ├── weather_presenter.py              # Main presenter orchestrator
│   ├── priority_engine.py                # Alert/data prioritization logic
│   └── presentation/                     # Specialized formatters
│       ├── __init__.py
│       ├── formatters.py                 # Date/time formatting, text layout
│       ├── html_formatters.py            # HTML-safe formatting for rich text
│       ├── current_conditions.py         # Current conditions presentation logic
│       ├── forecast.py                   # Forecast presentation logic
│       ├── alerts.py                     # Alert presentation and summarization
│       ├── environmental.py              # Air quality/environmental presentation
│       └── [other presentation modules]
│
├── models/                               # Data models (domain objects)
│   ├── __init__.py                       # Exports all models
│   ├── weather.py                        # WeatherData, Location, CurrentConditions, Forecast, HourlyForecast, TrendInsight, EnvironmentalConditions, AviationData
│   ├── alerts.py                         # WeatherAlert, WeatherAlerts
│   ├── config.py                         # AppConfig, AppSettings
│   └── errors.py                         # ApiError, domain-specific exceptions
│
├── ui/                                   # User interface (wxPython)
│   ├── __init__.py                       # Lazy loader for MainWindow
│   ├── main_window.py                    # Main application window (SizedFrame)
│   ├── system_tray.py                    # Taskbar/system tray integration
│   ├── taskbar_icon_updater.py           # Windows taskbar icon badge updates
│   └── dialogs/                          # Modal dialogs
│       ├── __init__.py
│       ├── settings_dialog.py            # Settings/preferences dialog
│       ├── location_dialog.py            # Location management dialog
│       ├── alert_dialog.py               # Alert details dialog
│       ├── discussion_dialog.py          # Area Forecast Discussion viewer
│       ├── explanation_dialog.py         # AI-generated explanation dialog
│       ├── air_quality_dialog.py         # Air quality details dialog
│       ├── aviation_dialog.py            # Aviation weather (METAR/TAF) dialog
│       ├── uv_index_dialog.py            # UV index details dialog
│       ├── weather_history_dialog.py     # Historical comparison dialog
│       ├── noaa_radio_dialog.py          # NOAA radio player dialog
│       ├── soundpack_manager_dialog.py   # Sound pack installation dialog
│       ├── soundpack_wizard_dialog.py    # Guided sound pack wizard
│       ├── community_packs_dialog.py     # Community sound packs browser
│       ├── nationwide_discussion_dialog.py # National discussion viewer
│       ├── progress_dialog.py            # Generic progress display
│       ├── update_dialog.py              # Update notification/installation dialog
│       ├── report_issue_dialog.py        # Bug report dialog
│       ├── model_browser_dialog.py       # AI model browser dialog
│       ├── weather_assistant_dialog.py   # AI weather assistant dialog
│       ├── debug_alert_dialog.py         # Debug alert inspection dialog
│       └── [other dialogs]
│
├── services/                             # Application services
│   ├── __init__.py                       # Lazy loader for common services
│   ├── environmental_client.py           # Air quality and pollen data fetching
│   ├── platform_detector.py              # Platform detection (Windows/macOS/Linux)
│   ├── startup_utils.py                  # Startup initialization utilities
│   ├── location_service.py               # Location geocoding and management
│   ├── national_discussion_service.py    # National forecast discussion fetching
│   ├── national_discussion_scraper.py    # Web scraping for discussions
│   ├── community_soundpack_service.py    # Community sound pack management
│   ├── pack_submission_service.py        # Sound pack submission handling
│   ├── notification_service.py           # Notification delivery coordination
│   ├── simple_update.py                  # Simple update checking
│   ├── weather_service/                  # Weather service module
│   │   ├── __init__.py
│   │   ├── weather_service.py            # Main WeatherService orchestrator
│   │   ├── api_client_manager.py         # API client initialization and selection
│   │   ├── weather_data_retrieval.py     # Data fetching with fallback handling
│   │   ├── alerts_discussion.py          # Alerts and discussion coordination
│   │   └── fallback_handler.py           # Fallback data source logic
│   ├── update_service/                   # GitHub-based update service
│   │   ├── __init__.py
│   │   ├── github_update_service.py      # Update checking and installation
│   │   ├── releases.py                   # GitHub release API client
│   │   ├── downloads.py                  # Download management
│   │   ├── signature_verification.py     # GPG signature verification
│   │   └── settings.py                   # Update preferences
│   ├── github_update_service.py          # Legacy update service
│   └── github_backend_client.py          # GitHub API wrapper
│
├── notifications/                        # Alert notifications and sound
│   ├── __init__.py
│   ├── weather_notifier.py               # Main notification orchestrator
│   ├── toast_notifier.py                 # Desktop toast notifications
│   ├── sound_player.py                   # Sound playback system
│   ├── sound_pack_installer.py           # Sound pack installation
│   ├── alert_sound_mapper.py             # Map alert types to sound files
│   ├── notification_test.py              # Test notification playback
│   ├── notification_event_manager.py     # Notification event tracking
│   └── [other notification modules]
│
├── noaa_radio/                           # NOAA Weather Radio integration
│   ├── __init__.py
│   ├── player.py                         # Radio stream player
│   ├── stations.py                       # NOAA radio station database
│   ├── station_db.py                     # Station database manager
│   ├── stream_url.py                     # Radio stream URL resolution
│   ├── wxradio_client.py                 # NOAA radio API client
│   └── preferences.py                    # Radio preferences storage
│
├── utils/                                # Utility modules
│   ├── __init__.py
│   ├── retry.py                          # Retry logic with exponential backoff
│   ├── unit_utils.py                     # Temperature/wind speed unit conversion
│   ├── thread_manager.py                 # Thread safety utilities
│   ├── taf_decoder.py                    # Terminal Aerodrome Forecast decoder
│   └── [other utilities]
│
├── weather_gov_api_client/               # Auto-generated Weather.gov API client
│   ├── __init__.py
│   ├── models/                           # Generated dataclasses for API responses
│   └── api/
│       └── default/                      # Generated API endpoint handlers
│
├── resources/                            # Static assets (icons, sounds, etc.)
│   └── [sound packs, icons, etc.]
│
└── [Core modules at package root]
    ├── weather_client_base.py            # Main WeatherClient implementation
    ├── weather_client.py                 # Compatibility facade and imports
    ├── weather_client_nws.py             # NWS-specific fetch logic
    ├── weather_client_openmeteo.py       # Open-Meteo-specific fetch logic
    ├── weather_client_visualcrossing.py  # Visual Crossing integration
    ├── weather_client_parsers.py         # Response parsing logic
    ├── weather_client_trends.py          # Trend analysis (pressure, wind)
    ├── weather_client_enrichment.py      # Data enrichment (confidence, etc.)
    ├── weather_client_alerts.py          # AlertAggregator for alert processing
    ├── weather_client_fusion.py          # DataFusionEngine for multi-source reconciliation
    ├── weather_client_parallel.py        # ParallelFetchCoordinator for concurrent fetches
    ├── alert_manager.py                  # StatefulAlertManager with rate limiting
    ├── alert_notification_system.py      # Alert notification delivery orchestrator
    ├── alert_lifecycle.py                # Alert change detection (diff_alerts)
    ├── cache.py                          # WeatherDataCache with TTL support
    ├── constants.py                      # Application constants (timeouts, alert priorities, etc.)
    ├── app_initialization.py             # App startup sequence
    ├── app_helpers.py                    # Helper functions for app logic
    ├── paths.py                          # Platform-specific path handling
    ├── location_manager.py               # Location management wrapper
    ├── location.py                       # Location model
    ├── geocoding.py                      # Geocoding utilities
    ├── screen_reader.py                  # Screen reader integration helpers
    ├── single_instance.py                # Single-instance enforcement (Windows)
    ├── formatters.py                     # Legacy/legacy text formatting
    ├── format_string_parser.py           # Custom format string parsing
    ├── dynamic_format_manager.py         # Dynamic format string management
    ├── forecast_confidence.py            # Forecast confidence calculation
    ├── weather_condition_analyzer.py     # Weather pattern analysis
    ├── ai_explainer.py                   # AI-generated explanations
    ├── ai_tools.py                       # AI integration utilities
    ├── visual_crossing_client.py         # Visual Crossing API client
    ├── openmeteo_client.py               # Open-Meteo HTTP client
    ├── openmeteo_geocoding_client.py     # Open-Meteo geocoding
    ├── openmeteo_mapper.py               # Open-Meteo response mapping
    ├── logging_config.py                 # Logging configuration helpers
    ├── config_utils.py                   # Configuration utilities
    ├── sound_events.py                   # Sound event definitions
    ├── soundpack_paths.py                # Sound pack path management
    ├── cli.py                            # Command-line interface
    └── api_wrapper.py                    # Wrapper for API client compatibility
```

## Directory Purposes

**api/:** HTTP clients for weather data sources. `nws/` handles US government weather service (latitude/longitude → grid points → forecast/alerts). `openmeteo_wrapper.py` queries Open-Meteo (global coverage). Each module specializes in endpoint handling, response parsing, and error recovery.

**config/:** Centralized configuration management. Handles loading/saving JSON config from `~/.config/accessiweather/`, secured API key storage via system keychain, location persistence, and user preference application.

**display/:** Transforms raw `WeatherData` models into structured presentation objects. `WeatherPresenter` is the public API. Internal formatters handle date/time, layout, and accessibility text. Alert prioritization logic determines what to show first.

**models/:** Pure Python dataclasses for type safety. Never imports from other app modules (only stdlib). Represents domain objects (location, weather, alerts, settings).

**ui/:** wxPython GUI components. `main_window.py` is the primary window (location selector, current/forecast/alerts display). Dialogs handle settings, location management, alert details, etc. System tray integration for minimize-to-tray functionality.

**services/:** Reusable business logic modules. `environmental_client.py` fetches air quality. `platform_detector.py` handles OS detection. `update_service/` manages GitHub-based auto-updates. `weather_service/` is a legacy orchestrator (mostly replaced by `WeatherClient`).

**notifications/:** Alert delivery system. `sound_player.py` plays audio. `toast_notifier.py` shows desktop notifications. `alert_sound_mapper.py` routes alert types to sound packs. Support for custom community sound packs.

**noaa_radio/:** Standalone NOAA Weather Radio integration. Streams radio, manages station database, resolves URLs from radio API.

**utils/:** Reusable utilities. `retry.py` implements exponential backoff. `unit_utils.py` handles temperature/wind conversions. `taf_decoder.py` parses aviation forecast text.

**weather_gov_api_client/:** Auto-generated OpenAPI client for Weather.gov. Contains generated dataclasses matching API schema. Rarely modified directly.

**[Root level]:** Core application logic. `weather_client_base.py` orchestrates multi-source data fetching with parallel execution. `alert_manager.py` tracks alert state and notification history. `cache.py` provides TTL-based caching. Alert processing split across `alert_lifecycle.py` (change detection), `alert_notification_system.py` (delivery logic), and `alert_manager.py` (state). Presentation preparation in `weather_client_enrichment.py` (confidence, trends).

## Key File Locations

**Entry Points:**
- `src/accessiweather/__main__.py`: Python module entry point (`python -m accessiweather`)
- `src/accessiweather/main.py`: Primary entry point for executable launcher
- `src/accessiweather/app.py`: wx.App instance and main event loop initialization

**Configuration:**
- `src/accessiweather/config/config_manager.py`: Main configuration orchestrator (loads, saves, applies settings)
- `src/accessiweather/paths.py`: Platform-specific path resolution for config directory
- `~/.config/accessiweather/accessiweather.json`: Runtime config storage (created at first run)

**Core Logic:**
- `src/accessiweather/weather_client_base.py`: Multi-source weather data orchestrator
- `src/accessiweather/alert_manager.py`: Alert state machine and cooldown tracking
- `src/accessiweather/alert_notification_system.py`: Alert delivery logic
- `src/accessiweather/display/weather_presenter.py`: Data-to-UI transformation

**UI:**
- `src/accessiweather/ui/main_window.py`: Primary application window
- `src/accessiweather/ui/dialogs/`: All modal dialogs (settings, locations, details)

**Testing:**
- `tests/test_*.py`: Unit tests (mocked APIs, no network)
- `tests/integration/`: Integration tests (real APIs, VCR cassettes for reproducibility)
- `tests/gui/`: GUI-specific tests (window management, event handling)

## Naming Conventions

**Files:**
- Source files: `snake_case.py` (e.g., `weather_client_nws.py`, `config_manager.py`)
- Test files: `test_*.py` (e.g., `test_weather_client.py`, `test_alert_manager.py`)
- Dialog files: `*_dialog.py` (e.g., `settings_dialog.py`, `alert_dialog.py`)
- Utilities: `*_utils.py` or `*_helper.py` (e.g., `unit_utils.py`, `app_helpers.py`)

**Directories:**
- Single-responsibility packages: Lowercase with underscores (e.g., `api/`, `config/`, `services/`, `notifications/`)
- Sub-packages for organization: `api/nws/`, `services/weather_service/`, `services/update_service/`, `ui/dialogs/`

**Classes:**
- PascalCase: `WeatherClient`, `AlertManager`, `ConfigManager`, `WeatherPresenter`, `MainWindow`
- Exceptions: `ApiError`, `VisualCrossingApiError`, `APITimeoutError`

**Functions:**
- snake_case: `fetch_weather_data()`, `format_accessible_message()`, `retry_with_backoff()`, `diff_alerts()`
- Private: Leading underscore (e.g., `_fetch_nws_data()`, `_get_http_client()`)

**Constants:**
- UPPER_CASE: `DEFAULT_TIMEOUT`, `CACHE_SCHEMA_VERSION`, `SEVERITY_PRIORITY_EXTREME`, `ALERT_HISTORY_MAX_LENGTH`

## Where to Add New Code

**New Weather Data Endpoint:**
- Implementation: `src/accessiweather/api/nws/` (for NWS), or create `src/accessiweather/api/new_source/` for new source
- Integration point: `src/accessiweather/weather_client_base.py` (add fetch method and call in orchestration)
- Parsing: Create `src/accessiweather/weather_client_newsource.py` following pattern of `weather_client_nws.py`
- Tests: `tests/test_weather_client_newsource.py` (unit), `tests/integration/test_newsource_api.py` (integration with cassettes)

**New UI Dialog:**
- Implementation: Create `src/accessiweather/ui/dialogs/new_dialog.py` (extends `wx.Dialog`)
- Integration: Import and instantiate in `src/accessiweather/ui/main_window.py` event handler
- Tests: `tests/gui/test_new_dialog.py` (test with `TOGA_BACKEND=toga_dummy` if wxPython compatible)

**New Feature (non-UI):**
- If data-related: Extend `src/accessiweather/models/weather.py` or create new model class
- If business logic: Add method to appropriate orchestrator (`WeatherClient`, `AlertManager`, etc.) or create new service in `src/accessiweather/services/`
- If configuration-related: Add field to `AppSettings` in `models/config.py` and handler in `config/settings.py`
- Tests: Add unit test in `tests/test_feature.py`, integration test if external APIs involved

**New Formatter/Presentation:**
- Implementation: `src/accessiweather/display/presentation/` (e.g., `aviation.py` for aviation formatting)
- Integration: Call from `WeatherPresenter.build_*()` method in `src/accessiweather/display/weather_presenter.py`
- Tests: `tests/test_presentation_aviation.py`

**Utilities:**
- Shared helpers: `src/accessiweather/utils/new_utility.py` (if cross-module reuse)
- Single-module utilities: Keep in module that uses it (avoid splitting until 2+ modules need it)
- Tests: `tests/test_utils_new_utility.py`

## Special Directories

**cache.db (implicit):**
- Purpose: Runtime in-memory cache (not persisted to disk by default)
- Generated: Yes, at runtime
- Committed: No (in-memory only)

**VCR Cassettes:**
- Location: `tests/integration/cassettes/`
- Purpose: Record real API responses for reproducible integration tests
- Generated: Yes, on first integration test run (if not committed)
- Committed: Yes (cassettes check into repo for CI reproducibility)

**soundpacks/ directory (project root):**
- Purpose: Community-contributed sound packs for alert sounds
- Generated: No (manually created)
- Committed: Yes

**resources/ directory:**
- Purpose: Static assets (icons, default sound files, etc.)
- Generated: No (manually created)
- Committed: Yes

**.planning/ directory:**
- Purpose: GSD (Generalist System Designer) planning documents
- Generated: Yes (by GSD agents)
- Committed: Yes

---

*Structure analysis: 2026-03-14*
