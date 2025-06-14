"""Tests for NoaaApiWrapper data transformation functionality."""

from unittest.mock import MagicMock

import pytest

from tests.api_wrapper_test_utils import api_wrapper


@pytest.mark.unit
def test_request_transformation_point_data(api_wrapper):
    """Test request transformation for point data."""
    # Test with object-style response that has additional_properties
    mock_properties = MagicMock()
    mock_properties.additional_properties = {
        "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
    }

    mock_response = MagicMock()
    mock_response.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_response)

    assert "properties" in result
    assert (
        result["properties"]["forecast"] == "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    )
    assert (
        result["properties"]["forecastHourly"]
        == "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    )


@pytest.mark.unit
def test_transform_point_data_dict_format(api_wrapper):
    """Test _transform_point_data with dictionary input."""
    input_data = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
            "county": "https://api.weather.gov/zones/county/PAC101",
            "timeZone": "America/New_York",
        }
    }

    result = api_wrapper._transform_point_data(input_data)

    assert result["properties"]["forecast"] == input_data["properties"]["forecast"]
    assert result["properties"]["forecastHourly"] == input_data["properties"]["forecastHourly"]
    assert result["properties"]["county"] == input_data["properties"]["county"]
    assert result["properties"]["timeZone"] == input_data["properties"]["timeZone"]


@pytest.mark.unit
def test_transform_point_data_object_with_additional_properties(api_wrapper):
    """Test _transform_point_data with object having additional_properties."""
    mock_properties = MagicMock()
    mock_properties.additional_properties = {
        "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
    }

    mock_data = MagicMock()
    mock_data.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_data)

    assert (
        result["properties"]["forecast"] == "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    )
    assert (
        result["properties"]["forecastHourly"]
        == "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    )


@pytest.mark.unit
def test_transform_point_data_object_without_additional_properties(api_wrapper):
    """Test _transform_point_data with object without additional_properties."""
    mock_properties = MagicMock()
    mock_properties.forecast = "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    mock_properties.forecast_hourly = "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    # Ensure additional_properties doesn't exist
    del mock_properties.additional_properties

    mock_data = MagicMock()
    mock_data.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_data)

    assert (
        result["properties"]["forecast"] == "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    )
    assert (
        result["properties"]["forecastHourly"]
        == "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly"
    )


@pytest.mark.unit
def test_transform_point_data_fallback(api_wrapper):
    """Test _transform_point_data fallback when no properties."""
    # Test with empty or missing properties
    mock_data = MagicMock()
    mock_data.properties = None

    # This should handle the case gracefully
    result = api_wrapper._transform_point_data(mock_data)
    assert isinstance(result, dict)


@pytest.mark.unit
def test_transform_point_data_with_missing_attributes(api_wrapper):
    """Test _transform_point_data with missing attributes."""
    mock_properties = MagicMock()
    # Only set some attributes, leave others missing
    mock_properties.forecast = "https://api.weather.gov/gridpoints/PHI/31,70/forecast"
    # Don't set forecast_hourly or other attributes
    del mock_properties.forecast_hourly
    del mock_properties.additional_properties

    mock_data = MagicMock()
    mock_data.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_data)

    assert "properties" in result
    assert result["properties"]["forecast"] == mock_properties.forecast
    # Missing attributes should be handled gracefully


@pytest.mark.unit
def test_transform_point_data_with_nested_properties(api_wrapper):
    """Test _transform_point_data with nested property structures."""
    input_data = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
            "relativeLocation": {
                "properties": {
                    "city": "Philadelphia",
                    "state": "PA",
                }
            },
            "county": "https://api.weather.gov/zones/county/PAC101",
        }
    }

    result = api_wrapper._transform_point_data(input_data)

    assert result["properties"]["forecast"] == input_data["properties"]["forecast"]
    assert result["properties"]["forecastHourly"] == input_data["properties"]["forecastHourly"]
    assert result["properties"]["county"] == input_data["properties"]["county"]
    # Nested properties should be preserved
    if "relativeLocation" in result["properties"]:
        assert (
            result["properties"]["relativeLocation"] == input_data["properties"]["relativeLocation"]
        )


@pytest.mark.unit
def test_transform_point_data_with_special_characters(api_wrapper):
    """Test _transform_point_data with URLs containing special characters."""
    input_data = {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast?units=us&format=json",
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly?units=us",
            "county": "https://api.weather.gov/zones/county/PAC101",
        }
    }

    result = api_wrapper._transform_point_data(input_data)

    assert result["properties"]["forecast"] == input_data["properties"]["forecast"]
    assert result["properties"]["forecastHourly"] == input_data["properties"]["forecastHourly"]
    assert result["properties"]["county"] == input_data["properties"]["county"]


@pytest.mark.unit
def test_transform_point_data_empty_properties(api_wrapper):
    """Test _transform_point_data with empty properties."""
    input_data = {"properties": {}}

    result = api_wrapper._transform_point_data(input_data)

    assert "properties" in result
    assert isinstance(result["properties"], dict)


@pytest.mark.unit
def test_transform_point_data_none_values(api_wrapper):
    """Test _transform_point_data with None values in properties."""
    input_data = {
        "properties": {
            "forecast": None,
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
            "county": None,
        }
    }

    result = api_wrapper._transform_point_data(input_data)

    assert "properties" in result
    # None values should be preserved or handled appropriately
    assert result["properties"]["forecast"] is None
    assert result["properties"]["forecastHourly"] == input_data["properties"]["forecastHourly"]
    assert result["properties"]["county"] is None


@pytest.mark.unit
def test_transform_point_data_type_conversion(api_wrapper):
    """Test _transform_point_data handles different data types correctly."""
    mock_properties = MagicMock()
    mock_properties.additional_properties = {
        "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
        "elevation": {"value": 123.45, "unitCode": "wmoUnit:m"},
        "gridId": "PHI",
        "gridX": 31,
        "gridY": 70,
    }

    mock_data = MagicMock()
    mock_data.properties = mock_properties

    result = api_wrapper._transform_point_data(mock_data)

    assert "properties" in result
    # String values
    assert isinstance(result["properties"]["forecast"], str)
    assert isinstance(result["properties"]["forecastHourly"], str)
    # Complex objects should be preserved
    if "elevation" in result["properties"]:
        assert isinstance(result["properties"]["elevation"], dict)
    # Numeric values should be preserved
    if "gridX" in result["properties"]:
        assert isinstance(result["properties"]["gridX"], int)
    if "gridY" in result["properties"]:
        assert isinstance(result["properties"]["gridY"], int)
