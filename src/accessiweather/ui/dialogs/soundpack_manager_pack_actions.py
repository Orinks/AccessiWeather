"""Import/export and local pack actions for the sound pack manager dialog."""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from pathlib import Path

import wx

from accessiweather.notifications.sound_pack_installer import safe_extractall

logger = logging.getLogger(__name__)


class SoundPackManagerPackActionsMixin:
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
                    safe_extractall(zf, pack_dir)

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
