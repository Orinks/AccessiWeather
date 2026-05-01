"""UI construction helpers for the sound pack manager dialog."""

from __future__ import annotations

import json

import wx

from .soundpack_manager_models import FRIENDLY_ALERT_CATEGORIES


class SoundPackManagerUiMixin:
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
        hint.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
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

        # Volume control for mapping
        vol_label = wx.StaticText(parent, label="Vol:")
        cat_row.Add(vol_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)

        self.volume_spin = wx.SpinCtrl(parent, min=0, max=100, initial=100, size=(60, -1))
        self.volume_spin.SetToolTip("Volume percentage (0-100%)")
        cat_row.Add(self.volume_spin, 0, wx.RIGHT, 5)

        self.set_volume_btn = wx.Button(parent, label="Set Vol")
        self.set_volume_btn.SetToolTip("Apply volume to current sound")
        self.set_volume_btn.Bind(wx.EVT_BUTTON, self._on_set_volume)
        self.set_volume_btn.Enable(False)
        cat_row.Add(self.set_volume_btn, 0)

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
        # Load volumes section if present
        pack_json = info.path / "pack.json"
        volumes_section = {}
        try:
            with open(pack_json, encoding="utf-8") as f:
                pack_data = json.load(f)
            volumes_section = pack_data.get("volumes", {})
        except Exception:
            pass

        for sound_name, sound_entry in info.sounds.items():
            # Handle both inline format and simple string format
            if isinstance(sound_entry, dict):
                sound_file = sound_entry.get("file", "")
                volume = sound_entry.get("volume", 1.0)
            else:
                sound_file = sound_entry
                volume = volumes_section.get(sound_name, 1.0)

            sound_path = info.path / sound_file
            status = "✓" if sound_path.exists() else "✗"
            # Get friendly name
            friendly = sound_name.replace("_", " ").title()
            for display_name, key in FRIENDLY_ALERT_CATEGORIES:
                if key == sound_name:
                    friendly = display_name
                    break
            # Show volume percentage
            vol_pct = int(volume * 100)
            display = f"{friendly} ({sound_file}) @ {vol_pct}% - {status}"
            self.sounds_listbox.Append(display, (sound_name, sound_file, volume))

        # Enable buttons
        self.duplicate_btn.Enable(True)
        self.edit_btn.Enable(True)
        self.delete_btn.Enable(self.selected_pack != "default")
        self.export_btn.Enable(True)
        self.share_btn.Enable(self.selected_pack != "default")

        # Update category mapping display
        self._on_category_changed(None)
