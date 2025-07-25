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


def get_available_sound_packs() -> dict[str, dict]:
    """Get all available sound packs with their metadata."""
    sound_packs = {}

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
                pack_data = json.load(f)

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
            pack_data = json.load(f)
        return pack_data.get("sounds", {})
    except Exception as e:
        logger.error(f"Failed to read sound pack {pack_dir}: {e}")
        return {}


def validate_sound_pack(pack_path: Path) -> tuple[bool, str]:
    """Validate a sound pack directory.

    Returns:
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

        for sound_name, sound_file in sounds.items():
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
