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

    def create(self, page_label: str = "General"):
        """Build the General tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Choose how often AccessiWeather refreshes and what appears on the tray icon.",
            left=5,
        )

        refresh_section = self.dialog.create_section(
            panel,
            sizer,
            "Weather refresh",
            "These settings affect general app behavior for everyday use.",
        )
        controls["update_interval"] = self.dialog.add_labeled_control_row(
            panel,
            refresh_section,
            "Refresh weather every (minutes):",
            lambda parent: wx.SpinCtrl(parent, min=1, max=120, initial=10),
        )

        controls["show_nationwide"] = wx.CheckBox(
            panel,
            label="Show the Nationwide location when a supported data source is selected",
        )
        refresh_section.Add(
            controls["show_nationwide"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        self.dialog.add_help_text(
            panel,
            refresh_section,
            "Nationwide is available when your weather source is set to Automatic or NWS.",
        )

        tray_section = self.dialog.create_section(
            panel,
            sizer,
            "Tray icon text",
            "Show a short weather summary on the notification-area icon and choose how it updates.",
        )
        controls["taskbar_icon_text_enabled"] = wx.CheckBox(
            panel,
            label="Show weather text on the tray icon",
        )
        controls["taskbar_icon_text_enabled"].Bind(
            wx.EVT_CHECKBOX,
            self.dialog._on_taskbar_icon_text_enabled_changed,
        )
        tray_section.Add(
            controls["taskbar_icon_text_enabled"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        controls["taskbar_icon_dynamic_enabled"] = wx.CheckBox(
            panel,
            label="Update tray text as conditions change",
        )
        tray_section.Add(
            controls["taskbar_icon_dynamic_enabled"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        controls["taskbar_icon_text_format"] = self.dialog.add_labeled_control_row(
            panel,
            tray_section,
            "Current tray text format:",
            lambda parent: wx.TextCtrl(
                parent,
                size=(320, -1),
                style=wx.TE_READONLY,
            ),
            expand_control=True,
        )
        controls["taskbar_icon_text_format_dialog"] = wx.Button(
            panel,
            label="Edit tray text format...",
        )
        controls["taskbar_icon_text_format_dialog"].Bind(
            wx.EVT_BUTTON,
            self.dialog._on_edit_taskbar_text_format,
        )
        tray_section.Add(
            controls["taskbar_icon_text_format_dialog"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
        return panel

    def load(self, settings):
        """Populate General tab controls from settings."""
        controls = self.dialog._controls

        controls["update_interval"].SetValue(getattr(settings, "update_interval_minutes", 10))

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
            "update_interval": "Update interval in minutes",
            "show_nationwide": "Show the Nationwide location when a supported data source is selected",
            "taskbar_icon_text_enabled": "Show weather text on the tray icon",
            "taskbar_icon_dynamic_enabled": "Update tray text as conditions change",
            "taskbar_icon_text_format": "Tray text format",
        }
        for key, name in names.items():
            controls[key].SetName(name)
