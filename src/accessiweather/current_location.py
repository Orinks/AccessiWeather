"""One-time native current-location detection helpers."""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from .location_classification import is_us_location
from .models import Location

logger = logging.getLogger(__name__)


class LocationDetectionStatus(Enum):
    """Outcome of a one-time current-location request."""

    SUCCESS = "success"
    DENIED = "denied"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class CurrentCoordinates:
    """Coordinates returned by a native location provider."""

    latitude: float
    longitude: float
    accuracy_meters: float | None = None


@dataclass(frozen=True)
class CurrentLocationResult:
    """Normalized result for the UI."""

    status: LocationDetectionStatus
    message: str
    coordinates: CurrentCoordinates | None = None
    location: Location | None = None


class CurrentLocationError(Exception):
    """Expected provider failure normalized for UI handling."""

    def __init__(self, status: LocationDetectionStatus, message: str) -> None:
        """Store the normalized status alongside the user-facing message."""
        super().__init__(message)
        self.status = status
        self.message = message


class CurrentLocationProvider(Protocol):
    """Protocol implemented by native one-shot providers."""

    async def detect(self, timeout_seconds: float = 15.0) -> CurrentCoordinates:
        """Return current coordinates or raise ``CurrentLocationError``."""
        raise NotImplementedError


def location_from_coordinates(
    coordinates: CurrentCoordinates,
    *,
    name: str | None = None,
) -> Location:
    """Create the same editable Location object used by manual location saves."""
    label = name or f"Current Location ({coordinates.latitude:.4f}, {coordinates.longitude:.4f})"
    location = Location(name=label, latitude=coordinates.latitude, longitude=coordinates.longitude)
    if is_us_location(location):
        location.country_code = "US"
    return location


class CurrentLocationService:
    """Facade that normalizes native provider outcomes for the UI."""

    def __init__(self, provider: CurrentLocationProvider | None = None) -> None:
        """Initialize with an injected provider or the native provider for this platform."""
        self._provider = provider or get_native_provider()

    async def detect_once(self, timeout_seconds: float = 15.0) -> CurrentLocationResult:
        """Run one user-initiated location request."""
        try:
            coordinates = await self._provider.detect(timeout_seconds=timeout_seconds)
        except CurrentLocationError as exc:
            return CurrentLocationResult(status=exc.status, message=exc.message)
        except TimeoutError:
            return CurrentLocationResult(
                status=LocationDetectionStatus.TIMEOUT,
                message="Current location detection timed out. You can still search manually.",
            )
        except Exception as exc:  # noqa: BLE001 - native providers can fail many ways
            logger.debug("Current location detection failed unexpectedly: %s", exc, exc_info=True)
            return CurrentLocationResult(
                status=LocationDetectionStatus.UNAVAILABLE,
                message="Current location is unavailable. You can still search manually.",
            )

        location = location_from_coordinates(coordinates)
        return CurrentLocationResult(
            status=LocationDetectionStatus.SUCCESS,
            message="Current location detected. Review the editable name before saving.",
            coordinates=coordinates,
            location=location,
        )


class UnsupportedLocationProvider:
    """Provider used where native location detection is not implemented."""

    async def detect(self, timeout_seconds: float = 15.0) -> CurrentCoordinates:
        raise CurrentLocationError(
            LocationDetectionStatus.UNSUPPORTED,
            "Current location detection is not supported on this platform. You can still search manually.",
        )


class WindowsLocationProvider:
    """One-shot Windows Location Services provider through WinRT when available."""

    async def detect(self, timeout_seconds: float = 15.0) -> CurrentCoordinates:
        try:
            geolocation = importlib.import_module("winsdk.windows.devices.geolocation")
        except Exception as exc:  # noqa: BLE001
            raise CurrentLocationError(
                LocationDetectionStatus.UNAVAILABLE,
                "Windows Location Services support is not installed. You can still search manually.",
            ) from exc

        try:
            access = await asyncio.wait_for(
                geolocation.Geolocator.request_access_async(),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            raise CurrentLocationError(
                LocationDetectionStatus.TIMEOUT,
                "Windows Location Services did not respond. You can still search manually.",
            ) from exc

        access_name = str(getattr(access, "name", access)).lower()
        if "allowed" not in access_name:
            raise CurrentLocationError(
                LocationDetectionStatus.DENIED,
                "Location permission was denied. You can still search manually.",
            )

        locator = geolocation.Geolocator()
        if hasattr(geolocation, "PositionAccuracy"):
            locator.desired_accuracy = geolocation.PositionAccuracy.DEFAULT

        try:
            position = await asyncio.wait_for(
                locator.get_geoposition_async(),
                timeout=timeout_seconds,
            )
        except TimeoutError as exc:
            raise CurrentLocationError(
                LocationDetectionStatus.TIMEOUT,
                "Windows Location Services timed out. You can still search manually.",
            ) from exc

        return _coordinates_from_windows_position(position)


def _coordinates_from_windows_position(position: Any) -> CurrentCoordinates:
    """Extract latitude/longitude from common WinRT Python projections."""
    coordinate = getattr(position, "coordinate", None)
    point = getattr(coordinate, "point", None)
    point_position = getattr(point, "position", None)

    latitude = getattr(point_position, "latitude", None)
    longitude = getattr(point_position, "longitude", None)
    if latitude is None or longitude is None:
        latitude = getattr(coordinate, "latitude", None)
        longitude = getattr(coordinate, "longitude", None)

    if latitude is None or longitude is None:
        raise CurrentLocationError(
            LocationDetectionStatus.UNAVAILABLE,
            "Windows Location Services returned no coordinates. You can still search manually.",
        )

    accuracy = getattr(coordinate, "accuracy", None)
    return CurrentCoordinates(
        latitude=float(latitude),
        longitude=float(longitude),
        accuracy_meters=float(accuracy) if accuracy is not None else None,
    )


class MacOSLocationProvider:
    """One-shot CoreLocation provider through PyObjC when available."""

    async def detect(self, timeout_seconds: float = 15.0) -> CurrentCoordinates:
        try:
            CoreLocation = importlib.import_module("CoreLocation")
            Foundation = importlib.import_module("Foundation")
        except Exception as exc:  # noqa: BLE001
            raise CurrentLocationError(
                LocationDetectionStatus.UNAVAILABLE,
                "macOS CoreLocation support is not installed. You can still search manually.",
            ) from exc

        loop = asyncio.get_running_loop()
        future: asyncio.Future[CurrentCoordinates] = loop.create_future()

        class _LocationDelegate(Foundation.NSObject):
            def locationManager_didUpdateLocations_(self, manager, locations):  # noqa: N802
                latest = locations.lastObject()
                coordinate = latest.coordinate()
                accuracy = latest.horizontalAccuracy()
                if not future.done():
                    loop.call_soon_threadsafe(
                        future.set_result,
                        CurrentCoordinates(
                            latitude=float(coordinate.latitude),
                            longitude=float(coordinate.longitude),
                            accuracy_meters=float(accuracy) if accuracy >= 0 else None,
                        ),
                    )
                manager.stopUpdatingLocation()

            def locationManager_didFailWithError_(self, manager, error):  # noqa: N802
                if not future.done():
                    loop.call_soon_threadsafe(
                        future.set_exception,
                        CurrentLocationError(
                            LocationDetectionStatus.UNAVAILABLE,
                            "macOS could not detect your current location. You can still search manually.",
                        ),
                    )
                manager.stopUpdatingLocation()

            def locationManagerDidChangeAuthorization_(self, manager):  # noqa: N802
                status = manager.authorizationStatus()
                denied_statuses = {
                    getattr(CoreLocation, "kCLAuthorizationStatusDenied", object()),
                    getattr(CoreLocation, "kCLAuthorizationStatusRestricted", object()),
                }
                if status in denied_statuses and not future.done():
                    loop.call_soon_threadsafe(
                        future.set_exception,
                        CurrentLocationError(
                            LocationDetectionStatus.DENIED,
                            "Location permission was denied. You can still search manually.",
                        ),
                    )

        manager = CoreLocation.CLLocationManager.alloc().init()
        delegate = _LocationDelegate.alloc().init()
        manager.setDelegate_(delegate)

        def _run_core_location() -> None:
            manager.requestWhenInUseAuthorization()
            if hasattr(manager, "requestLocation"):
                manager.requestLocation()
            else:
                manager.startUpdatingLocation()
            Foundation.NSRunLoop.currentRunLoop().runUntilDate_(
                Foundation.NSDate.dateWithTimeIntervalSinceNow_(timeout_seconds)
            )

        thread = threading.Thread(target=_run_core_location, daemon=True)
        thread.start()

        try:
            return await asyncio.wait_for(future, timeout=timeout_seconds + 0.5)
        except TimeoutError as exc:
            manager.stopUpdatingLocation()
            raise CurrentLocationError(
                LocationDetectionStatus.TIMEOUT,
                "macOS location detection timed out. You can still search manually.",
            ) from exc
        finally:
            # Keep delegate alive until the future completes; then break the reference cycle.
            manager.setDelegate_(None)


def get_native_provider() -> CurrentLocationProvider:
    """Return the provider for the current platform."""
    if sys.platform == "win32":
        return WindowsLocationProvider()
    if sys.platform == "darwin":
        return MacOSLocationProvider()
    return UnsupportedLocationProvider()
