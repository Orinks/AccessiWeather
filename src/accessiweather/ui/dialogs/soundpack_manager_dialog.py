"""wxPython Sound Pack Manager dialog."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import wx

from ...notifications.sound_pack_installer import SoundPackInstaller
from ...services.community_soundpack_service import CommunitySoundPackService

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

# Alert categories for mapping sounds
# These correspond to keys used by alert_sound_mapper.py for fallback resolution
FRIENDLY_ALERT_CATEGORIES: list[tuple[str, str]] = [
    # Core application sounds
    ("General Alert", "alert"),
    ("General Notification", "notify"),
    ("Error Sound", "error"),
    ("Success Sound", "success"),
    ("App Startup", "startup"),
    ("App Exit", "exit"),
    # Notification events
    ("Forecast Discussion Update", "discussion_update"),
    ("Severe Weather Risk Change", "severe_risk"),
    # ----- Severity-based fallbacks (used when specific event sound not found) -----
    ("Extreme Severity (fallback)", "extreme"),
    ("Severe Severity (fallback)", "severe"),
    ("Moderate Severity (fallback)", "moderate"),
    ("Minor Severity (fallback)", "minor"),
    # ----- Tornado -----
    ("Tornado Warning", "tornado_warning"),
    ("Tornado Watch", "tornado_watch"),
    # ----- Severe Thunderstorm -----
    ("Severe Thunderstorm Warning", "thunderstorm_warning"),
    ("Severe Thunderstorm Watch", "thunderstorm_watch"),
    # ----- Flood -----
    ("Flood Warning", "flood_warning"),
    ("Flood Watch", "flood_watch"),
    ("Flood Advisory", "flood_advisory"),
    ("Flash Flood Warning", "flash_flood_warning"),
    ("Flash Flood Watch", "flash_flood_watch"),
    ("Coastal Flood Warning", "coastal_flood_warning"),
    ("Coastal Flood Watch", "coastal_flood_watch"),
    ("Coastal Flood Advisory", "coastal_flood_advisory"),
    ("River Flood Warning", "river_flood_warning"),
    ("River Flood Watch", "river_flood_watch"),
    # ----- Heat -----
    ("Excessive Heat Warning", "excessive_heat_warning"),
    ("Excessive Heat Watch", "excessive_heat_watch"),
    ("Heat Advisory", "heat_advisory"),
    # ----- Winter / Cold -----
    ("Winter Storm Warning", "winter_storm_warning"),
    ("Winter Storm Watch", "winter_storm_watch"),
    ("Winter Weather Advisory", "winter_weather_advisory"),
    ("Blizzard Warning", "blizzard_warning"),
    ("Ice Storm Warning", "ice_storm_warning"),
    ("Ice Warning (generic)", "ice_warning"),
    ("Snow Warning (generic)", "snow_warning"),
    ("Snow Squall Warning", "snow_squall_warning"),
    ("Freeze Warning", "freeze_warning"),
    ("Freeze Watch", "freeze_watch"),
    ("Frost Advisory", "frost_advisory"),
    ("Extreme Cold Warning", "extreme_cold_warning"),
    ("Cold Weather Advisory", "cold_weather_advisory"),
    # ----- Wind -----
    ("High Wind Warning", "high_wind_warning"),
    ("High Wind Watch", "high_wind_watch"),
    ("Wind Advisory", "wind_advisory"),
    ("Wind Warning (generic)", "wind_warning"),
    ("Extreme Wind Warning", "extreme_wind_warning"),
    # ----- Tropical -----
    ("Hurricane Warning", "hurricane_warning"),
    ("Hurricane Watch", "hurricane_watch"),
    ("Tropical Storm Warning", "tropical_storm_warning"),
    ("Tropical Storm Watch", "tropical_storm_watch"),
    ("Storm Surge Warning", "storm_surge_warning"),
    ("Storm Surge Watch", "storm_surge_watch"),
    # ----- Fire -----
    ("Red Flag Warning", "red_flag_warning"),
    ("Fire Weather Watch", "fire_weather_watch"),
    ("Fire Warning (generic)", "fire_warning"),
    # ----- Marine -----
    ("Small Craft Advisory", "small_craft_advisory"),
    ("Gale Warning", "gale_warning"),
    ("Storm Warning (marine)", "storm_warning"),
    ("Hurricane Force Wind Warning", "hurricane_force_wind_warning"),
    ("Special Marine Warning", "special_marine_warning"),
    # ----- Fog / Visibility -----
    ("Dense Fog Advisory", "dense_fog_advisory"),
    ("Fog Advisory (generic)", "fog_advisory"),
    # ----- Air Quality / Dust -----
    ("Air Quality Alert", "air_quality_alert"),
    ("Dust Storm Warning", "dust_storm_warning"),
    ("Dust Advisory", "dust_advisory"),
    ("Dust Warning (generic)", "dust_warning"),
    # ----- Generic fallbacks (catch-all by alert type) -----
    ("Generic Warning", "warning"),
    ("Generic Watch", "watch"),
    ("Generic Advisory", "advisory"),
    ("Generic Statement", "statement"),
]


@dataclass
class SoundPackInfo:
    """Information about a sound pack."""

    pack_id: str
    name: str
    author: str
    description: str
    path: Path
    sounds: dict[str, str]


class SoundPackManagerDialog(wx.Dialog):
    """Dialog for managing sound packs."""

    def __init__(self, parent: wx.Window, app: AccessiWeatherApp) -> None:
        """Initialize the sound pack manager dialog."""
        super().__init__(
            parent,
            title="Sound Pack Manager",
            size=(850, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.app = app
        self.soundpacks_dir = Path(__file__).parent.parent.parent / "soundpacks"
        self.soundpacks_dir.mkdir(exist_ok=True)
        self.sound_packs: dict[str, SoundPackInfo] = {}
        self.selected_pack: str | None = None

        # External services
        self.installer = SoundPackInstaller(self.soundpacks_dir)
        self.community_service = self._create_community_service()

        # Preview player for sound previews (supports stop)
        from ...notifications.sound_player import get_preview_player
        self._preview_player = get_preview_player()
        self._current_preview_path: Path | None = None

        self._load_sound_packs()
        self._create_ui()
        self._refresh_pack_list()
        self.Centre()

        # Bind close event to stop any playing preview
        self.Bind(wx.EVT_CLOSE, self._on_dialog_close)

    def _create_community_service(self) -> CommunitySoundPackService | None:
        """Create the community soundpack service."""
        try:
            return CommunitySoundPackService()
        except Exception as exc:
            logger.warning("Community packs disabled - failed to initialize service: %s", exc)
            return None

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
                    data = json.load(f)
                self.sound_packs[pack_dir.name] = SoundPackInfo(
                    pack_id=pack_dir.name,
                    name=data.get("name", pack_dir.name),
                    author=data.get("author", "Unknown"),
                    description=data.get("description", ""),
                    path=pack_dir,
                    sounds=data.get("sounds", {}),
                )
            except Exception as e:
                logger.error(f"Failed to load sound pack {pack_dir.name}: {e}")

    def _create_ui(self) -> None:
        """Create the dialog UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Sound Pack Manager")
        title_font = title.GetFont()
        title_font.SetPointSize(14)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL, 10)

        # Content area - horizontal split
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left panel - Pack list
        left_panel = self._create_pack_list_panel(panel)
        content_sizer.Add(left_panel, 1, wx.EXPAND | wx.RIGHT, 10)

        # Right panel - Pack details
        right_panel = self._create_details_panel(panel)
        content_sizer.Add(right_panel, 2, wx.EXPAND)

        main_sizer.Add(content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Bottom buttons
        button_sizer = self._create_button_panel(panel)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)

    def _create_pack_list_panel(self, parent: wx.Window) -> wx.BoxSizer:
        """Create the left panel with pack list."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(parent, label="Available Sound Packs:")
        sizer.Add(label, 0, wx.BOTTOM, 5)

        self.pack_listbox = wx.ListBox(parent, style=wx.LB_SINGLE)
        self.pack_listbox.Bind(wx.EVT_LISTBOX, self._on_pack_selected)
        sizer.Add(self.pack_listbox, 1, wx.EXPAND | wx.BOTTOM, 10)

        # Import button
        import_btn = wx.Button(parent, label="Import Sound Pack...")
        import_btn.Bind(wx.EVT_BUTTON, self._on_import_pack)
        sizer.Add(import_btn, 0, wx.EXPAND | wx.BOTTOM, 5)

        hint = wx.StaticText(parent, label="Hint: Select your active pack in Settings > Audio.")
        hint.SetForegroundColour(wx.Colour(100, 100, 100))
        sizer.Add(hint, 0)

        return sizer

    def _create_details_panel(self, parent: wx.Window) -> wx.BoxSizer:
        """Create the right panel with pack details."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Pack info box
        info_box = wx.StaticBox(parent, label="Sound Pack Details")
        info_sizer = wx.StaticBoxSizer(info_box, wx.VERTICAL)

        self.name_label = wx.StaticText(parent, label="No pack selected")
        name_font = self.name_label.GetFont()
        name_font.SetPointSize(12)
        name_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.name_label.SetFont(name_font)
        info_sizer.Add(self.name_label, 0, wx.ALL, 5)

        self.author_label = wx.StaticText(parent, label="")
        info_sizer.Add(self.author_label, 0, wx.LEFT | wx.BOTTOM, 5)

        self.description_label = wx.StaticText(parent, label="")
        self.description_label.Wrap(400)
        info_sizer.Add(self.description_label, 0, wx.LEFT | wx.BOTTOM, 5)

        sizer.Add(info_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        # Sounds list
        sounds_label = wx.StaticText(parent, label="Sounds in this pack:")
        sizer.Add(sounds_label, 0, wx.BOTTOM, 5)

        self.sounds_listbox = wx.ListBox(parent)
        self.sounds_listbox.Bind(wx.EVT_LISTBOX, self._on_sound_selected)
        sizer.Add(self.sounds_listbox, 1, wx.EXPAND | wx.BOTTOM, 5)

        # Preview button
        preview_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.preview_btn = wx.Button(parent, label="Preview Selected Sound")
        self.preview_btn.Bind(wx.EVT_BUTTON, self._on_preview_sound)
        self.preview_btn.Enable(False)
        preview_sizer.Add(self.preview_btn, 0)
        sizer.Add(preview_sizer, 0, wx.BOTTOM, 10)

        # Mapping section
        mapping_box = wx.StaticBox(parent, label="Sound Mappings")
        mapping_sizer = wx.StaticBoxSizer(mapping_box, wx.VERTICAL)

        # Category selection
        cat_row = wx.BoxSizer(wx.HORIZONTAL)
        cat_label = wx.StaticText(parent, label="Alert Category:")
        cat_row.Add(cat_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.category_choice = wx.Choice(
            parent, choices=[name for name, _ in FRIENDLY_ALERT_CATEGORIES]
        )
        self.category_choice.Bind(wx.EVT_CHOICE, self._on_category_changed)
        cat_row.Add(self.category_choice, 1, wx.RIGHT, 10)

        self.mapping_file_text = wx.TextCtrl(parent, style=wx.TE_READONLY)
        cat_row.Add(self.mapping_file_text, 1, wx.RIGHT, 5)

        browse_btn = wx.Button(parent, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_browse_mapping)
        cat_row.Add(browse_btn, 0, wx.RIGHT, 5)

        self.preview_mapping_btn = wx.Button(parent, label="Preview")
        self.preview_mapping_btn.Bind(wx.EVT_BUTTON, self._on_preview_mapping)
        self.preview_mapping_btn.Enable(False)
        cat_row.Add(self.preview_mapping_btn, 0)

        mapping_sizer.Add(cat_row, 0, wx.EXPAND | wx.ALL, 5)

        # Custom key mapping
        custom_row = wx.BoxSizer(wx.HORIZONTAL)
        custom_label = wx.StaticText(parent, label="Custom Key:")
        custom_row.Add(custom_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.custom_key_input = wx.TextCtrl(parent, size=(200, -1), style=wx.TE_PROCESS_ENTER)
        self.custom_key_input.SetHint("e.g., excessive_heat_warning")
        custom_row.Add(self.custom_key_input, 1, wx.RIGHT, 5)

        add_mapping_btn = wx.Button(parent, label="Choose Sound...")
        add_mapping_btn.Bind(wx.EVT_BUTTON, self._on_add_custom_mapping)
        custom_row.Add(add_mapping_btn, 0, wx.RIGHT, 5)

        remove_mapping_btn = wx.Button(parent, label="Remove")
        remove_mapping_btn.Bind(wx.EVT_BUTTON, self._on_remove_mapping)
        custom_row.Add(remove_mapping_btn, 0)

        mapping_sizer.Add(custom_row, 0, wx.EXPAND | wx.ALL, 5)

        sizer.Add(mapping_sizer, 0, wx.EXPAND)

        return sizer

    def _create_button_panel(self, parent: wx.Window) -> wx.BoxSizer:
        """Create the bottom button panel."""
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side buttons
        self.create_btn = wx.Button(parent, label="Create Sound Pack...")
        self.create_btn.Bind(wx.EVT_BUTTON, self._on_create_pack)
        sizer.Add(self.create_btn, 0, wx.RIGHT, 5)

        self.browse_community_btn = wx.Button(parent, label="Browse Community")
        self.browse_community_btn.Bind(wx.EVT_BUTTON, self._on_browse_community)
        self.browse_community_btn.Enable(self.community_service is not None)
        sizer.Add(self.browse_community_btn, 0, wx.RIGHT, 5)

        self.share_btn = wx.Button(parent, label="Share Pack")
        self.share_btn.Bind(wx.EVT_BUTTON, self._on_share_pack)
        self.share_btn.Enable(False)
        sizer.Add(self.share_btn, 0, wx.RIGHT, 5)

        self.duplicate_btn = wx.Button(parent, label="Duplicate")
        self.duplicate_btn.Bind(wx.EVT_BUTTON, self._on_duplicate_pack)
        self.duplicate_btn.Enable(False)
        sizer.Add(self.duplicate_btn, 0, wx.RIGHT, 5)

        self.edit_btn = wx.Button(parent, label="Edit...")
        self.edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_pack)
        self.edit_btn.Enable(False)
        sizer.Add(self.edit_btn, 0, wx.RIGHT, 5)

        self.delete_btn = wx.Button(parent, label="Delete")
        self.delete_btn.Bind(wx.EVT_BUTTON, self._on_delete_pack)
        self.delete_btn.Enable(False)
        sizer.Add(self.delete_btn, 0, wx.RIGHT, 5)

        self.export_btn = wx.Button(parent, label="Export...")
        self.export_btn.Bind(wx.EVT_BUTTON, self._on_export_pack)
        self.export_btn.Enable(False)
        sizer.Add(self.export_btn, 0)

        sizer.AddStretchSpacer()

        # Close button
        close_btn = wx.Button(parent, wx.ID_CLOSE, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        sizer.Add(close_btn, 0)

        return sizer

    def _refresh_pack_list(self) -> None:
        """Refresh the pack list display."""
        self.pack_listbox.Clear()
        for pack_id, info in sorted(self.sound_packs.items(), key=lambda x: x[1].name):
            display = f"{info.name} (by {info.author})"
            self.pack_listbox.Append(display, pack_id)

        # Select first pack if available
        if self.pack_listbox.GetCount() > 0:
            self.pack_listbox.SetSelection(0)
            self._on_pack_selected(None)

    def _update_pack_details(self) -> None:
        """Update the details panel for selected pack."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            self.name_label.SetLabel("No pack selected")
            self.author_label.SetLabel("")
            self.description_label.SetLabel("")
            self.sounds_listbox.Clear()
            self.preview_btn.Enable(False)
            self.duplicate_btn.Enable(False)
            self.edit_btn.Enable(False)
            self.delete_btn.Enable(False)
            self.export_btn.Enable(False)
            self.share_btn.Enable(False)
            return

        info = self.sound_packs[self.selected_pack]
        self.name_label.SetLabel(info.name)
        self.author_label.SetLabel(f"Author: {info.author}")
        self.description_label.SetLabel(info.description or "No description available")
        self.description_label.Wrap(400)

        # Populate sounds list
        self.sounds_listbox.Clear()
        for sound_name, sound_file in info.sounds.items():
            sound_path = info.path / sound_file
            status = "✓" if sound_path.exists() else "✗"
            # Get friendly name
            friendly = sound_name.replace("_", " ").title()
            for display_name, key in FRIENDLY_ALERT_CATEGORIES:
                if key == sound_name:
                    friendly = display_name
                    break
            display = f"{friendly} ({sound_file}) - {status}"
            self.sounds_listbox.Append(display, (sound_name, sound_file))

        # Enable buttons
        self.duplicate_btn.Enable(True)
        self.edit_btn.Enable(True)
        self.delete_btn.Enable(self.selected_pack != "default")
        self.export_btn.Enable(True)
        self.share_btn.Enable(self.selected_pack != "default")

        # Update category mapping display
        self._on_category_changed(None)

    def _on_pack_selected(self, event) -> None:
        """Handle pack selection."""
        sel = self.pack_listbox.GetSelection()
        if sel == wx.NOT_FOUND:
            self.selected_pack = None
        else:
            self.selected_pack = self.pack_listbox.GetClientData(sel)
        self._update_pack_details()

    def _on_sound_selected(self, event) -> None:
        """Handle sound selection."""
        # Stop any current preview when selecting a different sound
        if self._preview_player.is_playing():
            self._preview_player.stop()
            self._current_preview_path = None
        self.preview_btn.SetLabel("Preview Selected Sound")

        sel = self.sounds_listbox.GetSelection()
        if sel == wx.NOT_FOUND or not self.selected_pack:
            self.preview_btn.Enable(False)
            return

        data = self.sounds_listbox.GetClientData(sel)
        if data:
            sound_name, sound_file = data
            info = self.sound_packs[self.selected_pack]
            sound_path = info.path / sound_file
            self.preview_btn.Enable(sound_path.exists())

    def _on_preview_sound(self, event) -> None:
        """Preview the selected sound (toggle play/stop)."""
        sel = self.sounds_listbox.GetSelection()
        if sel == wx.NOT_FOUND or not self.selected_pack:
            return

        data = self.sounds_listbox.GetClientData(sel)
        if not data:
            return

        sound_name, sound_file = data
        info = self.sound_packs[self.selected_pack]
        sound_path = info.path / sound_file

        if not sound_path.exists():
            return

        # Check if we're playing the same sound - toggle stop
        if self._preview_player.is_playing() and self._current_preview_path == sound_path:
            self._preview_player.stop()
            self.preview_btn.SetLabel("Preview Selected Sound")
            self._current_preview_path = None
        else:
            # Stop any current preview and play new one
            self._preview_player.stop()
            if self._preview_player.play(sound_path):
                self._current_preview_path = sound_path
                self.preview_btn.SetLabel("Stop Preview")
            else:
                self._current_preview_path = None
                self.preview_btn.SetLabel("Preview Selected Sound")

    def _on_category_changed(self, event) -> None:
        """Handle category selection change."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            self.mapping_file_text.SetValue("")
            self.preview_mapping_btn.Enable(False)
            return

        sel = self.category_choice.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        _, tech_key = FRIENDLY_ALERT_CATEGORIES[sel]
        info = self.sound_packs[self.selected_pack]
        current_file = info.sounds.get(tech_key, "")
        self.mapping_file_text.SetValue(current_file)

        if current_file:
            sound_path = info.path / current_file
            self.preview_mapping_btn.Enable(sound_path.exists())
        else:
            self.preview_mapping_btn.Enable(False)

    def _on_browse_mapping(self, event) -> None:
        """Browse for a sound file to map."""
        if not self.selected_pack:
            return

        sel = self.category_choice.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox(
                "Please select a category first.",
                "No Category",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        _, tech_key = FRIENDLY_ALERT_CATEGORIES[sel]
        self._apply_mapping(tech_key)

    def _on_add_custom_mapping(self, event) -> None:
        """Add a custom key mapping."""
        if not self.selected_pack:
            return

        key = self.custom_key_input.GetValue().strip().lower()
        if not key:
            wx.MessageBox(
                "Please enter a mapping key first.",
                "Missing Key",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self._apply_mapping(key)

    def _apply_mapping(self, key: str) -> None:
        """Apply a sound file mapping for the given key."""
        wildcard = "Audio files (*.wav;*.mp3;*.ogg;*.flac)|*.wav;*.mp3;*.ogg;*.flac"
        with wx.FileDialog(
            self,
            "Select Audio File",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return

            src_path = Path(dialog.GetPath())
            info = self.sound_packs[self.selected_pack]

            # Copy file to pack directory
            dest_path = info.path / src_path.name
            if src_path.resolve() != dest_path.resolve():
                shutil.copy2(src_path, dest_path)

            # Update pack.json
            pack_json = info.path / "pack.json"
            try:
                with open(pack_json, encoding="utf-8") as f:
                    data = json.load(f)
                sounds = data.get("sounds", {})
                sounds[key] = src_path.name
                data["sounds"] = sounds
                with open(pack_json, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                # Reload and refresh
                self._load_sound_packs()
                self._update_pack_details()

                wx.MessageBox(
                    f"Mapped '{key}' to '{src_path.name}'.",
                    "Mapping Updated",
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as e:
                logger.error(f"Failed to update mapping: {e}")
                wx.MessageBox(
                    f"Failed to update mapping: {e}",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_remove_mapping(self, event) -> None:
        """Remove a custom key mapping."""
        if not self.selected_pack:
            return

        key = self.custom_key_input.GetValue().strip().lower()
        if not key:
            wx.MessageBox(
                "Please enter a mapping key to remove.",
                "Missing Key",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        info = self.sound_packs[self.selected_pack]
        pack_json = info.path / "pack.json"

        try:
            with open(pack_json, encoding="utf-8") as f:
                data = json.load(f)
            sounds = data.get("sounds", {})

            if key not in sounds:
                wx.MessageBox(
                    f"No mapping exists for '{key}'.",
                    "Not Found",
                    wx.OK | wx.ICON_INFORMATION,
                )
                return

            del sounds[key]
            data["sounds"] = sounds
            with open(pack_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self._load_sound_packs()
            self._update_pack_details()

            wx.MessageBox(
                f"Removed mapping for '{key}'.",
                "Mapping Removed",
                wx.OK | wx.ICON_INFORMATION,
            )
        except Exception as e:
            logger.error(f"Failed to remove mapping: {e}")
            wx.MessageBox(
                f"Failed to remove mapping: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_preview_mapping(self, event) -> None:
        """Preview the current category mapping (toggle play/stop)."""
        if not self.selected_pack:
            return

        sel = self.category_choice.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        _, tech_key = FRIENDLY_ALERT_CATEGORIES[sel]
        info = self.sound_packs[self.selected_pack]
        filename = info.sounds.get(tech_key)

        if not filename:
            return

        sound_path = info.path / filename
        if not sound_path.exists():
            return

        # Check if we're playing the same sound - toggle stop
        if self._preview_player.is_playing() and self._current_preview_path == sound_path:
            self._preview_player.stop()
            self.preview_mapping_btn.SetLabel("Preview")
            self._current_preview_path = None
        else:
            # Stop any current preview and play new one
            self._preview_player.stop()
            # Also reset the other preview button
            self.preview_btn.SetLabel("Preview Selected Sound")
            if self._preview_player.play(sound_path):
                self._current_preview_path = sound_path
                self.preview_mapping_btn.SetLabel("Stop")
            else:
                self._current_preview_path = None
                self.preview_mapping_btn.SetLabel("Preview")

    def _on_import_pack(self, event) -> None:
        """Import a sound pack from ZIP."""
        wildcard = "ZIP files (*.zip)|*.zip"
        with wx.FileDialog(
            self,
            "Select Sound Pack ZIP File",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return

            zip_path = Path(dialog.GetPath())

            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    if "pack.json" not in zf.namelist():
                        wx.MessageBox(
                            "Invalid sound pack: missing pack.json file.",
                            "Import Error",
                            wx.OK | wx.ICON_ERROR,
                        )
                        return

                    with zf.open("pack.json") as f:
                        pack_data = json.load(f)

                    pack_name = pack_data.get("name", "Unknown Pack")
                    pack_id = pack_name.lower().replace(" ", "_").replace("-", "_")
                    pack_dir = self.soundpacks_dir / pack_id

                    if pack_dir.exists():
                        result = wx.MessageBox(
                            f"A sound pack named '{pack_name}' already exists. Overwrite?",
                            "Pack Exists",
                            wx.YES_NO | wx.ICON_QUESTION,
                        )
                        if result != wx.YES:
                            return
                        shutil.rmtree(pack_dir)

                    pack_dir.mkdir(exist_ok=True)
                    zf.extractall(pack_dir)

                self._load_sound_packs()
                self._refresh_pack_list()

                # Select the imported pack
                for i in range(self.pack_listbox.GetCount()):
                    if self.pack_listbox.GetClientData(i) == pack_id:
                        self.pack_listbox.SetSelection(i)
                        self._on_pack_selected(None)
                        break

                wx.MessageBox(
                    f"Sound pack '{pack_name}' imported successfully.",
                    "Import Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as e:
                logger.error(f"Failed to import sound pack: {e}")
                wx.MessageBox(
                    f"Failed to import sound pack: {e}",
                    "Import Error",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_create_pack(self, event) -> None:
        """Open the sound pack creation wizard."""
        from .soundpack_wizard_dialog import SoundPackWizardDialog

        wizard = SoundPackWizardDialog(self, self.soundpacks_dir)
        result = wizard.ShowModal()

        if result == wx.ID_OK and wizard.created_pack_id:
            self._load_sound_packs()
            self._refresh_pack_list()

            # Select the new pack
            for i in range(self.pack_listbox.GetCount()):
                if self.pack_listbox.GetClientData(i) == wizard.created_pack_id:
                    self.pack_listbox.SetSelection(i)
                    self._on_pack_selected(None)
                    break

        wizard.Destroy()

    def _on_duplicate_pack(self, event) -> None:
        """Duplicate the selected pack."""
        if not self.selected_pack:
            return

        info = self.sound_packs[self.selected_pack]

        # Generate unique name
        base = f"{self.selected_pack}_copy"
        candidate = base
        suffix = 2
        while (self.soundpacks_dir / candidate).exists():
            candidate = f"{base}{suffix}"
            suffix += 1

        dest_dir = self.soundpacks_dir / candidate
        shutil.copytree(info.path, dest_dir)

        # Update pack.json
        pack_json = dest_dir / "pack.json"
        try:
            with open(pack_json, encoding="utf-8") as f:
                data = json.load(f)
            data["name"] = f"{info.name} (Copy)"
            with open(pack_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to update pack.json: {e}")

        self._load_sound_packs()
        self._refresh_pack_list()

        # Select the new pack
        for i in range(self.pack_listbox.GetCount()):
            if self.pack_listbox.GetClientData(i) == candidate:
                self.pack_listbox.SetSelection(i)
                self._on_pack_selected(None)
                break

        wx.MessageBox(
            f"Created '{info.name} (Copy)'.",
            "Pack Duplicated",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_edit_pack(self, event) -> None:
        """Edit pack metadata."""
        if not self.selected_pack:
            return

        info = self.sound_packs[self.selected_pack]

        # Create edit dialog
        dialog = wx.Dialog(
            self,
            title="Edit Sound Pack Metadata",
            size=(400, 300),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Name
        sizer.Add(wx.StaticText(panel, label="Name:"), 0, wx.ALL, 5)
        name_input = wx.TextCtrl(panel, value=info.name)
        sizer.Add(name_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Author
        sizer.Add(wx.StaticText(panel, label="Author:"), 0, wx.ALL, 5)
        author_input = wx.TextCtrl(panel, value=info.author)
        sizer.Add(author_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Description
        sizer.Add(wx.StaticText(panel, label="Description:"), 0, wx.ALL, 5)
        desc_input = wx.TextCtrl(
            panel, value=info.description, style=wx.TE_MULTILINE, size=(-1, 100)
        )
        sizer.Add(desc_input, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_btn = wx.Button(panel, wx.ID_SAVE, label="Save")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        btn_sizer.Add(save_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(cancel_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(sizer)

        def on_save(evt):
            pack_json = info.path / "pack.json"
            try:
                with open(pack_json, encoding="utf-8") as f:
                    data = json.load(f)
                data["name"] = name_input.GetValue().strip() or info.name
                data["author"] = author_input.GetValue().strip()
                data["description"] = desc_input.GetValue().strip()
                with open(pack_json, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                self._load_sound_packs()
                self._refresh_pack_list()
                self._update_pack_details()
                dialog.EndModal(wx.ID_OK)

                wx.MessageBox(
                    "Sound pack metadata updated.",
                    "Pack Updated",
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as e:
                logger.error(f"Failed to save pack metadata: {e}")
                wx.MessageBox(
                    f"Failed to save pack metadata: {e}",
                    "Save Error",
                    wx.OK | wx.ICON_ERROR,
                )

        save_btn.Bind(wx.EVT_BUTTON, on_save)
        cancel_btn.Bind(wx.EVT_BUTTON, lambda e: dialog.EndModal(wx.ID_CANCEL))

        dialog.ShowModal()
        dialog.Destroy()

    def _on_delete_pack(self, event) -> None:
        """Delete the selected pack."""
        if not self.selected_pack or self.selected_pack == "default":
            return

        info = self.sound_packs[self.selected_pack]

        result = wx.MessageBox(
            f"Are you sure you want to delete '{info.name}'?\n\nThis action cannot be undone.",
            "Delete Sound Pack",
            wx.YES_NO | wx.ICON_WARNING,
        )

        if result != wx.YES:
            return

        try:
            shutil.rmtree(info.path)
            self._load_sound_packs()
            self._refresh_pack_list()
            self.selected_pack = None
            self._update_pack_details()

            wx.MessageBox(
                f"Sound pack '{info.name}' has been deleted.",
                "Pack Deleted",
                wx.OK | wx.ICON_INFORMATION,
            )
        except Exception as e:
            logger.error(f"Failed to delete sound pack: {e}")
            wx.MessageBox(
                f"Failed to delete sound pack: {e}",
                "Delete Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_export_pack(self, event) -> None:
        """Export the selected pack to ZIP."""
        if not self.selected_pack:
            return

        info = self.sound_packs[self.selected_pack]

        wildcard = "ZIP files (*.zip)|*.zip"
        with wx.FileDialog(
            self,
            "Export Sound Pack",
            defaultFile=f"{self.selected_pack}.zip",
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return

            output_path = Path(dialog.GetPath())

            try:
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for file_path in info.path.rglob("*"):
                        if file_path.is_file():
                            arcname = file_path.relative_to(info.path)
                            zf.write(file_path, arcname)

                wx.MessageBox(
                    f"Sound pack exported to {output_path}.",
                    "Export Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as e:
                logger.error(f"Failed to export sound pack: {e}")
                wx.MessageBox(
                    f"Failed to export sound pack: {e}",
                    "Export Error",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_browse_community(self, event) -> None:
        """Open the community packs browser."""
        if not self.community_service:
            # Try to reinitialize
            self.community_service = self._create_community_service()
            if self.community_service:
                self.browse_community_btn.Enable(True)
            else:
                wx.MessageBox(
                    "Community packs are temporarily unavailable. Please try again later.",
                    "Community Sound Packs",
                    wx.OK | wx.ICON_WARNING,
                )
                return

        from .community_packs_dialog import CommunityPacksBrowserDialog

        def on_installed(pack_name: str) -> None:
            """Handle pack installed callback."""
            self._load_sound_packs()
            self._refresh_pack_list()

        dialog = CommunityPacksBrowserDialog(self, self.soundpacks_dir, on_installed)
        dialog.ShowModal()
        dialog.Destroy()

    def _on_share_pack(self, event) -> None:
        """Share the selected pack with the community."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            wx.MessageBox(
                "Please select a sound pack to share.",
                "Share Pack",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        pack_id = self.selected_pack
        pack_info = self.sound_packs[pack_id]

        if pack_id == "default":
            wx.MessageBox(
                "The default sound pack comes preinstalled and cannot be shared with the community.",
                "Share Pack",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Confirm sharing
        result = wx.MessageBox(
            f"Are you sure you want to share '{pack_info.name}' with the community?\n\n"
            "This will submit a pull request for review.",
            "Confirm Share",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            return

        # Validate pack
        from ...notifications.sound_player import validate_sound_pack

        ok, msg = validate_sound_pack(pack_info.path)
        if not ok:
            wx.MessageBox(
                f"Sound pack validation failed: {msg}",
                "Share Pack",
                wx.OK | wx.ICON_ERROR,
            )
            return

        # Show progress dialog
        from .progress_dialog import ProgressDialog

        progress = ProgressDialog(self, "Sharing Sound Pack", "Preparing submission...")
        progress.Show()

        def share_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Build pack metadata
                    pack_meta = {
                        "name": pack_info.name,
                        "author": pack_info.author,
                        "description": pack_info.description,
                        "sounds": pack_info.sounds,
                    }

                    def on_progress(pct: float, status: str) -> bool:
                        return progress.update_progress(pct, status)

                    cancel_event = asyncio.Event()

                    # Check for cancellation
                    def check_cancel():
                        if progress.is_cancelled:
                            cancel_event.set()
                            return True
                        return False

                    if check_cancel():
                        wx.CallAfter(progress.Destroy)
                        return

                    progress.update_progress(10, "Connecting to backend...")

                    from ...services.pack_submission_service import PackSubmissionService

                    # Get config_manager from app if available
                    config_manager = getattr(self.app, "config_manager", None)
                    service = PackSubmissionService(config_manager=config_manager)

                    if check_cancel():
                        wx.CallAfter(progress.Destroy)
                        return

                    pr_url = loop.run_until_complete(
                        service.submit_pack(
                            pack_info.path,
                            pack_meta,
                            on_progress,
                            cancel_event,
                        )
                    )

                    wx.CallAfter(self._on_share_success, progress, pr_url)

                finally:
                    loop.close()
            except asyncio.CancelledError:
                wx.CallAfter(progress.Destroy)
            except Exception as e:
                logger.error(f"Pack submission failed: {e}")
                wx.CallAfter(self._on_share_error, progress, str(e))

        thread = threading.Thread(target=share_thread, daemon=True)
        thread.start()

    def _on_share_success(self, progress, pr_url: str) -> None:
        """Handle share success."""
        progress.Destroy()
        result = wx.MessageBox(
            f"🎉 Your sound pack has been submitted for review!\n\n"
            f"Pull Request: {pr_url}\n\n"
            "Would you like to open the pull request in your browser?",
            "Sound Pack Shared Successfully",
            wx.YES_NO | wx.ICON_INFORMATION,
        )
        if result == wx.YES:
            import webbrowser

            webbrowser.open(pr_url)

    def _on_share_error(self, progress, error: str) -> None:
        """Handle share error."""
        progress.complete_error(error)
        wx.CallLater(3000, progress.Destroy)

    def _on_dialog_close(self, event) -> None:
        """Handle dialog close event (X button or escape)."""
        # Stop any playing preview
        if self._preview_player:
            self._preview_player.stop()
        event.Skip()  # Allow normal close handling

    def _on_close(self, event) -> None:
        """Close the dialog."""
        # Stop any playing preview
        if self._preview_player:
            self._preview_player.stop()

        # Clean up community service
        if self.community_service:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.community_service.aclose())
                finally:
                    loop.close()
            except Exception:
                pass
        self.EndModal(wx.ID_CLOSE)


def show_soundpack_manager_dialog(parent: wx.Window, app: AccessiWeatherApp) -> None:
    """Show the sound pack manager dialog."""
    parent_ctrl = parent
    dialog = SoundPackManagerDialog(parent_ctrl, app)
    dialog.ShowModal()
    dialog.Destroy()
