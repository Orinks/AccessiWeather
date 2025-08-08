"""Sound pack management dialog for AccessiWeather.

This module provides a dialog for managing sound packs, including importing new packs,
previewing sounds, and selecting different sound packs.
"""

import asyncio
import json
import logging
import shutil
import zipfile
from pathlib import Path

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

# Supported alert keys for mapping
SUPPORTED_SOUND_KEYS = [
    "warning",
    "watch",
    "advisory",
    "statement",
    "extreme",
    "severe",
    "moderate",
    "minor",
    "alert",
    "notify",
]

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

        self._load_sound_packs()
        self._create_dialog()

    def _load_sound_packs(self) -> None:
        """Load all available sound packs."""
        self.sound_packs.clear()

        if not self.soundpacks_dir.exists():
            return

        for pack_dir in self.soundpacks_dir.iterdir():
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
                self.sound_packs[pack_dir.name] = pack_data

            except Exception as e:
                logger.error(f"Failed to load sound pack {pack_dir.name}: {e}")

    def _create_dialog(self) -> None:
        """Create the sound pack manager dialog."""
        self.dialog = toga.Window(
            title="Sound Pack Manager",
            size=(800, 600),
            resizable=True,
        )

        main_box = toga.Box(style=Pack(direction=COLUMN, padding=10, flex=1))

        # Title
        title_label = toga.Label(
            "Sound Pack Manager", style=Pack(font_size=16, font_weight="bold", padding_bottom=10)
        )
        main_box.add(title_label)

        # Content area
        content_box = toga.Box(style=Pack(direction=ROW, flex=1, padding_bottom=10))

        # Left panel - Sound pack list
        left_panel = self._create_pack_list_panel()
        content_box.add(left_panel)

        # Right panel - Pack details and sounds
        right_panel = self._create_pack_details_panel()
        content_box.add(right_panel)

        main_box.add(content_box)

        # Bottom buttons
        button_box = self._create_button_panel()
        main_box.add(button_box)

        self.dialog.content = main_box

        # Populate the pack list with loaded sound packs
        self._refresh_pack_list()

        # Select current pack if available
        if self.current_pack in self.sound_packs:
            self.selected_pack = self.current_pack
            # Find and set the current pack in the detailed list
            for item in self.pack_list.data:
                if item.pack_id == self.current_pack:
                    # Note: DetailedList selection is read-only, so we can't set it programmatically
                    # Just update the pack details instead
                    break
            self._update_pack_details()

    def _create_pack_list_panel(self) -> toga.Box:
        """Create the sound pack list panel."""
        panel = toga.Box(style=Pack(direction=COLUMN, flex=1, padding_right=10))

        # Panel title
        title_label = toga.Label(
            "Available Sound Packs", style=Pack(font_weight="bold", padding_bottom=5)
        )
        panel.add(title_label)

        # Pack list
        self.pack_list = toga.DetailedList(
            on_select=self._on_pack_selected,
            style=Pack(flex=1, padding_bottom=10),
        )
        panel.add(self.pack_list)

        # Import button
        self.import_button = toga.Button(
            "Import Sound Pack", on_press=self._on_import_pack, style=Pack(width=150)
        )
        panel.add(self.import_button)

        return panel

    def _create_pack_details_panel(self) -> toga.Box:
        """Create the pack details panel."""
        panel = toga.Box(style=Pack(direction=COLUMN, flex=2, padding_left=10))

        # Panel title
        title_label = toga.Label(
            "Sound Pack Details", style=Pack(font_weight="bold", padding_bottom=5)
        )
        panel.add(title_label)

        # Pack info box
        self.pack_info_box = toga.Box(
            style=Pack(direction=COLUMN, padding=10, background_color="#f0f0f0")
        )

        self.pack_name_label = toga.Label(
            "No pack selected", style=Pack(font_size=14, font_weight="bold", padding_bottom=5)
        )
        self.pack_info_box.add(self.pack_name_label)

        self.pack_author_label = toga.Label("", style=Pack(padding_bottom=5))
        self.pack_info_box.add(self.pack_author_label)

        self.pack_description_label = toga.Label("", style=Pack(padding_bottom=10))
        self.pack_info_box.add(self.pack_description_label)

        panel.add(self.pack_info_box)

        # Sounds section
        sounds_label = toga.Label(
            "Sounds in this pack:", style=Pack(font_weight="bold", padding=(10, 0, 5, 0))
        )
        panel.add(sounds_label)

        # Sound selection
        self.sound_selection = toga.Selection(
            items=[],
            accessor="display_name",
            on_change=self._on_sound_selected,
            style=Pack(flex=1, padding_bottom=10),
        )
        panel.add(self.sound_selection)

        # Mapping controls header with tooltip docs
        mapping_header = toga.Box(style=Pack(direction=ROW, padding_bottom=5))
        mapping_label = toga.Label(
            "Alert type/severity mapping:",
            style=Pack(font_weight="bold", padding_right=5),
            tooltip=(
                "Supported keys: warning, watch, advisory, statement; "
                "severities: extreme, severe, moderate, minor; "
                "fallbacks: alert, notify"
            ),
        )
        mapping_header.add(mapping_label)
        panel.add(mapping_header)

        # Mapping controls: key dropdown + file picker + preview
        mapping_row = toga.Box(style=Pack(direction=ROW, padding_bottom=10))
        self.mapping_key_selection = toga.Selection(
            items=[k.title() for k in SUPPORTED_SOUND_KEYS],
            on_change=self._on_mapping_key_change,
            style=Pack(width=200, margin_right=10),
        )
        self.mapping_file_input = toga.TextInput(
            readonly=True, placeholder="Select audio file...", style=Pack(flex=1, margin_right=10)
        )
        self.mapping_browse_button = toga.Button(
            "Browse...", on_press=self._on_browse_mapping_file, style=Pack(margin_right=10)
        )
        self.mapping_preview_button = toga.Button(
            "Preview", on_press=self._on_preview_mapping, enabled=False
        )
        mapping_row.add(self.mapping_key_selection)
        mapping_row.add(self.mapping_file_input)
        mapping_row.add(self.mapping_browse_button)
        mapping_row.add(self.mapping_preview_button)
        panel.add(mapping_row)

        # Sound action buttons
        sound_button_box = toga.Box(style=Pack(direction=ROW, padding_bottom=10))

        self.preview_button = toga.Button(
            "Preview Selected Sound",
            on_press=self._on_preview_sound,
            enabled=False,
            style=Pack(margin_right=10),
        )
        sound_button_box.add(self.preview_button)

        panel.add(sound_button_box)

        return panel

    def _create_button_panel(self) -> toga.Box:
        """Create the bottom button panel."""
        button_box = toga.Box(style=Pack(direction=ROW))

        # Add flexible space to push buttons to the right
        button_box.add(toga.Box(style=Pack(flex=1)))

        self.delete_button = toga.Button(
            "Delete Pack",
            on_press=self._on_delete_pack,
            enabled=False,
            style=Pack(margin_right=10, background_color="#ff4444", color="#ffffff"),
        )
        button_box.add(self.delete_button)

        self.select_button = toga.Button(
            "Select Pack",
            on_press=self._on_select_pack,
            enabled=False,
            style=Pack(margin_right=10, background_color="#4CAF50", color="#ffffff"),
        )
        button_box.add(self.select_button)

        self.close_button = toga.Button(
            "Close", on_press=self._on_close, style=Pack(margin_right=0)
        )
        button_box.add(self.close_button)

        return button_box

    def _on_pack_selected(self, widget) -> None:
        """Handle pack selection."""
        if not widget.selection:
            return

        selected_item = widget.selection
        self.selected_pack = selected_item.pack_id
        self._update_pack_details()

        # Enable buttons
        self.select_button.enabled = True
        self.delete_button.enabled = (
            self.selected_pack != "default"
        )  # Don't allow deleting default pack

    def _update_pack_details(self) -> None:
        """Update the pack details display."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            self.pack_name_label.text = "No pack selected"
            self.pack_author_label.text = ""
            self.pack_description_label.text = ""
            self.sound_selection.items = []
            return

        pack_info = self.sound_packs[self.selected_pack]

        # Update pack info
        self.pack_name_label.text = pack_info.get("name", self.selected_pack)
        self.pack_author_label.text = f"Author: {pack_info.get('author', 'Unknown')}"
        self.pack_description_label.text = pack_info.get("description", "No description available")

        # Update sound selection
        sounds = pack_info.get("sounds", {})
        sound_items = []
        for sound_name, sound_file in sounds.items():
            sound_path = pack_info["path"] / sound_file
            status = "✓" if sound_path.exists() else "✗"
            display_name = f"{sound_name.title()} ({sound_file}) - {status} {'Available' if sound_path.exists() else 'Missing'}"
            sound_items.append(
                {
                    "display_name": display_name,
                    "sound_name": sound_name,
                    "sound_file": sound_file,
                    "exists": sound_path.exists(),
                }
            )

        self.sound_selection.items = sound_items

    def _on_mapping_key_change(self, widget) -> None:
        """When the mapping key changes, populate the file input with current mapping if present."""
        try:
            if not self.selected_pack or self.selected_pack not in self.sound_packs:
                return
            pack_info = self.sound_packs[self.selected_pack]
            sounds = pack_info.get("sounds", {})
            key = (widget.value or "").strip().lower()
            current = sounds.get(key, "")
            self.mapping_file_input.value = current
            # Enable preview if file exists
            if current:
                sound_path = pack_info["path"] / current
                self.mapping_preview_button.enabled = (
                    sound_path.exists() and sound_path.stat().st_size > 0
                )
            else:
                self.mapping_preview_button.enabled = False
        except Exception as e:
            logger.warning(f"Failed to update mapping input: {e}")

    def _on_browse_mapping_file(self, widget) -> None:
        """Open a file dialog to choose an audio file for the selected key."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            return
        key_label = (self.mapping_key_selection.value or "").strip()
        if not key_label:
            return
        try:
            # Choose audio file
            def _apply_file_choice(_, path=None):
                if not path:
                    return
                try:
                    pack_info = self.sound_packs[self.selected_pack]
                    rel_name = Path(path).name  # store filename relative to pack
                    # Update pack.json
                    pack_json_path = pack_info["path"] / "pack.json"
                    with open(pack_json_path, encoding="utf-8") as f:
                        meta = json.load(f)
                    sounds = meta.get("sounds", {})
                    if not isinstance(sounds, dict):
                        sounds = {}
                    key = key_label.lower()
                    sounds[key] = rel_name
                    meta["sounds"] = sounds
                    with open(pack_json_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)
                    # Copy file into pack if not already there
                    dst = pack_info["path"] / rel_name
                    if Path(path) != dst:
                        try:
                            shutil.copy2(path, dst)
                        except Exception as copy_err:
                            logger.warning(f"Could not copy audio file: {copy_err}")
                    # Update in-memory data and UI
                    pack_info["sounds"] = sounds
                    self.mapping_file_input.value = rel_name
                    self._update_pack_details()
                    self.app.main_window.info_dialog(
                        "Mapping Updated",
                        f"Mapped '{key_label}' to '{rel_name}' in pack '{pack_info.get('name', self.selected_pack)}'.",
                    )
                except Exception as e:
                    logger.error(f"Failed to update mapping: {e}")
                    self.app.main_window.error_dialog(
                        "Mapping Error", f"Failed to update mapping: {e}"
                    )

            self.app.main_window.open_file_dialog(
                title="Select Audio File",
                file_types=["wav", "mp3", "ogg", "flac"],
                on_result=_apply_file_choice,
            )
        except Exception as e:
            logger.error(f"Failed to open file dialog: {e}")
            self.app.main_window.error_dialog(
                "File Dialog Error", f"Failed to open file dialog: {e}"
            )

    def _on_preview_mapping(self, widget) -> None:
        """Preview the audio currently mapped for the selected key."""
        try:
            if not self.selected_pack or self.selected_pack not in self.sound_packs:
                return
            key_label = (self.mapping_key_selection.value or "").strip()
            if not key_label:
                return
            pack_info = self.sound_packs[self.selected_pack]
            sounds = pack_info.get("sounds", {})
            filename = sounds.get(key_label.lower()) or f"{key_label.lower()}.wav"
            sound_path = pack_info["path"] / filename
            if not sound_path.exists():
                self.app.main_window.info_dialog(
                    "Sound Not Available",
                    f"The sound file '{filename}' is not available in this pack.",
                )
                return
            from ..notifications.sound_player import _play_sound_file

            _play_sound_file(sound_path)
        except Exception as e:
            logger.error(f"Failed to preview mapping: {e}")
            self.app.main_window.error_dialog("Preview Error", f"Failed to preview mapping: {e}")

    def _on_sound_selected(self, widget) -> None:
        """Handle sound selection."""
        if widget.value is None:
            self.preview_button.enabled = False
            return

        # Check if the selected sound file exists
        sound_item = widget.value
        if self.selected_pack and self.selected_pack in self.sound_packs:
            pack_info = self.sound_packs[self.selected_pack]
            sound_path = pack_info["path"] / sound_item.sound_file

            # Enable preview only if the actual sound file exists
            # This will work for classic, default, nature, minimal, and any other packs with real files
            self.preview_button.enabled = sound_path.exists() and sound_path.stat().st_size > 0
        else:
            self.preview_button.enabled = False

    def _on_preview_sound(self, widget) -> None:
        """Preview the selected sound."""
        if not self.sound_selection.value or not self.selected_pack:
            return

        try:
            sound_item = self.sound_selection.value
            sound_name = sound_item.sound_name

            # Check if the sound file exists
            pack_info = self.sound_packs[self.selected_pack]
            sound_path = pack_info["path"] / sound_item.sound_file

            if not sound_path.exists():
                self.app.main_window.info_dialog(
                    "Sound Not Available",
                    f"The sound file '{sound_item.sound_file}' is not available. This may be a placeholder sound pack.",
                )
                return

            from ..notifications.sound_player import play_notification_sound

            play_notification_sound(sound_name, self.selected_pack)

        except Exception as e:
            logger.error(f"Failed to preview sound: {e}")
            self.app.main_window.error_dialog("Preview Error", f"Failed to preview sound: {e}")

    def _on_import_pack(self, widget) -> None:
        """Import a new sound pack."""
        try:
            # Open file dialog to select sound pack zip file
            self.app.main_window.open_file_dialog(
                title="Select Sound Pack ZIP File",
                file_types=["zip"],
                on_result=self._import_pack_file,
            )
        except Exception as e:
            logger.error(f"Failed to open import dialog: {e}")
            self.app.main_window.error_dialog("Import Error", f"Failed to open import dialog: {e}")

    def _import_pack_file(self, widget, path=None) -> None:
        """Import a sound pack from a ZIP file."""
        if not path:
            return

        try:
            with zipfile.ZipFile(path, "r") as zip_file:
                # Check if pack.json exists in the zip
                if "pack.json" not in zip_file.namelist():
                    self.app.main_window.error_dialog(
                        "Invalid Sound Pack",
                        "The selected file is not a valid sound pack. Missing pack.json file.",
                    )
                    return

                # Read pack.json to get pack info
                with zip_file.open("pack.json") as f:
                    pack_info = json.load(f)

                pack_name = pack_info.get("name", "Unknown Pack")
                pack_id = pack_name.lower().replace(" ", "_").replace("-", "_")

                # Check if pack already exists
                pack_dir = self.soundpacks_dir / pack_id
                if pack_dir.exists():
                    # Ask user if they want to overwrite
                    result = self.app.main_window.question_dialog(
                        "Pack Already Exists",
                        f"A sound pack named '{pack_name}' already exists. Do you want to overwrite it?",
                    )
                    if not result:
                        return

                    # Remove existing pack
                    shutil.rmtree(pack_dir)

                # Extract the sound pack
                pack_dir.mkdir(exist_ok=True)
                zip_file.extractall(pack_dir)

                # Reload sound packs
                self._load_sound_packs()
                self._refresh_pack_list()

                self.app.main_window.info_dialog(
                    "Import Successful", f"Sound pack '{pack_name}' has been imported successfully."
                )

        except Exception as e:
            logger.error(f"Failed to import sound pack: {e}")
            self.app.main_window.error_dialog("Import Error", f"Failed to import sound pack: {e}")

    def _refresh_pack_list(self) -> None:
        """Refresh the sound pack list."""
        # Clear existing data
        self.pack_list.data.clear()

        # Add pack data to DetailedList
        for pack_id, pack_info in self.sound_packs.items():
            pack_name = pack_info.get("name", pack_id)
            author = pack_info.get("author", "Unknown")

            # Create a data object for the DetailedList
            pack_data = {
                "pack_id": pack_id,
                "pack_info": pack_info,
                "title": pack_name,
                "subtitle": f"by {author}",
                "icon": None,  # Could add icons later
            }

            self.pack_list.data.append(pack_data)

    def _on_delete_pack(self, widget) -> None:
        """Delete the selected sound pack."""
        if not self.selected_pack or self.selected_pack == "default":
            return

        pack_info = self.sound_packs.get(self.selected_pack, {})
        pack_name = pack_info.get("name", self.selected_pack)

        # Confirm deletion
        result = self.app.main_window.question_dialog(
            "Delete Sound Pack",
            f"Are you sure you want to delete the sound pack '{pack_name}'? This action cannot be undone.",
        )

        if result:
            try:
                pack_path = pack_info.get("path")
                if pack_path and pack_path.exists():
                    shutil.rmtree(pack_path)

                # Reload sound packs
                self._load_sound_packs()
                self._refresh_pack_list()

                # Clear selection
                self.selected_pack = None
                self._update_pack_details()
                self.select_button.enabled = False
                self.delete_button.enabled = False

                self.app.main_window.info_dialog(
                    "Pack Deleted", f"Sound pack '{pack_name}' has been deleted."
                )

            except Exception as e:
                logger.error(f"Failed to delete sound pack: {e}")
                self.app.main_window.error_dialog(
                    "Delete Error", f"Failed to delete sound pack: {e}"
                )

    def _on_select_pack(self, widget) -> None:
        """Select the current sound pack."""
        if self.selected_pack:
            self.current_pack = self.selected_pack
            self.dialog.close()

    def _on_close(self, widget) -> None:
        """Close the dialog."""
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

                # Small delay to ensure the UI updates
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Could not select first pack: {e}")
                import traceback

                logger.warning(f"Traceback: {traceback.format_exc()}")

        # Set focus to close button for predictable tab order
        # This allows users to tab through the interface in a logical order:
        # Close -> Import -> Pack Selection -> Select Pack -> Delete Pack -> Sound Selection -> Preview
        try:
            if self.close_button:
                self.close_button.focus()
                logger.info("Set initial focus to close button for predictable tab order")
            else:
                logger.warning("Close button not available for initial focus")
        except Exception as e:
            logger.warning(f"Could not set focus to close button: {e}")
            # Try import button as fallback
            try:
                if self.import_button:
                    self.import_button.focus()
                    logger.info("Set focus to import button as fallback")
            except Exception as fallback_e:
                logger.warning(f"Fallback focus attempt failed: {fallback_e}")

        return self.current_pack
