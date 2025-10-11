# Integrating Weather History into AccessiWeather App

This guide explains how to integrate the Weather History Tracker feature into the main AccessiWeather application.

## Overview

The Weather History Tracker is a standalone module that can be easily integrated into the existing app workflow. It works alongside the current weather fetching and display functionality.

## Integration Steps

### 1. Initialize History Tracker in App

Add the weather history tracker to the app initialization in `app_initialization.py`:

```python
from .weather_history import WeatherHistoryTracker

def initialize_components(app: AccessiWeatherApp) -> None:
    """Initialize core application components."""
    
    # ... existing initialization code ...
    
    # Initialize weather history tracker
    config = app.config_manager.get_config()
    if config.settings.weather_history_enabled:
        history_file = str(app.paths.data / "weather_history.json")
        app.weather_history_tracker = WeatherHistoryTracker(
            history_file=history_file,
            max_days=config.settings.weather_history_retention_days
        )
        app.weather_history_tracker.load()
        logger.info("Weather history tracker initialized")
    else:
        app.weather_history_tracker = None
```

### 2. Record Weather Data on Update

Add history recording to the weather update function in `background_tasks.py`:

```python
async def update_weather_data(app: AccessiWeatherApp) -> None:
    """Update weather data and record to history."""
    
    # ... existing weather update code ...
    
    # After successfully fetching weather data
    if app.weather_history_tracker and app.current_location and weather_data:
        try:
            # Record current conditions to history
            app.weather_history_tracker.add_entry(
                location=app.current_location,
                conditions=weather_data.current_conditions,
            )
            # Save periodically (e.g., once per update)
            app.weather_history_tracker.save()
            logger.debug("Weather data recorded to history")
        except Exception as e:
            logger.error(f"Failed to record weather history: {e}")
```

### 3. Display Comparison in UI

Add comparison display to the weather presenter in `display/weather_presenter.py`:

```python
def format_current_conditions(self, weather_data: WeatherData, app) -> str:
    """Format current conditions with history comparison."""
    
    parts = []
    
    # ... existing formatting code ...
    
    # Add history comparison if available
    if app.weather_history_tracker:
        try:
            comparison = app.weather_history_tracker.get_comparison_for_yesterday(
                app.current_location.name,
                weather_data.current_conditions
            )
            if comparison:
                parts.append("\nCompared to yesterday:")
                parts.append(comparison.get_accessible_summary())
        except Exception as e:
            logger.debug(f"Could not get weather comparison: {e}")
    
    return "\n".join(parts)
```

### 4. Add Settings UI

Add weather history settings to `dialogs/settings_dialog.py`:

```python
class SettingsDialog:
    """Settings dialog with weather history options."""
    
    def _create_general_tab(self) -> toga.Box:
        """Create general settings tab with history options."""
        
        # ... existing settings ...
        
        # Weather History section
        history_section = toga.Box(style=Pack(direction=COLUMN, padding=5))
        
        history_label = toga.Label(
            "Weather History",
            style=Pack(font_weight="bold", padding_bottom=5)
        )
        history_section.add(history_label)
        
        # Enable history toggle
        self.history_enabled_switch = toga.Switch(
            "Track weather history",
            value=self.config.settings.weather_history_enabled,
            style=Pack(padding_bottom=5),
        )
        history_section.add(self.history_enabled_switch)
        
        # Retention days slider
        retention_box = toga.Box(style=Pack(direction=ROW, padding_bottom=5))
        retention_label = toga.Label(
            "Keep history for (days):",
            style=Pack(padding_right=10, width=150)
        )
        self.retention_slider = toga.Slider(
            min=7,
            max=90,
            value=self.config.settings.weather_history_retention_days,
            style=Pack(flex=1),
        )
        self.retention_value_label = toga.Label(
            str(self.config.settings.weather_history_retention_days),
            style=Pack(padding_left=10, width=30)
        )
        self.retention_slider.on_change = self._on_retention_changed
        
        retention_box.add(retention_label)
        retention_box.add(self.retention_slider)
        retention_box.add(self.retention_value_label)
        history_section.add(retention_box)
        
        return history_section
    
    def _on_retention_changed(self, widget):
        """Update retention value label."""
        self.retention_value_label.text = str(int(widget.value))
    
    def _save_settings(self):
        """Save settings including weather history options."""
        
        # ... existing settings save code ...
        
        # Save weather history settings
        self.config.settings.weather_history_enabled = self.history_enabled_switch.value
        self.config.settings.weather_history_retention_days = int(self.retention_slider.value)
```

### 5. Add Menu Command for Viewing History

Add a menu command to view weather history in `event_handlers.py`:

```python
async def view_weather_history(app, widget=None):
    """Show weather history comparison dialog."""
    
    if not app.weather_history_tracker:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                "Weather history tracking is disabled. Enable it in Settings."
            )
        )
        return
    
    if not app.current_location:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                "Please select a location first."
            )
        )
        return
    
    # Get current weather data
    weather_data = await app.weather_client.fetch_weather(app.current_location)
    if not weather_data or not weather_data.current_conditions:
        await app.main_window.dialog(
            toga.InfoDialog(
                "Weather History",
                "Could not fetch current weather data."
            )
        )
        return
    
    # Get comparisons
    yesterday_comp = app.weather_history_tracker.get_comparison_for_yesterday(
        app.current_location.name,
        weather_data.current_conditions
    )
    week_comp = app.weather_history_tracker.get_comparison_for_last_week(
        app.current_location.name,
        weather_data.current_conditions
    )
    
    # Build message
    parts = [f"Weather History for {app.current_location.name}\n"]
    
    if yesterday_comp:
        parts.append("Compared to Yesterday:")
        parts.append(yesterday_comp.get_accessible_summary())
        parts.append("")
    else:
        parts.append("No data available for yesterday\n")
    
    if week_comp:
        parts.append("Compared to Last Week:")
        parts.append(week_comp.get_accessible_summary())
    else:
        parts.append("No data available for last week")
    
    await app.main_window.dialog(
        toga.InfoDialog(
            "Weather History",
            "\n".join(parts)
        )
    )
```

Then add the menu command in `app.py`:

```python
def startup(self):
    """Create and show the main window."""
    
    # ... existing startup code ...
    
    # Add history command to menu
    if self.weather_history_tracker:
        history_command = toga.Command(
            lambda widget: asyncio.create_task(event_handlers.view_weather_history(self, widget)),
            text="View Weather History",
            tooltip="Compare current weather with past days",
            group=toga.Group.VIEW,
        )
        self.commands.add(history_command)
```

## Configuration Options

The feature uses two settings in `AppSettings`:

- `weather_history_enabled` (bool): Enable/disable history tracking (default: True)
- `weather_history_retention_days` (int): Days to retain history (default: 30)

## Storage Location

History is stored in the app's data directory:
- **Windows**: `%APPDATA%\AccessiWeather\weather_history.json`
- **macOS**: `~/Library/Application Support/AccessiWeather/weather_history.json`
- **Linux**: `~/.local/share/AccessiWeather/weather_history.json`

## Testing Integration

When testing the integration:

1. **Test initialization**: Verify tracker is created on app startup
2. **Test recording**: Check that weather updates are recorded to history
3. **Test saving**: Ensure history file is created and updated
4. **Test comparison**: Verify comparisons work with real weather data
5. **Test settings**: Check that toggling settings works correctly
6. **Test cleanup**: Verify old entries are removed automatically

## Performance Considerations

- History recording adds minimal overhead (< 1ms per update)
- File I/O is asynchronous where possible
- History is loaded once at startup and saved periodically
- Cleanup runs automatically on load to prevent file growth

## Troubleshooting

### History not recording
- Check that `weather_history_enabled` is True
- Verify the data directory is writable
- Check logs for error messages

### File size growing too large
- Reduce `weather_history_retention_days`
- Manually delete the history file to reset

### Comparisons not showing
- Ensure at least one day of history exists
- Check that location names match exactly
- Verify weather data is being fetched successfully

## Future Enhancements

Potential additions for future versions:

1. **Visual graphs**: Chart temperature trends over time
2. **Statistics**: Show averages, highs, lows
3. **Export**: Allow exporting history to CSV
4. **Anomaly alerts**: Notify of unusual weather patterns
5. **Hourly tracking**: More granular history recording

## Example Integration PR

See the pull request that adds this feature for a complete implementation example:
- Feature implementation: `weather_history.py`
- Tests: `test_weather_history.py`, `test_weather_history_integration.py`
- Documentation: `weather_history_feature.md`
- Demo: `examples/weather_history_demo.py`
