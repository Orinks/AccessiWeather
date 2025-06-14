"""Menu factory module for AccessiWeather.

This module handles menu bar creation and menu-related functionality
for the WeatherApp, including debug menus and about dialog.
"""

import logging

import wx
import wx.adv

from accessiweather.version import __version__

logger = logging.getLogger(__name__)


class MenuFactory:
    """Handles menu creation and menu-related functionality for the WeatherApp."""

    def __init__(self, app_instance):
        """Initialize the MenuFactory.
        
        Args:
            app_instance: The WeatherApp instance
        """
        self.app = app_instance
        self.logger = logger

    def create_menu_bar(self):
        """Create the menu bar for the application.

        This method creates a menu bar with File and Help menus.
        If debug_mode or debug_alerts is enabled, it also adds a Debug menu.
        """
        # Create menu bar
        menu_bar = wx.MenuBar()

        # Create File menu
        file_menu = self._create_file_menu()
        menu_bar.Append(file_menu, "&File")

        # Add Debug menu if debug_mode is enabled
        if self.app.debug_mode:
            debug_menu = self.app.CreateDebugMenu()
            menu_bar.Append(debug_menu, "&Debug")

        # Create Help menu
        help_menu = self._create_help_menu()
        menu_bar.Append(help_menu, "&Help")

        # Set the menu bar
        self.app.SetMenuBar(menu_bar)

    def _create_file_menu(self):
        """Create the File menu.
        
        Returns:
            wx.Menu: The File menu
        """
        file_menu = wx.Menu()
        refresh_item = file_menu.Append(wx.ID_REFRESH, "&Refresh\tF5", "Refresh weather data")
        file_menu.AppendSeparator()
        settings_item = file_menu.Append(wx.ID_PREFERENCES, "&Settings...", "Open settings dialog")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit", "Exit the application")

        # Bind events
        self.app.Bind(wx.EVT_MENU, self.app.OnRefresh, refresh_item)
        self.app.Bind(wx.EVT_MENU, self.app.OnSettings, settings_item)
        self.app.Bind(wx.EVT_MENU, lambda e: self.app.Close(True), exit_item)

        return file_menu

    def _create_help_menu(self):
        """Create the Help menu.
        
        Returns:
            wx.Menu: The Help menu
        """
        help_menu = wx.Menu()
        check_updates_item = help_menu.Append(
            wx.ID_ANY, "Check for &Updates...", "Check for application updates"
        )
        help_menu.AppendSeparator()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "About AccessiWeather")

        # Bind events
        self.app.Bind(wx.EVT_MENU, self.app.OnCheckForUpdates, check_updates_item)
        self.app.Bind(wx.EVT_MENU, self.on_about, about_item)

        return help_menu

    def on_about(self, event):
        """Show the about dialog.

        Args:
            event: Menu event
        """
        info = wx.adv.AboutDialogInfo()
        info.SetName("AccessiWeather")
        info.SetVersion(__version__)
        info.SetDescription("An accessible weather application using NOAA data")
        info.SetCopyright("(C) 2023")
        info.SetWebSite("https://github.com/Orinks/AccessiWeather")

        wx.adv.AboutBox(info)
