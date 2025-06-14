"""Advanced settings tab for the settings dialog."""

import wx

from .constants import CACHE_ENABLED_KEY, CACHE_TTL_KEY, MINIMIZE_TO_TRAY_KEY


class AdvancedTab:
    """Handles the Advanced tab of the settings dialog."""

    def __init__(self, parent_panel):
        """Initialize the Advanced tab.

        Args:
            parent_panel: The parent panel for this tab
        """
        self.panel = parent_panel
        self._init_ui()

    def _init_ui(self):
        """Initialize the Advanced tab controls."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=5)  # Increased rows to 3
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # Minimize to Tray Toggle
        minimize_to_tray_label = "Minimize to system tray when closing"
        self.minimize_to_tray_ctrl = wx.CheckBox(
            self.panel, label=minimize_to_tray_label, name="Minimize to Tray"
        )
        tooltip_minimize = (
            "When checked, clicking the X button will minimize the app to the system tray "
            "instead of closing it. You can still exit from the system tray menu."
        )
        self.minimize_to_tray_ctrl.SetToolTip(tooltip_minimize)
        # Add a spacer in the first column
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.minimize_to_tray_ctrl, 0, wx.ALL, 5)

        # Cache Enabled Toggle
        cache_enabled_label = "Enable caching of weather data"
        self.cache_enabled_ctrl = wx.CheckBox(
            self.panel, label=cache_enabled_label, name="Enable Caching"
        )
        tooltip_cache = (
            "When checked, weather data will be cached to reduce API calls. "
            "This can improve performance and reduce data usage."
        )
        self.cache_enabled_ctrl.SetToolTip(tooltip_cache)
        # Add a spacer in the first column
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)
        grid_sizer.Add(self.cache_enabled_ctrl, 0, wx.ALL, 5)

        # Cache TTL
        cache_ttl_label = wx.StaticText(self.panel, label="Cache Time-to-Live (seconds):")
        self.cache_ttl_ctrl = wx.SpinCtrl(
            self.panel, min=60, max=3600, initial=300, name="Cache TTL"
        )
        tooltip_ttl = "How long cached data remains valid (in seconds)."
        self.cache_ttl_ctrl.SetToolTip(tooltip_ttl)
        grid_sizer.Add(cache_ttl_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        # Don't expand spin control
        grid_sizer.Add(self.cache_ttl_ctrl, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
        self.panel.SetSizer(sizer)

    def load_settings(self, settings):
        """Load settings into the controls.

        Args:
            settings: Dictionary containing current settings
        """
        # Load advanced settings
        minimize_to_tray = settings.get(MINIMIZE_TO_TRAY_KEY, True)
        cache_enabled = settings.get(CACHE_ENABLED_KEY, True)
        cache_ttl = settings.get(CACHE_TTL_KEY, 300)

        self.minimize_to_tray_ctrl.SetValue(minimize_to_tray)
        self.cache_enabled_ctrl.SetValue(cache_enabled)
        self.cache_ttl_ctrl.SetValue(cache_ttl)

    def get_settings(self):
        """Get settings from the controls.

        Returns:
            Dictionary containing the settings from this tab
        """
        return {
            MINIMIZE_TO_TRAY_KEY: self.minimize_to_tray_ctrl.GetValue(),
            CACHE_ENABLED_KEY: self.cache_enabled_ctrl.GetValue(),
            CACHE_TTL_KEY: self.cache_ttl_ctrl.GetValue(),
        }

    def validate(self):
        """Validate the settings in this tab.

        Returns:
            Tuple of (is_valid, error_message, focus_control)
        """
        cache_ttl = self.cache_ttl_ctrl.GetValue()

        if cache_ttl < 60:
            return False, "Cache TTL must be at least 60 seconds.", self.cache_ttl_ctrl

        return True, None, None
