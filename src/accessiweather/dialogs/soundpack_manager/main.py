from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path

import toga
from toga.style.pack import Pack

from ...notifications.sound_pack_installer import SoundPackInstaller
from ..community_packs_browser_dialog import CommunityPacksBrowserDialog
from . import (
    mappings as map_mod,
    ops as ops_mod,
    state as state_mod,
    ui as ui_mod,
    wizard_ops as wiz_mod,
)
from .community import CommunityIntegration

logger = logging.getLogger(__name__)


class SoundPackManagerDialog:
    """Orchestrates the modular Sound Pack Manager dialog.

    This class wires UI components (built in ui.py) with state, mapping, and
    filesystem operations implemented in sibling modules. It replaces the
    previous monolithic dialog, avoiding duplicated UI and logic.
    """

    def __init__(self, app: toga.App, current_pack: str = "default") -> None:
        """Construct the dialog orchestrator.

        Parameters
        ----------
        app: toga.App
            The running Toga app instance used for dialogs and file pickers.
        current_pack: str
            The pack id currently active in settings (used for initial focus).

        """
        self.app = app
        self.current_pack = current_pack
        self.selected_pack: str | None = None

        # Paths
        self.soundpacks_dir = Path(__file__).parent.parent / "soundpacks"
        self.soundpacks_dir.mkdir(exist_ok=True)

        # External services
        self.community_service = None
        self.installer = SoundPackInstaller(self.soundpacks_dir)

        # UI component placeholders used by the subpanels
        self.dialog: toga.Window | None = None
        self.pack_list = None
        self.pack_info_box = None
        self.pack_name_label = None
        self.pack_author_label = None
        self.pack_description_label = None
        self.sound_selection = None
        self.preview_button = None
        self.select_button = None
        self.delete_button = None
        self.import_button = None
        self.close_button = None
        self.mapping_key_selection = None
        self.mapping_file_input = None
        self.mapping_browse_button = None
        self.mapping_preview_button = None
        self.simple_key_input = None
        self.simple_file_button = None
        self.simple_remove_button = None

        # Data containers
        self.sound_packs: dict = {}

        # Initial load and UI creation
        self._load_sound_packs()
        self._create_dialog()

    # State helpers
    def _load_sound_packs(self) -> None:
        state_mod.load_sound_packs(self)

    def _refresh_pack_list(self) -> None:
        state_mod.refresh_pack_list(self)

    def _update_pack_details(self) -> None:
        state_mod.update_pack_details(self)

    # Mapping/meta helpers needed by mapping ops
    def _load_pack_meta(self, pack_info: dict) -> dict:
        return ops_mod.load_pack_meta(pack_info)

    def _save_pack_meta(self, pack_info: dict, meta: dict) -> None:
        ops_mod.save_pack_meta(pack_info, meta)

    # UI creation
    def _create_dialog(self) -> None:
        """Create dialog using the modular UI composer."""
        ui_mod.create_dialog_ui(self)

    # Event handlers
    def _on_pack_selected(self, widget) -> None:
        if not widget.selection:
            return
        sel = widget.selection
        pack_id = getattr(sel, "pack_id", None) or getattr(sel, "value", None) or None
        if isinstance(pack_id, dict):
            pack_id = pack_id.get("pack_id")
        self.selected_pack = pack_id
        self._update_pack_details()
        # Enable buttons when a pack is selected
        if getattr(self, "select_button", None):
            self.select_button.enabled = True
        if getattr(self, "duplicate_button", None):
            self.duplicate_button.enabled = True
        if getattr(self, "edit_button", None):
            self.edit_button.enabled = True
        if getattr(self, "delete_button", None):
            self.delete_button.enabled = bool(pack_id and pack_id != "default")
        if getattr(self, "share_button", None):
            self.share_button.enabled = bool(pack_id)

    def _on_sound_selected(self, widget) -> None:
        # Enable preview button only if the actual sound file exists
        if widget.value is None:
            if getattr(self, "preview_button", None):
                self.preview_button.enabled = False
            return
        if self.selected_pack and self.selected_pack in self.sound_packs:
            pack_info = self.sound_packs[self.selected_pack]
            try:
                sound_path = pack_info["path"] / widget.value.sound_file
                self.preview_button.enabled = sound_path.exists() and sound_path.stat().st_size > 0
            except Exception:
                self.preview_button.enabled = False
        else:
            if getattr(self, "preview_button", None):
                self.preview_button.enabled = False

    def _on_preview_sound(self, widget) -> None:
        map_mod.preview_selected_sound(self, widget)

    def _on_import_pack(self, widget) -> None:
        try:
            self.app.main_window.open_file_dialog(
                title="Select Sound Pack ZIP File",
                file_types=["zip"],
                on_result=lambda w, path=None: ops_mod.import_pack_file(self, w, path),
            )
        except Exception as e:
            logger.error(f"Failed to open import dialog: {e}")
            self.app.main_window.error_dialog("Import Error", f"Failed to open import dialog: {e}")

    def _on_simple_choose_file(self, widget) -> None:
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            return
        key = (self.simple_key_input.value or "").strip().lower()
        if not key:
            self.app.main_window.info_dialog("Missing Key", "Please enter a mapping key first.")
            return
        self.app.main_window.open_file_dialog(
            title="Select Audio File",
            file_types=["wav", "mp3", "ogg", "flac"],
            on_result=lambda w, path=None: map_mod.apply_simple_mapping(self, key, path),
        )

    def _on_simple_remove_mapping(self, widget) -> None:
        map_mod.on_simple_remove_mapping(self, widget)

    def _on_mapping_key_change(self, widget) -> None:
        map_mod.on_mapping_key_change(self, widget)

    def _on_browse_mapping_file(self, widget) -> None:
        map_mod.on_browse_mapping_file(self, widget)

    def _on_preview_mapping(self, widget) -> None:
        map_mod.preview_mapping(self, widget)

    def _on_delete_pack(self, widget) -> None:
        ops_mod.delete_pack(self, widget)

    def _on_create_pack(self, widget) -> None:
        ops_mod.create_pack(self)

    def _on_duplicate_pack(self, widget) -> None:
        ops_mod.duplicate_pack(self)

    def _on_edit_pack(self, widget) -> None:
        """Open a small editor to modify name, author, and description of the pack."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            return
        pack_info = self.sound_packs[self.selected_pack]
        pack_json_path = pack_info["path"] / "pack.json"
        # Load existing metadata
        meta = {}
        try:
            with open(pack_json_path, encoding="utf-8") as f:
                meta = json.load(f)  # type: ignore[name-defined]
        except Exception:
            meta = {}
        # Create a simple modal window with inputs
        edit_win = toga.Window(title="Edit Sound Pack Metadata", size=(480, 300), resizable=False)
        box = toga.Box(style=Pack(direction="column", padding=10))
        name_input = toga.TextInput(
            value=meta.get("name", self.selected_pack), style=Pack(margin_bottom=8)
        )
        author_input = toga.TextInput(value=meta.get("author", ""), style=Pack(margin_bottom=8))
        desc_input = toga.MultilineTextInput(
            value=meta.get("description", ""), style=Pack(flex=1, margin_bottom=8)
        )
        box.add(toga.Label("Name:"))
        box.add(name_input)
        box.add(toga.Label("Author:"))
        box.add(author_input)
        box.add(toga.Label("Description:"))
        box.add(desc_input)
        btn_row = toga.Box(style=Pack(direction="row"))

        def _save_changes(_):
            try:
                updated = {
                    **meta,
                    "name": (name_input.value or self.selected_pack).strip(),
                    "author": (author_input.value or "").strip(),
                    "description": (desc_input.value or "").strip(),
                }
                with open(pack_json_path, "w", encoding="utf-8") as f:
                    json.dump(updated, f, indent=2)  # type: ignore[name-defined]
                self._load_sound_packs()
                self._refresh_pack_list()
                self._update_pack_details()
                edit_win.close()
                self.app.main_window.info_dialog("Pack Updated", "Sound pack metadata updated.")
            except Exception as e:
                logger.error(f"Failed to save pack metadata: {e}")
                self.app.main_window.error_dialog(
                    "Save Error", f"Failed to save pack metadata: {e}"
                )

        def _cancel(_):
            edit_win.close()

        save_btn = toga.Button("Save", on_press=_save_changes, style=Pack(margin_right=10))
        cancel_btn = toga.Button("Cancel", on_press=_cancel)
        btn_row.add(save_btn)
        btn_row.add(cancel_btn)
        box.add(btn_row)
        edit_win.content = box
        self.app.windows.add(edit_win)
        edit_win.show()

    def _on_open_pack(self, widget) -> None:
        if self.selected_pack:
            self.current_pack = self.selected_pack
            self._update_pack_details()

    def _on_create_pack_wizard(self, widget) -> None:
        try:
            from ..soundpack_wizard_dialog import SoundPackWizardDialog
        except Exception:
            from accessiweather.dialogs.soundpack_wizard_dialog import (
                SoundPackWizardDialog,  # noqa: F401
            )

        def _create_from_wizard(state) -> str:
            return wiz_mod.create_pack_from_wizard_state(self, state)

        def _on_complete(new_pack_id: str | None) -> None:
            if not new_pack_id:
                return
            try:
                self._load_sound_packs()
                self._refresh_pack_list()
                self.selected_pack = new_pack_id
                self.current_pack = new_pack_id
                self._update_pack_details()
                with contextlib.suppress(Exception):
                    self.app.main_window.info_dialog(
                        "Pack Created",
                        f"Sound pack '{self.sound_packs[new_pack_id].get('name', new_pack_id)}' created.",
                    )
            except Exception as e:
                logger.error(f"Failed to finalize wizard pack creation: {e}")

        wizard = SoundPackWizardDialog(
            app=self.app,
            soundpacks_dir=self.soundpacks_dir,
            friendly_categories=None,  # The dialog has its own defaults
            create_pack_callback=_create_from_wizard,
            on_complete=_on_complete,
        )
        wizard.show()

    # Community integration
    def _on_browse_community_packs(self, widget) -> None:
        dlg = CommunityPacksBrowserDialog(
            app=self.app,
            service=getattr(self, "community_service", None),
            installer=self.installer,
            on_installed=CommunityIntegration(self).on_installed,
        )
        dlg.show()

    def _handle_community_installed(self, pack_display_name: str) -> None:
        try:
            self._load_sound_packs()
            self._refresh_pack_list()
            for pack_id, info in self.sound_packs.items():
                if info.get("name") == pack_display_name:
                    self.selected_pack = pack_id
                    self.current_pack = pack_id
                    self._update_pack_details()
                    break
        except Exception:
            pass

    def _on_close(self, widget) -> None:
        try:
            if getattr(self, "community_service", None):
                asyncio.create_task(self.community_service.aclose())
        except Exception:
            pass
        if self.dialog:
            self.dialog.close()


__all__ = ["SoundPackManagerDialog"]
