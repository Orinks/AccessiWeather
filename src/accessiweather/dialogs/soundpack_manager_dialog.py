"""Sound pack management dialog for AccessiWeather.

This module provides a dialog for managing sound packs, including importing new packs,
previewing sounds, and managing/editing pack contents. The active pack is selected
in Settings > General and is not changed from this manager.
"""

import asyncio
import contextlib
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from ..dialogs.community_packs_browser_dialog import CommunityPacksBrowserDialog
from ..notifications.alert_sound_mapper import CANONICAL_ALERT_KEYS  # noqa: F401
from ..notifications.sound_pack_installer import SoundPackInstaller
from ..notifications.sound_player import (  # noqa: F401
    get_available_sound_packs,
    get_sound_pack_sounds,
    validate_sound_pack,
)

# Community packs imports
from ..services.community_soundpack_service import CommunitySoundPackService


@dataclass
class AlertCategoryItem:
    """Data class for alert category selection items."""

    display_name: str
    technical_key: str

    def __str__(self) -> str:  # Shown by Selection and debug; only show friendly name
        return self.display_name

    def __repr__(self) -> str:  # Prevent noisy reprs in lists/debug UIs
        return f"{self.display_name}"


# Friendly alert categories for mapping (display name, technical key)
# Updated to match canonical keys from alert_sound_mapper
FRIENDLY_ALERT_CATEGORIES = [
    ("Tornado Warnings", "tornado_warning"),
    ("Flood Warnings", "flood_warning"),
    ("Heat Advisories", "heat_advisory"),
    ("Thunderstorm Warnings", "thunderstorm_warning"),
    ("Winter Storm Warnings", "winter_storm_warning"),
    ("Hurricane Warnings", "hurricane_warning"),
    ("Wind Warnings", "wind_warning"),
    ("Fire Weather Warnings", "fire_warning"),
    ("Air Quality Alerts", "air_quality_alert"),
    ("Fog Advisories", "fog_advisory"),
    ("Ice Warnings", "ice_warning"),
    ("Snow Warnings", "snow_warning"),
    ("Dust Warnings", "dust_warning"),
    ("Generic Warning", "warning"),
    ("Generic Watch", "watch"),
    ("Generic Advisory", "advisory"),
    ("Generic Statement", "statement"),
    ("General Alert", "alert"),
    ("General Notification", "notify"),
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
        # Community service and installer
        try:
            self.community_service = CommunitySoundPackService()
        except Exception:
            self.community_service = None
        self.installer = SoundPackInstaller(self.soundpacks_dir)

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

        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))

        # Title
        title_label = toga.Label(
            "Sound Pack Manager", style=Pack(font_size=16, font_weight="bold", margin_bottom=10)
        )
        main_box.add(title_label)

        # Content area
        content_box = toga.Box(style=Pack(direction=ROW, flex=1, margin_bottom=10))

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

        # Select current pack if available (for focus), but do not change app setting here
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
        panel = toga.Box(style=Pack(direction=COLUMN, flex=1, margin_right=10))

        # Panel title
        title_label = toga.Label(
            "Available Sound Packs", style=Pack(font_weight="bold", margin_bottom=5)
        )
        panel.add(title_label)

        # Pack list
        self.pack_list = toga.DetailedList(
            on_select=self._on_pack_selected,
            style=Pack(flex=1, margin_bottom=10),
        )
        panel.add(self.pack_list)

        # Import button
        self.import_button = toga.Button(
            "Import Sound Pack", on_press=self._on_import_pack, style=Pack(width=150)
        )
        panel.add(self.import_button)

        # Quick hint: Active pack is selected in Settings > General
        panel.add(
            toga.Label(
                "Hint: Select your active pack in Settings > General.",
                style=Pack(margin_top=8, font_style="italic"),
            )
        )

        return panel

    def _create_pack_details_panel(self) -> toga.Box:
        """Create the pack details panel."""
        panel = toga.Box(style=Pack(direction=COLUMN, flex=2, margin_left=10))

        # Panel title
        title_label = toga.Label(
            "Sound Pack Details", style=Pack(font_weight="bold", margin_bottom=5)
        )
        panel.add(title_label)

        # Pack info box
        self.pack_info_box = toga.Box(
            style=Pack(direction=COLUMN, margin=10, background_color="#f0f0f0")
        )

        self.pack_name_label = toga.Label(
            "No pack selected", style=Pack(font_size=14, font_weight="bold", margin_bottom=5)
        )
        self.pack_info_box.add(self.pack_name_label)

        self.pack_author_label = toga.Label("", style=Pack(margin_bottom=5))
        self.pack_info_box.add(self.pack_author_label)

        self.pack_description_label = toga.Label("", style=Pack(margin_bottom=10))
        self.pack_info_box.add(self.pack_description_label)

        panel.add(self.pack_info_box)

        # Sounds section
        sounds_label = toga.Label(
            "Sounds in this pack:", style=Pack(font_weight="bold", margin=(10, 0, 5, 0))
        )
        panel.add(sounds_label)

        # Sound selection
        self.sound_selection = toga.Selection(
            items=[],
            accessor="display_name",
            on_change=self._on_sound_selected,
            style=Pack(flex=1, margin_bottom=10),
        )
        panel.add(self.sound_selection)

        # Mapping controls header and help text (no widget tooltips; Toga tooltips are for Commands)
        mapping_header = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
        # WCAG: Keep labels concise; provide verbose guidance in separate help text.
        mapping_label = toga.Label(
            "Alert category:",
            style=Pack(font_weight="bold", margin_right=5),
        )
        mapping_header.add(mapping_label)
        panel.add(mapping_header)
        # Mapping controls: key dropdown + file picker + preview
        mapping_row = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        self.mapping_key_selection = toga.Selection(
            items=[
                AlertCategoryItem(display_name=name, technical_key=key)
                for name, key in FRIENDLY_ALERT_CATEGORIES
            ],
            accessor="display_name",
            on_change=self._on_mapping_key_change,
            style=Pack(width=260, margin_right=10),
        )
        # Accessibility: keep label concise; attach verbose help as description of the control
        with contextlib.suppress(Exception):
            self.mapping_key_selection.aria_label = "Alert category"
            self.mapping_key_selection.aria_description = (
                "Select from common weather alert categories. Each category maps to technical keys used by weather services. "
                "Use the custom mapping field below for specific alert types not listed."
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
        # Simpler controls for non-technical users: Add a custom key mapping directly
        simple_map_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
        simple_label = toga.Label("Add or change a mapping:", style=Pack(margin_right=10))
        self.simple_key_input = toga.TextInput(
            placeholder="e.g., excessive_heat_warning or tornado_warning",
            style=Pack(width=260, margin_right=10),
        )
        self.simple_file_button = toga.Button(
            "Choose Sound...", on_press=self._on_simple_choose_file, style=Pack(margin_right=10)
        )
        self.simple_remove_button = toga.Button(
            "Remove Mapping", on_press=self._on_simple_remove_mapping
        )
        simple_map_box.add(simple_label)
        simple_map_box.add(self.simple_key_input)
        simple_map_box.add(self.simple_file_button)
        simple_map_box.add(self.simple_remove_button)
        panel.add(simple_map_box)

        # Sound action buttons removed; preview is available per alert category mapping
        return panel

    def _create_button_panel(self) -> toga.Box:
        """Create the bottom button panel."""
        button_box = toga.Box(style=Pack(direction=ROW))

        # Add flexible space to push buttons to the right
        button_box.add(toga.Box(style=Pack(flex=1)))

        # Create New Pack
        self.create_button = toga.Button(
            "Create New",
            on_press=self._on_create_pack,
            style=Pack(margin_right=10),
        )
        button_box.add(self.create_button)

        # Create with Wizard (guided)
        self.create_wizard_button = toga.Button(
            "Create with Wizard",
            on_press=self._on_create_pack_wizard,
            style=Pack(margin_right=10),
        )
        button_box.add(self.create_wizard_button)

        # Browse Community Packs
        self.browse_community_button = toga.Button(
            "Browse Community",
            on_press=self._on_browse_community_packs,
            style=Pack(margin_right=10),
            enabled=self.community_service is not None,
        )
        button_box.add(self.browse_community_button)

        # Duplicate Selected Pack
        self.duplicate_button = toga.Button(
            "Duplicate",
            on_press=self._on_duplicate_pack,
            enabled=False,
            style=Pack(margin_right=10),
        )
        button_box.add(self.duplicate_button)

        # Edit Metadata of Selected Pack
        self.edit_button = toga.Button(
            "Edit",
            on_press=self._on_edit_pack,
            enabled=False,
            style=Pack(margin_right=10),
        )
        button_box.add(self.edit_button)

        # Open Selected Pack (focus/manage only; does not change active pack)
        self.select_button = toga.Button(
            "Open",
            on_press=self._on_open_pack,
            enabled=False,
            style=Pack(margin_right=10, background_color="#4CAF50", color="#ffffff"),
        )
        button_box.add(self.select_button)

        # Delete Selected Pack
        self.delete_button = toga.Button(
            "Delete Pack",
            on_press=self._on_delete_pack,
            enabled=False,
            style=Pack(margin_right=10, background_color="#ff4444", color="#ffffff"),
        )
        button_box.add(self.delete_button)

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
        if hasattr(self, "duplicate_button"):
            self.duplicate_button.enabled = True
        if hasattr(self, "edit_button"):
            self.edit_button.enabled = True
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

            # Use friendly name if available for recognized keys
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

        self.sound_selection.items = sound_items

        # Update mapping selection to a friendly category that has a mapping in this pack
        try:
            if self.mapping_key_selection is not None:
                sounds_keys = set(sounds.keys())
                mapping_items = getattr(self.mapping_key_selection, "items", []) or []
                selected_item = None
                for item in mapping_items:
                    # Derive a technical key from the item, handling Toga Row wrappers
                    technical_key = None
                    try:
                        # Direct attribute on dataclass
                        technical_key = getattr(item, "technical_key", None)
                        # Dict-style fallback
                        if not technical_key and isinstance(item, dict):
                            technical_key = item.get("technical_key")
                        if not technical_key:
                            # Toga Row case: display_name may be an AlertCategoryItem instance
                            dn = getattr(item, "display_name", None)
                            # If dn is a dataclass instance
                            if dn is not None:
                                tk2 = getattr(dn, "technical_key", None)
                                if tk2:
                                    technical_key = tk2
                                else:
                                    # If dn is a dataclass or string, try to map by friendly name
                                    name = (
                                        getattr(dn, "display_name", None)
                                        if dn is not None
                                        else None
                                    )
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
                    self.mapping_key_selection.value = selected_item
                    # Populate file input/preview state for initial selection
                    self._on_mapping_key_change(self.mapping_key_selection)
        except Exception as e:
            logger.warning(f"Failed to update mapping selection: {e}")

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
        """Safely extract the technical key from the current mapping selection."""
        try:
            if not self.mapping_key_selection or not self.mapping_key_selection.value:
                return None
            sel = self.mapping_key_selection.value

            # Direct attribute (dataclass instance assigned directly)
            tk = getattr(sel, "technical_key", None)
            if tk:
                return tk

            # Dict-style fallback
            if isinstance(sel, dict):
                tk = sel.get("technical_key")
                if tk:
                    return tk

            # Toga Row wrapper: display_name may actually be the AlertCategoryItem instance
            dn = getattr(sel, "display_name", None)
            if dn is not None:
                tk2 = getattr(dn, "technical_key", None)
                if tk2:
                    return tk2
                # Or try mapping from friendly name
                name = getattr(dn, "display_name", None) if dn is not None else None
                if not name and isinstance(dn, str):
                    name = dn
                if name:
                    for friendly, key in FRIENDLY_ALERT_CATEGORIES:
                        if friendly == name:
                            return key

            # Last resort: if selection is a plain string, normalize underscores
            if isinstance(sel, str):
                return sel.strip().lower().replace(" ", "_")

            return None
        except Exception:
            return None

    def _get_display_name_from_selection(self) -> str | None:
        from .soundpack_manager.mappings import get_display_name_from_selection as _dn

        return _dn(self)

    def _on_preview_mapping(self, widget) -> None:
        """Preview the audio currently mapped for the selected key."""
        try:
            if not self.selected_pack or self.selected_pack not in self.sound_packs:
                return
            technical_key = self._get_technical_key_from_selection()
            if not technical_key:
                return
            pack_info = self.sound_packs[self.selected_pack]
            sounds = pack_info.get("sounds", {})
            filename = sounds.get(technical_key) or f"{technical_key}.wav"
            sound_path = pack_info["path"] / filename
            if not sound_path.exists():
                self.app.main_window.info_dialog(
                    "Sound Not Available",
                    f"The sound file '{filename}' is not available in this pack.",
                )
                return
            from ..notifications.sound_player import play_sound_file

            play_sound_file(sound_path)
        except Exception as e:
            logger.error(f"Failed to preview mapping: {e}")
            self.app.main_window.error_dialog("Preview Error", f"Failed to preview mapping: {e}")

    def _on_sound_selected(self, widget) -> None:
        """Handle sound selection (no separate preview button)."""
        if widget.value is None:
            return
        # Preview is provided via the alert category mapping controls.

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
            self.app.main_window.open_file_dialog(
                title="Select Sound Pack ZIP File",
                file_types=["zip"],
                on_result=lambda w, path=None: self._import_pack_file(w, path),
            )
        except Exception as e:
            logger.error(f"Failed to open import dialog: {e}")
            self.app.main_window.error_dialog("Import Error", f"Failed to open import dialog: {e}")

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
        """Load pack.json metadata for a pack."""
        pack_json_path = pack_info["path"] / "pack.json"
        with open(pack_json_path, encoding="utf-8") as f:
            return json.load(f)

    def _save_pack_meta(self, pack_info: dict, meta: dict) -> None:
        """Save pack.json metadata for a pack."""
        pack_json_path = pack_info["path"] / "pack.json"
        with open(pack_json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def _on_simple_remove_mapping(self, widget) -> None:
        from .soundpack_manager.mappings import on_simple_remove_mapping as _srm

        _srm(self, widget)

    def _import_pack_file(self, widget, path: str | None = None) -> None:
        """Import a sound pack from a ZIP file."""
        from .soundpack_manager.ops import import_pack_file as _import

        _import(self, widget, path)

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
        """Create the pack on disk from the wizard state. Returns the new pack_id.

        This uses similar patterns to _on_create_pack but with user-provided metadata
        and selected sounds copied from a staging area.
        """

        # Sanitize and ensure unique ID
        def _slugify(name: str) -> str:
            slug = (name or "custom").strip().lower().replace(" ", "_").replace("-", "_")
            if not slug:
                slug = "custom"
            return slug

        base_id = _slugify(getattr(state, "pack_name", ""))
        if not base_id:
            base_id = "custom"
        pack_id = base_id
        suffix = 1
        while (self.soundpacks_dir / pack_id).exists():
            suffix += 1
            pack_id = f"{base_id}_{suffix}"

        pack_dir = self.soundpacks_dir / pack_id
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
                # Avoid collisions: if a different source would overwrite an existing file,
                # append a numeric suffix to the destination filename.
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
