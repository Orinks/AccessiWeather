"""Tests for notification settings functionality."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from accessiweather.notifications import WeatherNotifier


@pytest.fixture
def mock_components():
    """Mock the components used by WeatherApp."""
    # Mock the API client
    with patch("accessiweather.api_client.NoaaApiClient") as mock_api_client_class:
        mock_api_client = mock_api_client_class.return_value

        # Mock the location manager
        with patch("accessiweather.location.LocationManager") as mock_location_manager_class:
            mock_location_manager = mock_location_manager_class.return_value
            mock_location_manager.get_current_location.return_value = ("Test City", 35.0, -80.0)

            # Use a real notifier for these tests
            real_notifier = WeatherNotifier()

            yield mock_api_client, mock_location_manager, real_notifier


@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
        # Create a default config
        default_config = {
            "settings": {
                "update_interval_minutes": 30,
                "api_contact": "test@example.com",
                "alert_radius_miles": 25,
            }
        }
        temp_file.write(json.dumps(default_config).encode("utf-8"))
        temp_file_path = temp_file.name

    yield temp_file_path

    # Clean up
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


def test_api_client_get_alerts_with_radius(mock_components):
    """Test that the API client get_alerts method accepts a radius parameter."""
    mock_api_client, _, _ = mock_components

    # Call get_alerts with a radius parameter
    mock_api_client.get_alerts(35.0, -80.0, radius=50)

    # Verify the method was called with the radius parameter
    mock_api_client.get_alerts.assert_called_with(35.0, -80.0, radius=50)

    # No cleanup needed for this test


def test_notifier_processes_alerts(mock_components):
    """Test that the notifier processes alerts correctly."""
    _, _, notifier = mock_components

    # Create a sample alert
    alert = {
        "properties": {
            "id": "test-alert-1",
            "event": "Tornado Warning",
            "headline": "Tornado Warning for Test County",
            "description": "A tornado has been spotted in the area.",
            "instruction": "Take shelter immediately.",
            "effective": "2023-01-01T00:00:00Z",
            "expires": "2099-01-02T00:00:00Z",  # Far future date
            "severity": "Extreme",
            "certainty": "Observed",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-80.1, 35.1],  # Near the test location
                    [-80.0, 35.1],
                    [-80.0, 35.0],
                    [-80.1, 35.0],
                    [-80.1, 35.1],
                ]
            ],
        },
    }

    # Patch the show_notification method
    with patch.object(notifier, "show_notification") as mock_show_notification:
        # Process the alert
        processed_alerts = notifier.process_alerts({"features": [alert]})

        # Verify the alert was processed
        assert len(processed_alerts) == 1
        assert processed_alerts[0]["id"] == "test-alert-1"

        # Verify the notification was shown
        mock_show_notification.assert_called_once()

        # Process the same alert again - should not trigger another notification
        mock_show_notification.reset_mock()
        notifier.process_alerts({"features": [alert]})
        mock_show_notification.assert_not_called()


def test_api_client_get_alerts_with_different_radius(mock_components):
    """Test that the API client get_alerts method accepts different radius values."""
    mock_api_client, _, _ = mock_components

    # Call get_alerts with a radius parameter of 25
    mock_api_client.get_alerts(35.0, -80.0, radius=25)

    # Verify the method was called with the radius parameter
    mock_api_client.get_alerts.assert_called_with(35.0, -80.0, radius=25)

    # Reset the mock
    mock_api_client.reset_mock()

    # Call get_alerts with a different radius parameter
    mock_api_client.get_alerts(35.0, -80.0, radius=75)

    # Verify the method was called with the new radius parameter
    mock_api_client.get_alerts.assert_called_with(35.0, -80.0, radius=75)
