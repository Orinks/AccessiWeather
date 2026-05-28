"""Tests for one-time current-location detection."""

from __future__ import annotations

import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from accessiweather.config.config_manager import ConfigManager
from accessiweather.config.locations import LocationOperations
from accessiweather.models import AppConfig, AppSettings


class _FakeConfigManager:
    """Minimal stand-in for ``ConfigManager`` used by location save tests."""

    def __init__(self) -> None:
        self.save_calls = 0
        self._config = AppConfig(settings=AppSettings(), locations=[], current_location=None)

    def get_config(self) -> AppConfig:
        return self._config

    def save_config(self) -> bool:
        self.save_calls += 1
        return True

    def _get_logger(self) -> logging.Logger:
        return logging.getLogger("accessiweather.config.test")


class TestCurrentLocationProviders:
    async def test_factory_returns_unsupported_provider_on_linux(self, monkeypatch):
        from accessiweather.current_location import UnsupportedLocationProvider, get_native_provider

        monkeypatch.setattr("accessiweather.current_location.sys.platform", "linux")

        provider = get_native_provider()

        assert isinstance(provider, UnsupportedLocationProvider)

    async def test_service_returns_unavailable_result_when_provider_fails(self):
        from accessiweather.current_location import (
            CurrentLocationError,
            CurrentLocationService,
            LocationDetectionStatus,
        )

        provider = MagicMock()
        provider.detect = AsyncMock(
            side_effect=CurrentLocationError(
                LocationDetectionStatus.DENIED,
                "Location permission was denied.",
            )
        )
        service = CurrentLocationService(provider=provider)

        result = await service.detect_once()

        assert result.status is LocationDetectionStatus.DENIED
        assert result.coordinates is None
        assert "denied" in result.message.lower()
        provider.detect.assert_awaited_once()

    async def test_service_converts_coordinates_to_editable_location(self):
        from accessiweather.current_location import (
            CurrentCoordinates,
            CurrentLocationService,
            LocationDetectionStatus,
        )

        provider = MagicMock()
        provider.detect = AsyncMock(
            return_value=CurrentCoordinates(
                latitude=39.9526, longitude=-75.1652, accuracy_meters=25
            )
        )
        service = CurrentLocationService(provider=provider)

        result = await service.detect_once()

        assert result.status is LocationDetectionStatus.SUCCESS
        assert result.location is not None
        assert result.location.name == "Current Location (39.9526, -75.1652)"
        assert result.location.latitude == pytest.approx(39.9526)
        assert result.location.longitude == pytest.approx(-75.1652)


class TestCurrentLocationSaveFlow:
    async def test_detected_location_saves_like_manual_location_with_enrichment(self):
        from accessiweather.current_location import CurrentCoordinates, location_from_coordinates

        detected = location_from_coordinates(
            CurrentCoordinates(latitude=39.9526, longitude=-75.1652),
            name="Home",
        )
        mock_service = MagicMock()
        mock_service.enrich_location = AsyncMock(side_effect=lambda loc: loc)
        manager = _FakeConfigManager()
        ops = LocationOperations(cast(ConfigManager, manager), zone_enrichment_service=mock_service)

        ok = await ops.add_location_with_enrichment(
            detected.name,
            detected.latitude,
            detected.longitude,
            country_code=detected.country_code,
        )

        assert ok is True
        saved = manager.get_config().locations[0]
        assert saved.name == "Home"
        assert saved.latitude == pytest.approx(39.9526)
        assert saved.longitude == pytest.approx(-75.1652)
        assert manager.get_config().current_location is saved


class TestAddLocationDialogCurrentLocation:
    def test_detected_location_prefills_editable_name_and_selection(self):
        from accessiweather.current_location import CurrentCoordinates, location_from_coordinates
        from accessiweather.ui.dialogs.location_dialog import AddLocationDialog

        dialog = AddLocationDialog.__new__(AddLocationDialog)
        dialog.name_input = MagicMock()
        dialog.name_input.GetValue.return_value = ""
        dialog.results_list = MagicMock()
        dialog.location_manager = MagicMock()
        dialog.location_manager.format_coordinates.return_value = "39.9526N, 75.1652W"
        dialog._update_status = MagicMock()
        dialog._selected_location = None
        dialog._search_results = []

        detected = location_from_coordinates(
            CurrentCoordinates(latitude=39.9526, longitude=-75.1652)
        )

        dialog._apply_detected_location(detected)

        assert dialog._selected_location is detected
        dialog.name_input.SetValue.assert_called_once_with(detected.name)
        dialog._update_status.assert_called_once_with(
            "Detected current location. Review the editable name, then save it."
        )
