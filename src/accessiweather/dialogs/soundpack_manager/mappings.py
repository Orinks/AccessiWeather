from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def get_technical_key_from_selection(dlg) -> str | None:
    try:
        if not dlg.mapping_key_selection or not dlg.mapping_key_selection.value:
            return None
        sel = dlg.mapping_key_selection.value
        tk = getattr(sel, "technical_key", None)
        if tk:
            return tk
        # Fallbacks
        val = getattr(sel, "value", None)
        if val is not None:
            tk2 = getattr(val, "technical_key", None)
            if tk2:
                return tk2
        dn = getattr(sel, "display_name", None)
        if dn is not None:
            tk2 = getattr(dn, "technical_key", None)
            if tk2:
                return tk2
        return None
    except Exception:
        return None


def get_display_name_from_selection(dlg) -> str | None:
    try:
        if not dlg.mapping_key_selection or not dlg.mapping_key_selection.value:
            return None
        sel = dlg.mapping_key_selection.value
        if hasattr(sel, "display_name"):
            return sel.display_name
        if isinstance(sel, dict):
            return sel.get("display_name")
        return str(sel) if sel is not None else None
    except Exception:
        return None


def on_mapping_key_change(dlg, widget) -> None:
    try:
        if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
            return
        pack_info = dlg.sound_packs[dlg.selected_pack]
        sounds = pack_info.get("sounds", {})
        key = get_technical_key_from_selection(dlg)
        current = sounds.get(key, "") if key else ""
        dlg.mapping_file_input.value = current
        if current:
            sound_path = pack_info["path"] / current
            dlg.mapping_preview_button.enabled = (
                sound_path.exists() and sound_path.stat().st_size > 0
            )
        else:
            dlg.mapping_preview_button.enabled = False
    except Exception as e:
        logger.warning(f"Failed to update mapping input: {e}")


def on_browse_mapping_file(dlg, widget) -> None:
    if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
        return
    display_name = get_display_name_from_selection(dlg)
    technical_key = get_technical_key_from_selection(dlg)
    if not technical_key:
        dlg.app.main_window.info_dialog("Missing Key", "Please choose a category first.")
        return

    def _apply(_, path=None):
        if not path:
            return
        try:
            pack_info = dlg.sound_packs[dlg.selected_pack]
            rel_name = Path(path).name
            meta = dlg._load_pack_meta(pack_info)
            sounds = meta.get("sounds", {})
            if not isinstance(sounds, dict):
                sounds = {}
            key = technical_key
            sounds[key] = rel_name
            meta["sounds"] = sounds
            dlg._save_pack_meta(pack_info, meta)
            dst = pack_info["path"] / rel_name
            if Path(path) != dst:
                try:
                    shutil.copy2(path, dst)
                except Exception as copy_err:
                    logger.warning(f"Could not copy audio file: {copy_err}")
            pack_info["sounds"] = sounds
            dlg.mapping_file_input.value = rel_name
            dlg._update_pack_details()
            dlg.app.main_window.info_dialog(
                "Mapping Updated",
                f"Mapped '{display_name or key}' to '{rel_name}' in pack '{pack_info.get('name', dlg.selected_pack)}'.",
            )
        except Exception as e:
            logger.error(f"Failed to update mapping: {e}")
            dlg.app.main_window.error_dialog("Mapping Error", f"Failed to update mapping: {e}")

    dlg.app.main_window.open_file_dialog(
        title="Select Audio File",
        file_types=["wav", "mp3", "ogg", "flac"],
        on_result=_apply,
    )


def apply_simple_mapping(dlg, key: str, path: str | None) -> None:
    if not path:
        return
    try:
        pack_info = dlg.sound_packs[dlg.selected_pack]
        meta = dlg._load_pack_meta(pack_info)
        sounds = meta.get("sounds", {})
        if not isinstance(sounds, dict):
            sounds = {}
        rel_name = Path(path).name
        sounds[key] = rel_name
        meta["sounds"] = sounds
        dlg._save_pack_meta(pack_info, meta)
        dst = pack_info["path"] / rel_name
        if Path(path) != dst:
            with contextlib.suppress(Exception):
                shutil.copy2(path, dst)
        pack_info["sounds"] = sounds
        dlg._update_pack_details()
        dlg.app.main_window.info_dialog("Mapping Updated", f"Mapped '{key}' to '{rel_name}'.")
    except Exception as e:
        logger.error(f"Failed to update mapping: {e}")
        dlg.app.main_window.error_dialog("Mapping Error", f"Failed to update mapping: {e}")


def on_simple_remove_mapping(dlg, widget) -> None:
    if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
        return
    key = (dlg.simple_key_input.value or "").strip().lower()
    if not key:
        dlg.app.main_window.info_dialog("Missing Key", "Please enter a mapping key to remove.")
        return
    try:
        pack_info = dlg.sound_packs[dlg.selected_pack]
        meta = dlg._load_pack_meta(pack_info)
        sounds = meta.get("sounds", {}) or {}
        if key in sounds:
            sounds.pop(key, None)
            meta["sounds"] = sounds
            dlg._save_pack_meta(pack_info, meta)
            pack_info["sounds"] = sounds
            dlg._update_pack_details()
            dlg.app.main_window.info_dialog("Mapping Removed", f"Removed mapping for '{key}'.")
        else:
            dlg.app.main_window.info_dialog("Not Found", f"No mapping exists for '{key}'.")
    except Exception as e:
        logger.error(f"Failed to remove mapping: {e}")
        dlg.app.main_window.error_dialog("Remove Error", f"Failed to remove mapping: {e}")


def preview_mapping(dlg, widget) -> None:
    """Preview audio for the currently selected mapping key, if available."""
    try:
        if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
            return
        technical_key = get_technical_key_from_selection(dlg)
        if not technical_key:
            return
        pack_info = dlg.sound_packs[dlg.selected_pack]
        sounds = pack_info.get("sounds", {})
        filename = sounds.get(technical_key) or f"{technical_key}.wav"
        sound_path = pack_info["path"] / filename
        if not sound_path.exists():
            dlg.app.main_window.info_dialog(
                "Sound Not Available",
                f"The sound file '{filename}' is not available in this pack.",
            )
            return
        from ...notifications.sound_player import _play_sound_file

        _play_sound_file(sound_path)
    except Exception as e:
        logger.error(f"Failed to preview mapping: {e}")
        dlg.app.main_window.error_dialog("Preview Error", f"Failed to preview mapping: {e}")


def preview_selected_sound(dlg, widget) -> None:
    """Preview the sound selected from the sound list."""
    if not dlg.sound_selection.value or not dlg.selected_pack:
        return
    try:
        sound_item = dlg.sound_selection.value
        sound_name = sound_item.sound_name
        pack_info = dlg.sound_packs[dlg.selected_pack]
        sound_path = pack_info["path"] / sound_item.sound_file
        if not sound_path.exists():
            dlg.app.main_window.info_dialog(
                "Sound Not Available",
                f"The sound file '{sound_item.sound_file}' is not available. This may be a placeholder sound pack.",
            )
            return
        from ...notifications.sound_player import play_notification_sound

        play_notification_sound(sound_name, dlg.selected_pack)
    except Exception as e:
        logger.error(f"Failed to preview sound: {e}")
        dlg.app.main_window.error_dialog("Preview Error", f"Failed to preview sound: {e}")
