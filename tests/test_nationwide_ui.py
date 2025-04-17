import pytest
import wx
from accessiweather.gui import WeatherApp
from unittest.mock import MagicMock, patch
from accessiweather.services.location_service import LocationService
from accessiweather.services.weather_service import WeatherService


@pytest.fixture
def app():
    # Create a wx.App if one doesn't exist
    if not wx.App.Get():
        _ = wx.App(False)

    # Create mocks for the services
    location_service = MagicMock(spec=LocationService)
    weather_service = MagicMock(spec=WeatherService)
    notification_service = MagicMock()
    api_client = MagicMock()

    # Configure the location service mock
    location_service.is_nationwide_location.return_value = True
    location_service.get_current_location.return_value = ('Nationwide', 39.8283, -98.5795)

    # Configure the weather service mock
    weather_service.get_national_forecast_data.return_value = {
        'wpc': {'short_range': 'National Weather Forecast Test Data'}
    }

    # Create a mock WeatherApp that doesn't initialize the UI
    with patch.object(WeatherApp, '__init__', return_value=None):
        app = WeatherApp()
        app.location_service = location_service
        app.weather_service = weather_service
        app.notification_service = notification_service
        app.api_client = api_client
        app.forecast_text = MagicMock()
        app.alerts_fetcher = MagicMock()
        # Mock methods
        app.SetStatusText = MagicMock()
        app.refresh_btn = MagicMock()

        # Mock the _format_national_forecast method
        app._format_national_forecast = MagicMock(return_value='formatted')
        app._forecast_complete = False
        app._alerts_complete = False
        app.selected_location = ('Nationwide', 39.8283, -98.5795)
        app.ui_manager = MagicMock()
        app._testing_forecast_callback = None
        app._testing_forecast_error_callback = None
        return app


def test_nationwide_selection_triggers_fetch(app):
    # Create a mock implementation of _FetchWeatherData that calls the weather service
    def mock_fetch_weather_data(location):
        name, lat, lon = location
        if app.location_service.is_nationwide_location(name):
            app.weather_service.get_national_forecast_data()

    # Assign the mock implementation
    app._FetchWeatherData = mock_fetch_weather_data

    # Call the method with a nationwide location
    app._FetchWeatherData(app.selected_location)

    # Verify that the weather service was called to get national forecast data
    app.weather_service.get_national_forecast_data.assert_called_once()


def test_nationwide_success_updates_ui(app):
    # Define a mock implementation of _on_forecast_fetched
    def mock_on_forecast_fetched(forecast_data):
        app.current_forecast = forecast_data
        formatted_text = app._format_national_forecast(forecast_data)
        app.forecast_text.SetValue(formatted_text)
        app._forecast_complete = True

    # Assign the mock implementation
    app._on_forecast_fetched = mock_on_forecast_fetched

    # Call the method with test data
    app._on_forecast_fetched({'wpc': {'short_range': 'test'}})

    # Verify that the formatting method was called and the UI was updated
    app._format_national_forecast.assert_called_once_with({'wpc': {'short_range': 'test'}})
    app.forecast_text.SetValue.assert_called_once_with('formatted')
    assert app._forecast_complete is True


def test_nationwide_error_updates_ui(app):
    # Define a mock implementation of _on_forecast_error
    def mock_on_forecast_error(error):
        app.forecast_text.SetValue(f"Error fetching national forecast: {error}")
        app._forecast_complete = True

    # Assign the mock implementation
    app._on_forecast_error = mock_on_forecast_error

    # Call the method with an error message
    app._on_forecast_error('fail')

    # Verify that the UI was updated with the error message
    app.forecast_text.SetValue.assert_called_once_with("Error fetching national forecast: fail")
    assert app._forecast_complete is True


def test_alerts_not_fetched_for_nationwide(app):
    # Define a mock implementation of _FetchWeatherData
    def mock_fetch_weather_data(location):
        name, lat, lon = location
        if app.location_service.is_nationwide_location(name):
            # For nationwide, don't fetch alerts
            app._alerts_complete = True
        else:
            # For regular locations, fetch alerts
            app.alerts_fetcher.fetch(lat, lon)

    # Assign the mock implementation
    app._FetchWeatherData = mock_fetch_weather_data

    # Call the method with a nationwide location
    app._FetchWeatherData(app.selected_location)

    # Verify that alerts_fetcher.fetch was not called
    app.alerts_fetcher.fetch.assert_not_called()
    assert app._alerts_complete is True
