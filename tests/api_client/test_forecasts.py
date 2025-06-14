"""Tests for NoaaApiClient forecast functionality."""

from unittest.mock import patch

import pytest

from tests.api_client_test_utils import (
    SAMPLE_FORECAST_DATA,
    SAMPLE_HOURLY_FORECAST_DATA,
    SAMPLE_POINT_DATA,
    api_client,
    create_point_data_without_forecast,
)


def test_get_forecast_success(api_client):
    """Test getting forecast data successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # First call for point data
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,  # First call returns point data
            SAMPLE_FORECAST_DATA,  # Second call returns forecast data
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_forecast(lat, lon)

        assert result == SAMPLE_FORECAST_DATA
        assert mock_get.call_count == 2


def test_get_forecast_no_url(api_client):
    """Test getting forecast when point data doesn't contain forecast URL."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        bad_point_data = create_point_data_without_forecast()
        mock_get.return_value.json.return_value = bad_point_data
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_forecast(lat, lon)

        assert "Could not find forecast URL" in str(exc_info.value)


def test_get_hourly_forecast_success(api_client):
    """Test getting hourly forecast data successfully."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_HOURLY_FORECAST_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_hourly_forecast(lat, lon)

        assert result == SAMPLE_HOURLY_FORECAST_DATA
        assert mock_get.call_count == 2


def test_get_hourly_forecast_no_url(api_client):
    """Test getting hourly forecast when point data doesn't contain hourly forecast URL."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Create point data without hourly forecast URL
        bad_point_data = dict(SAMPLE_POINT_DATA)
        properties = {}
        properties_dict = SAMPLE_POINT_DATA.get("properties", {})
        if isinstance(properties_dict, dict):
            for key in list(properties_dict.keys()):
                if key != "forecastHourly":
                    properties[key] = properties_dict[key]
        bad_point_data["properties"] = properties

        mock_get.return_value.json.return_value = bad_point_data
        mock_get.return_value.raise_for_status.return_value = None

        with pytest.raises(ValueError) as exc_info:
            api_client.get_hourly_forecast(lat, lon)

        assert "Could not find hourly forecast URL" in str(exc_info.value)


@pytest.mark.unit
def test_get_forecast_url_extraction(api_client):
    """Test that forecast URL is extracted correctly from point data."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_FORECAST_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_forecast(lat, lon)

        # Verify the forecast URL was used correctly
        assert mock_get.call_count == 2
        forecast_call = mock_get.call_args_list[1]
        forecast_url = forecast_call[0][0]
        expected_url = SAMPLE_POINT_DATA["properties"]["forecast"]
        assert forecast_url == expected_url


@pytest.mark.unit
def test_get_hourly_forecast_url_extraction(api_client):
    """Test that hourly forecast URL is extracted correctly from point data."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_HOURLY_FORECAST_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        api_client.get_hourly_forecast(lat, lon)

        # Verify the hourly forecast URL was used correctly
        assert mock_get.call_count == 2
        forecast_call = mock_get.call_args_list[1]
        forecast_url = forecast_call[0][0]
        expected_url = SAMPLE_POINT_DATA["properties"]["forecastHourly"]
        assert forecast_url == expected_url


@pytest.mark.unit
def test_get_forecast_with_force_refresh(api_client):
    """Test getting forecast with force_refresh parameter."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_FORECAST_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_forecast(lat, lon, force_refresh=True)

        assert result == SAMPLE_FORECAST_DATA
        assert mock_get.call_count == 2


@pytest.mark.unit
def test_get_forecast_response_structure(api_client):
    """Test that forecast response has expected structure."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_FORECAST_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_forecast(lat, lon)

        # Verify response structure
        assert isinstance(result, dict)
        assert "properties" in result

        properties = result["properties"]
        assert "periods" in properties
        assert isinstance(properties["periods"], list)

        if properties["periods"]:
            period = properties["periods"][0]
            assert "name" in period
            assert "temperature" in period
            assert "shortForecast" in period


@pytest.mark.unit
def test_get_hourly_forecast_response_structure(api_client):
    """Test that hourly forecast response has expected structure."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.side_effect = [
            SAMPLE_POINT_DATA,
            SAMPLE_HOURLY_FORECAST_DATA,
        ]
        mock_get.return_value.raise_for_status.return_value = None

        result = api_client.get_hourly_forecast(lat, lon)

        # Verify response structure
        assert isinstance(result, dict)
        assert "properties" in result

        properties = result["properties"]
        assert "periods" in properties
        assert isinstance(properties["periods"], list)

        if properties["periods"]:
            period = properties["periods"][0]
            assert "number" in period
            assert "startTime" in period
            assert "endTime" in period
            assert "temperature" in period
            assert "shortForecast" in period


@pytest.mark.unit
def test_get_forecast_with_different_grid_points(api_client):
    """Test getting forecast for different grid points."""
    test_cases = [
        ("PHI", 50, 75),  # Philadelphia
        ("MLB", 30, 40),  # Melbourne, FL
        ("SEW", 125, 67),  # Seattle
    ]

    for grid_id, grid_x, grid_y in test_cases:
        lat, lon = 40.0, -75.0  # Coordinates don't matter for this test

        # Create custom point data for this grid
        custom_point_data = dict(SAMPLE_POINT_DATA)
        custom_point_data["properties"] = dict(SAMPLE_POINT_DATA["properties"])
        custom_point_data["properties"]["gridId"] = grid_id
        custom_point_data["properties"]["gridX"] = grid_x
        custom_point_data["properties"]["gridY"] = grid_y
        custom_point_data["properties"][
            "forecast"
        ] = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast"

        with patch("requests.get") as mock_get:
            mock_get.return_value.json.side_effect = [
                custom_point_data,
                SAMPLE_FORECAST_DATA,
            ]
            mock_get.return_value.raise_for_status.return_value = None

            result = api_client.get_forecast(lat, lon)

            assert result == SAMPLE_FORECAST_DATA
            # Verify the correct grid-specific URL was used
            forecast_call = mock_get.call_args_list[1]
            forecast_url = forecast_call[0][0]
            assert f"gridpoints/{grid_id}/{grid_x},{grid_y}/forecast" in forecast_url


@pytest.mark.unit
def test_forecast_error_propagation(api_client):
    """Test that forecast errors are properly propagated."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        # Point data succeeds, forecast fails
        from unittest.mock import MagicMock

        from requests.exceptions import HTTPError

        def side_effect(*args, **kwargs):
            if "/points/" in args[0]:
                # Return point data for first call
                response = MagicMock()
                response.json.return_value = SAMPLE_POINT_DATA
                response.raise_for_status.return_value = None
                return response
            elif "/gridpoints/" in args[0] and "/forecast" in args[0]:
                # Return a response that will raise HTTPError when raise_for_status is called
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_response.json.return_value = {"detail": "Internal Server Error"}

                # Create HTTPError that will be raised by raise_for_status
                http_error = HTTPError("500 Server Error")
                http_error.response = mock_response
                mock_response.raise_for_status.side_effect = http_error

                return mock_response
            else:
                # Fallback - should not happen in this test
                raise ValueError(f"Unexpected URL in test: {args[0]}")

        mock_get.side_effect = side_effect

        from accessiweather.api_client import NoaaApiError

        with pytest.raises(NoaaApiError) as exc_info:
            api_client.get_forecast(lat, lon)

        assert exc_info.value.error_type == NoaaApiError.SERVER_ERROR
