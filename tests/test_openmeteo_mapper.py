"""Tests for the OpenMeteoMapper class."""

import pytest

from accessiweather.openmeteo_mapper import OpenMeteoMapper

# Sample Open-Meteo API response data
SAMPLE_OPENMETEO_CURRENT_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "generationtime_ms": 0.123,
    "utc_offset_seconds": -18000,
    "timezone": "America/New_York",
    "timezone_abbreviation": "EST",
    "elevation": 100.0,
    "current_units": {
        "time": "iso8601",
        "temperature_2m": "°F",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°F",
        "precipitation": "inch",
        "weather_code": "wmo code",
        "cloud_cover": "%",
        "pressure_msl": "hPa",
        "wind_speed_10m": "mph",
        "wind_direction_10m": "°",
        "wind_gusts_10m": "mph",
    },
    "current": {
        "time": "2024-01-01T12:00",
        "temperature_2m": 72.5,
        "relative_humidity_2m": 65,
        "apparent_temperature": 75.2,
        "precipitation": 0.0,
        "weather_code": 1,
        "cloud_cover": 25,
        "pressure_msl": 1013.2,
        "wind_speed_10m": 8.5,
        "wind_direction_10m": 180,
        "wind_gusts_10m": 12.3,
    },
}

SAMPLE_OPENMETEO_FORECAST_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "daily_units": {
        "time": "iso8601",
        "weather_code": "wmo code",
        "temperature_2m_max": "°F",
        "temperature_2m_min": "°F",
        "wind_speed_10m_max": "mph",
        "wind_direction_10m_dominant": "°",
        "precipitation_sum": "inch",
    },
    "daily": {
        "time": ["2024-01-01", "2024-01-02"],
        "weather_code": [1, 2],
        "temperature_2m_max": [75.0, 78.0],
        "temperature_2m_min": [55.0, 58.0],
        "wind_speed_10m_max": [12.0, 15.0],
        "wind_direction_10m_dominant": [180, 225],
        "precipitation_sum": [0.0, 0.1],
    },
}

SAMPLE_OPENMETEO_HOURLY_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°F",
        "weather_code": "wmo code",
        "wind_speed_10m": "mph",
        "wind_direction_10m": "°",
    },
    "hourly": {
        "time": ["2024-01-01T12:00", "2024-01-01T13:00"],
        "temperature_2m": [72.0, 74.0],
        "weather_code": [1, 2],
        "wind_speed_10m": [8.5, 9.0],
        "wind_direction_10m": [180, 185],
        "is_day": [1, 1],
    },
}


@pytest.fixture
def mapper():
    """Create an OpenMeteoMapper instance for testing."""
    return OpenMeteoMapper()


@pytest.mark.unit
def test_mapper_initialization(mapper):
    """Test that the mapper initializes correctly."""
    assert mapper is not None


@pytest.mark.unit
def test_map_current_conditions_success(mapper):
    """Test successful mapping of current conditions."""
    result = mapper.map_current_conditions(SAMPLE_OPENMETEO_CURRENT_DATA)

    assert "properties" in result
    properties = result["properties"]

    # Check basic structure
    assert "@id" in properties
    assert "timestamp" in properties
    assert "temperature" in properties
    assert "dewpoint" in properties
    assert "windDirection" in properties
    assert "windSpeed" in properties
    assert "windGust" in properties
    assert "barometricPressure" in properties
    assert "relativeHumidity" in properties
    assert "textDescription" in properties

    # Check temperature mapping
    temp = properties["temperature"]
    assert temp["value"] == 72.5
    assert temp["unitCode"] == "wmoUnit:degF"
    assert temp["qualityControl"] == "qc:V"

    # Check wind mapping
    wind_speed = properties["windSpeed"]
    assert wind_speed["value"] == 8.5
    assert wind_speed["unitCode"] == "wmoUnit:mi_h-1"

    wind_direction = properties["windDirection"]
    assert wind_direction["value"] == 180
    assert wind_direction["unitCode"] == "wmoUnit:degree_(angle)"


@pytest.mark.unit
def test_map_current_conditions_with_missing_data(mapper):
    """Test mapping current conditions with missing data fields."""
    incomplete_data = {
        "current": {
            "time": "2024-01-01T12:00",
            "temperature_2m": 72.5,
            # Missing other fields
        },
        "current_units": {"temperature_2m": "°F"},
    }

    result = mapper.map_current_conditions(incomplete_data)

    assert "properties" in result
    properties = result["properties"]

    # Temperature should be mapped
    assert properties["temperature"]["value"] == 72.5

    # Missing fields should have None values
    assert properties["windSpeed"]["value"] is None
    assert properties["relativeHumidity"]["value"] is None


@pytest.mark.unit
def test_map_forecast_success(mapper):
    """Test successful mapping of forecast data."""
    result = mapper.map_forecast(SAMPLE_OPENMETEO_FORECAST_DATA)

    assert "properties" in result
    properties = result["properties"]

    assert "periods" in properties
    assert "updated" in properties
    assert "units" in properties
    assert "forecastGenerator" in properties

    periods = properties["periods"]
    # Should have 2 days * 2 periods (day/night) = 4 periods
    assert len(periods) == 4

    # Check first day period
    day_period = periods[0]
    assert day_period["isDaytime"] is True
    assert day_period["temperature"] == 75  # Fahrenheit temperature from test data
    assert day_period["temperatureUnit"] == "F"  # Fixed: now correctly recognizes "°F"
    assert "Monday" in day_period["name"] or "Sunday" in day_period["name"]  # Depends on date

    # Check first night period
    night_period = periods[1]
    assert night_period["isDaytime"] is False
    assert night_period["temperature"] == 55  # Fahrenheit temperature from test data
    assert "Night" in night_period["name"]


@pytest.mark.unit
def test_map_forecast_empty_data(mapper):
    """Test mapping forecast with empty data."""
    empty_data = {"daily": {}}

    result = mapper.map_forecast(empty_data)

    assert "properties" in result
    assert result["properties"]["periods"] == []


@pytest.mark.unit
def test_map_hourly_forecast_success(mapper):
    """Test successful mapping of hourly forecast data."""
    result = mapper.map_hourly_forecast(SAMPLE_OPENMETEO_HOURLY_DATA)

    assert "properties" in result
    properties = result["properties"]

    assert "periods" in properties
    assert "updated" in properties
    assert "units" in properties

    periods = properties["periods"]
    assert len(periods) == 2

    # Check first hour
    first_hour = periods[0]
    assert first_hour["number"] == 1
    assert first_hour["name"] == "This Hour"
    assert first_hour["temperature"] == 72
    assert first_hour["isDaytime"] is True

    # Check second hour
    second_hour = periods[1]
    assert second_hour["number"] == 2
    assert second_hour["temperature"] == 74


@pytest.mark.unit
def test_map_hourly_forecast_empty_data(mapper):
    """Test mapping hourly forecast with empty data."""
    empty_data = {"hourly": {}}

    result = mapper.map_hourly_forecast(empty_data)

    assert "properties" in result
    assert result["properties"]["periods"] == []


# Test helper methods
@pytest.mark.unit
def test_get_temperature_unit_code(mapper):
    """Test temperature unit code conversion."""
    assert mapper._get_temperature_unit_code("°F") == "wmoUnit:degF"
    assert mapper._get_temperature_unit_code("fahrenheit") == "wmoUnit:degF"
    assert mapper._get_temperature_unit_code("°C") == "wmoUnit:degC"
    assert mapper._get_temperature_unit_code("celsius") == "wmoUnit:degC"


@pytest.mark.unit
def test_get_wind_speed_unit_code(mapper):
    """Test wind speed unit code conversion."""
    assert mapper._get_wind_speed_unit_code("mph") == "wmoUnit:mi_h-1"
    assert mapper._get_wind_speed_unit_code("kmh") == "wmoUnit:km_h-1"
    assert mapper._get_wind_speed_unit_code("km/h") == "wmoUnit:km_h-1"
    assert mapper._get_wind_speed_unit_code("m/s") == "wmoUnit:m_s-1"
    assert mapper._get_wind_speed_unit_code("ms") == "wmoUnit:m_s-1"
    assert mapper._get_wind_speed_unit_code("kn") == "wmoUnit:kn"
    assert mapper._get_wind_speed_unit_code("xyz") == "wmoUnit:m_s-1"  # Default


@pytest.mark.unit
def test_calculate_dewpoint(mapper):
    """Test dewpoint calculation."""
    # Test with Fahrenheit temperature
    dewpoint = mapper._calculate_dewpoint(72.0, 65.0)
    assert dewpoint is not None
    assert isinstance(dewpoint, float)
    assert 50 < dewpoint < 80  # Reasonable range

    # Test with Celsius temperature
    dewpoint = mapper._calculate_dewpoint(22.0, 65.0)
    assert dewpoint is not None
    assert isinstance(dewpoint, float)
    assert 10 < dewpoint < 25  # Reasonable range

    # Test with None values
    assert mapper._calculate_dewpoint(None, 65.0) is None
    assert mapper._calculate_dewpoint(72.0, None) is None
    assert mapper._calculate_dewpoint(None, None) is None


@pytest.mark.unit
def test_cloud_cover_to_amount(mapper):
    """Test cloud cover percentage to amount conversion."""
    assert mapper._cloud_cover_to_amount(0) == "CLR"
    assert mapper._cloud_cover_to_amount(10) == "CLR"
    assert mapper._cloud_cover_to_amount(20) == "FEW"
    assert mapper._cloud_cover_to_amount(40) == "SCT"
    assert mapper._cloud_cover_to_amount(70) == "BKN"
    assert mapper._cloud_cover_to_amount(90) == "OVC"
    assert mapper._cloud_cover_to_amount(None) == "UNK"


@pytest.mark.unit
def test_degrees_to_direction(mapper):
    """Test wind direction conversion from degrees to cardinal directions."""
    assert mapper._degrees_to_direction(0) == "N"
    assert mapper._degrees_to_direction(90) == "E"
    assert mapper._degrees_to_direction(180) == "S"
    assert mapper._degrees_to_direction(270) == "W"
    assert mapper._degrees_to_direction(45) == "NE"
    assert mapper._degrees_to_direction(225) == "SW"
    assert mapper._degrees_to_direction(360) == "N"  # Should wrap around
    assert mapper._degrees_to_direction(None) == "VAR"


@pytest.mark.unit
def test_create_detailed_forecast(mapper):
    """Test detailed forecast creation."""
    daily_data = {
        "weather_code": [1],
        "temperature_2m_max": [75.0],
        "temperature_2m_min": [55.0],
        "wind_speed_10m_max": [12.0],
        "wind_direction_10m_dominant": [180],
        "precipitation_sum": [0.1],
    }
    daily_units = {"wind_speed_10m_max": "mph", "precipitation_sum": "inch"}

    # Test daytime forecast
    day_forecast = mapper._create_detailed_forecast(daily_data, daily_units, 0, True)
    assert "high near 75" in day_forecast
    assert "Wind S 12 mph" in day_forecast
    assert "Precipitation 0.10 inch" in day_forecast

    # Test nighttime forecast
    night_forecast = mapper._create_detailed_forecast(daily_data, daily_units, 0, False)
    assert "low near 55" in night_forecast
