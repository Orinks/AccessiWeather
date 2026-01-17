"""Settings dialog for application configuration using wxPython."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class GeneralSettingsPanel(forms.Panel):
    """General settings panel."""

    update_interval_label = fields.StaticText(label="Update Interval (minutes):")
    update_interval = fields.IntText(label="Update interval in minutes", default=10)

    temperature_unit_label = fields.StaticText(label="Temperature Unit:")
    temperature_unit = fields.ComboBox(
        label="Temperature unit",
        choices=["Fahrenheit", "Celsius"],
        read_only=True,
    )

    time_format_label = fields.StaticText(label="Time Format:")
    time_format = fields.ComboBox(
        label="Time format",
        choices=["12-hour", "24-hour"],
        read_only=True,
    )

    show_detailed_forecast = fields.CheckBox(label="Show detailed forecast")
    enable_alerts = fields.CheckBox(label="Enable weather alerts")


class DataSourcesPanel(forms.Panel):
    """Data sources settings panel."""

    data_source_label = fields.StaticText(label="Weather Data Source:")
    data_source = fields.ComboBox(
        label="Data source",
        choices=["Automatic", "NWS (US only)", "Open-Meteo", "Visual Crossing"],
        read_only=True,
    )

    visual_crossing_key_label = fields.StaticText(label="Visual Crossing API Key:")
    visual_crossing_key = fields.Text(label="Visual Crossing API key", password=True)


class NotificationsPanel(forms.Panel):
    """Notifications settings panel."""

    alert_notifications = fields.CheckBox(label="Enable alert notifications")
    notify_extreme = fields.CheckBox(label="Notify for extreme alerts")
    notify_severe = fields.CheckBox(label="Notify for severe alerts")
    notify_moderate = fields.CheckBox(label="Notify for moderate alerts")
    notify_minor = fields.CheckBox(label="Notify for minor alerts")


class AudioPanel(forms.Panel):
    """Audio settings panel."""

    sound_enabled = fields.CheckBox(label="Enable sounds")

    sound_pack_label = fields.StaticText(label="Sound Pack:")
    sound_pack = fields.ComboBox(
        label="Sound pack",
        choices=["Default"],
        read_only=True,
    )


class AdvancedPanel(forms.Panel):
    """Advanced settings panel."""

    minimize_to_tray = fields.CheckBox(label="Minimize to system tray")
    startup_enabled = fields.CheckBox(label="Start with Windows")
    debug_mode = fields.CheckBox(label="Enable debug mode")


class SettingsDialog(forms.SizedDialog):
    """Settings dialog with tabbed interface."""

    def __init__(self, parent, app: AccessiWeatherApp, **kwargs):
        """
        Initialize the settings dialog.

        Args:
            parent: Parent window
            app: Application instance
            **kwargs: Additional keyword arguments

        """
        self.app = app
        self.config_manager = app.config_manager
        self._result = False
        kwargs.setdefault("title", "Settings")
        super().__init__(parent=parent, **kwargs)

    def render(self, **kwargs):
        """Render the dialog and populate settings."""
        super().render(**kwargs)
        self._create_notebook()
        self._create_buttons()
        self._load_settings()
        self._setup_accessibility()

    def _create_notebook(self):
        """Create the tabbed notebook."""
        # Access the underlying wx control's panel
        panel = self.widget.control.GetContentsPane()

        self.notebook = wx.Notebook(panel)

        # Create panels for each tab
        self.general_panel = wx.Panel(self.notebook)
        self.data_sources_panel = wx.Panel(self.notebook)
        self.notifications_panel = wx.Panel(self.notebook)
        self.audio_panel = wx.Panel(self.notebook)
        self.advanced_panel = wx.Panel(self.notebook)

        # Build each panel
        self._build_general_panel()
        self._build_data_sources_panel()
        self._build_notifications_panel()
        self._build_audio_panel()
        self._build_advanced_panel()

        # Add tabs to notebook
        self.notebook.AddPage(self.general_panel, "General")
        self.notebook.AddPage(self.data_sources_panel, "Data Sources")
        self.notebook.AddPage(self.notifications_panel, "Notifications")
        self.notebook.AddPage(self.audio_panel, "Audio")
        self.notebook.AddPage(self.advanced_panel, "Advanced")

        # Add notebook to main sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)

    def _build_general_panel(self):
        """Build the general settings panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Update interval
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(self.general_panel, label="Update Interval (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.update_interval_ctrl = wx.SpinCtrl(self.general_panel, min=1, max=60, initial=10)
        row1.Add(self.update_interval_ctrl, 0)
        sizer.Add(row1, 0, wx.ALL, 5)

        # Temperature unit
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(
            wx.StaticText(self.general_panel, label="Temperature Unit:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.temp_unit_ctrl = wx.Choice(self.general_panel, choices=["Fahrenheit", "Celsius"])
        row2.Add(self.temp_unit_ctrl, 0)
        sizer.Add(row2, 0, wx.ALL, 5)

        # Time format
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        row3.Add(
            wx.StaticText(self.general_panel, label="Time Format:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.time_format_ctrl = wx.Choice(self.general_panel, choices=["12-hour", "24-hour"])
        row3.Add(self.time_format_ctrl, 0)
        sizer.Add(row3, 0, wx.ALL, 5)

        # Checkboxes
        self.detailed_forecast_ctrl = wx.CheckBox(
            self.general_panel, label="Show detailed forecast"
        )
        sizer.Add(self.detailed_forecast_ctrl, 0, wx.ALL, 5)

        self.enable_alerts_ctrl = wx.CheckBox(self.general_panel, label="Enable weather alerts")
        sizer.Add(self.enable_alerts_ctrl, 0, wx.ALL, 5)

        self.general_panel.SetSizer(sizer)

    def _build_data_sources_panel(self):
        """Build the data sources panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Data source
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(self.data_sources_panel, label="Weather Data Source:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.data_source_ctrl = wx.Choice(
            self.data_sources_panel,
            choices=["Automatic", "NWS (US only)", "Open-Meteo", "Visual Crossing"],
        )
        row1.Add(self.data_source_ctrl, 0)
        sizer.Add(row1, 0, wx.ALL, 5)

        # Visual Crossing API key
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(
            wx.StaticText(self.data_sources_panel, label="Visual Crossing API Key:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.vc_key_ctrl = wx.TextCtrl(
            self.data_sources_panel, style=wx.TE_PASSWORD, size=(250, -1)
        )
        row2.Add(self.vc_key_ctrl, 1)
        sizer.Add(row2, 0, wx.ALL | wx.EXPAND, 5)

        self.data_sources_panel.SetSizer(sizer)

    def _build_notifications_panel(self):
        """Build the notifications panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.alert_notif_ctrl = wx.CheckBox(
            self.notifications_panel, label="Enable alert notifications"
        )
        sizer.Add(self.alert_notif_ctrl, 0, wx.ALL, 5)

        self.notify_extreme_ctrl = wx.CheckBox(
            self.notifications_panel, label="Notify for extreme alerts"
        )
        sizer.Add(self.notify_extreme_ctrl, 0, wx.ALL, 5)

        self.notify_severe_ctrl = wx.CheckBox(
            self.notifications_panel, label="Notify for severe alerts"
        )
        sizer.Add(self.notify_severe_ctrl, 0, wx.ALL, 5)

        self.notify_moderate_ctrl = wx.CheckBox(
            self.notifications_panel, label="Notify for moderate alerts"
        )
        sizer.Add(self.notify_moderate_ctrl, 0, wx.ALL, 5)

        self.notify_minor_ctrl = wx.CheckBox(
            self.notifications_panel, label="Notify for minor alerts"
        )
        sizer.Add(self.notify_minor_ctrl, 0, wx.ALL, 5)

        self.notifications_panel.SetSizer(sizer)

    def _build_audio_panel(self):
        """Build the audio panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.sound_enabled_ctrl = wx.CheckBox(self.audio_panel, label="Enable sounds")
        sizer.Add(self.sound_enabled_ctrl, 0, wx.ALL, 5)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(self.audio_panel, label="Sound Pack:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.sound_pack_ctrl = wx.Choice(self.audio_panel, choices=["Default"])
        row1.Add(self.sound_pack_ctrl, 0)
        sizer.Add(row1, 0, wx.ALL, 5)

        self.audio_panel.SetSizer(sizer)

    def _build_advanced_panel(self):
        """Build the advanced panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.minimize_tray_ctrl = wx.CheckBox(self.advanced_panel, label="Minimize to system tray")
        sizer.Add(self.minimize_tray_ctrl, 0, wx.ALL, 5)

        self.startup_ctrl = wx.CheckBox(self.advanced_panel, label="Start with Windows")
        sizer.Add(self.startup_ctrl, 0, wx.ALL, 5)

        self.debug_ctrl = wx.CheckBox(self.advanced_panel, label="Enable debug mode")
        sizer.Add(self.debug_ctrl, 0, wx.ALL, 5)

        self.advanced_panel.SetSizer(sizer)

    def _create_buttons(self):
        """Create OK and Cancel buttons."""
        panel = self.widget.control.GetContentsPane()
        sizer = panel.GetSizer()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        button_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)

        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        button_sizer.Add(ok_btn, 0)

        sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

    def _load_settings(self):
        """Load current settings into UI controls."""
        try:
            settings = self.config_manager.get_settings()

            # General tab
            self.update_interval_ctrl.SetValue(getattr(settings, "update_interval_minutes", 10))

            temp_unit = getattr(settings, "temperature_unit", "fahrenheit")
            self.temp_unit_ctrl.SetSelection(0 if temp_unit == "fahrenheit" else 1)

            time_12h = getattr(settings, "time_format_12hour", True)
            self.time_format_ctrl.SetSelection(0 if time_12h else 1)

            self.detailed_forecast_ctrl.SetValue(getattr(settings, "show_detailed_forecast", True))
            self.enable_alerts_ctrl.SetValue(getattr(settings, "enable_alerts", True))

            # Data sources tab
            data_source = getattr(settings, "data_source", "auto")
            source_map = {"auto": 0, "nws": 1, "openmeteo": 2, "visualcrossing": 3}
            self.data_source_ctrl.SetSelection(source_map.get(data_source, 0))

            vc_key = getattr(settings, "visual_crossing_api_key", "") or ""
            self.vc_key_ctrl.SetValue(str(vc_key))

            # Notifications tab
            self.alert_notif_ctrl.SetValue(getattr(settings, "alert_notifications_enabled", True))
            self.notify_extreme_ctrl.SetValue(getattr(settings, "alert_notify_extreme", True))
            self.notify_severe_ctrl.SetValue(getattr(settings, "alert_notify_severe", True))
            self.notify_moderate_ctrl.SetValue(getattr(settings, "alert_notify_moderate", True))
            self.notify_minor_ctrl.SetValue(getattr(settings, "alert_notify_minor", False))

            # Audio tab
            self.sound_enabled_ctrl.SetValue(getattr(settings, "sound_enabled", True))
            # Sound pack selection would need to load available packs

            # Advanced tab
            self.minimize_tray_ctrl.SetValue(getattr(settings, "minimize_to_tray", False))
            self.startup_ctrl.SetValue(getattr(settings, "startup_enabled", False))
            self.debug_ctrl.SetValue(getattr(settings, "debug_mode", False))

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _save_settings(self) -> bool:
        """Save settings from UI controls."""
        try:
            # Map data source selection
            source_values = ["auto", "nws", "openmeteo", "visualcrossing"]
            data_source = source_values[self.data_source_ctrl.GetSelection()]

            settings_dict = {
                "update_interval_minutes": self.update_interval_ctrl.GetValue(),
                "temperature_unit": "fahrenheit"
                if self.temp_unit_ctrl.GetSelection() == 0
                else "celsius",
                "time_format_12hour": self.time_format_ctrl.GetSelection() == 0,
                "show_detailed_forecast": self.detailed_forecast_ctrl.GetValue(),
                "enable_alerts": self.enable_alerts_ctrl.GetValue(),
                "data_source": data_source,
                "visual_crossing_api_key": self.vc_key_ctrl.GetValue(),
                "alert_notifications_enabled": self.alert_notif_ctrl.GetValue(),
                "alert_notify_extreme": self.notify_extreme_ctrl.GetValue(),
                "alert_notify_severe": self.notify_severe_ctrl.GetValue(),
                "alert_notify_moderate": self.notify_moderate_ctrl.GetValue(),
                "alert_notify_minor": self.notify_minor_ctrl.GetValue(),
                "sound_enabled": self.sound_enabled_ctrl.GetValue(),
                "minimize_to_tray": self.minimize_tray_ctrl.GetValue(),
                "startup_enabled": self.startup_ctrl.GetValue(),
                "debug_mode": self.debug_ctrl.GetValue(),
            }

            success = self.config_manager.update_settings(**settings_dict)
            if success:
                logger.info("Settings saved successfully")
            return success

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        # Set accessible names for controls
        self.update_interval_ctrl.SetName("Update interval in minutes")
        self.temp_unit_ctrl.SetName("Temperature unit selection")
        self.time_format_ctrl.SetName("Time format selection")
        self.data_source_ctrl.SetName("Weather data source selection")
        self.vc_key_ctrl.SetName("Visual Crossing API key")

    def _on_ok(self, event):
        """Handle OK button press."""
        if self._save_settings():
            self._result = True
            self.widget.control.EndModal(wx.ID_OK)
        else:
            wx.MessageBox(
                "Failed to save settings. Please try again.",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_cancel(self, event):
        """Handle Cancel button press."""
        self._result = False
        self.widget.control.EndModal(wx.ID_CANCEL)

    def get_result(self) -> bool:
        """Get the dialog result."""
        return self._result


def show_settings_dialog(parent, app: AccessiWeatherApp) -> bool:
    """
    Show the settings dialog.

    Args:
        parent: Parent window (gui_builder widget)
        app: Application instance

    Returns:
        True if settings were changed, False otherwise

    """
    try:
        # Get the underlying wx control if parent is a gui_builder widget
        parent_ctrl = getattr(parent, "control", parent)

        # Create a standard wx dialog instead of gui_builder for simplicity
        dlg = wx.Dialog(
            parent_ctrl,
            title="Settings",
            size=(500, 450),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        # Use dialog directly as container (no intermediate panel)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(dlg)

        # Create panels
        general_panel = _create_general_panel(notebook, app)
        data_sources_panel = _create_data_sources_panel(notebook, app)
        notifications_panel = _create_notifications_panel(notebook, app)
        audio_panel = _create_audio_panel(notebook, app)
        advanced_panel = _create_advanced_panel(notebook, app)

        notebook.AddPage(general_panel, "General")
        notebook.AddPage(data_sources_panel, "Data Sources")
        notebook.AddPage(notifications_panel, "Notifications")
        notebook.AddPage(audio_panel, "Audio")
        notebook.AddPage(advanced_panel, "Advanced")

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Create buttons with dialog as parent
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()
        cancel_btn = wx.Button(dlg, wx.ID_CANCEL, "Cancel")
        ok_btn = wx.Button(dlg, wx.ID_OK, "OK")
        button_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)
        button_sizer.Add(ok_btn, 0)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        dlg.SetSizer(main_sizer)

        # Store references for saving
        dlg._controls = {
            "general": general_panel._controls,
            "data_sources": data_sources_panel._controls,
            "notifications": notifications_panel._controls,
            "audio": audio_panel._controls,
            "advanced": advanced_panel._controls,
        }
        dlg._app = app

        # Bind OK button
        dlg.Bind(wx.EVT_BUTTON, lambda e: _on_settings_ok(dlg, e), id=wx.ID_OK)

        result = dlg.ShowModal() == wx.ID_OK
        dlg.Destroy()
        return result

    except Exception as e:
        logger.error(f"Failed to show settings dialog: {e}")
        wx.MessageBox(
            f"Failed to open settings: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False


def _create_general_panel(parent, app):
    """Create the general settings panel."""
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.VERTICAL)
    controls = {}

    settings = app.config_manager.get_settings()

    # Update interval
    row1 = wx.BoxSizer(wx.HORIZONTAL)
    row1.Add(
        wx.StaticText(panel, label="Update Interval (minutes):"),
        0,
        wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
        10,
    )
    controls["update_interval"] = wx.SpinCtrl(
        panel, min=1, max=60, initial=getattr(settings, "update_interval_minutes", 10)
    )
    row1.Add(controls["update_interval"], 0)
    sizer.Add(row1, 0, wx.ALL, 5)

    # Temperature unit
    row2 = wx.BoxSizer(wx.HORIZONTAL)
    row2.Add(
        wx.StaticText(panel, label="Temperature Unit:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10
    )
    controls["temp_unit"] = wx.Choice(panel, choices=["Fahrenheit", "Celsius"])
    temp_unit = getattr(settings, "temperature_unit", "fahrenheit")
    controls["temp_unit"].SetSelection(0 if temp_unit == "fahrenheit" else 1)
    row2.Add(controls["temp_unit"], 0)
    sizer.Add(row2, 0, wx.ALL, 5)

    # Time format
    row3 = wx.BoxSizer(wx.HORIZONTAL)
    row3.Add(wx.StaticText(panel, label="Time Format:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
    controls["time_format"] = wx.Choice(panel, choices=["12-hour", "24-hour"])
    time_12h = getattr(settings, "time_format_12hour", True)
    controls["time_format"].SetSelection(0 if time_12h else 1)
    row3.Add(controls["time_format"], 0)
    sizer.Add(row3, 0, wx.ALL, 5)

    # Checkboxes
    controls["detailed_forecast"] = wx.CheckBox(panel, label="Show detailed forecast")
    controls["detailed_forecast"].SetValue(getattr(settings, "show_detailed_forecast", True))
    sizer.Add(controls["detailed_forecast"], 0, wx.ALL, 5)

    controls["enable_alerts"] = wx.CheckBox(panel, label="Enable weather alerts")
    controls["enable_alerts"].SetValue(getattr(settings, "enable_alerts", True))
    sizer.Add(controls["enable_alerts"], 0, wx.ALL, 5)

    panel.SetSizer(sizer)
    panel._controls = controls
    return panel


def _create_data_sources_panel(parent, app):
    """Create the data sources panel."""
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.VERTICAL)
    controls = {}

    settings = app.config_manager.get_settings()

    # Data source
    row1 = wx.BoxSizer(wx.HORIZONTAL)
    row1.Add(
        wx.StaticText(panel, label="Weather Data Source:"),
        0,
        wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
        10,
    )
    controls["data_source"] = wx.Choice(
        panel, choices=["Automatic", "NWS (US only)", "Open-Meteo", "Visual Crossing"]
    )
    data_source = getattr(settings, "data_source", "auto")
    source_map = {"auto": 0, "nws": 1, "openmeteo": 2, "visualcrossing": 3}
    controls["data_source"].SetSelection(source_map.get(data_source, 0))
    row1.Add(controls["data_source"], 0)
    sizer.Add(row1, 0, wx.ALL, 5)

    # Visual Crossing API key
    row2 = wx.BoxSizer(wx.HORIZONTAL)
    row2.Add(
        wx.StaticText(panel, label="Visual Crossing API Key:"),
        0,
        wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
        10,
    )
    controls["vc_key"] = wx.TextCtrl(panel, style=wx.TE_PASSWORD, size=(250, -1))
    vc_key = getattr(settings, "visual_crossing_api_key", "") or ""
    controls["vc_key"].SetValue(str(vc_key))
    row2.Add(controls["vc_key"], 1)
    sizer.Add(row2, 0, wx.ALL | wx.EXPAND, 5)

    panel.SetSizer(sizer)
    panel._controls = controls
    return panel


def _create_notifications_panel(parent, app):
    """Create the notifications panel."""
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.VERTICAL)
    controls = {}

    settings = app.config_manager.get_settings()

    controls["alert_notif"] = wx.CheckBox(panel, label="Enable alert notifications")
    controls["alert_notif"].SetValue(getattr(settings, "alert_notifications_enabled", True))
    sizer.Add(controls["alert_notif"], 0, wx.ALL, 5)

    controls["notify_extreme"] = wx.CheckBox(panel, label="Notify for extreme alerts")
    controls["notify_extreme"].SetValue(getattr(settings, "alert_notify_extreme", True))
    sizer.Add(controls["notify_extreme"], 0, wx.ALL, 5)

    controls["notify_severe"] = wx.CheckBox(panel, label="Notify for severe alerts")
    controls["notify_severe"].SetValue(getattr(settings, "alert_notify_severe", True))
    sizer.Add(controls["notify_severe"], 0, wx.ALL, 5)

    controls["notify_moderate"] = wx.CheckBox(panel, label="Notify for moderate alerts")
    controls["notify_moderate"].SetValue(getattr(settings, "alert_notify_moderate", True))
    sizer.Add(controls["notify_moderate"], 0, wx.ALL, 5)

    controls["notify_minor"] = wx.CheckBox(panel, label="Notify for minor alerts")
    controls["notify_minor"].SetValue(getattr(settings, "alert_notify_minor", False))
    sizer.Add(controls["notify_minor"], 0, wx.ALL, 5)

    panel.SetSizer(sizer)
    panel._controls = controls
    return panel


def _create_audio_panel(parent, app):
    """Create the audio panel."""
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.VERTICAL)
    controls = {}

    settings = app.config_manager.get_settings()

    controls["sound_enabled"] = wx.CheckBox(panel, label="Enable sounds")
    controls["sound_enabled"].SetValue(getattr(settings, "sound_enabled", True))
    sizer.Add(controls["sound_enabled"], 0, wx.ALL, 5)

    row1 = wx.BoxSizer(wx.HORIZONTAL)
    row1.Add(wx.StaticText(panel, label="Sound Pack:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
    controls["sound_pack"] = wx.Choice(panel, choices=["Default"])
    controls["sound_pack"].SetSelection(0)
    row1.Add(controls["sound_pack"], 0)
    sizer.Add(row1, 0, wx.ALL, 5)

    panel.SetSizer(sizer)
    panel._controls = controls
    return panel


def _create_advanced_panel(parent, app):
    """Create the advanced panel."""
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.VERTICAL)
    controls = {}

    settings = app.config_manager.get_settings()

    controls["minimize_tray"] = wx.CheckBox(panel, label="Minimize to system tray")
    controls["minimize_tray"].SetValue(getattr(settings, "minimize_to_tray", False))
    sizer.Add(controls["minimize_tray"], 0, wx.ALL, 5)

    controls["startup"] = wx.CheckBox(panel, label="Start with Windows")
    controls["startup"].SetValue(getattr(settings, "startup_enabled", False))
    sizer.Add(controls["startup"], 0, wx.ALL, 5)

    controls["debug"] = wx.CheckBox(panel, label="Enable debug mode")
    controls["debug"].SetValue(getattr(settings, "debug_mode", False))
    sizer.Add(controls["debug"], 0, wx.ALL, 5)

    panel.SetSizer(sizer)
    panel._controls = controls
    return panel


def _on_settings_ok(dlg, event):
    """Handle OK button in settings dialog."""
    try:
        controls = dlg._controls
        app = dlg._app

        # Map data source selection
        source_values = ["auto", "nws", "openmeteo", "visualcrossing"]
        data_source = source_values[controls["data_sources"]["data_source"].GetSelection()]

        settings_dict = {
            "update_interval_minutes": controls["general"]["update_interval"].GetValue(),
            "temperature_unit": "fahrenheit"
            if controls["general"]["temp_unit"].GetSelection() == 0
            else "celsius",
            "time_format_12hour": controls["general"]["time_format"].GetSelection() == 0,
            "show_detailed_forecast": controls["general"]["detailed_forecast"].GetValue(),
            "enable_alerts": controls["general"]["enable_alerts"].GetValue(),
            "data_source": data_source,
            "visual_crossing_api_key": controls["data_sources"]["vc_key"].GetValue(),
            "alert_notifications_enabled": controls["notifications"]["alert_notif"].GetValue(),
            "alert_notify_extreme": controls["notifications"]["notify_extreme"].GetValue(),
            "alert_notify_severe": controls["notifications"]["notify_severe"].GetValue(),
            "alert_notify_moderate": controls["notifications"]["notify_moderate"].GetValue(),
            "alert_notify_minor": controls["notifications"]["notify_minor"].GetValue(),
            "sound_enabled": controls["audio"]["sound_enabled"].GetValue(),
            "minimize_to_tray": controls["advanced"]["minimize_tray"].GetValue(),
            "startup_enabled": controls["advanced"]["startup"].GetValue(),
            "debug_mode": controls["advanced"]["debug"].GetValue(),
        }

        success = app.config_manager.update_settings(**settings_dict)
        if success:
            logger.info("Settings saved successfully")
            event.Skip()  # Allow dialog to close
        else:
            wx.MessageBox("Failed to save settings.", "Error", wx.OK | wx.ICON_ERROR)

    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        wx.MessageBox(f"Error saving settings: {e}", "Error", wx.OK | wx.ICON_ERROR)
