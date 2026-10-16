"""Closing Settings with edits must not silently throw them away."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import wx

from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple


class _Tab:
    def __init__(self, values):
        self.values = values

    def save(self):
        return dict(self.values)


def _dialog(provider_now):
    dlg = SettingsDialogSimple.__new__(SettingsDialogSimple)
    tab = _Tab({"ai_provider": "venice"})
    dlg._tab_objects = [tab]
    dlg._loaded_tab_values = dlg._collect_tab_values()
    tab.values["ai_provider"] = provider_now
    dlg.EndModal = MagicMock()
    dlg._on_ok = MagicMock()
    return dlg


def test_cancel_without_edits_closes_without_asking():
    dlg = _dialog("venice")
    with patch.object(wx, "MessageBox") as box:
        dlg._on_cancel(None)
    box.assert_not_called()
    dlg.EndModal.assert_called_once_with(wx.ID_CANCEL)


def test_cancel_after_switching_provider_offers_to_save():
    dlg = _dialog("openrouter")
    with patch.object(wx, "MessageBox", return_value=wx.YES):
        dlg._on_cancel("evt")
    dlg._on_ok.assert_called_once_with("evt")
    dlg.EndModal.assert_not_called()


def test_choosing_no_discards_and_cancel_keeps_dialog_open():
    dlg = _dialog("openrouter")
    with patch.object(wx, "MessageBox", return_value=wx.CANCEL):
        dlg._on_cancel(None)
    dlg.EndModal.assert_not_called()
    with patch.object(wx, "MessageBox", return_value=wx.NO):
        dlg._on_cancel(None)
    dlg.EndModal.assert_called_once_with(wx.ID_CANCEL)
    dlg._on_ok.assert_not_called()
