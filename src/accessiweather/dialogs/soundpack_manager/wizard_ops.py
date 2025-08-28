from __future__ import annotations

import contextlib
import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def create_pack_from_wizard_state(dlg, state) -> str:
    """Create the pack on disk from the wizard state. Returns the new pack_id."""

    def _slugify(name: str) -> str:
        slug = (name or "custom").strip().lower().replace(" ", "_").replace("-", "_")
        return slug or "custom"

    base_id = _slugify(getattr(state, "pack_name", "")) or "custom"
    pack_id = base_id
    suffix = 1
    while (dlg.soundpacks_dir / pack_id).exists():
        suffix += 1
        pack_id = f"{base_id}_{suffix}"

    pack_dir = dlg.soundpacks_dir / pack_id
    pack_dir.mkdir(parents=True, exist_ok=False)

    # Copy staged files into pack dir and build sounds mapping with filenames
    sounds: dict[str, str] = {}
    for key, src in (getattr(state, "sound_mappings", {}) or {}).items():
        try:
            src_path = Path(src)
            if not src_path.exists():
                continue
            dest_name = src_path.name
            dest_path = pack_dir / dest_name
            if dest_path.exists():
                try:
                    same = src_path.resolve() == dest_path.resolve()
                except Exception:
                    same = False
                if not same:
                    stem = dest_path.stem
                    suffix = dest_path.suffix
                    counter = 1
                    while True:
                        candidate = pack_dir / f"{stem}_{counter}{suffix}"
                        if not candidate.exists():
                            dest_path = candidate
                            dest_name = dest_path.name
                            break
                        counter += 1
            if src_path.resolve() != dest_path.resolve():
                with contextlib.suppress(Exception):
                    shutil.copy2(src_path, dest_path)
            sounds[key] = dest_name
        except Exception as copy_err:
            logger.warning(f"Failed to copy sound for {key}: {copy_err}")

    meta = {
        "name": getattr(state, "pack_name", pack_id) or pack_id,
        "author": getattr(state, "author", "") or "",
        "description": getattr(state, "description", "") or "",
        "sounds": sounds,
    }
    try:
        with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write pack.json: {e}")

    return pack_id
