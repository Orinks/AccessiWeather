# tests/conftest.py

# Import faulthandler setup first to enable faulthandler

import json
import logging
import os
import requests
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import wx

# Import the thread manager for thread cleanup
from accessiweather.utils.thread_manager import get_thread_manager, stop_all_threads

# Import our service classes plugin
pytest_plugins = ['tests.conftest_service_classes']


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def patch_requests():
    """
    Automatically patch requests.get, post, put, delete for all tests.
    Prevents real network calls during test runs.
    """
    with patch.object(requests, "get") as mock_get, \
         patch.object(requests, "post") as mock_post, \
         patch.object(requests, "put") as mock_put, \
         patch.object(requests, "delete") as mock_delete:
        # Set default return values (can be overridden in individual tests)
        for mock_method in (mock_get, mock_post, mock_put, mock_delete):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            mock_resp.raise_for_status = MagicMock()
            mock_method.return_value = mock_resp
        yield


@pytest.fixture(scope="session")
def stop_all_background_threads():
    """Stop all background threads at the end of the test session.
    
    This fixture ensures that any remaining threads are properly terminated
    at the end of the test session to prevent resource leaks.
    """
    yield  # Run all tests first
    
    # At the end of the session, stop all remaining threads
    logger.info("Stopping all background threads at end of test session")
    try:
        remaining_threads = stop_all_threads(timeout=0.2)
        if remaining_threads:
            logger.warning(f"Some threads could not be stopped: {remaining_threads}")
    except Exception as e:
        logger.error(f"Error stopping threads: {e}")


@pytest.fixture(scope="session", autouse=True)
def wx_app_session(stop_all_background_threads):
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
    # Window cleanup is handled by the function-scoped wx_app fixture
    # Thread cleanup is handled by the stop_all_background_threads fixture


def cancel_all_fetcher_threads(app):
    """Helper function to cancel all fetcher threads in a weather app instance.
    
    This helps prevent threading issues where background threads continue
    after test completion and try to access destroyed UI components.
    """
    logger.debug("Canceling all fetcher threads")
    try:
        # Cancel all known fetcher threads if they exist
        if hasattr(app, 'forecast_fetcher'):
            if hasattr(app.forecast_fetcher, 'cancel'):
                app.forecast_fetcher.cancel()
                logger.debug("Canceled forecast fetcher")
            elif hasattr(app.forecast_fetcher, '_stop_event'):
                app.forecast_fetcher._stop_event.set()
                logger.debug("Set stop event for forecast fetcher")
        
        if hasattr(app, 'alerts_fetcher'):
            if hasattr(app.alerts_fetcher, 'cancel'):
                app.alerts_fetcher.cancel()
                logger.debug("Canceled alerts fetcher")
            elif hasattr(app.alerts_fetcher, '_stop_event'):
                app.alerts_fetcher._stop_event.set()
                logger.debug("Set stop event for alerts fetcher")
            
        if hasattr(app, 'discussion_fetcher'):
            if hasattr(app.discussion_fetcher, 'cancel'):
                app.discussion_fetcher.cancel()
                logger.debug("Canceled discussion fetcher")
            elif hasattr(app.discussion_fetcher, '_stop_event'):
                app.discussion_fetcher._stop_event.set()
                logger.debug("Set stop event for discussion fetcher")
            
        if hasattr(app, 'national_forecast_fetcher'):
            if hasattr(app.national_forecast_fetcher, 'cancel'):
                app.national_forecast_fetcher.cancel()
                logger.debug("Canceled national forecast fetcher")
            elif hasattr(app.national_forecast_fetcher, '_stop_event'):
                app.national_forecast_fetcher._stop_event.set()
                logger.debug("Set stop event for national forecast fetcher")
        
        # Also ensure any threads registered with the thread manager are stopped
        try:
            thread_mgr = get_thread_manager()
            if thread_mgr:
                logger.debug("Stopping threads via thread manager")
                remaining = thread_mgr.stop_all_threads(timeout=0.1)
                if remaining:
                    logger.warning(f"Some threads remained after test: {remaining}")
        except Exception as tm_err:
            logger.warning(f"Error using thread manager: {tm_err}")
        
        # Process events to allow callbacks to execute
        wx.SafeYield()
        time.sleep(0.05)  # Small delay to let threads terminate
    except Exception as e:
        logger.warning(f"Exception canceling fetcher threads: {e}")


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
        # Clean up all top-level windows and get all app instances
        windows = list(wx.GetTopLevelWindows())
        
        # Cancel threads in all windows that might be WeatherApp instances
        for win in windows:
            # Try to cancel threads in potential WeatherApp instances
            try:
                if hasattr(win, 'forecast_fetcher') or hasattr(win, 'alerts_fetcher') or \
                   hasattr(win, 'discussion_fetcher') or hasattr(win, 'national_forecast_fetcher'):
                    cancel_all_fetcher_threads(win)
            except Exception as thread_e:
                logger.warning(f"Exception canceling threads in window: {thread_e}")
                
            # Now hide and destroy the window
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
def wx_app_isolated():
    """Create an isolated wx App for testing.

    This fixture creates a new wx.App for each test, rather than reusing
    the session-scoped app. This can help prevent issues with state leakage
    between tests, but is less efficient.
    """
    try:
        # Create a new isolated app
        app = wx.App(False)  # False means don't redirect stdout/stderr

        # Allow the app to initialize
        wx.SafeYield()
        time.sleep(0.1)  # Give the app a moment to fully initialize

        yield app

    finally:
        # Make sure any fetcher threads are cancelled first to avoid accessing
        # destroyed windows
        try:
            logger.debug("Stopping threads in isolated wx app")
            cancel_all_fetcher_threads(app)
        except Exception as thread_err:
            logger.warning(f"Error stopping threads in isolated app: {thread_err}")

        # Clean up after the test
        logger.debug("Cleaning up isolated wx app")
        try:
            # Find all top-level windows created during the test
            for win in list(wx.GetTopLevelWindows()):
                logger.debug(f"Cleaning up window: {win}")
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

            # Destroy the app
            app.Destroy()
            
            # One final check for any remaining threads
            try:
                thread_mgr = get_thread_manager()
                active_threads = thread_mgr.get_active_threads()
                if active_threads:
                    logger.warning(f"Found {len(active_threads)} active threads after isolated app cleanup")
                    thread_mgr.stop_all_threads(timeout=0.1)
            except Exception as tm_err:
                logger.warning(f"Error checking thread manager: {tm_err}")
                
        except Exception as e:
            logger.warning(f"Exception during isolated app cleanup: {e}")


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
    """Create a mock NoaaApiClient using patch.object."""
    from accessiweather.api_client import NoaaApiClient

    # Create a patcher for NoaaApiClient
    with patch.object(
        NoaaApiClient, '__new__', return_value=MagicMock(spec=NoaaApiClient)
    ) as mock_client:
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

        yield mock_client


@pytest.fixture
def mock_notifier():
    """Create a mock WeatherNotifier using patch.object."""
    from accessiweather.notifications import WeatherNotifier

    # Create a patcher for WeatherNotifier
    with patch.object(
        WeatherNotifier, '__new__', return_value=MagicMock(spec=WeatherNotifier)
    ) as mock_notifier:
        yield mock_notifier


@pytest.fixture
def mock_location_service():
    """Create a mock LocationService with test data using patch.object."""
    from accessiweather.services.location_service import LocationService

    # Create a patcher for LocationService
    with patch.object(
        LocationService, '__new__', return_value=MagicMock(spec=LocationService)
    ) as mock_location_service:
        # Configure the mock
        mock_location_service.get_current_location.return_value = ("Test City", 35.0, -80.0)
        mock_location_service.get_current_location_name.return_value = "Test City"
        mock_location_service.get_all_locations.return_value = ["Test City"]
        mock_location_service.get_location_coordinates.return_value = (35.0, -80.0)

        yield mock_location_service
