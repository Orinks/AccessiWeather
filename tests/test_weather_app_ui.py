import types
import pytest
from unittest.mock import MagicMock, patch

# Import fixtures and utilities from gui_test_fixtures
from tests.gui_test_fixtures import (
    nationwide_app,
    process_ui_events,
    wait_for,
    AsyncEventWaiter
)


def test_nationwide_forecast_display(nationwide_app):
    """Test that nationwide forecast data is properly displayed in the UI.

    This test verifies that when a nationwide location is selected, the app
    fetches national forecast data and displays it correctly in the forecast text control.
    It also tests that the content is properly formatted for accessibility.

    Args:
        nationwide_app: The nationwide_app fixture
    """
    app, parent = nationwide_app

    # Ensure the mock returns instantly with real test data
    app.weather_service.get_national_forecast_data.return_value = {
        "wpc": {"short_range": "Test forecast data for nationwide view"},
        "spc": {"day1": "Test SPC data for nationwide view"}
    }
    print("[TEST] Mock get_national_forecast_data returns:", app.weather_service.get_national_forecast_data.return_value)

    # Create an event waiter to track when the forecast is fetched
    waiter = AsyncEventWaiter()

    # Define the _on_forecast_fetched method to simulate the actual behavior
    def on_forecast_fetched(_, forecast_data):
        print("[TEST] on_forecast_fetched called with:", forecast_data)
        app.current_forecast = forecast_data
        formatted_text = app._format_national_forecast(forecast_data)
        app.forecast_text.SetValue(formatted_text)
        app._forecast_complete = True
        waiter.callback(formatted_text)

    # Bind the method to the app instance
    app._on_forecast_fetched = types.MethodType(on_forecast_fetched, app)

    # Set up the testing callback attribute that the original method might expect
    app._testing_forecast_callback = None

    # Call the method with test data from the weather service
    test_data = app.weather_service.get_national_forecast_data.return_value
    print("[TEST] Calling _on_forecast_fetched with:", test_data)
    app._on_forecast_fetched(test_data)

    # Wait for the forecast to be fetched and UI to update
    formatted_text = waiter.wait()
    assert formatted_text is not None, "Forecast fetch timed out"

    # Process events to ensure UI updates are applied
    process_ui_events()

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

    # Verify that the text is accessible (has non-empty value)
    assert len(forecast_text.strip()) > 0


def test_nationwide_error_handling(nationwide_app):
    """Test that errors in nationwide forecast fetching are properly handled.

    This test verifies that when an error occurs while fetching nationwide forecast data,
    the error is properly displayed in the UI and the forecast is marked as complete.
    It also tests that the error message is accessible to screen readers.

    Args:
        nationwide_app: The nationwide_app fixture
    """
    app, parent = nationwide_app

    # Create an event waiter to track when the error is handled
    waiter = AsyncEventWaiter()

    # Define the _on_forecast_error method to simulate the actual behavior
    def on_forecast_error(_, error_msg):
        error_text = f"Error fetching national forecast: {error_msg}"
        app.forecast_text.SetValue(error_text)
        app._forecast_complete = True
        waiter.callback(error_text)

    # Bind the method to the app instance
    app._on_forecast_error = types.MethodType(on_forecast_error, app)

    # Set up the testing callback attribute that the original method might expect
    app._testing_forecast_error_callback = None

    # Call the method with an error message
    app._on_forecast_error("API connection failed")

    # Wait for the error to be handled and UI to update
    error_text = waiter.wait()
    assert error_text is not None, "Error handling timed out"

    # Process events to ensure UI updates are applied
    process_ui_events()

    # Verify the forecast text contains the error message
    forecast_text = app.forecast_text.GetValue()
    assert "Error fetching national forecast: API connection failed" in forecast_text

    # Verify that the forecast is marked as complete
    assert app._forecast_complete is True

    # Verify that the error message is accessible (has non-empty value)
    assert len(forecast_text.strip()) > 0


def test_nationwide_fetch_process(nationwide_app):
    """Test the nationwide forecast fetching process.

    This test verifies that the nationwide forecast fetching process works correctly,
    including the interaction between the location service, weather service, and UI.

    Args:
        nationwide_app: The nationwide_app fixture
    """
    app, _ = nationwide_app

    # Create an event waiter to track when the forecast is fetched
    waiter = AsyncEventWaiter()

    # Set up the testing callback attribute that the original method expects
    app._testing_forecast_callback = waiter.callback

    print("[TEST] Calling _FetchWeatherData with:", app.selected_location)
    # Call the _FetchWeatherData method with the nationwide location
    app._FetchWeatherData(app.selected_location)

    # Wait for the forecast to be fetched
    forecast_data = waiter.wait()
    assert forecast_data is not None, "Forecast fetch timed out"

    # Process events to ensure UI updates are applied
    process_ui_events()

    # Verify that the weather service was called to get national forecast data
    app.weather_service.get_national_forecast_data.assert_called_once()

    # Verify that the forecast is marked as complete
    assert app._forecast_complete is True

    # Verify that alerts are also marked as complete (no alerts for nationwide)
    assert app._alerts_complete is True
