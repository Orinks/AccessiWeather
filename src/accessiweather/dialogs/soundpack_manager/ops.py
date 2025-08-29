from __future__ import annotations

import contextlib
import json
import logging
import shutil
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


# Pack.json helpers (mirror in-dialog helpers but usable from module functions)
def load_pack_meta(pack_info: dict) -> dict:
    pack_json_path = pack_info["path"] / "pack.json"
    with open(pack_json_path, encoding="utf-8") as f:
        return json.load(f)


def save_pack_meta(pack_info: dict, meta: dict) -> None:
    pack_json_path = pack_info["path"] / "pack.json"
    with open(pack_json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


# File copy helper


def copy_into_pack_if_needed(src: Path, dst_dir: Path) -> str:
    """Copy src into dst_dir if needed. Returns the dest filename used."""
    dest = dst_dir / src.name
    if src.resolve() != dest.resolve():
        with contextlib.suppress(Exception):
            shutil.copy2(src, dest)
    return dest.name


# Operations


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
            dlg._update_pack_details()
            dlg.app.main_window.info_dialog(
                "Import Successful", f"Sound pack '{pack_name}' has been imported successfully."
            )
    except Exception as e:
        logger.error(f"Failed to import sound pack: {e}")
        dlg.app.main_window.error_dialog("Import Error", f"Failed to import sound pack: {e}")


def create_pack(dlg) -> None:
    try:
        base = "custom"
        idx = 1
        while True:
            pack_id = f"{base}_{idx}"
            pack_dir = dlg.soundpacks_dir / pack_id
            if not pack_dir.exists():
                break
            idx += 1
        pack_dir.mkdir(parents=True, exist_ok=False)
        meta = {
            "name": f"Custom Pack {idx}",
            "author": "",
            "description": "A new custom sound pack.",
            "sounds": {
                "alert": "alert.wav",
                "notify": "notify.wav",
            },
        }
        try:
            with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write pack.json: {e}")
        dlg._load_sound_packs()
        dlg._refresh_pack_list()
        dlg.selected_pack = pack_id
        dlg.current_pack = pack_id
        dlg._update_pack_details()
        if hasattr(dlg, "duplicate_button"):
            dlg.duplicate_button.enabled = True
        if hasattr(dlg, "edit_button"):
            dlg.edit_button.enabled = True
        if hasattr(dlg, "select_button"):
            dlg.select_button.enabled = True
        if hasattr(dlg, "delete_button"):
            dlg.delete_button.enabled = pack_id != "default"
        dlg.app.main_window.info_dialog(
            "Pack Created", f"Created new sound pack '{meta['name']}' (ID: {pack_id})."
        )
    except Exception as e:
        logger.error(f"Failed to create sound pack: {e}")
        dlg.app.main_window.error_dialog("Create Error", f"Failed to create sound pack: {e}")


def duplicate_pack(dlg) -> None:
    if not dlg.selected_pack or dlg.selected_pack not in dlg.sound_packs:
        return
    try:
        src_info = dlg.sound_packs[dlg.selected_pack]
        src_dir = src_info.get("path")
        if not src_dir or not src_dir.exists():
            return
        base = f"{dlg.selected_pack}_copy"
        candidate = base
        suffix = 2
        while (dlg.soundpacks_dir / candidate).exists():
            candidate = f"{base}{suffix}"
            suffix += 1
        dst_dir = dlg.soundpacks_dir / candidate
        shutil.copytree(src_dir, dst_dir)
        pack_json_path = dst_dir / "pack.json"
        try:
            with open(pack_json_path, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
        name = meta.get("name", candidate)
        if "(Copy)" not in name:
            meta["name"] = f"{name} (Copy)"
        try:
            with open(pack_json_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write pack.json: {e}")
        dlg._load_sound_packs()
        dlg._refresh_pack_list()
        dlg.selected_pack = candidate
        dlg.current_pack = candidate
        dlg._update_pack_details()
        dlg.app.main_window.info_dialog(
            "Pack Duplicated",
            f"Created '{name} (Copy)'.",
        )
    except Exception as e:
        logger.error(f"Failed to duplicate sound pack: {e}")
        dlg.app.main_window.error_dialog("Duplicate Error", f"Failed to duplicate sound pack: {e}")


def delete_pack(dlg, widget) -> None:
    if not dlg.selected_pack or dlg.selected_pack == "default":
        return
    pack_info = dlg.sound_packs.get(dlg.selected_pack, {})
    pack_name = pack_info.get("name", dlg.selected_pack)
    result = dlg.app.main_window.question_dialog(
        "Delete Sound Pack",
        f"Are you sure you want to delete the sound pack '{pack_name}'? This action cannot be undone.",
    )
    if result:
        try:
            pack_path = pack_info.get("path")
            if pack_path and pack_path.exists():
                shutil.rmtree(pack_path)
            dlg._load_sound_packs()
            dlg._refresh_pack_list()
            dlg.selected_pack = None
            dlg._update_pack_details()
            dlg.select_button.enabled = False
            dlg.delete_button.enabled = False
            dlg.app.main_window.info_dialog(
                "Pack Deleted", f"Sound pack '{pack_name}' has been deleted."
            )
        except Exception as e:
            logger.error(f"Failed to delete sound pack: {e}")
            dlg.app.main_window.error_dialog("Delete Error", f"Failed to delete sound pack: {e}")
