"""Main application window for NOAA Weather App

This module provides the main application window and integrates all components.
"""

import wx
import os
import json
import time
import logging
import threading
import requests
import importlib
import sys

# Special import approach that allows for monkeypatching in tests
# Look for these classes in noaa_weather_app.gui first (for tests)
# If not found there, import them from their original modules

# Define what we need to import
to_import = {
    'NoaaApiClient': 'noaa_weather_app.api_client',
    'WeatherNotifier': 'noaa_weather_app.notifications',
    'LocationManager': 'noaa_weather_app.location',
    'GeocodingService': 'noaa_weather_app.geocoding'
}

# Try to import from gui module first (for test patching)
for name, original_module in to_import.items():
    try:
        # First try to get it from gui module (patched version in tests)
        gui_module = importlib.import_module('noaa_weather_app.gui')
        globals()[name] = getattr(gui_module, name)
    except (ImportError, AttributeError):
        # If not available in gui, import from original source
        module = importlib.import_module(original_module)
        globals()[name] = getattr(module, name)

# Import local modules
from .dialogs import LocationDialog, WeatherDiscussionDialog
from .ui_components import (
    AccessibleStaticText,
    AccessibleTextCtrl,
    AccessibleChoice,
    AccessibleButton,
    AccessibleListCtrl
)
from .async_fetchers import ForecastFetcher, AlertsFetcher, DiscussionFetcher

# Logger
logger = logging.getLogger(__name__)

# Constants
UPDATE_INTERVAL = 1800  # 30 minutes in seconds
CONFIG_PATH = os.path.expanduser("~/.noaa_weather_app/config.json")


class WeatherApp(wx.Frame):
    """Main application window"""
    
    def __init__(self, parent=None, api_client_class=None, notifier_class=None, location_manager_class=None, config_path=None):
        """Initialize the weather app
        
        Args:
            parent: Parent window
            api_client_class: Class to use for API client (for testing)
            notifier_class: Class to use for notifier (for testing)
            location_manager_class: Class to use for location manager (for testing)
            config_path: Custom path to config file (for testing)
        """
        super().__init__(parent, title="AccessiWeather", size=(800, 600))
        
        # Set component classes (used for dependency injection in tests)
        self._api_client_class = api_client_class or NoaaApiClient
        self._notifier_class = notifier_class or WeatherNotifier
        self._location_manager_class = location_manager_class or LocationManager
        self._config_path = config_path or CONFIG_PATH
        
        # Load config file if it exists
        self.config = self._load_config()
        
        # Initialize components
        self.api_client = self._initialize_api_client()
        self.notifier = self._notifier_class()
        
        # Initialize location manager
        # In the real app this is set externally, but for tests we need to initialize it here
        try:
            self.location_manager = self._location_manager_class()
            # Initialize with saved locations from config
            locations = self.config.get("locations", {})
            current = self.config.get("current")
            if locations:
                self.location_manager.set_locations(locations, current)
        except Exception as e:
            # This is primarily to support tests that mock LocationManager
            logger.warning(f"Could not initialize location manager: {e}")
            self.location_manager = None
        
        # Initialize async fetchers
        self.forecast_fetcher = ForecastFetcher(self.api_client)
        self.alerts_fetcher = AlertsFetcher(self.api_client)
        self.discussion_fetcher = DiscussionFetcher(self.api_client)
        
        # State variables
        self.current_forecast = None
        self.current_alerts = []
        self.updating = False
        
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
        
        # Test hooks for async tests
        self._testing_forecast_callback = None
        self._testing_forecast_error_callback = None
        self._testing_alerts_callback = None
        self._testing_alerts_error_callback = None
    
    def _load_config(self):
        """Load configuration from file
        
        Returns:
            Dict containing configuration or empty dict if not found
        """
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {str(e)}")
        
        # Return default config
        return {
            "locations": {},
            "current": None,
            "settings": {"update_interval_minutes": 30},
            "api_settings": {}
        }
    
    def _initialize_api_client(self):
        """Initialize the NOAA API client with configuration
        
        Returns:
            Configured NoaaApiClient instance
        """
        # Get API settings from config
        api_settings = self.config.get("api_settings", {})
        
        # Create API client with settings
        return self._api_client_class(
            user_agent="AccessiWeather",
            contact_info=api_settings.get("contact_info")
        )
    
    def InitUI(self):
        """Initialize the user interface"""
        # Create main panel
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Location controls
        location_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Location label
        location_label = AccessibleStaticText(panel, label="Location:")
        location_sizer.Add(location_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        
        # Location dropdown
        self.location_choice = AccessibleChoice(panel, choices=[], label="Location Selection")
        location_sizer.Add(self.location_choice, 1, wx.ALL | wx.EXPAND, 5)
        
        # Location buttons
        self.add_btn = AccessibleButton(panel, wx.ID_ANY, "Add")
        self.remove_btn = AccessibleButton(panel, wx.ID_ANY, "Remove")
        self.refresh_btn = AccessibleButton(panel, wx.ID_ANY, "Refresh")
        
        location_sizer.Add(self.add_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.remove_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(location_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Forecast panel
        forecast_label = AccessibleStaticText(panel, label="Forecast:")
        main_sizer.Add(forecast_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        self.forecast_text = AccessibleTextCtrl(
            panel,
            value="Select a location to view the forecast",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 200),
            label="Forecast Content"
        )
        main_sizer.Add(self.forecast_text, 1, wx.ALL | wx.EXPAND, 10)
        
        # Forecast discussion button
        self.discussion_btn = AccessibleButton(panel, wx.ID_ANY, "View Forecast Discussion")
        main_sizer.Add(self.discussion_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        
        # Alerts section
        alerts_label = AccessibleStaticText(panel, label="Weather Alerts:")
        main_sizer.Add(alerts_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        self.alerts_list = AccessibleListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            label="Weather Alerts List",
            size=(-1, 150)
        )
        
        # Set up columns
        self.alerts_list.InsertColumn(0, "Alert Type")
        self.alerts_list.InsertColumn(1, "Severity")
        self.alerts_list.InsertColumn(2, "Headline")
        self.alerts_list.SetColumnWidth(0, 150)
        self.alerts_list.SetColumnWidth(1, 100)
        self.alerts_list.SetColumnWidth(2, 500)
        
        main_sizer.Add(self.alerts_list, 0, wx.ALL | wx.EXPAND, 10)
        
        # Alert details button
        self.alert_btn = AccessibleButton(panel, wx.ID_ANY, "View Alert Details")
        main_sizer.Add(self.alert_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        
        # Set panel sizer
        panel.SetSizer(main_sizer)
        
        # Bind events
        self.Bind(wx.EVT_CHOICE, self.OnLocationChange, self.location_choice)
        self.Bind(wx.EVT_BUTTON, self.OnAddLocation, self.add_btn)
        self.Bind(wx.EVT_BUTTON, self.OnRemoveLocation, self.remove_btn)
        self.Bind(wx.EVT_BUTTON, self.OnRefresh, self.refresh_btn)
        self.Bind(wx.EVT_BUTTON, self.OnViewDiscussion, self.discussion_btn)
        self.Bind(wx.EVT_BUTTON, self.OnViewAlert, self.alert_btn)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnAlertActivated, self.alerts_list)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
    
    def OnKeyDown(self, event):
        """Handle key down events for accessibility
        
        Args:
            event: Key event
        """
        # Handle key events for accessibility
        # For example, F5 to refresh
        if event.GetKeyCode() == wx.WXK_F5:
            self.OnRefresh(event)
        else:
            event.Skip()
    
    def UpdateLocationDropdown(self):
        """Update the location dropdown with saved locations"""
        if self.location_manager is None:
            return
        
        # Get all locations
        locations = self.location_manager.get_all_locations()
        
        # Clear and repopulate dropdown
        self.location_choice.Clear()
        for location in locations:
            self.location_choice.Append(location)
        
        # Select current location
        current = self.location_manager.get_current_location_name()
        if current and current in locations:
            self.location_choice.SetStringSelection(current)
    
    def UpdateWeatherData(self):
        """Update weather data in a separate thread"""
        # Even if updating is true, we still want to proceed if this is a location change
        # This is to ensure that location changes always trigger a data refresh
        
        if self.location_manager is None:
            return
        
        # Get current location
        location = self.location_manager.get_current_location()
        if location is None:
            self.SetStatusText("No location selected")
            return
        
        # Always reset updating flag to ensure we can fetch for a new location
        # This is critical for location changes to work properly
        self.updating = True
        self._FetchWeatherData(location)
    
    def _FetchWeatherData(self, location):
        """Fetch weather data from NOAA API
        
        Args:
            location: Tuple of (name, lat, lon)
        """
        name, lat, lon = location
        self.SetStatusText(f"Updating weather data for {name}...")
        
        # Start forecast fetching thread
        self.forecast_fetcher.fetch(
            lat,
            lon,
            on_success=self._on_forecast_fetched,
            on_error=self._on_forecast_error
        )
        
        # Start alerts fetching thread
        self.alerts_fetcher.fetch(
            lat,
            lon,
            on_success=self._on_alerts_fetched,
            on_error=self._on_alerts_error
        )
    
    def _on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread
        
        Args:
            forecast_data: Dictionary with forecast data
        """
        # Save forecast data
        self.current_forecast = forecast_data
        
        # Update display
        self._UpdateForecastDisplay(forecast_data)
        
        # Update timestamp
        self.last_update = time.time()
        
        # Update status
        self.SetStatusText("Ready")
        
        # Reset updating flag when both forecast and alerts are complete
        if not getattr(self.alerts_fetcher, 'thread', None) or not self.alerts_fetcher.thread.is_alive():
            self.updating = False
        
        # Notify testing framework if hook is set
        if self._testing_forecast_callback:
            self._testing_forecast_callback(forecast_data)
    
    def _on_forecast_error(self, error_message):
        """Handle errors during forecast fetching
        
        Args:
            error_message: Error message
        """
        # Update status
        self.SetStatusText("Error fetching forecast")
        
        # Show error in forecast display
        self.forecast_text.SetValue(error_message)
        
        # Reset updating flag when both forecast and alerts are complete
        if not getattr(self.alerts_fetcher, 'thread', None) or not self.alerts_fetcher.thread.is_alive():
            self.updating = False
        
        # Notify testing framework if hook is set
        if self._testing_forecast_error_callback:
            self._testing_forecast_error_callback(error_message)
    
    def _on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread
        
        Args:
            alerts_data: Dictionary with alerts data
        """
        # Update alerts display
        self._UpdateAlertsDisplay(alerts_data)
        
        # Update timestamp
        self.last_update = time.time()
        
        # Reset updating flag when both forecast and alerts are complete
        if not getattr(self.forecast_fetcher, 'thread', None) or not self.forecast_fetcher.thread.is_alive():
            self.updating = False
        
        # Update status
        self.SetStatusText("Ready")
        
        # Notify testing framework if hook is set
        if self._testing_alerts_callback:
            self._testing_alerts_callback(alerts_data)
    
    def _on_alerts_error(self, error_message):
        """Handle errors during alerts fetching
        
        Args:
            error_message: Error message
        """
        # Update status
        self.SetStatusText("Error fetching alerts")
        
        # Clear alerts list
        self.alerts_list.DeleteAllItems()
        self.current_alerts = []
        
        # Reset updating flag when both forecast and alerts are complete
        if not getattr(self.forecast_fetcher, 'thread', None) or not self.forecast_fetcher.thread.is_alive():
            self.updating = False
        
        # Notify testing framework if hook is set
        if self._testing_alerts_error_callback:
            self._testing_alerts_error_callback(error_message)
    
    def _UpdateForecastDisplay(self, forecast_data):
        """Update the forecast display with data
        
        Args:
            forecast_data: Dictionary with forecast data
        """
        if not forecast_data or "properties" not in forecast_data:
            self.forecast_text.SetValue("No forecast data available")
            return
        
        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            self.forecast_text.SetValue("No forecast periods available")
            return
        
        # Format forecast text
        text = ""
        for period in periods[:5]:  # Show first 5 periods
            name = period.get("name", "Unknown")
            temp = period.get("temperature", "?")
            unit = period.get("temperatureUnit", "F")
            details = period.get("detailedForecast", "No details available")
            
            text += f"{name}: {temp}°{unit}\n"
            text += f"{details}\n\n"
        
        self.forecast_text.SetValue(text)
    
    def _UpdateAlertsDisplay(self, alerts_data):
        """Update the alerts display with data
        
        Args:
            alerts_data: Dictionary with alerts data
        """
        # Clear current alerts
        self.alerts_list.DeleteAllItems()
        self.current_alerts = []
        
        if not alerts_data or "features" not in alerts_data:
            return
        
        features = alerts_data.get("features", [])
        for feature in features:
            props = feature.get("properties", {})
            event = props.get("event", "Unknown")
            severity = props.get("severity", "Unknown")
            headline = props.get("headline", "No headline available")
            
            # Add to alerts list
            index = self.alerts_list.InsertItem(self.alerts_list.GetItemCount(), event)
            self.alerts_list.SetItem(index, 1, severity)
            self.alerts_list.SetItem(index, 2, headline)
            
            # Save alert data for details view
            self.current_alerts.append(props)
        
        # If there are alerts, notify the user
        if features:
            self.notifier.notify_alerts(len(features))
    
    def OnLocationChange(self, event):
        """Handle location choice change
        
        Args:
            event: Choice event
        """
        if self.location_manager is None:
            return
        
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            return
        
        # Set current location
        self.location_manager.set_current_location(selected)
        
        # Update weather data
        self.UpdateWeatherData()
    
    def OnAddLocation(self, event):
        """Handle add location button
        
        Args:
            event: Button event
        """
        if self.location_manager is None:
            wx.MessageBox("Location manager not initialized", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Show location dialog
        dialog = LocationDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            name, lat, lon = dialog.GetValues()
            if name and lat is not None and lon is not None:
                # Add location
                self.location_manager.add_location(name, lat, lon)
                
                # Update dropdown
                self.UpdateLocationDropdown()
                
                # Set as current location
                self.location_choice.SetStringSelection(name)
                self.location_manager.set_current_location(name)
                
                # Update weather data
                self.UpdateWeatherData()
        
        dialog.Destroy()
    
    def OnRemoveLocation(self, event):
        """Handle remove location button
        
        Args:
            event: Button event
        """
        if self.location_manager is None:
            return
        
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            wx.MessageBox("Please select a location to remove", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Confirm deletion
        dlg = wx.MessageDialog(
            self,
            f"Are you sure you want to remove {selected}?",
            "Confirm Removal",
            wx.YES_NO | wx.ICON_QUESTION
        )
        result = dlg.ShowModal()
        dlg.Destroy()
        
        if result != wx.ID_YES:
            return
        
        # Remove location
        self.location_manager.remove_location(selected)
        
        # Update dropdown
        self.UpdateLocationDropdown()
        
        # Update weather data
        if self.location_choice.GetCount() > 0:
            self.location_choice.SetSelection(0)
            new_selected = self.location_choice.GetStringSelection()
            if new_selected:
                self.location_manager.set_current_location(new_selected)
                self.UpdateWeatherData()
    
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
        if self.location_manager is None:
            return
        
        # Get current location
        location = self.location_manager.get_current_location()
        if location is None:
            wx.MessageBox("Please select a location first", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        name, lat, lon = location
        
        # Disable button while loading
        self.discussion_btn.Disable()
        
        # Show loading dialog
        loading_dialog = wx.ProgressDialog(
            "Loading Discussion",
            f"Fetching forecast discussion for {name}...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        loading_dialog.Pulse()
        
        # Fetch discussion in separate thread
        self.discussion_fetcher.fetch(
            lat,
            lon,
            on_success=self._on_discussion_fetched,
            on_error=self._on_discussion_error,
            additional_data=(name, loading_dialog)
        )
    
    def _on_discussion_fetched(self, discussion_text, name, loading_dialog):
        """Handle the fetched discussion in the main thread
        
        Args:
            discussion_text: The fetched discussion text
            name: Location name
            loading_dialog: Loading dialog reference
        """
        try:
            # Close loading dialog
            if loading_dialog:
                loading_dialog.Destroy()
            
            # Re-enable the button
            self.discussion_btn.Enable()
            
            # Show discussion dialog
            dialog = WeatherDiscussionDialog(self, title=f"Weather Discussion for {name}", text=discussion_text)
            dialog.ShowModal()
            dialog.Destroy()
            
        finally:
            self.SetStatusText("Ready")
    
    def _on_discussion_error(self, error_message, loading_dialog):
        """Handle errors during discussion fetching
        
        Args:
            error_message: Error message
            loading_dialog: Loading dialog reference
        """
        try:
            # Close loading dialog
            if loading_dialog:
                loading_dialog.Destroy()
            
            # Re-enable the button
            self.discussion_btn.Enable()
            
            # Show error message
            wx.MessageBox(f"Error fetching discussion: {error_message}", "Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.SetStatusText("Ready")
        
    def OnViewAlert(self, event):
        """Handle view alert button
        
        Args:
            event: Button event
        """
        # Get selected alert
        selected = self.alerts_list.GetFocusedItem()
        if selected < 0:
            wx.MessageBox("Please select an alert to view", "Error", wx.OK | wx.ICON_ERROR)
            return
        
        # Get alert details
        alert = self.current_alerts[selected]
        details = alert.get("description", "No details available")
        
        # Show alert details dialog
        dialog = WeatherDiscussionDialog(self, title="Alert Details", text=details)
        dialog.ShowModal()
        dialog.Destroy()
    
    def OnAlertActivated(self, event):
        """Handle alert list item activation
        
        Args:
            event: List item event
        """
        self.OnViewAlert(event)
    
    def OnClose(self, event):
        """Handle close event
        
        Args:
            event: Close event
        """
        self.Destroy()
    
    def OnTimer(self, event):
        """Handle timer event for periodic updates
        
        Args:
            event: Timer event
        """
        # Check if we need to update
        if time.time() - self.last_update > UPDATE_INTERVAL and not self.updating:
            self.UpdateWeatherData()
