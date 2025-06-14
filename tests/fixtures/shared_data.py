"""Shared test data and mock data for AccessiWeather tests."""

# Import mock data - using relative imports
try:
    from ..mock_data import (
        MOCK_NWS_ALERTS_DATA,
        MOCK_NWS_CURRENT_CONDITIONS,
        MOCK_NWS_FORECAST_DATA,
        MOCK_NWS_POINT_DATA,
        MOCK_OPENMETEO_CURRENT_WEATHER,
        MOCK_OPENMETEO_FORECAST,
    )
except ImportError:
    # Fallback to inline mock data if import fails
    MOCK_NWS_CURRENT_CONDITIONS = {
        "properties": {
            "temperature": {"value": 20.0, "unitCode": "wmoUnit:degC"},
            "textDescription": "Partly Cloudy",
            "relativeHumidity": {"value": 65},
            "windSpeed": {"value": 10, "unitCode": "wmoUnit:km_h-1"},
            "windDirection": {"value": 180},
            "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
        }
    }

    MOCK_NWS_FORECAST_DATA = {
        "properties": {
            "periods": [
                {
                    "name": "Today",
                    "temperature": 75,
                    "temperatureUnit": "F",
                    "shortForecast": "Sunny",
                    "detailedForecast": "Sunny with a high near 75.",
                    "windSpeed": "10 mph",
                    "windDirection": "SW",
                }
            ]
        }
    }

    MOCK_NWS_ALERTS_DATA = {
        "features": [
            {
                "properties": {
                    "headline": "Heat Advisory",
                    "description": "Dangerous heat conditions expected.",
                    "instruction": "Stay hydrated and avoid prolonged sun exposure.",
                    "severity": "Moderate",
                    "event": "Heat Advisory",
                    "urgency": "Expected",
                    "certainty": "Likely",
                }
            }
        ]
    }

    MOCK_NWS_POINT_DATA = {
        "properties": {
            "gridId": "PHI",
            "gridX": 50,
            "gridY": 75,
            "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
            "county": "https://api.weather.gov/zones/county/PAC091",
        }
    }

    MOCK_OPENMETEO_CURRENT_WEATHER = {
        "current": {
            "temperature_2m": 68.0,
            "weather_code": 2,
            "relative_humidity_2m": 65,
            "wind_speed_10m": 8.5,
            "wind_direction_10m": 180,
            "pressure_msl": 1013.2,
        }
    }

    MOCK_OPENMETEO_FORECAST = {
        "daily": {
            "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "weather_code": [1, 2, 3],
            "temperature_2m_max": [75.0, 78.0, 72.0],
            "temperature_2m_min": [55.0, 58.0, 52.0],
        }
    }


# Export all mock data
__all__ = [
    "MOCK_NWS_CURRENT_CONDITIONS",
    "MOCK_NWS_FORECAST_DATA",
    "MOCK_NWS_ALERTS_DATA",
    "MOCK_NWS_POINT_DATA",
    "MOCK_OPENMETEO_CURRENT_WEATHER",
    "MOCK_OPENMETEO_FORECAST",
]
