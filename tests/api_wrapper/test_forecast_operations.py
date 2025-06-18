"""Tests for NoaaApiWrapper forecast operations functionality."""

import pytest

from accessiweather.api_client import ApiClientError, NoaaApiError

from .conftest import (
    FORECAST_URL,
    SAMPLE_FORECAST_DATA,
    SAMPLE_HOURLY_FORECAST_DATA,
    TEST_LAT,
    TEST_LON,
)


@pytest.mark.unit
def test_get_forecast_success(api_wrapper):
    """Test getting forecast data successfully."""
    lat, lon = TEST_LAT, TEST_LON

    # The mock is already configured in conftest.py to return SAMPLE_FORECAST_DATA
    result = api_wrapper.get_forecast(lat, lon)

    assert result == SAMPLE_FORECAST_DATA
    # The method is called without explicit force_refresh parameter via **kwargs
    api_wrapper.nws_wrapper.get_forecast.assert_called_once_with(lat, lon)


@pytest.mark.unit
def test_get_hourly_forecast_success(api_wrapper):
    """Test getting hourly forecast data successfully."""
    lat, lon = TEST_LAT, TEST_LON

    # The mock is already configured in conftest.py to return SAMPLE_HOURLY_FORECAST_DATA
    result = api_wrapper.get_hourly_forecast(lat, lon)

    assert result == SAMPLE_HOURLY_FORECAST_DATA
    # The method is called without explicit force_refresh parameter via **kwargs
    api_wrapper.nws_wrapper.get_hourly_forecast.assert_called_once_with(lat, lon)


@pytest.mark.unit
def test_get_forecast_error_handling(api_wrapper):
    """Test error handling in get_forecast method."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure both providers to fail so the exception propagates
    nws_error = NoaaApiError(
        message="Unexpected error getting forecast", error_type="UNKNOWN_ERROR", url=FORECAST_URL
    )
    api_wrapper.nws_wrapper.get_forecast.side_effect = nws_error
    api_wrapper.openmeteo_wrapper.get_forecast.side_effect = Exception("Fallback also failed")

    with pytest.raises(NoaaApiError) as exc_info:
        api_wrapper.get_forecast(lat, lon)

    assert "Unexpected error getting forecast" in str(exc_info.value)
    assert exc_info.value.url == FORECAST_URL


@pytest.mark.unit
def test_get_hourly_forecast_error_handling(api_wrapper):
    """Test error handling in get_hourly_forecast method."""
    lat, lon = TEST_LAT, TEST_LON

    # Configure both providers to fail so the exception propagates
    nws_error = ApiClientError("Unable to retrieve hourly forecast data: Network error")
    api_wrapper.nws_wrapper.get_hourly_forecast.side_effect = nws_error
    api_wrapper.openmeteo_wrapper.get_hourly_forecast.side_effect = Exception(
        "Fallback also failed"
    )

    with pytest.raises(ApiClientError) as exc_info:
        api_wrapper.get_hourly_forecast(lat, lon)

    assert "Unable to retrieve hourly forecast data" in str(exc_info.value)
