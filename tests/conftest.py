"""Test configuration and fixtures for AccessiWeather Toga app tests."""

# Configure toga-dummy backend for testing
import os
import sys
from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import (
    HealthCheck,
    Verbosity,
    settings as hypothesis_settings,
)

# Ensure pytest-mock plugin loads before tests so the `mocker` fixture is available
pytest_plugins = ("pytest_mock",)

# =============================================================================
# Hypothesis Performance Profiles
# =============================================================================
# Register profiles for different test scenarios:
# - "fast": Minimal examples for quick iteration during development (10 examples)
# - "ci": Fast profile for CI pipelines (fewer examples, shorter deadlines)
# - "dev": Development profile (moderate examples for quick feedback)
# - "thorough": Full testing profile (many examples for release validation)
#
# Usage:
#   pytest --hypothesis-profile=fast  # Quick iteration
#   pytest --hypothesis-profile=ci    # Fast CI runs
#   pytest --hypothesis-profile=dev   # Development
#   pytest                            # Uses default (dev)
# =============================================================================

hypothesis_settings.register_profile(
    "ci",
    max_examples=25,
    deadline=None,  # Disable deadline to avoid flaky failures in CI
    suppress_health_check=[],
    verbosity=Verbosity.quiet,
)

hypothesis_settings.register_profile(
    "dev",
    max_examples=50,
    deadline=None,
    verbosity=Verbosity.normal,
)

hypothesis_settings.register_profile(
    "thorough",
    max_examples=200,
    deadline=None,
    verbosity=Verbosity.verbose,
)

hypothesis_settings.register_profile(
    "fast",
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    deadline=None,
)

# Load profile from environment or default to "dev"
_profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
hypothesis_settings.load_profile(_profile)

# Set toga to use the dummy backend for headless testing
os.environ["TOGA_BACKEND"] = "toga_dummy"

# Mock desktop-notifier (not provided by toga-dummy)
sys.modules["desktop-notifier"] = MagicMock()
sys.modules["desktop_notifier"] = MagicMock()

# Import only Toga helpers (guarded to avoid heavy imports when unavailable)
# If optional UI deps (e.g., toga) are not installed, allow non-UI tests to run
with suppress(Exception):
    from tests.toga_test_helpers import *  # noqa: F401, F403

# Explicitly load pytest-asyncio plugin even when autoload is disabled in CI

# Skip removed fixtures directories (basic_fixtures, sample_responses, gui_fixtures, mock_clients)


@pytest.fixture
def mock_simple_weather_apis():
    """Mock weather APIs for simple Toga app testing."""
    with (
        patch("httpx.AsyncClient") as mock_httpx_client,
    ):
        # Set up httpx client mock for simple weather client
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance

        # Mock Open-Meteo API responses
        mock_openmeteo_current = {
            "current": {
                "temperature_2m": 75.0,
                "weather_code": 1,
                "relative_humidity_2m": 65,
                "wind_speed_10m": 8.5,
                "wind_direction_10m": 180,
                "pressure_msl": 1013.2,
                "apparent_temperature": 78.0,
            }
        }

        mock_openmeteo_forecast = {
            "daily": {
                "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "weather_code": [1, 2, 3],
                "temperature_2m_max": [75.0, 78.0, 72.0],
                "temperature_2m_min": [55.0, 58.0, 52.0],
            }
        }

        # Configure mock responses
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = [mock_openmeteo_current, mock_openmeteo_forecast]
        mock_client_instance.get.return_value = mock_response

        yield {
            "httpx_client": mock_client_instance,
            "openmeteo_current": mock_openmeteo_current,
            "openmeteo_forecast": mock_openmeteo_forecast,
        }


@pytest.fixture
def mock_web_scraping():
    """Mock web scraping for national discussion data."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Mock weather discussion</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_simple_weather_apis_error():
    """Mock weather APIs to simulate error conditions for simple app."""
    with patch("httpx.AsyncClient") as mock_httpx_client:
        # Configure httpx client mock to raise errors
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.side_effect = Exception("API Error")

        yield {"httpx_client": mock_client_instance}


@pytest.fixture
def mock_simple_weather_apis_timeout():
    """Mock weather APIs to simulate timeout conditions for simple app."""
    with patch("httpx.AsyncClient") as mock_httpx_client:
        import httpx

        # Configure httpx client mock to raise timeout
        mock_client_instance = MagicMock()
        mock_httpx_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.get.side_effect = httpx.TimeoutException("Request timed out")

        yield {"httpx_client": mock_client_instance}


@pytest.fixture
def verify_no_real_api_calls():
    """Verify that no real API calls are made during tests."""
    with (
        patch("requests.get") as mock_requests_get,
        patch("httpx.get") as mock_httpx_get,
        patch("httpx.Client.get") as mock_httpx_client_get,
    ):
        # Configure mocks to raise if called
        mock_requests_get.side_effect = AssertionError("Real requests.get call detected!")
        mock_httpx_get.side_effect = AssertionError("Real httpx.get call detected!")
        mock_httpx_client_get.side_effect = AssertionError("Real httpx.Client.get call detected!")

        yield {
            "requests_get": mock_requests_get,
            "httpx_get": mock_httpx_get,
            "httpx_client_get": mock_httpx_client_get,
        }
