"""Shared utilities for NoaaApiClient tests."""

import pytest

from accessiweather.api_client import NoaaApiClient

# Sample test data
SAMPLE_POINT_DATA = {
    "@context": ["https://geojson.org/geojson-ld/geojson-context.jsonld"],
    "id": "https://api.weather.gov/points/40,-75",
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-75.0, 40.0]},
    "properties": {
        "@id": "https://api.weather.gov/points/40,-75",
        "gridId": "PHI",
        "gridX": 50,
        "gridY": 75,
        "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PHI/50,75/forecast/hourly",
        "forecastGridData": "https://api.weather.gov/gridpoints/PHI/50,75",
        "observationStations": "https://api.weather.gov/gridpoints/PHI/50,75/stations",
        "relativeLocation": {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-75.1, 40.1]},
            "properties": {"city": "Test City", "state": "PA"},
        },
        "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
        "county": "https://api.weather.gov/zones/county/PAC091",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
    },
}

SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny with a high near 75.",
            }
        ]
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "headline": "Test Alert",
                "description": "Test Description",
                "instruction": "Test Instruction",
                "severity": "Moderate",
                "event": "Test Event",
            }
        }
    ]
}

SAMPLE_DISCUSSION_PRODUCTS = {"@graph": [{"id": "AFD-PHI-202401010000", "@type": "wx:TextProduct"}]}

SAMPLE_DISCUSSION_TEXT = {
    "productText": """
This is a sample forecast discussion.
Multiple lines of text.
With weather information.
"""
}

SAMPLE_NATIONAL_PRODUCT = {
    "@graph": [{"id": "FXUS01-KWNH-202401010000", "@type": "wx:TextProduct"}]
}

SAMPLE_NATIONAL_PRODUCT_TEXT = {
    "productText": """
This is a sample national product text.
Multiple lines of text.
With weather information.
"""
}

# Sample station data
SAMPLE_STATIONS_DATA = {
    "features": [
        {
            "id": "https://api.weather.gov/stations/KXYZ",
            "properties": {
                "@id": "https://api.weather.gov/stations/KXYZ",
                "@type": "wx:ObservationStation",
                "elevation": {"unitCode": "wmoUnit:m", "value": 123.4},
                "name": "Test Station",
                "stationIdentifier": "KXYZ",
                "timeZone": "America/New_York",
            },
        },
        {
            "id": "https://api.weather.gov/stations/KABC",
            "properties": {
                "@id": "https://api.weather.gov/stations/KABC",
                "@type": "wx:ObservationStation",
                "elevation": {"unitCode": "wmoUnit:m", "value": 234.5},
                "name": "Another Test Station",
                "stationIdentifier": "KABC",
                "timeZone": "America/New_York",
            },
        },
    ]
}

# Sample current observation data
SAMPLE_OBSERVATION_DATA = {
    "properties": {
        "@id": "https://api.weather.gov/stations/KXYZ/observations/2023-01-01T12:00:00Z",
        "temperature": {"unitCode": "wmoUnit:degC", "value": 22.8, "qualityControl": "qc:V"},
        "dewpoint": {"unitCode": "wmoUnit:degC", "value": 15.6, "qualityControl": "qc:V"},
        "windDirection": {
            "unitCode": "wmoUnit:degree_(angle)",
            "value": 180,
            "qualityControl": "qc:V",
        },
        "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 15.0, "qualityControl": "qc:V"},
        "barometricPressure": {"unitCode": "wmoUnit:Pa", "value": 101325, "qualityControl": "qc:V"},
        "seaLevelPressure": {"unitCode": "wmoUnit:Pa", "value": 101325, "qualityControl": "qc:V"},
        "visibility": {"unitCode": "wmoUnit:km", "value": 16.09, "qualityControl": "qc:V"},
        "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": 65, "qualityControl": "qc:V"},
        "textDescription": "Partly Cloudy",
        "icon": "https://api.weather.gov/icons/land/day/sct?size=medium",
    }
}

# Sample hourly forecast data
SAMPLE_HOURLY_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "number": 1,
                "name": "This Hour",
                "startTime": "2023-01-01T12:00:00-05:00",
                "endTime": "2023-01-01T13:00:00-05:00",
                "isDaytime": True,
                "temperature": 72,
                "temperatureUnit": "F",
                "temperatureTrend": None,
                "windSpeed": "10 mph",
                "windDirection": "S",
                "icon": "https://api.weather.gov/icons/land/day/sct?size=small",
                "shortForecast": "Partly Sunny",
                "detailedForecast": "",
            },
            {
                "number": 2,
                "name": "Next Hour",
                "startTime": "2023-01-01T13:00:00-05:00",
                "endTime": "2023-01-01T14:00:00-05:00",
                "isDaytime": True,
                "temperature": 73,
                "temperatureUnit": "F",
                "temperatureTrend": "rising",
                "windSpeed": "12 mph",
                "windDirection": "S",
                "icon": "https://api.weather.gov/icons/land/day/sct?size=small",
                "shortForecast": "Partly Sunny",
                "detailedForecast": "",
            },
        ]
    }
}


# Shared fixtures
@pytest.fixture
def api_client():
    """Create a NoaaApiClient instance without caching."""
    return NoaaApiClient(
        user_agent="TestClient", contact_info="test@example.com", enable_caching=False
    )


@pytest.fixture
def cached_api_client():
    """Create a NoaaApiClient instance with caching enabled."""
    return NoaaApiClient(
        user_agent="TestClient", contact_info="test@example.com", enable_caching=True, cache_ttl=300
    )


def create_modified_point_data_without_zones():
    """Create point data without zone URLs for testing state fallback."""
    modified_point_data = dict(SAMPLE_POINT_DATA)
    properties = {}

    # Copy all properties except the zone ones
    properties_dict = SAMPLE_POINT_DATA.get("properties", {})
    if isinstance(properties_dict, dict):
        for key in list(properties_dict.keys()):
            if key not in ["county", "forecastZone", "fireWeatherZone"]:
                properties[key] = properties_dict[key]

    # Create a deep copy of the relativeLocation in a type-safe way
    rel_location = {}
    rel_properties = {"state": "PA"}

    # Copy other properties if they exist
    if isinstance(properties_dict, dict) and "relativeLocation" in properties_dict:
        rel_location_orig = properties_dict.get("relativeLocation", {})
        if isinstance(rel_location_orig, dict):
            for key in list(rel_location_orig.keys()):
                if key != "properties":
                    rel_location[key] = rel_location_orig[key]

            rel_props_orig = rel_location_orig.get("properties", {})
            if isinstance(rel_props_orig, dict):
                for key in list(rel_props_orig.keys()):
                    rel_properties[key] = rel_props_orig[key]

    rel_location["properties"] = rel_properties
    properties["relativeLocation"] = rel_location
    modified_point_data["properties"] = properties

    return modified_point_data


def create_point_data_without_forecast():
    """Create point data without forecast URL for testing error handling."""
    bad_point_data = dict(SAMPLE_POINT_DATA)
    properties = {}

    # Copy all properties except 'forecast'
    properties_dict = SAMPLE_POINT_DATA.get("properties", {})
    if isinstance(properties_dict, dict):
        for key in list(properties_dict.keys()):
            if key != "forecast":
                properties[key] = properties_dict[key]

    bad_point_data["properties"] = properties
    return bad_point_data
