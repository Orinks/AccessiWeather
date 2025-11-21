"""Essential Toga testing helpers for AccessiWeather."""

import asyncio
import os
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

# Configure Toga backend for testing:
# - Prefer 'toga_dummy' if available
# - Otherwise fall back to platform backend (winforms on Windows CI)
_backend = os.environ.get("TOGA_BACKEND")
if not _backend:
    try:
        __import__("toga_dummy")
        os.environ["TOGA_BACKEND"] = "toga_dummy"
    except ModuleNotFoundError:
        os.environ["TOGA_BACKEND"] = "toga_winforms"

from accessiweather.models import (  # noqa: E402
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)


class WeatherDataFactory:
    """Factory for creating mock weather data."""

    @staticmethod
    def create_location(
        name: str = "Test City, ST", lat: float = 40.0, lon: float = -75.0
    ) -> Location:
        return Location(name, lat, lon)

    @staticmethod
    def create_current_conditions(
        temp_f: float = 75.0, condition: str = "Partly Cloudy"
    ) -> CurrentConditions:
        return CurrentConditions(
            temperature_f=temp_f,
            temperature_c=(temp_f - 32) * 5 / 9,
            condition=condition,
            humidity=65,
            wind_speed_mph=8.5,
            wind_direction="S",
            pressure_in=30.15,
            visibility_miles=10.0,
            uv_index=5,
            last_updated=datetime.now(),
        )

    @staticmethod
    def create_forecast_period(name: str = "Today", temp: int = 78) -> ForecastPeriod:
        return ForecastPeriod(
            name=name,
            temperature=temp,
            temperature_unit="F",
            short_forecast="Sunny",
            detailed_forecast="Sunny skies with light winds.",
            start_time=datetime.now(),
            end_time=datetime.now(),
        )

    @staticmethod
    def create_forecast(num_periods: int = 7) -> Forecast:
        periods = [
            WeatherDataFactory.create_forecast_period(f"Day {i + 1}", 75 + i)
            for i in range(num_periods)
        ]
        return Forecast(periods=periods)

    @staticmethod
    def create_hourly_forecast(num_periods: int = 24) -> HourlyForecast:
        periods = []
        for i in range(num_periods):
            period = HourlyForecastPeriod(
                start_time=datetime.now(),
                temperature=70 + (i % 10),
                temperature_unit="F",
                short_forecast=f"Hour {i + 1}",
                wind_speed=f"{5 + (i % 5)} mph",
                wind_direction=f"{180 + (i * 10) % 360}°",
            )
            periods.append(period)
        return HourlyForecast(periods=periods)

    @staticmethod
    def create_weather_alert(title: str = "Test Alert", severity: str = "Minor") -> WeatherAlert:
        return WeatherAlert(
            title=title,
            description="Test weather alert for testing purposes.",
            severity=severity,
            event=title,
            headline=title,
            instruction="Take appropriate precautions.",
            onset=datetime.now(),
            expires=datetime.now(),
        )

    @staticmethod
    def create_weather_alerts(num_alerts: int = 2) -> WeatherAlerts:
        alerts = [
            WeatherDataFactory.create_weather_alert(
                f"Alert {i + 1}", "Minor" if i % 2 == 0 else "Moderate"
            )
            for i in range(num_alerts)
        ]
        return WeatherAlerts(alerts=alerts)

    @staticmethod
    def create_weather_data(
        include_current: bool = True,
        include_forecast: bool = True,
        include_hourly: bool = True,
        include_alerts: bool = True,
    ) -> WeatherData:
        location = WeatherDataFactory.create_location()
        weather_data = WeatherData(location=location)

        if include_current:
            weather_data.current = WeatherDataFactory.create_current_conditions()
        if include_forecast:
            weather_data.forecast = WeatherDataFactory.create_forecast()
        if include_hourly:
            weather_data.hourly_forecast = WeatherDataFactory.create_hourly_forecast()
        if include_alerts:
            weather_data.alerts = WeatherDataFactory.create_weather_alerts()

        weather_data.discussion = "Mock forecast discussion for testing."
        weather_data.last_updated = datetime.now()

        return weather_data


class AsyncTestHelper:
    """Helper for async testing operations."""

    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run a coroutine with a timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except TimeoutError:
            pytest.fail(f"Async operation timed out after {timeout} seconds")

    @staticmethod
    def create_async_mock(return_value: Any = None, side_effect: Any = None) -> AsyncMock:
        """Create an AsyncMock with optional return value or side effect."""
        mock = AsyncMock()
        if return_value is not None:
            mock.return_value = return_value
        if side_effect is not None:
            mock.side_effect = side_effect
        return mock


class MockTogaWidgets:
    """Mock Toga widgets for testing."""

    @staticmethod
    def create_widget(widget_type: str, **kwargs) -> Mock:
        """Create a mock widget of the specified type."""
        widget = Mock()
        widget.widget_type = widget_type

        # Common properties
        widget.enabled = kwargs.get("enabled", True)
        widget.visible = kwargs.get("visible", True)
        widget.style = kwargs.get("style", Mock())

        # Widget-specific properties
        if widget_type == "Button":
            widget.text = kwargs.get("text", "")
            widget.on_press = kwargs.get("on_press", Mock())
        elif widget_type == "Selection":
            widget.items = kwargs.get("items", [])
            widget.value = kwargs.get("value")
            widget.on_change = kwargs.get("on_change", Mock())
        elif widget_type == "MultilineTextInput":
            widget.value = kwargs.get("value", "")
            widget.readonly = kwargs.get("readonly", False)
        elif widget_type == "Table":
            widget.headings = kwargs.get("headings", [])
            widget.data = kwargs.get("data", [])
            widget.on_select = kwargs.get("on_select", Mock())
        elif widget_type == "Box":
            widget.direction = kwargs.get("direction", "COLUMN")
            widget.children = kwargs.get("children", [])

        return widget


# Pytest fixtures
@pytest.fixture
def weather_factory():
    """Pytest fixture for weather data factory."""
    return WeatherDataFactory()


@pytest.fixture
def async_helper():
    """Pytest fixture for async test helper."""
    return AsyncTestHelper()


@pytest.fixture
def mock_widgets():
    """Pytest fixture for mock Toga widgets."""
    return MockTogaWidgets()


@pytest.fixture
def mock_location():
    """Pytest fixture for mock location."""
    return WeatherDataFactory.create_location()


@pytest.fixture
def mock_weather_data():
    """Pytest fixture for mock weather data."""
    return WeatherDataFactory.create_weather_data()


@pytest.fixture
def mock_weather_client(mock_weather_data):
    """
    Pytest fixture for mock weather client.

    Return the same object as mock_weather_data to avoid timestamp-based flakiness.
    """
    client = Mock()
    client.get_weather_data = AsyncTestHelper.create_async_mock(return_value=mock_weather_data)
    return client


@pytest.fixture
def failing_weather_client():
    """Pytest fixture for failing weather client."""
    client = Mock()
    client.get_weather_data = AsyncTestHelper.create_async_mock(
        side_effect=Exception("Mock weather client failure")
    )
    return client


@pytest.fixture(autouse=True)
def setup_toga_backend():
    """Ensure a Toga backend is configured for tests. Prefer dummy if available."""
    if not os.environ.get("TOGA_BACKEND"):
        try:
            __import__("toga_dummy")
            os.environ["TOGA_BACKEND"] = "toga_dummy"
        except ModuleNotFoundError:
            os.environ["TOGA_BACKEND"] = "toga_winforms"
    yield


@pytest.fixture
def mock_toga_app():
    """Pytest fixture for mock Toga app."""
    app = Mock()
    app.main_loop = Mock()
    app.exit = Mock()
    app.paths = Mock()
    app.formal_name = "AccessiWeather"
    app.app_name = "accessiweather"
    return app


@pytest.fixture
def mock_toga_controls():
    """Pytest fixture for mock Toga controls."""
    return {
        "TextInput": MockTogaWidgets.create_widget("TextInput", value=""),
        "Button": MockTogaWidgets.create_widget("Button", text="Test Button"),
        "Selection": MockTogaWidgets.create_widget("Selection", items=["Option 1", "Option 2"]),
        "MultilineTextInput": MockTogaWidgets.create_widget("MultilineTextInput", value=""),
        "Table": MockTogaWidgets.create_widget("Table", headings=["Name", "Value"]),
    }


@pytest.fixture
def mock_simple_location():
    """Pytest fixture for simple location."""
    return WeatherDataFactory.create_location(name="New York, NY", lat=40.7128, lon=-74.0060)


@pytest.fixture
def sample_config():
    """Pytest fixture for sample config."""
    return {
        "settings": {
            "data_source": "auto",
            "temperature_unit": "both",
            "update_interval": 300,
            "notifications_enabled": True,
            "startup_location": "last_used",
            "minimize_to_tray": True,
            "show_in_taskbar": True,
            "auto_refresh": True,
            "sound_alerts": False,
            "visual_alerts": True,
            "alert_types": ["warning", "watch", "advisory"],
            "debug_mode": False,
            "log_level": "INFO",
            "cache_duration": 600,
            "api_timeout": 30,
            "retry_attempts": 3,
            "retry_delay": 1.0,
        },
        "locations": [
            {
                "name": "New York, NY",
                "latitude": 40.7128,
                "longitude": -74.0060,
            },
            {
                "name": "Philadelphia, PA",
                "latitude": 39.9526,
                "longitude": -75.1652,
            },
        ],
        "current_location": {
            "name": "New York, NY",
            "latitude": 40.7128,
            "longitude": -74.0060,
        },
    }


@pytest.fixture
def toga_test_environment():
    """Pytest fixture for Toga test environment."""
    env = Mock()
    env.is_test_mode = Mock(return_value=True)
    env.backend = "dummy"
    return env
