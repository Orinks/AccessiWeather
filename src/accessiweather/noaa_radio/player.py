"""NOAA Weather Radio audio player service using sound_lib.stream.URLStream."""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Lazy initialization of sound_lib to avoid import-time failures.
# The BASS audio library requires a valid audio device and may fail
# if initialized before the application is fully set up.
_sound_lib_initialized = False
_sound_lib_available = False


def _ensure_sound_lib() -> bool:
    """
    Check that sound_lib is available. Returns True if importable.

    Does NOT create a new Output() — the app's sound pack system already
    initializes BASS. Creating a second Output() causes BASS_ERROR_ALREADY (14).
    """
    global _sound_lib_initialized, _sound_lib_available
    if _sound_lib_initialized:
        return _sound_lib_available
    _sound_lib_initialized = True
    try:
        from sound_lib.stream import URLStream  # noqa: F401

        _sound_lib_available = True
    except ImportError:
        logger.warning("sound_lib is not installed")
    except Exception as e:
        logger.warning(f"sound_lib check failed: {e}")
    return _sound_lib_available


class RadioPlayer:
    """Audio player for streaming NOAA Weather Radio using sound_lib.stream.URLStream."""

    # Maximum number of automatic reconnection attempts on stream stall/failure
    MAX_RETRIES = 2

    def __init__(
        self,
        on_playing: Callable[[], None] | None = None,
        on_stopped: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_stalled: Callable[[], None] | None = None,
        on_reconnecting: Callable[[int], None] | None = None,
    ) -> None:
        """
        Initialize the RadioPlayer.

        Args:
            on_playing: Callback invoked when playback starts.
            on_stopped: Callback invoked when playback stops.
            on_error: Callback invoked on error, receives error message.
            on_stalled: Callback invoked when stream stalls (buffering).
            on_reconnecting: Callback invoked on reconnect attempt, receives attempt number.

        """
        self._stream = None
        self._volume: float = 1.0
        self._current_url: str | None = None
        self._fallback_urls: list[str] = []
        self._retry_count: int = 0
        self._on_playing = on_playing
        self._on_stopped = on_stopped
        self._on_error = on_error
        self._on_stalled = on_stalled
        self._on_reconnecting = on_reconnecting

    def play(self, url: str, fallback_urls: list[str] | None = None) -> bool:
        """
        Start streaming audio from the given URL.

        Stops any currently playing stream first.

        Args:
            url: The URL to stream audio from.
            fallback_urls: Optional list of alternative URLs to try on failure.

        Returns:
            True if playback started successfully, False otherwise.

        """
        if not _ensure_sound_lib():
            error_msg = "Audio playback is not available. Please ensure sound_lib is installed."
            logger.error(error_msg)
            if self._on_error:
                self._on_error(error_msg)
            return False

        # Stop any current playback
        self.stop()

        self._current_url = url
        self._fallback_urls = list(fallback_urls) if fallback_urls else []
        self._retry_count = 0

        return self._start_stream(url)

    def _start_stream(self, url: str) -> bool:
        """Start streaming from a specific URL (internal)."""
        try:
            from sound_lib.stream import URLStream

            self._stream = URLStream(url=url)
            self._stream.volume = self._volume
            self._stream.play()
            self._current_url = url
            logger.info(f"Started streaming: {url}")
            if self._on_playing:
                self._on_playing()
            return True
        except Exception as e:
            error_msg = f"Failed to start stream: {e}"
            logger.error(error_msg)
            self._stream = None
            # Try fallback URLs before reporting error
            if self._fallback_urls:
                next_url = self._fallback_urls.pop(0)
                logger.info(f"Trying fallback URL: {next_url}")
                return self._start_stream(next_url)
            if self._on_error:
                self._on_error(error_msg)
            return False

    def retry(self) -> bool:
        """
        Retry the current stream after a stall or failure.

        Returns:
            True if reconnection started, False if retries exhausted.

        """
        if self._current_url is None:
            return False
        self._retry_count += 1
        if self._retry_count > self.MAX_RETRIES:
            error_msg = "Stream unavailable after multiple attempts"
            logger.error(error_msg)
            if self._on_error:
                self._on_error(error_msg)
            return False
        logger.info(f"Reconnecting (attempt {self._retry_count}/{self.MAX_RETRIES})")
        if self._on_reconnecting:
            self._on_reconnecting(self._retry_count)
        # Clean up old stream without triggering on_stopped
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.free()
            except Exception:
                pass
            self._stream = None
        return self._start_stream(self._current_url)

    def stop(self) -> None:
        """Stop the currently playing stream and clean up."""
        was_playing = self.is_playing()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.free()
            except Exception as e:
                logger.debug(f"Error stopping stream: {e}")
            finally:
                self._stream = None
        if was_playing and self._on_stopped:
            self._on_stopped()

    def set_volume(self, level: float) -> None:
        """
        Set the playback volume.

        Args:
            level: Volume level from 0.0 to 1.0. Values outside this range are clamped.

        """
        self._volume = max(0.0, min(1.0, level))
        if self._stream is not None:
            try:
                self._stream.volume = self._volume
            except Exception as e:
                logger.debug(f"Error setting stream volume: {e}")

    def get_volume(self) -> float:
        """
        Get the current volume level.

        Returns:
            The current volume level (0.0 to 1.0).

        """
        return self._volume

    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.

        Returns:
            True if a stream is active and playing.

        """
        if self._stream is not None:
            try:
                return self._stream.is_playing
            except Exception:
                pass
        return False

    def is_stalled(self) -> bool:
        """
        Check if the stream has stalled (buffering/no data).

        Returns:
            True if the stream exists but is stalled.

        """
        if self._stream is not None:
            try:
                return self._stream.is_stalled
            except Exception:
                pass
        return False

    def check_health(self) -> None:
        """
        Check stream health and auto-retry on stall.

        Call this periodically (e.g., from a wx.Timer) to detect stalls
        and automatically attempt reconnection.
        """
        if self._stream is None:
            return
        if self.is_stalled():
            logger.warning("Stream stalled, attempting reconnect")
            if self._on_stalled:
                self._on_stalled()
            self.retry()
