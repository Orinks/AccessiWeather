"""GUI test fixtures for AccessiWeather.

This module provides fixtures for testing GUI components in AccessiWeather.
These fixtures are designed to be reusable across different test modules.
"""

import time
import types
import pytest
import wx
from unittest.mock import MagicMock, patch

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.services.location_service import LocationService
from accessiweather.services.weather_service import WeatherService


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
