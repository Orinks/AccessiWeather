from __future__ import annotations

import json
import logging

from .constants import FRIENDLY_ALERT_CATEGORIES

logger = logging.getLogger(__name__)


def load_sound_packs(dlg) -> None:
    """Populate dlg.sound_packs by scanning soundpacks_dir for pack.json files."""
    dlg.sound_packs.clear()
    if not dlg.soundpacks_dir.exists():
        return
    for pack_dir in dlg.soundpacks_dir.iterdir():
        if not pack_dir.is_dir():
            continue
        pack_json = pack_dir / "pack.json"
        if not pack_json.exists():
            continue
        try:
            with open(pack_json, encoding="utf-8") as f:
                pack_data = json.load(f)
            pack_data["directory"] = pack_dir.name
            pack_data["path"] = pack_dir
            dlg.sound_packs[pack_dir.name] = pack_data
        except Exception as e:
            logger.error(f"Failed to load sound pack {pack_dir.name}: {e}")


def refresh_pack_list(dlg) -> None:
    """Refresh the DetailedList with current dlg.sound_packs items."""
    if not getattr(dlg, "pack_list", None):
        return

    items: list[dict] = []
    for pack_id, pack_info in dlg.sound_packs.items():
        pack_name = pack_info.get("name", pack_id)
        author = pack_info.get("author", "Unknown")
        items.append(
            {
                "pack_id": pack_id,
                "pack_info": pack_info,
                "title": pack_name,
                "subtitle": f"by {author}",
                "icon": None,
            }
        )

    dlg.pack_list.data = items


def update_pack_details(dlg) -> None:
    """Update the right-hand details and mapping selection based on selected pack."""
    if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
        dlg.pack_name_label.text = "No pack selected"
        dlg.pack_author_label.text = ""
        dlg.pack_description_label.text = ""
        dlg.sound_selection.items = []
        return

    pack_info = dlg.sound_packs[dlg.selected_pack]

    # Update pack info labels
    dlg.pack_name_label.text = pack_info.get("name", dlg.selected_pack)
    dlg.pack_author_label.text = f"Author: {pack_info.get('author', 'Unknown')}"
    dlg.pack_description_label.text = pack_info.get("description", "No description available")

    # Build sound items for the list
    sounds = pack_info.get("sounds", {})
    sound_items = []
    for sound_name, sound_file in sounds.items():
        sound_path = pack_info["path"] / sound_file
        status = "✓" if sound_path.exists() else "✗"
        friendly_name = sound_name.title()
        for display_name, technical_key in FRIENDLY_ALERT_CATEGORIES:
            if technical_key == sound_name:
                friendly_name = display_name
                break
        display_name = f"{friendly_name} ({sound_file}) - {status} {'Available' if sound_path.exists() else 'Missing'}"
        sound_items.append(
            {
                "display_name": display_name,
                "sound_name": sound_name,
                "sound_file": sound_file,
                "exists": sound_path.exists(),
            }
        )
    dlg.sound_selection.items = sound_items

    # Preselect a mapping category that exists in this pack
    try:
        if dlg.mapping_key_selection is not None:
            sounds_keys = set(sounds.keys())
            mapping_items = getattr(dlg.mapping_key_selection, "items", []) or []
            selected_item = None
            for item in mapping_items:
                technical_key = None
                try:
                    technical_key = getattr(item, "technical_key", None)
                    if not technical_key and isinstance(item, dict):
                        technical_key = item.get("technical_key")
                    if not technical_key:
                        dn = getattr(item, "display_name", None)
                        if dn is not None:
                            tk2 = getattr(dn, "technical_key", None)
                            if tk2:
                                technical_key = tk2
                            else:
                                name = getattr(dn, "display_name", None) if dn is not None else None
                                if not name and isinstance(dn, str):
                                    name = dn
                                if name:
                                    for _name, _key in FRIENDLY_ALERT_CATEGORIES:
                                        if _name == name:
                                            technical_key = _key
                                            break
                except Exception:
                    technical_key = None
                if technical_key and technical_key in sounds_keys:
                    selected_item = item
                    break
            if selected_item is None and mapping_items:
                selected_item = mapping_items[0]
            if selected_item is not None:
                dlg.mapping_key_selection.value = selected_item
                # Update file input/preview for selected
                dlg._on_mapping_key_change(dlg.mapping_key_selection)
    except Exception as e:
        logger.warning(f"Failed to update mapping selection: {e}")
