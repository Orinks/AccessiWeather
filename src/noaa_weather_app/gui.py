"""Main GUI module for NOAA Weather App

This module provides the main application window and GUI components.
It integrates accessibility features for screen readers.
"""

import wx
import threading
import time
import logging
import json
import os
from typing import Dict, Any, List, Optional, Tuple
import traceback

from noaa_weather_app.api_client import NoaaApiClient
from noaa_weather_app.notifications import WeatherNotifier
from noaa_weather_app.accessible_widgets import (
    AccessibleTextCtrl, AccessibleButton, AccessibleListCtrl,
    AccessibleStaticText, AccessibleChoice
)

logger = logging.getLogger(__name__)

# Update interval in seconds
UPDATE_INTERVAL = 15 * 60  # 15 minutes


from noaa_weather_app.geocoding import GeocodingService

class AdvancedLocationDialog(wx.Dialog):
    """Dialog for manually entering lat/lon coordinates"""
    
    def __init__(self, parent, title="Advanced Location Options", lat=None, lon=None):
        """Initialize the advanced location dialog
        
        Args:
            parent: Parent window
            title: Dialog title
            lat: Initial latitude
            lon: Initial longitude
        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)
        
        # Create a panel with accessible widgets
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
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
        self.lat_ctrl.SetFocus()
        
        # Connect events
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
    
    def OnOK(self, event):
        """Handle OK button event
        
        Args:
            event: Button event
        """
        # Validate inputs
        lat_str = self.lat_ctrl.GetValue().strip()
        lon_str = self.lon_ctrl.GetValue().strip()
            
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
            Tuple of (latitude, longitude)
        """
        lat = float(self.lat_ctrl.GetValue().strip())
        lon = float(self.lon_ctrl.GetValue().strip())
        return (lat, lon)


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
        
        # Initialize geocoding service
        self.geocoding_service = GeocodingService()
        self.latitude = lat
        self.longitude = lon
        
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
        
        # Location search (address or zip code)
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = AccessibleStaticText(panel, label="Search Location:")
        self.search_ctrl = AccessibleTextCtrl(panel, value="", label="Search by Address or ZIP Code")
        search_sizer.Add(search_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        search_sizer.Add(self.search_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Search button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_button = AccessibleButton(panel, wx.ID_ANY, "Search")
        self.advanced_button = AccessibleButton(panel, wx.ID_ANY, "Advanced (Lat/Lon)")
        button_sizer.Add(self.search_button, 0, wx.ALL, 5)
        button_sizer.Add(self.advanced_button, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.CENTER, 5)
        
        # Result display
        self.result_text = AccessibleTextCtrl(
            panel,
            value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 60)
        )
        self.result_text.SetLabel("Search Result")
        sizer.Add(self.result_text, 0, wx.ALL | wx.EXPAND, 5)
        
        # Description for screen readers
        help_text = AccessibleStaticText(
            panel, 
            label="Enter an address, city, or ZIP code to search for a location"
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
        
        # If lat/lon are provided, show them in the result
        if lat is not None and lon is not None:
            self.latitude = lat
            self.longitude = lon
            self.result_text.SetValue(f"Custom coordinates: {lat}, {lon}")
        
        # Connect events
        self.Bind(wx.EVT_BUTTON, self.OnSearch, self.search_button)
        self.Bind(wx.EVT_BUTTON, self.OnAdvanced, self.advanced_button)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
    
    def OnSearch(self, event):
        """Handle search button click
        
        Args:
            event: Button event
        """
        # Get search query
        query = self.search_ctrl.GetValue().strip()
        if not query:
            wx.MessageBox("Please enter an address or ZIP code to search", "Error", wx.OK | wx.ICON_ERROR)
            self.search_ctrl.SetFocus()
            return
        
        # Show searching message
        self.result_text.SetValue("Searching...")
        wx.GetApp().Yield()  # Update UI immediately
        
        # Search for location
        result = self.geocoding_service.geocode_address(query)
        if result:
            lat, lon, address = result
            self.latitude = lat
            self.longitude = lon
            
            # If the user hasn't entered a name, suggest one based on the address
            if not self.name_ctrl.GetValue().strip():
                # Extract a short name from the address (first part before comma)
                suggested_name = address.split(',')[0]
                self.name_ctrl.SetValue(suggested_name)
            
            # Display result
            self.result_text.SetValue(f"Found: {address}\nCoordinates: {lat:.6f}, {lon:.6f}")
        else:
            self.result_text.SetValue("Location not found. Try a different search or use Advanced options.")
    
    def OnAdvanced(self, event):
        """Handle advanced button click to open manual lat/lon dialog
        
        Args:
            event: Button event
        """
        # Open advanced dialog with current coordinates if available
        dialog = AdvancedLocationDialog(
            self, 
            lat=self.latitude, 
            lon=self.longitude
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            lat, lon = dialog.GetValues()
            self.latitude = lat
            self.longitude = lon
            self.result_text.SetValue(f"Custom coordinates: {lat:.6f}, {lon:.6f}")
        
        dialog.Destroy()
    
    def OnOK(self, event):
        """Handle OK button event
        
        Args:
            event: Button event
        """
        # Validate inputs
        name = self.name_ctrl.GetValue().strip()
        
        if not name:
            wx.MessageBox("Please enter a location name", "Error", wx.OK | wx.ICON_ERROR)
            self.name_ctrl.SetFocus()
            return
        
        if self.latitude is None or self.longitude is None:
            wx.MessageBox("Please search for a location or enter coordinates using the Advanced option", "Error", wx.OK | wx.ICON_ERROR)
            self.search_ctrl.SetFocus()
            return
        
        event.Skip()  # Continue with default handler
    
    def GetValues(self):
        """Get the dialog values
        
        Returns:
            Tuple of (name, latitude, longitude)
        """
        name = self.name_ctrl.GetValue().strip()
        return (name, self.latitude, self.longitude)


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
        
        # Get accessible object
        accessible = self.text_ctrl.GetAccessible()
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
        super().__init__(parent, title="AccessiWeather", size=(800, 600))
        
        # Load config file if it exists
        self.config = self._load_config()
        
        # Initialize components
        self.api_client = self._initialize_api_client()
        self.notifier = WeatherNotifier()
        self.location_manager = None  # Will be set by main.py
        
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
        self.SetName("AccessiWeather")
        accessible = self.GetAccessible()
        if accessible:
            accessible.SetName("AccessiWeather")
            accessible.SetRole(wx.ACC_ROLE_WINDOW)
        
        # Initial load will be done after location_manager is set
    
    def _load_config(self):
        """Load configuration from file
        
        Returns:
            Dict containing configuration or empty dict if not found
        """
        # Config file locations to check
        config_paths = [
            os.path.join(os.getcwd(), "config.json"),  # Current directory
            os.path.expanduser("~/.accessiweather/config.json"),  # User home directory
            os.path.expanduser("~/.noaa_weather_app/config.json")  # Legacy location
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        logger.info(f"Loading config from {config_path}")
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error loading config from {config_path}: {str(e)}")
        
        # Default configuration if no file found
        logger.info("No config file found, using defaults")
        return {}
    
    def _initialize_api_client(self):
        """Initialize the NOAA API client with configuration
        
        Returns:
            Configured NoaaApiClient instance
        """
        # Default app name
        user_agent = "AccessiWeather"
        
        # Get API settings from config if available
        api_settings = self.config.get("api_settings", {})
        contact_info = api_settings.get("contact_info", None)
        
        # Initialize client with configured values
        return NoaaApiClient(user_agent=user_agent, contact_info=contact_info)
    
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
        accessible = self.forecast_text.GetAccessible()
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
        
        if self.location_manager is None:
            return
            
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
        if self.updating or self.location_manager is None:
            return
        
        # Get current location
        location = self.location_manager.get_current_location()
        if not location:
            self.SetStatusText("No location selected. Please add a location.")
            self.forecast_text.SetValue("No location selected. Please add a location.")
            return
        
        self.updating = True
        self.SetStatusText("Updating weather data...")
        
        # Clear any previous error messages
        self.forecast_text.SetValue("Loading forecast...")
        self.alerts_list.DeleteAllItems()
        
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
            logger.info(f"Fetching weather data for location: {name} ({lat}, {lon})")
            
            # Get forecast with detailed error handling
            try:
                logger.debug("Requesting forecast data...")
                start_time = time.time()
                forecast_data = self.api_client.get_forecast(lat, lon)
                logger.debug(f"Forecast data retrieved in {time.time() - start_time:.2f} seconds")
                wx.CallAfter(self._UpdateForecastDisplay, forecast_data)
            except Exception as e:
                logger.error(f"Failed to retrieve forecast: {str(e)}")
                error_message = f"Unable to retrieve forecast data: {str(e)}"
                wx.CallAfter(self.forecast_text.SetValue, error_message)
                wx.CallAfter(self.SetStatusText, f"Error: {str(e)}")
            
            # Get alerts with detailed error handling
            try:
                logger.debug("Requesting alerts data...")
                start_time = time.time()
                alerts_data = self.api_client.get_alerts(lat, lon)
                logger.debug(f"Alerts data retrieved in {time.time() - start_time:.2f} seconds")
                wx.CallAfter(self._UpdateAlertsDisplay, alerts_data)
            except Exception as e:
                logger.error(f"Failed to retrieve alerts: {str(e)}")
                # Just clear alerts list on error, we've already shown an error in the status bar
                wx.CallAfter(self.alerts_list.DeleteAllItems)
            
            # Update last update time
            self.last_update = time.time()
            wx.CallAfter(self.SetStatusText, f"Weather data updated at {time.strftime('%H:%M:%S')}")
            
        except Exception as e:
            error_msg = f"Error updating weather data: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"Traceback: {traceback.format_exc()}")
            wx.CallAfter(self.SetStatusText, error_msg)
            wx.CallAfter(self.forecast_text.SetValue, f"Error retrieving weather data:\n\n{str(e)}\n\nPlease check your internet connection and try again.")
        finally:
            self.updating = False
    
    def _UpdateForecastDisplay(self, forecast_data):
        """Update the forecast display with data
        
        Args:
            forecast_data: Dictionary with forecast data
        """
        try:
            self.current_forecast = forecast_data
            
            # Extract periods
            periods = forecast_data.get("properties", {}).get("periods", [])
            if not periods:
                logger.warning("No forecast periods found in data")
                logger.debug(f"Available properties: {list(forecast_data.get('properties', {}).keys())}")
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
            
            logger.debug(f"Processed {len(periods[:5])} forecast periods")
            self.forecast_text.SetValue(text)
        except Exception as e:
            logger.error(f"Error updating forecast display: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            self.forecast_text.SetValue(f"Error processing forecast data:\n\n{str(e)}")
    
    def _UpdateAlertsDisplay(self, alerts_data):
        """Update the alerts display with data
        
        Args:
            alerts_data: Dictionary with alerts data
        """
        try:
            # Process alerts
            logger.debug(f"Processing alerts data with {len(alerts_data.get('features', []))} features")
            self.current_alerts = self.notifier.process_alerts(alerts_data)
            
            # Clear and update list
            self.alerts_list.DeleteAllItems()
            
            if not self.current_alerts:
                logger.info("No active alerts for this location")
                index = self.alerts_list.InsertItem(0, "No active alerts")
                self.alerts_list.SetItem(index, 1, "")
                self.alerts_list.SetItem(index, 2, "")
                return
            
            for i, alert in enumerate(self.current_alerts):
                event_type = alert.get("event", "Unknown")
                severity = alert.get("severity", "Unknown")
                headline = alert.get("headline", "No details")
                
                index = self.alerts_list.InsertItem(i, event_type)
                self.alerts_list.SetItem(index, 1, severity)
                self.alerts_list.SetItem(index, 2, headline)
                
            logger.debug(f"Updated alerts list with {len(self.current_alerts)} items")
        except Exception as e:
            logger.error(f"Error updating alerts display: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            self.alerts_list.DeleteAllItems()
            index = self.alerts_list.InsertItem(0, "Error loading alerts")
            self.alerts_list.SetItem(index, 1, "Error")
            self.alerts_list.SetItem(index, 2, str(e)[:50])
    
    def OnLocationChange(self, event):
        """Handle location choice change
        
        Args:
            event: Choice event
        """
        selected = self.location_choice.GetStringSelection()
        if selected:
            logger.info(f"Location changed to: {selected}")
            success = self.location_manager.set_current_location(selected)
            if success:
                # Clear current forecast before fetching new data
                self.forecast_text.SetValue("Loading forecast...")
                self.alerts_list.DeleteAllItems()
                # Perform the update
                self.UpdateWeatherData()
            else:
                logger.error(f"Failed to set location: {selected}")
                self.SetStatusText(f"Error: Failed to set location {selected}")
    
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
