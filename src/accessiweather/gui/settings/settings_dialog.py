"""Main settings dialog for AccessiWeather."""

import logging

import wx

from .advanced_tab import AdvancedTab
from .display_tab import DisplayTab
from .general_tab import GeneralTab
from .updates_tab import UpdatesTab

logger = logging.getLogger(__name__)


class SettingsDialog(wx.Dialog):
    """A dialog window for modifying application settings."""

    def __init__(self, parent, current_settings):
        """Initialize the Settings Dialog.

        Args:
            parent: The parent window.
            current_settings (dict): A dictionary containing the current values
                                     for the settings to be edited.
        """
        super().__init__(parent, title="Settings", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.current_settings = current_settings
        self._init_ui()
        self._load_settings()
        self.SetSizerAndFit(self.main_sizer)
        self.CenterOnParent()

    def _init_ui(self):
        """Initialize the UI components of the dialog."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create notebook (tab control)
        self.notebook = wx.Notebook(self)
        self.main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Create General tab
        self.general_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.general_panel, "General")
        self.general_tab = GeneralTab(self.general_panel)

        # Create Display tab
        self.display_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.display_panel, "Display")
        self.display_tab = DisplayTab(self.display_panel)

        # Create Advanced tab
        self.advanced_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.advanced_panel, "Advanced")
        self.advanced_tab = AdvancedTab(self.advanced_panel)

        # Create Updates tab
        self.updates_panel = wx.Panel(self.notebook)
        self.notebook.AddPage(self.updates_panel, "Updates")
        self.updates_tab = UpdatesTab(self.updates_panel, self)

        # --- Buttons ---
        button_sizer = wx.StdDialogButtonSizer()

        ok_button = wx.Button(self, wx.ID_OK)
        ok_button.SetDefault()
        button_sizer.AddButton(ok_button)

        cancel_button = wx.Button(self, wx.ID_CANCEL)
        button_sizer.AddButton(cancel_button)

        button_sizer.Realize()

        self.main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        # Bind events
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        # Cancel is handled automatically by wx.Dialog

    def _load_settings(self):
        """Load current settings into the UI controls."""
        try:
            # Load settings into each tab
            self.general_tab.load_settings(self.current_settings)
            self.display_tab.load_settings(self.current_settings)
            self.advanced_tab.load_settings(self.current_settings)
            self.updates_tab.load_settings(self.current_settings)

            logger.debug("Settings loaded into dialog.")
        except Exception as e:
            logger.error(f"Error loading settings into dialog: {e}")
            wx.MessageBox(f"Error loading settings: {e}", "Error", wx.OK | wx.ICON_ERROR, self)

    def _on_ok(self, event):  # event is required by wx
        """Handle OK button click: Validate and signal success."""
        # Validate all tabs
        tabs = [
            ("General", self.general_tab, 0),
            ("Display", self.display_tab, 1),
            ("Advanced", self.advanced_tab, 2),
            ("Updates", self.updates_tab, 3),
        ]

        for tab_name, tab_obj, tab_index in tabs:
            is_valid, error_message, focus_control = tab_obj.validate()
            if not is_valid:
                wx.MessageBox(
                    error_message,
                    "Invalid Setting",
                    wx.OK | wx.ICON_WARNING,
                    self,
                )
                self.notebook.SetSelection(tab_index)  # Switch to the problematic tab
                if focus_control:
                    focus_control.SetFocus()
                return  # Prevent dialog closing

        # If validation passes, end the modal dialog with wx.ID_OK
        self.EndModal(wx.ID_OK)

    def get_settings(self):
        """Retrieve the modified settings from the UI controls.

        Should only be called after the dialog returns wx.ID_OK.

        Returns:
            dict: A dictionary containing the updated settings.
        """
        settings = {}
        
        # Get settings from each tab
        settings.update(self.general_tab.get_settings())
        settings.update(self.display_tab.get_settings())
        settings.update(self.advanced_tab.get_settings())
        settings.update(self.updates_tab.get_settings())
        
        return settings

    def get_api_settings(self):
        """Retrieve the API-specific settings from the UI controls.

        Should only be called after the dialog returns wx.ID_OK.

        Returns:
            dict: A dictionary containing the updated API settings.
        """
        return {}

    def get_api_keys(self):
        """Retrieve the API keys from the UI controls.

        Should only be called after the dialog returns wx.ID_OK.

        Returns:
            dict: A dictionary containing the updated API keys.
        """
        return {}
