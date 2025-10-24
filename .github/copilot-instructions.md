# AccessiWeather AI Coding Agent Instructions

## Project Overview
AccessiWeather is a cross-platform, accessible desktop weather application built with BeeWare/Toga (v0.9+) framework and Briefcase for packaging. The app targets Python 3.10+ (3.12 recommended) and prioritizes screen reader accessibility, multi-source weather data, and a simple architecture.

## Core Architecture

### Weather Data Sources (Multi-Source Strategy)
- **Primary**: NWS API (weather.gov) for US locations - most accurate, no API key required
- **Fallback**: Open-Meteo for NWS failures or international locations - free, no API key
- **Enrichment**: Visual Crossing for enhanced alert data - requires API key, optional
- **Data Flow**: `WeatherClient` coordinates sources, `WeatherDataCache` caches responses (5-minute default)
- **Alert System**: `AlertManager` + `AlertNotificationSystem` handle notifications with rate limiting and severity filtering

### Application Structure
- **Entry Point**: `src/accessiweather/app.py` - Main `AccessiWeatherApp(toga.App)` class
- **Config Management**: `ConfigManager` (JSON-based, uses `toga.App.paths.config`)
  - Portable mode supported: checks for `portable.txt` flag to use local config directory
  - Settings: `AppSettings` model with validation in `config/settings.py`
  - Locations: `LocationOperations` in `config/locations.py`
- **UI Builder**: `ui_builder.py` creates main window and menu system
- **Display Layer**: `WeatherPresenter` formats weather data for screen readers
- **Background Tasks**: Periodic updates via `asyncio.create_task` in `background_tasks.py`

### API Structure
- `api/nws/`: National Weather Service API wrappers (alerts, forecasts, gridpoints)
- `api/openmeteo_wrapper.py`: Open-Meteo integration
- `api/visualcrossing/`: Visual Crossing API (alerts, historical data)
- `api/base_wrapper.py`: Shared HTTP client patterns with retries

## Toga Framework Specifics

### Critical Patterns
1. **OptionContainer API**: Use `option_container.content.append(title, widget)` with TWO separate arguments, NOT `.add(title, widget)` or tuple format
2. **Accessibility**: ALL UI elements MUST have `aria_label` and `aria_description` attributes
3. **Testing**: Use Toga dummy backend (`toga_dummy` package) for unit tests
   - Set `TOGA_BACKEND=toga_dummy` environment variable
   - Fallback to `toga_winforms` on Windows if dummy unavailable
4. **Async Operations**: Toga uses `asyncio` - all long-running operations must be async
5. **Main Thread**: UI updates must happen on main thread, use `app.add_background_task()` for background work

### Common Gotchas
- OptionContainer: Use `.content.append(title, widget)` with two arguments, NOT tuple format `(title, widget)`
- Toga Selection widget (dropdown) uses `.items` list and `.value` property
- Modal dialogs: Create with `toga.Window`, show with `.show()`, close with `.close()`
- Focus management: Call `.focus()` on widgets for accessibility (may fail silently on some platforms)

## Development Workflow

### Local Development
```bash
# Run app in development mode (hot reload)
briefcase dev

# Run tests (uses pytest with Toga dummy backend)
pytest -v -p pytest_asyncio

# Format code (required before commit)
ruff format .

# Lint code
ruff check --fix .

# Type checking (optional, can be noisy)
pyright
```

### Pre-Commit Hooks
- Auto-formats code with `ruff format` (line length 100)
- Auto-fixes linting issues with `ruff check --fix`
- Runs last-failed unit tests (`pytest --lf --ff -m "unit"`)
- Type checks with pyright (excludes tests/)
- **Important**: Pre-commit will auto-stage formatted files

### Build & Package
```bash
# Create platform-specific app bundle
briefcase create

# Build installer (MSI on Windows, DMG on macOS, AppImage on Linux)
briefcase build

# Package for distribution
briefcase package
```

### Testing Conventions
- **Unit tests**: Fast, isolated tests in `tests/test_*.py`
- **Integration tests**: Test real API calls (marked with `@pytest.mark.integration`)
- **Fixtures**: Reusable test fixtures in `tests/toga_test_helpers.py`
  - `DummyConfigManager`: Mock config manager for testing
  - `WeatherDataFactory`: Creates mock weather data
  - `mock_app`: Toga app instance with dummy backend
- **Coverage**: Target 80%+ coverage (current: ~85%)

## Configuration System

### Config Structure
- **Storage**: `~/.config/accessiweather/accessiweather.json` (or portable directory)
- **Models**:
  - `AppConfig`: Top-level config with `settings`, `locations`, `last_location`
  - `AppSettings`: User preferences (units, display options, notifications, API keys)
  - `Location`: Saved locations with name, lat/lon
- **Validation**: `SettingsOperations._validate_and_fix_config()` ensures sane defaults

### Settings Patterns
- **Apply Settings**: Use `getattr(dialog, attr_name, None)` for defensive attribute access
- **Collect Settings**: Use `getattr(dialog, attr_name, fallback_value)` with defaults
- **Switches**: Toga Switch widgets with `.value` property (bool)
- **Number Inputs**: Use `.value` property (float), set `.min_value`/`.max_value` constraints

## Accessibility Requirements

### Screen Reader Support
- **Labels**: Every input/button/switch needs `aria_label` (short label)
- **Descriptions**: Every control needs `aria_description` (detailed explanation)
- **Keyboard Navigation**: All dialogs must support Tab/Shift+Tab navigation
- **Focus Management**: Set initial focus on most relevant widget (usually location dropdown)
- **Announcements**: Use descriptive text for status updates

### Example Pattern
```python
switch = toga.Switch(
    text="Enable feature",
    value=False
)
switch.aria_label = "Feature toggle"
switch.aria_description = "Enable or disable the feature functionality"
```

## Common Tasks

### Adding Settings UI
1. Add attribute to `SettingsDialog` class (e.g., `self.new_setting_switch`)
2. Create UI in appropriate settings tab function in `dialogs/settings_tabs.py`
3. Add to `apply_settings_to_ui()` in `dialogs/settings_handlers.py` (load from config)
4. Add to `collect_settings_from_ui()` in `dialogs/settings_handlers.py` (save to config)
5. Add to `AppSettings` model if new field needed
6. Write tests in `tests/test_toga_ui_components.py`

### Adding Weather API Integration
1. Create wrapper module in `api/` directory (follow `base_wrapper.py` pattern)
2. Add client class with `async` methods using `httpx.AsyncClient`
3. Integrate into `WeatherClient` with fallback logic
4. Add cache support with `WeatherDataCache`
5. Update tests with mocked responses

### Debugging Weather Issues
1. Enable debug logging: Set `ACCESSIWEATHER_DEBUG=1` environment variable
2. Check API responses: Look for 404/503 errors in logs
3. Verify location: NWS requires US locations with valid lat/lon
4. Test with curl: `curl -H "User-Agent: AccessiWeather/0.4" https://api.weather.gov/alerts/active?point=lat,lon`

## Code Style

### Ruff Configuration
- Line length: 100 characters
- Target: Python 3.12
- Auto-fixes: Import sorting, unused variables, whitespace
- Excludes: `weather_gov_api_client/` (auto-generated code)

### Type Hints
- Use modern syntax: `dict[str, Any]` not `Dict[str, Any]`
- Import from `__future__`: `from __future__ import annotations` for forward refs
- Optional imports: Use `TYPE_CHECKING` guard for type-only imports to avoid cycles

### Async Patterns
- Always `await` async functions
- Use `asyncio.create_task()` for fire-and-forget operations
- Add done callbacks: `task.add_done_callback(background_tasks.task_done_callback)`
- Avoid `asyncio.run()` in Toga apps (use app's event loop)

## Common Pitfalls

1. **OptionContainer**: Don't use `.add()` method, it doesn't exist
2. **Config Loading**: Always call `config_manager.load_config()` before accessing settings
3. **NWS Alerts**: Minor severity alerts disabled by default (user configurable)
4. **Toga Focus**: `.focus()` may fail silently on some platforms, always try-except
5. **Pre-commit**: Will auto-format and fail if tests don't pass, fix tests before retrying
6. **Alert Notifications**: Must respect rate limits (cooldowns, max per hour) to avoid spam
7. **API Keys**: Visual Crossing requires API key in settings, gracefully degrade if missing

## Resources

- Toga Docs: https://toga.readthedocs.io/
- BeeWare Tutorial: https://beeware.org/
- NWS API: https://www.weather.gov/documentation/services-web-api
- Open-Meteo: https://open-meteo.com/en/docs
- Briefcase Docs: https://briefcase.readthedocs.io/
