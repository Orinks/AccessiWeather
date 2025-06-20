"""Tests for the timer handlers module."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.gui.handlers.timer_handlers import WeatherAppTimerHandlers
from accessiweather.gui.settings.constants import AUTO_REFRESH_NATIONAL_KEY, UPDATE_INTERVAL_KEY
from accessiweather.location import NATIONWIDE_LOCATION_NAME


@pytest.fixture
def mock_handler():
    """Create a mock WeatherAppTimerHandlers instance."""
    handler = MagicMock(spec=WeatherAppTimerHandlers)

    # Set up required attributes and methods
    handler.config = {
        "settings": {
            UPDATE_INTERVAL_KEY: 10,  # 10 minutes
            AUTO_REFRESH_NATIONAL_KEY: True,
        }
    }
    handler.updating = False
    handler.last_update = 0.0
    handler.location_service = MagicMock()
    handler.UpdateWeatherData = MagicMock()
    handler.UpdateNationalData = MagicMock()

    # Add the OnTimer method from WeatherAppTimerHandlers
    handler.OnTimer = WeatherAppTimerHandlers.OnTimer.__get__(handler)

    return handler


def test_on_timer_calls_update_weather_data(mock_handler):
    """Test that OnTimer calls UpdateWeatherData when it's time to update."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_handler.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that will trigger an update
    mock_handler.last_update = mock_time - update_interval_seconds - 1

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_handler.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was called
    mock_handler.UpdateWeatherData.assert_called_once()


def test_on_timer_no_update_needed(mock_handler):
    """Test that OnTimer doesn't update when the interval hasn't elapsed."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_handler.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that won't trigger an update
    mock_handler.last_update = (
        mock_time - update_interval_seconds + 60
    )  # 1 minute before update is due

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_handler.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was not called
    mock_handler.UpdateWeatherData.assert_not_called()


def test_on_timer_already_updating(mock_handler):
    """Test that OnTimer doesn't update when already updating."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_handler.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that would trigger an update
    mock_handler.last_update = mock_time - update_interval_seconds - 1

    # Set updating flag to True
    mock_handler.updating = True

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_handler.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was not called
    mock_handler.UpdateWeatherData.assert_not_called()


def test_on_timer_updates_national_data_when_nationwide_selected(mock_handler):
    """Test that OnTimer calls UpdateNationalData when nationwide location is selected."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_handler.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that will trigger an update
    mock_handler.last_update = mock_time - update_interval_seconds - 1

    # Set up location service to return nationwide location
    mock_handler.location_service.get_current_location_name.return_value = NATIONWIDE_LOCATION_NAME
    mock_handler.location_service.is_nationwide_location.return_value = True

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_handler.OnTimer(MagicMock())

    # Verify that both UpdateWeatherData and UpdateNationalData were called
    mock_handler.UpdateWeatherData.assert_called_once()
    mock_handler.UpdateNationalData.assert_called_once()


def test_on_timer_does_not_update_national_data_when_not_nationwide(mock_handler):
    """Test that OnTimer doesn't call UpdateNationalData when nationwide location is not selected."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_handler.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that will trigger an update
    mock_handler.last_update = mock_time - update_interval_seconds - 1

    # Set up location service to return a non-nationwide location
    mock_handler.location_service.get_current_location_name.return_value = "New York"
    mock_handler.location_service.is_nationwide_location.return_value = False

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_handler.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was called but UpdateNationalData was not
    mock_handler.UpdateWeatherData.assert_called_once()
    mock_handler.UpdateNationalData.assert_not_called()


def test_on_timer_respects_auto_refresh_national_setting(mock_handler):
    """Test that OnTimer respects the auto_refresh_national setting."""
    # Set up the test
    mock_time = 1000.0
    update_interval_minutes = mock_handler.config["settings"][UPDATE_INTERVAL_KEY]
    update_interval_seconds = update_interval_minutes * 60

    # Set last_update to a time that will trigger an update
    mock_handler.last_update = mock_time - update_interval_seconds - 1

    # Set up location service to return nationwide location
    mock_handler.location_service.get_current_location_name.return_value = NATIONWIDE_LOCATION_NAME
    mock_handler.location_service.is_nationwide_location.return_value = True

    # Disable auto-refresh for national data
    mock_handler.config["settings"][AUTO_REFRESH_NATIONAL_KEY] = False

    # Call OnTimer with a mock event
    with patch("time.time", return_value=mock_time):
        mock_handler.OnTimer(MagicMock())

    # Verify that UpdateWeatherData was called but UpdateNationalData was not
    mock_handler.UpdateWeatherData.assert_called_once()
    mock_handler.UpdateNationalData.assert_not_called()
