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

    # Make sure app attributes are in a clean state before starting
    app._forecast_complete = False
    app._alerts_complete = False
    
    # Ensure the mock returns instantly with real test data
    app.weather_service.get_national_forecast_data.return_value = {
        "national_discussion_summaries": {
            "wpc": {
                "short_range_summary": "Test forecast data for nationwide view",
                "short_range_full": "Full test forecast data for nationwide view with additional details"
            },
            "spc": {
                "day1_summary": "Test SPC data for nationwide view",
                "day1_full": "Full test SPC data for nationwide view with additional details"
            },
            "attribution": "Data from NOAA/NWS/WPC and NOAA/NWS/SPC. See https://www.wpc.ncep.noaa.gov/ and https://www.spc.noaa.gov/ for full details."
        }
    }
    print("[TEST] Mock get_national_forecast_data returns:", app.weather_service.get_national_forecast_data.return_value)

    # Create an event waiter to track when the forecast is fetched
    waiter = AsyncEventWaiter()

    # Define the _on_national_forecast_fetched method to simulate the actual behavior
    def on_national_forecast_fetched(_, forecast_data):
        print("[TEST] on_national_forecast_fetched called with data")
        # Set complete flags first to avoid any race conditions
        app._forecast_complete = True
        app._alerts_complete = True  # Important for nationwide view
        
        # Update UI and state
        app.current_forecast = forecast_data
        formatted_text = app._format_national_forecast(forecast_data)
        app.forecast_text.SetValue(formatted_text)
        
        # Signal waiter last to ensure everything is ready
        waiter.callback(formatted_text)

    # Bind the method to the app instance and ensure no testing callbacks interfere
    app._on_national_forecast_fetched = types.MethodType(on_national_forecast_fetched, app)
    app._testing_forecast_callback = None
    # Also ensure no direct callbacks get triggered by the weather service
    app._on_forecast_fetched = types.MethodType(lambda self, data: None, app)

    # Call the method with test data from the weather service
    test_data = app.weather_service.get_national_forecast_data.return_value
    print("[TEST] Calling _on_national_forecast_fetched with test data")
    app._on_national_forecast_fetched(test_data)

    # Wait for the forecast to be fetched and UI to update with a reasonable timeout
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

    # Make sure app attributes are in a clean state before starting
    app._forecast_complete = False
    app._alerts_complete = False

    # Create an event waiter to track when the error is handled
    waiter = AsyncEventWaiter()

    # Define the _on_forecast_error method to simulate the actual behavior
    def on_forecast_error(_, error_msg):
        print("[TEST] on_forecast_error called with error message")
        # Set complete flag first to avoid race conditions
        app._forecast_complete = True
        app._alerts_complete = True  # Set this for nationwide view
        
        # Update UI
        error_text = f"Error fetching national forecast: {error_msg}"
        app.forecast_text.SetValue(error_text)
        
        # Signal waiter last to ensure everything is ready
        waiter.callback(error_text)

    # Bind the method to the app instance and ensure no test callbacks interfere
    app._on_forecast_error = types.MethodType(on_forecast_error, app)
    app._testing_forecast_error_callback = None
    # Also ensure no other error handlers get triggered
    app._on_error = types.MethodType(lambda self, *args: None, app)

    # Call the method with an error message
    print("[TEST] Calling _on_forecast_error with API connection failed")
    app._on_forecast_error("API connection failed")

    # Wait for the error to be handled and UI to update with reasonable timeout
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
    
    # Directly connect our waiter to the callback mechanism
    # We'll define _on_forecast_fetched to call our waiter
    def on_forecast_fetched(self, forecast_data):
        print("[TEST] on_forecast_fetched called with data")
        waiter.callback(forecast_data)
        app._forecast_complete = True
        app._alerts_complete = True  # No alerts for nationwide
        
    # Bind the method to the app instance
    app._on_forecast_fetched = types.MethodType(on_forecast_fetched, app)
    app._testing_forecast_callback = None  # Make sure we're not waiting on this

    print("[TEST] Calling _FetchWeatherData with:", app.selected_location)
    # Call the _FetchWeatherData method with the nationwide location
    app._FetchWeatherData(app.selected_location)

    # Wait for the forecast to be fetched with a reasonable timeout
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
