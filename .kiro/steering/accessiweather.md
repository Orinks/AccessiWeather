---
inclusion: always
---

# AccessiWeather Development Guide

## Core Architecture

**Main Application**: `AccessiWeatherApp(toga.App)` in `src/accessiweather/app.py`
- Configuration: Access via `app.config_manager.get_config().settings` (returns `AppSettings`)
- Never use `app.config` or `app.config_manager.settings` directly
- Config structure: `AppConfig` contains `settings: AppSettings` and `locations: list[Location]`

**Key Modules**:
- `weather_client.py` - Multi-source weather data orchestration
- `config/` - Configuration management with JSON persistence
- `api/` - Weather API wrappers (NWS, Open-Meteo, Visual Crossing)
- `ui_builder.py` - Toga UI construction
- `cache.py` - 5-minute TTL cache for API responses

## Critical Patterns & Rules

### Configuration Access
```python
# ALWAYS use this pattern
settings = app.config_manager.get_config().settings

# NEVER use these (will cause AttributeError)
# settings = app.config_manager.settings
# settings = app.config.settings
```

### Error Handling
Use Toga's built-in dialogs for all user-facing errors:
```python
# Standard pattern for async operations
try:
    result = await some_operation()
except SpecificError as e:
    logger.warning(f"Operation failed: {e}")
    await app.main_window.error_dialog("Operation Failed", str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    await app.main_window.error_dialog("Unexpected Error", f"An error occurred: {e}")

# For validation failures
if not valid_input:
    await app.main_window.error_dialog("Invalid Input", "Please check your data.")
    return

# Success notifications
await app.main_window.info_dialog("Success", "Operation completed.")
```

### UI Components & Accessibility
**MANDATORY**: Every UI element must have accessibility attributes:
```python
button = toga.Button("Save", on_press=save_handler)
button.aria_label = "Save current settings"
button.aria_description = "Saves all configuration changes to disk"

# For headings
label = toga.Label("Weather Settings")
label.aria_role = "heading"
label.aria_level = 2

# For dynamic content
status_label = toga.Label("Loading...")
status_label.aria_live = "polite"  # Use "assertive" for urgent updates
```

### Async Operations
```python
# Fire-and-forget background tasks
asyncio.create_task(update_weather_data())

# Blocking operations
result = await asyncio.to_thread(expensive_computation, args)

# NEVER use asyncio.run() in Toga apps - breaks event loop
```

### File Operations
Always use Toga's file dialogs:
```python
# File selection
file_path = await app.main_window.open_file_dialog(
    title="Select Configuration",
    file_types=["json"]
)

# Save dialog
save_path = await app.main_window.save_file_dialog(
    title="Export Settings",
    suggested_filename="weather_config.json",
    file_types=["json"]
)
```

### Cross-Platform Path Handling
```python
import ntpath  # Use for Windows paths even on Linux (CI compatibility)

# Correct cross-platform Windows path handling
app_dir = ntpath.dirname(sys.executable)
normalized = ntpath.normpath(path).lower()

# AVOID os.path for Windows paths - fails on Linux CI
```

## Testing Guidelines

**Test Markers**:
- `@pytest.mark.unit` - Fast, isolated tests (run in CI)
- `@pytest.mark.integration` - Real API calls (skipped in CI with `-m "not integration"`)

**Toga Testing**: Set `TOGA_BACKEND=toga_dummy` environment variable

## Common Pitfalls

1. **Config Access**: Use `app.config_manager.get_config().settings`, not direct attribute access
2. **Path Operations**: Use `ntpath` for Windows paths to ensure CI compatibility
3. **Async in Toga**: Never use `asyncio.run()` - use `create_task()` or `to_thread()`
4. **UI Accessibility**: Every element needs `aria_label` and `aria_description`
5. **OptionContainer**: Use `.content.append(title, widget)` (two separate arguments)
6. **Error Dialogs**: Use built-in `app.main_window.error_dialog()`, not custom classes
7. **Integration Tests**: Mark with `@pytest.mark.integration` to skip in CI

## Code Style

- **Line Length**: 100 characters (Ruff formatting)
- **Type Hints**: Modern syntax (`dict[str, Any]`, not `Dict`)
- **Imports**: Use `from __future__ import annotations` for forward references
- **Async**: Prefer `await` over callbacks; use `create_task()` for background work
