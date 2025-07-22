import json
import logging
from pathlib import Path

try:
    from playsound import playsound
except ImportError:
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
            meta = json.load(f)
        filename = meta.get("sounds", {}).get(event, f"{event}.wav")
        sound_file = pack_path / filename
        if not sound_file.exists():
            logger.warning(f"Sound file {sound_file} not found, falling back to default pack.")
            if pack_dir != DEFAULT_PACK:
                return get_sound_file(event, DEFAULT_PACK)
            return None
        return sound_file
    except Exception as e:
        logger.error(f"Error reading sound pack: {e}")
        return None

def play_notification_sound(event: str, pack_dir: str) -> None:
    """Play a notification sound for the given event and pack."""
    sound_file = get_sound_file(event, pack_dir)
    if sound_file and playsound:
        try:
            playsound(str(sound_file), block=False)
        except Exception as e:
            logger.error(f"Failed to play sound: {e}")
    else:
        logger.warning("Sound playback not available or sound file missing.")

def play_sample_sound(pack_dir: str) -> None:
    """Play a sample (alert) sound from the given pack."""
    play_notification_sound(DEFAULT_EVENT, pack_dir)
