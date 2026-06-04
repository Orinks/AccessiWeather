"""Shared NOAA Weather Radio playback session."""

from __future__ import annotations

from collections.abc import Callable

from accessiweather.noaa_radio.player import RadioPlayer
from accessiweather.noaa_radio.stations import Station


class RadioSession:
    """Owns radio stream state independently from any one dialog."""

    def __init__(self) -> None:
        """Initialize the shared playback session."""
        self.playing_station: Station | None = None
        self.current_urls: list[str] = []
        self.current_url_index = 0
        self._on_playing: Callable[[], None] | None = None
        self._on_stopped: Callable[[], None] | None = None
        self._on_error: Callable[[str], None] | None = None
        self._on_stalled: Callable[[], None] | None = None
        self._on_reconnecting: Callable[[int], None] | None = None
        self.player = RadioPlayer(
            on_playing=self._handle_playing,
            on_stopped=self._handle_stopped,
            on_error=self._handle_error,
            on_stalled=self._handle_stalled,
            on_reconnecting=self._handle_reconnecting,
        )

    def bind_callbacks(
        self,
        *,
        on_playing: Callable[[], None],
        on_stopped: Callable[[], None],
        on_error: Callable[[str], None],
        on_stalled: Callable[[], None],
        on_reconnecting: Callable[[int], None],
    ) -> None:
        """Attach UI callbacks for the currently visible dialog."""
        self._on_playing = on_playing
        self._on_stopped = on_stopped
        self._on_error = on_error
        self._on_stalled = on_stalled
        self._on_reconnecting = on_reconnecting

    def unbind_callbacks(self) -> None:
        """Detach UI callbacks when the dialog is dismissed."""
        self._on_playing = None
        self._on_stopped = None
        self._on_error = None
        self._on_stalled = None
        self._on_reconnecting = None

    def is_playing(self) -> bool:
        """Return whether a stream is currently active."""
        return self.player.is_playing()

    def stop(self, *, notify: bool = True) -> None:
        """Stop playback and clear session state."""
        self.player.stop(notify=notify)
        self.playing_station = None

    def _handle_playing(self) -> None:
        if self._on_playing is not None:
            self._on_playing()

    def _handle_stopped(self) -> None:
        self.playing_station = None
        if self._on_stopped is not None:
            self._on_stopped()

    def _handle_error(self, message: str) -> None:
        self.playing_station = None
        if self._on_error is not None:
            self._on_error(message)

    def _handle_stalled(self) -> None:
        if self._on_stalled is not None:
            self._on_stalled()

    def _handle_reconnecting(self, attempt: int) -> None:
        if self._on_reconnecting is not None:
            self._on_reconnecting(attempt)


_shared_session: RadioSession | None = None


def get_shared_radio_session() -> RadioSession:
    """Return the app-wide NOAA radio playback session."""
    global _shared_session
    if _shared_session is None:
        _shared_session = RadioSession()
    return _shared_session


def stop_shared_radio_session() -> None:
    """Stop the app-wide NOAA radio session, if it exists."""
    if _shared_session is not None:
        _shared_session.stop()
