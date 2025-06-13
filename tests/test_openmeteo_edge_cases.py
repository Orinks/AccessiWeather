"""Edge case tests for Open-Meteo integration."""

from unittest.mock import patch

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.openmeteo_mapper import OpenMeteoMapper


@pytest.fixture
def openmeteo_client():
    """Create an OpenMeteoApiClient for testing."""
    return OpenMeteoApiClient()


@pytest.fixture
def mapper():
    """Create an OpenMeteoMapper for testing."""
    return OpenMeteoMapper()


# Geographic edge cases
@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,description",
    [
        (90.0, 0.0, "North Pole"),
        (-90.0, 0.0, "South Pole"),
        (0.0, 180.0, "International Date Line East"),
        (0.0, -180.0, "International Date Line West"),
        (0.0, 0.0, "Null Island (Equator/Prime Meridian)"),
        (71.0, -8.0, "Arctic Circle"),
        (-66.5, 0.0, "Antarctic Circle"),
        (23.5, 0.0, "Tropic of Cancer"),
        (-23.5, 0.0, "Tropic of Capricorn"),
    ],
)
def test_extreme_geographic_locations(openmeteo_client, lat, lon, description):
    """Test API calls with extreme geographic locations."""
    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = {
            "latitude": lat,
            "longitude": lon,
            "current": {"temperature_2m": 0.0, "time": "2024-01-01T12:00"},
            "current_units": {"temperature_2m": "°C"},
        }

        result = openmeteo_client.get_current_weather(lat, lon)

        assert result is not None
        assert result["latitude"] == lat
        assert result["longitude"] == lon


# Extreme weather data values
@pytest.mark.unit
def test_extreme_temperature_values(mapper):
    """Test mapping of extreme temperature values."""
    extreme_data = {
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": -89.2,  # Record low temperature (Antarctica)
            "relative_humidity_2m": 0,  # Extremely dry
            "weather_code": 0,
        },
        "current_units": {"temperature_2m": "°C"},
    }

    result = mapper.map_current_conditions(extreme_data)

    assert result["properties"]["temperature"]["value"] == -89.2
    assert result["properties"]["relativeHumidity"]["value"] == 0


@pytest.mark.unit
def test_extreme_wind_values(mapper):
    """Test mapping of extreme wind values."""
    extreme_data = {
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": 20.0,
            "wind_speed_10m": 408.0,  # Record wind speed (km/h)
            "wind_direction_10m": 359.9,  # Almost full circle
            "wind_gusts_10m": 500.0,  # Extreme gust
            "weather_code": 95,  # Thunderstorm
        },
        "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
    }

    result = mapper.map_current_conditions(extreme_data)

    assert result["properties"]["windSpeed"]["value"] == 408.0
    assert result["properties"]["windDirection"]["value"] == 359.9
    assert result["properties"]["windGust"]["value"] == 500.0


# Data type edge cases
@pytest.mark.unit
def test_zero_and_negative_values(mapper):
    """Test handling of zero and negative values."""
    data_with_zeros = {
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": 0.0,
            "relative_humidity_2m": 0,
            "wind_speed_10m": 0.0,
            "precipitation": 0.0,
            "pressure_msl": 0.0,  # Impossible but test edge case
            "weather_code": 0,
        },
        "current_units": {"temperature_2m": "°C"},
    }

    result = mapper.map_current_conditions(data_with_zeros)

    assert result["properties"]["temperature"]["value"] == 0.0
    assert result["properties"]["windSpeed"]["value"] == 0.0
    assert result["properties"]["barometricPressure"]["value"] == 0.0


@pytest.mark.unit
def test_very_small_decimal_values(mapper):
    """Test handling of very small decimal values."""
    precision_data = {
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": 0.001,
            "precipitation": 0.0001,
            "wind_speed_10m": 0.1,
            "weather_code": 1,
        },
        "current_units": {"temperature_2m": "°C"},
    }

    result = mapper.map_current_conditions(precision_data)

    assert result["properties"]["temperature"]["value"] == 0.001


# Time and date edge cases
@pytest.mark.unit
def test_leap_year_date_handling(mapper):
    """Test handling of leap year dates."""
    leap_year_data = {
        "daily": {
            "time": ["2024-02-29"],  # Leap year date
            "weather_code": [1],
            "temperature_2m_max": [20.0],
            "temperature_2m_min": [10.0],
        },
        "daily_units": {"temperature_2m_max": "°C"},
    }

    result = mapper.map_forecast(leap_year_data)

    assert len(result["properties"]["periods"]) == 2  # Day and night


@pytest.mark.unit
def test_year_boundary_dates(mapper):
    """Test handling of year boundary dates."""
    year_boundary_data = {
        "daily": {
            "time": ["2023-12-31", "2024-01-01"],
            "weather_code": [1, 2],
            "temperature_2m_max": [5.0, 8.0],
            "temperature_2m_min": [-5.0, -2.0],
        },
        "daily_units": {"temperature_2m_max": "°C"},
    }

    result = mapper.map_forecast(year_boundary_data)

    # Should handle gracefully, may have fewer periods due to missing data
    assert len(result["properties"]["periods"]) >= 2  # At least some periods


@pytest.mark.unit
def test_timezone_edge_cases(openmeteo_client):
    """Test handling of different timezone scenarios."""
    with patch.object(openmeteo_client, "_make_request") as mock_request:
        # Test with different timezone offsets
        timezone_data = {
            "latitude": 0.0,
            "longitude": 0.0,
            "utc_offset_seconds": 43200,  # +12 hours (extreme positive)
            "timezone": "Pacific/Kiritimati",
            "current": {"temperature_2m": 25.0, "time": "2024-01-01T12:00"},
            "current_units": {"temperature_2m": "°C"},
        }
        mock_request.return_value = timezone_data

        result = openmeteo_client.get_current_weather(0.0, 0.0)

        assert result["utc_offset_seconds"] == 43200


# Data completeness edge cases
@pytest.mark.unit
def test_sparse_data_arrays(mapper):
    """Test handling of arrays with missing data points."""
    sparse_data = {
        "hourly": {
            "time": ["2024-01-01T12:00", "2024-01-01T13:00", "2024-01-01T14:00"],
            "temperature_2m": [20.0, None, 22.0],  # Missing middle value
            "weather_code": [1, 2],  # Shorter array
            "wind_speed_10m": [10.0, 12.0, 14.0],
            "is_day": [1, 1, 1],
        },
        "hourly_units": {"temperature_2m": "°C"},
    }

    result = mapper.map_hourly_forecast(sparse_data)

    periods = result["properties"]["periods"]
    assert len(periods) == 3

    # Second period should handle None temperature gracefully
    assert periods[1]["temperature"] is None


@pytest.mark.unit
def test_mismatched_array_lengths(mapper):
    """Test handling of arrays with different lengths."""
    mismatched_data = {
        "daily": {
            "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "weather_code": [1, 2],  # Only 2 values for 3 days
            "temperature_2m_max": [20.0, 22.0, 24.0],
            "temperature_2m_min": [10.0],  # Only 1 value for 3 days
        },
        "daily_units": {"temperature_2m_max": "°C"},
    }

    result = mapper.map_forecast(mismatched_data)

    # Should handle gracefully without crashing
    assert "periods" in result["properties"]


# Weather code edge cases
@pytest.mark.unit
def test_unknown_weather_codes(mapper):
    """Test handling of unknown or invalid weather codes."""
    unknown_code_data = {
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": 20.0,
            "weather_code": 999,  # Unknown code
        },
        "current_units": {"temperature_2m": "°C"},
    }

    result = mapper.map_current_conditions(unknown_code_data)

    # Should not crash and provide some description
    assert "textDescription" in result["properties"]
    assert result["properties"]["textDescription"] is not None


# API limit edge cases
@pytest.mark.unit
def test_maximum_forecast_days(openmeteo_client):
    """Test requesting maximum allowed forecast days."""
    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = {"daily": {"time": []}}

        # Request more than API maximum
        openmeteo_client.get_forecast(40.0, -75.0, days=20)

        # Should be clamped to API maximum
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] == 16


@pytest.mark.unit
def test_maximum_hourly_forecast_hours(openmeteo_client):
    """Test requesting maximum allowed hourly forecast hours."""
    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = {"hourly": {"time": []}}

        # Request more than API maximum
        openmeteo_client.get_hourly_forecast(40.0, -75.0, hours=500)

        # Should be clamped to API maximum
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] == 384


# Unit conversion edge cases
@pytest.mark.unit
def test_unit_conversion_edge_cases(mapper):
    """Test unit conversion with edge case values."""
    # Test dewpoint calculation with extreme values
    assert mapper._calculate_dewpoint(100.0, 100.0) is not None  # 100% humidity
    assert mapper._calculate_dewpoint(-40.0, 50.0) is not None  # Very cold
    assert mapper._calculate_dewpoint(50.0, 0.0) is None  # 0% humidity (mathematically undefined)

    # Test cloud cover conversion
    assert mapper._cloud_cover_to_amount(12.5) == "CLR"  # Boundary value
    assert mapper._cloud_cover_to_amount(25.0) == "FEW"  # Boundary value
    assert mapper._cloud_cover_to_amount(50.0) == "SCT"  # Boundary value
    assert mapper._cloud_cover_to_amount(87.5) == "BKN"  # Boundary value

    # Test wind direction conversion
    assert mapper._degrees_to_direction(11.25) == "NNE"  # Boundary value (11.25 is in NNE range)
    assert mapper._degrees_to_direction(360.0) == "N"  # Full circle
    assert mapper._degrees_to_direction(720.0) == "N"  # Multiple circles


# Memory and performance edge cases
@pytest.mark.unit
def test_large_dataset_handling(mapper):
    """Test handling of large datasets."""
    # Create large hourly dataset (1 week = 168 hours)
    large_hourly_data = {
        "hourly": {
            "time": [
                f"2024-01-{day:02d}T{hour:02d}:00" for day in range(1, 8) for hour in range(24)
            ],
            "temperature_2m": [20.0 + (i % 10) for i in range(168)],
            "weather_code": [1 + (i % 5) for i in range(168)],
            "wind_speed_10m": [10.0 + (i % 20) for i in range(168)],
            "is_day": [1 if 6 <= (i % 24) <= 18 else 0 for i in range(168)],
        },
        "hourly_units": {"temperature_2m": "°C"},
    }

    result = mapper.map_hourly_forecast(large_hourly_data)

    assert len(result["properties"]["periods"]) == 168
    assert result is not None


@pytest.mark.unit
def test_empty_arrays_handling(mapper):
    """Test handling of completely empty data arrays."""
    empty_data: dict = {
        "daily": {
            "time": [],
            "weather_code": [],
            "temperature_2m_max": [],
            "temperature_2m_min": [],
        },
        "daily_units": {},
    }

    result = mapper.map_forecast(empty_data)

    assert result["properties"]["periods"] == []
