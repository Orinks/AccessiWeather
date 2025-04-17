"""GUI test fixtures for AccessiWeather.

This module provides fixtures for testing GUI components in AccessiWeather.
These fixtures are designed to be reusable across different test modules.
"""

import time
import types
import threading
import pytest
import wx
from unittest.mock import MagicMock, patch

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.services.location_service import LocationService
from accessiweather.services.weather_service import WeatherService
# Import UI components for creating test UI elements
from accessiweather.gui.ui_components import AccessibleTextCtrl, AccessibleListCtrl


def wait_for(condition_func, timeout=5.0, poll_interval=0.05):
    """Utility: Wait for a condition to be True or timeout.

    Args:
        condition_func: Function that returns True when condition is met
        timeout: Maximum time to wait in seconds
        poll_interval: Time between checks in seconds

    Returns:
        True if condition was met, False if timeout occurred
    """
    start = time.time()
    while time.time() - start < timeout:
        if condition_func():
            return True
        wx.Yield()
        time.sleep(poll_interval)
    return False


def process_ui_events(iterations=5, sleep_time=0.02):
    """Process pending UI events.

    This function processes pending UI events to ensure UI updates are applied.
    It's useful for tests that need to wait for UI updates to be processed.

    Args:
        iterations: Number of times to process events
        sleep_time: Time to sleep between iterations in seconds
    """
    for _ in range(iterations):
        wx.Yield()
        time.sleep(sleep_time)


def simulate_ui_action(action_func, process_events=True):
    """Simulate a UI action and process events.

    This function simulates a UI action and processes events to ensure
    the action is fully processed by the UI.

    Args:
        action_func: Function that performs the UI action
        process_events: Whether to process events after the action
    """
    action_func()
    if process_events:
        process_ui_events()


class AsyncEventWaiter:
    """Helper class for waiting for asynchronous events.

    This class provides a way to wait for asynchronous events to complete
    in GUI tests, such as when a background thread updates the UI.
    """
    def __init__(self):
        self.event = threading.Event()
        self.result = None

    def callback(self, result=None):
        """Callback to be called when the event completes.

        Args:
            result: Optional result to store
        """
        self.result = result
        self.event.set()

    def wait(self, timeout=5.0):
        """Wait for the event to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            The result passed to the callback, or None if timeout
        """
        start_time = time.time()
        while not self.event.is_set() and time.time() - start_time < timeout:
            wx.Yield()
            time.sleep(0.05)
        return self.result


@pytest.fixture
def mock_weather_app(wx_app_session):
    """Create a WeatherApp instance with mocked services.

    This fixture creates a WeatherApp with properly mocked services and UI components
    for testing GUI functionality.

    Args:
        wx_app_session: The wx.App fixture from conftest.py

    Returns:
        A configured WeatherApp instance with mocks and its parent frame
    """
    # Create mocks for the services
    location_service = MagicMock(spec=LocationService)
    weather_service = MagicMock(spec=WeatherService)
    notification_service = MagicMock()
    api_client = MagicMock()

    # Configure the location service mock
    location_service.get_current_location.return_value = ('Test City', 35.0, -80.0)
    location_service.get_all_locations.return_value = ['Test City', 'Nationwide']

    # Configure the weather service mock with realistic test data
    weather_service.get_forecast.return_value = {
        'properties': {
            'periods': [
                {
                    'name': 'Today',
                    'temperature': 75,
                    'temperatureUnit': 'F',
                    'shortForecast': 'Sunny',
                    'detailedForecast': 'Sunny with a high near 75.'
                }
            ]
        }
    }

    # Create a WeatherApp instance with mocked initialization
    with patch.object(WeatherApp, '__init__', return_value=None):
        app = WeatherApp()

        # Set up the mocked services
        app.location_service = location_service
        app.weather_service = weather_service
        app.notification_service = notification_service
        app.api_client = api_client

        # Create a parent frame for UI components
        parent = wx.Frame(None, title="Test Frame")

        # Create real UI components for testing
        app.forecast_text = wx.TextCtrl(
            parent,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(400, 300)
        )

        app.alerts_list = wx.ListCtrl(
            parent,
            style=wx.LC_REPORT,
            size=(400, 200)
        )

        app.refresh_btn = MagicMock()

        # Set up other required attributes and mocks
        app.alerts_fetcher = MagicMock()
        app.forecast_fetcher = MagicMock()
        app.SetStatusText = MagicMock()  # Mock the SetStatusText method
        app._forecast_complete = False
        app._alerts_complete = False
        app.selected_location = ('Test City', 35.0, -80.0)
        app.ui_manager = MagicMock()

        # Mock the _FetchWeatherData method to avoid calling the original
        def fetch_weather_data(self, location):
            name, lat, lon = location
            # Call the fetchers directly
            self.forecast_fetcher.fetch(lat, lon,
                                       on_success=self._on_forecast_fetched,
                                       on_error=self._on_forecast_error)
            self.alerts_fetcher.fetch(lat, lon,
                                     on_success=self._on_alerts_fetched,
                                     on_error=self._on_alerts_error)
            self.refresh_btn.Disable()

        app._FetchWeatherData = types.MethodType(fetch_weather_data, app)

        # Add the parent frame to the yield so we can properly clean it up
        yield app, parent

        # Clean up
        parent.Destroy()


@pytest.fixture
def ui_component_frame(wx_app_session):
    """Create a frame for testing UI components.

    This fixture creates a frame that can be used to host UI components
    for testing. It ensures proper cleanup after the test.

    Args:
        wx_app_session: The wx.App fixture from conftest.py

    Returns:
        A wx.Frame instance
    """
    # Create a parent frame for UI components
    frame = wx.Frame(None, title="Test UI Components")

    # Show the frame to ensure UI updates are processed
    frame.Show()
    wx.Yield()

    yield frame

    # Clean up
    frame.Hide()
    wx.Yield()
    frame.Destroy()
    wx.Yield()


@pytest.fixture
def text_control(ui_component_frame):
    """Create an AccessibleTextCtrl for testing.

    This fixture creates an AccessibleTextCtrl that can be used for testing
    text-based UI components.

    Args:
        ui_component_frame: The frame fixture

    Returns:
        An AccessibleTextCtrl instance
    """
    # Create a text control
    text_ctrl = AccessibleTextCtrl(
        ui_component_frame,
        style=wx.TE_MULTILINE | wx.TE_READONLY,
        size=(400, 300),
        label="Test Text Control"
    )

    # Process events to ensure the control is properly initialized
    wx.Yield()

    yield text_ctrl


@pytest.fixture
def list_control(ui_component_frame):
    """Create an AccessibleListCtrl for testing.

    This fixture creates an AccessibleListCtrl that can be used for testing
    list-based UI components.

    Args:
        ui_component_frame: The frame fixture

    Returns:
        An AccessibleListCtrl instance
    """
    # Create a list control
    list_ctrl = AccessibleListCtrl(
        ui_component_frame,
        style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
        label="Test List Control",
        size=(400, 200)
    )

    # Set up columns
    list_ctrl.InsertColumn(0, "Column 1")
    list_ctrl.InsertColumn(1, "Column 2")
    list_ctrl.SetColumnWidth(0, 150)
    list_ctrl.SetColumnWidth(1, 250)

    # Process events to ensure the control is properly initialized
    wx.Yield()

    yield list_ctrl


@pytest.fixture
def nationwide_app(wx_app_session):
    """Create a WeatherApp instance with mocked services for nationwide testing.

    This fixture creates a WeatherApp with properly mocked services and UI components
    for testing the nationwide forecast display functionality.

    Args:
        wx_app_session: The wx.App fixture from conftest.py

    Returns:
        A configured WeatherApp instance with mocks and its parent frame
    """
    # Create mocks for the services
    location_service = MagicMock(spec=LocationService)
    weather_service = MagicMock(spec=WeatherService)
    notification_service = MagicMock()
    api_client = MagicMock()

    # Configure the location service mock
    location_service.is_nationwide_location.return_value = True
    location_service.get_current_location.return_value = ('Nationwide', 39.8283, -98.5795)

    # Configure the weather service mock with realistic test data
    weather_service.get_national_forecast_data.return_value = {
        'wpc': {
            'short_range': ('WPC SHORT RANGE FORECAST DISCUSSION\n\n'
                            'Valid 12Z Tue Apr 30 2023 - 12Z Thu May 2 2023\n\n'
                            'Test forecast data for nationwide view.')
        },
        'spc': {
            'day1': ('SPC DAY 1 OUTLOOK\n\n'
                     'Valid 120000Z - 011200Z\n\n'
                     'Test SPC data for nationwide view.')
        }
    }

    # Create a WeatherApp instance with mocked initialization
    with patch.object(WeatherApp, '__init__', return_value=None):
        app = WeatherApp()

        # Set up the mocked services
        app.location_service = location_service
        app.weather_service = weather_service
        app.notification_service = notification_service
        app.api_client = api_client

        # Create a real TextCtrl for testing instead of a mock
        # This allows us to test the actual behavior with a real control
        parent = wx.Frame(None, title="Test Frame")
        app.forecast_text = wx.TextCtrl(
            parent,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(400, 300)
        )

        # Set up other required attributes and mocks
        app.alerts_fetcher = MagicMock()
        app.SetStatusText = MagicMock()  # Mock the SetStatusText method
        app.refresh_btn = MagicMock()
        app._forecast_complete = False
        app._alerts_complete = False
        app.selected_location = ('Nationwide', 39.8283, -98.5795)
        app.ui_manager = MagicMock()

        # Mock the _FetchWeatherData method to avoid calling the original
        def fetch_weather_data(self, location):
            name, lat, lon = location
            # For nationwide location, get national forecast data
            if self.location_service.is_nationwide_location(name):
                forecast_data = self.weather_service.get_national_forecast_data()
                self._on_forecast_fetched(forecast_data)
                self._forecast_complete = True
                self._alerts_complete = True  # No alerts for nationwide
            else:
                # Call the fetchers directly
                self.forecast_fetcher.fetch(lat, lon,
                                           on_success=self._on_forecast_fetched,
                                           on_error=self._on_forecast_error)
                self.alerts_fetcher.fetch(lat, lon,
                                         on_success=self._on_alerts_fetched,
                                         on_error=self._on_alerts_error)
            self.refresh_btn.Disable()

        app._FetchWeatherData = types.MethodType(fetch_weather_data, app)

        # Create the actual _format_national_forecast method
        # This is better than mocking it as we want to test the actual formatting
        def format_national_forecast(_, national_data):
            """Format national forecast data for display

            Args:
                national_data: Dictionary with national forecast data

            Returns:
                Formatted text for display
            """
            lines = []

            # Add WPC data
            wpc_data = national_data.get("wpc", {})
            if wpc_data:
                lines.append("=== WEATHER PREDICTION CENTER (WPC) ===")

                # Short Range Forecast
                short_range = wpc_data.get("short_range")
                if short_range:
                    lines.append("\n--- SHORT RANGE FORECAST (Days 1-3) ---")
                    # Extract and add a summary (first few lines)
                    summary = "\n".join(short_range.split("\n")[0:10])
                    lines.append(summary)

            # Add SPC data
            spc_data = national_data.get("spc", {})
            if spc_data:
                lines.append("\n=== STORM PREDICTION CENTER (SPC) ===")

                # Day 1 Outlook
                day1 = spc_data.get("day1")
                if day1:
                    lines.append("\n--- DAY 1 CONVECTIVE OUTLOOK ---")
                    # Extract and add a summary (first few lines)
                    summary = "\n".join(day1.split("\n")[0:10])
                    lines.append(summary)

            # If no data was added, add a message
            if len(lines) == 0:
                lines.append("No data available for national forecast.")

            return "\n".join(lines)

        # Bind the method to the instance
        app._format_national_forecast = types.MethodType(format_national_forecast, app)

        # Add the parent frame to the yield so we can properly clean it up
        yield app, parent

        # Clean up
        parent.Destroy()
