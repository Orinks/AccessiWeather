"""Dialog components for NOAA Weather App

This module provides dialog windows for user interaction.
"""

import wx
import logging
from noaa_weather_app.geocoding import GeocodingService

from .ui_components import (
    AccessibleStaticText,
    AccessibleTextCtrl,
    AccessibleButton
)

logger = logging.getLogger(__name__)


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
        try:
            # Validate inputs
            lat = float(self.lat_ctrl.GetValue())
            lon = float(self.lon_ctrl.GetValue())
            
            # Check range
            if lat < -90 or lat > 90:
                wx.MessageBox(
                    "Latitude must be between -90 and 90 degrees",
                    "Validation Error",
                    wx.OK | wx.ICON_ERROR
                )
                return
            
            if lon < -180 or lon > 180:
                wx.MessageBox(
                    "Longitude must be between -180 and 180 degrees",
                    "Validation Error",
                    wx.OK | wx.ICON_ERROR
                )
                return
                
            # Continue with default handler
            event.Skip()
            
        except ValueError:
            wx.MessageBox(
                "Please enter valid numbers for latitude and longitude",
                "Validation Error",
                wx.OK | wx.ICON_ERROR
            )
    
    def GetValues(self):
        """Get the dialog values
        
        Returns:
            Tuple of (latitude, longitude)
        """
        try:
            lat = float(self.lat_ctrl.GetValue())
            lon = float(self.lon_ctrl.GetValue())
            return lat, lon
        except ValueError:
            return None, None


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
            wx.MessageBox(
                "Please enter an address, city, or ZIP code to search",
                "Search Error",
                wx.OK | wx.ICON_ERROR
            )
            return
        
        # Search for location
        try:
            result = self.geocoding_service.geocode_address(query)
            if result:
                lat, lon, address = result
                self.latitude = lat
                self.longitude = lon
                self.result_text.SetValue(f"Found: {address}\nCoordinates: {lat}, {lon}")
                
                # Auto-populate name field if it's empty
                if not self.name_ctrl.GetValue().strip():
                    self.name_ctrl.SetValue(query)
            else:
                self.result_text.SetValue("No results found for the given address")
                self.latitude = None
                self.longitude = None
        except Exception as e:
            logger.error(f"Error during geocoding: {str(e)}")
            self.result_text.SetValue(f"Error: {str(e)}")
            self.latitude = None
            self.longitude = None
    
    def OnAdvanced(self, event):
        """Handle advanced button click to open manual lat/lon dialog
        
        Args:
            event: Button event
        """
        # Get current lat/lon if available
        current_lat = self.latitude
        current_lon = self.longitude
        
        # Create and show advanced dialog
        dialog = AdvancedLocationDialog(
            self,
            lat=current_lat,
            lon=current_lon
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            lat, lon = dialog.GetValues()
            if lat is not None and lon is not None:
                self.latitude = lat
                self.longitude = lon
                self.result_text.SetValue(f"Custom coordinates: {lat}, {lon}")
        
        dialog.Destroy()
    
    def OnOK(self, event):
        """Handle OK button event
        
        Args:
            event: Button event
        """
        # Validate inputs
        name = self.name_ctrl.GetValue().strip()
        if not name:
            wx.MessageBox(
                "Please enter a name for the location",
                "Validation Error",
                wx.OK | wx.ICON_ERROR
            )
            return
        
        if self.latitude is None or self.longitude is None:
            wx.MessageBox(
                "Please search for a location or enter coordinates manually",
                "Validation Error",
                wx.OK | wx.ICON_ERROR
            )
            return
        
        # Continue with default handler
        event.Skip()
    
    def GetValues(self):
        """Get the dialog values
        
        Returns:
            Tuple of (name, latitude, longitude)
        """
        return self.name_ctrl.GetValue().strip(), self.latitude, self.longitude


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
