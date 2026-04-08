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

    def create(self, page_label: str = "Updates"):
        """Build the Updates tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Choose how AccessiWeather checks for new releases and when you want to check manually.",
            left=5,
        )

        auto_section = self.dialog.create_section(
            panel,
            sizer,
            "Automatic update checks",
            "Stable is safest for everyday use. Development includes the latest work but may be less predictable.",
        )
        controls["auto_update"] = wx.CheckBox(panel, label="Check for updates automatically")
        auto_section.Add(
            controls["auto_update"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["update_channel"] = wx.Choice(
            panel,
            choices=[
                "Stable (production releases only)",
                "Development (latest features, may be unstable)",
            ],
        )
        self.dialog.add_labeled_row(
            panel,
            auto_section,
            "Release channel:",
            controls["update_channel"],
        )
        controls["update_check_interval"] = wx.SpinCtrl(panel, min=1, max=168, initial=24)
        self.dialog.add_labeled_row(
            panel,
            auto_section,
            "Check every (hours):",
            controls["update_check_interval"],
        )

        manual_section = self.dialog.create_section(
            panel,
            sizer,
            "Check now",
            "Use this if you want an immediate update check instead of waiting for the next scheduled one.",
        )
        check_btn = wx.Button(panel, label="Check for updates now")
        check_btn.Bind(wx.EVT_BUTTON, self.dialog._on_check_updates)
        manual_section.Add(check_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["update_status"] = wx.StaticText(
            panel,
            label="Ready to check for updates.",
        )
        manual_section.Add(
            controls["update_status"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
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
            "update_channel": "Release channel",
            "update_check_interval": "Update check interval in hours",
        }
        for key, name in names.items():
            controls[key].SetName(name)
