"""Sound pack management dialog for AccessiWeather.

This module provides a dialog for managing sound packs, including importing new packs,
previewing sounds, and managing/editing pack contents. The active pack is selected
in Settings > General and is not changed from this manager.
"""

import asyncio
import logging
from pathlib import Path

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from ..dialogs.community_packs_browser_dialog import CommunityPacksBrowserDialog
from ..dialogs.update_progress_dialog import UpdateProgressDialog
from ..notifications.alert_sound_mapper import CANONICAL_ALERT_KEYS  # noqa: F401
from ..notifications.sound_pack_installer import SoundPackInstaller
from ..notifications.sound_player import (  # noqa: F401
    get_available_sound_packs,
    get_sound_pack_sounds,
    validate_sound_pack,
)

# Community packs imports
from ..services.community_soundpack_service import CommunitySoundPackService

# Import shared constants/datatypes for categories
from .soundpack_manager.constants import FRIENDLY_ALERT_CATEGORIES

logger = logging.getLogger(__name__)


class SoundPackManagerDialog:
    """Dialog for managing sound packs."""

    def __init__(self, app: toga.App, current_pack: str = "default"):
        """Initialize the sound pack manager dialog."""
        self.app = app
        self.current_pack = current_pack
        self.soundpacks_dir = Path(__file__).parent.parent / "soundpacks"
        self.soundpacks_dir.mkdir(exist_ok=True)

        # Sound pack data
        self.sound_packs: dict[str, dict] = {}
        self.selected_pack: str | None = None

        # UI components
        self.dialog: toga.Window | None = None
        self.pack_list: toga.DetailedList | None = None
        self.pack_info_box: toga.Box | None = None
        self.pack_name_label: toga.Label | None = None
        self.pack_author_label: toga.Label | None = None
        self.pack_description_label: toga.Label | None = None
        self.sound_selection: toga.Selection | None = None
        self.preview_button: toga.Button | None = None
        self.select_button: toga.Button | None = None
        self.delete_button: toga.Button | None = None
        self.import_button: toga.Button | None = None
        self.close_button: toga.Button | None = None
        # Community service and installer
        try:
            self.community_service = CommunitySoundPackService()
        except Exception:
            self.community_service = None
        self.installer = SoundPackInstaller(self.soundpacks_dir)

        # Pack submission service
        try:
            from ..services.pack_submission_service import (
                PackSubmissionService,  # local import safety
            )

            self.submission_service = PackSubmissionService()
        except Exception:
            self.submission_service = None

        self._load_sound_packs()
        self._create_dialog()

    def _load_sound_packs(self) -> None:
        from .soundpack_manager.state import load_sound_packs as _load

        _load(self)

    def _create_dialog(self) -> None:
        """Create the sound pack manager dialog."""
        from .soundpack_manager.ui import create_dialog_ui as _ui

        _ui(self)

    def _create_pack_list_panel(self) -> toga.Box:
        from .soundpack_manager.ui import create_pack_list_panel as _panel

        return _panel(self)

    def _create_pack_details_panel(self) -> toga.Box:
        from .soundpack_manager.ui import create_pack_details_panel as _panel

        return _panel(self)

    def _create_button_panel(self) -> toga.Box:
        from .soundpack_manager.ui import create_button_panel as _btns

        return _btns(self)

    def _on_pack_selected(self, widget) -> None:
        """Handle pack selection."""
        if not widget.selection:
            return

        selected_item = widget.selection
        self.selected_pack = selected_item.pack_id
        self._update_pack_details()

        # Enable buttons
        self.select_button.enabled = True
        if hasattr(self, "duplicate_button"):
            self.duplicate_button.enabled = True
        if hasattr(self, "edit_button"):
            self.edit_button.enabled = True
        self.delete_button.enabled = (
            self.selected_pack != "default"
        )  # Don't allow deleting default pack
        # Share button state: enabled when a non-default pack is selected and metadata is valid
        try:
            if hasattr(self, "share_button"):
                enable_share = False
                if self.selected_pack and self.selected_pack != "default":
                    info = self.sound_packs.get(self.selected_pack) or {}
                    try:
                        meta = self._load_pack_meta(info)
                    except Exception:
                        meta = {}
                    name_ok = bool((meta.get("name") or "").strip())
                    author_ok = bool((meta.get("author") or "").strip())
                    enable_share = name_ok and author_ok
                self.share_button.enabled = enable_share
        except Exception:
            pass

    def _update_pack_details(self) -> None:
        from .soundpack_manager.state import update_pack_details as _upd

        _upd(self)

    def _on_mapping_key_change(self, widget) -> None:
        """When the mapping key changes, populate the file input with current mapping if present."""
        from .soundpack_manager.mappings import on_mapping_key_change as _mkc

        _mkc(self, widget)

    def _on_browse_mapping_file(self, widget) -> None:
        """Open a file dialog to choose an audio file for the selected key."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            return
        from .soundpack_manager.mappings import on_browse_mapping_file as _b

        _b(self, widget)

    def _get_selected_mapping_item(self):
        try:
            return self.mapping_key_selection.value if self.mapping_key_selection else None
        except Exception:
            return None

    def _get_technical_key_from_selection(self) -> str | None:
        from .soundpack_manager.mappings import get_technical_key_from_selection as _tk

        return _tk(self)

    def _get_display_name_from_selection(self) -> str | None:
        from .soundpack_manager.mappings import get_display_name_from_selection as _dn

        return _dn(self)

    def _on_preview_mapping(self, widget) -> None:
        from .soundpack_manager.mappings import preview_mapping as _prev

        _prev(self, widget)

    def _on_sound_selected(self, widget) -> None:
        """Handle sound selection (no separate preview button)."""
        if widget.value is None:
            return
        # Preview is provided via the alert category mapping controls.

    def _on_preview_sound(self, widget) -> None:
        from .soundpack_manager.mappings import preview_selected_sound as _ps

        _ps(self, widget)

    def _on_import_pack(self, widget) -> None:
        """Import a new sound pack."""
        self.app.main_window.open_file_dialog(
            title="Select Sound Pack ZIP File",
            file_types=["zip"],
            on_result=lambda w, path=None: self._import_pack_file(w, path),
        )

    def _on_simple_choose_file(self, widget) -> None:
        """Simplified: pick a file and map it to the entered key, copying into the pack."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            return
        key = (self.simple_key_input.value or "").strip().lower()
        if not key:
            self.app.main_window.info_dialog("Missing Key", "Please enter a mapping key first.")
            return

        self.app.main_window.open_file_dialog(
            title="Select Audio File",
            file_types=["wav", "mp3", "ogg", "flac"],
            on_result=lambda _, path=None: self._apply_simple_mapping(key, path),
        )

    def _apply_simple_mapping(self, key: str, path: str | None) -> None:
        from .soundpack_manager.mappings import apply_simple_mapping as _asm

        _asm(self, key, path)

    def _load_pack_meta(self, pack_info: dict) -> dict:
        from .soundpack_manager.ops import load_pack_meta as _load

        return _load(pack_info)

    def _save_pack_meta(self, pack_info: dict, meta: dict) -> None:
        from .soundpack_manager.ops import save_pack_meta as _save

        _save(pack_info, meta)

    def _on_simple_remove_mapping(self, widget) -> None:
        from .soundpack_manager.mappings import on_simple_remove_mapping as _srm

        _srm(self, widget)

    def _import_pack_file(self, widget, path: str | None = None) -> None:
        """Import a sound pack from a ZIP file."""
        from .soundpack_manager.ops import import_pack_file as _import

        _import(self, widget, path)

    def _refresh_pack_list(self) -> None:
        from .soundpack_manager.state import refresh_pack_list as _refresh

        _refresh(self)

    def _on_delete_pack(self, widget) -> None:
        """Delete the selected sound pack."""
        from .soundpack_manager.ops import delete_pack as _del

        _del(self, widget)

    def _on_create_pack(self, widget) -> None:
        """Create a new, empty sound pack with default metadata and no sounds."""
        from .soundpack_manager.ops import create_pack as _create

        _create(self)

    def _on_duplicate_pack(self, widget) -> None:
        """Duplicate the currently selected pack into a new pack directory."""
        from .soundpack_manager.ops import duplicate_pack as _dup

        _dup(self)

    def _on_edit_pack(self, widget) -> None:
        """Open a small editor to modify name, author, and description of the pack."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            return

        pack_info = self.sound_packs[self.selected_pack]
        # Load existing metadata
        try:
            meta = self._load_pack_meta(pack_info)
        except Exception:
            meta = {}

        # Create a simple modal window with inputs
        edit_win = toga.Window(title="Edit Sound Pack Metadata", size=(480, 300), resizable=False)
        box = toga.Box(style=Pack(direction=COLUMN, padding=10))

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

        btn_row = toga.Box(style=Pack(direction=ROW))

        def _save_changes(_):
            try:
                updated = {
                    **meta,
                    "name": (name_input.value or self.selected_pack).strip(),
                    "author": (author_input.value or "").strip(),
                    "description": (desc_input.value or "").strip(),
                }
                self._save_pack_meta(pack_info, updated)
                # Update in-memory and UI
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
        """Open the selected pack for management.

        This focuses the selected pack inside the manager. It does NOT change
        the app's active sound pack; that selection is made in Settings > General.
        """
        if self.selected_pack:
            self.current_pack = self.selected_pack
            # Keep dialog open; users can edit, preview, or import assets
            self._update_pack_details()

    def _on_create_pack_wizard(self, widget) -> None:
        """Launch the guided wizard to create a new sound pack."""
        try:

            def _on_complete(new_pack_id: str | None):
                # Refresh list and select the new pack if created
                self._load_sound_packs()
                self._refresh_pack_list()
                if new_pack_id and new_pack_id in self.sound_packs:
                    self.selected_pack = new_pack_id
                    self.current_pack = new_pack_id
                    self._update_pack_details()
                    if hasattr(self, "select_button"):
                        self.select_button.enabled = True
                    if hasattr(self, "delete_button"):
                        self.delete_button.enabled = new_pack_id != "default"

            # Create and show the wizard dialog
            from .soundpack_wizard_dialog import SoundPackWizardDialog

            wizard = SoundPackWizardDialog(
                app=self.app,
                soundpacks_dir=self.soundpacks_dir,
                friendly_categories=FRIENDLY_ALERT_CATEGORIES,
                create_pack_callback=self._create_pack_from_wizard_state,
                on_complete=_on_complete,
            )
            wizard.show()
        except Exception as e:
            logger.error(f"Failed to open wizard: {e}")
            self.app.main_window.error_dialog("Wizard Error", f"Failed to open wizard: {e}")

    def _create_pack_from_wizard_state(self, state) -> str:
        from .soundpack_manager.wizard_ops import create_pack_from_wizard_state as _wiz

        return _wiz(self, state)

    async def _on_browse_community_packs(self, widget) -> None:
        """Open the community packs browser dialog and refresh after install."""
        if not self.community_service:
            await self.app.main_window.info_dialog(
                "Community Packs",
                "Community service is not available in this build.",
            )
            return

        def _on_installed(pack_display_name: str):
            # Refresh local list on the main loop and auto-select the installed pack
            try:
                self._load_sound_packs()
                self._refresh_pack_list()
                # Try to find the newly installed pack by its display name
                for pack_id, info in self.sound_packs.items():
                    if info.get("name") == pack_display_name:
                        self.selected_pack = pack_id
                        self.current_pack = pack_id
                        self._update_pack_details()
                        break
            except Exception:
                pass

        browser = CommunityPacksBrowserDialog(
            app=self.app,
            service=self.community_service,
            installer=self.installer,
            on_installed=_on_installed,
        )
        browser.show()

    def _on_close(self, widget) -> None:
        """Close the dialog."""
        try:
            if getattr(self, "community_service", None):
                # Schedule async cleanup of HTTP client without blocking UI
                asyncio.create_task(self.community_service.aclose())
        except Exception:
            pass
        self.dialog.close()

    async def show(self) -> str:
        """Show the dialog and return the selected pack."""
        self.dialog.show()

        # Set initial focus for accessibility after dialog is shown
        # Longer delay to ensure dialog is fully rendered and accessible before setting focus
        await asyncio.sleep(0.3)

        # Select first pack if available for better accessibility
        if self.pack_list and self.pack_list.data and len(self.pack_list.data) > 0:
            try:
                first_pack = self.pack_list.data[0]
                logger.info(f"Attempting to select first pack: {first_pack}")
                logger.info(f"Pack list data count: {len(self.pack_list.data)}")
                logger.info(
                    f"Select button enabled before selection: {getattr(self.select_button, 'enabled', 'N/A')}"
                )

                self.pack_list.selection = first_pack
                logger.info(f"Set pack list selection to: {self.pack_list.selection}")

                # Manually trigger the selection handler to ensure buttons are enabled
                self._on_pack_selected(self.pack_list)
                logger.info(
                    f"Select button enabled after selection: {getattr(self.select_button, 'enabled', 'N/A')}"
                )
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Could not select first pack: {e}")
                import traceback

                logger.warning(f"Traceback: {traceback.format_exc()}")

        return self.current_pack

    async def _on_share_pack(self, widget) -> None:
        """Validate and submit the selected pack to the community repository via PR."""
        try:
            if not getattr(self, "submission_service", None):
                await self.app.main_window.info_dialog(
                    "Share Pack",
                    "Pack sharing is not available in this build.",
                )
                return

            if not self.selected_pack or self.selected_pack == "default":
                await self.app.main_window.info_dialog(
                    "Share Pack",
                    "Please select a non-default sound pack to share.",
                )
                return

            pack_info = self.sound_packs.get(self.selected_pack)
            if not pack_info:
                await self.app.main_window.error_dialog(
                    "Share Pack",
                    "Could not load selected pack information.",
                )
                return

            # Load metadata
            try:
                meta = self._load_pack_meta(pack_info)
            except Exception:
                meta = {}

            name = (meta.get("name") or self.selected_pack).strip()
            author = (meta.get("author") or "").strip()

            # Basic metadata validation
            missing = []
            if not name:
                missing.append("name")
            if not author:
                missing.append("author")
            if missing:
                await self.app.main_window.error_dialog(
                    "Incomplete Metadata",
                    f"Please add the following to pack.json before sharing: {', '.join(missing)}",
                )
                return

            # Structural validation
            ok, msg = validate_sound_pack(pack_info["path"])
            if not ok:
                await self.app.main_window.error_dialog(
                    "Validation Failed",
                    f"Please fix the following before sharing:\n{msg}",
                )
                return

            # Confirm
            body = (
                f"You are about to share the sound pack '{name}' by {author}.\n\n"
                "This will:\n"
                "- Clone the community repository\n"
                "- Create a new Git branch\n"
                "- Copy your pack into the repository\n"
                "- Open a Pull Request on GitHub using the gh CLI\n\n"
                "Do you want to continue?"
            )
            proceed = await self.app.main_window.question_dialog("Share Pack", body)
            if not proceed:
                return

            # Progress dialog
            progress = UpdateProgressDialog(self.app, title="Sharing Sound Pack")
            progress.show_and_prepare()

            def _progress_cb(pct: float, status: str) -> bool | None:
                # Bridge to our dialog; schedule without awaiting
                try:
                    asyncio.create_task(progress.set_status(status))
                    asyncio.create_task(progress.update_progress(pct))
                except Exception:
                    pass
                # Allow cancellation
                return not progress.is_cancelled

            try:
                pr_url = await self.submission_service.submit_pack(
                    pack_path=pack_info["path"],
                    pack_meta=meta,
                    progress_callback=_progress_cb,
                )
            except asyncio.CancelledError:
                await progress.complete_error("Share cancelled.")
                progress.close()
                return
            except Exception as e:
                await progress.complete_error(str(e))
                progress.close()
                return

            await progress.complete_success("Pack shared successfully!")
            progress.close()

            # Offer to open PR
            open_msg = f"Your pull request was created successfully.\n\nPR: {pr_url}\n\nOpen it in your browser now?"
            if await self.app.main_window.question_dialog("Share Complete", open_msg):
                try:
                    import webbrowser

                    webbrowser.open(pr_url)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Share pack failed: {e}")
            await self.app.main_window.error_dialog("Share Failed", str(e))
