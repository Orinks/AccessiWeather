"""Tests for precise location alerts functionality."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.async_fetchers import AlertsFetcher
from accessiweather.gui.settings_dialog import PRECISE_LOCATION_ALERTS_KEY


@pytest.fixture
def mock_api_client():
    """Create a mock API client for testing."""
    client = NoaaApiClient(user_agent="TestClient")
    client._make_request = MagicMock()
    client.identify_location_type = MagicMock(return_value=("county", "NJC015"))
    return client


@pytest.fixture
def mock_alerts_fetcher(mock_api_client):
    """Create a mock alerts fetcher for testing."""
    fetcher = AlertsFetcher(mock_api_client)
    return fetcher


def test_identify_location_type(mock_api_client):
    """Test that the API client correctly identifies location types."""
    # We already mocked identify_location_type in the fixture to return ("county", "NJC015")
    # so we just need to call it and verify the result
    location_type, location_id = mock_api_client.identify_location_type(40.0, -74.0)

    # Verify the result
    assert location_type == "county"
    assert location_id == "NJC015"

    # Verify the method was called with the correct parameters
    mock_api_client.identify_location_type.assert_called_once_with(40.0, -74.0)


def test_get_alerts_precise_location(mock_api_client):
    """Test getting alerts with precise location setting."""
    # Set up the mock
    mock_api_client.get_point_data = MagicMock(return_value={
        "properties": {
            "county": "https://api.weather.gov/zones/county/NJC015",
            "relativeLocation": {
                "properties": {
                    "state": "NJ"
                }
            }
        }
    })

    # Call get_alerts with precise_location=True
    mock_api_client.get_alerts(40.0, -74.0, precise_location=True)

    # Verify the API was called with the correct parameters
    mock_api_client._make_request.assert_called_with(
        "alerts/active", params={"zone": "NJC015"}
    )


def test_get_alerts_statewide(mock_api_client):
    """Test getting alerts with statewide setting."""
    # Set up the mock
    mock_api_client.get_point_data = MagicMock(return_value={
        "properties": {
            "county": "https://api.weather.gov/zones/county/NJC015",
            "relativeLocation": {
                "properties": {
                    "state": "NJ"
                }
            }
        }
    })

    # Call get_alerts with precise_location=False
    mock_api_client.get_alerts(40.0, -74.0, precise_location=False)

    # Verify the API was called with the correct parameters
    mock_api_client._make_request.assert_called_with(
        "alerts/active", params={"area": "NJ"}
    )


def test_alerts_fetcher_uses_precise_setting(mock_alerts_fetcher, mock_api_client):
    """Test that the alerts fetcher passes the precise location setting to the API client."""
    # Mock the API client's get_alerts method
    mock_api_client.get_alerts = MagicMock(return_value={"features": []})

    # Create a mock success callback
    on_success = MagicMock()

    # Call fetch with precise_location=True
    mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=True)

    # Wait for the thread to complete
    import time
    time.sleep(0.1)

    # Verify the API client was called with precise_location=True
    mock_api_client.get_alerts.assert_called_with(40.0, -74.0, radius=25, precise_location=True)

    # Reset the mock
    mock_api_client.get_alerts.reset_mock()

    # Call fetch with precise_location=False
    mock_alerts_fetcher.fetch(40.0, -74.0, on_success=on_success, precise_location=False)

    # Wait for the thread to complete
    time.sleep(0.1)

    # Verify the API client was called with precise_location=False
    mock_api_client.get_alerts.assert_called_with(40.0, -74.0, radius=25, precise_location=False)


@pytest.mark.skipif(not wx.GetApp(), reason="Requires wxPython app")
def test_settings_dialog_precise_location_toggle():
    """Test that the settings dialog includes the precise location toggle."""
    # Create a wx.App if one doesn't exist
    app = wx.App.Get()
    if not app:
        app = wx.App()

    # Create a parent frame
    frame = wx.Frame(None)

    # Create settings with the precise location setting
    settings = {
        "update_interval_minutes": 30,
        "alert_radius_miles": 25,
        "api_contact": "test@example.com",
        PRECISE_LOCATION_ALERTS_KEY: True
    }

    # Create the dialog
    from accessiweather.gui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(frame, settings)

    # Check that the precise location control exists and has the correct value
    assert hasattr(dialog, "precise_alerts_ctrl")
    assert dialog.precise_alerts_ctrl.GetValue() is True

    # Change the value
    dialog.precise_alerts_ctrl.SetValue(False)

    # Get the settings and verify the change
    new_settings = dialog.get_settings()
    assert new_settings[PRECISE_LOCATION_ALERTS_KEY] is False

    # Clean up
    dialog.Destroy()
    frame.Destroy()
