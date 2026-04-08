"""Advanced settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)


class AdvancedTab:
    """Advanced tab: system options, reset functions, config file management, API key portability."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self, page_label: str = "Advanced"):
        """Build the Advanced tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Advanced settings include startup behavior, backup tools, and maintenance actions that you may not need every day.",
            left=5,
        )

        startup_section = self.dialog.create_section(
            panel,
            sizer,
            "Startup and window behavior",
            "These options change how AccessiWeather launches and where it goes when you close or minimize it.",
        )
        controls["minimize_tray"] = wx.CheckBox(
            panel,
            label="Minimize to the notification area when closing",
        )
        controls["minimize_tray"].Bind(
            wx.EVT_CHECKBOX,
            self.dialog._on_minimize_tray_changed,
        )
        startup_section.Add(controls["minimize_tray"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["minimize_on_startup"] = wx.CheckBox(
            panel,
            label="Start minimized to the notification area",
        )
        startup_section.Add(
            controls["minimize_on_startup"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        controls["startup"] = wx.CheckBox(panel, label="Launch automatically at startup")
        startup_section.Add(controls["startup"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["weather_history"] = wx.CheckBox(
            panel,
            label="Enable weather history comparisons",
        )
        startup_section.Add(
            controls["weather_history"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        backup_section = self.dialog.create_section(
            panel,
            sizer,
            "Backup and transfer",
            "Use these tools when you want to move settings or encrypted API keys between installations.",
        )
        export_btn = wx.Button(panel, label="Export settings...")
        export_btn.Bind(wx.EVT_BUTTON, self.dialog._on_export_settings)
        backup_section.Add(export_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        import_btn = wx.Button(panel, label="Import settings...")
        import_btn.Bind(wx.EVT_BUTTON, self.dialog._on_import_settings)
        backup_section.Add(import_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        export_api_keys_btn = wx.Button(panel, label="Export API keys (encrypted)")
        export_api_keys_btn.Bind(wx.EVT_BUTTON, self.dialog._on_export_encrypted_api_keys)
        backup_section.Add(export_api_keys_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        import_api_keys_btn = wx.Button(panel, label="Import API keys (encrypted)")
        import_api_keys_btn.Bind(wx.EVT_BUTTON, self.dialog._on_import_encrypted_api_keys)
        backup_section.Add(import_api_keys_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        folders_section = self.dialog.create_section(
            panel,
            sizer,
            "Folders and files",
            "Open the locations where AccessiWeather stores configuration or sound pack files.",
        )
        open_config_btn = wx.Button(panel, label="Open current config folder")
        open_config_btn.Bind(wx.EVT_BUTTON, self.dialog._on_open_config_dir)
        folders_section.Add(open_config_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        open_installed_config_btn = wx.Button(
            panel,
            label="Open installed config folder (source)",
        )
        open_installed_config_btn.Bind(
            wx.EVT_BUTTON,
            self.dialog._on_open_installed_config_dir,
        )
        folders_section.Add(
            open_installed_config_btn,
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        if self.dialog._is_runtime_portable_mode():
            migrate_config_btn = wx.Button(
                panel,
                label="Copy installed config to portable",
            )
            migrate_config_btn.Bind(
                wx.EVT_BUTTON,
                self.dialog._on_copy_installed_config_to_portable,
            )
            folders_section.Add(
                migrate_config_btn,
                0,
                wx.LEFT | wx.RIGHT | wx.BOTTOM,
                10,
            )
        open_sounds_btn = wx.Button(panel, label="Open sound packs folder")
        open_sounds_btn.Bind(wx.EVT_BUTTON, self.dialog._on_open_soundpacks_dir)
        folders_section.Add(open_sounds_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        reset_section = self.dialog.create_section(
            panel,
            sizer,
            "Reset and maintenance",
            "Use these actions carefully. Resetting all app data removes settings, saved locations, caches, and alert state.",
        )
        reset_btn = wx.Button(panel, label="Reset settings to defaults")
        reset_btn.Bind(wx.EVT_BUTTON, self.dialog._on_reset_defaults)
        reset_section.Add(reset_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        full_reset_btn = wx.Button(
            panel,
            label="Reset all app data (settings, locations, caches)",
        )
        full_reset_btn.Bind(wx.EVT_BUTTON, self.dialog._on_full_reset)
        reset_section.Add(full_reset_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
        return panel

    def load(self, settings):
        """Populate Advanced tab controls from settings."""
        controls = self.dialog._controls

        minimize_to_tray = getattr(settings, "minimize_to_tray", False)
        controls["minimize_tray"].SetValue(minimize_to_tray)
        controls["minimize_on_startup"].SetValue(getattr(settings, "minimize_on_startup", False))
        self.dialog._update_minimize_on_startup_state(minimize_to_tray)

        controls["startup"].SetValue(getattr(settings, "startup_enabled", False))
        controls["weather_history"].SetValue(getattr(settings, "weather_history_enabled", True))

    def save(self) -> dict:
        """Return Advanced tab settings as a dict."""
        controls = self.dialog._controls
        return {
            "minimize_to_tray": controls["minimize_tray"].GetValue(),
            "minimize_on_startup": controls["minimize_on_startup"].GetValue(),
            "startup_enabled": controls["startup"].GetValue(),
            "weather_history_enabled": controls["weather_history"].GetValue(),
        }

    def setup_accessibility(self):
        """Set accessibility names for Advanced tab controls."""
        controls = self.dialog._controls
        names = {
            "minimize_tray": "Minimize to the notification area when closing",
            "minimize_on_startup": "Start minimized to the notification area",
            "startup": "Launch automatically at startup",
            "weather_history": "Enable weather history comparisons",
        }
        for key, name in names.items():
            controls[key].SetName(name)
