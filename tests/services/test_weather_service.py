"""Tests for the WeatherService class."""

import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.services.weather_service import WeatherService

# Sample test data
SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny with a high near 75.",
            }
        ]
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "headline": "Test Alert",
                "description": "Test Description",
                "instruction": "Test Instruction",
                "severity": "Moderate",
                "event": "Test Event",
            }
        }
    ]
}

SAMPLE_DISCUSSION_TEXT = """
This is a sample forecast discussion.
Multiple lines of text.
With weather information.
"""

SAMPLE_NATIONAL_DISCUSSION_DATA = {
    "wpc": {
        "short_range_summary": "WPC Short Range Summary",
        "short_range_full": "WPC Full Discussion",
    },
    "spc": {"day1_summary": "SPC Day 1 Summary", "day1_full": "SPC Full Discussion"},
    "attribution": "Data from NOAA/NWS",
}


# Fixture to create a mocked NoaaApiClient
@pytest.fixture
def mock_api_client():
    client = MagicMock(spec=NoaaApiClient)
    # Set default return values
    client.get_forecast.return_value = SAMPLE_FORECAST_DATA
    client.get_alerts.return_value = SAMPLE_ALERTS_DATA
    client.get_discussion.return_value = SAMPLE_DISCUSSION_TEXT
    client.get_national_discussion_summary.return_value = {
        "wpc": {"short_range_summary": "WPC Summary"},
        "spc": {"day1_summary": "SPC Summary"},
    }
    return client


# Fixture to create a WeatherService instance with the mocked client
@pytest.fixture
def weather_service(mock_api_client):
    return WeatherService(mock_api_client)


def test_get_forecast_success(weather_service, mock_api_client):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_forecast(lat, lon)

    assert result == SAMPLE_FORECAST_DATA
    mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_forecast_with_force_refresh(weather_service, mock_api_client):
    """Test getting forecast data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_forecast(lat, lon, force_refresh=True)

    assert result == SAMPLE_FORECAST_DATA
    mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=True)


def test_get_forecast_error(weather_service, mock_api_client):
    """Test getting forecast data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_forecast.side_effect = Exception("API Error")

    # Also mock the OpenMeteo client to fail so fallback doesn't work
    with patch.object(weather_service.openmeteo_client, 'get_forecast') as mock_openmeteo:
        mock_openmeteo.side_effect = Exception("OpenMeteo Error")

        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_forecast(lat, lon)

        assert "NWS failed and Open-Meteo fallback failed" in str(exc_info.value)
        mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_alerts_success(weather_service, mock_api_client):
    """Test getting alerts data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_alerts(lat, lon)

    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_alerts_with_force_refresh(weather_service, mock_api_client):
    """Test getting alerts data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_alerts(lat, lon, force_refresh=True)

    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(lat, lon, force_refresh=True)


def test_get_alerts_error(weather_service, mock_api_client):
    """Test getting alerts data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_alerts.side_effect = Exception("API Error")

    with pytest.raises(ApiClientError) as exc_info:
        weather_service.get_alerts(lat, lon)

    assert "Unable to retrieve alerts data" in str(exc_info.value)
    mock_api_client.get_alerts.assert_called_once()


def test_get_discussion_success(weather_service, mock_api_client):
    """Test getting discussion data successfully."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_discussion(lat, lon)

    assert result == SAMPLE_DISCUSSION_TEXT
    mock_api_client.get_discussion.assert_called_once_with(lat, lon, force_refresh=False)


def test_get_discussion_with_force_refresh(weather_service, mock_api_client):
    """Test getting discussion data with force_refresh=True."""
    lat, lon = 40.0, -75.0

    result = weather_service.get_discussion(lat, lon, force_refresh=True)

    assert result == SAMPLE_DISCUSSION_TEXT
    mock_api_client.get_discussion.assert_called_once_with(lat, lon, force_refresh=True)


def test_get_discussion_error(weather_service, mock_api_client):
    """Test getting discussion data when API client raises an error."""
    lat, lon = 40.0, -75.0
    mock_api_client.get_discussion.side_effect = Exception("API Error")

    with pytest.raises(ApiClientError) as exc_info:
        weather_service.get_discussion(lat, lon)

    assert "Unable to retrieve forecast discussion data" in str(exc_info.value)
    mock_api_client.get_discussion.assert_called_once()


def test_get_national_forecast_data_success(weather_service):
    """Test getting national forecast data successfully."""
    # Mock the NationalDiscussionScraper.fetch_all_discussions method
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA
        assert weather_service.national_data_timestamp > 0


def test_get_national_forecast_data_with_cache(weather_service):
    """Test getting national forecast data from cache."""
    # Set up cache
    weather_service.national_data_cache = SAMPLE_NATIONAL_DISCUSSION_DATA
    weather_service.national_data_timestamp = time.time()

    # Mock the scraper to verify it's not called
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_not_called()


def test_get_national_forecast_data_with_force_refresh(weather_service):
    """Test getting national forecast data with force_refresh=True."""
    # Set up cache
    weather_service.national_data_cache = {"old": "data"}
    weather_service.national_data_timestamp = time.time()

    # Mock the scraper
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data(force_refresh=True)

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA


def test_get_national_forecast_data_with_expired_cache(weather_service):
    """Test getting national forecast data with expired cache."""
    # Set up expired cache (timestamp from 2 hours ago)
    weather_service.national_data_cache = {"old": "data"}
    weather_service.national_data_timestamp = time.time() - 7200  # 2 hours ago

    # Mock the scraper
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA

        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()

        # Verify cache was updated
        assert weather_service.national_data_cache == SAMPLE_NATIONAL_DISCUSSION_DATA


def test_get_national_forecast_data_error_no_cache(weather_service):
    """Test getting national forecast data when scraper raises an error and no cache exists."""
    # Ensure no cache
    weather_service.national_data_cache = None

    # Mock the scraper to raise an exception
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.side_effect = Exception("Scraper Error")

        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_national_forecast_data()

        assert "Unable to retrieve nationwide forecast data" in str(exc_info.value)
        mock_fetch.assert_called_once()


def test_get_national_forecast_data_error_with_cache(weather_service):
    """Test getting national forecast data when scraper raises an error but cache exists."""
    # Set up cache
    weather_service.national_data_cache = SAMPLE_NATIONAL_DISCUSSION_DATA
    weather_service.national_data_timestamp = time.time() - 7200  # Expired cache (2 hours ago)

    # Mock the scraper to raise an exception
    with patch.object(weather_service.national_scraper, "fetch_all_discussions") as mock_fetch:
        mock_fetch.side_effect = Exception("Scraper Error")

        # Should return cached data even though it's expired
        result = weather_service.get_national_forecast_data()

        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_fetch.assert_called_once()


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
