"""Debug handlers for the WeatherApp class

This module contains the debug-related handlers for the WeatherApp class.
"""

import json
import logging

import wx

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppDebugHandlers(WeatherAppHandlerBase):
    """Debug handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides debug-related event handlers for the WeatherApp class.
    """

    def CreateDebugMenu(self):
        """Create a debug menu for the main application.

        This method is only called when debug_mode is enabled.
        """
        # Create the debug menu
        debug_menu = wx.Menu()

        # Add menu items
        self.debug_show_config_item = debug_menu.Append(
            wx.ID_ANY, "Show Configuration", "Display the current configuration"
        )
        self.debug_show_api_data_item = debug_menu.Append(
            wx.ID_ANY, "Show API Data", "Display the raw API data for the current location"
        )
        self.debug_log_viewer_item = debug_menu.Append(
            wx.ID_ANY, "Open Log Viewer", "Open a window to view the application log"
        )

        self.debug_console_item = debug_menu.Append(
            wx.ID_ANY, "Open Debug Console", "Open a Python console for debugging"
        )

        debug_menu.AppendSeparator()

        # Add alert testing items (now part of regular debug mode)
        self.debug_test_alerts_item = debug_menu.Append(
            wx.ID_ANY, "Test Alert Update", "Manually trigger an alert update"
        )
        self.debug_verify_interval_item = debug_menu.Append(
            wx.ID_ANY, "Verify Update Interval", "Verify the unified update interval"
        )
        debug_menu.AppendSeparator()

        # Add general debug items
        self.debug_toggle_debug_msgs_item = debug_menu.Append(
            wx.ID_ANY, "Toggle Debug Messages", "Toggle display of debug message boxes"
        )

        # Bind events
        self.Bind(wx.EVT_MENU, self.OnShowConfig, self.debug_show_config_item)
        self.Bind(wx.EVT_MENU, self.OnShowApiData, self.debug_show_api_data_item)
        self.Bind(wx.EVT_MENU, self.OnOpenLogViewer, self.debug_log_viewer_item)
        self.Bind(wx.EVT_MENU, self.OnOpenDebugConsole, self.debug_console_item)
        self.Bind(wx.EVT_MENU, self.OnToggleDebugMessages, self.debug_toggle_debug_msgs_item)
        self.Bind(wx.EVT_MENU, self.OnTestAlerts, self.debug_test_alerts_item)
        self.Bind(wx.EVT_MENU, self.OnVerifyInterval, self.debug_verify_interval_item)

        return debug_menu

    def OnShowConfig(self, event):  # event is required by wx
        """Show the current configuration in a dialog.

        Args:
            event: Menu event
        """
        # Format the config as pretty JSON
        config_json = json.dumps(self.config, indent=4)

        # Create a dialog with a text control
        dialog = wx.Dialog(self, title="Configuration", size=(600, 400))
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Add a text control with the config
        text_ctrl = wx.TextCtrl(
            dialog, value=config_json, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

        # Add a close button
        close_btn = wx.Button(dialog, wx.ID_CLOSE, "Close")
        sizer.Add(close_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Bind the close button
        close_btn.Bind(wx.EVT_BUTTON, lambda e: dialog.EndModal(wx.ID_CLOSE))

        dialog.SetSizer(sizer)
        dialog.ShowModal()
        dialog.Destroy()

    def OnShowApiData(self, event):  # event is required by wx
        """Show the raw API data for the current location.

        Args:
            event: Menu event
        """
        # Get the current location
        location = self.location_service.get_current_location()
        if not location:
            wx.MessageBox("No location selected", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Create a notebook dialog
        dialog = wx.Dialog(self, title="API Data", size=(800, 600))
        sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(dialog)
        sizer.Add(notebook, 1, wx.ALL | wx.EXPAND, 10)

        # Add pages for different data types
        self._add_api_data_page(notebook, "Forecast", self.current_forecast)
        self._add_api_data_page(notebook, "Alerts", self.current_alerts)

        if hasattr(self, "hourly_forecast_data"):
            self._add_api_data_page(notebook, "Hourly Forecast", self.hourly_forecast_data)

        # Add a close button
        close_btn = wx.Button(dialog, wx.ID_CLOSE, "Close")
        sizer.Add(close_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Bind the close button
        close_btn.Bind(wx.EVT_BUTTON, lambda e: dialog.EndModal(wx.ID_CLOSE))

        dialog.SetSizer(sizer)
        dialog.ShowModal()
        dialog.Destroy()

    def _add_api_data_page(self, notebook, title, data):
        """Add a page to the API data notebook.

        Args:
            notebook: The notebook to add the page to
            title: The title of the page
            data: The data to display
        """
        panel = wx.Panel(notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Format the data as pretty JSON
        try:
            data_json = json.dumps(data, indent=4)
        except (TypeError, ValueError):
            data_json = f"Unable to format data as JSON: {str(data)}"

        # Add a text control with the data
        text_ctrl = wx.TextCtrl(
            panel, value=data_json, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL
        )
        sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(sizer)
        notebook.AddPage(panel, title)

    def OnOpenLogViewer(self, event):  # event is required by wx
        """Open a window to view the application log.

        Args:
            event: Menu event
        """
        from ..debug_log_window import DebugLogWindow

        # Create the log window if it doesn't exist
        if not hasattr(self, "_debug_log_window") or self._debug_log_window is None:
            self._debug_log_window = DebugLogWindow(self)

        # Show the log window
        self._debug_log_window.Show()
        self._debug_log_window.Raise()

    def OnOpenDebugConsole(self, event):  # event is required by wx
        """Open a Python console for debugging.

        Args:
            event: Menu event
        """
        from ..debug_console import DebugConsole

        # Create the console window if it doesn't exist
        if not hasattr(self, "_debug_console") or self._debug_console is None:
            # Create a context dictionary with useful variables
            context = {
                "app": self,
                "wx": wx,
            }
            self._debug_console = DebugConsole(self, context)

        # Show the console window
        self._debug_console.Show()
        self._debug_console.Raise()

    def OnTestAlerts(self, event):  # event is required by wx
        """Manually trigger an alert update.

        Args:
            event: Menu event
        """
        self.test_alert_update()

    def OnVerifyInterval(self, event):  # event is required by wx
        """Verify the unified update interval.

        Args:
            event: Menu event
        """
        self.verify_update_interval()

    def OnToggleDebugMessages(self, event):  # event is required by wx
        """Toggle display of debug message boxes.

        Args:
            event: Menu event
        """
        # Toggle the debug_mode flag
        self.debug_mode = not self.debug_mode

        # Update the menu item text
        status = "ON" if self.debug_mode else "OFF"
        self.debug_toggle_debug_msgs_item.SetItemLabel(
            f"Toggle Debug Messages (Currently {status})"
        )

        # Show a message box to confirm the change
        wx.MessageBox(
            f"Debug messages are now {'enabled' if self.debug_mode else 'disabled'}",
            "Debug Messages",
            wx.OK | wx.ICON_INFORMATION,
        )

        # Log the change
        logger.info(f"Debug messages {'enabled' if self.debug_mode else 'disabled'}")
