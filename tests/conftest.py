"""
Pytest configuration and shared fixtures.

This conftest provides minimal, focused fixtures for fast unit testing.
All external API calls should be mocked - no live network requests in unit tests.
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test environment variables before any imports
os.environ["ACCESSIWEATHER_TEST_MODE"] = "1"
os.environ["PYTEST_CURRENT_TEST"] = "true"

# Configure hypothesis for fast CI runs
from hypothesis import settings as hypothesis_settings

hypothesis_settings.register_profile("ci", max_examples=25, deadline=None)
hypothesis_settings.register_profile("dev", max_examples=50, deadline=None)
hypothesis_settings.register_profile("thorough", max_examples=200, deadline=None)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

if TYPE_CHECKING:
    from accessiweather.models import Location


# =============================================================================
# Location Fixtures
# =============================================================================


@pytest.fixture
def sample_location() -> Location:
    """Return a sample US location for testing."""
    from accessiweather.models import Location

    return Location(
        name="Test City, NY",
        latitude=40.7128,
        longitude=-74.0060,
        country_code="US",
    )


@pytest.fixture
def international_location() -> Location:
    """Return a sample international location (outside US)."""
    from accessiweather.models import Location

    return Location(
        name="London, UK",
        latitude=51.5074,
        longitude=-0.1278,
        country_code="GB",
    )


# =============================================================================
# Weather Data Fixtures
# =============================================================================


@pytest.fixture
def sample_current_conditions():
    """Sample current weather conditions."""
    from accessiweather.models import CurrentConditions

    return CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Partly Cloudy",
        humidity=65,
        wind_speed_mph=10.0,
        wind_speed_kph=16.1,
        wind_direction="NW",
        pressure_in=30.05,
        pressure_mb=1017.0,
        feels_like_f=74.0,
        feels_like_c=23.3,
    )


@pytest.fixture
def sample_forecast():
    """Sample weather forecast."""
    from accessiweather.models import Forecast, ForecastPeriod

    periods = [
        ForecastPeriod(
            name="Today",
            temperature=75,
            temperature_unit="F",
            short_forecast="Sunny",
            detailed_forecast="Sunny with highs near 75.",
        ),
        ForecastPeriod(
            name="Tonight",
            temperature=55,
            temperature_unit="F",
            short_forecast="Clear",
            detailed_forecast="Clear skies with lows around 55.",
        ),
    ]
    return Forecast(periods=periods, generated_at=datetime.now(UTC))


@pytest.fixture
def sample_hourly_forecast():
    """Sample hourly forecast."""
    from accessiweather.models import HourlyForecast, HourlyForecastPeriod

    now = datetime.now(UTC)
    periods = [
        HourlyForecastPeriod(
            start_time=now + timedelta(hours=i),
            temperature=70 + i,
            temperature_unit="F",
            short_forecast="Partly Cloudy",
        )
        for i in range(24)
    ]
    return HourlyForecast(periods=periods, generated_at=now)


@pytest.fixture
def sample_weather_alert():
    """Sample weather alert."""
    from accessiweather.models import WeatherAlert

    return WeatherAlert(
        id="test-alert-001",
        title="Heat Advisory",
        description="Heat advisory in effect from noon to 8 PM.",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Heat Advisory",
        headline="Heat Advisory issued",
        onset=datetime.now(UTC),
        expires=datetime.now(UTC) + timedelta(hours=8),
    )


@pytest.fixture
def sample_weather_alerts(sample_weather_alert):
    """Sample weather alerts collection."""
    from accessiweather.models import WeatherAlerts

    return WeatherAlerts(alerts=[sample_weather_alert])


@pytest.fixture
def sample_weather_data(sample_location, sample_current_conditions, sample_forecast):
    """Complete sample weather data."""
    from accessiweather.models import WeatherAlerts, WeatherData

    return WeatherData(
        location=sample_location,
        current=sample_current_conditions,
        forecast=sample_forecast,
        alerts=WeatherAlerts(alerts=[]),
    )


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary directory for configuration files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def mock_app():
    """Mock Toga app for ConfigManager tests."""
    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = Path(tempfile.mkdtemp())
    return app


# =============================================================================
# HTTP Mocking Fixtures
# =============================================================================


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for API tests."""
    with patch("httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = client_instance
        mock.return_value.__aexit__.return_value = None
        yield client_instance


@pytest.fixture
def mock_httpx_response():
    """Create mock HTTP responses for testing."""

    def _create_response(status_code: int = 200, json_data: dict | None = None):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            from httpx import HTTPStatusError

            response.raise_for_status.side_effect = HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=response
            )
        return response

    return _create_response


# =============================================================================
# Async Test Helpers
# =============================================================================


@pytest.fixture
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()
