from __future__ import annotations

import contextlib
import json
import shutil
import zipfile
from pathlib import Path


def on_import_pack(dlg, widget) -> None:
    try:
        dlg.app.main_window.open_file_dialog(
            title="Select Sound Pack ZIP File",
            file_types=["zip"],
            on_result=lambda w, path=None: import_pack_file(dlg, w, path),
        )
    except Exception as e:
        dlg.logger.error(f"Failed to open import dialog: {e}")
        dlg.app.main_window.error_dialog("Import Error", f"Failed to open import dialog: {e}")


def on_simple_choose_file(dlg, widget) -> None:
    if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
        return
    key = (dlg.simple_key_input.value or "").strip().lower()
    if not key:
        dlg.app.main_window.info_dialog("Missing Key", "Please enter a mapping key first.")
        return

    def _apply(_, path=None):
        if not path:
            return
        try:
            pack_info = dlg.sound_packs[dlg.selected_pack]
            pack_json_path = pack_info["path"] / "pack.json"
            with open(pack_json_path, encoding="utf-8") as f:
                meta = json.load(f)
            sounds = meta.get("sounds", {})
            if not isinstance(sounds, dict):
                sounds = {}
            rel_name = Path(path).name
            sounds[key] = rel_name
            meta["sounds"] = sounds
            with open(pack_json_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            dst = pack_info["path"] / rel_name
            if Path(path) != dst:
                with contextlib.suppress(Exception):
                    shutil.copy2(path, dst)
            pack_info["sounds"] = sounds
            dlg._update_pack_details()
            dlg.app.main_window.info_dialog("Mapping Updated", f"Mapped '{key}' to '{rel_name}'.")
        except Exception as e:
            dlg.logger.error(f"Failed to update mapping: {e}")
            dlg.app.main_window.error_dialog("Mapping Error", f"Failed to update mapping: {e}")

    dlg.app.main_window.open_file_dialog(
        title="Select Audio File",
        file_types=["wav", "mp3", "ogg", "flac"],
        on_result=_apply,
    )


def on_simple_remove_mapping(dlg, widget) -> None:
    if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
        return
    key = (dlg.simple_key_input.value or "").strip().lower()
    if not key:
        dlg.app.main_window.info_dialog("Missing Key", "Please enter a mapping key to remove.")
        return
    try:
        pack_info = dlg.sound_packs[dlg.selected_pack]
        pack_json_path = pack_info["path"] / "pack.json"
        with open(pack_json_path, encoding="utf-8") as f:
            meta = json.load(f)
        sounds = meta.get("sounds", {}) or {}
        if key in sounds:
            sounds.pop(key, None)
            meta["sounds"] = sounds
            with open(pack_json_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            pack_info["sounds"] = sounds
            dlg._update_pack_details()
            dlg.app.main_window.info_dialog("Mapping Removed", f"Removed mapping for '{key}'.")
        else:
            dlg.app.main_window.info_dialog("Not Found", f"No mapping exists for '{key}'.")
    except Exception as e:
        dlg.logger.error(f"Failed to remove mapping: {e}")
        dlg.app.main_window.error_dialog("Remove Error", f"Failed to remove mapping: {e}")


def import_pack_file(dlg, widget, path: str | None = None) -> None:
    if not path:
        return
    try:
        with zipfile.ZipFile(path, "r") as zip_file:
            if "pack.json" not in zip_file.namelist():
                dlg.app.main_window.error_dialog(
                    "Invalid Sound Pack",
                    "The selected file is not a valid sound pack. Missing pack.json file.",
                )
                return
            with zip_file.open("pack.json") as f:
                pack_info = json.load(f)
            pack_name = pack_info.get("name", "Unknown Pack")
            pack_id = pack_name.lower().replace(" ", "_").replace("-", "_")
            pack_dir = dlg.soundpacks_dir / pack_id
            if pack_dir.exists():
                result = dlg.app.main_window.question_dialog(
                    "Pack Already Exists",
                    f"A sound pack named '{pack_name}' already exists. Do you want to overwrite it?",
                )
                if not result:
                    return
                shutil.rmtree(pack_dir)
            pack_dir.mkdir(exist_ok=True)
            zip_file.extractall(pack_dir)
            dlg._load_sound_packs()
            dlg._refresh_pack_list()
            dlg.app.main_window.info_dialog(
                "Import Successful", f"Sound pack '{pack_name}' has been imported successfully."
            )
    except Exception as e:
        dlg.logger.error(f"Failed to import sound pack: {e}")
        dlg.app.main_window.error_dialog("Import Error", f"Failed to import sound pack: {e}")
