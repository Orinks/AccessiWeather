"""Tests for WeatherChat dialog."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

from accessiweather.ui.dialogs.weather_assistant_dialog import (
    MAX_CONTEXT_TURNS,
    SYSTEM_PROMPT,
    _build_weather_context,
    show_weather_assistant_dialog,
)


@dataclass
class MockLocation:
    """Mock Location for testing."""

    name: str = "Test City"
    latitude: float = 40.0
    longitude: float = -74.0
    timezone: str | None = None
    country_code: str | None = None


@dataclass
class MockCurrentConditions:
    """Mock CurrentConditions for testing."""

    temperature_f: float | None = 72.0
    feels_like_f: float | None = 70.0
    condition: str | None = "Partly Cloudy"
    humidity: int | None = 65
    wind_speed_mph: float | None = 8.0
    wind_direction: str | None = "NW"
    pressure_in: float | None = 30.12
    visibility_miles: float | None = 10.0
    uv_index: float | None = 5.0


@dataclass
class MockForecastPeriod:
    """Mock ForecastPeriod for testing."""

    name: str = "Tonight"
    temperature: float = 55.0
    temperature_unit: str = "F"
    short_forecast: str | None = "Clear"


@dataclass
class MockForecast:
    """Mock Forecast for testing."""

    periods: list = field(default_factory=lambda: [MockForecastPeriod()])

    def has_data(self):
        return bool(self.periods)


@dataclass
class MockAlert:
    """Mock alert for testing."""

    event: str = "Wind Advisory"
    severity: str = "Moderate"
    title: str = "Wind Advisory"


@dataclass
class MockAlerts:
    """Mock WeatherAlerts for testing."""

    alerts: list = field(default_factory=lambda: [MockAlert()])

    def has_alerts(self):
        return bool(self.alerts)


@dataclass
class MockTrendInsight:
    """Mock TrendInsight for testing."""

    metric: str = "temperature"
    direction: str = "rising"
    change: float | None = 5.0
    unit: str | None = "°F"
    summary: str | None = "Temperature rising 5°F over the last 3 hours"


@dataclass
class MockWeatherData:
    """Mock WeatherData for testing."""

    location: MockLocation = field(default_factory=MockLocation)
    current: MockCurrentConditions | None = field(default_factory=MockCurrentConditions)
    forecast: MockForecast | None = field(default_factory=MockForecast)
    alerts: MockAlerts | None = None
    trend_insights: list = field(default_factory=list)


class TestBuildWeatherContext:
    """Tests for _build_weather_context."""

    def test_no_weather_data(self):
        """Test with no weather data loaded."""
        app = MagicMock()
        app.current_weather_data = None
        result = _build_weather_context(app)
        assert result == "No weather data currently loaded."

    def test_basic_current_conditions(self):
        """Test with basic current conditions."""
        app = MagicMock()
        app.current_weather_data = MockWeatherData()
        result = _build_weather_context(app)

        assert "Test City" in result
        assert "72°F" in result
        assert "Partly Cloudy" in result
        assert "65%" in result
        assert "8 mph" in result
        assert "NW" in result
        assert "30.12 inHg" in result
        assert "10.0 miles" in result
        assert "UV Index: 5.0" in result

    def test_with_forecast(self):
        """Test with forecast data."""
        app = MagicMock()
        app.current_weather_data = MockWeatherData()
        result = _build_weather_context(app)

        assert "Forecast:" in result
        assert "Tonight" in result
        assert "55°F" in result
        assert "Clear" in result

    def test_with_alerts(self):
        """Test with active alerts."""
        app = MagicMock()
        app.current_weather_data = MockWeatherData(alerts=MockAlerts())
        result = _build_weather_context(app)

        assert "Active Alerts:" in result
        assert "Wind Advisory" in result
        assert "Moderate" in result

    def test_with_trend_insights(self):
        """Test with trend insights."""
        app = MagicMock()
        app.current_weather_data = MockWeatherData(trend_insights=[MockTrendInsight()])
        result = _build_weather_context(app)

        assert "Trend Insights:" in result
        assert "Temperature rising" in result

    def test_no_current_conditions(self):
        """Test with weather data but no current conditions."""
        app = MagicMock()
        app.current_weather_data = MockWeatherData(current=None)
        result = _build_weather_context(app)

        assert "Test City" in result
        # Should not crash with None current
        assert "Temperature:" not in result

    def test_partial_current_conditions(self):
        """Test with some fields None."""
        app = MagicMock()
        conditions = MockCurrentConditions()
        conditions.wind_speed_mph = None
        conditions.wind_direction = None
        conditions.pressure_in = None
        app.current_weather_data = MockWeatherData(current=conditions)
        result = _build_weather_context(app)

        assert "72°F" in result
        assert "Wind:" not in result
        assert "Pressure:" not in result

    def test_wind_without_direction(self):
        """Test wind with speed but no direction."""
        app = MagicMock()
        conditions = MockCurrentConditions()
        conditions.wind_direction = None
        app.current_weather_data = MockWeatherData(current=conditions)
        result = _build_weather_context(app)

        assert "Wind: 8 mph" in result
        assert "from" not in result.split("Wind:")[1].split("\n")[0]


class TestSystemPrompt:
    """Tests for the system prompt."""

    def test_prompt_exists(self):
        """Test system prompt is defined."""
        assert SYSTEM_PROMPT
        assert "WeatherChat" in SYSTEM_PROMPT
        assert "screen reader" in SYSTEM_PROMPT

    def test_prompt_no_markdown_instruction(self):
        """Test prompt instructs no markdown."""
        assert "plain text" in SYSTEM_PROMPT
        assert "No bold" in SYSTEM_PROMPT


class TestMaxContextTurns:
    """Tests for conversation limits."""

    def test_max_turns_defined(self):
        """Test max turns is reasonable."""
        assert MAX_CONTEXT_TURNS > 0
        assert MAX_CONTEXT_TURNS <= 50


class TestShowWeatherChatDialog:
    """Tests for the show function."""

    def test_function_exists(self):
        """Test the show function is importable."""
        assert callable(show_weather_assistant_dialog)
