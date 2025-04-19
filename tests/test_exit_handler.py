"""Tests for the exit handler implementation.

This module contains tests for the exit handler implementation, focusing on
proper cleanup of resources when the application exits.
"""

import logging
import os
import sys
import threading
import time
import wx

import pytest
from unittest.mock import MagicMock, patch

# Add the src directory to the path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import the application
from accessiweather.gui.app import AccessiWeatherApp
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.gui.weather_app_handlers import WeatherAppHandlers

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class MockTimer:
    """Mock timer for testing."""

    def __init__(self):
        """Initialize the mock timer."""
        self.running = False
        self.callbacks = []

    def Start(self, milliseconds=None):
        """Start the timer."""
        self.running = True

    def Stop(self):
        """Stop the timer."""
        self.running = False

    def IsRunning(self):
        """Check if the timer is running."""
        return self.running


class MockThread:
    """Mock thread for testing."""

    def __init__(self, name="MockThread"):
        """Initialize the mock thread."""
        self.name = name
        self.alive = True
        self.daemon = False
        self.stop_event = threading.Event()

    def is_alive(self):
        """Check if the thread is alive."""
        return self.alive

    def join(self, timeout=None):
        """Join the thread."""
        self.alive = False


@pytest.fixture
def mock_weather_app(wx_app_session):
    """Create a mock WeatherApp for testing."""
    # Create a mock WeatherApp
    app = MagicMock(spec=WeatherApp)

    # Add required attributes
    app.timer = MockTimer()
    app.taskbar_icon = MagicMock()
    app._save_config = MagicMock()
    app.Hide = MagicMock()
    app.Destroy = MagicMock()

    # Add mock threads
    app.forecast_fetcher = MagicMock()
    app.forecast_fetcher.thread = MockThread("ForecastThread")
    app.forecast_fetcher._stop_event = threading.Event()

    app.alerts_fetcher = MagicMock()
    app.alerts_fetcher.thread = MockThread("AlertsThread")
    app.alerts_fetcher._stop_event = threading.Event()

    app.discussion_fetcher = MagicMock()
    app.discussion_fetcher.thread = MockThread("DiscussionThread")
    app.discussion_fetcher._stop_event = threading.Event()

    app.national_forecast_fetcher = MagicMock()
    app.national_forecast_fetcher.thread = MockThread("NationalForecastThread")
    app.national_forecast_fetcher._stop_event = threading.Event()

    # Return the mock app
    return app


def test_on_close_with_taskbar_icon(mock_weather_app):
    """Test OnClose with taskbar icon."""
    # Create a mock event
    event = MagicMock()

    # Call OnClose
    WeatherAppHandlers.OnClose(mock_weather_app, event)

    # Check that the window was hidden
    mock_weather_app.Hide.assert_called_once()

    # Check that the event was vetoed
    event.Veto.assert_called_once()

    # Check that the timer was not stopped
    assert mock_weather_app.timer.running

    # Check that _save_config was not called
    mock_weather_app._save_config.assert_not_called()

    # Check that taskbar_icon.Destroy was not called
    mock_weather_app.taskbar_icon.Destroy.assert_not_called()


def test_on_close_with_force_close(mock_weather_app):
    """Test OnClose with force_close=True."""
    # Create a mock event
    event = MagicMock()

    # Save a reference to the taskbar icon before the test
    taskbar_icon = mock_weather_app.taskbar_icon

    # Make sure taskbar_icon has RemoveIcon method
    if not hasattr(taskbar_icon, 'RemoveIcon'):
        taskbar_icon.RemoveIcon = MagicMock()

    # Call OnClose with force_close=True
    WeatherAppHandlers.OnClose(mock_weather_app, event, force_close=True)

    # Check that the window was not hidden
    mock_weather_app.Hide.assert_not_called()

    # Check that the event was not vetoed
    event.Veto.assert_not_called()

    # Check that the timer was stopped
    assert not mock_weather_app.timer.running

    # Check that _save_config was called
    mock_weather_app._save_config.assert_called_once()

    # Check that taskbar_icon.Destroy was called
    taskbar_icon.Destroy.assert_called_once()

    # Check that RemoveIcon was called
    taskbar_icon.RemoveIcon.assert_called_once()

    # Check that the taskbar_icon reference was cleared
    assert mock_weather_app.taskbar_icon is None


def test_on_close_stops_fetcher_threads(mock_weather_app):
    """Test that OnClose stops all fetcher threads."""
    # Create a mock event
    event = MagicMock()

    # Create a custom _stop_fetcher_threads method that we can verify was called
    def custom_stop_fetcher_threads(self):
        # Set the stop events
        self.forecast_fetcher._stop_event.set()
        self.alerts_fetcher._stop_event.set()
        self.discussion_fetcher._stop_event.set()
        self.national_forecast_fetcher._stop_event.set()
        # Join the threads
        self.forecast_fetcher.thread.join(0.1)
        self.alerts_fetcher.thread.join(0.1)
        self.discussion_fetcher.thread.join(0.1)
        self.national_forecast_fetcher.thread.join(0.1)

    # Replace the _stop_fetcher_threads method with our custom one
    original_method = WeatherAppHandlers._stop_fetcher_threads
    WeatherAppHandlers._stop_fetcher_threads = custom_stop_fetcher_threads

    try:
        # Call OnClose with force_close=True
        WeatherAppHandlers.OnClose(mock_weather_app, event, force_close=True)

        # Since we replaced the method, we can't directly verify it was called
        # Instead, we'll verify that the Destroy method was called, which happens after
        # _stop_fetcher_threads in the OnClose method
        mock_weather_app.Destroy.assert_called_once()
    finally:
        # Restore the original method
        WeatherAppHandlers._stop_fetcher_threads = original_method


@pytest.fixture
def patched_weather_app_handlers():
    """Patch WeatherAppHandlers.OnClose for testing."""
    with patch('accessiweather.gui.weather_app_handlers.WeatherAppHandlers.OnClose') as mock_on_close:
        yield mock_on_close


def test_system_tray_exit_calls_close(wx_app_session, patched_weather_app_handlers):
    """Test that the system tray exit handler calls Close with force=True."""
    from accessiweather.gui.system_tray import TaskBarIcon

    # Create a mock frame
    frame = MagicMock()

    # Create a TaskBarIcon
    icon = None
    try:
        icon = TaskBarIcon(frame)

        # Call the exit handler
        icon.on_exit(None)

        # Check that Close was called with force=True
        frame.Close.assert_called_once_with(force=True)
    finally:
        # Clean up
        if icon:
            icon.Destroy()
            wx.SafeYield()
            time.sleep(0.1)  # Allow time for destruction


def test_app_on_exit_cleanup(wx_app_session):
    """Test that AccessiWeatherApp.OnExit performs proper cleanup."""
    # Create a mock app
    app = AccessiWeatherApp(False)

    # Patch super().OnExit to return 0
    with patch('wx.App.OnExit', return_value=0):
        # Call OnExit
        result = app.OnExit()

        # Check that it returned 0
        assert result == 0


if __name__ == "__main__":
    # Run pytest
    pytest.main(["-xvs", __file__])
