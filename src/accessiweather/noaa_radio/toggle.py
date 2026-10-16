"""
Play/stop NOAA Weather Radio without the radio dialog being open.

This backs the system-wide hotkey, so every outcome has to be announced through
a notification rather than the dialog status line -- the window is usually
hidden in the tray when this runs.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from accessiweather.noaa_radio.clients import get_weatherindex_client, load_station_database
from accessiweather.noaa_radio.preferences import RadioPreferences
from accessiweather.noaa_radio.session import RadioSession, get_shared_radio_session
from accessiweather.noaa_radio.station_db import StationDatabase
from accessiweather.noaa_radio.stations import Station
from accessiweather.noaa_radio.stream_url import StreamURLProvider

logger = logging.getLogger(__name__)

NotifyCallback = Callable[[str], None]
ThreadFactory = Callable[[Callable[[], None]], threading.Thread]

NO_STATION_MESSAGE = (
    "No station to play yet. Open NOAA Weather Radio and play a station once, "
    "then this hotkey will resume it."
)


class RadioToggleController:
    """Toggles the shared radio session between playing and stopped."""

    def __init__(
        self,
        *,
        session: RadioSession | None = None,
        preferences: RadioPreferences | None = None,
        station_database: StationDatabase | None = None,
        url_provider: StreamURLProvider | None = None,
        notify: NotifyCallback | None = None,
        auto_tuner_provider: Callable[[], object | None] | None = None,
        thread_factory: ThreadFactory | None = None,
    ) -> None:
        """Initialize the controller with injectable dependencies for tests."""
        self._session = session or get_shared_radio_session()
        self._preferences = preferences or RadioPreferences()
        self._station_database = station_database
        self._url_provider = url_provider or StreamURLProvider(
            use_fallback=False,
            weatherindex_client=get_weatherindex_client(),
        )
        self._notify = notify
        self._auto_tuner_provider = auto_tuner_provider
        self._thread_factory = thread_factory or self._make_thread

    @staticmethod
    def _make_thread(target: Callable[[], None]) -> threading.Thread:
        """Create the worker thread used for stream lookup and playback."""
        return threading.Thread(target=target, name="RadioHotkeyToggle", daemon=True)

    def toggle(self) -> None:
        """Stop playback if the radio is on, otherwise resume the last station."""
        if self._session.is_playing():
            self._stop()
            return
        self._thread_factory(self._start).start()

    def _stop(self) -> None:
        """Stop playback and cancel any alert auto-tune window still counting down."""
        self._cancel_auto_tune()
        try:
            self._session.stop()
        except Exception:
            logger.exception("Could not stop NOAA Weather Radio from the hotkey")
            self._announce("Could not stop NOAA Weather Radio.")
            return
        # The silence is the confirmation: a notification after every stop is
        # one more thing to dismiss for the person who just wanted quiet.
        logger.info("NOAA Weather Radio hotkey: stopped.")

    def _cancel_auto_tune(self) -> None:
        """Keep a pending alert auto-tune from re-starting what the user just stopped."""
        if self._auto_tuner_provider is None:
            return
        try:
            auto_tuner = self._auto_tuner_provider()
            if auto_tuner is not None:
                auto_tuner.stop()
        except Exception:
            logger.debug("Could not cancel alert radio auto-tune", exc_info=True)

    def _start(self) -> None:
        """Resolve the remembered station and put it on the air."""
        try:
            call_sign = self._resolve_call_sign()
            if call_sign is None:
                self._announce(NO_STATION_MESSAGE)
                return

            station = self._find_station(call_sign)
            if station is None:
                self._announce(f"{call_sign} is no longer in the station list.")
                return

            urls = self._preferences.reorder_urls(
                station.call_sign, self._url_provider.get_stream_urls(station.call_sign)
            )
            if not urls:
                self._announce(f"No stream is available for {station.call_sign}.")
                return

            self._play(station, urls)
        except Exception:
            logger.exception("NOAA Weather Radio hotkey playback failed")
            self._announce("Could not start NOAA Weather Radio.")

    def _resolve_call_sign(self) -> str | None:
        """Return the last played station, falling back to the first favorite."""
        last_station = self._preferences.get_last_station()
        if last_station:
            return last_station
        favorites = self._preferences.get_favorite_stations()
        return favorites[0] if favorites else None

    def _find_station(self, call_sign: str) -> Station | None:
        """Look up a station record by call sign."""
        matches = self._get_station_database().get_stations_by_call_signs([call_sign])
        return matches[0] if matches else None

    def _get_station_database(self) -> StationDatabase:
        """Return the injected database, or load the WeatherIndex directory on the worker."""
        if self._station_database is None:
            self._station_database = load_station_database(get_weatherindex_client())
        return self._station_database

    def _play(self, station: Station, urls: list[str]) -> None:
        """Try each stream URL in order until one starts."""
        self._session.playing_station = station
        self._session.current_urls = urls
        self._session.current_url_index = 0

        for index, url in enumerate(urls):
            self._session.current_url_index = index
            if self._session.player.play(url):
                # Station names already end in the state ("Mobile, AL"), so
                # appending station.state would say it twice.
                self._announce(f"Playing {station.call_sign}, {station.name}.")
                return

        self._session.playing_station = None
        self._announce(f"Could not start {station.call_sign}.")

    def _announce(self, message: str) -> None:
        """Report the outcome to the user, who probably cannot see the window."""
        logger.info("NOAA Weather Radio hotkey: %s", message)
        if self._notify is None:
            return
        try:
            self._notify(message)
        except Exception:
            logger.debug("Could not announce radio hotkey result", exc_info=True)
