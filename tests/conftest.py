"""
Test configuration and fixtures for AccessiWeather tests.

This module supports both Toga and wxPython testing environments:
- During wxPython migration: Run backend-only tests with `pytest -m "not toga_ui"`
- For Toga tests: Requires toga_dummy backend
- For wxPython tests: Will be added as migration progresses

Quick Commands:
    pytest -m "not toga_ui"           # Backend-only tests (during migration)
    pytest -m "not toga_ui and not toga"  # Exclude all Toga-related tests
    pytest --ignore=tests/test_toga*  # Ignore Toga test files entirely
    pytest tests/test_cache.py        # Run specific backend test
"""

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

# =============================================================================
# Legacy Toga UI Tests - Excluded During wxPython Migration
# =============================================================================
# These test files import from legacy Toga UI code (handlers/, dialogs/,
# ui_builder.py, event_handlers.py) that has been removed during the wxPython
# migration. They are excluded from collection until migrated to wxPython.
#
# To migrate a test file:
# 1. Update imports to use wxPython UI components from src/accessiweather/ui/
# 2. Update test assertions to work with wxPython widgets
# 3. Remove the file from this list
#
# Run `pytest --collect-only` to see which tests are being collected.
# =============================================================================
collect_ignore = [
    "test_air_quality_dialog.py",
    "test_air_quality_integration.py",
    "test_additional_coverage.py",
    "test_alert_ui_accessibility.py",
    "test_aviation_handlers.py",
    "test_forecast_heading_properties.py",
    "test_hourly_aqi_ui_integration.py",
    "test_keyboard_shortcuts.py",
    "test_location_handlers.py",
    "test_settings_dialog.py",
    "test_settings_visual_crossing_validation.py",
    "test_settings_save_priority.py",
    "test_settings_priority_tab.py",
    "test_settings_openmeteo_model.py",
    "test_sound_pack_system.py",
    "test_system_tray_integration.py",
    "test_system_tray_window_management.py",
    "test_uv_index_integration.py",
    "test_uv_index_dialog.py",
    "test_weather_display_updates.py",
    "test_update_progress_dialog.py",
    "test_toga_ui_components.py",
    "test_app.py",
]

# Ensure pytest-mock plugin loads before tests so the `mocker` fixture is available
pytest_plugins = ("pytest_mock",)

# =============================================================================
# UI Framework Detection
# =============================================================================
# Detect which UI framework is available for testing.
# During wxPython migration, Toga may not be installed.
# =============================================================================

TOGA_AVAILABLE = False
WXPYTHON_AVAILABLE = False

try:
    import toga_dummy  # noqa: F401

    TOGA_AVAILABLE = True
except ImportError:
    pass

try:
    import wx  # noqa: F401

    WXPYTHON_AVAILABLE = True
except ImportError:
    pass

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

# =============================================================================
# Toga Backend Setup (Optional during wxPython migration)
# =============================================================================
# Only set up Toga backend if toga_dummy is available.
# This allows backend-only tests to run without Toga installed.
# =============================================================================

if TOGA_AVAILABLE:
    os.environ["TOGA_BACKEND"] = "toga_dummy"

# Mock desktop-notifier (may not be available in all environments)
sys.modules["desktop-notifier"] = MagicMock()
sys.modules["desktop_notifier"] = MagicMock()

# Import Toga helpers only if Toga is available
# This allows non-UI tests to run without Toga installed
if TOGA_AVAILABLE:
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


# =============================================================================
# Skip Markers for UI Framework Tests
# =============================================================================
# Automatically skip tests based on available UI frameworks.
# =============================================================================


def pytest_configure(config):
    """Register custom markers and configure test collection."""
    # These markers are already defined in pytest.ini, but we document them here
    config.addinivalue_line(
        "markers",
        "toga_ui: marks tests requiring Toga UI (skip during wxPython migration)",
    )
    config.addinivalue_line(
        "markers",
        "wxpython: marks tests requiring wxPython UI",
    )
    config.addinivalue_line(
        "markers",
        "backend: marks backend-only tests (no UI dependencies)",
    )


def pytest_collection_modifyitems(config, items):
    """Automatically skip UI tests when the required framework is unavailable."""
    skip_toga = pytest.mark.skip(reason="Toga not available (toga_dummy not installed)")
    skip_wx = pytest.mark.skip(reason="wxPython not available")

    for item in items:
        # Skip Toga UI tests if Toga is not available
        if "toga_ui" in item.keywords and not TOGA_AVAILABLE:
            item.add_marker(skip_toga)

        # Skip tests in test_toga_*.py files if Toga is not available
        if "test_toga" in str(item.fspath) and not TOGA_AVAILABLE:
            item.add_marker(skip_toga)

        # Skip wxPython tests if wxPython is not available
        if "wxpython" in item.keywords and not WXPYTHON_AVAILABLE:
            item.add_marker(skip_wx)
        if "wx_only" in item.keywords and not WXPYTHON_AVAILABLE:
            item.add_marker(skip_wx)


# =============================================================================
# Fixture Availability Flags
# =============================================================================
# These fixtures can be used to conditionally skip tests at runtime.
# =============================================================================


@pytest.fixture
def requires_toga():
    """Skip test if Toga is not available."""
    if not TOGA_AVAILABLE:
        pytest.skip("Toga not available")


@pytest.fixture
def requires_wxpython():
    """Skip test if wxPython is not available."""
    if not WXPYTHON_AVAILABLE:
        pytest.skip("wxPython not available")
