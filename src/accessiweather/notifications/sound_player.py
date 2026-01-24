import json
import logging
import platform
import sys
from pathlib import Path
from typing import Any

# Try sound_lib first (supports stopping playback)
SOUND_LIB_AVAILABLE = False
_sound_lib_output = None
_sound_lib_stream = None

try:
    if sys.platform == "win32":
        from sound_lib import output, stream

        _sound_lib_output = output.Output()
        SOUND_LIB_AVAILABLE = True
except ImportError:
    pass
except Exception:
    pass

# Fallback to playsound3
try:
    from playsound3 import playsound

    PLAYSOUND_AVAILABLE = True
except ImportError:
    PLAYSOUND_AVAILABLE = False
    playsound = None

logger = logging.getLogger(__name__)

SOUNDPACKS_DIR = Path(__file__).parent.parent / "soundpacks"
DEFAULT_PACK = "default"
DEFAULT_EVENT = "alert"


def get_sound_file(event: str, pack_dir: str) -> Path | None:
    """Resolve the sound file for a given event and pack."""
    pack_path = SOUNDPACKS_DIR / pack_dir
    pack_json = pack_path / "pack.json"
    if not pack_json.exists():
        logger.warning(f"pack.json not found in {pack_path}, falling back to default.")
        pack_path = SOUNDPACKS_DIR / DEFAULT_PACK
        pack_json = pack_path / "pack.json"
        if not pack_json.exists():
            logger.error("Default sound pack is missing!")
            return None
    try:
        with open(pack_json, encoding="utf-8") as f:
            meta: dict[str, Any] = json.load(f)
        sounds = meta.get("sounds", {})
        if not isinstance(sounds, dict):
            sounds = {}
        filename = sounds.get(event, f"{event}.wav")
        sound_file = pack_path / filename
        if not sound_file.exists():
            logger.warning(f"Sound file {sound_file} not found, falling back to default pack.")
            if pack_dir != DEFAULT_PACK:
                return get_sound_file(event, DEFAULT_PACK)
            return None
        return sound_file
    except Exception as e:
        logger.error(f"Error reading sound pack: {e}")
        # If we failed to read the current pack and it's not the default, try the default
        if pack_dir != DEFAULT_PACK:
            logger.info("Falling back to default sound pack due to error")
            return get_sound_file(event, DEFAULT_PACK)
        return None


def _play_sound_file(sound_file: Path, block: bool = False) -> bool:
    """Try to play a sound file using playsound3; return True if played."""
    if not PLAYSOUND_AVAILABLE or playsound is None:
        logger.warning("playsound3 not available")
        return False

    try:
        # Convert path for cross-platform compatibility
        if platform.system() == "Windows":
            sound_path = str(sound_file).replace("\\", "/")
        else:
            sound_path = str(sound_file)
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
    """
    Stop all currently playing sounds.

    Note: playsound3 doesn't support stopping sounds mid-playback.
    This function is kept for API compatibility.
    """


class PreviewPlayer:
    """
    Sound preview player with stop support.

    Uses sound_lib on Windows for stop functionality,
    falls back to playsound3 (no stop support) on other platforms.
    """

    def __init__(self):
        """Initialize the preview player."""
        self._current_stream = None
        self._is_playing = False

    def play(self, sound_file: Path) -> bool:
        """
        Play a sound file for preview.

        Stops any currently playing preview first.

        Args:
            sound_file: Path to the sound file.

        Returns:
            True if playback started successfully.
        """
        # Stop any current playback first
        self.stop()

        if not sound_file.exists():
            logger.warning(f"Sound file not found: {sound_file}")
            return False

        if SOUND_LIB_AVAILABLE:
            return self._play_with_sound_lib(sound_file)
        elif PLAYSOUND_AVAILABLE:
            return self._play_with_playsound(sound_file)
        else:
            logger.warning("No audio backend available")
            return False

    def _play_with_sound_lib(self, sound_file: Path) -> bool:
        """Play using sound_lib (supports stop)."""
        try:
            from sound_lib import stream

            self._current_stream = stream.FileStream(file=str(sound_file))
            self._current_stream.play()
            self._is_playing = True
            logger.debug(f"Playing preview with sound_lib: {sound_file}")
            return True
        except Exception as e:
            logger.warning(f"sound_lib playback failed: {e}")
            self._current_stream = None
            self._is_playing = False
            return False

    def _play_with_playsound(self, sound_file: Path) -> bool:
        """Play using playsound3 (no stop support)."""
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
        """
        Toggle play/stop for a sound file.

        Args:
            sound_file: Path to the sound file.

        Returns:
            True if now playing, False if stopped.
        """
        if self.is_playing():
            self.stop()
            return False
        else:
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


def play_notification_sound(event: str, pack_dir: str) -> None:
    """Play a notification sound for the given event and pack."""
    sound_file = get_sound_file(event, pack_dir)
    if not sound_file:
        logger.warning("Sound file not found.")
        return

    if not _play_sound_file(sound_file):
        logger.warning("Sound playback not available or all methods failed.")


def play_sample_sound(pack_dir: str) -> None:
    """Play a sample (alert) sound from the given pack."""
    play_notification_sound(DEFAULT_EVENT, pack_dir)


def play_startup_sound(pack_dir: str = DEFAULT_PACK) -> None:
    """Play the application startup sound."""
    try:
        play_notification_sound("startup", pack_dir)
        logger.debug(f"Played startup sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play startup sound: {e}")


def play_exit_sound(pack_dir: str = DEFAULT_PACK) -> None:
    """Play the application exit sound."""
    try:
        play_notification_sound("exit", pack_dir)
        logger.debug(f"Played exit sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play exit sound: {e}")


def play_exit_sound_blocking(pack_dir: str = DEFAULT_PACK) -> None:
    """Play the application exit sound and wait for it to finish."""
    try:
        sound_file = get_sound_file("exit", pack_dir)
        if not sound_file:
            logger.warning("Exit sound file not found.")
            return

        # Use playsound3 with blocking playback
        if _play_sound_file(sound_file, block=True):
            logger.debug(f"Played exit sound (blocking) from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play exit sound: {e}")


def play_error_sound(pack_dir: str = DEFAULT_PACK) -> None:
    """Play an error sound."""
    try:
        play_notification_sound("error", pack_dir)
        logger.debug(f"Played error sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play error sound: {e}")


def play_success_sound(pack_dir: str = DEFAULT_PACK) -> None:
    """Play a success sound."""
    try:
        play_notification_sound("success", pack_dir)
        logger.debug(f"Played success sound from pack: {pack_dir}")
    except Exception as e:
        logger.debug(f"Failed to play success sound: {e}")


def get_available_sound_packs() -> dict[str, dict]:
    """Get all available sound packs with their metadata."""
    sound_packs: dict[str, dict] = {}

    if not SOUNDPACKS_DIR.exists():
        return sound_packs

    for pack_dir in SOUNDPACKS_DIR.iterdir():
        if not pack_dir.is_dir():
            continue

        pack_json = pack_dir / "pack.json"
        if not pack_json.exists():
            continue

        try:
            with open(pack_json, encoding="utf-8") as f:
                pack_data: dict[str, Any] = json.load(f)

            pack_data["directory"] = pack_dir.name
            pack_data["path"] = str(pack_dir)
            sound_packs[pack_dir.name] = pack_data

        except Exception as e:
            logger.error(f"Failed to load sound pack {pack_dir.name}: {e}")

    return sound_packs


def get_sound_pack_sounds(pack_dir: str) -> dict[str, str]:
    """Get all sounds available in a sound pack."""
    pack_path = SOUNDPACKS_DIR / pack_dir
    pack_json = pack_path / "pack.json"

    if not pack_json.exists():
        return {}

    try:
        with open(pack_json, encoding="utf-8") as f:
            pack_data: dict[str, Any] = json.load(f)
        sounds = pack_data.get("sounds", {})
        return sounds if isinstance(sounds, dict) else {}
    except Exception as e:
        logger.error(f"Failed to read sound pack {pack_dir}: {e}")
        return {}


def get_sound_file_for_candidates(candidates: list[str], pack_dir: str) -> Path | None:
    """
    Resolve a sound file trying multiple candidate event keys, with fallbacks.

    Tries the given pack first across all candidates, then falls back to the
    default pack. If still nothing is found, falls back to the default 'alert'
    event in the current pack (which itself may fall back to the default pack).
    """
    # Try in the requested pack
    pack_path = SOUNDPACKS_DIR / pack_dir
    pack_json = pack_path / "pack.json"

    def _load_sounds(_pack_json: Path) -> dict[str, Any]:
        try:
            with open(_pack_json, encoding="utf-8") as f:
                meta: dict[str, Any] = json.load(f)
            sounds = meta.get("sounds", {})
            return sounds if isinstance(sounds, dict) else {}
        except Exception:
            return {}

    # Candidate search in requested pack
    if pack_json.exists():
        sounds = _load_sounds(pack_json)
        for event in candidates:
            # Prefer explicit mapping if present; otherwise try event.wav
            filename = sounds.get(event) or f"{event}.wav"
            candidate_path = pack_path / filename
            if candidate_path.exists():
                return candidate_path

    # Fall back to default pack for candidates
    default_pack_path = SOUNDPACKS_DIR / DEFAULT_PACK
    default_pack_json = default_pack_path / "pack.json"
    if default_pack_json.exists():
        default_sounds = _load_sounds(default_pack_json)
        for event in candidates:
            filename = default_sounds.get(event) or f"{event}.wav"
            candidate_path = default_pack_path / filename
            if candidate_path.exists():
                return candidate_path

    # Final fallback: always use the default pack's 'alert'
    return get_sound_file(DEFAULT_EVENT, DEFAULT_PACK)


def play_notification_sound_candidates(candidates: list[str], pack_dir: str) -> None:
    """Play the first available sound from a list of candidate event keys."""
    sound_file = get_sound_file_for_candidates(candidates, pack_dir)
    if not sound_file:
        logger.warning("No candidate sound file found.")
        return
    if not _play_sound_file(sound_file):
        logger.warning("Sound playback not available or all methods failed.")


def validate_sound_pack(pack_path: Path) -> tuple[bool, str]:
    """
    Validate a sound pack directory.

    Returns
    -------
        tuple: (is_valid, error_message)

    """
    if not pack_path.exists():
        return False, "Sound pack directory does not exist"

    if not pack_path.is_dir():
        return False, "Sound pack path is not a directory"

    pack_json = pack_path / "pack.json"
    if not pack_json.exists():
        return False, "Missing pack.json file"

    try:
        with open(pack_json, encoding="utf-8") as f:
            pack_data = json.load(f)

        # Check required fields
        if "name" not in pack_data:
            return False, "Missing 'name' field in pack.json"

        if "sounds" not in pack_data:
            return False, "Missing 'sounds' field in pack.json"

        # Check if sound files exist
        sounds = pack_data["sounds"]
        missing_files = []

        for _sound_name, sound_file in sounds.items():
            sound_path = pack_path / sound_file
            if not sound_path.exists():
                missing_files.append(sound_file)

        if missing_files:
            return False, f"Missing sound files: {', '.join(missing_files)}"

        return True, "Sound pack is valid"

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in pack.json: {e}"
    except Exception as e:
        return False, f"Error validating sound pack: {e}"
