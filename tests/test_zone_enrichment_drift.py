"""
Tests for zone-metadata drift correction on weather refresh (Unit 3).

Covers the seven scenarios enumerated in the Forecast Products PR 1 plan:

1. Stored field null + fresh non-null -> diff returns that field; update persists.
2. Stored and fresh both non-null and equal -> no update, no persist.
3. Stored and fresh both non-null and differ -> diff returns changed field; overwrite.
4. Stored non-null + fresh null/missing -> diff returns empty; stored value preserved.
5. Stored all six null + fresh all six present -> all six populated in one call.
6. /points raises -> drift skipped silently; refresh not broken; no persist.
7. Drift write from refresh thread is bounced via wx.CallAfter to the main thread.
"""

from __future__ import annotations

import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.config.config_manager import ConfigManager
from accessiweather.config.locations import LocationOperations
from accessiweather.models import AppConfig, AppSettings, Location
from accessiweather.services.zone_enrichment_service import (
    diff_zone_fields,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

FULL_FRESH_FIELDS = {
    "timezone": "America/New_York",
    "cwa_office": "PHI",
    "forecast_zone_id": "PAZ106",
    "county_zone_id": "PAC091",
    "fire_zone_id": "PAZ106",
    "radar_station": "KDIX",
}

FULL_POINTS_PROPERTIES = {
    "cwa": "PHI",
    "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
    "county": "https://api.weather.gov/zones/county/PAC091",
    "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
    "radarStation": "KDIX",
    "timeZone": "America/New_York",
}


class _FakeConfigManager:
    """Minimal stand-in for ``ConfigManager`` used by LocationOperations tests."""

    def __init__(self, locations: list[Location] | None = None) -> None:
        self.save_calls = 0
        self._config = AppConfig(
            settings=AppSettings(),
            locations=list(locations) if locations else [],
            current_location=None,
        )

    def get_config(self) -> AppConfig:
        return self._config

    def save_config(self) -> bool:
        self.save_calls += 1
        return True

    def _get_logger(self) -> logging.Logger:
        return logging.getLogger("accessiweather.config.test")


def _us_location(**overrides) -> Location:
    """Build a US location with optional zone-field overrides."""
    base = {
        "name": "Philadelphia, PA",
        "latitude": 39.95,
        "longitude": -75.16,
        "country_code": "US",
    }
    base.update(overrides)
    return Location(**base)


# ---------------------------------------------------------------------------
# Scenarios 1-5: diff_zone_fields pure-data behaviour
# ---------------------------------------------------------------------------


class TestDiffZoneFieldsPopulateNull:
    """Scenario 1: stored null + fresh non-null -> diff returns that field."""

    def test_single_null_field_populated_from_fresh(self):
        stored = _us_location(cwa_office="PHI")  # all others null
        fresh = {
            "timezone": "America/New_York",
            "cwa_office": "PHI",
            "forecast_zone_id": None,
            "county_zone_id": None,
            "fire_zone_id": None,
            "radar_station": None,
        }

        changes = diff_zone_fields(stored, fresh)

        assert changes == {"timezone": "America/New_York"}


class TestDiffZoneFieldsNoChangeWhenEqual:
    """Scenario 2: stored and fresh both non-null and equal -> no update."""

    def test_no_changes_when_all_fields_match(self):
        stored = _us_location(**FULL_FRESH_FIELDS)
        fresh = dict(FULL_FRESH_FIELDS)

        changes = diff_zone_fields(stored, fresh)

        assert changes == {}


class TestDiffZoneFieldsOverwriteOnChange:
    """Scenario 3: stored and fresh both non-null and differ -> diff overwrites."""

    def test_single_field_overwritten_when_fresh_differs(self):
        stored = _us_location(cwa_office="PHI", forecast_zone_id="PAZ106")
        fresh = {
            "timezone": None,
            "cwa_office": "LWX",  # <-- boundary change
            "forecast_zone_id": "PAZ106",
            "county_zone_id": None,
            "fire_zone_id": None,
            "radar_station": None,
        }

        changes = diff_zone_fields(stored, fresh)

        assert changes == {"cwa_office": "LWX"}


class TestDiffZoneFieldsFreshNullPreserved:
    """Scenario 4: stored non-null + fresh null/missing -> stored value preserved."""

    def test_fresh_null_does_not_overwrite_populated_stored_value(self):
        stored = _us_location(
            cwa_office="PHI",
            forecast_zone_id="PAZ106",
            timezone="America/New_York",
        )
        fresh = {
            "timezone": None,
            "cwa_office": None,
            "forecast_zone_id": None,
            "county_zone_id": None,
            "fire_zone_id": None,
            "radar_station": None,
        }

        changes = diff_zone_fields(stored, fresh)

        assert changes == {}

    def test_fresh_missing_keys_do_not_overwrite_stored(self):
        stored = _us_location(
            cwa_office="PHI",
            forecast_zone_id="PAZ106",
        )
        # fresh dict omits half the keys entirely
        fresh = {"cwa_office": "PHI"}

        changes = diff_zone_fields(stored, fresh)

        assert changes == {}


class TestDiffZoneFieldsLegacyLocationFirstRefresh:
    """Scenario 5: stored all six null + fresh all six present -> all populated."""

    def test_legacy_location_populates_all_fields_from_fresh(self):
        stored = _us_location()  # all six zone fields null
        fresh = dict(FULL_FRESH_FIELDS)

        changes = diff_zone_fields(stored, fresh)

        assert changes == FULL_FRESH_FIELDS
        assert set(changes.keys()) == {
            "timezone",
            "cwa_office",
            "forecast_zone_id",
            "county_zone_id",
            "fire_zone_id",
            "radar_station",
        }


# ---------------------------------------------------------------------------
# update_zone_metadata persistence
# ---------------------------------------------------------------------------


class TestUpdateZoneMetadata:
    """LocationOperations.update_zone_metadata mutates + persists via save_config."""

    def test_applies_changes_and_persists(self):
        stored = _us_location()  # all null
        manager = _FakeConfigManager(locations=[stored])
        ops = LocationOperations(cast(ConfigManager, manager))

        ok = ops.update_zone_metadata("Philadelphia, PA", dict(FULL_FRESH_FIELDS))

        assert ok is True
        assert manager.save_calls == 1
        updated = manager.get_config().locations[0]
        assert updated.timezone == "America/New_York"
        assert updated.cwa_office == "PHI"
        assert updated.forecast_zone_id == "PAZ106"
        assert updated.county_zone_id == "PAC091"
        assert updated.fire_zone_id == "PAZ106"
        assert updated.radar_station == "KDIX"
        # Identity fields untouched
        assert updated.name == "Philadelphia, PA"
        assert updated.latitude == pytest.approx(39.95)

    def test_updates_current_location_pointer_when_same_location(self):
        stored = _us_location()
        manager = _FakeConfigManager(locations=[stored])
        manager._config.current_location = stored
        ops = LocationOperations(cast(ConfigManager, manager))

        ok = ops.update_zone_metadata("Philadelphia, PA", {"cwa_office": "PHI"})

        assert ok is True
        # current_location should reflect the new fields as well
        current = manager.get_config().current_location
        assert current is not None
        assert current.cwa_office == "PHI"

    def test_returns_false_when_location_not_found(self):
        manager = _FakeConfigManager(locations=[_us_location()])
        ops = LocationOperations(cast(ConfigManager, manager))

        ok = ops.update_zone_metadata("Does Not Exist", {"cwa_office": "PHI"})

        assert ok is False
        assert manager.save_calls == 0

    def test_empty_fields_dict_is_noop(self):
        stored = _us_location(cwa_office="PHI")
        manager = _FakeConfigManager(locations=[stored])
        ops = LocationOperations(cast(ConfigManager, manager))

        ok = ops.update_zone_metadata("Philadelphia, PA", {})

        # Idempotent: nothing to persist, treat as success (no change).
        assert ok is False
        assert manager.save_calls == 0

    def test_idempotent_when_values_unchanged(self):
        stored = _us_location(cwa_office="PHI")
        manager = _FakeConfigManager(locations=[stored])
        ops = LocationOperations(cast(ConfigManager, manager))

        # Re-apply the same value — cheap, should not corrupt anything.
        ok = ops.update_zone_metadata("Philadelphia, PA", {"cwa_office": "PHI"})

        # We still persist (caller already filtered via diff); either result is
        # acceptable as long as the field ends up correct.
        assert ok is True
        assert manager.get_config().locations[0].cwa_office == "PHI"


# ---------------------------------------------------------------------------
# Drift hook wiring in weather_client_nws
# ---------------------------------------------------------------------------


class TestWeatherClientDriftHook:
    """Scenario 7: drift hook runs in the refresh path and uses wx.CallAfter."""

    def test_drift_hook_calls_wx_callafter_with_update_zone_metadata(self):
        """After /points succeeds and diff produces changes, wx.CallAfter is invoked."""
        from accessiweather import weather_client_nws

        stored = _us_location()  # legacy: all zone fields null
        manager = _FakeConfigManager(locations=[stored])
        ops = LocationOperations(cast(ConfigManager, manager))

        # Install sink pointing at our ops
        weather_client_nws.set_zone_drift_sink(ops)
        try:
            with patch.object(weather_client_nws, "wx") as mock_wx:
                weather_client_nws._apply_zone_drift_correction(
                    stored, {"properties": FULL_POINTS_PROPERTIES}
                )
                mock_wx.CallAfter.assert_called_once()
                args, _ = mock_wx.CallAfter.call_args
                callable_arg, location_name, fields_dict = args[0], args[1], args[2]
                # The callable should be the bound update_zone_metadata
                assert callable_arg == ops.update_zone_metadata
                assert location_name == "Philadelphia, PA"
                assert fields_dict == FULL_FRESH_FIELDS
        finally:
            weather_client_nws.set_zone_drift_sink(None)

    def test_drift_hook_noop_when_no_changes(self):
        """Equal stored + fresh produces no wx.CallAfter invocation."""
        from accessiweather import weather_client_nws

        stored = _us_location(**FULL_FRESH_FIELDS)
        manager = _FakeConfigManager(locations=[stored])
        ops = LocationOperations(cast(ConfigManager, manager))

        weather_client_nws.set_zone_drift_sink(ops)
        try:
            with patch.object(weather_client_nws, "wx") as mock_wx:
                weather_client_nws._apply_zone_drift_correction(
                    stored, {"properties": FULL_POINTS_PROPERTIES}
                )
                mock_wx.CallAfter.assert_not_called()
        finally:
            weather_client_nws.set_zone_drift_sink(None)

    def test_drift_hook_noop_when_no_sink_installed(self):
        """With no sink registered, the hook is a silent no-op."""
        from accessiweather import weather_client_nws

        # Ensure sink is cleared
        weather_client_nws.set_zone_drift_sink(None)

        stored = _us_location()
        # Should not raise, even though we'd otherwise have changes to persist.
        with patch.object(weather_client_nws, "wx") as mock_wx:
            weather_client_nws._apply_zone_drift_correction(
                stored, {"properties": FULL_POINTS_PROPERTIES}
            )
            mock_wx.CallAfter.assert_not_called()

    def test_drift_exception_never_breaks_caller(self):
        """A buggy sink must not raise out of the drift hook."""
        from accessiweather import weather_client_nws

        stored = _us_location()
        broken_ops = MagicMock()
        broken_ops.update_zone_metadata.side_effect = RuntimeError("boom")
        # Make the diff path itself raise by pointing wx.CallAfter at a side-effect
        weather_client_nws.set_zone_drift_sink(broken_ops)
        try:
            with patch.object(weather_client_nws, "wx") as mock_wx:
                mock_wx.CallAfter.side_effect = RuntimeError("wx blew up")
                # Must not raise
                weather_client_nws._apply_zone_drift_correction(
                    stored, {"properties": FULL_POINTS_PROPERTIES}
                )
        finally:
            weather_client_nws.set_zone_drift_sink(None)


# ---------------------------------------------------------------------------
# Scenario 6: /points raises -> drift skipped, no cascade
# ---------------------------------------------------------------------------


class TestPointsFetchErrorSkipsDrift:
    """Scenario 6: if /points raises, drift is skipped and refresh continues."""

    async def test_points_raise_does_not_persist_and_does_not_cascade(self):
        """
        Simulate the refresh path's /points fetch failing with an HTTP error.

        The drift code path must not run (no wx.CallAfter), and the exception is
        the caller's concern — weather_client_nws surfaces errors via its
        existing retry/return-None mechanism. Here we just assert that our drift
        helper is not invoked when the points properties argument is missing or
        malformed.
        """
        from accessiweather import weather_client_nws

        stored = _us_location()
        manager = _FakeConfigManager(locations=[stored])
        ops = LocationOperations(cast(ConfigManager, manager))

        weather_client_nws.set_zone_drift_sink(ops)
        try:
            with patch.object(weather_client_nws, "wx") as mock_wx:
                # Simulate malformed/absent properties (what we'd have if /points
                # itself raised before producing a payload).
                weather_client_nws._apply_zone_drift_correction(stored, None)
                weather_client_nws._apply_zone_drift_correction(stored, {})
                weather_client_nws._apply_zone_drift_correction(stored, {"properties": None})
                mock_wx.CallAfter.assert_not_called()
        finally:
            weather_client_nws.set_zone_drift_sink(None)
        assert manager.save_calls == 0

    async def test_get_nws_all_data_parallel_raising_does_not_cascade_drift(self):
        """Integration-lite: when the /points HTTP call raises, drift isn't attempted."""
        from accessiweather import weather_client_nws

        stored = _us_location()
        manager = _FakeConfigManager(locations=[stored])
        ops = LocationOperations(cast(ConfigManager, manager))

        # Install sink; wire a mock http client whose .get raises on the first call
        weather_client_nws.set_zone_drift_sink(ops)
        try:
            mock_client = MagicMock(spec=httpx.AsyncClient)
            # Use a non-retryable exception so the decorator doesn't re-raise —
            # get_nws_all_data_parallel should convert to a (None, ...) tuple.
            mock_client.get = AsyncMock(side_effect=ValueError("bad points payload"))

            with patch.object(weather_client_nws, "wx") as mock_wx:
                result = await weather_client_nws.get_nws_all_data_parallel.__wrapped__(
                    stored,
                    "https://api.weather.gov",
                    "UA",
                    5.0,
                    mock_client,
                )
                assert result == (None, None, None, None, None, None)
                mock_wx.CallAfter.assert_not_called()
        finally:
            weather_client_nws.set_zone_drift_sink(None)
        assert manager.save_calls == 0
