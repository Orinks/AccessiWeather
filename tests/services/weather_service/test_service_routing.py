"""Tests for WeatherService routing and alert processing functionality."""

from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_should_use_openmeteo_us_location(weather_service):
    """Test that NWS is preferred for US locations."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # US coordinates (New York)
    lat, lon = 40.7128, -74.0060

    # Mock the geocoding service to return True for US location
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value
        mock_geocoding_instance.validate_coordinates.return_value = True

        result = weather_service._should_use_openmeteo(lat, lon)

    assert result is False


@pytest.mark.unit
def test_should_use_openmeteo_non_us_location(weather_service):
    """Test that Open-Meteo is used for non-US locations."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock the geocoding service to return False for non-US location
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value
        mock_geocoding_instance.validate_coordinates.return_value = False

        result = weather_service._should_use_openmeteo(lat, lon)

    assert result is True


@pytest.mark.unit
def test_should_use_openmeteo_edge_cases(weather_service):
    """Test edge cases for location detection."""
    # Set the data source to auto for this test
    weather_service.config = {"settings": {"data_source": "auto"}}

    # Test coordinates at US borders
    test_cases = [
        (49.0, -125.0, True),  # Canada (north of US)
        (25.0, -80.0, False),  # Florida (US)
        (32.0, -117.0, False),  # California (US)
        (19.0, -155.0, False),  # Hawaii (US)
        (64.0, -153.0, False),  # Alaska (US)
    ]

    # Mock the geocoding service to return appropriate values
    with patch("accessiweather.geocoding.GeocodingService") as mock_geocoding_class:
        mock_geocoding_instance = mock_geocoding_class.return_value

        for lat, lon, expected in test_cases:
            # Set the mock to return False for non-US (expected=True) and True for US (expected=False)
            mock_geocoding_instance.validate_coordinates.return_value = not expected

            result = weather_service._should_use_openmeteo(lat, lon)
            assert result == expected, f"Failed for coordinates ({lat}, {lon})"


def test_process_alerts(weather_service):
    """Test processing alerts data."""
    alerts_data = {
        "features": [
            {
                "id": "alert1",
                "properties": {
                    "headline": "Test Alert 1",
                    "description": "Description 1",
                    "instruction": "Instruction 1",
                    "severity": "Moderate",
                    "event": "Test Event 1",
                    "effective": "2024-01-01T00:00:00Z",
                    "expires": "2024-01-02T00:00:00Z",
                    "status": "Actual",
                    "messageType": "Alert",
                    "areaDesc": "Test Area 1",
                },
            },
            {
                "id": "alert2",
                "properties": {
                    "headline": "Test Alert 2",
                    "description": "Description 2",
                    "instruction": "Instruction 2",
                    "severity": "Severe",
                    "event": "Test Event 2",
                    "effective": "2024-01-01T00:00:00Z",
                    "expires": "2024-01-02T00:00:00Z",
                    "status": "Actual",
                    "messageType": "Alert",
                    "areaDesc": "Test Area 2",
                },
            },
        ]
    }

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 2
    assert new_count == 2  # Both alerts are new
    assert updated_count == 0  # No alerts were updated
    assert processed_alerts[0]["headline"] == "Test Alert 1"
    assert processed_alerts[0]["severity"] == "Moderate"
    assert processed_alerts[1]["headline"] == "Test Alert 2"
    assert processed_alerts[1]["severity"] == "Severe"


def test_process_alerts_empty(weather_service):
    """Test processing empty alerts data."""
    alerts_data: dict = {"features": []}

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 0
    assert new_count == 0
    assert updated_count == 0


def test_process_alerts_missing_properties(weather_service):
    """Test processing alerts data with missing properties."""
    alerts_data = {
        "features": [
            {
                "id": "alert1",
                "properties": {
                    # Missing most properties
                    "headline": "Test Alert"
                },
            }
        ]
    }

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 1
    assert new_count == 1
    assert updated_count == 0
    assert processed_alerts[0]["headline"] == "Test Alert"
    # Check default values for missing properties
    assert processed_alerts[0]["description"] == "No description available"
    assert processed_alerts[0]["instruction"] == ""
    assert processed_alerts[0]["severity"] == "Unknown"
    assert processed_alerts[0]["event"] == "Unknown Event"
