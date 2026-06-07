"""Automatic NOAA Weather Radio tuning for newly issued weather alerts."""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import wx

from accessiweather.noaa_radio.preferences import RadioPreferences
from accessiweather.noaa_radio.session import RadioSession, get_shared_radio_session
from accessiweather.noaa_radio.station_db import StationDatabase
from accessiweather.noaa_radio.stations import Station
from accessiweather.noaa_radio.stream_url import StreamURLProvider
from accessiweather.noaa_radio.weatherindex_client import WeatherIndexClient

if TYPE_CHECKING:
    from accessiweather.models import AppSettings, Location, WeatherAlert

logger = logging.getLogger(__name__)

SettingsProvider = Callable[[], "AppSettings | None"]
LocationProvider = Callable[[], "Location | None"]
StatusCallback = Callable[[str], None]
ThreadFactory = Callable[[Callable[[], None]], threading.Thread]

_COUNTY_ZONE_RE = re.compile(r"^(?P<state>[A-Z]{2})C(?P<county>\d{3})$")
_NWR_SAME_WEATHER_EVENT_NAMES: frozenset[str] = frozenset(
    {
        # Weather-related operational NWR-SAME event codes published by NWS.
        # Weather advisories and their follow-up statements are intentionally
        # absent because NWSI 10-1710 Appendix G says they have no SAME/EAS
        # event code and are not broadcast with SAME/EAS headers or 1050 Hz WAT.
        "blizzard warning",
        "coastal flood watch",
        "coastal flood warning",
        "dust storm warning",
        "extreme wind warning",
        "flash flood watch",
        "flash flood warning",
        "flash flood statement",
        "flood watch",
        "flood warning",
        "flood statement",
        "high wind watch",
        "high wind warning",
        "hurricane watch",
        "hurricane warning",
        "hurricane statement",
        "hurricane local statement",
        "severe thunderstorm watch",
        "severe thunderstorm warning",
        "severe weather statement",
        "snow squall warning",
        "special marine warning",
        "special weather statement",
        "storm surge watch",
        "storm surge warning",
        "tornado watch",
        "tornado warning",
        "tropical storm watch",
        "tropical storm warning",
        "tsunami watch",
        "tsunami warning",
        "winter storm watch",
        "winter storm warning",
    }
)
_STATE_FIPS: dict[str, str] = {
    "AL": "01",
    "AK": "02",
    "AZ": "04",
    "AR": "05",
    "CA": "06",
    "CO": "08",
    "CT": "09",
    "DE": "10",
    "DC": "11",
    "FL": "12",
    "GA": "13",
    "HI": "15",
    "ID": "16",
    "IL": "17",
    "IN": "18",
    "IA": "19",
    "KS": "20",
    "KY": "21",
    "LA": "22",
    "ME": "23",
    "MD": "24",
    "MA": "25",
    "MI": "26",
    "MN": "27",
    "MS": "28",
    "MO": "29",
    "MT": "30",
    "NE": "31",
    "NV": "32",
    "NH": "33",
    "NJ": "34",
    "NM": "35",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "OR": "41",
    "PA": "42",
    "RI": "44",
    "SC": "45",
    "SD": "46",
    "TN": "47",
    "TX": "48",
    "UT": "49",
    "VT": "50",
    "VA": "51",
    "WA": "53",
    "WV": "54",
    "WI": "55",
    "WY": "56",
    "AS": "60",
    "GU": "66",
    "MP": "69",
    "PR": "72",
    "VI": "78",
}


def county_zone_to_same_code(zone_id: str | None) -> str | None:
    """Convert an NWS county zone id like PAC091 to a SAME/FIPS code."""
    if not isinstance(zone_id, str):
        return None
    normalized = zone_id.rsplit("/", 1)[-1].strip().upper()
    match = _COUNTY_ZONE_RE.match(normalized)
    if not match:
        return None

    state_fips = _STATE_FIPS.get(match.group("state"))
    if state_fips is None:
        return None
    return f"0{state_fips}{match.group('county')}"


def is_nwr_same_weather_event(alert: WeatherAlert) -> bool:
    """Return whether an alert event is eligible for NWR-SAME auto-tune."""
    return _normalize_event_name(alert.event) in _NWR_SAME_WEATHER_EVENT_NAMES


def _normalize_event_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().casefold().split())


class AlertStationResolver(Protocol):
    """Resolves an alert batch to a reliable NOAA Weather Radio station."""

    def resolve_station(
        self,
        alerts: list[WeatherAlert],
        location: Location | None,
    ) -> Station | None:
        """Return the station that reliably covers the alert batch, if known."""


class NoReliableAlertStationResolver:
    """
    Conservative resolver for tests or deployments without coverage metadata.

    Nearest station or favorite station would be a guess when station coverage
    cannot be queried, so this resolver always skips auto-tune.
    """

    def resolve_station(
        self,
        alerts: list[WeatherAlert],
        location: Location | None,
    ) -> Station | None:
        del alerts, location
        return None


class WeatherIndexAlertStationResolver:
    """Resolve alert coverage to a WeatherIndex station using SAME county metadata."""

    def __init__(
        self,
        *,
        station_database: StationDatabase | None = None,
        weatherindex_client: WeatherIndexClient | None = None,
    ) -> None:
        """Configure station and WeatherIndex dependencies."""
        self._station_database = station_database or StationDatabase()
        self._weatherindex_client = weatherindex_client or WeatherIndexClient()

    def resolve_station(
        self,
        alerts: list[WeatherAlert],
        location: Location | None,
    ) -> Station | None:
        """Return the first station whose WeatherIndex SAME coverage matches the alert."""
        same_codes = self._alert_same_codes(alerts)
        if not same_codes:
            logger.info(
                "Weather radio auto-tune skipped: alert has no SAME or county zone metadata"
            )
            return None

        for station in self._candidate_stations(location, self._alert_states(alerts)):
            metadata = self._weatherindex_client.get_station_metadata(station.call_sign)
            if metadata is None or not metadata.served_counties:
                continue
            station_same_codes = {county.same_code for county in metadata.served_counties}
            if same_codes & station_same_codes:
                logger.info(
                    "Matched alert SAME coverage to WeatherIndex station %s",
                    station.call_sign,
                )
                return station

        logger.info(
            "Weather radio auto-tune skipped: WeatherIndex has no matching station coverage"
        )
        return None

    def _candidate_stations(self, location: Location | None, states: set[str]) -> list[Station]:
        stations = self._station_database.get_all_stations()
        if location is not None:
            return [
                result.station
                for result in self._station_database.find_nearest(
                    location.latitude, location.longitude, limit=None
                )
            ]

        # Without a current location, try transmitters in affected states first,
        # then the remaining database by call sign. Matching still requires SAME
        # coverage, so this tie-breaker is deterministic without guessing.
        return sorted(
            stations,
            key=lambda station: (
                0 if station.state.upper() in states else 1,
                station.call_sign.upper(),
            ),
        )

    def _alert_same_codes(self, alerts: list[WeatherAlert]) -> set[str]:
        same_codes: set[str] = set()
        for alert in alerts:
            for same_code in getattr(alert, "same_codes", []):
                normalized = self._normalize_same_code(same_code)
                if normalized is not None:
                    same_codes.add(normalized)
            for zone_id in alert.affected_zones:
                same_code = self._county_zone_to_same(zone_id)
                if same_code is not None:
                    same_codes.add(same_code)
        return same_codes

    def _alert_states(self, alerts: list[WeatherAlert]) -> set[str]:
        states: set[str] = set()
        for alert in alerts:
            for zone_id in alert.affected_zones:
                normalized = zone_id.rsplit("/", 1)[-1].strip().upper()
                match = _COUNTY_ZONE_RE.match(normalized)
                if match:
                    states.add(match.group("state"))
            for same_code in getattr(alert, "same_codes", []):
                normalized = self._normalize_same_code(same_code)
                state = self._same_code_to_state(normalized) if normalized else None
                if state:
                    states.add(state)
        return states

    @staticmethod
    def _normalize_same_code(value: object) -> str | None:
        if isinstance(value, int):
            return f"{value:06d}"
        if not isinstance(value, str):
            return None
        digits = "".join(ch for ch in value.strip() if ch.isdigit())
        if not digits:
            return None
        return digits.zfill(6)

    @staticmethod
    def _county_zone_to_same(zone_id: str) -> str | None:
        return county_zone_to_same_code(zone_id)

    @staticmethod
    def _same_code_to_state(same_code: str | None) -> str | None:
        if same_code is None or len(same_code) != 6:
            return None
        state_fips = same_code[1:3]
        for state, fips in _STATE_FIPS.items():
            if fips == state_fips:
                return state
        return None


class AlertRadioAutoTuner:
    """Starts a user-configured weather radio station for qualifying alert batches."""

    def __init__(
        self,
        *,
        settings_provider: SettingsProvider,
        location_provider: LocationProvider,
        preferences_path: Path | str | None = None,
        status_callback: StatusCallback | None = None,
        session: RadioSession | None = None,
        preferences: RadioPreferences | None = None,
        station_resolver: AlertStationResolver | None = None,
        url_provider: StreamURLProvider | None = None,
        thread_factory: ThreadFactory | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize the auto tuner with injectable dependencies for tests."""
        weatherindex_client = WeatherIndexClient()
        self._settings_provider = settings_provider
        self._location_provider = location_provider
        self._status_callback = status_callback
        self._session = session or get_shared_radio_session()
        self._preferences = preferences or RadioPreferences(path=preferences_path)
        self._station_resolver = station_resolver or WeatherIndexAlertStationResolver(
            weatherindex_client=weatherindex_client
        )
        self._url_provider = url_provider or StreamURLProvider(
            use_fallback=False,
            weatherindex_client=weatherindex_client,
        )
        self._thread_factory = thread_factory or self._make_thread
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._generation = 0
        self._auto_station_call_sign: str | None = None
        self._stop_at_monotonic: float | None = None

    @staticmethod
    def _make_thread(target: Callable[[], None]) -> threading.Thread:
        """Create the worker thread used for stream setup and stop timing."""
        return threading.Thread(target=target, name="AlertRadioAutoTune", daemon=True)

    def tune_for_alerts(self, alerts: list[WeatherAlert]) -> None:
        """Schedule weather radio playback for an eligible alert notification batch."""
        if not alerts:
            return

        eligible_alerts = [alert for alert in alerts if is_nwr_same_weather_event(alert)]
        if not eligible_alerts:
            logger.info("Weather radio auto-tune skipped: no NWR-SAME weather event in alert batch")
            return

        settings = self._safe_get_settings()
        if not getattr(settings, "auto_tune_weather_radio_alerts", False):
            return

        duration_minutes = self._validated_duration_minutes(settings)
        now = self._monotonic()
        stop_at = now + duration_minutes * 60
        with self._lock:
            # Duplicate alert batches extend the current pending/active tune
            # window. They do not start overlapping station resolution or audio.
            if self._is_auto_tune_active_locked(now):
                self._stop_at_monotonic = max(self._stop_at_monotonic or stop_at, stop_at)
                self._wake_event.set()
                logger.info(
                    "Extended pending or active weather radio auto-tune for alert batch of "
                    "%d alert(s)",
                    len(eligible_alerts),
                )
                return

            if self._session.is_playing():
                playing_station = self._session.playing_station
                station_label = (
                    playing_station.call_sign if playing_station is not None else "unknown station"
                )
                self._emit_status(
                    "Weather radio auto-tune skipped because NOAA Weather Radio is already "
                    f"playing {station_label}."
                )
                return

            self._generation += 1
            generation = self._generation
            self._auto_station_call_sign = None
            self._stop_at_monotonic = stop_at
            self._wake_event.clear()
            self._worker = self._thread_factory(
                lambda: self._worker_loop(list(eligible_alerts), generation)
            )
            self._worker.start()

        logger.info(
            "Scheduled weather radio auto-tune resolution for %d minute(s)",
            duration_minutes,
        )

    def stop(self) -> None:
        """Cancel pending auto-tune timing without stopping unrelated manual playback."""
        with self._lock:
            self._generation += 1
            self._clear_auto_state_locked()
            self._wake_event.set()

    def _safe_get_settings(self) -> AppSettings | None:
        try:
            return self._settings_provider()
        except Exception as exc:
            logger.debug("Weather radio auto-tune settings unavailable: %s", exc)
            return None

    @staticmethod
    def _validated_duration_minutes(settings: AppSettings | None) -> int:
        value = getattr(settings, "auto_tune_weather_radio_duration_minutes", 5)
        if isinstance(value, int) and 1 <= value <= 60:
            return value
        return 5

    def _resolve_alert_station(self, alerts: list[WeatherAlert]) -> Station | None:
        """Resolve the alert batch to a reliable station through the configured resolver."""
        location = self._safe_get_location()
        try:
            return self._station_resolver.resolve_station(alerts, location)
        except Exception as exc:
            logger.warning("Weather radio auto-tune station resolution failed: %s", exc)
            return None

    def _safe_get_location(self) -> Location | None:
        try:
            return self._location_provider()
        except Exception as exc:
            logger.debug("Weather radio auto-tune location unavailable: %s", exc)
            return None

    def _worker_loop(self, alerts: list[WeatherAlert], generation: int) -> None:
        try:
            station = self._resolve_alert_station(alerts)
            if station is None:
                self._emit_status(
                    "Weather radio auto-tune skipped: AccessiWeather does not have a reliable "
                    "station match for this alert."
                )
                return

            with self._lock:
                if generation != self._generation:
                    return
                if self._session.is_playing():
                    playing_station = self._session.playing_station
                    station_label = (
                        playing_station.call_sign
                        if playing_station is not None
                        else "unknown station"
                    )
                    self._emit_status(
                        "Weather radio auto-tune skipped because NOAA Weather Radio is already "
                        f"playing {station_label}."
                    )
                    return
                self._auto_station_call_sign = station.call_sign

            if not self._play_station(station, generation):
                return

            while True:
                with self._lock:
                    if generation != self._generation:
                        return
                    stop_at = self._stop_at_monotonic

                if stop_at is None:
                    return

                remaining = stop_at - self._monotonic()
                if remaining <= 0:
                    break

                self._wake_event.wait(min(remaining, 1.0))
                self._wake_event.clear()

                if not self._session.is_playing():
                    logger.info("Weather radio auto-tune ended because playback stopped")
                    return

                playing_station = self._session.playing_station
                if playing_station is None or playing_station.call_sign != station.call_sign:
                    logger.info("Weather radio auto-tune relinquished control to manual playback")
                    return

            playing_station = self._session.playing_station
            if (
                self._session.is_playing()
                and playing_station is not None
                and playing_station.call_sign == station.call_sign
            ):
                self._session.stop()
                self._emit_status(f"Weather radio auto-tune stopped {station.call_sign}.")
        finally:
            with self._lock:
                if generation == self._generation:
                    self._clear_auto_state_locked()

    def _play_station(self, station: Station, generation: int) -> bool:
        urls = self._preferences.reorder_urls(
            station.call_sign,
            self._url_provider.get_stream_urls(station.call_sign),
        )
        if not urls:
            self._emit_status(
                f"Weather radio auto-tune skipped: no stream is available for {station.call_sign}."
            )
            return False

        with self._lock:
            if generation != self._generation:
                return False
            self._session.playing_station = station
            self._session.current_urls = urls
            self._session.current_url_index = 0

        for index, url in enumerate(urls):
            with self._lock:
                if generation != self._generation:
                    return False
                self._session.current_url_index = index

            if self._session.player.play(url):
                self._emit_status(
                    f"Weather radio auto-tune started {station.call_sign} for active alerts."
                )
                return True

        with self._lock:
            if generation == self._generation:
                self._session.playing_station = None
        self._emit_status(f"Weather radio auto-tune could not start {station.call_sign}.")
        return False

    def _is_auto_tune_active_locked(self, now: float) -> bool:
        return self._worker is not None and (
            self._stop_at_monotonic is not None and self._stop_at_monotonic > now
        )

    def _clear_auto_state_locked(self) -> None:
        self._worker = None
        self._auto_station_call_sign = None
        self._stop_at_monotonic = None

    def _emit_status(self, message: str) -> None:
        logger.info(message)
        if self._status_callback is None:
            return
        try:
            wx.CallAfter(self._status_callback, message)
        except Exception:
            logger.debug("Could not post weather radio auto-tune status", exc_info=True)
