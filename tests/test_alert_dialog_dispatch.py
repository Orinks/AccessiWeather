"""Tests for AlertDialog mode dispatch and control creation."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
import wx

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog


@pytest.fixture(scope="module")
def wx_app():
    app = wx.App()
    yield app
    app.Destroy()


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


class TestDispatch:
    def test_separate_mode_creates_subject_ctrl(self, wx_app):
        settings = AppSettings(alert_display_style="separate")
        dlg = AlertDialog(None, _alert(), settings)
        try:
            assert hasattr(dlg, "subject_ctrl")
            assert not hasattr(dlg, "combined_ctrl")
        finally:
            dlg.Destroy()

    def test_combined_mode_creates_combined_ctrl(self, wx_app):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(None, _alert(), settings)
        try:
            assert hasattr(dlg, "combined_ctrl")
            assert not hasattr(dlg, "subject_ctrl")
        finally:
            dlg.Destroy()

    def test_none_settings_defaults_to_separate(self, wx_app):
        dlg = AlertDialog(None, _alert(), None)
        try:
            assert hasattr(dlg, "subject_ctrl")
            assert not hasattr(dlg, "combined_ctrl")
        finally:
            dlg.Destroy()

    def test_combined_mode_textctrl_contains_headline(self, wx_app):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(None, _alert(), settings)
        try:
            assert "H" in dlg.combined_ctrl.GetValue()
            assert "Issued:" in dlg.combined_ctrl.GetValue()
        finally:
            dlg.Destroy()
