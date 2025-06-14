"""Tests for NoaaApiWrapper forecast functionality."""

from unittest.mock import patch

import pytest

from accessiweather.api_client import NoaaApiError
from tests.api_wrapper_test_utils import (
    SAMPLE_FORECAST_DATA,
    SAMPLE_POINT_DATA,
    MockUnexpectedStatus,
    api_wrapper,
)


@pytest.mark.unit
def test_get_forecast_success(api_wrapper):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_FORECAST_DATA

            result = api_wrapper.get_forecast(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            mock_get_point.assert_called_once_with(lat, lon)
            mock_request.assert_called_once()

            # Verify the correct forecast URL was used
            call_args = mock_request.call_args[0]
            assert "gridpoints/PHI/31,70/forecast" in call_args[0]


@pytest.mark.unit
def test_get_hourly_forecast_success(api_wrapper):
    """Test getting hourly forecast data successfully."""
    lat, lon = 40.0, -75.0

    # Sample hourly forecast data
    sample_hourly_data = {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "startTime": "2023-01-01T06:00:00-05:00",
                    "endTime": "2023-01-01T07:00:00-05:00",
                    "isDaytime": True,
                    "temperature": 45,
                    "temperatureUnit": "F",
                    "windSpeed": "10 mph",
                    "windDirection": "NW",
                    "shortForecast": "Mostly Sunny",
                }
            ]
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = sample_hourly_data

            result = api_wrapper.get_hourly_forecast(lat, lon)

            assert result == sample_hourly_data
            mock_get_point.assert_called_once_with(lat, lon)
            mock_request.assert_called_once()

            # Verify the correct hourly forecast URL was used
            call_args = mock_request.call_args[0]
            assert "gridpoints/PHI/31,70/forecast/hourly" in call_args[0]


@pytest.mark.unit
def test_get_forecast_error_handling(api_wrapper):
    """Test error handling in get_forecast method."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.side_effect = NoaaApiError("Forecast error", NoaaApiError.SERVER_ERROR)

            with pytest.raises(NoaaApiError):
                api_wrapper.get_forecast(lat, lon)

    # Test when point data retrieval fails
    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.side_effect = NoaaApiError("Point data error", NoaaApiError.CLIENT_ERROR)

        with pytest.raises(NoaaApiError):
            api_wrapper.get_forecast(lat, lon)


@pytest.mark.unit
def test_get_hourly_forecast_error_handling(api_wrapper):
    """Test error handling in get_hourly_forecast method."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.side_effect = NoaaApiError(
                "Hourly forecast error", NoaaApiError.SERVER_ERROR
            )

            with pytest.raises(NoaaApiError):
                api_wrapper.get_hourly_forecast(lat, lon)


@pytest.mark.unit
def test_get_forecast_with_missing_url(api_wrapper):
    """Test get_forecast when point data is missing forecast URL."""
    lat, lon = 40.0, -75.0

    # Point data without forecast URL
    point_data_no_forecast = {
        "properties": {
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
            "county": "https://api.weather.gov/zones/county/PAC101",
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = point_data_no_forecast

        with pytest.raises(NoaaApiError):
            api_wrapper.get_forecast(lat, lon)


@pytest.mark.unit
def test_get_hourly_forecast_with_missing_url(api_wrapper):
    """Test get_hourly_forecast when point data is missing hourly forecast URL."""
    lat, lon = 40.0, -75.0

    # Point data without hourly forecast URL
    point_data_no_hourly = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "county": "https://api.weather.gov/zones/county/PAC101",
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = point_data_no_hourly

        with pytest.raises(NoaaApiError):
            api_wrapper.get_hourly_forecast(lat, lon)


@pytest.mark.unit
def test_get_forecast_with_force_refresh(api_wrapper):
    """Test get_forecast with force_refresh parameter."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = SAMPLE_FORECAST_DATA

            # Test with force_refresh=True
            result = api_wrapper.get_forecast(lat, lon, force_refresh=True)

            assert result == SAMPLE_FORECAST_DATA
            # Verify force_refresh was passed to get_point_data
            mock_get_point.assert_called_once_with(lat, lon, force_refresh=True)


@pytest.mark.unit
def test_get_hourly_forecast_with_force_refresh(api_wrapper):
    """Test get_hourly_forecast with force_refresh parameter."""
    lat, lon = 40.0, -75.0

    sample_hourly_data = {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "startTime": "2023-01-01T06:00:00-05:00",
                    "temperature": 45,
                    "shortForecast": "Sunny",
                }
            ]
        }
    }

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = sample_hourly_data

            # Test with force_refresh=True
            result = api_wrapper.get_hourly_forecast(lat, lon, force_refresh=True)

            assert result == sample_hourly_data
            # Verify force_refresh was passed to get_point_data
            mock_get_point.assert_called_once_with(lat, lon, force_refresh=True)


@pytest.mark.unit
def test_get_forecast_with_invalid_coordinates(api_wrapper):
    """Test get_forecast with invalid coordinates."""
    lat, lon = 999.0, 999.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.side_effect = NoaaApiError("Invalid coordinates", NoaaApiError.CLIENT_ERROR)

        with pytest.raises(NoaaApiError):
            api_wrapper.get_forecast(lat, lon)


@pytest.mark.unit
def test_get_forecast_with_malformed_response(api_wrapper):
    """Test get_forecast with malformed API response."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            # Return malformed forecast data
            mock_request.return_value = {"invalid": "structure"}

            result = api_wrapper.get_forecast(lat, lon)

            # Should return the malformed data as-is
            assert result == {"invalid": "structure"}


@pytest.mark.unit
def test_get_forecast_with_empty_response(api_wrapper):
    """Test get_forecast with empty API response."""
    lat, lon = 40.0, -75.0

    with patch.object(api_wrapper, "get_point_data") as mock_get_point:
        mock_get_point.return_value = SAMPLE_POINT_DATA

        with patch.object(api_wrapper, "_make_api_request") as mock_request:
            mock_request.return_value = {}

            result = api_wrapper.get_forecast(lat, lon)

            assert result == {}


@pytest.mark.unit
def test_get_forecast_url_extraction(api_wrapper):
    """Test proper extraction of forecast URL from point data."""
    lat, lon = 40.0, -75.0

    # Test with different URL formats
    test_cases = [
        "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "https://api.weather.gov/gridpoints/MLB/50,50/forecast",
        "https://api.weather.gov/gridpoints/BOX/65,75/forecast",
    ]

    for forecast_url in test_cases:
        point_data = {
            "properties": {
                "forecast": forecast_url,
                "forecastHourly": forecast_url + "/hourly",
            }
        }

        with patch.object(api_wrapper, "get_point_data") as mock_get_point:
            mock_get_point.return_value = point_data

            with patch.object(api_wrapper, "_make_api_request") as mock_request:
                mock_request.return_value = SAMPLE_FORECAST_DATA

                api_wrapper.get_forecast(lat, lon)

                # Verify the correct URL was extracted and used
                call_args = mock_request.call_args[0]
                assert forecast_url.replace("https://api.weather.gov/", "") in call_args[0]
