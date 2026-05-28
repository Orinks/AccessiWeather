"""Tests for one-time current-location detection."""

from __future__ import annotations

import logging
from types import SimpleNamespace
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


class _ImmediateThread:
    """Thread stand-in that runs the CoreLocation target synchronously."""

    def __init__(self, target, daemon: bool) -> None:
        self._target = target
        self.daemon = daemon

    def start(self) -> None:
        self._target()


class _FakeNSObject:
    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        return self


class _FakeRunLoop:
    @classmethod
    def currentRunLoop(cls):
        return cls()

    def runUntilDate_(self, date) -> None:
        return None


class _FakeDate:
    @staticmethod
    def dateWithTimeIntervalSinceNow_(timeout_seconds):
        return timeout_seconds


class _FakeLocation:
    def __init__(self, *, accuracy: float) -> None:
        self._accuracy = accuracy

    def coordinate(self):
        return SimpleNamespace(latitude=39.9526, longitude=-75.1652)

    def horizontalAccuracy(self):
        return self._accuracy


class _FakeLocations:
    def __init__(self, *, accuracy: float) -> None:
        self._accuracy = accuracy

    def lastObject(self):
        return _FakeLocation(accuracy=self._accuracy)


def _fake_core_location_modules(mode: str):
    class FakeManager(_FakeNSObject):
        def __init__(self) -> None:
            self.delegate = None
            self.stopped = False

        def setDelegate_(self, delegate) -> None:
            self.delegate = delegate

        def requestWhenInUseAuthorization(self) -> None:
            return None

        def authorizationStatus(self):
            return "denied"

        def stopUpdatingLocation(self) -> None:
            self.stopped = True

        if mode != "success-start-updating":

            def requestLocation(self) -> None:
                if mode == "success-request-location":
                    self.delegate.locationManager_didUpdateLocations_(
                        self, _FakeLocations(accuracy=15)
                    )
                elif mode == "failure":
                    self.delegate.locationManager_didFailWithError_(self, object())
                elif mode == "denied":
                    self.delegate.locationManagerDidChangeAuthorization_(self)

        def startUpdatingLocation(self) -> None:
            if mode == "success-start-updating":
                self.delegate.locationManager_didUpdateLocations_(self, _FakeLocations(accuracy=-1))

    fake_foundation = SimpleNamespace(
        NSObject=_FakeNSObject,
        NSRunLoop=_FakeRunLoop,
        NSDate=_FakeDate,
    )
    fake_core_location = SimpleNamespace(
        CLLocationManager=FakeManager,
        kCLAuthorizationStatusDenied="denied",
        kCLAuthorizationStatusRestricted="restricted",
    )
    return fake_foundation, fake_core_location


class TestCurrentLocationProviders:
    async def test_unsupported_provider_reports_manual_fallback(self):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            UnsupportedLocationProvider,
        )

        provider = UnsupportedLocationProvider()

        with pytest.raises(CurrentLocationError) as exc_info:
            await provider.detect()

        assert exc_info.value.status is LocationDetectionStatus.UNSUPPORTED
        assert "search manually" in exc_info.value.message

    async def test_factory_returns_unsupported_provider_on_linux(self, monkeypatch):
        from accessiweather.current_location import UnsupportedLocationProvider, get_native_provider

        monkeypatch.setattr("accessiweather.current_location.sys.platform", "linux")

        provider = get_native_provider()

        assert isinstance(provider, UnsupportedLocationProvider)

    async def test_factory_returns_windows_provider_on_windows(self, monkeypatch):
        from accessiweather.current_location import WindowsLocationProvider, get_native_provider

        monkeypatch.setattr("accessiweather.current_location.sys.platform", "win32")

        provider = get_native_provider()

        assert isinstance(provider, WindowsLocationProvider)

    async def test_factory_returns_macos_provider_on_macos(self, monkeypatch):
        from accessiweather.current_location import MacOSLocationProvider, get_native_provider

        monkeypatch.setattr("accessiweather.current_location.sys.platform", "darwin")

        provider = get_native_provider()

        assert isinstance(provider, MacOSLocationProvider)

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

    async def test_service_returns_timeout_result_for_plain_timeout(self):
        from accessiweather.current_location import CurrentLocationService, LocationDetectionStatus

        provider = MagicMock()
        provider.detect = AsyncMock(side_effect=TimeoutError)
        service = CurrentLocationService(provider=provider)

        result = await service.detect_once()

        assert result.status is LocationDetectionStatus.TIMEOUT
        assert "timed out" in result.message

    async def test_service_returns_unavailable_result_for_unexpected_failure(self):
        from accessiweather.current_location import CurrentLocationService, LocationDetectionStatus

        provider = MagicMock()
        provider.detect = AsyncMock(side_effect=RuntimeError("native backend exploded"))
        service = CurrentLocationService(provider=provider)

        result = await service.detect_once()

        assert result.status is LocationDetectionStatus.UNAVAILABLE
        assert "unavailable" in result.message

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
        assert result.location.country_code == "US"

    async def test_service_leaves_unclear_international_coordinates_without_country_code(self):
        from accessiweather.current_location import (
            CurrentCoordinates,
            CurrentLocationService,
            LocationDetectionStatus,
        )

        provider = MagicMock()
        provider.detect = AsyncMock(
            return_value=CurrentCoordinates(latitude=51.5074, longitude=-0.1278, accuracy_meters=25)
        )
        service = CurrentLocationService(provider=provider)

        result = await service.detect_once()

        assert result.status is LocationDetectionStatus.SUCCESS
        assert result.location is not None
        assert result.location.country_code is None


class TestWindowsCurrentLocationProvider:
    def test_coordinates_from_windows_position_uses_point_position(self):
        from accessiweather.current_location import _coordinates_from_windows_position

        position = SimpleNamespace(
            coordinate=SimpleNamespace(
                point=SimpleNamespace(
                    position=SimpleNamespace(latitude=39.9526, longitude=-75.1652)
                ),
                accuracy=12.5,
            )
        )

        coordinates = _coordinates_from_windows_position(position)

        assert coordinates.latitude == pytest.approx(39.9526)
        assert coordinates.longitude == pytest.approx(-75.1652)
        assert coordinates.accuracy_meters == pytest.approx(12.5)

    def test_coordinates_from_windows_position_uses_projection_fallback(self):
        from accessiweather.current_location import _coordinates_from_windows_position

        position = SimpleNamespace(
            coordinate=SimpleNamespace(latitude=40.0, longitude=-76.0, accuracy=None)
        )

        coordinates = _coordinates_from_windows_position(position)

        assert coordinates.latitude == pytest.approx(40.0)
        assert coordinates.longitude == pytest.approx(-76.0)
        assert coordinates.accuracy_meters is None

    def test_coordinates_from_windows_position_rejects_missing_coordinates(self):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            _coordinates_from_windows_position,
        )

        with pytest.raises(CurrentLocationError) as exc_info:
            _coordinates_from_windows_position(SimpleNamespace(coordinate=SimpleNamespace()))

        assert exc_info.value.status is LocationDetectionStatus.UNAVAILABLE

    async def test_windows_provider_reports_unavailable_when_winsdk_missing(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            WindowsLocationProvider,
        )

        def fake_import(name: str):
            if name == "winsdk.windows.devices.geolocation":
                raise ModuleNotFoundError(name)
            raise AssertionError(name)

        monkeypatch.setattr("accessiweather.current_location.importlib.import_module", fake_import)

        with pytest.raises(CurrentLocationError) as exc_info:
            await WindowsLocationProvider().detect()

        assert exc_info.value.status is LocationDetectionStatus.UNAVAILABLE

    async def test_windows_provider_reports_denied_permission(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            WindowsLocationProvider,
        )

        class FakeGeolocator:
            @staticmethod
            async def request_access_async():
                return SimpleNamespace(name="Denied")

        fake_geolocation = SimpleNamespace(Geolocator=FakeGeolocator)
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_geolocation,
        )

        with pytest.raises(CurrentLocationError) as exc_info:
            await WindowsLocationProvider().detect()

        assert exc_info.value.status is LocationDetectionStatus.DENIED

    async def test_windows_provider_reports_access_timeout(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            WindowsLocationProvider,
        )

        class FakeGeolocator:
            @staticmethod
            async def request_access_async():
                return SimpleNamespace(name="Allowed")

        async def fake_wait_for(awaitable, timeout):
            awaitable.close()
            raise TimeoutError

        fake_geolocation = SimpleNamespace(Geolocator=FakeGeolocator)
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_geolocation,
        )
        monkeypatch.setattr("accessiweather.current_location.asyncio.wait_for", fake_wait_for)

        with pytest.raises(CurrentLocationError) as exc_info:
            await WindowsLocationProvider().detect()

        assert exc_info.value.status is LocationDetectionStatus.TIMEOUT
        assert "did not respond" in exc_info.value.message

    async def test_windows_provider_reports_position_timeout(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            WindowsLocationProvider,
        )

        class FakeGeolocator:
            @staticmethod
            async def request_access_async():
                return SimpleNamespace(name="Allowed")

            async def get_geoposition_async(self):
                return SimpleNamespace()

        calls = 0

        async def fake_wait_for(awaitable, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                return await awaitable
            awaitable.close()
            raise TimeoutError

        fake_geolocation = SimpleNamespace(Geolocator=FakeGeolocator)
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_geolocation,
        )
        monkeypatch.setattr("accessiweather.current_location.asyncio.wait_for", fake_wait_for)

        with pytest.raises(CurrentLocationError) as exc_info:
            await WindowsLocationProvider().detect()

        assert exc_info.value.status is LocationDetectionStatus.TIMEOUT
        assert "timed out" in exc_info.value.message

    async def test_windows_provider_returns_coordinates_when_allowed(self, monkeypatch):
        from accessiweather.current_location import WindowsLocationProvider

        class FakeGeolocator:
            desired_accuracy = None

            @staticmethod
            async def request_access_async():
                return SimpleNamespace(name="Allowed")

            async def get_geoposition_async(self):
                return SimpleNamespace(
                    coordinate=SimpleNamespace(latitude=39.9526, longitude=-75.1652, accuracy=8)
                )

        fake_geolocation = SimpleNamespace(
            Geolocator=FakeGeolocator,
            PositionAccuracy=SimpleNamespace(DEFAULT="default"),
        )
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_geolocation,
        )

        coordinates = await WindowsLocationProvider().detect()

        assert coordinates.latitude == pytest.approx(39.9526)
        assert coordinates.longitude == pytest.approx(-75.1652)
        assert coordinates.accuracy_meters == pytest.approx(8)


class TestMacOSCurrentLocationProvider:
    async def test_macos_provider_reports_unavailable_when_pyobjc_missing(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            MacOSLocationProvider,
        )

        def fake_import(name: str):
            if name == "CoreLocation":
                raise ModuleNotFoundError(name)
            raise AssertionError(name)

        monkeypatch.setattr("accessiweather.current_location.importlib.import_module", fake_import)

        with pytest.raises(CurrentLocationError) as exc_info:
            await MacOSLocationProvider().detect()

        assert exc_info.value.status is LocationDetectionStatus.UNAVAILABLE

    async def test_macos_provider_returns_coordinates_from_request_location(self, monkeypatch):
        from accessiweather.current_location import MacOSLocationProvider

        fake_foundation, fake_core_location = _fake_core_location_modules(
            "success-request-location"
        )
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_core_location if name == "CoreLocation" else fake_foundation,
        )
        monkeypatch.setattr("accessiweather.current_location.threading.Thread", _ImmediateThread)

        coordinates = await MacOSLocationProvider().detect(timeout_seconds=0.1)

        assert coordinates.latitude == pytest.approx(39.9526)
        assert coordinates.longitude == pytest.approx(-75.1652)
        assert coordinates.accuracy_meters == pytest.approx(15)

    async def test_macos_provider_uses_start_updating_location_fallback(self, monkeypatch):
        from accessiweather.current_location import MacOSLocationProvider

        fake_foundation, fake_core_location = _fake_core_location_modules("success-start-updating")
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_core_location if name == "CoreLocation" else fake_foundation,
        )
        monkeypatch.setattr("accessiweather.current_location.threading.Thread", _ImmediateThread)

        coordinates = await MacOSLocationProvider().detect(timeout_seconds=0.1)

        assert coordinates.latitude == pytest.approx(39.9526)
        assert coordinates.longitude == pytest.approx(-75.1652)
        assert coordinates.accuracy_meters is None

    async def test_macos_provider_reports_native_failure(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            MacOSLocationProvider,
        )

        fake_foundation, fake_core_location = _fake_core_location_modules("failure")
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_core_location if name == "CoreLocation" else fake_foundation,
        )
        monkeypatch.setattr("accessiweather.current_location.threading.Thread", _ImmediateThread)

        with pytest.raises(CurrentLocationError) as exc_info:
            await MacOSLocationProvider().detect(timeout_seconds=0.1)

        assert exc_info.value.status is LocationDetectionStatus.UNAVAILABLE

    async def test_macos_provider_reports_denied_authorization(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            MacOSLocationProvider,
        )

        fake_foundation, fake_core_location = _fake_core_location_modules("denied")
        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_core_location if name == "CoreLocation" else fake_foundation,
        )
        monkeypatch.setattr("accessiweather.current_location.threading.Thread", _ImmediateThread)

        with pytest.raises(CurrentLocationError) as exc_info:
            await MacOSLocationProvider().detect(timeout_seconds=0.1)

        assert exc_info.value.status is LocationDetectionStatus.DENIED

    async def test_macos_provider_reports_timeout(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentLocationError,
            LocationDetectionStatus,
            MacOSLocationProvider,
        )

        fake_foundation, fake_core_location = _fake_core_location_modules("timeout")

        async def fake_wait_for(future, timeout):
            raise TimeoutError

        monkeypatch.setattr(
            "accessiweather.current_location.importlib.import_module",
            lambda name: fake_core_location if name == "CoreLocation" else fake_foundation,
        )
        monkeypatch.setattr("accessiweather.current_location.threading.Thread", _ImmediateThread)
        monkeypatch.setattr("accessiweather.current_location.asyncio.wait_for", fake_wait_for)

        with pytest.raises(CurrentLocationError) as exc_info:
            await MacOSLocationProvider().detect(timeout_seconds=0.1)

        assert exc_info.value.status is LocationDetectionStatus.TIMEOUT


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


class TestEditLocationDialogCurrentLocation:
    async def test_detection_uses_reverse_geocoded_location_when_available(self, monkeypatch):
        from accessiweather.current_location import (
            CurrentCoordinates,
            CurrentLocationResult,
            LocationDetectionStatus,
            location_from_coordinates,
        )
        from accessiweather.models import Location
        from accessiweather.ui.dialogs.location_dialog import EditLocationDialog

        detected = location_from_coordinates(
            CurrentCoordinates(latitude=39.9571, longitude=-74.8069)
        )
        resolved = Location(
            name="Mount Holly, NJ",
            latitude=39.9571,
            longitude=-74.8069,
            country_code="US",
            timezone="America/New_York",
        )
        applied: list[Location] = []
        dialog = EditLocationDialog.__new__(EditLocationDialog)
        dialog.current_location_service = MagicMock()
        dialog.current_location_service.detect_once = AsyncMock(
            return_value=CurrentLocationResult(
                status=LocationDetectionStatus.SUCCESS,
                message="Detected",
                coordinates=CurrentCoordinates(latitude=39.9571, longitude=-74.8069),
                location=detected,
            )
        )
        dialog.location_manager = MagicMock()
        dialog.location_manager.reverse_geocode_coordinates = AsyncMock(return_value=resolved)

        monkeypatch.setattr(
            "accessiweather.ui.dialogs.location_dialog.wx.CallAfter",
            lambda func, *args: func(*args),
        )
        dialog._on_current_location_detected = applied.append

        await dialog._do_current_location_detection()

        assert applied == [resolved]
        dialog.location_manager.reverse_geocode_coordinates.assert_awaited_once_with(
            39.9571,
            -74.8069,
        )

    def test_edit_result_includes_editable_display_name(self):
        from accessiweather.models import Location
        from accessiweather.ui.dialogs.location_dialog import EditLocationDialog

        original = Location(name="Lumberton", latitude=39.965, longitude=-74.805)
        selected = Location(
            name="Mount Holly, NJ",
            latitude=39.9571,
            longitude=-74.8069,
            country_code="US",
        )
        dialog = EditLocationDialog.__new__(EditLocationDialog)
        dialog._location = original
        dialog._selected_location = selected
        dialog.name_input = MagicMock()
        dialog.name_input.GetValue.return_value = "Mount Holly, NJ"
        dialog.marine_checkbox = MagicMock()
        dialog.marine_checkbox.GetValue.return_value = True

        result = dialog.get_result()

        assert result.display_name == "Mount Holly, NJ"
        assert result.latitude == pytest.approx(39.9571)
        assert result.longitude == pytest.approx(-74.8069)
        assert result.country_code == "US"
        assert result.marine_mode is True
