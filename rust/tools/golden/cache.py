"""Golden outputs for the offline weather cache (cache.py + cache_serialization.py).

Writes rust/testdata/golden/cache/*.json. The stored files are captured
byte for byte so the Rust writer can be checked against json.dump(indent=2).
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from common import frozen_datetime, write

import accessiweather.cache as cache_module
import accessiweather.cache_serialization as serialization
from accessiweather.cache import CACHE_SCHEMA_VERSION, WeatherDataCache
from accessiweather.models import (
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    SourceAttribution,
    TrendInsight,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)

NOW = datetime(2026, 7, 15, 16, 0, 0, tzinfo=UTC)
EDT = timezone(timedelta(hours=-4))
IST = timezone(timedelta(hours=5, minutes=30))


def freeze(now):
    frozen = frozen_datetime(now)
    cache_module.datetime = frozen
    serialization.datetime = frozen


def rich_weather(location):
    return WeatherData(
        location=location,
        current=CurrentConditions(
            temperature_f=72.5,
            temperature_c=22.5,
            condition='Partly cloudy — café ° \U0001f326 "quoted" \\ tab\there',
            humidity=55,
            dewpoint_f=55.4,
            dewpoint_c=13.0,
            wind_speed_mph=10.0,
            wind_speed_kph=16.09344,
            wind_direction="NW",
            pressure_in=30.01,
            pressure_mb=1016.2,
            feels_like_f=None,
            visibility_miles=10.0,
            visibility_km=16.09344,
            uv_index=0.1 + 0.2,
            sunrise_time=datetime(2026, 7, 15, 5, 40, 12, 123456, tzinfo=EDT),
            sunset_time=datetime(2026, 7, 15, 20, 25, tzinfo=UTC),
            precipitation_in=3.937e-05,
            cloud_cover=40.0,
        ),
        forecast=Forecast(
            periods=[
                ForecastPeriod(
                    name="Today",
                    temperature=80.0,
                    temperature_unit="F",
                    short_forecast="Sunny",
                    detailed_forecast="Sunny, with a high near 80.\nWinds light.",
                    wind_speed="5 to 10 mph",
                    wind_direction="W",
                    icon="https://api.weather.gov/icons/land/day/few?size=medium",
                    start_time=datetime(2026, 7, 15, 6, tzinfo=EDT),
                    end_time=datetime(2026, 7, 15, 18, tzinfo=EDT),
                    precipitation_probability=20.0,
                ),
                ForecastPeriod(
                    name="Tonight",
                    temperature=-0.0,
                    start_time=datetime(2026, 7, 15, 18, tzinfo=IST),
                ),
                ForecastPeriod(name="Huge", temperature=1e16, temperature_unit="C"),
            ],
            generated_at=datetime(2026, 7, 15, 15, 30, tzinfo=UTC),
            summary="not cached",
        ),
        hourly_forecast=HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=datetime(2026, 7, 15, 12, tzinfo=EDT),
                    end_time=datetime(2026, 7, 15, 13, tzinfo=EDT),
                    temperature=78.0,
                    short_forecast="Sunny",
                    wind_speed="10 mph",
                    wind_direction="W",
                    humidity=50,
                    dewpoint_f=58.0,
                    pressure_mb=1015.0,
                    pressure_in=29.97,
                    precipitation_probability=5.0,
                ),
                HourlyForecastPeriod(
                    start_time=datetime(2026, 7, 15, 17, tzinfo=UTC), temperature=1.5e-07
                ),
            ],
            generated_at=None,
        ),
        discussion="AFD text\r\nwith ünicode and control \x01 chars \x7f",
        discussion_issuance_time=datetime(2026, 7, 15, 14, 2, tzinfo=UTC),
        alerts=WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Heat Advisory",
                    description="Hot.",
                    severity="Moderate",
                    urgency="Expected",
                    certainty="Likely",
                    event="Heat Advisory",
                    headline="Heat Advisory until 8 PM",
                    instruction="Drink water.",
                    onset=datetime(2026, 7, 15, 12, tzinfo=EDT),
                    expires=datetime(2026, 7, 15, 20, tzinfo=EDT),
                    sent=datetime(2026, 7, 15, 11, tzinfo=EDT),
                    areas=["Kings", "Queens"],
                    id="urn:oid:2.49.0.1.840.0.abc",
                    source="NWS",
                    message_type="Alert",
                    affected_zones=["NYZ075"],
                    same_codes=["036047"],
                    same_event_codes=["HTY"],
                ),
                WeatherAlert(title="Plain", description=""),
            ]
        ),
        environmental=EnvironmentalConditions(
            air_quality_index=42.0,
            air_quality_category="Good",
            air_quality_pollutant="PM2.5",
            air_quality_updated_at=datetime(2026, 7, 15, 15, tzinfo=EDT),
            pollen_index=3.5,
            sources=["AirNow", "Open-Meteo"],
            uv_index=6.0,
        ),
        trend_insights=[
            TrendInsight(
                metric="temperature",
                direction="rising",
                change=6.0,
                unit="°F",
                timeframe_hours=24,
                summary="Temperature rising +6.0°F over 24h",
                sparkline="↑↑",
            ),
            TrendInsight(metric="pressure", direction="unavailable", timeframe_hours=6),
        ],
        source_attribution=SourceAttribution(
            field_sources={"condition": "nws", "forecast_source": "nws", "humidity": "openmeteo"},
            contributing_sources={"nws"},
            failed_sources=set(),
        ),
        incomplete_sections={"hourly_forecast"},
        stale=False,
        stale_since=None,
        stale_reason=None,
    )


def store_cases():
    cases = [
        (
            "rich",
            Location(name="Brooklyn, NY", latitude=40.6782, longitude=-73.9442, country_code="us"),
            "rich",
        ),
        ("minimal", Location(name="Nowhere", latitude=0.0, longitude=-0.5), "minimal"),
        (
            "stale_flags",
            Location(name="Zürich / été", latitude=47.3769, longitude=8.5417, country_code="CH"),
            "stale",
        ),
    ]
    out = []
    for name, location, kind in cases:
        if kind == "rich":
            weather = rich_weather(location)
        elif kind == "minimal":
            weather = WeatherData(location=location)
        else:
            weather = WeatherData(
                location=location,
                current=CurrentConditions(temperature_c=-3.25, condition="Snow"),
                stale=True,
                stale_since=datetime(2026, 7, 15, 9, tzinfo=UTC),
                stale_reason="All weather sources failed",
                incomplete_sections=set(),
            )
        freeze(NOW)
        with tempfile.TemporaryDirectory() as tmp:
            cache = WeatherDataCache(Path(tmp))
            cache.store(location, weather)
            files = list(Path(tmp).glob("*.json"))
            assert len(files) == 1
            out.append(
                {
                    "name": name,
                    "now": NOW,
                    "location": location,
                    "weather": weather,
                    "file_name": files[0].name,
                    "file_text": files[0].read_bytes().decode("ascii"),
                }
            )
    write("cache", "store", out)


def payload(saved_at, weather, schema=CACHE_SCHEMA_VERSION, location=None):
    doc = {"schema_version": schema, "saved_at": saved_at, "weather": weather}
    if location is not None:
        doc["location"] = location
    return json.dumps(doc, indent=2)


def load_cases():
    loc = Location(name="Test City", latitude=40.0, longitude=-74.0)
    saved = {"iso": (NOW - timedelta(minutes=30)).isoformat()}
    old = {"iso": (NOW - timedelta(minutes=200)).isoformat()}
    named_tz_weather = {
        "current": {
            "temperature_f": 70,
            "humidity": 61,
            "condition": "Clear",
            "sunrise_time": {"iso": "2026-07-15T09:40:00+00:00", "original_tz": "America/New_York"},
            "sunset_time": {"iso": "2026-07-16T00:25:00+00:00", "utc_offset_seconds": -14400},
        },
        "forecast": {
            "periods": [
                {"name": "Today", "temperature": 80, "start_time": "2026-07-15T06:00:00-04:00"},
                {
                    "temperature": 60.5,
                    "start_time": {"iso": "2026-07-15T22:00:00+00:00", "original_tz": "Not/AZone"},
                },
                "not a dict",
            ],
            "generated_at": {"iso": "   "},
        },
        "hourly_forecast": {
            "periods": [
                {
                    "start_time": {"iso": "2026-07-15T16:00:00+00:00", "utc_offset_seconds": 19800},
                    "pressure_mb": 1012,
                },
                {"temperature": 71.0},
            ]
        },
        "alerts": {
            "alerts": [
                {"event": "Flood"},
                {"title": "Z", "areas": ["A"], "affected_zones": ["NYZ1"]},
                5,
            ]
        },
        "environmental": {"air_quality_index": None, "sources": ["x"]},
        "trend_insights": [{"metric": "pressure", "timeframe_hours": "12"}, "bad"],
        "source_attribution": {"contributing_sources": ["openmeteo"], "field_sources": {"a": "b"}},
        "incomplete_sections": ["current"],
        "stale": True,
        "stale_reason": "ignored",
        "discussion": "d",
        "discussion_issuance_time": "2026-07-15T12:00:00Z",
    }
    cases = [
        (
            "fresh",
            payload(
                saved,
                named_tz_weather,
                location={
                    "name": "Stored",
                    "latitude": 41.5,
                    "longitude": -73.25,
                    "country_code": "us",
                },
            ),
            True,
        ),
        ("fresh_strict", payload(saved, {"current": {"temperature_c": 20.0}}), False),
        ("stale_allowed", payload(old, {"current": {"temperature_c": 20.0}}), True),
        ("stale_rejected", payload(old, {"current": {"temperature_c": 20.0}}), False),
        ("legacy_saved_at_string", payload((NOW - timedelta(minutes=5)).isoformat(), {}), True),
        ("missing_saved_at", payload(None, {"discussion": "x"}), True),
        ("schema_mismatch", payload(saved, {}, schema=5), True),
        ("no_schema", json.dumps({"saved_at": saved, "weather": {}}), True),
        ("weather_not_object", payload(saved, ["x"]), True),
        ("invalid_json", "{not json", True),
    ]
    out = []
    for name, text, allow_stale in cases:
        freeze(NOW)
        with tempfile.TemporaryDirectory() as tmp:
            cache = WeatherDataCache(Path(tmp))
            path = cache._path_for_location(loc)
            path.write_text(text, encoding="utf-8")
            result = cache.load(loc, allow_stale=allow_stale)
            out.append(
                {
                    "name": name,
                    "now": NOW,
                    "allow_stale": allow_stale,
                    "file_text": text,
                    "result": result,
                    "file_kept": path.exists(),
                }
            )
    write("cache", "load", out)


def purge_cases():
    files = {
        "fresh.json": payload({"iso": (NOW - timedelta(minutes=100)).isoformat()}, {}),
        "boundary.json": payload({"iso": (NOW - timedelta(minutes=360)).isoformat()}, {}),
        "old.json": payload({"iso": (NOW - timedelta(minutes=361)).isoformat()}, {}),
        "no_saved_at.json": payload(None, {}),
        "broken.json": "{",
        "other.txt": "not json",
    }
    freeze(NOW)
    with tempfile.TemporaryDirectory() as tmp:
        for file_name, text in files.items():
            (Path(tmp) / file_name).write_text(text, encoding="utf-8")
        WeatherDataCache(Path(tmp)).purge_expired()
        remaining = sorted(p.name for p in Path(tmp).iterdir())
    write("cache", "purge", {"now": NOW, "files": files, "remaining": remaining})


def key_cases():
    locations = [
        Location(name="Home", latitude=40.0, longitude=-75.0),
        Location(name="New York, NY", latitude=40.7128, longitude=-74.006),
        Location(name="___", latitude=-33.8688, longitude=151.2093),
        Location(name="Zürich été!!", latitude=47.3769, longitude=8.5417),
        Location(name="tiny", latitude=1e-05, longitude=1e16),
    ]
    write(
        "cache",
        "keys",
        [{"location": loc, "key": serialization._safe_location_key(loc)} for loc in locations],
    )


if __name__ == "__main__":
    ZoneInfo("America/New_York")  # tzdata must be available
    store_cases()
    load_cases()
    purge_cases()
    key_cases()
