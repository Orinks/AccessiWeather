# Refactor Concerns & Risks — AccessiWeather

## Summary
The "extract don't rewrite" approach is sound for this codebase. Some partial extractions have already been done (app_initialization, app_helpers, weather_client_enrichment, weather_client_fusion, etc.). The remaining large files have specific coupling risks documented below.

---

## Target 1: `weather_client_base.py` (1,399 lines)

### What's left to extract
The `WeatherClient` class still owns:
- 15 private unit conversion helpers (`_convert_mps_to_mph`, `_convert_pa_to_inches`, etc., lines 1355–1398)
- `_merge_current_conditions` (~60+ lines)
- HTTP client lifecycle (`_get_http_client`, httpx session setup)
- Cache delegation (`get_cached_weather`, `_persist_weather_data`)

### Coupling risks
- **Unit conversion methods** are called extensively by subclass methods and parsers. Extracting to `utils/unit_conversion.py` requires updating all call sites that use `self._convert_*`.
- **`WeatherClient` is re-exported** through `weather_client.py` → `__init__.py`. Public interface is stable; internal method moves are safe.
- **`_get_http_client()`** is inherited by NWS and OpenMeteo subclasses (if inheritance used). Verify whether subclasses call `super()._get_http_client()`.
- **Alert deduplication** references are already delegated — low risk.

### Test risk: MEDIUM
- 63.4% coverage means 148 uncovered lines. Extraction could move uncovered code — ensure tests accompany each extracted module.

---

## Target 2: `weather_client_nws.py` (1,533 lines)

### What's left to extract
- **Module-level helper functions** (lines 41–233): small pure functions, easy to extract to `weather_client_nws_helpers.py`
- **4 large parse functions** (lines 1235–end): `parse_nws_current_conditions`, `parse_nws_forecast`, `parse_nws_alerts`, `parse_nws_hourly_forecast` — these are already module-level (not class methods), making extraction mechanical
- **NWS API call logic** (lines 234–~1234): station selection, observation fetching, grid point lookups

### Coupling risks
- **Parsers are already called via `weather_client_parsers.py`** — check if it's a shim that re-exports from `weather_client_nws.py` or has its own implementations
- **`parse_nws_current_conditions`** takes raw API dict and returns `CurrentConditions` model — no `self` dependency, pure function extraction
- **`_station_sort_key`, `_scrub_measurements`** are helper functions used within the parse functions — must move together
- **Import chain**: `weather_client_base.py` imports `weather_client_nws as nws_client` — after extraction, update import to new module name

### Test risk: HIGH
- 54.8% coverage (309 missing lines) — worst of the 4 targets
- Large parse functions are complex; edge cases likely untested
- **Mandatory**: write tests for extracted parse functions before/during extraction

---

## Target 3: `app.py` (1,693 lines)

### What's left to extract
1. **Windows toast identity helpers** (~440 lines of module-level code before `AccessiWeatherApp`):
   - `set_windows_app_user_model_id`, `_is_unc_path`, `_needs_shortcut_repair`, `_run_powershell_json`, `_resolve_start_menu_shortcut_path`, `_toast_identity_stamp_path`, `_load_toast_identity_stamp`, `_should_repair_shortcut`, `_write_toast_identity_stamp`, `ensure_windows_toast_identity`
   - Natural extraction target: `windows_toast_identity.py`
2. **Timer management** (lines ~1240–1320): `_stop_auto_update_checks`, `_start_auto_update_checks`, `_on_auto_update_check_timer`, `_stop_background_updates`, `_start_background_updates`
3. **Update download/apply** (lines ~1289–1462): `_check_for_updates_on_startup`, `_download_and_apply_update` (~80 lines)
4. **Tray icon setup** (lines ~1174–1220): `_initialize_tray_icon`, `_initialize_taskbar_updater`, `_show_or_minimize_window`

### Coupling risks
- **`AccessiWeatherApp` instance (`self`) is threaded through everything** — extracted functions will need `app` parameter (pattern already established by `app_initialization.py`)
- **`self._update_timer`, `self._event_check_timer`, `self._auto_update_check_timer`** are instance state — timer manager module needs app reference or must return timers
- **Windows toast helpers are already platform-guarded** (`if sys.platform != "win32": return`) — safe to extract to separate module
- **Notifier property** has lazy init logic that interacts with platform detection — keep in app.py or extract carefully
- `app_initialization.py` already established the pattern: `def initialize_components(app: AccessiWeatherApp)` — use same pattern for timer manager

### Test risk: LOW
- 91.3% coverage — well tested
- Module-level Windows toast helpers have platform guards; tests likely mock platform

---

## Target 4: `main_window.py` (1,390 lines)

### What's left to extract
1. **Notification event handling** (lines ~933–1000, ~1256–1303): `refresh_notification_events_async`, `_get_notification_event_manager`, `_get_fallback_notifier`, `_on_notification_event_data_received`, `_process_notification_events`
2. **Dialog management** (lines ~462–640): `_on_explain_weather`, `_on_discussion`, `_on_aviation`, `_on_air_quality`, `_on_uv_index`, `_on_noaa_radio`, `_on_weather_chat`, `_on_soundpack_manager`
3. **Debug/test notification helpers** (lines ~638–778): test notification methods — could be a debug mixin

### Coupling risks
- **`self` (MainWindow) carries `app` reference** — extracted methods need `window` parameter
- **`_get_discussion_service()`** (line 996, ~50 lines) — lazy-initializes a service, accesses `self.app.config_manager` — tight coupling to both window and app
- **Event handlers** that interact with wx widgets need `self` — can't be plain functions without window reference; mixin pattern is cleaner
- **`_process_notification_events`** calls into `alert_manager` and `alert_notification_system` via `self.app` — deep coupling
- **Coverage is excluded** — no coverage data; need manual test review before extraction

### Test risk: MEDIUM-HIGH
- UI excluded from coverage measurement
- `tests/gui/` directory exists but scope unknown
- Notification event tests in `test_notification_event_manager.py`, `test_split_notification_timers.py`

---

## Cross-Cutting Risks

### Circular Import Risk
- **Current mitigation**: lazy imports inside function bodies, `TYPE_CHECKING` guards
- **Risk**: extracted modules that import from `app.py` or `main_window.py` create new cycles
- **Mitigation**: extracted modules should only import from models, utils, and services — never from app/main_window

### Thread Safety
- wx.Timer callbacks fire on main thread — safe
- Async completions use `wx.CallAfter` — safe
- Extracted timer modules must not introduce new threading primitives

### Import Forwarding for Backward Compat
- `weather_client.py` is a 1-line re-export shim for `WeatherClient`
- After extraction, add similar shims if any internal import path changes
- Public API: `from accessiweather import WeatherClient` must remain stable

### Test Strategy Per PR
- Each extraction PR must include:
  1. Moved code (no logic changes)
  2. Updated imports in all consumers
  3. Import forwarding shim if public path changes
  4. New tests for previously uncovered code in extracted module
  5. `pytest --tb=short -x` must pass

### Safe Extraction Order (recommended)
1. `windows_toast_identity.py` from `app.py` (pure functions, platform-guarded, well-tested)
2. Unit conversion helpers from `weather_client_base.py` (pure functions, no state)
3. NWS parse functions from `weather_client_nws.py` (already module-level, add tests first)
4. Timer management from `app.py` (uses established `app_initialization.py` pattern)
5. Notification event handling from `main_window.py` (needs careful interface design)
