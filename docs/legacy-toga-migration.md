# Legacy Toga UI Code Migration

This document tracks the migration from Toga to wxPython for the AccessiWeather UI.

## Status: wxPython Migration Complete

The main application UI has been fully migrated to wxPython. The legacy Toga UI code has been removed.

## Removed Directories and Files

The following legacy Toga UI code has been removed:

### Source Files (Deleted)

- `src/accessiweather/handlers/` - Toga event handlers
  - `ai_handlers.py`
  - `alert_handlers.py`
  - `aviation_handlers.py`
  - `location_handlers.py`
  - `settings_handlers.py`
  - `update_handlers.py`
  - `weather_handlers.py`
  - `__init__.py`

- `src/accessiweather/dialogs/` - Toga dialog implementations
  - `air_quality_dialog.py`
  - `aviation_dialog.py`
  - `community_packs_browser_dialog.py`
  - `discussion.py`
  - `explanation_dialog.py`
  - `location_dialog.py`
  - `model_selection.py`
  - `settings_dialog.py`
  - `settings_handlers.py`
  - `settings_operations.py`
  - `settings_tabs.py`
  - `soundpack_manager_dialog.py`
  - `soundpack_wizard_dialog.py`
  - `update_progress_dialog.py`
  - `uv_index_dialog.py`
  - `weather_history_dialog.py`
  - `soundpack_manager/` (subdirectory)
  - `__init__.py`

- `src/accessiweather/ui_builder.py` - Toga UI construction
- `src/accessiweather/event_handlers.py` - Toga event handler re-exports
- `src/accessiweather/alert_details_dialog.py` - Toga alert dialog

### Test Files (Excluded from Collection)

The following test files have been excluded from pytest collection via `collect_ignore` in `tests/conftest.py`. They test the removed Toga UI code and need to be migrated to test the wxPython equivalents:

| Test File | Coverage | Migration Priority |
|-----------|----------|-------------------|
| `test_toga_ui_components.py` | General Toga UI | Low - covered by wxPython tests |
| `test_settings_dialog.py` | Settings dialog | Medium |
| `test_settings_priority_tab.py` | Display priority settings | Medium |
| `test_settings_save_priority.py` | Settings save handlers | Medium |
| `test_settings_openmeteo_model.py` | Model selection settings | Medium |
| `test_settings_visual_crossing_validation.py` | API key validation | Medium |
| `test_air_quality_dialog.py` | Air quality dialog | Low |
| `test_air_quality_integration.py` | Air quality handlers | Low |
| `test_uv_index_dialog.py` | UV index dialog | Low |
| `test_uv_index_integration.py` | UV index handlers | Low |
| `test_aviation_handlers.py` | Aviation weather handlers | Low |
| `test_location_handlers.py` | Location management | Medium |
| `test_keyboard_shortcuts.py` | Keyboard shortcuts | Medium |
| `test_system_tray_integration.py` | System tray | High |
| `test_system_tray_window_management.py` | Window management | High |
| `test_weather_display_updates.py` | Weather display updates | High |
| `test_update_progress_dialog.py` | Update progress UI | Low |
| `test_sound_pack_system.py` | Sound pack manager dialog | Low |
| `test_forecast_heading_properties.py` | Forecast formatting | Low |
| `test_hourly_aqi_ui_integration.py` | Hourly AQI display | Low |
| `test_alert_ui_accessibility.py` | Alert accessibility | Medium |
| `test_additional_coverage.py` | Misc coverage | Low |

## New wxPython UI Location

The new wxPython UI code is located in:

- `src/accessiweather/ui/main_window.py` - Main application window
- `src/accessiweather/ui/dialogs/` - wxPython dialog implementations
  - `air_quality_dialog.py`
  - `alert_dialog.py`
  - `aviation_dialog.py`
  - `community_packs_dialog.py`
  - `explanation_dialog.py`
  - `location_dialog.py`
  - `progress_dialog.py`
  - `settings_dialog.py`
  - `soundpack_manager_dialog.py`
  - `soundpack_wizard_dialog.py`
  - `uv_index_dialog.py`
  - `weather_history_dialog.py`

## Migrating Tests

To migrate a test file from Toga to wxPython:

1. Update imports from `accessiweather.dialogs` to `accessiweather.ui.dialogs`
2. Update imports from `accessiweather.handlers` to the appropriate wxPython handlers
3. Replace Toga widget mocking with wxPython widget mocking
4. Update assertions to match wxPython widget APIs
5. Remove the test file from `collect_ignore` in `tests/conftest.py`
6. Run the tests to verify they pass

### Example Import Change

```python
# Old Toga import
from accessiweather.dialogs.settings_dialog import SettingsDialog

# New wxPython import
from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple
```

## Backend Code Preserved

The following backend code was preserved (not UI-specific):

- `src/accessiweather/ai_explainer.py` - AI explanation logic (UI function removed)
- `src/accessiweather/app_helpers.py` - Utility functions (Toga-specific functions removed)
- `src/accessiweather/background_tasks.py` - Background task scheduling
- All other non-UI modules remain unchanged
