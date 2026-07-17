"""
Regression tests: air quality must reflect the *current* hour.

Open-Meteo hourly series start at local midnight and run several days into the
future. Earlier code selected the furthest-future entry (for the summary) and
index 0 / midnight (for the hourly list), so users saw a forecast hour instead
of the reading for "now". These tests lock in current-hour anchoring.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from accessiweather.models import Location
from accessiweather.models.weather_conditions import EnvironmentalConditions
from accessiweather.services.environmental_client import EnvironmentalDataClient


def _loc() -> Location:
    return Location(name="Test City", latitude=40.0, longitude=-74.0)


def _now_hour_utc() -> datetime:
    return datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


def _make_async_client(payload: dict) -> AsyncMock:
    """Build a mock that behaves like `async with httpx.AsyncClient() as c`."""
    response = SimpleNamespace(
        json=lambda: payload,
        raise_for_status=lambda: None,
    )
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ── _current_hour_index ──


class TestCurrentHourIndex:
    def test_picks_current_hour_not_last(self):
        client = EnvironmentalDataClient()
        now = _now_hour_utc().replace(tzinfo=None)
        # Series from 3h ago to 3h ahead; offset 0 => local == utc.
        times = [(now + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(-3, 4)]
        assert client._current_hour_index(times, 0) == 3

    def test_respects_utc_offset(self):
        client = EnvironmentalDataClient()
        offset = -4 * 3600  # e.g. US Eastern (EDT)
        now_local = (datetime.now(UTC) + timedelta(seconds=offset)).replace(
            minute=0, second=0, microsecond=0, tzinfo=None
        )
        times = [(now_local + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(-2, 5)]
        assert client._current_hour_index(times, offset) == 2

    def test_empty_series_returns_zero(self):
        assert EnvironmentalDataClient()._current_hour_index([], 0) == 0

    def test_all_future_falls_back_to_first(self):
        client = EnvironmentalDataClient()
        future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        times = [(future + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(3)]
        assert client._current_hour_index(times, 0) == 0


# ── _value_near ──


class TestValueNear:
    def test_direct_value(self):
        assert EnvironmentalDataClient()._value_near([10, 20, 30], 1) == 20.0

    def test_skips_none_forward(self):
        assert EnvironmentalDataClient()._value_near([10, None, 30], 1) == 30.0

    def test_falls_back_behind(self):
        assert EnvironmentalDataClient()._value_near([10, 20, None], 2) == 20.0

    def test_all_none_returns_none(self):
        assert EnvironmentalDataClient()._value_near([None, None], 0) is None

    def test_empty_returns_none(self):
        assert EnvironmentalDataClient()._value_near([], 0) is None


# ── _drop_past_hours ──


class TestDropPastHours:
    def test_drops_past_entries(self):
        now = _now_hour_utc()
        entries = [
            SimpleNamespace(timestamp=now - timedelta(hours=2)),
            SimpleNamespace(timestamp=now - timedelta(hours=1)),
            SimpleNamespace(timestamp=now),
            SimpleNamespace(timestamp=now + timedelta(hours=1)),
        ]
        result = EnvironmentalDataClient()._drop_past_hours(entries)
        assert len(result) == 2
        assert result[0].timestamp == now

    def test_all_past_keeps_original(self):
        now = _now_hour_utc()
        entries = [SimpleNamespace(timestamp=now - timedelta(hours=3))]
        assert EnvironmentalDataClient()._drop_past_hours(entries) == entries

    def test_naive_timestamps_treated_as_utc(self):
        now = _now_hour_utc().replace(tzinfo=None)
        entries = [
            SimpleNamespace(timestamp=now - timedelta(hours=1)),
            SimpleNamespace(timestamp=now + timedelta(hours=1)),
        ]
        result = EnvironmentalDataClient()._drop_past_hours(entries)
        assert len(result) == 1


# ── fetch_hourly_air_quality (full path) ──


@pytest.mark.asyncio
class TestFetchHourlyAirQuality:
    def _payload(self):
        """Series from local midnight through +2 days; distinctive per-hour AQI."""
        midnight = _now_hour_utc().replace(hour=0)
        now = _now_hour_utc()
        hours_since_midnight = int((now - midnight).total_seconds() // 3600)
        times = []
        aqi = []
        for h in range(72):
            ts = midnight + timedelta(hours=h)
            times.append(ts.strftime("%Y-%m-%dT%H:%M"))
            # Current hour=99 (distinctive); other hours=50; far future=200.
            aqi.append(99 if h == hours_since_midnight else 50)
        aqi[-1] = 200  # what the old "latest" logic would have surfaced
        return {"utc_offset_seconds": 0, "hourly": {"time": times, "us_aqi": aqi}}, now

    async def test_list_starts_at_current_hour(self):
        payload, now = self._payload()
        client = EnvironmentalDataClient()
        with patch(
            "accessiweather.services.environmental_client.httpx.AsyncClient",
            return_value=_make_async_client(payload),
        ):
            result = await client.fetch_hourly_air_quality(_loc(), hours=24)

        assert result is not None
        # entry[0] is "now", not an earlier hour and not the far-future peak.
        assert result[0]["timestamp"].strftime("%H") == now.strftime("%H")
        assert result[0]["aqi"] == 99
        assert result[0]["aqi"] != 200  # not the far-future entry

    async def test_timestamps_are_timezone_aware_and_correct_instant(self):
        """Timestamps carry the location's offset (not naive/mislabelled-UTC)."""
        offset = -4 * 3600  # e.g. US Eastern (EDT)
        now_local = (datetime.now(UTC) + timedelta(seconds=offset)).replace(
            minute=0, second=0, microsecond=0, tzinfo=None
        )
        times = [(now_local + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(6)]
        aqi = [50] * 6
        payload = {"utc_offset_seconds": offset, "hourly": {"time": times, "us_aqi": aqi}}

        client = EnvironmentalDataClient()
        with patch(
            "accessiweather.services.environmental_client.httpx.AsyncClient",
            return_value=_make_async_client(payload),
        ):
            result = await client.fetch_hourly_air_quality(_loc(), hours=6)

        ts = result[0]["timestamp"]
        # Aware, with the location's offset attached.
        assert ts.tzinfo is not None
        assert ts.utcoffset() == timedelta(seconds=offset)
        # Local wall-clock renders as the location's time...
        assert ts.strftime("%H:%M") == now_local.strftime("%H:%M")
        # ...and converts to the correct UTC instant.
        assert ts.astimezone(UTC).hour == (now_local.hour - offset // 3600) % 24


# ── _populate_air_quality (summary) ──


@pytest.mark.asyncio
class TestPopulateAirQuality:
    async def test_summary_uses_current_hour(self):
        midnight = _now_hour_utc().replace(hour=0)
        now = _now_hour_utc()
        hours_since_midnight = int((now - midnight).total_seconds() // 3600)
        times, aqi, pm25, pm10 = [], [], [], []
        for h in range(72):
            ts = midnight + timedelta(hours=h)
            times.append(ts.strftime("%Y-%m-%dT%H:%M"))
            aqi.append(88 if h == hours_since_midnight else 40)
            pm25.append(70 if h == hours_since_midnight else 10)
            pm10.append(20 if h == hours_since_midnight else 5)
        aqi[-1] = 300  # far-future value the old code would have picked

        payload = {
            "utc_offset_seconds": 0,
            "hourly": {
                "time": times,
                "us_aqi": aqi,
                "us_aqi_pm2_5": pm25,
                "us_aqi_pm10": pm10,
            },
        }

        client = EnvironmentalDataClient()
        env = EnvironmentalConditions()
        mock_client = _make_async_client(payload)
        await client._populate_air_quality(mock_client, {}, env)

        assert env.air_quality_index == 88  # current hour, not 300
        assert env.air_quality_category == "Moderate"
        assert env.air_quality_pollutant == "PM2_5"  # dominant at the current hour
