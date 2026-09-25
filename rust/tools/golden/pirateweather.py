"""Golden outputs for the Pirate Weather port (parsers per unit bundle, alerts,
minutely precipitation, beach conditions) and the Open-Meteo Marine surf
summary.

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\pirateweather.py

Writes rust/testdata/golden/pirateweather/*.json.
"""

from __future__ import annotations

import copy
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provider_golden_common as common  # noqa: E402

from accessiweather import (  # noqa: E402
    pirate_weather_client,
    pirate_weather_current,
    pirate_weather_parsing,
    surf_conditions,
)
from accessiweather.models import Location  # noqa: E402
from accessiweather.notifications.minutely_precipitation import (  # noqa: E402
    parse_pirate_weather_minutely_block,
)
from accessiweather.pirate_weather_client import PirateWeatherClient  # noqa: E402

AREA = "pirateweather"
common.freeze(pirate_weather_client, pirate_weather_current, pirate_weather_parsing, surf_conditions)
common.fast_retries()

SAMPLE = {
    "latitude": 40.7128,
    "longitude": -74.006,
    "timezone": "America/New_York",
    "offset": -5,
    "currently": {
        "time": 1700000000,
        "summary": "Partly Cloudy",
        "icon": "partly-cloudy-day",
        "temperature": 68.0,
        "apparentTemperature": 66.5,
        "humidity": 0.65,
        "dewPoint": 55.0,
        "windSpeed": 10.0,
        "windGust": 18.0,
        "windBearing": 180,
        "pressure": 1013.0,
        "uvIndex": 3,
        "cloudCover": 0.45,
        "visibility": 10.0,
        "precipIntensity": 0.0,
        "precipType": ["rain", "Snow", "none"],
    },
    "minutely": {
        "summary": "Rain starting in 10 min.",
        "icon": "rain",
        "data": [
            {"time": 1700000060, "precipIntensity": 0.0, "precipProbability": 0.0},
            {"time": 1700000120, "precipIntensity": 0.02, "precipProbability": 0.6,
             "precipType": "Rain", "precipIntensityError": 0.01},
            {"time": "bad"},
            "junk",
        ],
    },
    "hourly": {
        "summary": "Cloudy until evening.",
        "data": [
            {
                "time": 1700000000,
                "summary": "Partly Cloudy",
                "icon": "partly-cloudy-day",
                "temperature": 68.0,
                "apparentTemperature": 66.5,
                "humidity": 0.65,
                "dewPoint": 55.0,
                "windSpeed": 10.5,
                "windGust": 18.0,
                "windBearing": 180,
                "pressure": 1013.0,
                "uvIndex": 3,
                "cloudCover": 0.45,
                "visibility": 10.0,
                "precipIntensity": 0.3,
                "precipProbability": 0.1,
                "precipAccumulation": 0.12,
                "liquidAccumulation": 0.1,
                "snowAccumulation": 0.0,
            },
            {
                "time": 1700003600,
                "icon": "sleet",
                "temperature": 34.0,
                "humidity": 0.9,
                "windSpeed": None,
                "precipType": "sleet",
            },
            {"summary": "", "precipType": ["freezing-rain"]},
        ],
    },
    "daily": {
        "summary": "Mixed precipitation this week.",
        "data": [
            {
                "time": 1699938000,
                "summary": "Mostly cloudy throughout the day.",
                "icon": "cloudy",
                "sunriseTime": 1699962000,
                "sunsetTime": 1699998000,
                "moonPhase": 0.52,
                "temperatureHigh": 75.0,
                "temperatureLow": 55.0,
                "temperatureMax": 76.0,
                "temperatureMin": 54.0,
                "windSpeed": 8.5,
                "windGust": 14.0,
                "windBearing": 200,
                "uvIndex": 4,
                "cloudCover": 0.6,
                "precipProbability": 0.205,
                "precipIntensity": 0.01,
                "precipAccumulation": 0.3,
                "snowAccumulation": 1.2,
            },
            {
                "time": 1700024400,
                "icon": "mixed",
                "temperatureMax": 50.0,
                "temperatureMin": 30.0,
                "windSpeed": 2.5,
                "precipType": "mixed",
            },
            {
                "time": 1700110800,
                "precipType": ["snow", "ice"],
                "temperatureHigh": 40.0,
                "temperatureLow": 20.0,
            },
        ],
    },
    "alerts": [
        {
            "title": "Winter Storm Warning",
            "severity": "severe",
            "time": 1700000000,
            "expires": 1700050000,
            "description": "Heavy snow expected.",
            "uri": "https://alerts.weather.gov/cap/123",
            "regions": [" New York ", "", "Hudson Valley"],
        },
        {"title": "Wind Advisory", "severity": "advisory", "time": 1700000000},
        {"title": "", "severity": "EXTREME", "time": 1700000000, "expires": -999},
    ],
}

LONDON_DST = {
    "timezone": "Europe/London",
    "offset": 1,
    "daily": {
        "data": [
            {
                "time": int(datetime(2025, 10, 26 + i, 0, 0, tzinfo=UTC).timestamp()),
                "temperatureHigh": 60.0 + i,
                "temperatureLow": 45.0 + i,
                "summary": "Cloudy",
            }
            for i in range(3)
        ]
    },
}

LONDON_DUPLICATE = {
    "timezone": "Europe/London",
    "offset": 1,
    "daily": {
        "data": [
            {
                "time": int(datetime(2025, 10, 25 + i, 23, 0, tzinfo=UTC).timestamp()),
                "temperatureHigh": 60.0 + i,
                "summary": "Cloudy",
            }
            for i in range(3)
        ]
    },
}

FIXED_OFFSET_UNKNOWN_ZONE = {
    "timezone": "Mars/Olympus_Mons",
    "offset": 5.5,
    "currently": {"time": 1700000000, "temperature": 20.0, "humidity": 0.4},
    "daily": {"data": [{"time": 1699900000, "sunriseTime": 1699920000, "sunsetTime": 0}]},
    "hourly": {"data": [{"time": 1700000000, "temperature": 20.0}]},
}


def parse_all(body: dict, units: str) -> dict:
    client = PirateWeatherClient(api_key="k", units=units)
    location = Location(name="Beach", latitude=40.0, longitude=-74.0)
    return {
        "units": units,
        "input": body,
        "now": common.now_local_iso(),
        "current": client._parse_current_conditions(body),
        "forecast": client._parse_forecast(body),
        "hourly": client._parse_hourly_forecast(body),
        "alerts": client._parse_alerts(body),
        "minutely": parse_pirate_weather_minutely_block(body, units=client.units),
        "beach": common.run(beach(body, location)),
    }


async def beach(body: dict, location: Location):
    class Stub:
        async def get_forecast_data(self, _location):
            return body

    class Weather:
        pirate_weather_client = Stub()

    return await surf_conditions.fetch_pirate_weather_beach_conditions(location, Weather())


MARINE_CASES = {
    "full": {
        "current": {
            "time": "2026-06-07T12:00",
            "wave_height": 1.4,
            "wave_direction": 270,
            "wave_period": 8,
            "swell_wave_height": [0.9],
            "swell_wave_direction": "250",
            "swell_wave_period": 11,
            "sea_surface_temperature": 18.55,
        },
        "current_units": {
            "wave_height": "m",
            "wave_period": "s",
            "swell_wave_height": "m",
            "swell_wave_period": "s",
            "sea_surface_temperature": "°C",
        },
    },
    "utc_time_text_direction": {
        "current": {"time": "2026-06-07T12:00Z", "wave_height": 2.0, "wave_direction": "offshore"},
    },
    "empty_values": {"current": {"time": "2026-06-07T12:00", "wave_height": None, "wave_period": []}},
    "bad_time": {"current": {"time": "not-a-time", "wave_height": 0.25}, "current_units": []},
    "no_current": {"hourly": {}},
}


def main() -> None:
    common.reset(AREA)
    bodies = common.unique_bodies(
        [f"pirate_weather/{n}.yaml" for n in (
            "current_nyc", "current_london", "current_wind_gust", "alerts_nyc", "alerts_tromso",
            "forecast_daily_summary", "forecast_nyc", "hourly_nyc", "minutely_nyc",
        )]
    )
    for name, body in bodies:
        common.write(AREA, f"parse_{name}_us", parse_all(body, "us"))
    for units in ("us", "si", "ca", "uk"):
        common.write(AREA, f"parse_sample_{units}", parse_all(copy.deepcopy(SAMPLE), units))
    common.write(AREA, "parse_london_dst", parse_all(LONDON_DST, "uk"))
    common.write(AREA, "parse_london_duplicate_dates", parse_all(LONDON_DUPLICATE, "uk"))
    common.write(AREA, "parse_fixed_offset_unknown_zone", parse_all(FIXED_OFFSET_UNKNOWN_ZONE, "si"))

    location = Location(name="Porto", latitude=41.15, longitude=-8.63, country_code="PT")
    for name, body in MARINE_CASES.items():
        report = surf_conditions.format_openmeteo_marine_report(body, location)
        common.write(
            AREA,
            f"marine_{name}",
            {
                "input": body,
                "now": common.now_local_iso(),
                "product": report.to_text_product() if report else None,
            },
        )

    # Request shape and HTTP error messages.
    nyc = Location(name="NYC", latitude=40.7128, longitude=-74.006)
    for status in (200, 400, 401, 429, 503):
        router = common.Router([("https://api.pirateweather.net/", status, bodies[0][1] if status == 200 else {})])
        common.patch_httpx(router)
        client = PirateWeatherClient(api_key="secret", user_agent="AccessiWeather/2.0", units="uk")
        try:
            result = common.run(client.get_current_conditions(nyc))
            error = None
        except pirate_weather_client.PirateWeatherApiError as exc:
            result, error = None, {"message": exc.message, "status_code": exc.status_code}
        common.write(
            AREA,
            f"fetch_status_{status}",
            {"exchanges": router.exchanges(), "output": result, "error": error},
        )

    router = common.Router(
        [("https://marine-api.open-meteo.com/", 200, MARINE_CASES["full"])]
    )
    common.patch_httpx(router)
    product = common.run(surf_conditions.fetch_openmeteo_marine_surf_conditions(location))
    common.write(AREA, "fetch_marine", {"exchanges": router.exchanges(), "output": product})


if __name__ == "__main__":
    main()
