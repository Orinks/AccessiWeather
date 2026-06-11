"""
Save-time validation in the Edit Location and Tray Text Format dialogs.

Covers two user-facing guarantees:
- EditLocationDialog._on_save blocks closing on an empty or duplicate name so
  the backend rejection in update_location_details is never silent.
- TrayTextFormatDialog._on_ok warns about invalid format strings (unknown
  placeholders, unbalanced braces) and lets the user keep editing or save anyway.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import wx

from accessiweather.ui.dialogs.location_dialog import EditLocationDialog
from accessiweather.ui.dialogs.tray_text_format_dialog import TrayTextFormatDialog


def _edit_dialog_double(
    *,
    current_name: str = "Home",
    entered_name: str = "Home",
    existing_names: tuple[str, ...] = ("Home", "Work"),
) -> MagicMock:
    """Build a stand-in EditLocationDialog with just what _on_save touches."""
    dlg = MagicMock()
    dlg.name_input.GetValue.return_value = entered_name
    dlg._location.name = current_name
    dlg.app.config_manager.get_location_names.return_value = list(existing_names)
    return dlg


class TestEditLocationDialogSaveValidation:
    """EditLocationDialog._on_save name validation."""

    def test_empty_name_blocks_save(self):
        dlg = _edit_dialog_double(entered_name="   ")
        with patch.object(wx, "MessageBox") as message_box:
            EditLocationDialog._on_save(dlg, event=None)

        message_box.assert_called_once()
        dlg.EndModal.assert_not_called()
        dlg.name_input.SetFocus.assert_called_once()

    def test_duplicate_name_blocks_save(self):
        dlg = _edit_dialog_double(current_name="Home", entered_name="Work")
        with patch.object(wx, "MessageBox") as message_box:
            EditLocationDialog._on_save(dlg, event=None)

        message_box.assert_called_once()
        dlg.EndModal.assert_not_called()
        dlg.name_input.SetFocus.assert_called_once()

    def test_unchanged_name_saves(self):
        dlg = _edit_dialog_double(current_name="Home", entered_name="Home")
        with patch.object(wx, "MessageBox") as message_box:
            EditLocationDialog._on_save(dlg, event=None)

        message_box.assert_not_called()
        dlg.EndModal.assert_called_once_with(wx.ID_OK)

    def test_new_unique_name_saves(self):
        dlg = _edit_dialog_double(current_name="Home", entered_name="Beach House")
        with patch.object(wx, "MessageBox") as message_box:
            EditLocationDialog._on_save(dlg, event=None)

        message_box.assert_not_called()
        dlg.EndModal.assert_called_once_with(wx.ID_OK)

    def test_entered_name_is_stripped_before_checks(self):
        dlg = _edit_dialog_double(current_name="Home", entered_name="  Work  ")
        with patch.object(wx, "MessageBox") as message_box:
            EditLocationDialog._on_save(dlg, event=None)

        message_box.assert_called_once()
        dlg.EndModal.assert_not_called()


def _tray_dialog_double(format_value: str, validation: tuple[bool, str | None]) -> MagicMock:
    """Build a stand-in TrayTextFormatDialog with just what _on_ok touches."""
    dlg = MagicMock()
    dlg._format_ctrl.GetValue.return_value = format_value
    dlg._updater.validate_format_string.return_value = validation
    return dlg


class TestTrayTextFormatDialogOkValidation:
    """TrayTextFormatDialog._on_ok format validation."""

    def test_valid_format_saves_without_prompt(self):
        dlg = _tray_dialog_double("{temp} {condition}", (True, None))
        event = MagicMock()
        with patch.object(wx, "MessageBox") as message_box:
            TrayTextFormatDialog._on_ok(dlg, event)

        message_box.assert_not_called()
        event.Skip.assert_called_once()

    def test_invalid_format_keeps_editing_when_declined(self):
        dlg = _tray_dialog_double("{tmp}", (False, "Unsupported placeholder(s): tmp"))
        event = MagicMock()
        with patch.object(wx, "MessageBox", return_value=wx.NO) as message_box:
            TrayTextFormatDialog._on_ok(dlg, event)

        message_box.assert_called_once()
        event.Skip.assert_not_called()
        dlg._format_ctrl.SetFocus.assert_called_once()

    def test_invalid_format_saves_when_confirmed(self):
        dlg = _tray_dialog_double("{tmp}", (False, "Unsupported placeholder(s): tmp"))
        event = MagicMock()
        with patch.object(wx, "MessageBox", return_value=wx.YES):
            TrayTextFormatDialog._on_ok(dlg, event)

        event.Skip.assert_called_once()
