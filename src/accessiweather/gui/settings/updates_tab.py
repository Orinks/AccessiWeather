"""Updates settings tab for the settings dialog."""

import logging

import wx

from .constants import (
    AUTO_UPDATE_CHECK_KEY,
    DEFAULT_AUTO_UPDATE_CHECK,
    DEFAULT_UPDATE_CHANNEL,
    DEFAULT_UPDATE_CHECK_INTERVAL,
    UPDATE_CHANNEL_KEY,
    UPDATE_CHECK_INTERVAL_KEY,
)

logger = logging.getLogger(__name__)


class UpdatesTab:
    """Handles the Updates tab of the settings dialog."""

    def __init__(self, parent_panel, parent_dialog):
        """Initialize the Updates tab.

        Args:
            parent_panel: The parent panel for this tab
            parent_dialog: The parent settings dialog (for accessing main app)
        """
        self.panel = parent_panel
        self.parent_dialog = parent_dialog
        self._init_ui()

    def _init_ui(self):
        """Initialize the Updates tab controls."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # Auto-check for updates toggle
        auto_check_label = "Automatically check for updates"
        self.auto_update_check_ctrl = wx.CheckBox(
            self.panel, label=auto_check_label, name="Auto Check Updates"
        )
        tooltip_auto_check = (
            "When checked, AccessiWeather will automatically check for updates "
            "in the background according to the interval below."
        )
        self.auto_update_check_ctrl.SetToolTip(tooltip_auto_check)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)  # Empty cell for alignment
        grid_sizer.Add(self.auto_update_check_ctrl, 0, wx.ALL, 5)

        # Update check interval
        interval_label = wx.StaticText(self.panel, label="Check interval (hours):")
        self.update_check_interval_ctrl = wx.SpinCtrl(
            self.panel, min=1, max=168, initial=24, name="Update Check Interval"
        )
        tooltip_interval = (
            "How often to check for updates (in hours). Minimum 1 hour, maximum 1 week."
        )
        self.update_check_interval_ctrl.SetToolTip(tooltip_interval)
        grid_sizer.Add(interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.update_check_interval_ctrl, 0, wx.ALL, 5)

        # Update channel selection
        channel_label = wx.StaticText(self.panel, label="Update channel:")
        self.update_channel_ctrl = wx.Choice(self.panel, name="Update Channel")
        self.update_channel_ctrl.AppendItems(
            ["Stable releases only", "Development builds (includes pre-releases)"]
        )
        tooltip_channel = (
            "Choose which type of updates to receive. "
            "Stable releases are tested and recommended for most users. "
            "Development builds include the latest features but may be less stable."
        )
        self.update_channel_ctrl.SetToolTip(tooltip_channel)
        grid_sizer.Add(channel_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.update_channel_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Manual check button
        check_now_label = wx.StaticText(self.panel, label="Manual check:")
        self.check_now_button = wx.Button(
            self.panel, label="Check for Updates Now", name="Check Now"
        )
        tooltip_check_now = "Click to immediately check for available updates."
        self.check_now_button.SetToolTip(tooltip_check_now)
        grid_sizer.Add(check_now_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.check_now_button, 0, wx.ALL, 5)

        sizer.Add(grid_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Add informational text
        info_text = (
            "Update Information:\n\n"
            "• Stable releases are thoroughly tested and recommended for daily use\n"
            "• Development builds include the latest features and bug fixes\n"
            "• When updates are available, you can choose to download manually or install automatically\n"
            "• Automatic installation requires administrator privileges and UAC confirmation"
        )
        info_label = wx.StaticText(self.panel, label=info_text)
        info_label.SetFont(info_label.GetFont().Smaller())
        sizer.Add(info_label, 0, wx.ALL, 15)

        self.panel.SetSizer(sizer)

        # Bind events
        self.auto_update_check_ctrl.Bind(wx.EVT_CHECKBOX, self._on_auto_update_toggle)
        self.check_now_button.Bind(wx.EVT_BUTTON, self._on_check_now)

    def _on_auto_update_toggle(self, event):
        """Handle auto-update checkbox toggle."""
        enabled = self.auto_update_check_ctrl.GetValue()
        self.update_check_interval_ctrl.Enable(enabled)

    def _on_check_now(self, event):
        """Handle check for updates now button."""
        logger.info("Check for Updates Now button clicked in settings dialog")

        # Get the parent window (should be the main WeatherApp)
        parent = self.parent_dialog.GetParent()
        logger.debug(f"Parent window type: {type(parent).__name__}")

        if hasattr(parent, "OnCheckForUpdates"):
            logger.info("Parent has OnCheckForUpdates method, calling it")
            # Create a fake event to pass to the handler
            fake_event = wx.CommandEvent(wx.wxEVT_COMMAND_MENU_SELECTED)
            parent.OnCheckForUpdates(fake_event)
            logger.debug("OnCheckForUpdates method called successfully")
        else:
            logger.warning("Parent does not have OnCheckForUpdates method")
            wx.MessageBox(
                "Update checking is not available at this time.",
                "Check for Updates",
                wx.OK | wx.ICON_INFORMATION,
                self.panel,
            )

    def load_settings(self, settings):
        """Load settings into the controls.

        Args:
            settings: Dictionary containing current settings
        """
        # Load update settings
        auto_update_check = settings.get(AUTO_UPDATE_CHECK_KEY, DEFAULT_AUTO_UPDATE_CHECK)
        update_check_interval = settings.get(
            UPDATE_CHECK_INTERVAL_KEY, DEFAULT_UPDATE_CHECK_INTERVAL
        )
        update_channel = settings.get(UPDATE_CHANNEL_KEY, DEFAULT_UPDATE_CHANNEL)

        self.auto_update_check_ctrl.SetValue(auto_update_check)
        self.update_check_interval_ctrl.SetValue(update_check_interval)
        self.update_check_interval_ctrl.Enable(auto_update_check)

        # Set update channel dropdown
        if update_channel == "dev":
            self.update_channel_ctrl.SetSelection(1)  # Development builds
        else:
            self.update_channel_ctrl.SetSelection(0)  # Stable releases (default)

    def get_settings(self):
        """Get settings from the controls.

        Returns:
            Dictionary containing the settings from this tab
        """
        return {
            AUTO_UPDATE_CHECK_KEY: self.auto_update_check_ctrl.GetValue(),
            UPDATE_CHECK_INTERVAL_KEY: self.update_check_interval_ctrl.GetValue(),
            UPDATE_CHANNEL_KEY: "dev" if self.update_channel_ctrl.GetSelection() == 1 else "stable",
        }

    def validate(self):
        """Validate the settings in this tab.

        Returns:
            Tuple of (is_valid, error_message, focus_control)
        """
        # No validation needed for updates tab currently
        return True, None, None
