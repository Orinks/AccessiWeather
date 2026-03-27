"""General settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)


class GeneralTab:
    """General settings tab: update interval, nationwide location, taskbar icon text."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self):
        """Build the General tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        # Update interval
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(panel, label="Update Interval (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["update_interval"] = wx.SpinCtrl(panel, min=1, max=120, initial=10)
        row1.Add(controls["update_interval"], 0)
        sizer.Add(row1, 0, wx.ALL, 5)

        # Show Nationwide location
        controls["show_nationwide"] = wx.CheckBox(
            panel, label="Show Nationwide location (requires Auto or NWS data source)"
        )
        sizer.Add(controls["show_nationwide"], 0, wx.ALL, 5)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(wx.StaticText(panel, label="Taskbar icon text:"), 0, wx.LEFT | wx.TOP, 5)

        controls["taskbar_icon_text_enabled"] = wx.CheckBox(
            panel, label="Show weather text on tray icon"
        )
        controls["taskbar_icon_text_enabled"].Bind(
            wx.EVT_CHECKBOX,
            self.dialog._on_taskbar_icon_text_enabled_changed,
        )
        sizer.Add(controls["taskbar_icon_text_enabled"], 0, wx.ALL, 5)

        controls["taskbar_icon_dynamic_enabled"] = wx.CheckBox(
            panel, label="Update tray text dynamically"
        )
        sizer.Add(controls["taskbar_icon_dynamic_enabled"], 0, wx.LEFT | wx.BOTTOM, 15)

        row_taskbar_format = wx.BoxSizer(wx.HORIZONTAL)
        row_taskbar_format.Add(
            wx.StaticText(panel, label="Current tray text format:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["taskbar_icon_text_format"] = wx.TextCtrl(
            panel,
            size=(280, -1),
            style=wx.TE_READONLY,
        )
        row_taskbar_format.Add(controls["taskbar_icon_text_format"], 1)
        controls["taskbar_icon_text_format_dialog"] = wx.Button(panel, label="Edit Format...")
        controls["taskbar_icon_text_format_dialog"].Bind(
            wx.EVT_BUTTON,
            self.dialog._on_edit_taskbar_text_format,
        )
        row_taskbar_format.Add(controls["taskbar_icon_text_format_dialog"], 0, wx.LEFT, 8)
        sizer.Add(row_taskbar_format, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 15)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "General")
        return panel

    def load(self, settings):
        """Populate General tab controls from settings."""
        controls = self.dialog._controls

        controls["update_interval"].SetValue(getattr(settings, "update_interval_minutes", 10))

        # Show Nationwide — also gated on data source (cross-tab dep handled by dialog)
        data_source = getattr(settings, "data_source", "auto")
        if data_source not in ("auto", "nws"):
            controls["show_nationwide"].SetValue(False)
            controls["show_nationwide"].Enable(False)
        else:
            controls["show_nationwide"].SetValue(
                getattr(settings, "show_nationwide_location", True)
            )
            controls["show_nationwide"].Enable(True)

        taskbar_text_enabled = getattr(settings, "taskbar_icon_text_enabled", False)
        controls["taskbar_icon_text_enabled"].SetValue(taskbar_text_enabled)
        controls["taskbar_icon_dynamic_enabled"].SetValue(
            getattr(settings, "taskbar_icon_dynamic_enabled", True)
        )
        controls["taskbar_icon_text_format"].SetValue(
            getattr(settings, "taskbar_icon_text_format", "{temp} {condition}")
        )
        self.dialog._update_taskbar_text_controls_state(taskbar_text_enabled)

    def save(self) -> dict:
        """Return General tab settings as a dict."""
        controls = self.dialog._controls
        return {
            "update_interval_minutes": controls["update_interval"].GetValue(),
            "show_nationwide_location": controls["show_nationwide"].GetValue(),
            "taskbar_icon_text_enabled": controls["taskbar_icon_text_enabled"].GetValue(),
            "taskbar_icon_dynamic_enabled": controls["taskbar_icon_dynamic_enabled"].GetValue(),
            "taskbar_icon_text_format": controls["taskbar_icon_text_format"].GetValue(),
        }

    def setup_accessibility(self):
        """Set accessibility names for General tab controls."""
        controls = self.dialog._controls
        names = {
            "update_interval": "Update Interval (minutes)",
            "show_nationwide": "Show Nationwide location (requires Auto or NWS data source)",
            "taskbar_icon_text_enabled": "Show weather text on tray icon",
            "taskbar_icon_dynamic_enabled": "Update tray text dynamically",
            "taskbar_icon_text_format": "Tray text format",
        }
        for key, name in names.items():
            controls[key].SetName(name)
