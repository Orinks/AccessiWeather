import logging
import platform
import sys
from collections.abc import Collection
from pathlib import Path
from typing import Any

from ..runtime_env import is_compiled_runtime
from ..sound_events import normalize_muted_sound_events
from ..soundpack_paths import get_soundpacks_dir
from .sound_pack_helpers import (
    get_available_sound_packs as _get_available_sound_packs,
    get_sound_entry as _get_pack_sound_entry,
    get_sound_entry_for_candidates as _get_pack_sound_entry_for_candidates,
    get_sound_pack_sounds as _get_pack_sounds,
    parse_sound_entry,
    validate_sound_pack as _validate_sound_pack,
)

# Try sound_lib first (supports stopping playback, cross-platform)
SOUND_LIB_AVAILABLE = False
_sound_lib_output = None
_active_streams: list = []  # Keep references to prevent garbage collection

try:
    from sound_lib import output

    _sound_lib_output = output.Output()
    SOUND_LIB_AVAILABLE = True
except ImportError:
    pass
except Exception as e:
    logging.getLogger(__name__).debug(f"sound_lib initialization failed: {e}")

# Fallback to playsound3
try:
    from playsound3 import playsound

    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False
    playsound = None

logger = logging.getLogger(__name__)

SOUNDPACKS_DIR = get_soundpacks_dir()
DEFAULT_PACK = "default"
DEFAULT_EVENT = "alert"


def is_sound_event_muted(event: str, muted_events: Collection[str] | None = None) -> bool:
    """Return True when a user-level mute disables the event."""
    if not event:
        return False
    return event in set(normalize_muted_sound_events(muted_events))


def _log_packaging_sound_diagnostics() -> None:
    """Emit debug-only sound dependency/path diagnostics for packaged troubleshooting."""
    logger.debug(
        "[packaging-diag] sound deps: sound_lib_available=%s playsound_available=%s "
        "compiled=%s meipass=%s soundpacks_dir=%s exists=%s",
        SOUND_LIB_AVAILABLE,
        PLAYSOUND_AVAILABLE,
        is_compiled_runtime(),
        getattr(sys, "_MEIPASS", None),
        SOUNDPACKS_DIR,
        SOUNDPACKS_DIR.exists(),
    )


_log_packaging_sound_diagnostics()


def _parse_sound_entry(
    entry: str | dict[str, Any], event: str, volumes: dict[str, float] | None = None
) -> tuple[str, float]:
    """Parse a sound entry from pack.json and return (filename, volume)."""
    return parse_sound_entry(entry, event, volumes)


def get_sound_entry(event: str, pack_dir: str) -> tuple[Path | None, float]:
    """Resolve the sound file and volume for a given event and pack."""
    return _get_pack_sound_entry(
        event,
        pack_dir,
        soundpacks_dir=SOUNDPACKS_DIR,
        default_pack=DEFAULT_PACK,
        logger=logger,
    )


def get_sound_file(event: str, pack_dir: str) -> Path | None:
    """Resolve the sound file for a given event and pack."""
    sound_file, _ = get_sound_entry(event, pack_dir)
    return sound_file


def _play_sound_file(sound_file: Path, block: bool = False, volume: float = 1.0) -> bool:
    """Play a sound file with optional volume control."""
    # Clamp volume to valid range
    volume = max(0.0, min(1.0, volume))
    if volume <= 0.0:
        logger.debug(f"Skipping silent sound playback: {sound_file}")
        return True

    # Always prefer sound_lib when available (supports volume, stop, better reliability)
    if SOUND_LIB_AVAILABLE:
        try:
            from sound_lib import stream

            # Clean up finished streams to prevent memory leak
            _active_streams[:] = [s for s in _active_streams if s.is_playing]

            s = stream.FileStream(file=str(sound_file))
            s.volume = volume
            s.play()
            if block:
                # Wait for playback to complete
                import time

                while s.is_playing:
                    time.sleep(0.1)
                s.free()
            else:
                # Keep reference to prevent garbage collection during playback
                _active_streams.append(s)
            logger.debug(f"Played sound using sound_lib at volume {volume}: {sound_file}")
            return True
        except Exception as e:
            logger.debug(f"sound_lib playback failed, falling back to playsound3: {e}")

    # Fall back to playsound3 (no volume control)
    if not PLAYSOUND_AVAILABLE or playsound is None:
        logger.warning("No audio backend available")
        return False

    try:
        # Convert path for cross-platform compatibility
        if platform.system() == "Windows":
            sound_path = str(sound_file).replace("\\", "/")
        else:
            sound_path = str(sound_file)
        if volume < 1.0:
            logger.debug(
                f"Volume adjustment requested ({volume}) but playsound3 doesn't support it"
            )
        playsound(sound_path, block=block)
        logger.debug(f"Played sound using playsound3: {sound_file}")
        return True
    except Exception as e:
        logger.warning(f"playsound3 failed: {e}")
        return False


def play_sound_file(sound_file: Path) -> bool:
    """Public API to play a sound file. Returns True if successful."""
    return _play_sound_file(sound_file)


def stop_all_sounds() -> None:
    """Stop all currently playing sound_lib streams."""
    import contextlib

    for s in list(_active_streams):
        with contextlib.suppress(Exception):
            s.stop()
    _active_streams.clear()


class PreviewPlayer:
    """Sound preview player with stop support."""

    def __init__(self):
        """Initialize the preview player."""
        self._current_stream = None
        self._is_playing = False

    def play(self, sound_file: Path, volume: float = 1.0) -> bool:
        """Play a sound file for preview."""
        # Stop any current playback first
        self.stop()

        if not sound_file.exists():
            logger.warning(f"Sound file not found: {sound_file}")
            return False

        # Clamp volume to valid range
        volume = max(0.0, min(1.0, volume))

        if SOUND_LIB_AVAILABLE:
            return self._play_with_sound_lib(sound_file, volume)
        if PLAYSOUND_AVAILABLE:
            return self._play_with_playsound(sound_file)
        logger.warning("No audio backend available")
        return False

    def _play_with_sound_lib(self, sound_file: Path, volume: float = 1.0) -> bool:
        """Play using sound_lib (supports stop and volume)."""
        try:
            from sound_lib import stream

            self._current_stream = stream.FileStream(file=str(sound_file))
            self._current_stream.volume = volume
            self._current_stream.play()
            self._is_playing = True
            logger.debug(f"Playing preview with sound_lib at volume {volume}: {sound_file}")
            return True
        except Exception as e:
            logger.warning(f"sound_lib playback failed: {e}")
            self._current_stream = None
            self._is_playing = False
            return False

    def _play_with_playsound(self, sound_file: Path) -> bool:
        """Play using playsound3 (no stop or volume support)."""
        try:
            if platform.system() == "Windows":
                sound_path = str(sound_file).replace("\\", "/")
            else:
                sound_path = str(sound_file)
            playsound(sound_path, block=False)
            self._is_playing = True
            logger.debug(f"Playing preview with playsound3: {sound_file}")
            return True
        except Exception as e:
            logger.warning(f"playsound3 playback failed: {e}")
            self._is_playing = False
            return False

    def stop(self) -> None:
        """Stop the currently playing preview."""
        if self._current_stream is not None:
            try:
                self._current_stream.stop()
                self._current_stream.free()
            except Exception as e:
                logger.debug(f"Error stopping sound: {e}")
            finally:
                self._current_stream = None

        self._is_playing = False

    def is_playing(self) -> bool:
        """Check if a preview is currently playing."""
        if self._current_stream is not None:
            try:
                return self._current_stream.is_playing
            except Exception:
                pass
        return self._is_playing

    def toggle(self, sound_file: Path) -> bool:
        """Toggle play/stop for a sound file."""
        if self.is_playing():
            self.stop()
            return False
        self.play(sound_file)
        return True


# Global preview player instance
_preview_player: PreviewPlayer | None = None


def get_preview_player() -> PreviewPlayer:
    """Get the global preview player instance."""
    global _preview_player
    if _preview_player is None:
        _preview_player = PreviewPlayer()
    return _preview_player


def is_playsound_available() -> bool:
    """Check if playsound3 is available."""
    return PLAYSOUND_AVAILABLE


# Backwards compatibility alias
is_sound_lib_available = is_playsound_available


def play_notification_sound(
    event: str,
    pack_dir: str,
    *,
    muted_events: Collection[str] | None = None,
) -> None:
    """Play a notification sound for the given event and pack."""
    if is_sound_event_muted(event, muted_events):
        logger.debug(f"Skipping muted sound event: {event}")
        return

    sound_file, volume = get_sound_entry(event, pack_dir)
    if not sound_file:
        logger.warning("Sound file not found.")
        return

    if not _play_sound_file(sound_file, volume=volume):
        logger.warning("Sound playback not available or all methods failed.")


def play_sample_sound(pack_dir: str) -> None:
    """Play a sample (alert) sound from the given pack."""
    play_notification_sound(DEFAULT_EVENT, pack_dir)


def play_startup_sound(
    pack_dir: str = DEFAULT_PACK, *, muted_events: Collection[str] | None = None
) -> None:
    """Play the application startup sound."""
    try:
        play_notification_sound("startup", pack_dir, muted_events=muted_events)
        logger.debug(f"Played startup sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play startup sound: {e}")


def play_exit_sound(
    pack_dir: str = DEFAULT_PACK, *, muted_events: Collection[str] | None = None
) -> None:
    """Play the application exit sound."""
    try:
        if is_sound_event_muted("exit", muted_events):
            logger.debug("Skipping muted sound event: exit")
            return

        sound_file, volume = get_sound_entry("exit", pack_dir)
        logger.debug(
            "[packaging-diag] exit sound async: pack=%s file=%s exists=%s volume=%s sound_lib=%s playsound3=%s",
            pack_dir,
            sound_file,
            bool(sound_file and sound_file.exists()),
            volume,
            SOUND_LIB_AVAILABLE,
            PLAYSOUND_AVAILABLE,
        )
        if not sound_file:
            logger.warning("Exit sound file not found.")
            return
        _play_sound_file(sound_file, volume=volume)
        logger.debug(f"Played exit sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play exit sound: {e}")


def play_exit_sound_blocking(
    pack_dir: str = DEFAULT_PACK, *, muted_events: Collection[str] | None = None
) -> None:
    """Play the application exit sound and wait for it to finish."""
    try:
        if is_sound_event_muted("exit", muted_events):
            logger.debug("Skipping muted sound event: exit")
            return

        sound_file, volume = get_sound_entry("exit", pack_dir)
        logger.debug(
            "[packaging-diag] exit sound blocking: pack=%s file=%s exists=%s volume=%s sound_lib=%s playsound3=%s",
            pack_dir,
            sound_file,
            bool(sound_file and sound_file.exists()),
            volume,
            SOUND_LIB_AVAILABLE,
            PLAYSOUND_AVAILABLE,
        )
        if not sound_file:
            logger.warning("Exit sound file not found.")
            return

        if _play_sound_file(sound_file, block=True, volume=volume):
            logger.debug(f"Played exit sound (blocking) from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play exit sound: {e}")


def play_error_sound(
    pack_dir: str = DEFAULT_PACK, *, muted_events: Collection[str] | None = None
) -> None:
    """Play an error sound."""
    try:
        play_notification_sound("error", pack_dir, muted_events=muted_events)
        logger.debug(f"Played error sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play error sound: {e}")


def play_success_sound(
    pack_dir: str = DEFAULT_PACK, *, muted_events: Collection[str] | None = None
) -> None:
    """Play a success sound."""
    try:
        play_notification_sound("success", pack_dir, muted_events=muted_events)
        logger.debug(f"Played success sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play success sound: {e}")


def play_data_updated_sound(
    pack_dir: str = DEFAULT_PACK, *, muted_events: Collection[str] | None = None
) -> None:
    """Play a sound when weather data is successfully refreshed."""
    try:
        play_notification_sound("data_updated", pack_dir, muted_events=muted_events)
        logger.debug(f"Played data_updated sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play data_updated sound: {e}")


def play_fetch_error_sound(
    pack_dir: str = DEFAULT_PACK, *, muted_events: Collection[str] | None = None
) -> None:
    """Play a sound when a weather data fetch fails."""
    try:
        play_notification_sound("fetch_error", pack_dir, muted_events=muted_events)
        logger.debug(f"Played fetch_error sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play fetch_error sound: {e}")


def get_available_sound_packs() -> dict[str, dict]:
    """Get all available sound packs with their metadata."""
    return _get_available_sound_packs(soundpacks_dir=SOUNDPACKS_DIR, logger=logger)


def get_sound_pack_sounds(pack_dir: str) -> dict[str, str]:
    """Get all sounds available in a sound pack."""
    return _get_pack_sounds(pack_dir, soundpacks_dir=SOUNDPACKS_DIR, logger=logger)


def get_sound_entry_for_candidates(
    candidates: list[str], pack_dir: str
) -> tuple[Path | None, float]:
    """Resolve a sound file and volume trying multiple candidate event keys."""
    return _get_pack_sound_entry_for_candidates(
        candidates,
        pack_dir,
        soundpacks_dir=SOUNDPACKS_DIR,
        default_pack=DEFAULT_PACK,
        default_event=DEFAULT_EVENT,
    )


def get_sound_file_for_candidates(candidates: list[str], pack_dir: str) -> Path | None:
    """Resolve a sound file trying multiple candidate event keys."""
    sound_file, _ = get_sound_entry_for_candidates(candidates, pack_dir)
    return sound_file


def play_notification_sound_candidates(
    candidates: list[str],
    pack_dir: str,
    *,
    logical_event: str | None = None,
    muted_events: Collection[str] | None = None,
) -> None:
    """Play the first available sound from a list of candidate event keys."""
    effective_event = logical_event or (candidates[0] if candidates else None)
    if effective_event and is_sound_event_muted(effective_event, muted_events):
        logger.debug(f"Skipping muted sound event: {effective_event}")
        return

    filtered_candidates = [
        candidate for candidate in candidates if not is_sound_event_muted(candidate, muted_events)
    ]
    if not filtered_candidates:
        logger.debug("All candidate sound events are muted; skipping playback")
        return

    sound_file, volume = get_sound_entry_for_candidates(filtered_candidates, pack_dir)
    if not sound_file:
        logger.warning("No candidate sound file found.")
        return
    if not _play_sound_file(sound_file, volume=volume):
        logger.warning("Sound playback not available or all methods failed.")


def validate_sound_pack(pack_path: Path) -> tuple[bool, str]:
    """Validate a sound pack directory."""
    return _validate_sound_pack(pack_path)
