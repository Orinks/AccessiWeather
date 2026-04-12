"""Tests for NOAA radio station availability suppression cache."""

from __future__ import annotations

from accessiweather.noaa_radio.availability_cache import StationAvailabilityCache


def test_suppress_marks_station_unavailable(tmp_path):
    cache = StationAvailabilityCache(path=tmp_path / "availability.json")

    cache.suppress("WXK27", ttl_seconds=1800, reason="all_streams_failed")

    assert cache.is_suppressed("WXK27") is True
    assert cache.get_suppressed_call_signs() == ["WXK27"]


def test_suppression_expires_after_ttl(tmp_path):
    current_time = 1000.0

    def time_fn() -> float:
        return current_time

    cache = StationAvailabilityCache(path=tmp_path / "availability.json", time_fn=time_fn)
    cache.suppress("WXK27", ttl_seconds=1800, reason="all_streams_failed")

    current_time = 2801.0

    assert cache.is_suppressed("WXK27") is False
    assert cache.get_record("WXK27") is None


def test_clear_unsuppresses_station(tmp_path):
    cache = StationAvailabilityCache(path=tmp_path / "availability.json")
    cache.suppress("WXK27", ttl_seconds=1800, reason="all_streams_failed")

    cache.clear("WXK27")

    assert cache.is_suppressed("WXK27") is False
    assert cache.get_suppressed_call_signs() == []


def test_corrupt_json_fails_soft(tmp_path):
    path = tmp_path / "availability.json"
    path.write_text("{not valid json", encoding="utf-8")

    cache = StationAvailabilityCache(path=path)

    assert cache.get_suppressed_call_signs() == []
    assert cache.is_suppressed("WXK27") is False


def test_path_based_persistence_works_across_instances(tmp_path):
    path = tmp_path / "availability.json"

    first = StationAvailabilityCache(path=path, time_fn=lambda: 1000.0)
    first.suppress("wxk27", ttl_seconds=1800, reason="all_streams_failed")

    second = StationAvailabilityCache(path=path, time_fn=lambda: 1000.0)

    assert second.is_suppressed("WXK27") is True
    assert second.get_record("WXK27") == {
        "reason": "all_streams_failed",
        "expires_at": 2800.0,
    }
