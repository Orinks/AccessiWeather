"""Tests for the NOAA API client"""

from unittest.mock import MagicMock, patch

import unittest
from unittest.mock import MagicMock, patch
import requests
from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.weather_app import WeatherApp

class TestNoaaApiClient(unittest.TestCase):
    def setUp(self):
        self.api_client = NoaaApiClient(user_agent="Test User Agent")
        self.api_client_with_contact = NoaaApiClient(user_agent="Test User Agent", contact_info="test@example.com")

    def mock_response(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"mock": "data"})
        mock_resp.status_code = 200
        return mock_resp

    @patch("accessiweather.api_client.requests.get")
    def test_get_national_product_success(self, mock_get):
        """Test retrieving a national product (e.g., FXUS01 KWNH)"""
        product_type = "FXUS01"
        location = "KWNH"
        endpoint_url = f"https://api.weather.gov/products/types/{product_type}/locations/{location}"
        product_id = "202404160800-FXUS01-KWNH"
        mock_get.side_effect = [
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"@graph": [{"id": product_id}]}),
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"productText": "Sample forecast text"}),
                raise_for_status=MagicMock(),
            ),
        ]
        text = self.api_client.get_national_product(product_type, location)
        self.assertEqual(text, "Sample forecast text")
        self.assertEqual(mock_get.call_args_list[0][0][0], endpoint_url)
        self.assertIn(product_id, mock_get.call_args_list[1][0][0])

    @patch("accessiweather.api_client.requests.get")
    def test_get_national_product_no_data(self, mock_get):
        """Test handling when no national product is available"""
        product_type = "FXUS01"
        location = "KWNH"
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"@graph": []}),
            raise_for_status=MagicMock(),
        )
        text = self.api_client.get_national_product(product_type, location)
        self.assertIsNone(text)

    @patch.object(NoaaApiClient, "get_national_product")
    def test_get_national_forecast_data_aggregation(self, mock_get_national_product):
        """Test that get_national_forecast_data aggregates multiple products"""
        mock_get_national_product.side_effect = lambda typ, loc, force_refresh=False: f"{typ}-{loc}"
        data = self.api_client.get_national_forecast_data()
        self.assertEqual(data["wpc"]["short_range"], "FXUS01-KWNH")
        self.assertEqual(data["wpc"]["medium_range"], "FXUS06-KWNH")
        self.assertEqual(data["spc"]["day1"], "ACUS01-KWNS")
        # ...continue for other keys as in the implementation plan

    @patch("accessiweather.api_client.requests.get")
    def test_get_national_product_error(self, mock_get):
        """Test error handling when request fails"""
        mock_get.side_effect = requests.RequestException("Network error")
        text = self.api_client.get_national_product("FXUS01", "KWNH")
        self.assertIsNone(text)  # Should gracefully handle and return None


    """Test suite for NoaaApiClient"""

    def test_init(self):
        """Test client initialization without contact info"""
        self.assertEqual(self.api_client.user_agent, "Test User Agent")
        self.assertEqual(self.api_client.headers, {
            "User-Agent": "Test User Agent",
            "Accept": "application/geo+json",
        })

    def test_init_with_contact(self):
        """Test client initialization with contact info"""
        self.assertEqual(self.api_client_with_contact.user_agent, "Test User Agent")
        self.assertEqual(self.api_client_with_contact.contact_info, "test@example.com")
        self.assertIn("test@example.com", self.api_client_with_contact.headers["User-Agent"])
        self.assertEqual(self.api_client_with_contact.headers, {
            "User-Agent": "Test User Agent (test@example.com)",
            "Accept": "application/geo+json",
        })

    @patch("accessiweather.api_client.requests.get")
    def test_get_point_data(self, mock_get):
        """Test retrieving point data"""
        mock_response = self.mock_response()
        mock_response.status_code = 200
        mock_response.json.return_value = {"properties": {"forecast": "test_forecast_url"}}
        mock_get.return_value = mock_response

        data = self.api_client.get_point_data(35.0, -80.0)

        self.assertEqual(data["properties"]["forecast"], "test_forecast_url")
        self.assertEqual(mock_get.call_count, 1)
        mock_get.assert_called_with(
            "https://api.weather.gov/points/35.0,-80.0",
            headers=self.api_client.headers,
            params=None,
            timeout=10,
        )

    @patch("accessiweather.api_client.requests.get")
    def test_get_forecast(self, mock_get):
        """Test retrieving forecast data"""
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.raise_for_status = MagicMock()
        forecast_url = "https://api.weather.gov/gridpoints/GSP/112,57/forecast"
        point_mock.json = MagicMock(return_value={"properties": {"forecast": forecast_url}})

        forecast_mock = self.mock_response()
        forecast_mock.status_code = 200

        mock_get.side_effect = [point_mock, forecast_mock]

        data = self.api_client.get_forecast(35.0, -80.0)

        self.assertEqual(data, {"mock": "data"})
        self.assertEqual(mock_get.call_count, 2)
        calls = mock_get.call_args_list
        self.assertEqual(calls[0][0][0], "https://api.weather.gov/points/35.0,-80.0")
        self.assertEqual(calls[1][0][0], forecast_url)

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts(self, mock_get):
        """Test retrieving alerts"""
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(
            return_value={"properties": {"relativeLocation": {"properties": {"state": "NC"}}}}
        )
        point_mock.status_code = 200

        alerts_mock = self.mock_response()
        alerts_mock.status_code = 200

        mock_get.side_effect = [point_mock, alerts_mock]

        data = self.api_client.get_alerts(35.0, -80.0, radius=50)

        self.assertEqual(data, {"mock": "data"})
        self.assertEqual(mock_get.call_count, 2)
        calls = mock_get.call_args_list
        self.assertEqual(calls[0][0][0], "https://api.weather.gov/points/35.0,-80.0")
        self.assertEqual(calls[1][0][0], "https://api.weather.gov/alerts/active")
        self.assertEqual(calls[1][1]["params"], {"area": "NC"})

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_county_fallback(self, mock_get):
        """Test alerts retrieval with county fallback for state."""
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(
            return_value={"properties": {"county": "https://api.weather.gov/zones/county/TXC141"}}
        )
        point_mock.status_code = 200

        alerts_mock = self.mock_response()
        alerts_mock.status_code = 200

        mock_get.side_effect = [point_mock, alerts_mock]

        data = self.api_client.get_alerts(35.0, -80.0, radius=50)

        self.assertEqual(data, {"mock": "data"})
        self.assertEqual(mock_get.call_count, 2)
        calls = mock_get.call_args_list
        self.assertEqual(calls[0][0][0], "https://api.weather.gov/points/35.0,-80.0")
        self.assertEqual(calls[1][0][0], "https://api.weather.gov/alerts/active")
        self.assertEqual(calls[1][1]["params"], {"zone": "TXC141"})

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_no_state(self, mock_get):
        """Test retrieving alerts when state cannot be determined"""
        point_mock = MagicMock()
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(return_value={"properties": {}})
        point_mock.status_code = 200

        alerts_mock = self.mock_response()
        alerts_mock.status_code = 200
        alerts_mock.json = MagicMock(return_value={"features": [{"id": "test"}]})

        mock_get.side_effect = [point_mock, alerts_mock]

        _ = self.api_client.get_alerts(35.0, -80.0, radius=50)

        self.assertEqual(mock_get.call_count, 2)
        calls = mock_get.call_args_list
        self.assertEqual(calls[0][0][0], "https://api.weather.gov/points/35.0,-80.0")
        self.assertEqual(calls[1][0][0], "https://api.weather.gov/alerts/active")
        params = calls[1][1]["params"]
        self.assertIn("point", params)
        self.assertIn("radius", params)
        self.assertEqual(params["point"], "35.0,-80.0")
        self.assertEqual(params["radius"], "50")

    @patch("accessiweather.api_client.NoaaApiClient.get_point_data")
    @patch("accessiweather.api_client.NoaaApiClient._make_request")
    def test_get_alerts_michigan_location(self, mock_make_request, mock_get_point_data):
        """Test retrieving alerts for a Michigan location (Lumberton)."""
        mock_get_point_data.return_value = {
            "properties": {
                "relativeLocation": {"properties": {"state": "MI", "city": "Lumberton Township"}}
            }
        }
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
        data = self.api_client.get_alerts(43.1, -86.3, radius=25, force_refresh=True)
        mock_get_point_data.assert_called_once_with(43.1, -86.3, force_refresh=True)
        self.assertEqual(mock_make_request.call_count, 1)
        call_args = mock_make_request.call_args
        self.assertEqual(call_args[0][0], "https://api.weather.gov/alerts/active")
        self.assertEqual(call_args[1]["params"], {"area": "MI"})
        self.assertTrue(call_args[1]["force_refresh"])
        self.assertIsInstance(data, dict)
        self.assertIn("features", data)
        self.assertEqual(len(data["features"]), 1)
        self.assertEqual(data["features"][0]["properties"]["headline"], headline)

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_direct(self, mock_get):
        """Test retrieving alerts with direct URL"""
        mock_response = self.mock_response()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        alerts_url = "https://api.weather.gov/alerts/active/area/NY"
        data = self.api_client.get_alerts_direct(alerts_url)
        self.assertEqual(data, {"mock": "data"})
        mock_get.assert_called_once()

    @patch("accessiweather.api_client.requests.get")
    def test_get_alerts_no_state_fallback(self, mock_get):
        # Create point data mock response with no state info
        point_mock = MagicMock()
        point_mock.status_code = 200
        point_mock.raise_for_status = MagicMock()
        point_mock.json = MagicMock(
            return_value={"properties": {"relativeLocation": {"properties": {}}}}
        )
        alerts_mock = self.mock_response()
        alerts_mock.status_code = 200
        mock_get.side_effect = [point_mock, alerts_mock]
        data = self.api_client.get_alerts(35.0, -80.0, radius=50)
        self.assertEqual(data, {"mock": "data"})
        self.assertEqual(mock_get.call_count, 2)
        calls = mock_get.call_args_list
        self.assertEqual(calls[0][0][0], "https://api.weather.gov/points/35.0,-80.0")
        self.assertEqual(calls[1][0][0], "https://api.weather.gov/alerts/active")
        params = calls[1][1]["params"]
        self.assertIn("point", params)
        self.assertIn("radius", params)
        self.assertEqual(params["point"], "35.0,-80.0")
        self.assertEqual(params["radius"], "50")

    @patch("requests.get")
    def test_request_uses_formatted_user_agent(self, mock_get):
        """Test that requests use the properly formatted User-Agent"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"mock": "data"})
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        client = NoaaApiClient(user_agent="AccessiWeather", contact_info="test@example.com")
        client.get_point_data(35.0, -80.0)
        _, kwargs = mock_get.call_args
        expected_ua = "AccessiWeather (test@example.com)"
        self.assertEqual(kwargs["headers"]["User-Agent"], expected_ua)
