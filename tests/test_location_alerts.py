"""Tests for location-specific alert functionality.

This module tests the enhanced alert functionality that identifies location types
and filters alerts based on precise location or statewide settings.
"""

import json
import os
from unittest.mock import MagicMock

import pytest

from accessiweather.api_client import NoaaApiClient


@pytest.fixture
def mock_api_client():
    """Create a mock API client for testing."""
    client = NoaaApiClient(user_agent="TestClient")
    client._make_request = MagicMock()  # Mock the _make_request method
    return client


@pytest.fixture
def sample_point_data():
    """Sample point data for testing location identification."""
    # Load sample data from file
    file_path = os.path.join(os.path.dirname(__file__), "data", "sample_point_data.json")
    with open(file_path, "r") as f:
        return json.load(f)


@pytest.fixture
def sample_alerts_data():
    """Sample alerts data for testing."""
    # Load sample data from file
    file_path = os.path.join(os.path.dirname(__file__), "data", "sample_alerts_data.json")
    with open(file_path, "r") as f:
        return json.load(f)


def test_identify_location_type(mock_api_client, sample_point_data):
    """Test that the API client correctly identifies location types."""
    # Mock the get_point_data method to return our sample data
    mock_api_client.get_point_data = MagicMock(return_value=sample_point_data)

    # Call the method that will identify location type
    location_type, location_id = mock_api_client.identify_location_type(40.0, -74.0)

    # Assert that the location type and ID are correctly identified
    assert location_type == "county"
    assert location_id == "NJC015"  # This should match what's in the sample data


def test_get_alerts_precise_location(mock_api_client, sample_point_data, sample_alerts_data):
    """Test getting alerts for a precise location."""
    # Mock the necessary methods
    mock_api_client.get_point_data = MagicMock(return_value=sample_point_data)
    mock_api_client._make_request.return_value = sample_alerts_data

    # Call get_alerts with precise_location=True
    alerts = mock_api_client.get_alerts(40.0, -74.0, precise_location=True)

    # Check that the correct endpoint and parameters were used
    mock_api_client._make_request.assert_called_with(
        "alerts/active", params={"zone": "NJC015"}, force_refresh=False  # Should use the county/zone ID
    )

    # Verify the returned alerts
    assert alerts == sample_alerts_data


def test_get_alerts_statewide(mock_api_client, sample_point_data, sample_alerts_data):
    """Test getting statewide alerts."""
    # Mock the necessary methods
    mock_api_client.get_point_data = MagicMock(return_value=sample_point_data)
    mock_api_client._make_request.return_value = sample_alerts_data

    # Call get_alerts with precise_location=False
    alerts = mock_api_client.get_alerts(40.0, -74.0, precise_location=False)

    # Check that the correct endpoint and parameters were used
    mock_api_client._make_request.assert_called_with(
        "alerts/active", params={"area": "NJ"}, force_refresh=False  # Should use the state code
    )

    # Verify the returned alerts
    assert alerts == sample_alerts_data


def test_fallback_to_radius_search(mock_api_client):
    """Test fallback to radius search when location type cannot be determined."""
    # Mock get_point_data to return data without location information
    mock_api_client.get_point_data = MagicMock(return_value={"properties": {}})
    mock_api_client._make_request.return_value = {"features": []}

    # Call get_alerts
    mock_api_client.get_alerts(40.0, -74.0, radius=25)

    # Check that it fell back to radius search
    mock_api_client._make_request.assert_called_with(
        "alerts/active", params={"point": "40.0,-74.0", "radius": "25"}, force_refresh=False
    )
