"""Sound pack lookup and validation helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


def parse_sound_entry(
    entry: str | dict[str, Any], event: str, volumes: dict[str, float] | None = None
) -> tuple[str, float]:
    """Parse a pack sound entry and return a clamped filename/volume pair."""
    if isinstance(entry, dict):
        filename = entry.get("file", f"{event}.ogg")
        volume = entry.get("volume", 1.0)
    else:
        filename = str(entry) if entry else f"{event}.ogg"
        volume = volumes[event] if volumes and event in volumes else 1.0

    try:
        volume = max(0.0, min(1.0, float(volume)))
    except (TypeError, ValueError):
        volume = 1.0

    return filename, volume


def get_sound_entry(
    event: str,
    pack_dir: str,
    *,
    soundpacks_dir: Path,
    default_pack: str,
    logger: logging.Logger,
) -> tuple[Path | None, float]:
    """Resolve a sound file and volume for an event in a pack."""
    pack_path = soundpacks_dir / pack_dir
    pack_json = pack_path / "pack.json"
    if not pack_json.exists():
        logger.warning(f"pack.json not found in {pack_path}, falling back to default.")
        pack_path = soundpacks_dir / default_pack
        pack_json = pack_path / "pack.json"
        if not pack_json.exists():
            logger.error("Default sound pack is missing!")
            return None, 1.0
    try:
        sounds, volumes = load_pack_sounds(pack_json)
        filename, volume = parse_sound_entry(sounds.get(event, f"{event}.ogg"), event, volumes)

        sound_file = pack_path / filename
        if not sound_file.exists():
            logger.warning(f"Sound file {sound_file} not found, falling back to default pack.")
            if pack_dir != default_pack:
                return get_sound_entry(
                    event,
                    default_pack,
                    soundpacks_dir=soundpacks_dir,
                    default_pack=default_pack,
                    logger=logger,
                )
            return None, 1.0
        return sound_file, volume
    except Exception as e:
        logger.error(f"Error reading sound pack: {e}")
        if pack_dir != default_pack:
            logger.info("Falling back to default sound pack due to error")
            return get_sound_entry(
                event,
                default_pack,
                soundpacks_dir=soundpacks_dir,
                default_pack=default_pack,
                logger=logger,
            )
        return None, 1.0


def get_available_sound_packs(*, soundpacks_dir: Path, logger: logging.Logger) -> dict[str, dict]:
    """Return all available sound packs with metadata."""
    sound_packs: dict[str, dict] = {}
    if not soundpacks_dir.exists():
        return sound_packs

    for pack_dir in soundpacks_dir.iterdir():
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


def get_sound_pack_sounds(
    pack_dir: str, *, soundpacks_dir: Path, logger: logging.Logger
) -> dict[str, str]:
    """Return a pack's event-to-filename sound map."""
    pack_json = soundpacks_dir / pack_dir / "pack.json"
    if not pack_json.exists():
        return {}

    try:
        sounds, _volumes = load_pack_sounds(pack_json)
        result: dict[str, str] = {}
        for event, entry in sounds.items():
            if isinstance(entry, dict):
                result[event] = entry.get("file", f"{event}.ogg")
            else:
                result[event] = str(entry)
        return result
    except Exception as e:
        logger.error(f"Failed to read sound pack {pack_dir}: {e}")
        return {}


def get_sound_entry_for_candidates(
    candidates: list[str],
    pack_dir: str,
    *,
    soundpacks_dir: Path,
    default_pack: str,
    default_event: str,
) -> tuple[Path | None, float]:
    """Resolve a sound file and volume trying candidate event keys."""
    pack_path = soundpacks_dir / pack_dir
    pack_json = pack_path / "pack.json"

    if pack_json.exists():
        sounds, volumes = load_pack_sounds(pack_json)
        found = find_candidate_sound(candidates, pack_path, sounds, volumes)
        if found[0] is not None:
            return found

    default_pack_path = soundpacks_dir / default_pack
    default_pack_json = default_pack_path / "pack.json"
    if default_pack_json.exists():
        default_sounds, default_volumes = load_pack_sounds(default_pack_json)
        found = find_candidate_sound(candidates, default_pack_path, default_sounds, default_volumes)
        if found[0] is not None:
            return found

    return get_sound_entry(
        default_event,
        default_pack,
        soundpacks_dir=soundpacks_dir,
        default_pack=default_pack,
        logger=logging.getLogger(__name__),
    )


def validate_sound_pack(pack_path: Path) -> tuple[bool, str]:
    """Validate a sound pack directory and its pack.json contents."""
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

        if "name" not in pack_data:
            return False, "Missing 'name' field in pack.json"
        if "sounds" not in pack_data:
            return False, "Missing 'sounds' field in pack.json"

        missing_files = []
        for sound_name, sound_entry in pack_data["sounds"].items():
            sound_file = (
                sound_entry.get("file", f"{sound_name}.ogg")
                if isinstance(sound_entry, dict)
                else str(sound_entry)
            )
            if not (pack_path / sound_file).exists():
                missing_files.append(sound_file)

        if missing_files:
            return False, f"Missing sound files: {', '.join(missing_files)}"

        volumes = pack_data.get("volumes", {})
        if volumes and not isinstance(volumes, dict):
            return False, "'volumes' field must be a dictionary"

        for event, volume in volumes.items():
            try:
                vol = float(volume)
            except (TypeError, ValueError):
                return False, f"Invalid volume value for '{event}': {volume}"
            if vol < 0.0 or vol > 1.0:
                return False, f"Volume for '{event}' must be between 0.0 and 1.0"

        return True, "Sound pack is valid"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in pack.json: {e}"
    except Exception as e:
        return False, f"Error validating sound pack: {e}"


def load_pack_sounds(pack_json: Path) -> tuple[dict[str, Any], dict[str, float]]:
    """Load sound and volume mappings from a pack.json file."""
    with open(pack_json, encoding="utf-8") as f:
        meta: dict[str, Any] = json.load(f)
    sounds = meta.get("sounds", {})
    volumes = meta.get("volumes", {})
    return sounds if isinstance(sounds, dict) else {}, volumes if isinstance(volumes, dict) else {}


def find_candidate_sound(
    candidates: list[str],
    pack_path: Path,
    sounds: dict[str, Any],
    volumes: dict[str, float],
) -> tuple[Path | None, float]:
    """Find the first existing candidate sound in a loaded pack."""
    for event in candidates:
        entry = sounds.get(event)
        if entry is not None:
            filename, volume = parse_sound_entry(entry, event, volumes)
        else:
            filename = f"{event}.ogg"
            volume = volumes.get(event, 1.0)
        candidate_path = pack_path / filename
        if candidate_path.exists():
            return candidate_path, volume
    return None, 1.0
