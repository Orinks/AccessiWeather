---
description: AccessiWeather project-specific patterns, conventions, and architectural guidelines for Toga/BeeWare development
globs: src/accessiweather/**/*.py, tests/**/*.py, *.py
alwaysApply: true
---

# AccessiWeather Project Guidelines (BeeWare/Toga)

AccessiWeather is a desktop weather application built with BeeWare/Toga, focused on accessibility and screen reader compatibility. This guide covers project-specific patterns and conventions for the Toga-based architecture.

## **Project Architecture**

- **Technology Stack**: Python 3.7+ with Toga/BeeWare for cross-platform GUI, httpx for async API calls
- **Build System**: Briefcase for packaging and distribution across platforms
- **Main Structure**:
  ```
  src/accessiweather/
  ├── app.py               # Main Toga application class
  ├── __init__.py          # Package exports and main() entry
  ├── cli.py               # Command-line interface
  ├── config.py            # Configuration management using Toga paths
  ├── models.py            # Simple dataclasses for weather data
  ├── weather_client.py    # Unified weather API client
  ├── location_manager.py  # Location management
  ├── dialogs/             # Dialog windows (Toga-based)
  ├── resources/           # Static resources
  └── utils/               # Common utilities
  ```

## **Naming Conventions**

- **Files**: Use snake_case for all Python files (e.g., `weather_service.py`, `settings_dialog.py`)
- **Classes**: Use PascalCase (e.g., `WeatherService`, `LocationManager`)
- **Methods/Functions**: Use snake_case (e.g., `get_current_weather`, `update_forecast`)
- **Constants**: Use SCREAMING_SNAKE_CASE (e.g., `UPDATE_INTERVAL`, `CONFIG_DIR`)

## **Code Style & Formatting**

- **Line Length**: 100 characters maximum (configured in Black and flake8)
- **Formatter**: Black with `--line-length=100`
- **Import Order**: isort with Black profile compatibility
- **Type Hints**: Required for all public methods and functions
- **String Quotes**: Black's preference (generally double quotes)

```python
# ✅ DO: Proper formatting with type hints
def get_weather_data(latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
    """Get weather data for coordinates.

    Args:
        latitude: Location latitude
        longitude: Location longitude

    Returns:
        Weather data dict or None if failed
    """
    pass

# ❌ DON'T: Missing type hints, poor formatting
def get_weather_data(lat,lng):
    pass
```

## **Logging Standards**

- **Logger Creation**: Use `logging.getLogger(__name__)` in every module
- **Log Levels**: DEBUG for development, INFO for normal operation
- **Formatting**: Structured logging with module names
- **Configuration**: Centralized in `logging_config.py`

```python
# ✅ DO: Standard logging pattern
import logging

logger = logging.getLogger(__name__)

class WeatherService:
    def fetch_data(self):
        logger.info("Fetching weather data")
        try:
            # API call
            logger.debug("API response received")
        except Exception as e:
            logger.error("Failed to fetch data: %s", e)

# ❌ DON'T: Direct print statements or root logger
print("Debug info")  # Use logger.debug() instead
```

## **Exception Handling**

- **Custom Exceptions**: Inherit from base exception classes
- **API Errors**: Use specific exception types (`NoaaApiError`, `OpenMeteoError`)
- **Error Classification**: Include error types and context

```python
# ✅ DO: Structured exception handling
class WeatherServiceError(Exception):
    """Base exception for weather service operations."""
    pass

class ApiClientError(WeatherServiceError):
    """Exception for API client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

# ✅ DO: Proper exception handling with context
try:
    data = api_client.fetch_weather()
except ApiClientError as e:
    logger.error("API error (status: %s): %s", e.status_code, e)
    return None
```

## **Configuration Management (Toga)**

- **Config Location**: Uses Toga's `app.paths.config` for OS-appropriate paths
- **Settings Storage**: JSON files with dataclass models for validation
- **Cross-Platform**: Toga handles platform-specific config directories automatically
- **User Agent**: Required for NOAA API compliance

```python
# ✅ DO: Toga configuration management
import toga
from .models import AppConfig, AppSettings

class ConfigManager:
    def __init__(self, app: toga.App):
        self.app = app
        self.config_file = self.app.paths.config / "accessiweather.json"
        # Toga automatically handles platform-specific paths:
        # Windows: %APPDATA%/AccessiWeather/
        # macOS: ~/Library/Application Support/AccessiWeather/
        # Linux: ~/.config/AccessiWeather/

    def load_config(self) -> AppConfig:
        """Load configuration using dataclass models."""
        if self.config_file.exists():
            with open(self.config_file, encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        return AppConfig.default()
```

## **Toga/BeeWare UI Patterns**

- **Framework**: Toga 0.5.1+ for cross-platform native UI
- **Async-First**: All operations use async/await patterns
- **Screen Reader Support**: Native accessibility through platform APIs
- **Layout System**: Uses Travertino CSS-like styling with Pack layout

```python
# ✅ DO: Toga application structure
import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

class AccessiWeatherApp(toga.App):
    def startup(self):
        """Initialize the application."""
        # Create main UI container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Add widgets with proper styling
        title = toga.Label(
            "AccessiWeather",
            style=Pack(text_align="center", font_size=18, font_weight="bold")
        )
        main_box.add(title)

        # Set main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

# ✅ DO: Async event handlers
async def _on_refresh_pressed(self, widget):
    """Handle refresh button press."""
    await self._refresh_weather_data()
```

## **API Integration (Async)**

- **Multiple Providers**: NOAA (US), Open-Meteo (International), Visual Crossing (alerts)
- **Async-First**: All API calls use httpx with async/await
- **Unified Client**: Single `WeatherClient` class handles provider selection
- **Error Handling**: Provider-specific error types with async exception handling

```python
# ✅ DO: Async weather client pattern
import httpx
from .models import WeatherData, Location

class WeatherClient:
    def __init__(self, user_agent: str, data_source: str = "auto"):
        self.user_agent = user_agent
        self.data_source = data_source
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def get_weather_data(self, location: Location) -> WeatherData:
        """Get weather data with automatic provider selection."""
        try:
            if self._is_us_location(location):
                return await self._get_nws_weather(location)
            else:
                return await self._get_openmeteo_weather(location)
        except httpx.TimeoutException:
            raise WeatherApiError("Request timed out", error_type="timeout")
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            raise WeatherApiError(str(e))

    async def _get_nws_weather(self, location: Location) -> WeatherData:
        """Fetch weather from NOAA."""
        async with self.http_client as client:
            response = await client.get(f"https://api.weather.gov/points/{location.latitude},{location.longitude}")
            # Process response...
```

## **Testing Patterns (Async)**

- **Test Framework**: pytest with pytest-asyncio for async testing
- **Mock Strategy**: httpx-mock for API calls, pytest fixtures for components
- **Async Tests**: All tests involving API calls use async/await
- **Toga Testing**: Minimal UI testing, focus on logic and data flow

```python
# ✅ DO: Async test structure
import pytest
import httpx
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_weather_client_success():
    """Test successful weather retrieval."""
    client = WeatherClient(user_agent="Test/1.0")
    location = Location("Test City", 40.7128, -74.0060)

    with httpx_mock.HTTPXMock() as mock:
        mock.add_response(
            url="https://api.weather.gov/points/40.7128,-74.0060",
            json={"properties": {"forecast": "test_url"}}
        )

        weather_data = await client.get_weather_data(location)
        assert weather_data is not None

@pytest.fixture
async def weather_client():
    """Provide a weather client for testing."""
    return WeatherClient(user_agent="Test/1.0")

# ✅ DO: Test async event handlers
@pytest.mark.asyncio
async def test_refresh_weather_data(app_instance):
    """Test weather data refresh."""
    await app_instance._refresh_weather_data()
    assert app_instance.current_weather_data is not None
```

## **Build & Distribution (Briefcase)**

- **Build Tool**: Briefcase for cross-platform native packaging
- **Supported Platforms**: Windows, macOS, Linux, iOS, Android, Web
- **Configuration**: All build settings in `pyproject.toml` `[tool.briefcase]` section
- **Development**: `briefcase dev` for running during development
- **Distribution**: `briefcase package` for creating platform installers

```python
# ✅ DO: Briefcase project configuration (pyproject.toml)
[tool.briefcase]
project_name = "Accessiweather"
bundle = "net.orinks.accessiweather"
version = "0.0.1"
url = "http://accessiweather.orinks.net"
license.file = "LICENSE"
author = "Orinks"
author_email = "orin8722@gmail.com"

[tool.briefcase.app.accessiweather]
formal_name = "AccessiWeather"
description = "Accessible weather application"
sources = ["src/accessiweather"]
entry_point = "accessiweather:main"
requires = [
    "toga>=0.5.1",
    "httpx>=0.20.0",
    "desktop-notifier",
    # Other dependencies...
]

# ✅ DO: Entry point definition
def main():
    """Main entry point for BeeWare app."""
    return AccessiWeatherApp(
        "AccessiWeather",
        "net.orinks.accessiweather",
        description="Simple, accessible weather application"
    )
```

## **Error Handling & Logging**

- **Structured Logging**: Use rotating file handlers with size limits
- **Log Locations**: User-specific log directories (`~/AccessiWeather_logs/`)
- **Debug Mode**: Enhanced logging and additional features for development

## **Simplified Architecture Pattern**

- **Direct Integration**: Business logic integrated directly into app class
- **Dataclass Models**: Simple dataclasses for data structures
- **Component Composition**: Components initialized in app startup
- **Async State Management**: State managed through async methods

```python
# ✅ DO: Simplified Toga app structure
class AccessiWeatherApp(toga.App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Core components initialized directly
        self.config_manager: ConfigManager | None = None
        self.weather_client: WeatherClient | None = None
        self.location_manager: LocationManager | None = None
        self.current_weather_data: WeatherData | None = None

    def startup(self):
        """Initialize components and UI."""
        self._initialize_components()
        self._create_main_ui()
        self._load_initial_data()

    def _initialize_components(self):
        """Initialize core components."""
        self.config_manager = ConfigManager(self)
        self.weather_client = WeatherClient(user_agent="AccessiWeather/2.0")
        self.location_manager = LocationManager()
```

## **Async Operations (Toga)**

- **Native Async**: Toga runs on asyncio event loop natively
- **Background Tasks**: Use `asyncio.create_task()` for concurrent operations
- **UI Updates**: Direct async method calls, no threading concerns
- **Async Context**: All I/O operations should be async

```python
# ✅ DO: Native async operations in Toga
import asyncio

class AccessiWeatherApp(toga.App):
    async def on_running(self):
        """Start background tasks when app starts running."""
        # Start periodic updates as background task
        asyncio.create_task(self._start_background_updates())

    async def _refresh_weather_data(self):
        """Refresh weather data asynchronously."""
        if self.is_updating:
            return

        self.is_updating = True
        try:
            # Direct async call - no threading needed
            weather_data = await self.weather_client.get_weather_data(location)
            # Direct UI update - no CallAfter needed
            await self._update_weather_displays(weather_data)
        finally:
            self.is_updating = False

    async def _start_background_updates(self):
        """Background update loop."""
        while True:
            await asyncio.sleep(update_interval)
            if not self.is_updating:
                await self._refresh_weather_data()
```

## **Data Models & Validation**

- **Dataclass Models**: Use Python dataclasses for data structures
- **Type Hints**: All models use full type annotations with union syntax
- **Validation**: Built-in validation through dataclass field defaults
- **Serialization**: JSON serialization through custom `from_dict`/`to_dict` methods

```python
# ✅ DO: Dataclass models with type hints
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Location:
    """Simple location data."""
    name: str
    latitude: float
    longitude: float

    def __str__(self) -> str:
        return self.name

@dataclass
class WeatherData:
    """Complete weather data structure."""
    location: Location
    current: CurrentConditions | None = None
    forecast: Forecast | None = None
    alerts: WeatherAlerts | None = None
    last_updated: datetime = field(default_factory=datetime.now)

    def has_data(self) -> bool:
        """Check if we have meaningful weather data."""
        return any([
            self.current and self.current.has_data(),
            self.forecast and self.forecast.has_data(),
        ])
```

## **Dialog & Window Management**

- **Modal Dialogs**: Use async dialog patterns with `await`
- **Window Lifecycle**: Properly handle window creation/destruction
- **Focus Management**: Set initial focus for accessibility
- **Dialog Results**: Return meaningful values from dialog operations

```python
# ✅ DO: Async dialog pattern
class SettingsDialog:
    def __init__(self, parent_app, config_manager):
        self.parent_app = parent_app
        self.config_manager = config_manager
        self.dialog_window = None

    async def show_and_wait(self) -> bool:
        """Show dialog and wait for result."""
        self.dialog_window = toga.Window(title="Settings")
        # ... configure dialog content ...
        self.dialog_window.show()

        # Dialog handles its own event loop
        return await self._wait_for_result()

    async def _on_save_pressed(self, widget):
        """Handle save button press."""
        try:
            self.config_manager.save_config()
            self.dialog_window.close()
            self._result = True
        except Exception as e:
            await self.dialog_window.error_dialog("Save Error", str(e))

# ✅ DO: Focus management for accessibility
def _create_main_ui(self):
    """Create main UI with proper focus order."""
    # ... create widgets ...

async def on_running(self):
    """Set initial focus when app is ready."""
    await asyncio.sleep(0.1)  # Let UI render
    if self.location_selection:
        self.location_selection.focus()
```

## **System Integration**

- **System Tray**: Use `toga.MenuStatusIcon` for system tray integration
- **Desktop Notifications**: Use `desktop-notifier` library for cross-platform notifications
- **Platform Paths**: Always use `app.paths.*` for file system access
- **Single Instance**: Custom single-instance management for desktop apps

```python
# ✅ DO: System tray integration
def _initialize_system_tray(self):
    """Initialize system tray functionality."""
    self.status_icon = toga.MenuStatusIcon(
        id="accessiweather_main",
        icon=self.icon,
        text="AccessiWeather",
    )

    # Create tray commands
    self.show_hide_command = toga.Command(
        self._on_show_hide_window,
        text="Show AccessiWeather",
        group=self.status_icon,
    )

    self.status_icons.add(self.status_icon)
    self.status_icons.commands.add(self.show_hide_command)

# ✅ DO: Platform-appropriate file paths
def __init__(self, app: toga.App):
    """Use Toga paths for cross-platform compatibility."""
    self.config_file = self.app.paths.config / "accessiweather.json"
    self.cache_dir = self.app.paths.cache
    self.data_dir = self.app.paths.data
    # Automatically handles:
    # Windows: %APPDATA%, %LOCALAPPDATA%
    # macOS: ~/Library/Application Support, ~/Library/Caches
    # Linux: ~/.config, ~/.cache
```
