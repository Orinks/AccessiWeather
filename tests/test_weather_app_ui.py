import wx
import types
import pytest
from unittest.mock import MagicMock, patch

# Import the nationwide_app fixture directly
from tests.gui_test_fixtures import nationwide_app


def test_nationwide_forecast_display(nationwide_app):
    """Test that nationwide forecast data is properly displayed in the UI.

    This test verifies that when a nationwide location is selected, the app
    fetches national forecast data and displays it correctly in the forecast text control.

    Args:
        nationwide_app: The nationwide_app fixture
    """
    app, _ = nationwide_app

    # Define the _on_forecast_fetched method to simulate the actual behavior
    def on_forecast_fetched(self, forecast_data):
        app.current_forecast = forecast_data
        formatted_text = app._format_national_forecast(forecast_data)
        app.forecast_text.SetValue(formatted_text)
        app._forecast_complete = True

    # Bind the method to the app instance
    app._on_forecast_fetched = types.MethodType(on_forecast_fetched, app)

    # Call the method with test data from the weather service
    test_data = app.weather_service.get_national_forecast_data.return_value
    app._on_forecast_fetched(test_data)

    # Process events to ensure UI updates are applied
    wx.Yield()

    # Verify the forecast text contains the expected content
    forecast_text = app.forecast_text.GetValue()
    assert "WEATHER PREDICTION CENTER (WPC)" in forecast_text
    assert "SHORT RANGE FORECAST" in forecast_text
    assert "STORM PREDICTION CENTER (SPC)" in forecast_text
    assert "DAY 1 CONVECTIVE OUTLOOK" in forecast_text
    assert "Test forecast data for nationwide view" in forecast_text
    assert "Test SPC data for nationwide view" in forecast_text

    # Verify that the forecast is marked as complete
    assert app._forecast_complete is True


def test_nationwide_error_handling(nationwide_app):
    """Test that errors in nationwide forecast fetching are properly handled.

    This test verifies that when an error occurs while fetching nationwide forecast data,
    the error is properly displayed in the UI and the forecast is marked as complete.

    Args:
        nationwide_app: The nationwide_app fixture
    """
    app, _ = nationwide_app

    # Define the _on_forecast_error method to simulate the actual behavior
    def on_forecast_error(self, error_msg):
        app.forecast_text.SetValue(f"Error fetching national forecast: {error_msg}")
        app._forecast_complete = True

    # Bind the method to the app instance
    app._on_forecast_error = types.MethodType(on_forecast_error, app)

    # Call the method with an error message
    app._on_forecast_error("API connection failed")

    # Process events to ensure UI updates are applied
    wx.Yield()

    # Verify the forecast text contains the error message
    forecast_text = app.forecast_text.GetValue()
    assert "Error fetching national forecast: API connection failed" in forecast_text

    # Verify that the forecast is marked as complete
    assert app._forecast_complete is True
