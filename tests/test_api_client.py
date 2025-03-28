"""Tests for the NOAA API client"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
import requests

from accessiweather.api_client import NoaaApiClient


@pytest.fixture
def mock_response():
    """Create a mock response object"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"mock": "data"})
    mock_resp.status_code = 200
    return mock_resp


@pytest.fixture
def api_client():
    """Create an instance of the NoaaApiClient"""
    return NoaaApiClient(user_agent="Test User Agent")


@pytest.fixture
def api_client_with_contact():
    """Create an instance of the NoaaApiClient with contact information"""
    return NoaaApiClient(user_agent="Test User Agent", contact_info="test@example.com")


class TestNoaaApiClient:
    """Test suite for NoaaApiClient"""

    def test_init(self, api_client):
        """Test client initialization without contact info"""
        assert api_client.user_agent == "Test User Agent"
        assert api_client.headers == {
            "User-Agent": "Test User Agent", 
            "Accept": "application/geo+json"
        }
    
    def test_init_with_contact(self, api_client_with_contact):
        """Test client initialization with contact info"""
        assert api_client_with_contact.user_agent == "Test User Agent"
        assert api_client_with_contact.contact_info == "test@example.com"
        assert api_client_with_contact.headers == {
            "User-Agent": "Test User Agent (test@example.com)", 
            "Accept": "application/geo+json"
        }

    @patch("accessiweather.api_client.requests.get")
    def test_get_point_data(self, mock_get, api_client, mock_response):
        """Test retrieving point data"""
        # Configure mock response with a proper status code
        mock_response.status_code = 200
        mock_response.json.return_value = {"properties": {"forecast": "test_forecast_url"}}
        mock_get.return_value = mock_response
        
        # Call the method
        data = api_client.get_point_data(35.0, -80.0)
        
        # Verify the result
        assert data["properties"]["forecast"] == "test_forecast_url"
        assert mock_get.call_count == 1
        mock_get.assert_called_with(
            "https://api.weather.gov/points/35.0,-80.0", 
            headers=api_client.headers, 
            params=None
        )

    @patch("accessiweather.api_client.requests.get")
    def test_get_forecast(self, mock_get, api_client, mock_response):
        """Test retrieving forecast data"""
        # For the point data request
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/GSP/112,57/forecast"
            }
        })
        
        # For the forecast request
        forecast_mock = mock_response
        forecast_mock.status_code = 200
        
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

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts(self, mock_get, api_client, mock_response):
        """Test retrieving alerts"""
        # Create point data mock response
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={
            "properties": {
                "relativeLocation": {
                    "properties": {
                        "state": "NC"
                    }
                }
            }
        })
        point_mock.status_code = 200
        
        # Create alerts mock response
        alerts_mock = mock_response
        alerts_mock.status_code = 200
        
        # Set up the side effects for consecutive calls
        mock_get.side_effect = [point_mock, alerts_mock]
        
        # Call the method
        data = api_client.get_alerts(35.0, -80.0, radius=50)
        
        # Verify the result
        assert data == {"mock": "data"}
        assert mock_get.call_count == 2
        
        # Check calls
        calls = mock_get.call_args_list
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"  # Point data request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"      # Alerts request
        assert calls[1][1]["params"] == {"area": "NC"}                       # State-based filtering

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_county_fallback(self, mock_get, api_client, mock_response):
        """Test retrieving alerts with county fallback for state determination"""
        # Create point data mock response with no relativeLocation but with county
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={
            "properties": {
                "county": "https://api.weather.gov/zones/county/TXC141"
            }
        })
        point_mock.status_code = 200
        
        # Create alerts mock response
        alerts_mock = mock_response
        alerts_mock.status_code = 200
        
        # Set up the side effects for consecutive calls
        mock_get.side_effect = [point_mock, alerts_mock]
        
        # Call the method
        data = api_client.get_alerts(35.0, -80.0, radius=50)
        
        # Verify the result
        assert data == {"mock": "data"}
        assert mock_get.call_count == 2
        
        # Check calls
        calls = mock_get.call_args_list
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"  # Point data request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"      # Alerts request
        assert calls[1][1]["params"] == {"area": "TX"}                       # State-based filtering

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_no_state(self, mock_get, api_client, mock_response):
        """Test retrieving alerts when state cannot be determined"""
        # Create point data mock response with no state information
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={
            "properties": {}
        })
        point_mock.status_code = 200
        
        # Create alerts mock response with features
        alerts_mock = mock_response
        alerts_mock.status_code = 200
        alerts_mock.json = MagicMock(return_value={"features": [{"id": "test"}]})
        
        # Set up the side effects for consecutive calls
        mock_get.side_effect = [point_mock, alerts_mock]
        
        # Call the method
        data = api_client.get_alerts(35.0, -80.0, radius=50)
        
        # We should get a result with the point-radius parameters
        assert mock_get.call_count == 2
        
        # Check calls
        calls = mock_get.call_args_list
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"  # Point data request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"      # Alerts request
        
        # Ensure we're using point-radius search parameters
        params = calls[1][1]["params"]
        assert "point" in params
        assert "radius" in params
        assert params["point"] == "35.0,-80.0"
        assert params["radius"] == "50"

    @patch("accessiweather.api_client.NoaaApiClient.get_point_data")
    @patch("accessiweather.api_client.NoaaApiClient._make_request")
    def test_get_alerts_michigan_location(self, mock_make_request, mock_get_point_data):
        """Test retrieving alerts for a Michigan location (simulating Lumberton Township)"""
        # Set up mock for get_point_data
        mock_get_point_data.return_value = {
            "properties": {
                "relativeLocation": {
                    "properties": {
                        "state": "MI",
                        "city": "Lumberton Township"
                    }
                }
            }
        }
        
        # Set up mock for _make_request
        mock_make_request.return_value = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.1234",
                    "properties": {
                        "event": "Winter Weather Advisory",
                        "headline": "Winter Weather Advisory for Lumberton Township, MI",
                        "severity": "Moderate"
                    }
                }
            ]
        }
        
        # Create client and call the method
        client = NoaaApiClient(user_agent="Test User Agent")
        data = client.get_alerts(43.1, -86.3, radius=25)
        
        # Verify the mocks were called as expected
        mock_get_point_data.assert_called_once_with(43.1, -86.3)
        
        # Check that the state parameter was correctly extracted and used
        assert mock_make_request.call_count == 1
        call_args = mock_make_request.call_args
        assert call_args[0][0] == "https://api.weather.gov/alerts/active"
        assert call_args[1]["params"] == {"area": "MI"}
        
        # Check that the response is properly processed
        assert isinstance(data, dict)
        assert "features" in data
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["headline"] == "Winter Weather Advisory for Lumberton Township, MI"

    @patch("accessiweather.api_client.requests.get")
    def test_get_discussion(self, mock_get, api_client):
        """Test retrieving forecast discussion"""
        # Mock responses for the three API calls
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.json.return_value = {
            "properties": {
                "gridId": "ABC"
            }
        }
        
        products_mock = MagicMock()
        products_mock.status_code = 200
        products_mock.json.return_value = {
            "@graph": [{
                "id": "ABC-AFD-202503121200"
            }]
        }
        
        discussion_mock = MagicMock()
        discussion_mock.status_code = 200
        discussion_mock.json.return_value = {
            "productText": "Test forecast discussion text"
        }
        
        # Set up the side effects for consecutive calls
        mock_get.side_effect = [point_mock, products_mock, discussion_mock]
        
        # Call the method with lat/lon parameters
        data = api_client.get_discussion(35.0, -80.0)
        
        # Verify the result
        assert data == "Test forecast discussion text"
        assert mock_get.call_count == 3
        
        # Check calls
        calls = mock_get.call_args_list
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"
        assert calls[1][0][0] == "https://api.weather.gov/products/types/AFD/locations/ABC"
        assert calls[2][0][0] == "https://api.weather.gov/products/ABC-AFD-202503121200"

    @patch("accessiweather.api_client.requests.get")
    def test_api_error_handling(self, mock_get, api_client):
        """Test error handling in API requests"""
        # Mock a failed request with a requests.RequestException type
        mock_get.side_effect = requests.RequestException("Test connection error")
        
        # Test that the error is properly raised and converted to ConnectionError
        with pytest.raises(ConnectionError) as exc_info:
            api_client.get_point_data(35.0, -80.0)
        
        # Verify the error message
        assert "Failed to connect to NOAA API" in str(exc_info.value)

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_direct(self, mock_get, api_client, mock_response):
        """Test retrieving alerts with direct URL"""
        # Mock the response
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Call the method
        data = api_client.get_alerts_direct("https://api.weather.gov/alerts/active/area/NY")
        
        # Verify the result
        assert data == {"mock": "data"}
        mock_get.assert_called_once()

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_no_state_fallback(self, mock_get, api_client, mock_response):
        """Test retrieving alerts when no state can be determined"""
        # Create point data mock response with no state info
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.raise_for_status = MagicMock()
        # This response is missing the state information
        point_mock.json = MagicMock(return_value={
            "properties": {
                "relativeLocation": {
                    "properties": {}
                }
            }
        })
        
        # Create alerts mock response
        alerts_mock = mock_response
        alerts_mock.status_code = 200
        
        # Set up the side effects for consecutive calls
        mock_get.side_effect = [point_mock, alerts_mock]
        
        # Call the method - this should fall back to point-radius search
        data = api_client.get_alerts(35.0, -80.0, radius=50)
        
        # Verify the result
        assert data == {"mock": "data"}
        assert mock_get.call_count == 2
        
        # Check calls
        calls = mock_get.call_args_list
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"  # Point data request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"      # Alerts request
        
        # Ensure we're using point-radius parameters since no state was found
        params = calls[1][1]["params"]
        assert "point" in params
        assert "radius" in params
        assert params["point"] == "35.0,-80.0"
        assert params["radius"] == "50"

    def test_request_uses_formatted_user_agent(self, monkeypatch):
        """Test that requests use the properly formatted User-Agent"""
        # Create a mock for requests.get
        mock_get = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"mock": "data"})
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Apply the monkeypatch
        monkeypatch.setattr("requests.get", mock_get)
        
        # Create client with contact info
        client = NoaaApiClient(user_agent="AccessiWeather", contact_info="test@example.com")
        
        # Make a request
        client.get_point_data(35.0, -80.0)
        
        # Verify the User-Agent header was properly formatted in the request
        args, kwargs = mock_get.call_args
        assert kwargs["headers"]["User-Agent"] == "AccessiWeather (test@example.com)"
