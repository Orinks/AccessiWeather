"""Updates settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)


class UpdatesTab:
    """Updates tab: auto-update settings, update channel, check interval."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self):
        """Build the Updates tab panel and add it to the notebook."""
        panel = wx.Panel(self.dialog.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        controls["auto_update"] = wx.CheckBox(panel, label="Check for updates automatically")
        sizer.Add(controls["auto_update"], 0, wx.ALL, 5)

        row_ch = wx.BoxSizer(wx.HORIZONTAL)
        row_ch.Add(
            wx.StaticText(panel, label="Update Channel:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["update_channel"] = wx.Choice(
            panel,
            choices=[
                "Stable (Production releases only)",
                "Development (Latest features, may be unstable)",
            ],
        )
        row_ch.Add(controls["update_channel"], 0)
        sizer.Add(row_ch, 0, wx.LEFT, 5)

        row_int = wx.BoxSizer(wx.HORIZONTAL)
        row_int.Add(
            wx.StaticText(panel, label="Check Interval (hours):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["update_check_interval"] = wx.SpinCtrl(panel, min=1, max=168, initial=24)
        row_int.Add(controls["update_check_interval"], 0)
        sizer.Add(row_int, 0, wx.LEFT | wx.TOP, 5)

        check_btn = wx.Button(panel, label="Check for Updates Now")
        check_btn.Bind(wx.EVT_BUTTON, self.dialog._on_check_updates)
        sizer.Add(check_btn, 0, wx.ALL, 10)

        controls["update_status"] = wx.StaticText(panel, label="Ready to check for updates")
        sizer.Add(controls["update_status"], 0, wx.LEFT, 10)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "Updates")
        return panel

    def load(self, settings):
        """Populate Updates tab controls from settings."""
        controls = self.dialog._controls
        controls["auto_update"].SetValue(getattr(settings, "auto_update_enabled", True))
        channel = getattr(settings, "update_channel", "stable")
        controls["update_channel"].SetSelection(0 if channel == "stable" else 1)
        controls["update_check_interval"].SetValue(
            getattr(settings, "update_check_interval_hours", 24)
        )

    def save(self) -> dict:
        """Return Updates tab settings as a dict."""
        controls = self.dialog._controls
        return {
            "auto_update_enabled": controls["auto_update"].GetValue(),
            "update_channel": "stable" if controls["update_channel"].GetSelection() == 0 else "dev",
            "update_check_interval_hours": controls["update_check_interval"].GetValue(),
        }

    def setup_accessibility(self):
        """Set accessibility names for Updates tab controls."""
        controls = self.dialog._controls
        names = {
            "auto_update": "Check for updates automatically",
            "update_channel": "Update Channel",
            "update_check_interval": "Check Interval (hours)",
        }
        for key, name in names.items():
            controls[key].SetName(name)
