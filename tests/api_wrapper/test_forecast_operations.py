"""Tests for NoaaApiWrapper forecast operations functionality."""

from unittest.mock import patch

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiError

from .conftest import (
    FORECAST_URL,
    HOURLY_FORECAST_URL,
    SAMPLE_FORECAST_DATA,
    SAMPLE_HOURLY_FORECAST_DATA,
    TEST_LAT,
    TEST_LON,
)


@pytest.mark.unit
def test_get_forecast_success(api_wrapper):
    """Test getting forecast data successfully."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper.nws_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecast": FORECAST_URL,
                    "gridId": "PHI",
                    "gridX": 31,
                    "gridY": 70,
                }
            }

            # Mock forecast data fetch
            mock_fetch_url.return_value = SAMPLE_FORECAST_DATA

            result = api_wrapper.get_forecast(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            mock_get_point.assert_called_once_with(lat, lon, force_refresh=False)
            mock_fetch_url.assert_called_once_with(FORECAST_URL)


@pytest.mark.unit
def test_get_hourly_forecast_success(api_wrapper):
    """Test getting hourly forecast data successfully."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper.nws_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with hourly forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecastHourly": HOURLY_FORECAST_URL,
                    "gridId": "PHI",
                    "gridX": 31,
                    "gridY": 70,
                }
            }

            # Mock hourly forecast data fetch
            mock_fetch_url.return_value = SAMPLE_HOURLY_FORECAST_DATA

            result = api_wrapper.get_hourly_forecast(lat, lon)

            assert result == SAMPLE_HOURLY_FORECAST_DATA
            mock_get_point.assert_called_once_with(lat, lon, force_refresh=False)
            mock_fetch_url.assert_called_once_with(HOURLY_FORECAST_URL)


@pytest.mark.unit
def test_get_forecast_error_handling(api_wrapper):
    """Test error handling in get_forecast method."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper.nws_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecast": FORECAST_URL,
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
            assert exc_info.value.url == FORECAST_URL


@pytest.mark.unit
def test_get_hourly_forecast_error_handling(api_wrapper):
    """Test error handling in get_hourly_forecast method."""
    lat, lon = TEST_LAT, TEST_LON

    with patch.object(api_wrapper.nws_wrapper, "get_point_data") as mock_get_point:
        with patch.object(api_wrapper.nws_wrapper, "_fetch_url") as mock_fetch_url:
            # Mock point data with hourly forecast URL
            mock_get_point.return_value = {
                "properties": {
                    "forecastHourly": HOURLY_FORECAST_URL,
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
