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

    def create(self):
        """Build the Advanced tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        # System options
        controls["minimize_tray"] = wx.CheckBox(
            panel, label="Minimize to notification area when closing"
        )
        controls["minimize_tray"].Bind(wx.EVT_CHECKBOX, self.dialog._on_minimize_tray_changed)
        sizer.Add(controls["minimize_tray"], 0, wx.ALL, 5)

        controls["minimize_on_startup"] = wx.CheckBox(
            panel, label="Start minimized to notification area"
        )
        sizer.Add(controls["minimize_on_startup"], 0, wx.LEFT | wx.BOTTOM, 5)

        controls["startup"] = wx.CheckBox(panel, label="Launch automatically at startup")
        sizer.Add(controls["startup"], 0, wx.LEFT | wx.BOTTOM, 5)

        controls["weather_history"] = wx.CheckBox(panel, label="Enable weather history comparisons")
        sizer.Add(controls["weather_history"], 0, wx.LEFT | wx.BOTTOM, 5)

        # Reset Configuration
        sizer.Add(wx.StaticText(panel, label="Reset Configuration"), 0, wx.LEFT | wx.TOP, 5)
        sizer.Add(
            wx.StaticText(panel, label="Restore all settings to their default values."),
            0,
            wx.LEFT,
            5,
        )

        reset_btn = wx.Button(panel, label="Reset all settings to defaults")
        reset_btn.Bind(wx.EVT_BUTTON, self.dialog._on_reset_defaults)
        sizer.Add(reset_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Full Data Reset
        sizer.Add(wx.StaticText(panel, label="Full Data Reset"), 0, wx.LEFT, 5)
        sizer.Add(
            wx.StaticText(
                panel,
                label="Reset all application data: settings, locations, caches, and alert state.",
            ),
            0,
            wx.LEFT,
            5,
        )

        full_reset_btn = wx.Button(panel, label="Reset all app data (settings, locations, caches)")
        full_reset_btn.Bind(wx.EVT_BUTTON, self.dialog._on_full_reset)
        sizer.Add(full_reset_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Configuration Files
        sizer.Add(wx.StaticText(panel, label="Configuration Files"), 0, wx.LEFT, 5)

        open_config_btn = wx.Button(panel, label="Open current config directory")
        open_config_btn.Bind(wx.EVT_BUTTON, self.dialog._on_open_config_dir)
        sizer.Add(open_config_btn, 0, wx.LEFT | wx.TOP, 10)

        open_installed_config_btn = wx.Button(
            panel, label="Open installed config directory (source)"
        )
        open_installed_config_btn.Bind(wx.EVT_BUTTON, self.dialog._on_open_installed_config_dir)
        sizer.Add(open_installed_config_btn, 0, wx.LEFT | wx.TOP, 10)

        if self.dialog._is_runtime_portable_mode():
            migrate_config_btn = wx.Button(panel, label="Copy installed config to portable")
            migrate_config_btn.Bind(
                wx.EVT_BUTTON, self.dialog._on_copy_installed_config_to_portable
            )
            sizer.Add(migrate_config_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        # Settings Backup
        sizer.Add(wx.StaticText(panel, label="Settings Backup"), 0, wx.LEFT | wx.TOP, 5)

        export_btn = wx.Button(panel, label="Export Settings...")
        export_btn.Bind(wx.EVT_BUTTON, self.dialog._on_export_settings)
        sizer.Add(export_btn, 0, wx.LEFT | wx.TOP, 10)

        import_btn = wx.Button(panel, label="Import Settings...")
        import_btn.Bind(wx.EVT_BUTTON, self.dialog._on_import_settings)
        sizer.Add(import_btn, 0, wx.LEFT | wx.TOP, 10)

        sizer.Add(
            wx.StaticText(panel, label="API Key Portability (Encrypted)"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )
        sizer.Add(
            wx.StaticText(
                panel,
                label=(
                    "Optional: export API keys to an encrypted bundle for transfer. "
                    "Import requires your passphrase and stores keys in this machine's keyring."
                ),
            ),
            0,
            wx.LEFT,
            5,
        )

        export_api_keys_btn = wx.Button(panel, label="Export API keys (encrypted)")
        export_api_keys_btn.Bind(wx.EVT_BUTTON, self.dialog._on_export_encrypted_api_keys)
        sizer.Add(export_api_keys_btn, 0, wx.LEFT | wx.TOP, 10)

        import_api_keys_btn = wx.Button(panel, label="Import API keys (encrypted)")
        import_api_keys_btn.Bind(wx.EVT_BUTTON, self.dialog._on_import_encrypted_api_keys)
        sizer.Add(import_api_keys_btn, 0, wx.LEFT | wx.TOP, 10)

        # Sound Pack Files
        sizer.Add(wx.StaticText(panel, label="Sound Pack Files"), 0, wx.LEFT | wx.TOP, 5)

        open_sounds_btn = wx.Button(panel, label="Open sound packs folder")
        open_sounds_btn.Bind(wx.EVT_BUTTON, self.dialog._on_open_soundpacks_dir)
        sizer.Add(open_sounds_btn, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "Advanced")
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
            "minimize_tray": "Minimize to notification area when closing",
            "minimize_on_startup": "Start minimized to notification area",
            "startup": "Launch automatically at startup",
            "weather_history": "Enable weather history comparisons",
        }
        for key, name in names.items():
            controls[key].SetName(name)
