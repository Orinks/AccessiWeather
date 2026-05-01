"""Integration tests for the Copy-to-clipboard button on AlertDialog."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
import wx

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog

pytestmark = pytest.mark.xdist_group("wx")


@pytest.fixture(scope="module")
def wx_app():
    app = wx.GetApp() or wx.App()
    yield app


@pytest.fixture
def hidden_parent(wx_app):
    frame = wx.Frame(None)
    frame.Hide()
    yield frame
    frame.Destroy()


@pytest.fixture
def fake_clipboard(monkeypatch):
    clipboard = SimpleNamespace(text="")

    def set_data(data):
        clipboard.text = data.GetText()
        return True

    def get_data(data):
        data.SetText(clipboard.text)
        return True

    monkeypatch.setattr(
        wx,
        "TheClipboard",
        SimpleNamespace(
            Open=lambda: True,
            Close=lambda: None,
            SetData=set_data,
            GetData=get_data,
        ),
    )
    return clipboard


def _alert():
    return SimpleNamespace(
        title="t",
        description="D",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Frost Advisory",
        headline="H",
        instruction="I",
        areas=[],
        references=[],
        sent=datetime(2026, 4, 18, 14, 10),
        expires=datetime(2026, 4, 18, 22, 15),
    )


def _read_clipboard_text() -> str:
    assert wx.TheClipboard.Open(), "test could not open clipboard"
    try:
        data = wx.TextDataObject()
        ok = wx.TheClipboard.GetData(data)
        return data.GetText() if ok else ""
    finally:
        wx.TheClipboard.Close()


class TestCopyButton:
    def test_copy_button_exists_in_separate_mode(self, hidden_parent):
        settings = AppSettings(alert_display_style="separate")
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            assert hasattr(dlg, "copy_btn")
            assert dlg.copy_btn.GetId() == wx.ID_COPY
            assert dlg.copy_btn.GetLabel() == "Cop&y to clipboard"
        finally:
            dlg.Destroy()

    def test_copy_button_exists_in_combined_mode(self, hidden_parent):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            assert hasattr(dlg, "copy_btn")
            assert dlg.copy_btn.GetId() == wx.ID_COPY
        finally:
            dlg.Destroy()

    def test_copy_writes_combined_text_to_clipboard(self, hidden_parent, fake_clipboard):
        settings = AppSettings(alert_display_style="separate")
        alert = _alert()
        dlg = AlertDialog(hidden_parent, alert, settings)
        try:
            dlg._on_copy(None)
            assert _read_clipboard_text() == AlertDialog._copy_payload(alert, settings)
            assert fake_clipboard.text == AlertDialog._copy_payload(alert, settings)
        finally:
            dlg.Destroy()

    def test_copy_flashes_copied_label(self, hidden_parent, fake_clipboard):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            dlg._on_copy(None)
            assert dlg.copy_btn.GetLabel() == "Copied!"
        finally:
            dlg.Destroy()

    def test_copy_failure_path_flashes_copy_failed(self, hidden_parent, monkeypatch):
        settings = AppSettings()
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            monkeypatch.setattr(wx.TheClipboard, "Open", lambda: False)
            # Should NOT raise.
            dlg._on_copy(None)
            assert dlg.copy_btn.GetLabel() == "Copy failed"
        finally:
            dlg.Destroy()
