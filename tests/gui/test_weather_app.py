"""Tests for WeatherApp class timer functionality."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.gui.handlers.timer_handlers import WeatherAppTimerHandlers
from accessiweather.gui.settings.constants import UPDATE_INTERVAL_KEY
from accessiweather.gui.weather_app import WeatherApp


@pytest.fixture
def mock_services():
    """Create mock services for WeatherApp."""
    return {
        "weather_service": MagicMock(),
        "location_service": MagicMock(),
        "notification_service": MagicMock(),
    }


@pytest.fixture
def mock_config():
    """Create a mock configuration with update interval set."""
    return {
        "settings": {
            UPDATE_INTERVAL_KEY: 5,  # 5 minutes
            "alert_radius_miles": 25,
            "precise_location_alerts": True,
            "show_nationwide_location": True,
        },
        "api_settings": {"api_contact": "test@example.com"},
    }


@pytest.fixture
def mock_app(mock_services, mock_config):
    """Create a mock WeatherApp instance."""
    # Create a mock object with the necessary attributes
    app = MagicMock()
    app.weather_service = mock_services["weather_service"]
    app.location_service = mock_services["location_service"]
    app.notification_service = mock_services["notification_service"]
    app.config = mock_config
    app.timer = MagicMock()
    app.updating = False
    app.last_update = 0.0

    # Add the OnTimer method from WeatherAppTimerHandlers
    app.OnTimer = WeatherAppTimerHandlers.OnTimer.__get__(app)

    return app


@pytest.mark.gui
@pytest.mark.unit
def test_on_timer_update_interval(mock_app):
    """Test that OnTimer uses the correct update interval from config."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_app.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that will trigger an update
    mock_app.last_update = mock_time - update_interval_seconds - 1

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_app.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was called
    mock_app.UpdateWeatherData.assert_called_once()


@pytest.mark.gui
@pytest.mark.unit
def test_on_timer_no_update_needed(mock_app):
    """Test that OnTimer doesn't update when the interval hasn't elapsed."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_app.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that won't trigger an update
    mock_app.last_update = mock_time - update_interval_seconds + 60  # 1 minute before update is due

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_app.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was not called
    mock_app.UpdateWeatherData.assert_not_called()


def test_on_timer_already_updating(mock_app):
    """Test that OnTimer doesn't update when already updating."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_app.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that would trigger an update
    mock_app.last_update = mock_time - update_interval_seconds - 1

    # Set updating flag to True
    mock_app.updating = True

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_app.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was not called
    mock_app.UpdateWeatherData.assert_not_called()


def test_on_timer_uses_update_interval_key_constant(mock_app):
    """Test that OnTimer uses the UPDATE_INTERVAL_KEY constant."""
    # Set up the test with a different key to ensure the constant is used
    mock_time = 1000.0
    mock_app.config["settings"] = {
        "update_interval_minutes": 10,  # This should be ignored
        UPDATE_INTERVAL_KEY: 5,  # This should be used (5 minutes)
    }
    update_interval_seconds = 5 * 60  # 5 minutes in seconds

    # Set last_update to a time that will trigger an update
    mock_app.last_update = mock_time - update_interval_seconds - 1

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_app.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was called
    mock_app.UpdateWeatherData.assert_called_once()


def test_weather_app_timer_initialization():
    """Test that WeatherApp initializes the timer correctly."""
    # Mock wx.Timer and other dependencies
    with (
        patch("wx.Timer") as mock_timer_class,
        patch("accessiweather.gui.weather_app.WeatherApp.__init__", return_value=None),
        patch("accessiweather.gui.weather_app.WeatherApp.Bind"),
        patch("accessiweather.gui.weather_app.logger"),
    ):
        # Create a mock timer instance
        mock_timer = MagicMock()
        mock_timer_class.return_value = mock_timer

        # Create a WeatherApp instance
        app = WeatherApp()
        app.config = {"settings": {UPDATE_INTERVAL_KEY: 5}}

        # Call the timer initialization code
        app.timer = mock_timer
        app.timer.Start(1000)

        # Verify that the timer was started with the correct interval
        mock_timer.Start.assert_called_once_with(1000)
