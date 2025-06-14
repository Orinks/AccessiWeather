"""Sample data fixtures for testing weather API responses."""

import pytest


@pytest.fixture
def sample_nws_point_response():
    """Sample NWS point API response."""
    return {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/50,75/forecast/hourly",
            "forecastGridData": "https://api.weather.gov/gridpoints/PHI/50,75",
            "observationStations": "https://api.weather.gov/gridpoints/PHI/50,75/stations",
            "relativeLocation": {"properties": {"city": "Test City", "state": "PA"}},
            "gridId": "PHI",
            "gridX": 50,
            "gridY": 75,
        }
    }


@pytest.fixture
def sample_nws_forecast_response():
    """Sample NWS forecast API response."""
    return {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "name": "Today",
                    "startTime": "2024-01-01T12:00:00-05:00",
                    "endTime": "2024-01-01T18:00:00-05:00",
                    "isDaytime": True,
                    "temperature": 72,
                    "temperatureUnit": "F",
                    "temperatureTrend": None,
                    "windSpeed": "10 mph",
                    "windDirection": "SW",
                    "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
                    "shortForecast": "Sunny",
                    "detailedForecast": "Sunny skies with light winds.",
                },
                {
                    "number": 2,
                    "name": "Tonight",
                    "startTime": "2024-01-01T18:00:00-05:00",
                    "endTime": "2024-01-02T06:00:00-05:00",
                    "isDaytime": False,
                    "temperature": 45,
                    "temperatureUnit": "F",
                    "temperatureTrend": None,
                    "windSpeed": "5 mph",
                    "windDirection": "W",
                    "icon": "https://api.weather.gov/icons/land/night/few?size=medium",
                    "shortForecast": "Clear",
                    "detailedForecast": "Clear skies overnight.",
                },
            ]
        }
    }


@pytest.fixture
def sample_nws_current_response():
    """Sample NWS current conditions response."""
    return {
        "properties": {
            "timestamp": "2024-01-01T12:00:00Z",
            "textDescription": "Sunny",
            "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
            "presentWeather": [],
            "temperature": {"value": 22.2, "unitCode": "wmoUnit:degC"},
            "dewpoint": {"value": 10.0, "unitCode": "wmoUnit:degC"},
            "windDirection": {"value": 225, "unitCode": "wmoUnit:degree_(angle)"},
            "windSpeed": {"value": 4.47, "unitCode": "wmoUnit:m_s-1"},
            "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
            "relativeHumidity": {"value": 65, "unitCode": "wmoUnit:percent"},
            "visibility": {"value": 16093, "unitCode": "wmoUnit:m"},
        }
    }


@pytest.fixture
def sample_nws_alerts_response():
    """Sample NWS alerts response."""
    return {
        "features": [
            {
                "properties": {
                    "id": "urn:oid:2.49.0.1.840.0.123456789",
                    "areaDesc": "Test County",
                    "geocode": {"FIPS6": ["42101"], "UGC": ["PAC101"]},
                    "affectedZones": ["https://api.weather.gov/zones/county/PAC101"],
                    "references": [],
                    "sent": "2024-01-01T12:00:00-05:00",
                    "effective": "2024-01-01T12:00:00-05:00",
                    "onset": "2024-01-01T15:00:00-05:00",
                    "expires": "2024-01-01T21:00:00-05:00",
                    "ends": "2024-01-01T21:00:00-05:00",
                    "status": "Actual",
                    "messageType": "Alert",
                    "category": "Met",
                    "severity": "Minor",
                    "certainty": "Likely",
                    "urgency": "Expected",
                    "event": "Winter Weather Advisory",
                    "sender": "w-nws.webmaster@noaa.gov",
                    "senderName": "NWS Philadelphia PA",
                    "headline": "Winter Weather Advisory issued January 1 at 12:00PM EST until January 1 at 9:00PM EST by NWS Philadelphia PA",
                    "description": "Light snow expected this afternoon and evening.",
                    "instruction": "Use caution while traveling.",
                    "response": "Prepare",
                    "parameters": {
                        "AWIPSidentifier": ["WSUPHI"],
                        "WMOidentifier": ["WWUS51 KPHI 011700"],
                        "NWSheadline": [
                            "WINTER WEATHER ADVISORY IN EFFECT FROM 3 PM THIS AFTERNOON TO 9 PM EST THIS EVENING"
                        ],
                        "BLOCKCHANNEL": ["EAS", "NWEM", "CMAS"],
                        "VTEC": ["/O.NEW.KPHI.WW.Y.0001.240101T2000Z-240102T0200Z/"],
                        "eventEndingTime": ["2024-01-01T21:00:00-05:00"],
                    },
                }
            }
        ]
    }


@pytest.fixture
def sample_openmeteo_current_response():
    """Sample Open-Meteo current weather response."""
    return {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "generationtime_ms": 0.123,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 25.0,
        "current_units": {
            "time": "iso8601",
            "interval": "seconds",
            "temperature_2m": "°F",
            "relative_humidity_2m": "%",
            "apparent_temperature": "°F",
            "is_day": "",
            "precipitation": "inch",
            "weather_code": "wmo code",
            "pressure_msl": "hPa",
            "wind_speed_10m": "mph",
            "wind_direction_10m": "°",
        },
        "current": {
            "time": "2024-01-01T12:00",
            "interval": 900,
            "temperature_2m": 59.0,
            "relative_humidity_2m": 70,
            "apparent_temperature": 57.2,
            "is_day": 1,
            "precipitation": 0.0,
            "weather_code": 2,
            "pressure_msl": 1013.2,
            "wind_speed_10m": 6.2,
            "wind_direction_10m": 225,
        },
    }


@pytest.fixture
def sample_openmeteo_forecast_response():
    """Sample Open-Meteo forecast response."""
    return {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "generationtime_ms": 0.456,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 25.0,
        "daily_units": {
            "time": "iso8601",
            "weather_code": "wmo code",
            "temperature_2m_max": "°F",
            "temperature_2m_min": "°F",
            "apparent_temperature_max": "°F",
            "apparent_temperature_min": "°F",
            "sunrise": "iso8601",
            "sunset": "iso8601",
            "precipitation_sum": "inch",
            "precipitation_probability_max": "%",
            "wind_speed_10m_max": "mph",
            "wind_gusts_10m_max": "mph",
            "wind_direction_10m_dominant": "°",
        },
        "daily": {
            "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "weather_code": [1, 2, 3],
            "temperature_2m_max": [64.4, 66.2, 59.0],
            "temperature_2m_min": [46.4, 48.2, 41.0],
            "apparent_temperature_max": [62.6, 64.4, 57.2],
            "apparent_temperature_min": [44.6, 46.4, 39.2],
            "sunrise": ["2024-01-01T07:30:00", "2024-01-02T07:30:00", "2024-01-03T07:31:00"],
            "sunset": ["2024-01-01T17:30:00", "2024-01-02T17:31:00", "2024-01-03T17:32:00"],
            "precipitation_sum": [0.0, 0.1, 0.3],
            "precipitation_probability_max": [0, 20, 60],
            "wind_speed_10m_max": [8.1, 10.3, 12.4],
            "wind_gusts_10m_max": [15.7, 18.6, 22.4],
            "wind_direction_10m_dominant": [225, 180, 270],
        },
    }
