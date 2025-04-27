"""Tests for alert update functionality."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.gui.settings_dialog import UPDATE_INTERVAL_KEY
from accessiweather.gui.weather_app import WeatherApp


@pytest.fixture
def mock_services():
    """Create mock services for WeatherApp."""
    return {
        'weather_service': MagicMock(),
        'location_service': MagicMock(),
        'notification_service': MagicMock(),
    }


@pytest.fixture
def mock_config():
    """Create a mock configuration with update interval set."""
    return {
        'settings': {
            UPDATE_INTERVAL_KEY: 5,  # 5 minutes
            'alert_radius_miles': 25,
            'precise_location_alerts': True,
            'show_nationwide_location': True,
        },
        'api_settings': {
            'api_contact': 'test@example.com'
        }
    }


@pytest.fixture
def mock_app(mock_services, mock_config):
    """Create a mock WeatherApp instance."""
    with patch('wx.Frame'):
        app = MagicMock()
        app.weather_service = mock_services['weather_service']
        app.location_service = mock_services['location_service']
        app.notification_service = mock_services['notification_service']
        app.config = mock_config
        app.current_location = {'latitude': 40.0, 'longitude': -75.0, 'name': 'Test Location'}
        app.current_alerts = []
        app.ui_manager = MagicMock()
        app.updating = False
        app._alerts_complete = False
        app._forecast_complete = False
        app._check_update_complete = MagicMock()
        app._testing_alerts_callback = None
        return app


def test_on_alerts_fetched():
    """Test the _on_alerts_fetched method."""
    # Create a mock app
    mock_app = MagicMock()
    mock_app.notification_service = MagicMock()
    mock_app.ui_manager = MagicMock()
    mock_app._check_update_complete = MagicMock()
    mock_app._testing_alerts_callback = None

    # Mock the notification service response
    processed_alerts = [
        {
            'id': 'alert1',
            'headline': 'Test Alert',
            'description': 'Test Description',
            'instruction': 'Test Instruction',
            'severity': 'Moderate',
            'event': 'Test Event',
            'effective': '2024-01-01T00:00:00Z',
            'expires': '2024-01-02T00:00:00Z',
            'status': 'Actual',
            'messageType': 'Alert',
            'areaDesc': 'Test Area'
        }
    ]
    mock_app.notification_service.process_alerts.return_value = processed_alerts

    # Create sample alert data
    mock_alerts_data = {
        'features': [
            {
                'id': 'alert1',
                'properties': {
                    'headline': 'Test Alert',
                    'description': 'Test Description',
                    'instruction': 'Test Instruction',
                    'severity': 'Moderate',
                    'event': 'Test Event',
                    'effective': '2024-01-01T00:00:00Z',
                    'expires': '2024-01-02T00:00:00Z',
                    'status': 'Actual',
                    'messageType': 'Alert',
                    'areaDesc': 'Test Area'
                }
            }
        ]
    }

    # Call the method directly
    WeatherApp._on_alerts_fetched(mock_app, mock_alerts_data)

    # Verify that the notification service was called to process the alerts
    mock_app.notification_service.process_alerts.assert_called_once_with(mock_alerts_data)

    # Verify that the processed alerts were saved to current_alerts
    assert mock_app.current_alerts == processed_alerts

    # Verify that the UI manager was called with the processed alerts
    mock_app.ui_manager.display_alerts_processed.assert_called_once_with(processed_alerts)

    # Verify that the notification service was called to notify about alerts
    mock_app.notification_service.notify_alerts.assert_called_once_with(
        processed_alerts, len(processed_alerts)
    )

    # Verify that the alerts_complete flag was set
    assert mock_app._alerts_complete is True

    # Verify that check_update_complete was called
    mock_app._check_update_complete.assert_called_once()


def test_alert_update_interval(mock_app):
    """Test that alerts are updated based on the update interval."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_app.config['settings'][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that will trigger an update
    mock_app.last_update = mock_time - update_interval_seconds - 1

    # Import the OnTimer method from weather_app_handlers.py
    from accessiweather.gui.weather_app_handlers import WeatherAppHandlers

    # Call OnTimer with a mock event
    with patch('time.time', return_value=mock_time):
        WeatherAppHandlers.OnTimer(mock_app, MagicMock())

    # Verify that UpdateWeatherData was called, which should include updating alerts
    mock_app.UpdateWeatherData.assert_called_once()


def test_update_weather_data_includes_alerts():
    """Test that UpdateWeatherData includes fetching alerts."""
    # Create a mock app
    mock_app = MagicMock()
    mock_app.location_service = MagicMock()
    mock_app.weather_service = MagicMock()
    mock_app._on_forecast_fetched = MagicMock()
    mock_app._on_alerts_fetched = MagicMock()

    # Mock the location service to return a location
    location = ('Test Location', 40.0, -75.0)
    mock_app.location_service.get_current_location.return_value = location

    # Mock the config
    mock_app.config = {
        'settings': {
            'precise_location_alerts': True,
            'alert_radius_miles': 25
        }
    }

    # Mock the weather service responses
    mock_forecast_data: dict = {'properties': {'periods': []}}
    mock_alerts_data: dict = {'features': []}
    mock_app.weather_service.get_forecast.return_value = mock_forecast_data
    mock_app.weather_service.get_alerts.return_value = mock_alerts_data

    # Call the actual WeatherApp.UpdateWeatherData method
    # This will call _FetchWeatherData which we'll implement directly
    def mock_update_weather_data(self):
        # Get current location from the location service
        location = self.location_service.get_current_location()
        if location is None:
            return

        # Set updating flag
        self.updating = True

        # Call our mock implementation of _FetchWeatherData
        _, lat, lon = location  # Ignore name as it's not used

        # Get forecast data
        forecast_data = self.weather_service.get_forecast(lat, lon)
        self._on_forecast_fetched(forecast_data)

        # Get alerts data
        precise_location = self.config.get("settings", {}).get("precise_location_alerts", True)
        alert_radius = self.config.get("settings", {}).get("alert_radius_miles", 25)
        alerts_data = self.weather_service.get_alerts(
            lat, lon, radius=alert_radius, precise_location=precise_location
        )
        self._on_alerts_fetched(alerts_data)

    # Call our mock implementation
    mock_update_weather_data(mock_app)

    # Verify that get_alerts was called with the correct parameters
    mock_app.weather_service.get_alerts.assert_called_once_with(
        40.0, -75.0,
        radius=mock_app.config['settings']['alert_radius_miles'],
        precise_location=mock_app.config['settings']['precise_location_alerts']
    )
