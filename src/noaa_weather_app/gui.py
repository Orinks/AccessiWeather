"""Main GUI module for NOAA Weather App

This module provides the main application window and GUI components.
It integrates accessibility features for screen readers.
"""

import wx
import threading
import time
import logging
from typing import Dict, Any, List, Optional, Tuple

from noaa_weather_app.api_client import NoaaApiClient
from noaa_weather_app.notifications import WeatherNotifier
from noaa_weather_app.location import LocationManager
from noaa_weather_app.accessible_widgets import (
    AccessibleTextCtrl, AccessibleButton, AccessibleListCtrl,
    AccessibleStaticText, AccessibleChoice
)

logger = logging.getLogger(__name__)

# Update interval in seconds
UPDATE_INTERVAL = 15 * 60  # 15 minutes


class LocationDialog(wx.Dialog):
    """Dialog for adding or editing a location"""
    
    def __init__(self, parent, title="Add Location", location_name="", lat=None, lon=None):
        """Initialize the location dialog
        
        Args:
            parent: Parent window
            title: Dialog title
            location_name: Initial location name
            lat: Initial latitude
            lon: Initial longitude
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        
        # Create a panel with accessible widgets
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Name field
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = AccessibleStaticText(panel, label="Location Name:")
        self.name_ctrl = AccessibleTextCtrl(panel, value=location_name, label="Location Name")
        name_sizer.Add(name_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        name_sizer.Add(self.name_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Latitude field
        lat_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lat_label = AccessibleStaticText(panel, label="Latitude:")
        self.lat_ctrl = AccessibleTextCtrl(
            panel, 
            value=str(lat) if lat is not None else "", 
            label="Latitude"
        )
        lat_sizer.Add(lat_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lat_sizer.Add(self.lat_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lat_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Longitude field
        lon_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lon_label = AccessibleStaticText(panel, label="Longitude:")
        self.lon_ctrl = AccessibleTextCtrl(
            panel, 
            value=str(lon) if lon is not None else "", 
            label="Longitude"
        )
        lon_sizer.Add(lon_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lon_sizer.Add(self.lon_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lon_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Description for screen readers
        help_text = AccessibleStaticText(
            panel, 
            label="Enter latitude and longitude in decimal format (e.g., 35.123, -80.456)"
        )
        sizer.Add(help_text, 0, wx.ALL, 10)
        
        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = AccessibleButton(panel, wx.ID_OK, "Save")
        self.cancel_button = AccessibleButton(panel, wx.ID_CANCEL, "Cancel")
        
        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        sizer.Fit(self)
        
        # Set initial focus for accessibility
        self.name_ctrl.SetFocus()
        
        # Connect events
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
    
    def OnOK(self, event):
        """Handle OK button event
        
        Args:
            event: Button event
        """
        # Validate inputs
        name = self.name_ctrl.GetValue().strip()
        lat_str = self.lat_ctrl.GetValue().strip()
        lon_str = self.lon_ctrl.GetValue().strip()
        
        if not name:
            wx.MessageBox("Please enter a location name", "Error", wx.OK | wx.ICON_ERROR)
            self.name_ctrl.SetFocus()
            return
            
        try:
            lat = float(lat_str)
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be between -90 and 90")
        except ValueError as e:
            wx.MessageBox(f"Invalid latitude: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            self.lat_ctrl.SetFocus()
            return
            
        try:
            lon = float(lon_str)
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be between -180 and 180")
        except ValueError as e:
            wx.MessageBox(f"Invalid longitude: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
            self.lon_ctrl.SetFocus()
            return
            
        event.Skip()  # Continue with default handler
    
    def GetValues(self):
        """Get the dialog values
        
        Returns:
            Tuple of (name, latitude, longitude)
        """
        name = self.name_ctrl.GetValue().strip()
        lat = float(self.lat_ctrl.GetValue().strip())
        lon = float(self.lon_ctrl.GetValue().strip())
        return (name, lat, lon)


class WeatherDiscussionDialog(wx.Dialog):
    """Dialog for displaying weather discussion text"""
    
    def __init__(self, parent, title="Weather Discussion", text=""):
        """Initialize the weather discussion dialog
        
        Args:
            parent: Parent window
            title: Dialog title
            text: Discussion text
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create a text control for the discussion
        self.text_ctrl = wx.TextCtrl(
            panel,
            value=text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        
        # Set accessible name and description
        self.text_ctrl.SetName("Weather Discussion Text")
        
        # Create accessible object
        accessible = self.text_ctrl.CreateAccessible()
        if accessible:
            accessible.SetName("Weather Discussion Text")
            accessible.SetRole(wx.ACC_ROLE_TEXT)
            
        # Add to sizer with expansion
        sizer.Add(self.text_ctrl, 1, wx.ALL | wx.EXPAND, 10)
        
        # Close button
        close_button = AccessibleButton(panel, wx.ID_CLOSE, "Close")
        sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        self.SetSize((600, 400))
        
        # Bind events
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CLOSE)
        
        # Set initial focus for accessibility
        self.text_ctrl.SetFocus()
    
    def OnClose(self, event):
        """Handle close button event
        
        Args:
            event: Button event
        """
        self.EndModal(wx.ID_CLOSE)


class WeatherApp(wx.Frame):
    """Main application window"""
    
    def __init__(self, parent=None):
        """Initialize the weather app
        
        Args:
            parent: Parent window
        """
        super().__init__(parent, title="NOAA Weather App", size=(800, 600))
        
        # Initialize components
        self.api_client = NoaaApiClient()
        self.notifier = WeatherNotifier()
        self.location_manager = LocationManager()
        
        # State variables
        self.current_forecast = None
        self.current_alerts = []
        self.updating = False
        self.update_thread = None
        
        # Create UI
        self.InitUI()
        
        # Set up status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")
        
        # Start update timer
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.timer.Start(1000)  # Check every 1 second for updates
        
        # Last update timestamp
        self.last_update = 0
        
        # Register with accessibility system
        self.SetName("NOAA Weather App")
        accessible = self.CreateAccessible()
        if accessible:
            accessible.SetName("NOAA Weather App")
            accessible.SetRole(wx.ACC_ROLE_WINDOW)
        
        # Initial load
        self.UpdateLocationDropdown()
        self.UpdateWeatherData()
    
    def InitUI(self):
        """Initialize the user interface"""
        # Create main panel with accessible keyboard navigation
        self.panel = wx.Panel(self)
        self.panel.SetName("Main Panel")
        
        # Create keyboard event handler for accessibility
        self.panel.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        
        # Main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Location section
        location_sizer = wx.BoxSizer(wx.HORIZONTAL)
        location_label = AccessibleStaticText(self.panel, label="Location:")
        self.location_choice = AccessibleChoice(self.panel, label="Location Selector")
        
        # Location buttons
        self.add_location_btn = AccessibleButton(self.panel, label="Add Location")
        self.remove_location_btn = AccessibleButton(self.panel, label="Remove Location")
        
        location_sizer.Add(location_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        location_sizer.Add(self.location_choice, 1, wx.ALL | wx.EXPAND, 5)
        location_sizer.Add(self.add_location_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.remove_location_btn, 0, wx.ALL, 5)
        main_sizer.Add(location_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Weather info section
        weather_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Left side - forecast
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        forecast_label = AccessibleStaticText(self.panel, label="Current Forecast:")
        self.forecast_text = wx.TextCtrl(
            self.panel, 
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        
        # Make forecast text accessible
        self.forecast_text.SetName("Forecast Text")
        accessible = self.forecast_text.CreateAccessible()
        if accessible:
            accessible.SetName("Forecast Text")
            accessible.SetRole(wx.ACC_ROLE_TEXT)
        
        left_sizer.Add(forecast_label, 0, wx.ALL, 5)
        left_sizer.Add(self.forecast_text, 1, wx.ALL | wx.EXPAND, 5)
        
        # Right side - alerts
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        alerts_label = AccessibleStaticText(self.panel, label="Weather Alerts:")
        self.alerts_list = AccessibleListCtrl(
            self.panel, 
            style=wx.LC_REPORT | wx.BORDER_SUNKEN,
            label="Weather Alerts List"
        )
        
        # Set up alerts list columns
        self.alerts_list.InsertColumn(0, "Type", width=150)
        self.alerts_list.InsertColumn(1, "Severity", width=100)
        self.alerts_list.InsertColumn(2, "Headline", width=300)
        
        # Buttons for alerts
        alerts_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.view_alert_btn = AccessibleButton(self.panel, label="View Alert Details")
        alerts_btn_sizer.Add(self.view_alert_btn, 1, wx.ALL, 5)
        
        right_sizer.Add(alerts_label, 0, wx.ALL, 5)
        right_sizer.Add(self.alerts_list, 1, wx.ALL | wx.EXPAND, 5)
        right_sizer.Add(alerts_btn_sizer, 0, wx.EXPAND, 5)
        
        # Add left and right sizers to the weather sizer
        weather_sizer.Add(left_sizer, 1, wx.EXPAND | wx.RIGHT, 10)
        weather_sizer.Add(right_sizer, 1, wx.EXPAND | wx.LEFT, 10)
        main_sizer.Add(weather_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
        # Bottom buttons
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = AccessibleButton(self.panel, label="Refresh Now")
        self.discussion_btn = AccessibleButton(self.panel, label="View Forecast Discussion")
        
        bottom_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        bottom_sizer.Add(self.discussion_btn, 0, wx.ALL, 5)
        main_sizer.Add(bottom_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        # Set main sizer for panel
        self.panel.SetSizer(main_sizer)
        
        # Bind events
        self.location_choice.Bind(wx.EVT_CHOICE, self.OnLocationChange)
        self.add_location_btn.Bind(wx.EVT_BUTTON, self.OnAddLocation)
        self.remove_location_btn.Bind(wx.EVT_BUTTON, self.OnRemoveLocation)
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.OnRefresh)
        self.discussion_btn.Bind(wx.EVT_BUTTON, self.OnViewDiscussion)
        self.view_alert_btn.Bind(wx.EVT_BUTTON, self.OnViewAlert)
        self.alerts_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnAlertActivated)
        
        # Close event
        self.Bind(wx.EVT_CLOSE, self.OnClose)
    
    def OnKeyDown(self, event):
        """Handle key down events for accessibility
        
        Args:
            event: Key event
        """
        # Add global keyboard shortcuts here
        key_code = event.GetKeyCode()
        
        # Example: F5 to refresh
        if key_code == wx.WXK_F5:
            self.UpdateWeatherData()
        else:
            event.Skip()
    
    def UpdateLocationDropdown(self):
        """Update the location dropdown with saved locations"""
        self.location_choice.Clear()
        
        locations = self.location_manager.get_all_locations()
        for location in locations:
            self.location_choice.Append(location)
        
        # Set current location if available
        current = self.location_manager.get_current_location()
        if current:
            name, _, _ = current
            self.location_choice.SetStringSelection(name)
    
    def UpdateWeatherData(self):
        """Update weather data in a separate thread"""
        if self.updating:
            return
        
        # Get current location
        location = self.location_manager.get_current_location()
        if not location:
            self.SetStatusText("No location selected. Please add a location.")
            self.forecast_text.SetValue("No location selected. Please add a location.")
            return
        
        self.updating = True
        self.SetStatusText("Updating weather data...")
        
        # Start update in a separate thread
        self.update_thread = threading.Thread(target=self._FetchWeatherData, args=(location,))
        self.update_thread.daemon = True
        self.update_thread.start()
    
    def _FetchWeatherData(self, location):
        """Fetch weather data from NOAA API
        
        Args:
            location: Tuple of (name, lat, lon)
        """
        name, lat, lon = location
        
        try:
            # Get forecast
            forecast_data = self.api_client.get_forecast(lat, lon)
            
            # Get alerts
            alerts_data = self.api_client.get_alerts(lat, lon)
            
            # Process data
            wx.CallAfter(self._UpdateForecastDisplay, forecast_data)
            wx.CallAfter(self._UpdateAlertsDisplay, alerts_data)
            wx.CallAfter(self.SetStatusText, f"Weather data updated at {time.strftime('%H:%M:%S')}")
            
            # Update last update time
            self.last_update = time.time()
        except Exception as e:
            wx.CallAfter(self.SetStatusText, f"Error updating weather data: {str(e)}")
            logger.error(f"Error updating weather data: {str(e)}")
        finally:
            self.updating = False
    
    def _UpdateForecastDisplay(self, forecast_data):
        """Update the forecast display with data
        
        Args:
            forecast_data: Dictionary with forecast data
        """
        self.current_forecast = forecast_data
        
        # Extract periods
        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            self.forecast_text.SetValue("No forecast data available.")
            return
        
        # Format forecast text
        text = ""
        for period in periods[:5]:  # Show next 5 periods
            name = period.get("name", "Unknown")
            temp = period.get("temperature", "?")
            unit = period.get("temperatureUnit", "F")
            detail = period.get("detailedForecast", "No details available.")
            
            text += f"{name}: {temp}°{unit}\n"
            text += f"{detail}\n\n"
        
        self.forecast_text.SetValue(text)
    
    def _UpdateAlertsDisplay(self, alerts_data):
        """Update the alerts display with data
        
        Args:
            alerts_data: Dictionary with alerts data
        """
        # Process alerts
        self.current_alerts = self.notifier.process_alerts(alerts_data)
        
        # Clear and update list
        self.alerts_list.DeleteAllItems()
        
        for i, alert in enumerate(self.current_alerts):
            event_type = alert.get("event", "Unknown")
            severity = alert.get("severity", "Unknown")
            headline = alert.get("headline", "No details")
            
            index = self.alerts_list.InsertItem(i, event_type)
            self.alerts_list.SetItem(index, 1, severity)
            self.alerts_list.SetItem(index, 2, headline)
    
    def OnLocationChange(self, event):
        """Handle location choice change
        
        Args:
            event: Choice event
        """
        selected = self.location_choice.GetStringSelection()
        if selected:
            self.location_manager.set_current_location(selected)
            self.UpdateWeatherData()
    
    def OnAddLocation(self, event):
        """Handle add location button
        
        Args:
            event: Button event
        """
        dialog = LocationDialog(self, title="Add Location")
        if dialog.ShowModal() == wx.ID_OK:
            name, lat, lon = dialog.GetValues()
            self.location_manager.add_location(name, lat, lon)
            self.UpdateLocationDropdown()
            self.location_choice.SetStringSelection(name)
            self.location_manager.set_current_location(name)
            self.UpdateWeatherData()
        dialog.Destroy()
    
    def OnRemoveLocation(self, event):
        """Handle remove location button
        
        Args:
            event: Button event
        """
        selected = self.location_choice.GetStringSelection()
        if not selected:
            wx.MessageBox("Please select a location to remove", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        if wx.MessageBox(
            f"Are you sure you want to remove the location '{selected}'?", 
            "Confirm Removal", 
            wx.YES_NO | wx.ICON_QUESTION
        ) == wx.YES:
            self.location_manager.remove_location(selected)
            self.UpdateLocationDropdown()
            
            # Update data if we have any locations left
            if self.location_choice.GetCount() > 0:
                self.UpdateWeatherData()
            else:
                self.forecast_text.SetValue("No location selected. Please add a location.")
                self.alerts_list.DeleteAllItems()
    
    def OnRefresh(self, event):
        """Handle refresh button
        
        Args:
            event: Button event
        """
        self.UpdateWeatherData()
    
    def OnViewDiscussion(self, event):
        """Handle view discussion button
        
        Args:
            event: Button event
        """
        location = self.location_manager.get_current_location()
        if not location:
            wx.MessageBox("No location selected. Please add a location.", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        name, lat, lon = location
        
        try:
            self.SetStatusText("Fetching forecast discussion...")
            discussion_text = self.api_client.get_discussion(lat, lon)
            
            if not discussion_text:
                wx.MessageBox("No forecast discussion available.", "Information", wx.OK | wx.ICON_INFORMATION)
                return
            
            # Show discussion dialog
            dialog = WeatherDiscussionDialog(self, title=f"Weather Discussion for {name}", text=discussion_text)
            dialog.ShowModal()
            dialog.Destroy()
        except Exception as e:
            wx.MessageBox(f"Error fetching discussion: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.SetStatusText("Ready")
    
    def OnViewAlert(self, event):
        """Handle view alert button
        
        Args:
            event: Button event
        """
        self.ShowSelectedAlert()
    
    def OnAlertActivated(self, event):
        """Handle double-click on alert
        
        Args:
            event: List event
        """
        self.ShowSelectedAlert()
    
    def ShowSelectedAlert(self):
        """Show details for the selected alert"""
        selected = self.alerts_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select an alert to view", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        if selected >= len(self.current_alerts):
            return
        
        alert = self.current_alerts[selected]
        event_type = alert.get("event", "Unknown Event")
        description = alert.get("description", "No description available.")
        
        # Show alert details in a dialog
        wx.MessageBox(
            description,
            f"Alert: {event_type}",
            wx.OK | wx.ICON_INFORMATION
        )
    
    def OnTimer(self, event):
        """Handle timer event for periodic updates
        
        Args:
            event: Timer event
        """
        # Check if we need to update
        if time.time() - self.last_update > UPDATE_INTERVAL and not self.updating:
            self.UpdateWeatherData()
    
    def OnClose(self, event):
        """Handle window close event
        
        Args:
            event: Close event
        """
        self.timer.Stop()
        event.Skip()  # Continue with default handler
