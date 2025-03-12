"""Tests for the NOAA API client"""

import pytest
import json
from unittest.mock import patch, MagicMock

from noaa_weather_app.api_client import NoaaApiClient


@pytest.fixture
def mock_response():
    """Create a mock response object"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"mock": "data"})
    return mock_resp


@pytest.fixture
def api_client():
    """Create an instance of the NoaaApiClient"""
    return NoaaApiClient(user_agent="Test User Agent")


class TestNoaaApiClient:
    """Test suite for NoaaApiClient"""

    def test_init(self, api_client):
        """Test client initialization"""
        assert api_client.user_agent == "Test User Agent"
        assert api_client.headers == {
            "User-Agent": "Test User Agent", 
            "Accept": "application/geo+json"
        }

    @patch("noaa_weather_app.api_client.requests.get")
    def test_get_point_data(self, mock_get, api_client, mock_response):
        """Test retrieving point data"""
        mock_get.return_value = mock_response
        
        # Call the method
        data = api_client.get_point_data(35.0, -80.0)
        
        # Verify the result
        assert data == {"mock": "data"}
        mock_get.assert_called_once_with(
            "https://api.weather.gov/points/35.0,-80.0",
            headers=api_client.headers,
            params=None
        )

    @patch("noaa_weather_app.api_client.requests.get")
    def test_get_forecast(self, mock_get, api_client, mock_response):
        """Test retrieving forecast data"""
        # For the point data request
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/GSP/112,57/forecast"
            }
        })
        
        # For the forecast request
        forecast_mock = mock_response
        
        # Set up the side effects for consecutive calls
        mock_get.side_effect = [point_mock, forecast_mock]
        
        # Call the method
        data = api_client.get_forecast(35.0, -80.0)
        
        # Verify results
        assert data == {"mock": "data"}
        assert mock_get.call_count == 2
        
        # Check calls
        calls = mock_get.call_args_list
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"
        assert calls[1][0][0] == "https://api.weather.gov/gridpoints/GSP/112,57/forecast"

    @patch("noaa_weather_app.api_client.requests.get")
    def test_get_alerts(self, mock_get, api_client, mock_response):
        """Test retrieving alerts"""
        mock_get.return_value = mock_response
        
        # Call the method
        data = api_client.get_alerts(35.0, -80.0, radius=50)
        
        # Verify the result
        assert data == {"mock": "data"}
        mock_get.assert_called_once_with(
            "https://api.weather.gov/alerts/active",
            headers=api_client.headers,
            params={"point": "35.0,-80.0", "radius": 50}
        )

    @patch("noaa_weather_app.api_client.requests.get")
    def test_get_discussion(self, mock_get, api_client):
        """Test retrieving forecast discussion"""
        # Mock responses for the three API calls
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={"properties": {"gridId": "GSP"}})
        
        products_mock = MagicMock()
        products_mock.raise_for_status = MagicMock()
        products_mock.json = MagicMock(return_value={
            "@graph": [{
                "id": "GSP-AFD-202503121200"
            }]
        })
        
        discussion_mock = MagicMock()
        discussion_mock.raise_for_status = MagicMock()
        discussion_mock.json = MagicMock(return_value={
            "productText": "Test forecast discussion text"
        })
        
        # Set up side effects
        mock_get.side_effect = [point_mock, products_mock, discussion_mock]
        
        # Call the method
        result = api_client.get_discussion(35.0, -80.0)
        
        # Verify the result
        assert result == "Test forecast discussion text"
        assert mock_get.call_count == 3
        
        # Check calls
        calls = mock_get.call_args_list
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"
        assert calls[1][0][0] == "https://api.weather.gov/products/types/AFD/locations/GSP"
        assert calls[2][0][0] == "https://api.weather.gov/products/GSP-AFD-202503121200"

    @patch("noaa_weather_app.api_client.requests.get")
    def test_api_error_handling(self, mock_get, api_client):
        """Test error handling in API requests"""
        # Mock a failed request
        mock_get.side_effect = Exception("Test connection error")
        
        # Test that the error is properly raised
        with pytest.raises(ConnectionError) as exc_info:
            api_client.get_point_data(35.0, -80.0)
            
        assert "Failed to connect to NOAA API" in str(exc_info.value)
