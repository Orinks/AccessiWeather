t"""Tests for the NOAA API client"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from accessiweather.api_client import ApiClientError, NoaaApiClient

# Removed unused logging import


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
    return NoaaApiClient(
        user_agent="Test User Agent", contact_info="test@example.com"
    )


class TestNoaaApiClient:
    """Test suite for NoaaApiClient"""

    def test_init(self, api_client):
        """Test client initialization without contact info"""
        print("START: test_init")
        assert api_client.user_agent == "Test User Agent"
        assert api_client.headers == {
            "User-Agent": "Test User Agent",
            "Accept": "application/geo+json",
        }
        print("END: test_init")

    def test_init_with_contact(self, api_client_with_contact):
        """Test client initialization with contact info"""
        print("START: test_init_with_contact")
        assert api_client_with_contact.user_agent == "Test User Agent"
        assert api_client_with_contact.contact_info == "test@example.com"
        assert api_client_with_contact.headers == {
            "User-Agent": "Test User Agent (test@example.com)",
            "Accept": "application/geo+json",
        }
        print("END: test_init_with_contact")

    @patch("accessiweather.api_client.requests.get")
    def test_get_point_data(self, mock_get, api_client, mock_response):
        """Test retrieving point data"""
        print("START: test_get_point_data")
        # Configure mock response with a proper status code
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "properties": {"forecast": "test_forecast_url"}
        }
        mock_get.return_value = mock_response

        # Call the method
        data = api_client.get_point_data(35.0, -80.0)

        # Verify the result
        assert data["properties"]["forecast"] == "test_forecast_url"
        assert mock_get.call_count == 1
        mock_get.assert_called_with(
            "https://api.weather.gov/points/35.0,-80.0",
            headers=api_client.headers,
            params=None,
            timeout=10,  # Added timeout=10
        )
        print("END: test_get_point_data")

    @patch("accessiweather.api_client.requests.get")
    def test_get_forecast(self, mock_get, api_client, mock_response):
        """Test retrieving forecast data"""
        print("START: test_get_forecast")
        # For the point data request
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.raise_for_status = MagicMock()
        forecast_url = "https://api.weather.gov/gridpoints/GSP/112,57/forecast"
        point_mock.json = MagicMock(
            return_value={"properties": {"forecast": forecast_url}}
        )

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
        assert calls[1][0][0] == forecast_url
        print("END: test_get_forecast")

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts(self, mock_get, api_client, mock_response):
        """Test retrieving alerts"""
        print("START: test_get_alerts")
        # Create point data mock response
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(
            return_value={
                "properties": {
                    "relativeLocation": {"properties": {"state": "NC"}}
                }
            }
        )
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
        # Point data request
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"
        # Alerts request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"
        # State-based filtering
        assert calls[1][1]["params"] == {"area": "NC"}
        print("END: test_get_alerts")

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_county_fallback(
        self, mock_get, api_client, mock_response
    ):
        """Test alerts retrieval with county fallback for state."""
        print("START: test_get_alerts_county_fallback")
        # Create point data mock response with no relativeLocation
        # but with county
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(
            return_value={
                "properties": {
                    "county": "https://api.weather.gov/zones/county/TXC141"
                }
            }
        )
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
        # Point data request
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"
        # Alerts request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"
        # State-based filtering
        assert calls[1][1]["params"] == {"area": "TX"}
        print("END: test_get_alerts_county_fallback")

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_no_state(self, mock_get, api_client, mock_response):
        """Test retrieving alerts when state cannot be determined"""
        print("START: test_get_alerts_no_state")
        # Create point data mock response with no state information
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={"properties": {}})
        point_mock.status_code = 200

        # Create alerts mock response with features
        alerts_mock = mock_response
        alerts_mock.status_code = 200
        alerts_mock.json = MagicMock(
            return_value={"features": [{"id": "test"}]}
        )

        # Set up the side effects for consecutive calls
        mock_get.side_effect = [point_mock, alerts_mock]

        # Call the method (assign to _ as data is not used in assertions)
        _ = api_client.get_alerts(35.0, -80.0, radius=50)

        # We should get a result with the point-radius parameters
        assert mock_get.call_count == 2

        # Check calls
        calls = mock_get.call_args_list
        # Point data request
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"
        # Alerts request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"

        # Ensure we're using point-radius search parameters
        params = calls[1][1]["params"]
        assert "point" in params
        assert "radius" in params
        assert params["point"] == "35.0,-80.0"
        assert params["radius"] == "50"
        print("END: test_get_alerts_no_state")

    @patch("accessiweather.api_client.NoaaApiClient.get_point_data")
    @patch("accessiweather.api_client.NoaaApiClient._make_request")
    def test_get_alerts_michigan_location(
        self, mock_make_request, mock_get_point_data
    ):
        """Test retrieving alerts for a Michigan location (Lumberton)."""
        print("START: test_get_alerts_michigan_location")
        # Set up mock for get_point_data
        mock_get_point_data.return_value = {
            "properties": {
                "relativeLocation": {
                    "properties": {"state": "MI", "city": "Lumberton Township"}
                }
            }
        }

        # Set up mock for _make_request
        headline = "Winter Weather Advisory for Lumberton Township, MI"
        mock_make_request.return_value = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.1234",
                    "properties": {
                        "event": "Winter Weather Advisory",
                        "headline": headline,
                        "severity": "Moderate",
                    },
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
        assert data["features"][0]["properties"]["headline"] == headline
        print("END: test_get_alerts_michigan_location")

    @patch("accessiweather.api_client.requests.get")
    def test_get_discussion(self, mock_get, api_client):
        """Test retrieving forecast discussion"""
        print("START: test_get_discussion")
        # Mock responses for the three API calls
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.json.return_value = {"properties": {"gridId": "ABC"}}

        products_mock = MagicMock()
        products_mock.status_code = 200
        products_mock.json.return_value = {
            "@graph": [{"id": "ABC-AFD-202503121200"}]
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
        products_url = (
            "https://api.weather.gov/products/types/AFD/locations/ABC"
        )
        assert calls[1][0][0] == products_url
        discussion_url = (
            "https://api.weather.gov/products/ABC-AFD-202503121200"
        )
        assert calls[2][0][0] == discussion_url
        print("END: test_get_discussion")

    @patch("accessiweather.api_client.logger.error")  # Patch logger.error
    @patch("accessiweather.api_client.requests.get")
    def test_api_error_handling(self, mock_get, mock_logger_error, api_client):
        """Test error handling and suppress traceback for expected errors"""
        print("START: test_api_error_handling")
        # Mock a failed request with a requests.RequestException type
        mock_get.side_effect = requests.RequestException(
            "Test connection error"
        )

        # Test that the error is raised and converted to ApiClientError
        with pytest.raises(ApiClientError) as exc_info:
            api_client.get_point_data(35.0, -80.0)

        # Verify the error message (updated for retry logic)
        assert "Request failed after 1 retries" in str(exc_info.value)
        # Verify logger.error was called (suppressing traceback)
        mock_logger_error.assert_called_once()
        # Optional: Check arguments if needed for more specific verification
        # args, kwargs = mock_logger_error.call_args
        # assert "Network error during API request" in args[0]
        # assert kwargs.get('exc_info') is not True
        print("END: test_api_error_handling")

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_direct(self, mock_get, api_client, mock_response):
        """Test retrieving alerts with direct URL"""
        print("START: test_get_alerts_direct")
        # Mock the response
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Call the method
        alerts_url = "https://api.weather.gov/alerts/active/area/NY"
        data = api_client.get_alerts_direct(alerts_url)

        # Verify the result
        assert data == {"mock": "data"}
        mock_get.assert_called_once()
        print("END: test_get_alerts_direct")

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_no_state_fallback(
        self, mock_get, api_client, mock_response
    ):
        """Test retrieving alerts when no state can be determined"""
        print("START: test_get_alerts_no_state_fallback")
        # Create point data mock response with no state info
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.raise_for_status = MagicMock()
        # This response is missing the state information
        point_mock.json = MagicMock(
            return_value={
                "properties": {"relativeLocation": {"properties": {}}}
            }
        )

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
        # Point data request
        assert calls[0][0][0] == "https://api.weather.gov/points/35.0,-80.0"
        # Alerts request
        assert calls[1][0][0] == "https://api.weather.gov/alerts/active"

        # Ensure we're using point-radius parameters since no state was found
        params = calls[1][1]["params"]
        assert "point" in params
        assert "radius" in params
        assert params["point"] == "35.0,-80.0"
        assert params["radius"] == "50"
        print("END: test_get_alerts_no_state_fallback")

    def test_request_uses_formatted_user_agent(self, monkeypatch):
        """Test that requests use the properly formatted User-Agent"""
        print("START: test_request_uses_formatted_user_agent")
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
        client = NoaaApiClient(
            user_agent="AccessiWeather", contact_info="test@example.com"
        )

        # Make a request
        client.get_point_data(35.0, -80.0)

        # Verify the User-Agent header was properly formatted in the request
        args, kwargs = mock_get.call_args
        expected_ua = "AccessiWeather (test@example.com)"
        assert kwargs["headers"]["User-Agent"] == expected_ua
        print("END: test_request_uses_formatted_user_agent")
