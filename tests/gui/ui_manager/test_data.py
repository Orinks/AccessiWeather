"""Shared test data for UI Manager tests."""

# --- Test Data ---

SAMPLE_FORECAST_DATA = {
    "properties": {
        "periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperatureUnit": "F",
                "detailedForecast": "Sunny with a high near 75.",
            },
            {
                "name": "Tonight",
                "temperature": 60,
                "temperatureUnit": "F",
                "detailedForecast": "Clear with a low around 60.",
            },
        ]
    }
}

SAMPLE_NATIONAL_FORECAST_DATA = {
    "national_discussion_summaries": {
        "wpc": {
            "short_range_summary": "Rain in the Northeast, sunny in the West.",
            "short_range_full": "Detailed WPC discussion...",
        },
        "spc": {
            "day1_summary": "Severe storms possible in the Plains.",
            "day1_full": "Detailed SPC discussion...",
        },
        "attribution": "National Weather Service",
    }
}

SAMPLE_ALERTS_DATA = {
    "features": [
        {
            "properties": {
                "event": "Severe Thunderstorm Warning",
                "severity": "Severe",
                "headline": "Severe thunderstorm warning until 5 PM",
            }
        },
        {
            "properties": {
                "event": "Flash Flood Watch",
                "severity": "Moderate",
                "headline": "Flash flood watch in effect",
            }
        },
    ]
}

# Sample WeatherAPI.com data
SAMPLE_WEATHERAPI_FORECAST_DATA = {
    "forecast": [
        {
            "date": "2023-06-01",
            "high": 75,
            "low": 60,
            "condition": "Sunny",
            "precipitation_probability": 10,
            "max_wind_speed": 15,
        },
        {
            "date": "2023-06-02",
            "high": 80,
            "low": 65,
            "condition": "Partly cloudy",
            "precipitation_probability": 20,
            "max_wind_speed": 12,
        },
    ],
    "location": {"name": "London", "region": "City of London", "country": "United Kingdom"},
    "hourly": [
        {"time": "2023-06-01 12:00", "temperature": 72, "condition": "Sunny"},
        {"time": "2023-06-01 13:00", "temperature": 74, "condition": "Sunny"},
    ],
}

SAMPLE_WEATHERAPI_CURRENT_DATA = {
    "temperature": 72,
    "temperature_c": 22.2,
    "condition": "Sunny",
    "humidity": 45,
    "wind_speed": 10,
    "wind_speed_kph": 16.1,
    "wind_direction": "NW",
    "pressure": 30.1,
    "pressure_mb": 1019,
    "feelslike": 70,
    "feelslike_c": 21.1,
}

SAMPLE_WEATHERAPI_ALERTS_DATA = {
    "alerts": [
        {
            "event": "Flood Warning",
            "severity": "Moderate",
            "headline": "Flood warning for London area",
        },
        {
            "event": "Wind Advisory",
            "severity": "Minor",
            "headline": "Wind advisory in effect until evening",
        },
    ]
}
