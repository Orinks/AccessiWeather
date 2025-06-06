"""Comprehensive mock data for API testing."""

# NWS API Mock Data
MOCK_NWS_POINT_DATA = {
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
            "properties": {"city": "Philadelphia", "state": "PA"},
        },
        "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
        "county": "https://api.weather.gov/zones/county/PAC091",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
    },
}

MOCK_NWS_FORECAST_DATA = {
    "properties": {
        "updated": "2024-01-01T12:00:00+00:00",
        "units": "us",
        "forecastGenerator": "BaselineForecastGenerator",
        "generatedAt": "2024-01-01T12:00:00+00:00",
        "updateTime": "2024-01-01T12:00:00+00:00",
        "validTimes": "2024-01-01T12:00:00+00:00/P7DT12H",
        "elevation": {"unitCode": "wmoUnit:m", "value": 100},
        "periods": [
            {
                "number": 1,
                "name": "Today",
                "startTime": "2024-01-01T12:00:00-05:00",
                "endTime": "2024-01-01T18:00:00-05:00",
                "isDaytime": True,
                "temperature": 75,
                "temperatureUnit": "F",
                "temperatureTrend": None,
                "windSpeed": "10 mph",
                "windDirection": "SW",
                "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
                "shortForecast": "Sunny",
                "detailedForecast": "Sunny with a high near 75. Southwest wind around 10 mph.",
            },
            {
                "number": 2,
                "name": "Tonight",
                "startTime": "2024-01-01T18:00:00-05:00",
                "endTime": "2024-01-02T06:00:00-05:00",
                "isDaytime": False,
                "temperature": 55,
                "temperatureUnit": "F",
                "temperatureTrend": None,
                "windSpeed": "5 mph",
                "windDirection": "W",
                "icon": "https://api.weather.gov/icons/land/night/few?size=medium",
                "shortForecast": "Clear",
                "detailedForecast": "Clear skies with a low around 55. West wind around 5 mph.",
            },
        ],
    }
}

MOCK_NWS_ALERTS_DATA = {
    "@context": ["https://geojson.org/geojson-ld/geojson-context.jsonld"],
    "type": "FeatureCollection",
    "features": [
        {
            "id": "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.123456789",
            "type": "Feature",
            "geometry": None,
            "properties": {
                "@id": "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.123456789",
                "@type": "wx:Alert",
                "id": "urn:oid:2.49.0.1.840.0.123456789",
                "areaDesc": "Philadelphia County",
                "geocode": {"FIPS6": ["042101"], "UGC": ["PAC101"]},
                "affectedZones": ["https://api.weather.gov/zones/county/PAC101"],
                "references": [],
                "sent": "2024-01-01T12:00:00-05:00",
                "effective": "2024-01-01T12:00:00-05:00",
                "onset": "2024-01-01T14:00:00-05:00",
                "expires": "2024-01-01T20:00:00-05:00",
                "ends": "2024-01-01T20:00:00-05:00",
                "status": "Actual",
                "messageType": "Alert",
                "category": "Met",
                "severity": "Moderate",
                "certainty": "Likely",
                "urgency": "Expected",
                "event": "Heat Advisory",
                "sender": "w-nws.webmaster@noaa.gov",
                "senderName": "NWS Philadelphia PA",
                "headline": "Heat Advisory issued January 01 at 12:00PM EST until January 01 at 8:00PM EST by NWS Philadelphia PA",
                "description": "Hot temperatures and high humidity will combine to create a dangerous situation in which heat illnesses are possible.",
                "instruction": "A Heat Advisory means that a period of hot temperatures is expected. The combination of hot temperatures and high humidity will combine to create a situation in which heat illnesses are possible. Drink plenty of fluids, stay in an air-conditioned room, stay out of the sun, and check up on relatives and neighbors.",
                "response": "Execute",
                "parameters": {
                    "AWIPSidentifier": ["NPWPHI"],
                    "WMOidentifier": ["WWUS51 KPHI 011700"],
                    "NWSheadline": [
                        "HEAT ADVISORY IN EFFECT FROM 2 PM THIS AFTERNOON TO 8 PM EST THIS EVENING"
                    ],
                    "BLOCKCHANNEL": ["CMAS", "EAS", "NWEM"],
                },
            },
        }
    ],
    "title": "Current watches, warnings, and advisories for Philadelphia County (PAC101) PA",
    "updated": "2024-01-01T12:00:00+00:00",
}

MOCK_NWS_CURRENT_CONDITIONS = {
    "properties": {
        "@id": "https://api.weather.gov/stations/KPHL/observations/2024-01-01T12:00:00+00:00",
        "@type": "wx:ObservationStation",
        "elevation": {"unitCode": "wmoUnit:m", "value": 11},
        "station": "https://api.weather.gov/stations/KPHL",
        "timestamp": "2024-01-01T12:00:00+00:00",
        "rawMessage": "KPHL 011200Z 25010KT 10SM FEW250 22/15 A3015 RMK AO2 SLP210 T02220150",
        "textDescription": "Partly Cloudy",
        "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
        "presentWeather": [],
        "temperature": {"unitCode": "wmoUnit:degC", "value": 22.2, "qualityControl": "qc:V"},
        "dewpoint": {"unitCode": "wmoUnit:degC", "value": 15.0, "qualityControl": "qc:V"},
        "windDirection": {
            "unitCode": "wmoUnit:degree_(angle)",
            "value": 250,
            "qualityControl": "qc:V",
        },
        "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 18.52, "qualityControl": "qc:V"},
        "windGust": {"unitCode": "wmoUnit:km_h-1", "value": None, "qualityControl": "qc:Z"},
        "barometricPressure": {"unitCode": "wmoUnit:Pa", "value": 102050, "qualityControl": "qc:V"},
        "seaLevelPressure": {"unitCode": "wmoUnit:Pa", "value": 102100, "qualityControl": "qc:V"},
        "visibility": {"unitCode": "wmoUnit:m", "value": 16093, "qualityControl": "qc:C"},
        "maxTemperatureLast24Hours": {
            "unitCode": "wmoUnit:degC",
            "value": None,
            "qualityControl": "qc:Z",
        },
        "minTemperatureLast24Hours": {
            "unitCode": "wmoUnit:degC",
            "value": None,
            "qualityControl": "qc:Z",
        },
        "precipitationLastHour": {
            "unitCode": "wmoUnit:mm",
            "value": None,
            "qualityControl": "qc:Z",
        },
        "precipitationLast3Hours": {
            "unitCode": "wmoUnit:mm",
            "value": None,
            "qualityControl": "qc:Z",
        },
        "precipitationLast6Hours": {
            "unitCode": "wmoUnit:mm",
            "value": None,
            "qualityControl": "qc:Z",
        },
        "relativeHumidity": {
            "unitCode": "wmoUnit:percent",
            "value": 65.5,
            "qualityControl": "qc:V",
        },
        "windChill": {"unitCode": "wmoUnit:degC", "value": None, "qualityControl": "qc:Z"},
        "heatIndex": {"unitCode": "wmoUnit:degC", "value": None, "qualityControl": "qc:Z"},
        "cloudLayers": [{"base": {"unitCode": "wmoUnit:m", "value": 7620}, "amount": "FEW"}],
    }
}

# Open-Meteo API Mock Data
MOCK_OPENMETEO_CURRENT_WEATHER = {
    "latitude": 40.0,
    "longitude": -75.0,
    "generationtime_ms": 0.123,
    "utc_offset_seconds": -18000,
    "timezone": "America/New_York",
    "timezone_abbreviation": "EST",
    "elevation": 100.0,
    "current_units": {
        "time": "iso8601",
        "interval": "seconds",
        "temperature_2m": "°F",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°F",
        "is_day": "",
        "precipitation": "inch",
        "weather_code": "wmo code",
        "cloud_cover": "%",
        "pressure_msl": "hPa",
        "surface_pressure": "hPa",
        "wind_speed_10m": "mph",
        "wind_direction_10m": "°",
        "wind_gusts_10m": "mph",
    },
    "current": {
        "time": "2024-01-01T12:00",
        "interval": 900,
        "temperature_2m": 72.5,
        "relative_humidity_2m": 65,
        "apparent_temperature": 75.2,
        "is_day": 1,
        "precipitation": 0.0,
        "weather_code": 1,
        "cloud_cover": 25,
        "pressure_msl": 1013.2,
        "surface_pressure": 1010.5,
        "wind_speed_10m": 8.5,
        "wind_direction_10m": 180,
        "wind_gusts_10m": 12.3,
    },
}

MOCK_OPENMETEO_FORECAST = {
    "latitude": 40.0,
    "longitude": -75.0,
    "generationtime_ms": 0.456,
    "utc_offset_seconds": -18000,
    "timezone": "America/New_York",
    "timezone_abbreviation": "EST",
    "elevation": 100.0,
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
        "time": [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",
            "2024-01-04",
            "2024-01-05",
            "2024-01-06",
            "2024-01-07",
        ],
        "weather_code": [1, 2, 3, 61, 80, 95, 0],
        "temperature_2m_max": [75.0, 78.0, 72.0, 68.0, 70.0, 73.0, 76.0],
        "temperature_2m_min": [55.0, 58.0, 52.0, 48.0, 50.0, 53.0, 56.0],
        "apparent_temperature_max": [77.0, 80.0, 74.0, 70.0, 72.0, 75.0, 78.0],
        "apparent_temperature_min": [53.0, 56.0, 50.0, 46.0, 48.0, 51.0, 54.0],
        "sunrise": [
            "2024-01-01T07:15:00",
            "2024-01-02T07:15:00",
            "2024-01-03T07:16:00",
            "2024-01-04T07:16:00",
            "2024-01-05T07:17:00",
            "2024-01-06T07:17:00",
            "2024-01-07T07:18:00",
        ],
        "sunset": [
            "2024-01-01T17:30:00",
            "2024-01-02T17:31:00",
            "2024-01-03T17:32:00",
            "2024-01-04T17:33:00",
            "2024-01-05T17:34:00",
            "2024-01-06T17:35:00",
            "2024-01-07T17:36:00",
        ],
        "precipitation_sum": [0.0, 0.1, 0.0, 0.5, 0.2, 1.2, 0.0],
        "precipitation_probability_max": [10, 30, 5, 70, 40, 90, 0],
        "wind_speed_10m_max": [12.0, 15.0, 8.0, 18.0, 14.0, 22.0, 10.0],
        "wind_gusts_10m_max": [18.0, 22.0, 12.0, 28.0, 20.0, 35.0, 15.0],
        "wind_direction_10m_dominant": [180, 225, 270, 315, 0, 45, 90],
    },
}

# Geocoding Mock Data
MOCK_GEOCODING_US_LOCATION = {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "address": "New York, NY, USA",
    "raw": {
        "address": {
            "country_code": "us",
            "state": "New York",
            "city": "New York",
            "postcode": "10001",
        }
    },
}

MOCK_GEOCODING_NON_US_LOCATION = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "address": "London, England, UK",
    "raw": {
        "address": {
            "country_code": "gb",
            "state": "England",
            "city": "London",
            "postcode": "SW1A 1AA",
        }
    },
}

# Web Scraping Mock Data
MOCK_WPC_DISCUSSION = """
<html>
<head><title>WPC Discussion</title></head>
<body>
<pre>
FXUS01 KWNH 011200
FXDUS1 KWNH 011200

Short Range Forecast Discussion
NWS Weather Prediction Center College Park MD
800 AM EST Mon Jan 01 2024

Valid 12Z Mon Jan 01 2024 - 12Z Wed Jan 03 2024

...SYNOPSIS...
A strong high pressure system will dominate the eastern United States
through Tuesday, bringing clear skies and pleasant temperatures.

...DISCUSSION...
The current synoptic pattern shows a robust 1030 mb high pressure
center located over the Ohio Valley. This system will continue to
provide stable atmospheric conditions across the Mid-Atlantic and
Northeast regions through the forecast period.

Temperature forecasts remain on track with model guidance, expecting
highs in the mid to upper 70s across the I-95 corridor today.

$$
</pre>
</body>
</html>
"""

MOCK_SPC_DISCUSSION = """
<html>
<head><title>SPC Day 1 Convective Outlook</title></head>
<body>
<pre>
ACUS01 KWNS 011200
SWODY1 KWNS 011200

SPC AC 011200

Day 1 Convective Outlook
NWS Storm Prediction Center Norman OK
0700 AM CST Mon Jan 01 2024

Valid 011200Z - 021200Z

...THERE IS A MARGINAL RISK OF SEVERE THUNDERSTORMS ACROSS PORTIONS
OF THE SOUTHERN PLAINS...

...SUMMARY...
Isolated severe thunderstorms are possible across portions of the
southern Plains this afternoon and evening, with primary threats
being large hail and damaging winds.

...DISCUSSION...
A weak shortwave trough will move across the southern Plains today,
providing modest upper-level divergence and lift for thunderstorm
development.

$$
</pre>
</body>
</html>
"""
