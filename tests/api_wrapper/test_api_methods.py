"""Tests for NoaaApiWrapper API methods functionality."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.api_wrapper import NoaaApiWrapper

# Sample test data
SAMPLE_POINT_DATA = {
    "properties": {
        "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
        "forecastGridData": "https://api.weather.gov/gridpoints/PHI/31,70",
        "observationStations": "https://api.weather.gov/gridpoints/PHI/31,70/stations",
        "county": "https://api.weather.gov/zones/county/PAC101",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
        "timeZone": "America/New_York",
        "radarStation": "KDIX",
    }
}


# Create UnexpectedStatus class for testing
class MockUnexpectedStatus(Exception):
    def __init__(self, status_code, content=None):
        self.status_code = status_code
        self.content = content
        super().__init__(f"Unexpected status code: {status_code}")


@pytest.fixture
def api_wrapper():
    """Create a NoaaApiWrapper instance without caching."""
    with (
        patch("accessiweather.api.nws_wrapper.NwsApiWrapper") as mock_nws,
        patch("accessiweather.api.openmeteo_wrapper.OpenMeteoApiWrapper") as mock_openmeteo,
    ):

        # Create mock instances with proper attributes
        mock_nws_instance = MagicMock()
        mock_nws_instance.client = MagicMock()
        mock_nws_instance.client._headers = {"User-Agent": "TestClient (test@example.com)"}
        mock_nws_instance.cache = None
        mock_nws_instance._generate_cache_key = MagicMock(return_value="test_cache_key")
        mock_nws_instance._get_cached_or_fetch = MagicMock()
        mock_nws_instance._make_api_request = MagicMock()
        mock_nws_instance._transform_point_data = MagicMock()
        mock_nws_instance._rate_limit = MagicMock()
        mock_nws_instance._handle_rate_limit = MagicMock()
        mock_nws_instance._handle_client_error = MagicMock()
        mock_nws_instance.get_point_data = MagicMock()
        mock_nws_instance.last_request_time = None
        mock_nws_instance.max_retries = 3
        mock_nws_instance.retry_initial_wait = 5.0
        mock_nws_instance.retry_backoff = 2.0
        mock_nws.return_value = mock_nws_instance

        mock_openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = mock_openmeteo_instance

        wrapper = NoaaApiWrapper(
            user_agent="TestClient", contact_info="test@example.com", enable_caching=False
        )

        # Ensure the wrapper has the expected attributes
        wrapper.nws_wrapper = mock_nws_instance
        wrapper.openmeteo_wrapper = mock_openmeteo_instance

        return wrapper


@pytest.fixture
def cached_api_wrapper():
    """Create a NoaaApiWrapper instance with caching enabled."""
    with (
        patch("accessiweather.api.nws_wrapper.NwsApiWrapper") as mock_nws,
        patch("accessiweather.api.openmeteo_wrapper.OpenMeteoApiWrapper") as mock_openmeteo,
    ):

        # Create mock cache
        mock_cache = MagicMock()
        mock_cache.default_ttl = 300

        # Create mock instances with proper attributes
        mock_nws_instance = MagicMock()
        mock_nws_instance.client = MagicMock()
        mock_nws_instance.client._headers = {"User-Agent": "TestClient (test@example.com)"}
        mock_nws_instance.cache = mock_cache
        mock_nws_instance._generate_cache_key = MagicMock(return_value="test_cache_key")
        mock_nws_instance._get_cached_or_fetch = MagicMock()
        mock_nws_instance._make_api_request = MagicMock()
        mock_nws_instance._transform_point_data = MagicMock()
        mock_nws_instance._rate_limit = MagicMock()
        mock_nws_instance._handle_rate_limit = MagicMock()
        mock_nws_instance._handle_client_error = MagicMock()
        mock_nws_instance.get_point_data = MagicMock()
        mock_nws_instance.last_request_time = None
        mock_nws_instance.max_retries = 3
        mock_nws_instance.retry_initial_wait = 5.0
        mock_nws_instance.retry_backoff = 2.0
        mock_nws.return_value = mock_nws_instance

        mock_openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = mock_openmeteo_instance

        wrapper = NoaaApiWrapper(
            user_agent="TestClient",
            contact_info="test@example.com",
            enable_caching=True,
            cache_ttl=300,
        )

        # Ensure the wrapper has the expected attributes
        wrapper.nws_wrapper = mock_nws_instance
        wrapper.openmeteo_wrapper = mock_openmeteo_instance

        return wrapper


@pytest.mark.unit
def test_identify_location_type_county(api_wrapper):
    """Test identifying county location type."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {
                "county": "https://api.weather.gov/zones/county/PAC101",
                "forecastZone": "https://api.weather.gov/zones/forecast/PAZ103",
                "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            }
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "county"
        assert location_id == "PAC101"
        mock_get_point.assert_called_once_with(lat, lon, force_refresh=False)


@pytest.mark.unit
def test_get_forecast_success(api_wrapper):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0

    # Sample forecast data that would be returned from the forecast URL
    sample_forecast_data = {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "name": "Tonight",
                    "temperature": 45,
                    "temperatureUnit": "F",
                    "windSpeed": "5 mph",
                    "windDirection": "NW",
                    "shortForecast": "Clear",
                    "detailedForecast": "Clear skies tonight.",
                }
            ]
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
                    "gridId": "PHI",
                    "gridX": 31,
                    "gridY": 70,
                }
            }

            # Mock forecast data fetch
            mock_fetch_url.return_value = sample_forecast_data

            result = api_wrapper.get_forecast(lat, lon)

            assert result == sample_forecast_data
            mock_get_point.assert_called_once_with(lat, lon, force_refresh=False)
            mock_fetch_url.assert_called_once_with(
                "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
            )


@pytest.mark.unit
def test_get_hourly_forecast_success(api_wrapper):
    """Test getting hourly forecast data successfully."""
    lat, lon = 40.0, -75.0

    # Sample hourly forecast data that would be returned from the hourly forecast URL
    sample_hourly_forecast_data = {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "startTime": "2024-01-15T18:00:00-05:00",
                    "temperature": 45,
                    "temperatureUnit": "F",
                    "windSpeed": "5 mph",
                    "windDirection": "NW",
                    "shortForecast": "Clear",
                }
            ]
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with hourly forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
                    "gridId": "PHI",
                    "gridX": 31,
                    "gridY": 70,
                }
            }

            # Mock hourly forecast data fetch
            mock_fetch_url.return_value = sample_hourly_forecast_data

            result = api_wrapper.get_hourly_forecast(lat, lon)

            assert result == sample_hourly_forecast_data
            mock_get_point.assert_called_once_with(lat, lon, force_refresh=False)
            mock_fetch_url.assert_called_once_with(
                "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
            )


@pytest.mark.unit
def test_get_forecast_error_handling(api_wrapper):
    """Test error handling in get_forecast method."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
                    "gridId": "PHI",
                    "gridX": 31,
                    "gridY": 70,
                }
            }

            # Mock fetch URL to raise an exception
            mock_fetch_url.side_effect = Exception("Network error")

            with pytest.raises(NoaaApiError) as exc_info:
                api_wrapper.get_forecast(lat, lon)

            assert "Unexpected error getting forecast" in str(exc_info.value)
            assert exc_info.value.url == "https://api.weather.gov/gridpoints/PHI/31,70/forecast"


@pytest.mark.unit
def test_get_hourly_forecast_error_handling(api_wrapper):
    """Test error handling in get_hourly_forecast method."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with hourly forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
                    "gridId": "PHI",
                    "gridX": 31,
                    "gridY": 70,
                }
            }

            # Mock fetch URL to raise an exception
            mock_fetch_url.side_effect = Exception("Network error")

            with pytest.raises(ApiClientError) as exc_info:
                api_wrapper.get_hourly_forecast(lat, lon)

            assert "Unable to retrieve hourly forecast data" in str(exc_info.value)


@pytest.mark.unit
def test_identify_location_type_forecast_zone(api_wrapper):
    """Test identifying forecast zone location type."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {
                "forecastZone": "https://api.weather.gov/zones/forecast/PAZ103",
                "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            }
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "forecast"
        assert location_id == "PAZ103"


@pytest.mark.unit
def test_identify_location_type_fire_zone(api_wrapper):
    """Test identifying fire weather zone location type."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {
                "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            }
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "fire"
        assert location_id == "PAZ103"


@pytest.mark.unit
def test_identify_location_type_state_fallback(api_wrapper):
    """Test falling back to state when no specific zone is found."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {
            "properties": {"relativeLocation": {"properties": {"state": "PA"}}}
        }

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type == "state"
        assert location_id == "PA"


@pytest.mark.unit
def test_identify_location_type_none(api_wrapper):
    """Test when location type cannot be determined."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = {"properties": {}}

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type is None
        assert location_id is None


@pytest.mark.unit
def test_identify_location_type_error_handling(api_wrapper):
    """Test error handling in identify_location_type."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.side_effect = Exception("API error")

        location_type, location_id = api_wrapper.identify_location_type(lat, lon)

        assert location_type is None
        assert location_id is None


@pytest.mark.unit
def test_get_alerts_direct_success(api_wrapper):
    """Test successful direct alerts retrieval."""
    url = "https://api.weather.gov/alerts/active?zone=PAC101"
    mock_response = {
        "features": [
            {
                "id": "alert1",
                "properties": {"headline": "Test Alert", "description": "Test alert description"},
            }
        ]
    }

    with patch.object(api_wrapper, "_fetch_url") as mock_fetch:
        mock_fetch.return_value = mock_response

        result = api_wrapper.get_alerts_direct(url)

        assert result == mock_response
        mock_fetch.assert_called_once_with(url)


@pytest.mark.unit
def test_get_alerts_direct_with_caching(cached_api_wrapper):
    """Test direct alerts retrieval with caching."""
    url = "https://api.weather.gov/alerts/active?zone=PAC101"
    mock_response = {
        "features": [
            {
                "id": "alert1",
                "properties": {"headline": "Test Alert", "description": "Test alert description"},
            }
        ]
    }

    with patch.object(cached_api_wrapper, "_fetch_url") as mock_fetch:
        mock_fetch.return_value = mock_response

        # First call should fetch
        result1 = cached_api_wrapper.get_alerts_direct(url)
        assert result1 == mock_response
        mock_fetch.assert_called_once_with(url)

        # Second call should use cache
        mock_fetch.reset_mock()
        result2 = cached_api_wrapper.get_alerts_direct(url)
        assert result2 == mock_response
        mock_fetch.assert_not_called()


@pytest.mark.unit
def test_get_alerts_direct_error_handling(api_wrapper):
    """Test error handling in get_alerts_direct."""
    url = "https://api.weather.gov/alerts/active?zone=PAC101"

    with patch.object(api_wrapper, "_fetch_url") as mock_fetch:
        mock_fetch.side_effect = Exception("Network error")

        with pytest.raises(Exception) as excinfo:
            api_wrapper.get_alerts_direct(url)

        assert "Unable to retrieve alerts from URL" in str(excinfo.value)


@pytest.mark.unit
def test_get_alerts_with_county_zone(api_wrapper):
    """Test get_alerts with county zone identification."""
    lat, lon = 40.0, -75.0
    mock_response = {
        "features": [
            {
                "id": "alert1",
                "properties": {"headline": "Test Alert", "description": "Test alert description"},
            }
        ]
    }

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_identify.return_value = ("county", "PAC101")
            mock_request.return_value = mock_response

            result = api_wrapper.get_alerts(lat, lon, precise_location=True)

            assert result == mock_response
            mock_identify.assert_called_once_with(lat, lon, force_refresh=False)
            mock_request.assert_called_once()


@pytest.mark.unit
def test_get_alerts_with_state_fallback(api_wrapper):
    """Test get_alerts with state fallback when precise_location=False."""
    lat, lon = 40.0, -75.0
    mock_response = {
        "features": [
            {
                "id": "alert1",
                "properties": {"headline": "Test Alert", "description": "Test alert description"},
            }
        ]
    }

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        with patch.object(api_wrapper, "_fetch_url") as mock_fetch:
            mock_identify.return_value = ("state", "PA")
            mock_fetch.return_value = mock_response

            result = api_wrapper.get_alerts(lat, lon, precise_location=False)

            assert result == mock_response
            mock_identify.assert_called_once_with(lat, lon, force_refresh=False)
            expected_url = f"{api_wrapper.BASE_URL}/alerts/active?area=PA"
            mock_fetch.assert_called_once_with(expected_url)


@pytest.mark.unit
def test_get_alerts_with_point_radius_fallback(api_wrapper):
    """Test get_alerts with point-radius fallback when location cannot be determined."""
    lat, lon = 40.0, -75.0
    radius = 50
    mock_response = {
        "features": [
            {
                "id": "alert1",
                "properties": {"headline": "Test Alert", "description": "Test alert description"},
            }
        ]
    }

    with patch.object(api_wrapper, "identify_location_type") as mock_identify:
        with patch.object(api_wrapper, "_fetch_url") as mock_fetch:
            mock_identify.return_value = (None, None)
            mock_fetch.return_value = mock_response

            result = api_wrapper.get_alerts(lat, lon, radius=radius)

            assert result == mock_response
            mock_identify.assert_called_once_with(lat, lon, force_refresh=False)
            expected_url = f"{api_wrapper.BASE_URL}/alerts/active?point={lat},{lon}&radius={radius}"
            mock_fetch.assert_called_once_with(expected_url)
