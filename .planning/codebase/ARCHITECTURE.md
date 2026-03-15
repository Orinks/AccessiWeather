# Architecture

**Analysis Date:** 2026-03-14

## Pattern Overview

**Overall:** Layered architecture with clear separation between UI, business logic, and external API integration. The app follows a service-oriented pattern with asynchronous data fetching, intelligent caching, and lifecycle-aware state management.

**Key Characteristics:**
- Async-first design using `asyncio` for non-blocking I/O
- Multi-source weather data aggregation with smart fallback routing
- Alert state machine with change detection and notification throttling
- Presentation layer that decouples data models from display formatting
- Lazy loading and lazy initialization for performance optimization
- Cross-platform UI using wxPython with screen reader accessibility

## Layers

**UI Layer:**
- Purpose: Present weather information and handle user interactions
- Location: `src/accessiweather/ui/`
- Contains: Main window (`main_window.py`), modal dialogs (`dialogs/`), system tray integration (`system_tray.py`)
- Depends on: Display layer (presentation), models, services
- Used by: Main application entry point

**Presentation Layer:**
- Purpose: Transform raw weather data into structured, accessible view models
- Location: `src/accessiweather/display/`
- Contains: `WeatherPresenter` orchestrator, presentation classes (`presentation/`), formatters
- Depends on: Models, utilities for formatting
- Used by: UI layer, business logic

**Business Logic Layer:**
- Purpose: Orchestrate weather data fetching, alert management, and state transitions
- Location: `src/accessiweather/` (core modules)
- Contains: `WeatherClient` (multi-source orchestration), `AlertManager` (state tracking), `AlertNotificationSystem` (delivery), background tasks
- Depends on: API clients, cache, models, services
- Used by: App initialization, UI event handlers

**Service Layer:**
- Purpose: Provide cross-cutting concerns and specialized operations
- Location: `src/accessiweather/services/`
- Contains: Weather service (`weather_service/`), update service, platform detection, environmental data, national discussion fetching
- Depends on: API clients, models, utilities
- Used by: Business logic layer, app initialization

**API Client Layer:**
- Purpose: Encapsulate external API communication
- Location: `src/accessiweather/api/`, `src/accessiweather/api_client/`
- Contains: NWS client (`api/nws/`), Open-Meteo wrapper, Visual Crossing client, endpoint-specific handlers
- Depends on: HTTP client (`httpx`), models
- Used by: Business logic (WeatherClient), services

**Data Model Layer:**
- Purpose: Define domain objects and configuration structures
- Location: `src/accessiweather/models/`
- Contains: Weather data models (`weather.py`), alert models (`alerts.py`), configuration (`config.py`), errors
- Depends on: Python stdlib only
- Used by: All other layers

**Support Modules:**
- Purpose: Cross-cutting utilities and configuration
- Location: `src/accessiweather/` (utilities), `src/accessiweather/config/`
- Contains: Cache, configuration management, geocoding, logging, screen reader integration, paths
- Depends on: Models, stdlib
- Used by: All layers

## Data Flow

**Weather Fetch Flow:**

1. User selects location in UI → `MainWindow` calls `WeatherClient.fetch_weather(location)`
2. `WeatherClient._fetch_nws_data()` and `._fetch_openmeteo_data()` execute in parallel via `asyncio.gather()`
3. Each data fetch:
   - Checks `WeatherDataCache` for valid cached entry (5-min default TTL)
   - If cache miss: Makes parallel API calls (current, forecast, alerts, hourly) via `retry_with_backoff()`
   - Parses responses via weather-source-specific parsers (`weather_client_nws.py`, `weather_client_openmeteo.py`)
   - Returns structured data models
4. `DataFusionEngine` reconciles multi-source data based on `SourcePriorityConfig`
5. `AlertAggregator` processes alerts with `alert_lifecycle.diff_alerts()` for change detection
6. Optional enrichment via `weather_client_enrichment.py` (confidence, trends, environmental data)
7. Final `WeatherData` object passed to `WeatherPresenter` for formatting
8. Presenter generates `CurrentConditionsPresentation`, `ForecastPresentation`, alert summaries
9. UI layer receives presentation objects and renders via wxPython widgets

**Alert Notification Flow:**

1. `WeatherClient.fetch_weather()` detects alert changes via `AlertLifecycleDiff`
2. `AlertNotificationSystem.process_alerts_for_notification()` evaluates each alert against `AlertManager` state
3. `AlertManager` checks cooldown rules (`per_alert_cooldown`, `global_cooldown`, `escalation_cooldown`)
4. If notification passes filters, `format_accessible_message()` generates screen-reader-friendly title/message
5. `SafeDesktopNotifier.notify()` sends toast notification (platform-specific: `winsound` on Windows, `playsound3` on macOS/Linux)
6. `AlertManager.record_notification()` updates state with timestamp and count
7. Sound pack system plays associated alert sound via `sound_player.py`

**Configuration Flow:**

1. App startup: `ConfigManager.load_config()` reads `~/.config/accessiweather/accessiweather.json`
2. `LocationOperations` loads saved locations into memory
3. `SettingsOperations` applies user preferences
4. `SecureStorage`/`LazySecureStorage` defers keyring access until API keys needed
5. `SourcePriorityConfig` determines weather source routing
6. Settings applied throughout lifecycle: `WeatherClient.settings`, `AlertManager.alerts_enabled`, presentation formatters

**State Management:**

- **Cache State:** `WeatherDataCache` holds in-memory entries with expiration tracking
- **Alert State:** `AlertManager` maintains `AlertState` per alert with content hash history, notification counts, last-seen timestamps
- **Config State:** `ConfigManager._config` holds in-memory `AppConfig` (settings, locations, secrets)
- **In-Flight Requests:** `WeatherClient._in_flight_requests` deduplicates concurrent fetch requests
- **Previous Alerts:** `WeatherClient._previous_alerts` cached for lifecycle diffing on next fetch

## Key Abstractions

**WeatherClient:**
- Purpose: Unified interface for multi-source weather data fetching
- Examples: `src/accessiweather/weather_client_base.py`, `weather_client_nws.py`, `weather_client_openmeteo.py`
- Pattern: Facade with optional method overrides for testing; uses internal modules for source-specific logic

**AlertManager:**
- Purpose: Stateful alert lifecycle tracking with change detection and notification rate limiting
- Examples: `src/accessiweather/alert_manager.py`
- Pattern: State machine; maintains bounded history of alert content hashes for escalation/change detection

**WeatherPresenter:**
- Purpose: Transform raw `WeatherData` into display-ready presentation objects
- Examples: `src/accessiweather/display/weather_presenter.py`, `presentation/formatters.py`
- Pattern: Builder pattern; generates structured view models with fallback text for accessibility

**ConfigManager:**
- Purpose: Centralized configuration orchestration with lazy loading
- Examples: `src/accessiweather/config/config_manager.py`
- Pattern: Delegate pattern; delegates to `LocationOperations`, `SettingsOperations`, `SecureStorage` for domain-specific logic

**EnvironmentalDataClient:**
- Purpose: Provide air quality and pollen data from secondary sources
- Examples: `src/accessiweather/services/environmental_client.py`
- Pattern: Lazy initialization; only instantiated if `air_quality_enabled` or `pollen_enabled`

## Entry Points

**Application Startup:**
- Location: `src/accessiweather/__main__.py` or `src/accessiweather/main.py`
- Triggers: User launches executable or `python -m accessiweather`
- Responsibilities: Set Windows AppUserModelID (if Windows), initialize wx App, load config, create UI, start background tasks

**Main App Class:**
- Location: `src/accessiweather/app.py` (wxPython `wx.App` subclass)
- Triggers: wx event loop initialization
- Responsibilities: Create main window, initialize managers (ConfigManager, AlertManager, WeatherClient), set up event bindings

**Main Window:**
- Location: `src/accessiweather/ui/main_window.py`
- Triggers: Created by app, shown on startup
- Responsibilities: Render location selector, current/forecast display, alerts list, menu bar; bind UI events to handlers

**Background Tasks:**
- Location: Various async methods launched via `asyncio.create_task()`
- Triggers: Initialization, timer events, user actions
- Responsibilities: Periodic weather refresh, alert polling, notification delivery

## Error Handling

**Strategy:** Defensive with fallback and graceful degradation

**Patterns:**

- **API Timeouts:** `APITimeoutError` caught in `WeatherClient._fetch_nws_data()` and `._fetch_openmeteo_data()` → return `None` values → UI displays cached data or "stale data" warning
- **Invalid Location:** Caught during geocoding → user sees error dialog → original location preserved
- **Missing Config:** `ConfigManager.load_config()` creates default `AppConfig` if file missing
- **Keyring Access Failures:** `SecureStorage` catches exceptions, logs warning, returns empty string for API key → disables that integration
- **JSON Decode Errors:** Caught in cache load/save operations → rebuilds cache from scratch
- **HTTP Connection Errors:** `httpx` retry logic with exponential backoff via `retry_with_backoff()` utility
- **Alert State Corruption:** `AlertManager` validates state on load, falls back to fresh state if corrupted

## Cross-Cutting Concerns

**Logging:** Stdlib `logging` module with `logging.basicConfig()` set in `app.py` (INFO level). Modules use `logger = logging.getLogger(__name__)` pattern.

**Validation:**
- Coordinates validated before API calls (latitude -90 to 90, longitude -180 to 180)
- Location names sanitized before display
- API responses validated against dataclass constructors (raises `ValidationError` if invalid)

**Authentication:**
- API keys stored securely via `keyring` system keychain
- `LazySecureStorage` defers keyring access until first use
- No credentials logged; sensitive data masked in log output (`api_key[:4]...`)

**Accessibility:**
- All wxPython widgets named appropriately (e.g., `name="Location selection"`)
- Alert messages formatted via `format_accessible_message()` for screen reader clarity
- Status updates announced via text widget updates
- Focus management in dialogs (SizedFrame/SizedPanel with proper sizer chains)

**Performance:**
- In-flight request deduplication via `_in_flight_requests` map
- HTTP connection pooling with `httpx.Limits` (30 max, 15 keepalive)
- Cache with 5-minute default TTL to reduce API load
- Lazy module imports in `services.__init__` via `__getattr__()`
- Presentation formatting deferred until display (not during fetch)

---

*Architecture analysis: 2026-03-14*
