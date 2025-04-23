"""Tests for the WeatherService class."""

import pytest
from unittest.mock import MagicMock, patch

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
                "detailedForecast": "Sunny with a high near 75."
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
                "event": "Test Event"
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
        "short_range_full": "WPC Full Discussion"
    },
    "spc": {
        "day1_summary": "SPC Day 1 Summary",
        "day1_full": "SPC Full Discussion"
    },
    "attribution": "Data from NOAA/NWS"
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
        "spc": {"day1_summary": "SPC Summary"}
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
    
    with pytest.raises(ApiClientError) as exc_info:
        weather_service.get_forecast(lat, lon)
    
    assert "Unable to retrieve forecast data" in str(exc_info.value)
    mock_api_client.get_forecast.assert_called_once_with(lat, lon, force_refresh=False)

def test_get_alerts_success(weather_service, mock_api_client):
    """Test getting alerts data successfully."""
    lat, lon = 40.0, -75.0
    radius = 25
    precise_location = True
    
    result = weather_service.get_alerts(lat, lon, radius=radius, precise_location=precise_location)
    
    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(
        lat, lon, radius=radius, precise_location=precise_location, force_refresh=False
    )

def test_get_alerts_with_force_refresh(weather_service, mock_api_client):
    """Test getting alerts data with force_refresh=True."""
    lat, lon = 40.0, -75.0
    radius = 25
    precise_location = True
    
    result = weather_service.get_alerts(
        lat, lon, radius=radius, precise_location=precise_location, force_refresh=True
    )
    
    assert result == SAMPLE_ALERTS_DATA
    mock_api_client.get_alerts.assert_called_once_with(
        lat, lon, radius=radius, precise_location=precise_location, force_refresh=True
    )

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
    
    assert "Unable to retrieve discussion data" in str(exc_info.value)
    mock_api_client.get_discussion.assert_called_once()

def test_get_national_forecast_data_success(weather_service):
    """Test getting national forecast data successfully."""
    # Mock the national_discussion_scraper module
    with patch("accessiweather.services.national_discussion_scraper.get_national_discussion_summaries") as mock_scraper:
        mock_scraper.return_value = SAMPLE_NATIONAL_DISCUSSION_DATA
        
        result = weather_service.get_national_forecast_data()
        
        assert result == {"national_discussion_summaries": SAMPLE_NATIONAL_DISCUSSION_DATA}
        mock_scraper.assert_called_once()

def test_get_national_forecast_data_error(weather_service):
    """Test getting national forecast data when scraper raises an error."""
    with patch("accessiweather.services.national_discussion_scraper.get_national_discussion_summaries") as mock_scraper:
        mock_scraper.side_effect = Exception("Scraper Error")
        
        with pytest.raises(ApiClientError) as exc_info:
            weather_service.get_national_forecast_data()
        
        assert "Unable to retrieve nationwide forecast data" in str(exc_info.value)
        mock_scraper.assert_called_once()

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
                    "areaDesc": "Test Area 1"
                }
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
                    "areaDesc": "Test Area 2"
                }
            }
        ]
    }
    
    processed_alerts = weather_service.process_alerts(alerts_data)
    
    assert len(processed_alerts) == 2
    assert processed_alerts[0]["headline"] == "Test Alert 1"
    assert processed_alerts[0]["severity"] == "Moderate"
    assert processed_alerts[1]["headline"] == "Test Alert 2"
    assert processed_alerts[1]["severity"] == "Severe"

def test_process_alerts_empty(weather_service):
    """Test processing empty alerts data."""
    alerts_data = {"features": []}
    
    processed_alerts = weather_service.process_alerts(alerts_data)
    
    assert len(processed_alerts) == 0

def test_process_alerts_missing_properties(weather_service):
    """Test processing alerts data with missing properties."""
    alerts_data = {
        "features": [
            {
                "id": "alert1",
                "properties": {
                    # Missing most properties
                    "headline": "Test Alert"
                }
            }
        ]
    }
    
    processed_alerts = weather_service.process_alerts(alerts_data)
    
    assert len(processed_alerts) == 1
    assert processed_alerts[0]["headline"] == "Test Alert"
    # Check default values for missing properties
    assert processed_alerts[0]["description"] == "No description available"
    assert processed_alerts[0]["instruction"] == ""
    assert processed_alerts[0]["severity"] == "Unknown"
    assert processed_alerts[0]["event"] == "Unknown Event"