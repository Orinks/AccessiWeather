"""Tests for application exit handling with proper thread safety.

This module contains mock-based tests for application exit functionality,
avoiding the threading and UI simulation problems of the original test approach.
These tests verify the expected behavior during app exit without launching an
actual application instance or depending on simulated UI interactions.
"""

import threading
import wx
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.gui.weather_app import WeatherApp


class TestAppExitSafe:
    """Test suite for application exit handling using thread-safe mocks.
    
    This approach avoids the race conditions and flaky behavior of the original tests
    while still verifying that the application properly cleans up resources during exit.
    """

    def test_app_close_cancels_fetchers(self, wx_app):
        """Test that closing the app cancels all fetcher threads."""
        # Create mocks for the fetchers
        mock_forecast_fetcher = MagicMock()
        mock_alerts_fetcher = MagicMock()
        mock_discussion_fetcher = MagicMock()
        mock_national_forecast_fetcher = MagicMock()

        # Create a test config
        test_config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {"contact_info": "test@example.com"},
        }

        # Create mock services
        mock_weather_service = MagicMock()
        mock_location_service = MagicMock()
        # Configure location_service to return a valid location tuple
        mock_location_service.get_current_location.return_value = ("Test Location", 37.7749, -122.4194)
        mock_notification_service = MagicMock()
        mock_notification_service.notifier = MagicMock()

        # Patch UpdateWeatherData to prevent it from running during initialization
        with patch('accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData'), \
             patch('accessiweather.gui.weather_app.wx.MessageDialog'):
            # Create the app with our mocks
            app = WeatherApp(
                parent=None,
                weather_service=mock_weather_service,
                location_service=mock_location_service,
                notification_service=mock_notification_service,
                config=test_config
            )

            # Replace the fetchers with our mocks and give them _stop_event attributes
            app.forecast_fetcher = mock_forecast_fetcher
            app.forecast_fetcher._stop_event = threading.Event()
            app.alerts_fetcher = mock_alerts_fetcher
            app.alerts_fetcher._stop_event = threading.Event()
            app.discussion_fetcher = mock_discussion_fetcher
            app.discussion_fetcher._stop_event = threading.Event()
            app.national_forecast_fetcher = mock_national_forecast_fetcher
            app.national_forecast_fetcher._stop_event = threading.Event()

            # Trigger OnClose event
            app.OnClose(wx.CloseEvent())

            # Verify that all fetcher _stop_events were set
            assert app.forecast_fetcher._stop_event.is_set(), "Forecast fetcher stop event not set"
            assert app.alerts_fetcher._stop_event.is_set(), "Alerts fetcher stop event not set"
            assert app.discussion_fetcher._stop_event.is_set(), "Discussion fetcher stop event not set"
            assert app.national_forecast_fetcher._stop_event.is_set(), "National forecast fetcher stop event not set"

            # Clean up
            wx.CallAfter(app.Destroy)
            wx.SafeYield()

    def test_app_minimizes_to_tray(self, wx_app):
        """Test that the app minimizes to tray instead of closing when taskbar is active."""
        # Create a test config
        test_config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {"contact_info": "test@example.com"},
        }

        # Create mock services
        mock_weather_service = MagicMock()
        mock_location_service = MagicMock()
        # Configure location_service to return a valid location tuple
        mock_location_service.get_current_location.return_value = ("Test Location", 37.7749, -122.4194)
        mock_notification_service = MagicMock()
        mock_notification_service.notifier = MagicMock()

        # Patch UpdateWeatherData to prevent it from running during initialization
        with patch('accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData'), \
             patch('accessiweather.gui.weather_app.wx.MessageDialog'):
            # Create the app with our mocks
            app = WeatherApp(
                parent=None,
                weather_service=mock_weather_service,
                location_service=mock_location_service,
                notification_service=mock_notification_service,
                config=test_config
            )

            # Create a mock taskbar icon
            mock_taskbar_icon = MagicMock()
            app.taskbar_icon = mock_taskbar_icon

            # Mock the Hide method to verify it gets called
            original_hide = app.Hide
            app.Hide = MagicMock(side_effect=original_hide)

            # Mock Veto method on the event
            close_event = wx.CloseEvent()
            close_event.Veto = MagicMock()

            # Trigger OnClose event
            app.OnClose(close_event)

            # If taskbar icon exists, app should be hidden instead of destroyed
            app.Hide.assert_called_once()
            close_event.Veto.assert_called_once()

            # Clean up
            wx.CallAfter(app.Destroy)
            wx.SafeYield()

    def test_force_close_destroys_app(self, wx_app):
        """Test that force close destroys the app even with taskbar icon."""
        # Create a test config
        test_config = {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30, "alert_radius_miles": 25},
            "api_settings": {"contact_info": "test@example.com"},
        }

        # Create mock services
        mock_weather_service = MagicMock()
        mock_location_service = MagicMock()
        # Configure location_service to return a valid location tuple
        mock_location_service.get_current_location.return_value = ("Test Location", 37.7749, -122.4194)
        mock_notification_service = MagicMock()
        mock_notification_service.notifier = MagicMock()

        # Patch UpdateWeatherData to prevent it from running during initialization
        with patch('accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData'), \
             patch('accessiweather.gui.weather_app.wx.MessageDialog'):
            # Create the app with our mocks
            app = WeatherApp(
                parent=None,
                weather_service=mock_weather_service,
                location_service=mock_location_service,
                notification_service=mock_notification_service,
                config=test_config
            )

            # Create a mock taskbar icon
            mock_taskbar_icon = MagicMock()
            app.taskbar_icon = mock_taskbar_icon

            # Set the force close flag
            app._force_close = True

            # Create a close event
            close_event = wx.CloseEvent()

            # Create a mock for Destroy method to verify it gets called
            original_destroy = app.Destroy
            app.Destroy = MagicMock(side_effect=original_destroy)

            # Trigger OnClose event
            app.OnClose(close_event)

            # Verify Destroy was called
            app.Destroy.assert_called_once()

            # Clean up - no need to manually destroy since we called the real destroy through the mock
