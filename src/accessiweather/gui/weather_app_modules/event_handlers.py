"""Event handling for WeatherApp.

This module handles menu events, keyboard shortcuts, timer events,
and other UI event processing for the WeatherApp.
"""

import logging
import time

import wx
import wx.adv

from accessiweather.version import __version__

from ..settings_dialog import UPDATE_INTERVAL_KEY

logger = logging.getLogger(__name__)


class WeatherAppEventHandlers:
    """Event handling for WeatherApp."""

    def __init__(self, weather_app):
        """Initialize the event handlers module.

        Args:
            weather_app: Reference to the main WeatherApp instance
        """
        self.app = weather_app
        logger.debug("WeatherAppEventHandlers initialized")

    def OnTimer(self, event):
        """Handle timer event for periodic updates

        Args:
            event: Timer event
        """
        # Get update interval from config (default to 10 minutes)
        settings = self.app.config.get("settings", {})
        update_interval_minutes = settings.get(UPDATE_INTERVAL_KEY, 10)
        update_interval_seconds = update_interval_minutes * 60

        # Calculate time since last update
        now = time.time()
        time_since_last_update = now - self.app.last_update
        next_update_in = update_interval_seconds - time_since_last_update

        # Enhanced logging in debug mode
        if self.app.debug_mode:
            logger.info(
                f"[DEBUG] Timer check: interval={update_interval_minutes}min, "
                f"time_since_last={time_since_last_update:.1f}s, "
                f"next_update_in={next_update_in:.1f}s"
            )
        else:
            # Regular debug logging
            logger.debug(
                f"Timer check: interval={update_interval_minutes}min, "
                f"time_since_last={time_since_last_update:.1f}s, "
                f"next_update_in={next_update_in:.1f}s"
            )

        # Check if it's time to update
        if time_since_last_update >= update_interval_seconds:
            if not self.app.updating:
                logger.info(
                    f"Timer triggered weather update. "
                    f"Interval: {update_interval_minutes} minutes, "
                    f"Time since last update: {time_since_last_update:.1f} seconds"
                )
                self.app.UpdateWeatherData()
            else:
                logger.debug("Timer skipped update: already updating.")

    def OnCharHook(self, event):
        """Handle character hook events for global keyboard shortcuts.

        This is a higher-level event handler that will catch keyboard events
        before they reach individual controls.

        Args:
            event: Character hook event
        """
        key_code = event.GetKeyCode()

        if key_code == wx.WXK_ESCAPE:
            # Escape key to minimize to system tray
            logger.info("Escape key pressed in CharHook, hiding to system tray")
            if hasattr(self.app, "taskbar_icon") and self.app.taskbar_icon:
                logger.info("Hiding app to system tray from CharHook")
                self.app.Hide()
                return  # Don't skip the event - we've handled it

        # For all other keys, allow normal processing
        event.Skip()

    def OnAbout(self, event):
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

    def _create_menu_bar(self):
        """Create the menu bar for the application.

        This method creates a menu bar with File and Help menus.
        If debug_mode or debug_alerts is enabled, it also adds a Debug menu.
        """
        # Create menu bar
        menu_bar = wx.MenuBar()

        # Create File menu
        file_menu = wx.Menu()
        refresh_item = file_menu.Append(wx.ID_REFRESH, "&Refresh\tF5", "Refresh weather data")
        file_menu.AppendSeparator()
        settings_item = file_menu.Append(wx.ID_PREFERENCES, "&Settings...", "Open settings dialog")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit", "Exit the application")

        # Add File menu to menu bar
        menu_bar.Append(file_menu, "&File")

        # Add Debug menu if debug_mode is enabled
        if self.app.debug_mode:
            debug_menu = self.app.CreateDebugMenu()
            menu_bar.Append(debug_menu, "&Debug")

        # Create Help menu
        help_menu = wx.Menu()
        check_updates_item = help_menu.Append(
            wx.ID_ANY, "Check for &Updates...", "Check for application updates"
        )
        help_menu.AppendSeparator()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "About AccessiWeather")

        # Add Help menu to menu bar
        menu_bar.Append(help_menu, "&Help")

        # Set the menu bar
        self.app.SetMenuBar(menu_bar)

        # Bind events
        self.app.Bind(wx.EVT_MENU, self.app.OnRefresh, refresh_item)
        self.app.Bind(wx.EVT_MENU, self.app.OnSettings, settings_item)
        self.app.Bind(wx.EVT_MENU, lambda e: self.app.Close(True), exit_item)
        self.app.Bind(wx.EVT_MENU, self.app.OnCheckForUpdates, check_updates_item)
        self.app.Bind(wx.EVT_MENU, self.OnAbout, about_item)
