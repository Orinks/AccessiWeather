# tests/conftest.py

# Import faulthandler setup first to enable faulthandler
import json
import logging
import os
import tempfile
import time
from unittest.mock import MagicMock

import pytest
import wx

# Import faulthandler_setup for side effects (enables faulthandler)
import tests.faulthandler_setup  # noqa: F401
from tests.wx_cleanup_utils import safe_cleanup


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Faulthandler is already enabled by the faulthandler_setup module

# No need to import test utilities here


@pytest.fixture(scope="session")
def wx_app_session():
    """Create a wx App for testing (session-scoped).

    This fixture creates a wx.App that can be used for the entire test session.
    It ensures proper cleanup after all tests are complete.
    """
    # Create a new app for the session
    # This is more reliable than checking for an existing app
    app = wx.App(False)  # False means don't redirect stdout/stderr

    # Allow the app to initialize
    wx.SafeYield()
    time.sleep(0.1)  # Give the app a moment to fully initialize

    yield app

    # Clean up after all tests using the safe cleanup utility
    logger.info("Performing session cleanup")
    try:
        # Use the safe cleanup utility
        safe_cleanup()
    except Exception as e:
        logger.warning(f"Exception during wx cleanup: {e}")
        # Continue with test completion even if cleanup fails


@pytest.fixture
def wx_app(wx_app_session):
    """Create a wx App for testing (function-scoped).

    This fixture uses the session-scoped app but provides function-level
    cleanup.
    """
    # The app is already created by the session fixture
    app = wx_app_session

    # Process any pending events before the test
    wx.SafeYield()
    time.sleep(0.05)  # Give a moment for events to process

    yield app

    # Clean up after the test for any top-level windows
    logger.debug("Performing function-level cleanup")
    try:
        # Clean up all top-level windows
        windows = list(wx.GetTopLevelWindows())
        for win in windows:
            if win and win.IsShown():
                try:
                    # Hide the window first
                    win.Hide()
                    wx.SafeYield()
                    # Then destroy it
                    wx.CallAfter(win.Destroy)
                    wx.SafeYield()
                except Exception as win_e:
                    logger.warning(f"Exception cleaning up window: {win_e}")

        # Process pending events
        for _ in range(5):
            wx.SafeYield()
            time.sleep(0.02)
    except Exception as e:
        logger.warning(f"Exception during function-level wx cleanup: {e}")


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for configuration files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the directory structure
        os.makedirs(temp_dir, exist_ok=True)
        yield temp_dir


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Create a temporary config file for testing."""
    # Create a temporary config file
    config_path = os.path.join(temp_config_dir, "config.json")
    config_data = {
        "locations": {"Test City": {"lat": 35.0, "lon": -80.0}},
        "current": "Test City",
        "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
        "api_settings": {"contact_info": "test@example.com"},
        "testing": {"use_mocks": True, "skip_api_calls": True},
    }

    with open(config_path, "w") as f:
        json.dump(config_data, f)

    yield config_path


@pytest.fixture
def mock_api_client():
    """Create a mock NoaaApiClient."""
    from accessiweather.api_client import NoaaApiClient

    # Create a mock API client
    mock_client = MagicMock(spec=NoaaApiClient)

    # Configure common mock responses
    mock_client.get_point_data.return_value = {
        "properties": {
            "forecast": ("https://api.weather.gov/gridpoints/RAH/53,88/forecast"),
            "forecastHourly": ("https://api.weather.gov/gridpoints/RAH/53,88/forecast/hourly"),
            "relativeLocation": {"properties": {"city": "Test City", "state": "NC"}},
        }
    }

    mock_client.get_forecast.return_value = {
        "properties": {
            "periods": [
                {
                    "name": "Today",
                    "temperature": 75,
                    "temperatureUnit": "F",
                    "shortForecast": "Sunny",
                    "detailedForecast": "Sunny with a high near 75.",
                }
            ]
        }
    }

    mock_client.get_alerts.return_value = {"features": []}

    return mock_client


@pytest.fixture
def mock_notifier():
    """Create a mock WeatherNotifier."""
    from accessiweather.notifications import WeatherNotifier

    # Create a mock notifier
    mock_notifier = MagicMock(spec=WeatherNotifier)
    return mock_notifier


@pytest.fixture
def mock_location_manager(temp_config_dir):
    """Create a mock LocationManager with test data."""
    from accessiweather.location import LocationManager

    # Create a real location manager with the temp directory
    location_manager = LocationManager(config_dir=temp_config_dir)

    # Add test locations
    location_manager.add_location("Test City", 35.0, -80.0)
    location_manager.set_current_location("Test City")

    return location_manager
