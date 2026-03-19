# Architecture — AccessiWeather

## High-Level Structure

```
src/accessiweather/
├── app.py                    # wx.App subclass — application lifecycle (1,693 lines) ← TARGET
├── app_initialization.py     # Extracted: component init, deferred startup (270 lines)
├── app_helpers.py            # Extracted: minor helpers (61 lines)
├── ui/
│   ├── main_window.py        # wx.Frame — primary window (1,390 lines) ← TARGET
│   └── system_tray.py        # Tray icon handler (286 lines)
├── weather_client_base.py    # WeatherClient class (1,399 lines) ← TARGET
├── weather_client.py         # Re-export shim: `from .weather_client_base import WeatherClient`
├── weather_client_nws.py     # NWS API calls + parsers (1,533 lines) ← TARGET
├── weather_client_parsers.py # Already extracted parser delegation shim
├── weather_client_enrichment.py  # Enrichment logic (435 lines) — already extracted
├── weather_client_fusion.py      # Data fusion engine (370 lines) — already extracted
├── weather_client_parallel.py    # Parallel fetch coordinator — already extracted
├── weather_client_alerts.py      # Alert aggregator — already extracted
├── weather_client_trends.py      # Trend insights — already extracted
├── weather_client_openmeteo.py   # OpenMeteo source (607 lines)
├── weather_client_visualcrossing.py  # VC source
├── cache.py                  # WeatherDataCache (715 lines)
├── alert_manager.py          # Alert dedup & management (689 lines)
├── alert_notification_system.py  # Alert notification dispatch (562 lines)
├── models/                   # attrs-based data models
├── config/                   # ConfigManager, source priority
├── display/                  # WeatherPresenter (formatting layer)
├── services/                 # Environmental data client
├── notifications/            # Notification event manager
├── performance/              # Perf timers
├── noaa_radio/               # NOAA radio player
└── utils/                    # retry, unit conversion helpers
```

## Layer Model

```
Entry Point (main.py / cli.py)
    ↓
AccessiWeatherApp (app.py) — wx.App lifecycle, timers, tray
    ↓
MainWindow (ui/main_window.py) — all user-facing widgets & menus
    ↓
WeatherClient (weather_client_base.py) — orchestrates data fetching
    ├── WeatherClientNWS (weather_client_nws.py) — NWS API + parsing
    ├── WeatherClientOpenMeteo (weather_client_openmeteo.py) — OM source
    ├── VisualCrossingClient — VC source
    ├── ParallelFetchCoordinator — concurrent fetch
    ├── DataFusionEngine — source merging
    ├── AlertAggregator — alert dedup
    └── Enrichment / Trends
    ↓
Models (attrs) / Cache / Config
```

## Key Classes

### `AccessiWeatherApp` (app.py:443)
Subclasses `wx.App`. Responsibilities mixed across 1,693 lines:
- **Windows toast identity** (~440 lines of module-level helpers before the class)
- **OnInit** — orchestrates full startup sequence
- **Onboarding flow** — first-start wizard, API key prompts, portable mode
- **Timer management** — `_update_timer`, `_auto_update_check_timer`, `_event_check_timer` (wx.Timer)
- **Background async** — runs asyncio loop in daemon thread, `run_async()` / `call_after_async()`
- **Auto-update checks** — download, verify, apply update
- **Tray icon** — initialize/teardown `TaskbarIconUpdater`
- **Notifier property** — lazy init of `desktop-notifier` / `toasted`
- **Runtime settings refresh** — re-reads config, restarts timers

### `MainWindow` (ui/main_window.py:23)
Subclasses `SizedFrame`. Responsibilities:
- **Widget creation** — location chooser, conditions panel, alerts list, forecast tabs
- **Menu bar** — full menu tree with all actions
- **Keyboard shortcuts** — escape accelerator, focus management
- **Weather data callbacks** — `_on_weather_data_received`, `_on_weather_error`
- **Alert display** — `_update_alerts`, `_show_alert_details`
- **Notification event processing** — `_on_notification_event_data_received`, `_process_notification_events`
- **Dialog launchers** — discussion, aviation, AI explainer, NOAA radio, settings, history
- **Tray minimize logic** — `_should_minimize_to_tray`, `_minimize_to_tray`

### `WeatherClient` (weather_client_base.py:52)
Single class, 1,399 lines. Already delegates to extracted modules for enrichment/fusion/parallel/alerts/trends. Still contains:
- **HTTP client management** — `_get_http_client()`, httpx session
- **Cache integration** — `get_cached_weather()`
- **Source orchestration** — `_determine_api_choice()`, fetch coordination
- **Unit conversion methods** — ~15 private conversion helpers (lines 1355–1398)
- **Parse delegation stubs** — thin wrappers that call into parsers module
- **Merge logic** — `_merge_current_conditions()`
- **Data persistence** — `_persist_weather_data()`

### `WeatherClientNWS` (weather_client_nws.py)
Not a class — a module of functions. Contains:
- **Module-level helper functions** (lines 41–233): `_parse_iso_datetime`, `_station_sort_key`, `_scrub_measurements`, `_extract_scalar`, `_extract_float`, `_format_unit`, `_format_wind_speed`, etc.
- **Large parsing functions** (lines 1235–end): `parse_nws_current_conditions`, `parse_nws_forecast`, `parse_nws_alerts`, `parse_nws_hourly_forecast`
- Lines 234–1234 (~1,000 lines) are NWS API call implementations

## Public Interface Surface
- `WeatherClient` class is re-exported via `weather_client.py` → `__init__.py`
- `AccessiWeatherApp` is instantiated in `main.py`
- `MainWindow` is created by `AccessiWeatherApp.OnInit`
- All inter-module wiring happens through these three classes

## Threading Model
- **Main thread**: wx event loop
- **Async thread**: `asyncio.new_event_loop()` in `daemon=True` Thread
- **wx.CallAfter**: bridges async results back to main thread
- **wx.Timer**: drives periodic refresh (background updates, auto-update checks)
