"""
Dialog for configuring AccessiWeather settings.

This module provides the main SettingsDialog class that coordinates between
specialized components for UI building, data handling, and validation.
"""

import logging

import wx
import wx.adv

from .settings.constants import TAB_ADVANCED, TAB_DISPLAY, TAB_GENERAL, TAB_UPDATES
from .settings.data_handler import SettingsDataHandler
from .settings.tab_components import (
    AdvancedTabBuilder,
    DisplayTabBuilder,
    GeneralTabBuilder,
    UpdatesTabBuilder,
)

logger = logging.getLogger(__name__)


class SettingsDialog(wx.Dialog):
    """
    A dialog window for modifying application settings.

    This class coordinates between specialized components for UI building,
    data handling, and validation while maintaining the main dialog structure.
    """

    def __init__(self, parent, current_settings):
        """
        Initialize the Settings Dialog.

        Args:
            parent: The parent window.
            current_settings (dict): A dictionary containing the current values
                                     for the settings to be edited.
        """
        super().__init__(parent, title="Settings", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.current_settings = current_settings

        # Initialize specialized handlers
        self.data_handler = SettingsDataHandler(self)

        # Build UI and load settings
        self._init_ui()
        self.data_handler.load_settings(current_settings)
        self.SetSizerAndFit(self.main_sizer)
        self.CenterOnParent()

    def _init_ui(self):
        """Initialize the UI components of the dialog using specialized builders."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook (tab control)
        self.notebook = wx.Notebook(self)
        self.main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Create tabs using specialized builders
        self._create_general_tab()
        self._create_display_tab()
        self._create_advanced_tab()
        self._create_updates_tab()

        # Create dialog buttons
        self._create_buttons()

        # Bind events
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _create_general_tab(self):
        """Create the General settings tab."""
        self.general_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.general_panel, TAB_GENERAL)
        builder = GeneralTabBuilder(self)
        builder.build_tab(self.general_panel)

    def _create_display_tab(self):
        """Create the Display settings tab."""
        self.display_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.display_panel, TAB_DISPLAY)
        builder = DisplayTabBuilder(self)
        builder.build_tab(self.display_panel)

    def _create_advanced_tab(self):
        """Create the Advanced settings tab."""
        self.advanced_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.advanced_panel, TAB_ADVANCED)
        builder = AdvancedTabBuilder(self)
        builder.build_tab(self.advanced_panel)

    def _create_updates_tab(self):
        """Create the Updates settings tab."""
        self.updates_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.updates_panel, TAB_UPDATES)
        builder = UpdatesTabBuilder(self)
        builder.build_tab(self.updates_panel)

    def _create_buttons(self):
        """Create the dialog buttons."""
        button_sizer = wx.StdDialogButtonSizer()

        ok_button = wx.Button(self, wx.ID_OK)
        ok_button.SetDefault()
        button_sizer.AddButton(ok_button)

        cancel_button = wx.Button(self, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)

        button_sizer.Realize()
        self.main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

    # Event handlers for UI components
    def _on_auto_update_toggle(self, event):
        """Handle auto-update checkbox toggle."""
        enabled = self.auto_update_check_ctrl.GetValue()
        self.update_check_interval_ctrl.Enable(enabled)

    def _on_check_now(self, event):
        """Handle check for updates now button."""
        logger.info("Check for Updates Now button clicked in settings dialog")

        # Get the parent window (should be the main WeatherApp)
        parent = self.GetParent()
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
                self,
            )

    def _on_taskbar_text_toggle(self, event):
        """Handle taskbar text toggle checkbox."""
        enabled = self.taskbar_text_ctrl.GetValue()
        self.taskbar_format_ctrl.Enable(enabled)
        self.dynamic_format_ctrl.Enable(enabled)

    def _on_ok(self, event):
        """Handle OK button click: Validate and signal success."""
        if self.data_handler.validate_settings():
            self.EndModal(wx.ID_OK)

    def get_settings(self):
        """
        Retrieve the modified settings from the UI controls.

        Returns:
            dict: A dictionary containing the updated settings.
        """
        return self.data_handler.get_settings()

    def get_api_settings(self):
        """
        Retrieve the API-specific settings from the UI controls.

        Returns:
            dict: A dictionary containing the updated API settings.
        """
        return self.data_handler.get_api_settings()

    def get_api_keys(self):
        """
        Retrieve the API keys from the UI controls.

        Returns:
            dict: A dictionary containing the updated API keys.
        """
        return self.data_handler.get_api_keys()
