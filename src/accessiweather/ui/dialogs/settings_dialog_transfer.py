"""Import/export handlers for the settings dialog."""

from __future__ import annotations

import logging
from pathlib import Path

import wx

from .settings_dialog_constants import API_KEYS_TRANSFER_NOTE

logger = logging.getLogger("accessiweather.ui.dialogs.settings_dialog")


class SettingsDialogTransferMixin:
    def _prompt_passphrase(self, title: str, message: str) -> str | None:
        """Prompt for passphrase using masked text entry."""
        with wx.TextEntryDialog(
            self, message, title, style=wx.OK | wx.CANCEL | wx.TE_PASSWORD
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            value = dlg.GetValue().strip()
            return value or None

    def _on_export_encrypted_api_keys(self, event):
        """Export API keys from keyring to encrypted bundle file."""
        passphrase = self._prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt exported API keys.",
        )
        if passphrase is None:
            return

        confirm = self._prompt_passphrase(
            "Confirm passphrase",
            "Re-enter the passphrase to confirm encrypted export.",
        )
        if confirm is None:
            return
        if passphrase != confirm:
            wx.MessageBox("Passphrases do not match.", "Export Cancelled", wx.OK | wx.ICON_WARNING)
            return

        with wx.FileDialog(
            self,
            "Export API keys (encrypted)",
            wildcard="Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
            defaultFile="accessiweather_api_keys.keys",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            export_path = Path(dlg.GetPath())
            if self.config_manager.export_encrypted_api_keys(export_path, passphrase):
                wx.MessageBox(
                    f"Encrypted API key bundle exported successfully to:\n{export_path}",
                    "Export Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "Failed to export encrypted API keys. Ensure at least one API key is saved.",
                    "Export Failed",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_import_encrypted_api_keys(self, event):
        """Import encrypted API key bundle into local secure storage."""
        with wx.FileDialog(
            self,
            "Import API keys (encrypted)",
            wildcard="Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            import_path = Path(dlg.GetPath())

        passphrase = self._prompt_passphrase(
            "Import API keys (encrypted)",
            "Enter the passphrase used when exporting this encrypted bundle.",
        )
        if passphrase is None:
            return

        if self.config_manager.import_encrypted_api_keys(import_path, passphrase):
            self._load_settings()
            wx.MessageBox(
                "Encrypted API keys imported successfully into this machine's secure keyring.",
                "Import Complete",
                wx.OK | wx.ICON_INFORMATION,
            )
        else:
            wx.MessageBox(
                "Failed to import encrypted API keys. Check passphrase and bundle file.",
                "Import Failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_export_settings(self, event):
        """Export settings to file."""
        with wx.FileDialog(
            self,
            "Export Settings",
            wildcard="JSON files (*.json)|*.json",
            defaultFile="accessiweather_settings.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                export_path = Path(dlg.GetPath())
                try:
                    if self.config_manager.export_settings(export_path):
                        wx.MessageBox(
                            f"Settings exported successfully to:\n{export_path}\n\n"
                            f"Note: {API_KEYS_TRANSFER_NOTE}",
                            "Export Complete",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to export settings. Please try again.",
                            "Export Failed",
                            wx.OK | wx.ICON_ERROR,
                        )
                except Exception as e:
                    logger.error(f"Error exporting settings: {e}")
                    wx.MessageBox(
                        f"Error exporting settings: {e}",
                        "Export Error",
                        wx.OK | wx.ICON_ERROR,
                    )

    def _on_import_settings(self, event):
        """Import settings from file."""
        with wx.FileDialog(
            self,
            "Import Settings",
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                import_path = Path(dlg.GetPath())
                result = wx.MessageBox(
                    "Importing settings will overwrite your current preferences.\n\n"
                    "Your saved locations will NOT be affected.\n\n"
                    f"Important: {API_KEYS_TRANSFER_NOTE}\n\n"
                    "Do you want to continue?",
                    "Confirm Import",
                    wx.YES_NO | wx.ICON_QUESTION,
                )
                if result == wx.YES:
                    try:
                        if self.config_manager.import_settings(import_path):
                            self._load_settings()
                            wx.MessageBox(
                                "Settings imported successfully!\n\n"
                                f"Note: {API_KEYS_TRANSFER_NOTE}",
                                "Import Complete",
                                wx.OK | wx.ICON_INFORMATION,
                            )
                        else:
                            wx.MessageBox(
                                "Failed to import settings.\n\n"
                                "The file may be invalid or corrupted.",
                                "Import Failed",
                                wx.OK | wx.ICON_ERROR,
                            )
                    except Exception as e:
                        logger.error(f"Error importing settings: {e}")
                        wx.MessageBox(
                            f"Error importing settings: {e}",
                            "Import Error",
                            wx.OK | wx.ICON_ERROR,
                        )
