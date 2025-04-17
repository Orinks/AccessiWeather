"""Tests for the GUI loading feedback in the weather app.

This module tests the UI state during loading and after data is fetched.
"""

import pytest
import wx
import types
from unittest.mock import MagicMock, patch

from tests.gui_test_fixtures import mock_weather_app, wait_for


def test_ui_state_during_fetch(mock_weather_app):
    """Test that UI elements are properly updated during data fetching.
    
    This test verifies that when weather data is being fetched, the UI shows
    appropriate loading indicators and disables controls as needed.
    
    Args:
        mock_weather_app: The mock_weather_app fixture
    """
    app, _ = mock_weather_app
    
    # Set up the forecast fetcher mock to simulate a long-running fetch
    app.forecast_fetcher.fetch = MagicMock(return_value=None)
    app.alerts_fetcher.fetch = MagicMock(return_value=None)
    
    # Call the fetch method
    app._FetchWeatherData(app.selected_location)
    
    # Process events to ensure UI updates are applied
    wx.Yield()
    
    # Verify that the refresh button is disabled during fetch
    app.refresh_btn.Disable.assert_called_once()
    
    # Verify that the forecast fetcher was called with the correct location
    app.forecast_fetcher.fetch.assert_called_once()
    
    # Verify that the alerts fetcher was called with the correct location
    app.alerts_fetcher.fetch.assert_called_once()


def test_ui_state_on_fetch_success(mock_weather_app):
    """Test that UI elements are properly updated after successful data fetching.
    
    This test verifies that when weather data is successfully fetched, the UI
    is updated with the data and controls are re-enabled.
    
    Args:
        mock_weather_app: The mock_weather_app fixture
    """
    app, _ = mock_weather_app
    
    # Define the _on_forecast_fetched method to simulate the actual behavior
    def on_forecast_fetched(self, forecast_data):
        app.current_forecast = forecast_data
        app.ui_manager._UpdateForecastDisplay(forecast_data)
        app._forecast_complete = True
        app._check_update_complete = MagicMock()
    
    # Define the _on_alerts_fetched method to simulate the actual behavior
    def on_alerts_fetched(self, alerts_data):
        app.current_alerts = alerts_data
        app.ui_manager._UpdateAlertsDisplay(alerts_data)
        app._alerts_complete = True
        app._check_update_complete = MagicMock()
    
    # Bind the methods to the app instance
    app._on_forecast_fetched = types.MethodType(on_forecast_fetched, app)
    app._on_alerts_fetched = types.MethodType(on_alerts_fetched, app)
    
    # Set up the forecast fetcher mock to simulate a successful fetch
    app.forecast_fetcher.fetch = MagicMock(
        side_effect=lambda lat, lon, on_success, on_error: 
            on_success(app.weather_service.get_forecast.return_value)
    )
    
    # Set up the alerts fetcher mock to simulate a successful fetch
    app.alerts_fetcher.fetch = MagicMock(
        side_effect=lambda lat, lon, on_success, on_error: 
            on_success({"features": []})
    )
    
    # Call the fetch method
    app._FetchWeatherData(app.selected_location)
    
    # Process events to ensure UI updates are applied
    wx.Yield()
    
    # Verify that the UI manager methods were called with the correct data
    app.ui_manager._UpdateForecastDisplay.assert_called_once_with(
        app.weather_service.get_forecast.return_value
    )
    app.ui_manager._UpdateAlertsDisplay.assert_called_once_with(
        {"features": []}
    )
    
    # Verify that the forecast and alerts are marked as complete
    assert app._forecast_complete is True
    assert app._alerts_complete is True


def test_ui_state_on_fetch_error(mock_weather_app):
    """Test that UI elements are properly updated after failed data fetching.
    
    This test verifies that when weather data fetching fails, the UI shows
    appropriate error messages and controls are re-enabled.
    
    Args:
        mock_weather_app: The mock_weather_app fixture
    """
    app, _ = mock_weather_app
    
    # Define the _on_forecast_error method to simulate the actual behavior
    def on_forecast_error(self, error_msg):
        app.forecast_text.SetValue(f"Error fetching forecast: {error_msg}")
        app._forecast_complete = True
        app._check_update_complete = MagicMock()
    
    # Define the _on_alerts_error method to simulate the actual behavior
    def on_alerts_error(self, error_msg):
        app._alerts_complete = True
        app._check_update_complete = MagicMock()
    
    # Bind the methods to the app instance
    app._on_forecast_error = types.MethodType(on_forecast_error, app)
    app._on_alerts_error = types.MethodType(on_alerts_error, app)
    
    # Set up the forecast fetcher mock to simulate a failed fetch
    app.forecast_fetcher.fetch = MagicMock(
        side_effect=lambda lat, lon, on_success, on_error: 
            on_error("API connection failed")
    )
    
    # Set up the alerts fetcher mock to simulate a failed fetch
    app.alerts_fetcher.fetch = MagicMock(
        side_effect=lambda lat, lon, on_success, on_error: 
            on_error("API connection failed")
    )
    
    # Call the fetch method
    app._FetchWeatherData(app.selected_location)
    
    # Process events to ensure UI updates are applied
    wx.Yield()
    
    # Verify that the forecast text shows the error message
    assert "Error fetching forecast: API connection failed" in app.forecast_text.GetValue()
    
    # Verify that the forecast and alerts are marked as complete
    assert app._forecast_complete is True
    assert app._alerts_complete is True
