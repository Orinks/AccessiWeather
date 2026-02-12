"""NOAA Weather Radio audio player service using sound_lib.stream.URLStream."""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Try to import sound_lib for URL streaming
SOUND_LIB_AVAILABLE = False
_sound_lib_output = None

try:
    from sound_lib import output

    _sound_lib_output = output.Output()
    SOUND_LIB_AVAILABLE = True
except ImportError:
    pass
except Exception as e:
    logger.debug(f"sound_lib initialization failed: {e}")


class RadioPlayer:
    """Audio player for streaming NOAA Weather Radio using sound_lib.stream.URLStream."""

    def __init__(
        self,
        on_playing: Callable[[], None] | None = None,
        on_stopped: Callable[[], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize the RadioPlayer.

        Args:
            on_playing: Callback invoked when playback starts.
            on_stopped: Callback invoked when playback stops.
            on_error: Callback invoked on error, receives error message.

        """
        self._stream = None
        self._volume: float = 1.0
        self._on_playing = on_playing
        self._on_stopped = on_stopped
        self._on_error = on_error

    def play(self, url: str) -> bool:
        """
        Start streaming audio from the given URL.

        Stops any currently playing stream first.

        Args:
            url: The URL to stream audio from.

        Returns:
            True if playback started successfully, False otherwise.

        """
        if not SOUND_LIB_AVAILABLE:
            error_msg = "sound_lib is not available; cannot stream audio"
            logger.error(error_msg)
            if self._on_error:
                self._on_error(error_msg)
            return False

        # Stop any current playback
        self.stop()

        try:
            from sound_lib.stream import URLStream

            self._stream = URLStream(url=url)
            self._stream.volume = self._volume
            self._stream.play()
            logger.info(f"Started streaming: {url}")
            if self._on_playing:
                self._on_playing()
            return True
        except Exception as e:
            error_msg = f"Failed to start stream: {e}"
            logger.error(error_msg)
            self._stream = None
            if self._on_error:
                self._on_error(error_msg)
            return False

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
