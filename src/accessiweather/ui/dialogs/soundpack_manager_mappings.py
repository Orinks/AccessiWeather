"""Sound mapping and preview handlers for the sound pack manager dialog."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import wx

from .soundpack_manager_models import FRIENDLY_ALERT_CATEGORIES

logger = logging.getLogger(__name__)


class SoundPackManagerMappingMixin:
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
            # Handle both old (name, file) and new (name, file, volume) formats
            if len(data) >= 2:
                sound_file = data[1]
                volume = data[2] if len(data) > 2 else 1.0
            else:
                return
            info = self.sound_packs[self.selected_pack]
            sound_path = info.path / sound_file
            exists = sound_path.exists()
            self.preview_btn.Enable(exists)
            # Enable Set Vol button for sounds list selection too
            self.set_volume_btn.Enable(exists)
            # Update the volume spinner to show this sound's volume
            self.volume_spin.SetValue(int(volume * 100))

    def _on_preview_sound(self, event) -> None:
        """Preview the selected sound (toggle play/stop)."""
        sel = self.sounds_listbox.GetSelection()
        if sel == wx.NOT_FOUND or not self.selected_pack:
            return

        data = self.sounds_listbox.GetClientData(sel)
        if not data or len(data) < 2:
            return

        # Data is (sound_name, sound_file, volume)
        sound_file = data[1]
        # Use the volume from the shared spinner
        volume = self.volume_spin.GetValue() / 100.0
        info = self.sound_packs[self.selected_pack]
        sound_path = info.path / sound_file

        if not sound_path.exists():
            return

        # Check if we're playing the same sound - toggle stop
        if self._preview_player.is_playing() and self._current_preview_path == sound_path:
            self._preview_player.stop()
            self._preview_timer.Stop()
            self.preview_btn.SetLabel("Preview Selected Sound")
            self._current_preview_path = None
        else:
            # Stop any current preview and play new one
            self._preview_player.stop()
            if self._preview_player.play(sound_path, volume):
                self._current_preview_path = sound_path
                self.preview_btn.SetLabel("Stop Preview")
                # Start timer to detect when playback finishes
                self._preview_timer.Start(200)  # Check every 200ms
            else:
                self._current_preview_path = None
                self.preview_btn.SetLabel("Preview Selected Sound")

    def _on_preview_timer(self, event) -> None:
        """Check if preview playback has finished and reset button state."""
        if not self._preview_player.is_playing():
            self._preview_timer.Stop()
            self._current_preview_path = None
            self.preview_btn.SetLabel("Preview Selected Sound")

    def _on_category_changed(self, event) -> None:
        """Handle category selection change."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            self.mapping_file_text.SetValue("")
            self.volume_spin.SetValue(100)
            return

        sel = self.category_choice.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        _, tech_key = FRIENDLY_ALERT_CATEGORIES[sel]
        info = self.sound_packs[self.selected_pack]
        sound_entry = info.sounds.get(tech_key, "")

        # Handle both inline format and simple string format
        if isinstance(sound_entry, dict):
            current_file = sound_entry.get("file", "")
            volume = sound_entry.get("volume", 1.0)
        else:
            current_file = sound_entry
            # Check volumes section
            pack_json = info.path / "pack.json"
            volume = 1.0
            try:
                with open(pack_json, encoding="utf-8") as f:
                    pack_data = json.load(f)
                volumes_section = pack_data.get("volumes", {})
                volume = volumes_section.get(tech_key, 1.0)
            except Exception:
                pass

        self.mapping_file_text.SetValue(current_file)
        self.volume_spin.SetValue(int(volume * 100))

        if current_file:
            sound_path = info.path / current_file
            self.set_volume_btn.Enable(sound_path.exists())
        else:
            self.set_volume_btn.Enable(False)

    def _on_set_volume(self, event) -> None:
        """Set volume for selected sound (from list or category mapping)."""
        if not self.selected_pack:
            return

        info = self.sound_packs[self.selected_pack]
        volume = self.volume_spin.GetValue() / 100.0

        # First check if a sound is selected in the sounds list
        list_sel = self.sounds_listbox.GetSelection()
        cat_sel = self.category_choice.GetSelection()

        if list_sel != wx.NOT_FOUND:
            # Use the selected sound from the list
            data = self.sounds_listbox.GetClientData(list_sel)
            if data and len(data) >= 2:
                sound_key = data[0]
                sound_file = data[1]
            else:
                return
        elif cat_sel != wx.NOT_FOUND:
            # Fall back to category selection
            _, sound_key = FRIENDLY_ALERT_CATEGORIES[cat_sel]
            sound_entry = info.sounds.get(sound_key)
            if not sound_entry:
                wx.MessageBox(
                    "No sound mapped to this category yet.",
                    "No Sound",
                    wx.OK | wx.ICON_INFORMATION,
                )
                return
            sound_file = (
                sound_entry.get("file", "") if isinstance(sound_entry, dict) else sound_entry
            )
        else:
            wx.MessageBox(
                "Please select a sound from the list or a category.",
                "No Selection",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        if not sound_file:
            return

        # Update pack.json
        pack_json = info.path / "pack.json"
        try:
            with open(pack_json, encoding="utf-8") as f:
                pack_data = json.load(f)
            sounds = pack_data.get("sounds", {})

            # Use inline format if volume != 1.0, otherwise keep simple format
            if volume < 1.0:
                sounds[sound_key] = {"file": sound_file, "volume": volume}
            else:
                sounds[sound_key] = sound_file
                # Remove from volumes section if present
                if "volumes" in pack_data and sound_key in pack_data["volumes"]:
                    del pack_data["volumes"][sound_key]

            pack_data["sounds"] = sounds
            with open(pack_json, "w", encoding="utf-8") as f:
                json.dump(pack_data, f, indent=2)

            # Reload and refresh
            self._load_sound_packs()
            self._update_pack_details()

            # Re-select the sound we just modified in the list
            for i in range(self.sounds_listbox.GetCount()):
                item_data = self.sounds_listbox.GetClientData(i)
                if item_data and item_data[0] == sound_key:
                    self.sounds_listbox.SetSelection(i)
                    break

        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            wx.MessageBox(
                f"Failed to set volume: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

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

            # Get volume from spinner (convert percentage to 0.0-1.0)
            volume = self.volume_spin.GetValue() / 100.0

            # Update pack.json
            pack_json = info.path / "pack.json"
            try:
                with open(pack_json, encoding="utf-8") as f:
                    data = json.load(f)
                sounds = data.get("sounds", {})

                # Use inline format if volume != 1.0, otherwise keep simple format
                if volume < 1.0:
                    sounds[key] = {"file": src_path.name, "volume": volume}
                else:
                    sounds[key] = src_path.name
                    # Remove from volumes section if present
                    if "volumes" in data and key in data["volumes"]:
                        del data["volumes"][key]

                data["sounds"] = sounds
                with open(pack_json, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                # Reload and refresh
                self._load_sound_packs()
                self._update_pack_details()

                vol_str = f" at {int(volume * 100)}%" if volume < 1.0 else ""
                wx.MessageBox(
                    f"Mapped '{key}' to '{src_path.name}'{vol_str}.",
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
