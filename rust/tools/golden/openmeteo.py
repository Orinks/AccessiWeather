"""Golden outputs for the Open-Meteo port (parsers, NWS-shaped mapper, fetch URLs).

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\openmeteo.py

Writes rust/testdata/golden/openmeteo/{parse_*,fetch_*}.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
import provider_golden_common as common  # noqa: E402

from accessiweather import (  # noqa: E402
    openmeteo_client,
    openmeteo_forecast_mapper,
    openmeteo_mapper,
    weather_client_openmeteo,
    weather_client_openmeteo_current,
)
from accessiweather.models import Location  # noqa: E402
from accessiweather.weather_client_parsers import degrees_to_cardinal  # noqa: E402

AREA = "openmeteo"

common.freeze(
    weather_client_openmeteo,
    weather_client_openmeteo_current,
    openmeteo_mapper,
    openmeteo_forecast_mapper,
)
common.fast_retries()


def parse_all(body: dict) -> dict:
    current = weather_client_openmeteo_current.parse_openmeteo_current_conditions(body)
    if isinstance(current.wind_direction, int | float):
        current.wind_direction = degrees_to_cardinal(current.wind_direction)
    mapper = openmeteo_mapper.OpenMeteoMapper()
    return {
        "input": body,
        "now": common.now_local_iso(),
        "current": current,
        "forecast": weather_client_openmeteo.parse_openmeteo_forecast(body),
        "hourly": weather_client_openmeteo.parse_openmeteo_hourly_forecast(body),
        "mapped_current": mapper.map_current_conditions(body),
        "mapped_forecast": mapper.map_forecast(body),
        "mapped_hourly": mapper.map_hourly_forecast(body),
        "hourly_uv": mapper.map_hourly_uv_index(body),
    }


def daily_payload(start: str, days: int, offset: int | None) -> dict:
    from datetime import date, timedelta

    base = date.fromisoformat(start)
    return {
        "utc_offset_seconds": offset,
        "daily": {
            "time": [(base + timedelta(days=i)).isoformat() for i in range(days)],
            "temperature_2m_max": [20.0 + i for i in range(days)],
            "weather_code": [1] * days,
        },
    }


SYNTHETIC: dict[str, dict] = {
    "bst_daily": daily_payload("2026-03-27", 7, 3600),
    "india_daily": daily_payload("2026-01-10", 3, 19800),
    "nzdt_daily": daily_payload("2026-01-10", 3, 46800),
    "argentina_daily": daily_payload("2026-01-10", 3, -10800),
    "no_offset_daily": daily_payload("2026-01-10", 3, None),
    "current_drizzle_snow_code": {
        "utc_offset_seconds": -18000,
        "current": {
            "time": "2026-01-10T08:00",
            "temperature_2m": 33.0,
            "relative_humidity_2m": 92,
            "apparent_temperature": 27.0,
            "weather_code": 71,
            "wind_speed_10m": 9.0,
            "wind_direction_10m": 20,
            "pressure_msl": 1004.2,
            "precipitation": 0.01,
            "rain": 0.01,
            "showers": 0.0,
            "snowfall": 0.0,
            "snow_depth": 0.02,
            "visibility": 12000.0,
            "uv_index": None,
        },
        "current_units": {
            "temperature_2m": "°F",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mp/h",
            "pressure_msl": "hPa",
            "precipitation": "inch",
            "snow_depth": "m",
            "visibility": "m",
        },
        "daily": {
            "sunrise": ["2026-01-10T07:18"],
            "sunset": ["2026-01-10T16:52"],
            "uv_index_max": [1.35],
        },
    },
    "current_mixed_precip": {
        "current": {
            "temperature_2m": 32.0,
            "relative_humidity_2m": 90,
            "weather_code": 3,
            "rain": 0.02,
            "showers": 0.01,
            "snowfall": 0.03,
            "wind_direction_10m": 359,
            "pressure_msl": 1000,
        },
        "current_units": {"temperature_2m": "°F", "pressure_msl": "hPa", "snow_depth": "m"},
        "daily": {"sunrise": [], "sunset": [], "uv_index_max": []},
    },
    "current_celsius_units_hot": {
        "utc_offset_seconds": 7200,
        "current": {
            "time": "2026-07-01T15:00",
            "temperature_2m": 35.0,
            "relative_humidity_2m": 18,
            "apparent_temperature": 41.0,
            "weather_code": 0,
            "wind_speed_10m": 12.0,
            "wind_direction_10m": 225,
            "pressure_msl": 1011.0,
            "precipitation": 0.0,
            "visibility": 24140.0,
            "uv_index": 9.1,
        },
        "current_units": {
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "wind_speed_10m": "km/h",
            "pressure_msl": "hPa",
            "precipitation": "mm",
            "visibility": "m",
        },
    },
    "current_visibility_ft": {
        "current": {
            "temperature_2m": 41.0,
            "relative_humidity_2m": 95,
            "apparent_temperature": 39.0,
            "weather_code": 3,
            "wind_speed_10m": 8.0,
            "wind_direction_10m": 180,
            "pressure_msl": 1010,
            "rain": 0.0,
            "showers": 0.0,
            "snowfall": 0.0,
            "snow_depth": 0.5,
            "visibility": 2640.0,
        },
        "current_units": {
            "temperature_2m": "°F",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
            "snow_depth": "ft",
            "visibility": "ft",
        },
        "daily": {"sunrise": [], "sunset": [], "uv_index_max": []},
    },
    "hourly_unit_metadata": {
        "utc_offset_seconds": 0,
        "hourly": {
            "time": ["2026-03-19T12:00", "2026-03-19T13:00"],
            "temperature_2m": [72.0, 20.0],
            "relative_humidity_2m": [55, 80],
            "dew_point_2m": [None, 15.5],
            "weather_code": [1, 999],
            "wind_speed_10m": [16.0934, None],
            "wind_direction_10m": [180, 350],
            "pressure_msl": [1015.0, 1016.5],
            "precipitation_probability": [20, 5],
            "snowfall": [0.0, 0.1],
            "uv_index": [4.0, 0.0],
            "snow_depth": [0.5, None],
            "freezing_level_height": [6500.0, 900.0],
            "visibility": [52800.0, 1200.0],
            "apparent_temperature": [72.0, 12.0],
            "is_day": [1, 0],
        },
        "hourly_units": {
            "temperature_2m": "°F",
            "wind_speed_10m": "km/h",
            "pressure_msl": "hPa",
            "snow_depth": "ft",
            "freezing_level_height": "ft",
            "visibility": "ft",
        },
    },
    "mapper_daily_pairs": {
        "utc_offset_seconds": 36000,
        "daily": {
            "time": ["2026-02-01", "2026-02-02", "2026-02-03"],
            "weather_code": [61, 2, 95],
            "temperature_2m_max": [81.6, 79.2, 77.0],
            "temperature_2m_min": [70.4, None, 68.9],
            "wind_speed_10m_max": [14.7, 0.0, 22],
            "wind_direction_10m_dominant": [100, 200, None],
            "precipitation_sum": [0.254, 0.0, 1.5],
        },
        "daily_units": {
            "temperature_2m_max": "°F",
            "temperature_2m_min": "°F",
            "wind_speed_10m_max": "mp/h",
            "precipitation_sum": "inch",
        },
    },
    "mapper_z_dates_short_series": {
        "utc_offset_seconds": 0,
        "daily": {
            "time": ["2026-02-01T00:00Z", "2026-02-02"],
            "weather_code": [3],
            "temperature_2m_max": [50],
            "temperature_2m_min": [40],
            "wind_speed_10m_max": [5],
        },
    },
}


FETCH_BASE = "https://api.open-meteo.com/v1"


async def fetch_case(name: str, coro_factory, body: dict) -> None:
    router = common.Router([(FETCH_BASE, 200, body)])
    common.patch_httpx(router)
    async with httpx.AsyncClient() as client:
        result = await coro_factory(client)
    common.write(
        AREA,
        f"fetch_{name}",
        {"now": common.now_local_iso(), "exchanges": router.exchanges(), "output": result},
    )


def main() -> None:
    common.reset(AREA)
    bodies = common.unique_bodies(
        [
            "openmeteo/current_weather_nyc.yaml",
            "openmeteo/current_weather_celsius.yaml",
            "openmeteo/current_weather_london.yaml",
            "openmeteo/current_weather_alaska.yaml",
            "openmeteo/current_weather_with_uv.yaml",
            "openmeteo/forecast_daily.yaml",
            "openmeteo/forecast_alaska.yaml",
            "openmeteo/forecast_extended.yaml",
            "openmeteo/hourly_forecast.yaml",
            "weather_client/openmeteo_current.yaml",
            "weather_client/openmeteo_forecast.yaml",
        ],
        host="api.open-meteo.com",
    )
    for name, body in bodies:
        common.write(AREA, f"parse_{name}", parse_all(body))
    for name, body in SYNTHETIC.items():
        common.write(AREA, f"parse_{name}", parse_all(body))

    nyc = Location(name="New York", latitude=40.7128, longitude=-74.006)
    london = Location(name="London", latitude=51.5074, longitude=-0.1278)
    current_body = dict(bodies[0][1])
    forecast_body = next(b for n, b in bodies if n.startswith("forecast_daily"))
    hourly_body = next(b for n, b in bodies if n.startswith("hourly_forecast"))

    wc = weather_client_openmeteo
    common.run(
        fetch_case(
            "current_best_match",
            lambda c: wc.get_openmeteo_current_conditions(nyc, FETCH_BASE, 10.0, c, "best_match"),
            current_body,
        )
    )
    common.run(
        fetch_case(
            "forecast_model_clamped",
            lambda c: wc.get_openmeteo_forecast(london, FETCH_BASE, 10.0, c, days=30, model="icon_seamless"),
            forecast_body,
        )
    )
    common.run(
        fetch_case(
            "hourly_min_clamped",
            lambda c: wc.get_openmeteo_hourly_forecast(nyc, FETCH_BASE, 10.0, c, "best_match", hours=0),
            hourly_body,
        )
    )

    # Dict client (weather service path): URL shape with repeated list params.
    router = common.Router([(FETCH_BASE, 200, {"ok": True})])
    common.patch_httpx(router)
    client = openmeteo_client.OpenMeteoApiClient()
    client.get_current_weather(40.7128, -74.006)
    client.get_forecast(40.0, -74.0, days=20, temperature_unit="celsius", model="gfs_seamless")
    client.get_hourly_forecast(51.5, -0.12, hours=500, wind_speed_unit="kmh", precipitation_unit="mm")
    common.write(AREA, "fetch_dict_client_urls", {"exchanges": router.exchanges()})


if __name__ == "__main__":
    main()
