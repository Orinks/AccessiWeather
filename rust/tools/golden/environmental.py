"""Golden outputs for the environmental port (Open-Meteo air quality, pollen,
hourly UV, AirNow observations and key validation).

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\environmental.py

Writes rust/testdata/golden/environmental/*.json.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provider_golden_common as common  # noqa: E402

from accessiweather.models import Location  # noqa: E402
from accessiweather.services import airnow_client, environmental_client  # noqa: E402
from accessiweather.services.airnow_client import AirNowClient  # noqa: E402
from accessiweather.services.environmental_client import EnvironmentalDataClient  # noqa: E402

AREA = "environmental"
common.freeze(environmental_client, airnow_client)
common.fast_retries()

AQ = EnvironmentalDataClient.AIR_QUALITY_ENDPOINT
POLLEN = EnvironmentalDataClient.POLLEN_ENDPOINT
UV = "https://api.open-meteo.com/v1/forecast"
AIRNOW = AirNowClient.ENDPOINT


def hours(start: str, count: int) -> list[str]:
    base = date.fromisoformat(start)
    return [f"{base + timedelta(days=h // 24)}T{h % 24:02d}:00" for h in range(count)]


def series(count: int, fn) -> list:
    return [fn(i) for i in range(count)]


# The frozen now is 2025-01-15 17:30 UTC = 12:30 at UTC-5 (index 12).
TIMES = hours("2025-01-15", 72)
AQ_BODY = {
    "utc_offset_seconds": -18000,
    "hourly": {
        "time": TIMES,
        "us_aqi": series(72, lambda i: None if i in (12, 40) else 20 + (i * 7) % 90 + 0.45),
        "us_aqi_pm2_5": series(72, lambda i: 15 + i % 40),
        "us_aqi_pm10": series(72, lambda i: 30 + (i * 3) % 50),
        "pm2_5": series(72, lambda i: 3.25 + i * 0.1),
        "pm10": series(72, lambda i: None if i % 5 == 0 else 7.15 + i),
        "ozone": series(72, lambda i: 40.05 + i),
        "nitrogen_dioxide": series(72, lambda i: 10.25),
        "sulphur_dioxide": series(72, lambda i: 1.35),
        "carbon_monoxide": series(72, lambda i: 200.45 + i),
    },
}
POLLEN_BODY = {
    "utc_offset_seconds": -18000,
    "hourly": {
        "time": TIMES,
        "tree_pollen": series(72, lambda i: 12.5 + i),
        "grass_pollen": series(72, lambda i: None),
        "weed_pollen": series(72, lambda i: 40.0 + i * 2),
    },
}
UV_BODY = {
    "utc_offset_seconds": -18000,
    "hourly": {"time": TIMES, "uv_index": series(72, lambda i: None if i == 30 else (i % 24) * 0.55)},
}
AIRNOW_BODY = [
    {
        "DateObserved": "2025-01-15",
        "HourObserved": 11,
        "LocalTimeZone": "EST",
        "ReportingArea": "Philadelphia",
        "ParameterName": "O3",
        "AQI": 42,
        "Category": {"Number": 1, "Name": "Good"},
    },
    {
        "DateObserved": "2025-01-15",
        "HourObserved": "11",
        "LocalTimeZone": "EST",
        "ReportingArea": " Philadelphia ",
        "ParameterName": "PM2.5",
        "AQI": "87",
        "Category": {"Number": 2, "Name": "Moderate"},
    },
]

FETCH_CASES = {
    "all_openmeteo": ([(AQ, 200, AQ_BODY), (POLLEN, 200, POLLEN_BODY), (UV, 200, UV_BODY)], {}, ""),
    "prefer_airnow": (
        [(AQ, 200, AQ_BODY), (POLLEN, 200, POLLEN_BODY), (UV, 200, UV_BODY), (AIRNOW, 200, AIRNOW_BODY)],
        {"prefer_airnow": True, "hourly_hours": 5},
        "airnow-key",
    ),
    "airnow_down_falls_back": (
        [(AQ, 200, AQ_BODY), (POLLEN, 200, POLLEN_BODY), (UV, 200, UV_BODY), (AIRNOW, 500, {})],
        {"prefer_airnow": True, "include_pollen": False},
        "airnow-key",
    ),
    "short_pollutant_series_drops_hourly": (
        [
            (AQ, 200, {**AQ_BODY, "hourly": {**AQ_BODY["hourly"], "ozone": [1.0, 2.0]}}),
            (UV, 200, UV_BODY),
        ],
        {"include_pollen": False, "hourly_hours": 30},
        "",
    ),
    "services_down": ([], {"include_hourly_uv": True}, ""),
    "nothing_requested": (
        [],
        {
            "include_air_quality": False,
            "include_pollen": False,
            "include_hourly_air_quality": False,
            "include_hourly_uv": False,
        },
        "",
    ),
}

AIRNOW_PARSE_CASES = {
    "documented_schema": AIRNOW_BODY,
    "live_camelcase": [
        {
            "dateObserved": "2026-07-22",
            "hourObserved": "09:00",
            "localTimeZone": "EDT",
            "reportingAreaName": "Riverline",
            "parameterName": "PM2.5",
            "nowcastAQI": 28,
            "aqiCategoryName": "Good",
        },
        {
            "dateObserved": "2026-07-22",
            "hourObserved": "09:00",
            "localTimeZone": "EDT",
            "reportingAreaName": "Riverline",
            "parameterName": "OZONE",
            "nowcastAQI": 28,
            "aqiCategoryName": "Good",
        },
    ],
    "invalid_records_derived_category": [
        {"ParameterName": "O3", "AQI": -1},
        {"ParameterName": "PM10", "AQI": None},
        {"ParameterName": "CO", "AQI": "not available"},
        {"ParameterName": "PM2.5", "AQI": 151, "Category": {}},
    ],
    "named_zone_slash_date": [
        {
            "DateObserved": "07/04/2026",
            "HourObserved": 23.0,
            "LocalTimeZone": "America/Denver",
            "ParameterName": "",
            "AQI": 301.5,
            "Category": "  ",
        }
    ],
    "bad_hour": [{"DateObserved": "2026-07-04", "HourObserved": "25", "LocalTimeZone": "HST", "AQI": 5}],
    "malformed_dict": {"a": 1},
    "malformed_list": ["bad", {"AQI": None}],
}


def main() -> None:
    common.reset(AREA)
    location = Location(name="Philadelphia", latitude=39.9526, longitude=-75.1652, country_code="US")
    for name, (routes, options, key) in FETCH_CASES.items():
        router = common.Router(routes)
        common.patch_httpx(router)
        client = EnvironmentalDataClient(user_agent="AccessiWeather/2.0", airnow_api_key=key)
        result = common.run(client.fetch(location, **options))
        common.write(
            AREA,
            f"fetch_{name}",
            {
                "now": common.now_local_iso(),
                "options": options,
                "airnow_key": key,
                "exchanges": router.exchanges(),
                "output": result,
            },
        )

    for name, payload in AIRNOW_PARSE_CASES.items():
        common.write(
            AREA,
            f"airnow_parse_{name}",
            {"input": payload, "output": AirNowClient("key")._parse_observations(payload)},
        )

    for name, route in {
        "ok": (AIRNOW, 200, []),
        "forbidden": (AIRNOW, 403, {}),
        "rate_limited": (AIRNOW, 429, {}),
        "server_error": (AIRNOW, 502, {}),
        "error_body": (AIRNOW, 200, {"WebServiceError": [{"Message": "Invalid API key"}]}),
        "unexpected_body": (AIRNOW, 200, {"x": 1}),
    }.items():
        router = common.Router([route])
        common.patch_httpx(router)
        valid, reason = common.run(AirNowClient(" key ", user_agent="AccessiWeather/2.0").validate_api_key())
        common.write(
            AREA,
            f"airnow_validate_{name}",
            {"exchanges": router.exchanges(), "valid": valid, "reason": reason},
        )


if __name__ == "__main__":
    main()
