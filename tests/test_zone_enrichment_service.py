"""
Tests for ZoneEnrichmentService and the enriched add-location flow.

Covers the six scenarios enumerated in the Forecast Products PR 1 plan:

1. US happy path: /points fetched, all six fields populated.
2. Non-US: /points never called, fields stay null.
3. /points raises httpx.HTTPError: save still proceeds, fields null, debug log.
4. /points returns non-200: save still proceeds, fields null.
5. Partial payload: present fields are populated, missing stay null.
6. No modal dialog is ever shown for a /points failure (pure service).
"""

from __future__ import annotations

import importlib.util
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.config.config_manager import ConfigManager
from accessiweather.config.locations import LocationOperations
from accessiweather.models import AppConfig, AppSettings, Location
from accessiweather.services.zone_enrichment_service import (
    ZoneEnrichmentService,
    _extract_zone_fields,
    _is_us_location,
    _last_path_segment,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


FULL_POINTS_PROPERTIES = {
    "cwa": "PHI",
    "forecastZone": "https://api.weather.gov/zones/forecast/PAZ106",
    "county": "https://api.weather.gov/zones/county/PAC091",
    "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ106",
    "radarStation": "KDIX",
    "timeZone": "America/New_York",
}


def _build_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    """Construct a mock httpx.Response-shaped object for the service."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_body if json_body is not None else {}
    return response


def _make_service_with_response(response: MagicMock) -> tuple[ZoneEnrichmentService, AsyncMock]:
    """Build a ZoneEnrichmentService wired to a mock async client returning ``response``."""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=response)
    service = ZoneEnrichmentService(client=mock_client)
    return service, mock_client.get


def _make_service_with_error(error: Exception) -> tuple[ZoneEnrichmentService, AsyncMock]:
    """Build a service where the mock client raises ``error`` on .get()."""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=error)
    service = ZoneEnrichmentService(client=mock_client)
    return service, mock_client.get


# ---------------------------------------------------------------------------
# Unit tests for the small helper functions
# ---------------------------------------------------------------------------


class TestLastPathSegment:
    """_last_path_segment extracts the final URL path component."""

    def test_typical_forecast_zone_url(self):
        assert _last_path_segment("https://api.weather.gov/zones/forecast/PAZ106") == "PAZ106"

    def test_trailing_slash_stripped(self):
        assert _last_path_segment("https://api.weather.gov/zones/county/PAC091/") == "PAC091"

    def test_none_returns_none(self):
        assert _last_path_segment(None) is None

    def test_empty_string_returns_none(self):
        assert _last_path_segment("") is None

    def test_non_string_returns_none(self):
        assert _last_path_segment(12345) is None  # type: ignore[arg-type]


class TestIsUsLocation:
    """_is_us_location honours country_code then falls back to bounds."""

    def test_explicit_us_country_code(self):
        loc = Location(name="X", latitude=0.0, longitude=0.0, country_code="US")
        assert _is_us_location(loc) is True

    def test_explicit_non_us_country_code(self):
        loc = Location(name="X", latitude=40.0, longitude=-75.0, country_code="GB")
        assert _is_us_location(loc) is False

    def test_continental_us_bounds(self):
        loc = Location(name="Philly", latitude=39.95, longitude=-75.16)
        assert _is_us_location(loc) is True

    def test_outside_us_bounds(self):
        loc = Location(name="London", latitude=51.5, longitude=-0.12)
        assert _is_us_location(loc) is False


# ---------------------------------------------------------------------------
# ZoneEnrichmentService scenarios (plan A-R1 / A-R2 / A-R3)
# ---------------------------------------------------------------------------


class TestEnrichmentHappyPath:
    """Scenario 1: US location, working /points call populates all six fields."""

    async def test_all_six_fields_populated(self):
        service, get_mock = _make_service_with_response(
            _build_response(200, {"properties": FULL_POINTS_PROPERTIES})
        )

        location = Location(
            name="Philadelphia, PA",
            latitude=39.95,
            longitude=-75.16,
            country_code="US",
        )

        enriched = await service.enrich_location(location)

        get_mock.assert_awaited_once()
        assert enriched.timezone == "America/New_York"
        assert enriched.cwa_office == "PHI"
        assert enriched.forecast_zone_id == "PAZ106"
        assert enriched.county_zone_id == "PAC091"
        assert enriched.fire_zone_id == "PAZ106"
        assert enriched.radar_station == "KDIX"
        # Original identity fields untouched
        assert enriched.name == "Philadelphia, PA"
        assert enriched.latitude == pytest.approx(39.95)
        assert enriched.longitude == pytest.approx(-75.16)


class TestEnrichmentNonUs:
    """Scenario 2: non-US locations never trigger a /points call."""

    async def test_non_us_location_skipped(self):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()
        service = ZoneEnrichmentService(client=mock_client)

        location = Location(
            name="London, UK",
            latitude=51.5,
            longitude=-0.12,
            country_code="GB",
        )

        enriched = await service.enrich_location(location)

        mock_client.get.assert_not_awaited()
        assert enriched is location  # returned unchanged
        assert enriched.timezone is None
        assert enriched.cwa_office is None
        assert enriched.forecast_zone_id is None
        assert enriched.county_zone_id is None
        assert enriched.fire_zone_id is None
        assert enriched.radar_station is None


class TestEnrichmentHttpError:
    """Scenario 3: /points raises httpx.HTTPError -> fields stay null, debug log."""

    async def test_http_error_does_not_raise(self, caplog):
        service, _ = _make_service_with_error(httpx.ConnectError("boom"))

        location = Location(
            name="US loc",
            latitude=39.95,
            longitude=-75.16,
            country_code="US",
        )

        with caplog.at_level(
            logging.DEBUG, logger="accessiweather.services.zone_enrichment_service"
        ):
            enriched = await service.enrich_location(location)

        assert enriched.timezone is None
        assert enriched.cwa_office is None
        assert enriched.forecast_zone_id is None
        assert enriched.county_zone_id is None
        assert enriched.fire_zone_id is None
        assert enriched.radar_station is None
        # Debug log emitted (not higher level so user is not alarmed)
        assert any(
            "points request failed" in record.message.lower() or "points" in record.message.lower()
            for record in caplog.records
        )

    async def test_timeout_is_handled(self):
        service, _ = _make_service_with_error(httpx.ReadTimeout("slow"))
        location = Location(name="US loc", latitude=39.95, longitude=-75.16, country_code="US")

        enriched = await service.enrich_location(location)
        assert enriched.forecast_zone_id is None


class TestEnrichmentNon200:
    """Scenario 4: /points returns a non-200 -> fields stay null."""

    async def test_404_leaves_fields_null(self):
        service, _ = _make_service_with_response(_build_response(404, {"error": "nope"}))

        location = Location(name="US loc", latitude=39.95, longitude=-75.16, country_code="US")

        enriched = await service.enrich_location(location)

        assert enriched.forecast_zone_id is None
        assert enriched.cwa_office is None
        assert enriched.timezone is None

    async def test_500_leaves_fields_null(self):
        service, _ = _make_service_with_response(_build_response(500, {}))

        location = Location(name="US loc", latitude=39.95, longitude=-75.16, country_code="US")

        enriched = await service.enrich_location(location)
        assert enriched.radar_station is None


class TestEnrichmentPartialPayload:
    """Scenario 5: present fields populated, absent fields stay null."""

    async def test_only_cwa_and_timezone_present(self):
        partial_properties = {
            "cwa": "PHI",
            "timeZone": "America/New_York",
            # forecastZone, county, fireWeatherZone, radarStation all absent
        }
        service, _ = _make_service_with_response(
            _build_response(200, {"properties": partial_properties})
        )

        location = Location(name="US loc", latitude=39.95, longitude=-75.16, country_code="US")

        enriched = await service.enrich_location(location)

        assert enriched.cwa_office == "PHI"
        assert enriched.timezone == "America/New_York"
        assert enriched.forecast_zone_id is None
        assert enriched.county_zone_id is None
        assert enriched.fire_zone_id is None
        assert enriched.radar_station is None

    async def test_properties_key_missing_leaves_fields_null(self):
        # Valid 200 but no 'properties' dict at all
        service, _ = _make_service_with_response(_build_response(200, {"foo": "bar"}))

        location = Location(name="US loc", latitude=39.95, longitude=-75.16, country_code="US")

        enriched = await service.enrich_location(location)
        assert enriched.forecast_zone_id is None
        assert enriched.cwa_office is None


class TestExtractZoneFields:
    """Unit test for the pure mapping helper."""

    def test_full_mapping(self):
        fields = _extract_zone_fields(FULL_POINTS_PROPERTIES)
        assert fields == {
            "timezone": "America/New_York",
            "cwa_office": "PHI",
            "forecast_zone_id": "PAZ106",
            "county_zone_id": "PAC091",
            "fire_zone_id": "PAZ106",
            "radar_station": "KDIX",
        }

    def test_partial_mapping_nulls_missing(self):
        fields = _extract_zone_fields({"cwa": "PHI"})
        assert fields["cwa_office"] == "PHI"
        assert fields["forecast_zone_id"] is None
        assert fields["timezone"] is None

    def test_empty_dict(self):
        fields = _extract_zone_fields({})
        assert all(value is None for value in fields.values())


# ---------------------------------------------------------------------------
# Integration with LocationOperations (save flow)
# ---------------------------------------------------------------------------


class _FakeConfigManager:
    """Minimal stand-in for ``ConfigManager`` used by LocationOperations tests."""

    def __init__(self) -> None:
        self.save_calls = 0
        self._config = AppConfig(
            settings=AppSettings(),
            locations=[],
            current_location=None,
        )

    def get_config(self) -> AppConfig:
        return self._config

    def save_config(self) -> bool:
        self.save_calls += 1
        return True

    def _get_logger(self) -> logging.Logger:
        return logging.getLogger("accessiweather.config.test")


class TestAddLocationWithEnrichment:
    """LocationOperations.add_location_with_enrichment integrates the service."""

    async def test_us_location_persists_enriched_fields(self):
        mock_service = MagicMock(spec=ZoneEnrichmentService)

        def _enrich(loc: Location) -> Location:
            from dataclasses import replace

            return replace(
                loc,
                timezone="America/New_York",
                cwa_office="PHI",
                forecast_zone_id="PAZ106",
                county_zone_id="PAC091",
                fire_zone_id="PAZ106",
                radar_station="KDIX",
            )

        mock_service.enrich_location = AsyncMock(side_effect=_enrich)

        manager = _FakeConfigManager()
        ops = LocationOperations(cast(ConfigManager, manager), zone_enrichment_service=mock_service)

        ok = await ops.add_location_with_enrichment(
            "Philadelphia, PA",
            39.95,
            -75.16,
            country_code="US",
        )

        assert ok is True
        assert manager.save_calls == 1
        assert len(manager.get_config().locations) == 1
        saved = manager.get_config().locations[0]
        assert saved.cwa_office == "PHI"
        assert saved.forecast_zone_id == "PAZ106"
        assert saved.county_zone_id == "PAC091"
        assert saved.fire_zone_id == "PAZ106"
        assert saved.radar_station == "KDIX"
        assert saved.timezone == "America/New_York"
        mock_service.enrich_location.assert_awaited_once()

    async def test_non_us_location_still_saved_without_enrichment(self):
        # Return original unchanged (what the real service would do for non-US)
        mock_service = MagicMock(spec=ZoneEnrichmentService)
        mock_service.enrich_location = AsyncMock(side_effect=lambda loc: loc)

        manager = _FakeConfigManager()
        ops = LocationOperations(cast(ConfigManager, manager), zone_enrichment_service=mock_service)

        ok = await ops.add_location_with_enrichment(
            "London, UK",
            51.5,
            -0.12,
            country_code="GB",
        )

        assert ok is True
        saved = manager.get_config().locations[0]
        assert saved.cwa_office is None
        assert saved.forecast_zone_id is None
        assert saved.timezone is None

    async def test_enrichment_failure_never_blocks_save(self):
        """Scenario 6: even a catastrophic enrichment error never blocks save."""
        mock_service = MagicMock(spec=ZoneEnrichmentService)
        # Real service never raises, but defend against future regressions:
        mock_service.enrich_location = AsyncMock(side_effect=RuntimeError("unexpected"))

        manager = _FakeConfigManager()
        ops = LocationOperations(cast(ConfigManager, manager), zone_enrichment_service=mock_service)

        ok = await ops.add_location_with_enrichment("US loc", 39.95, -75.16, country_code="US")

        assert ok is True
        saved = manager.get_config().locations[0]
        assert saved.cwa_office is None
        assert saved.forecast_zone_id is None

    async def test_duplicate_name_rejected_without_calling_service(self):
        mock_service = MagicMock(spec=ZoneEnrichmentService)
        mock_service.enrich_location = AsyncMock(side_effect=lambda loc: loc)

        manager = _FakeConfigManager()
        manager._config.locations.append(Location(name="dupe", latitude=1.0, longitude=2.0))
        ops = LocationOperations(cast(ConfigManager, manager), zone_enrichment_service=mock_service)

        ok = await ops.add_location_with_enrichment("dupe", 1.0, 2.0)

        assert ok is False
        mock_service.enrich_location.assert_not_awaited()
        assert manager.save_calls == 0


class TestNoModalDialog:
    """Scenario 6: save flow never spawns a modal dialog on /points failure."""

    async def test_http_error_does_not_touch_wx(self):
        service, _ = _make_service_with_error(httpx.ConnectError("no net"))

        location = Location(name="US loc", latitude=39.95, longitude=-75.16, country_code="US")

        # Patch wx.MessageDialog (if importable) to fail loudly if anyone uses it.
        patchers = []
        if importlib.util.find_spec("wx") is not None:
            msg_dialog_patcher = patch(
                "wx.MessageDialog",
                side_effect=AssertionError("wx.MessageDialog must not be invoked"),
            )
            message_box_patcher = patch(
                "wx.MessageBox",
                side_effect=AssertionError("wx.MessageBox must not be invoked"),
            )
            msg_dialog_patcher.start()
            message_box_patcher.start()
            patchers.extend([msg_dialog_patcher, message_box_patcher])

        try:
            enriched = await service.enrich_location(location)
        finally:
            for p in patchers:
                p.stop()

        # Service completed normally and never touched wx
        assert enriched.forecast_zone_id is None
