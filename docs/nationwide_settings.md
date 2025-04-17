# Nationwide Settings Feature

This document outlines the implementation plan for adding settings to hide/show the Nationwide view in the AccessiWeather application.

## Overview

The Nationwide view cannot be removed like a regular location, but users should be able to hide it from the locations dropdown if they don't want to use it. This feature will add a setting to control the visibility of the Nationwide location.

## Implementation Plan

### 1. Add Setting Key Constant

Add a constant for the Nationwide visibility setting in `settings_dialog.py`:

```python
# Constants for settings keys
UPDATE_INTERVAL_KEY = "update_interval_minutes"
ALERT_RADIUS_KEY = "alert_radius_miles"
PRECISE_LOCATION_ALERTS_KEY = "precise_location_alerts"
CACHE_ENABLED_KEY = "cache_enabled"
CACHE_TTL_KEY = "cache_ttl"
SHOW_NATIONWIDE_KEY = "show_nationwide"  # New setting
```

### 2. Update Settings Dialog

Update the `SettingsDialog` class to include a checkbox for showing/hiding the Nationwide view:

```python
def _init_general_tab(self):
    """Initialize the General tab controls."""
    panel = self.general_panel
    sizer = wx.BoxSizer(wx.VERTICAL)

    # --- Input Fields ---
    grid_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=5)
    grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

    # API Contact Info
    api_contact_label = wx.StaticText(panel, label="API Contact Info:")
    self.api_contact_ctrl = wx.TextCtrl(panel, name="API Contact")
    tooltip_api = (
        "Your email or website URL for NOAA API identification. "
        "This helps NOAA contact you if your app is causing issues."
    )
    self.api_contact_ctrl.SetToolTip(tooltip_api)
    grid_sizer.Add(api_contact_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
    grid_sizer.Add(self.api_contact_ctrl, 0, wx.EXPAND | wx.ALL, 5)

    # Update Interval
    update_interval_label = wx.StaticText(panel, label="Update Interval (minutes):")
    self.update_interval_ctrl = wx.SpinCtrl(
        panel, min=5, max=120, initial=30, name="Update Interval"
    )
    tooltip_interval = "How often to automatically update weather data."
    self.update_interval_ctrl.SetToolTip(tooltip_interval)
    grid_sizer.Add(update_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
    # Don't expand spin control
    grid_sizer.Add(self.update_interval_ctrl, 0, wx.ALL, 5)

    # Alert Radius
    alert_radius_label = wx.StaticText(panel, label="Alert Radius (miles):")
    self.alert_radius_ctrl = wx.SpinCtrl(
        panel, min=5, max=100, initial=25, name="Alert Radius"
    )
    tooltip_radius = (
        "Radius in miles to search for alerts when precise location is not available."
    )
    self.alert_radius_ctrl.SetToolTip(tooltip_radius)
    grid_sizer.Add(alert_radius_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
    # Don't expand spin control
    grid_sizer.Add(self.alert_radius_ctrl, 0, wx.ALL, 5)

    # Precise Location Alerts Toggle
    precise_alerts_label = "Use precise location for alerts"
    self.precise_alerts_ctrl = wx.CheckBox(
        panel, label=precise_alerts_label, name="Precise Location Alerts"
    )
    tooltip_precise = (
        "When checked, only shows alerts for your specific location. "
        "When unchecked, shows all alerts for your state."
    )
    self.precise_alerts_ctrl.SetToolTip(tooltip_precise)
    # Add a spacer in the first column
    grid_sizer.Add((1, 1), 0, wx.ALL, 5)
    grid_sizer.Add(self.precise_alerts_ctrl, 0, wx.ALL, 5)
    
    # Show Nationwide Toggle
    show_nationwide_label = "Show Nationwide location"
    self.show_nationwide_ctrl = wx.CheckBox(
        panel, label=show_nationwide_label, name="Show Nationwide"
    )
    tooltip_nationwide = (
        "When checked, shows the Nationwide location in the locations dropdown. "
        "When unchecked, hides the Nationwide location."
    )
    self.show_nationwide_ctrl.SetToolTip(tooltip_nationwide)
    # Add a spacer in the first column
    grid_sizer.Add((1, 1), 0, wx.ALL, 5)
    grid_sizer.Add(self.show_nationwide_ctrl, 0, wx.ALL, 5)

    sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 10)
    panel.SetSizer(sizer)
```

Update the `_load_settings` method to load the Nationwide visibility setting:

```python
def _load_settings(self):
    """Load current settings into the UI controls."""
    try:
        # Load general settings
        api_contact = self.current_settings.get(API_CONTACT_KEY, "")
        update_interval = self.current_settings.get(UPDATE_INTERVAL_KEY, 30)
        alert_radius = self.current_settings.get(ALERT_RADIUS_KEY, 25)
        precise_alerts = self.current_settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
        show_nationwide = self.current_settings.get(SHOW_NATIONWIDE_KEY, True)  # Default to True

        self.api_contact_ctrl.SetValue(api_contact)
        self.update_interval_ctrl.SetValue(update_interval)
        self.alert_radius_ctrl.SetValue(alert_radius)
        self.precise_alerts_ctrl.SetValue(precise_alerts)
        self.show_nationwide_ctrl.SetValue(show_nationwide)

        # Load advanced settings
        cache_enabled = self.current_settings.get(CACHE_ENABLED_KEY, True)
        cache_ttl = self.current_settings.get(CACHE_TTL_KEY, 300)

        self.cache_enabled_ctrl.SetValue(cache_enabled)
        self.cache_ttl_ctrl.SetValue(cache_ttl)
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
```

Update the `get_settings` method to include the Nationwide visibility setting:

```python
def get_settings(self):
    """
    Retrieve the modified settings from the UI controls.

    Should only be called after the dialog returns wx.ID_OK.

    Returns:
        dict: A dictionary containing the updated settings.
    """
    return {
        # General settings
        UPDATE_INTERVAL_KEY: self.update_interval_ctrl.GetValue(),
        ALERT_RADIUS_KEY: self.alert_radius_ctrl.GetValue(),
        PRECISE_LOCATION_ALERTS_KEY: self.precise_alerts_ctrl.GetValue(),
        SHOW_NATIONWIDE_KEY: self.show_nationwide_ctrl.GetValue(),  # New setting
        # Advanced settings
        CACHE_ENABLED_KEY: self.cache_enabled_ctrl.GetValue(),
        CACHE_TTL_KEY: self.cache_ttl_ctrl.GetValue(),
    }
```

### 3. Update Location Manager

Update the `LocationManager` class to respect the Nationwide visibility setting:

```python
def get_all_locations(self) -> List[str]:
    """Get all saved location names

    Returns:
        List of location names
    """
    # Get all locations
    locations = list(self.saved_locations.keys())
    
    # Check if Nationwide should be hidden
    show_nationwide = self.config.get("settings", {}).get(SHOW_NATIONWIDE_KEY, True)
    if not show_nationwide and NATIONWIDE_LOCATION_NAME in locations:
        # Remove Nationwide from the list but keep it in saved_locations
        locations.remove(NATIONWIDE_LOCATION_NAME)
        
    return locations
```

Add a method to update the Nationwide visibility setting:

```python
def set_nationwide_visibility(self, show: bool) -> None:
    """Set the visibility of the Nationwide location
    
    Args:
        show: Whether to show the Nationwide location
    """
    # Update the setting in the config
    if "settings" not in self.config:
        self.config["settings"] = {}
    self.config["settings"][SHOW_NATIONWIDE_KEY] = show
    
    # Save the config
    self._save_config()
```

### 4. Update Location Service

Update the `LocationService` class to handle the Nationwide visibility setting:

```python
def set_nationwide_visibility(self, show: bool) -> None:
    """Set the visibility of the Nationwide location
    
    Args:
        show: Whether to show the Nationwide location
    """
    self.location_manager.set_nationwide_visibility(show)
```

### 5. Update Weather App Handlers

Update the `OnSettings` method in both `WeatherAppHandlers` and `WeatherAppHandlersRefactored` classes to handle changes to the Nationwide visibility setting:

```python
def OnSettings(self, event):  # event is required by wx
    """Handle settings button click

    Args:
        event: Button event
    """
    # Get current settings
    settings = self.config.get("settings", {})
    api_settings = self.config.get("api_settings", {})

    # Combine settings and api_settings for the dialog
    combined_settings = settings.copy()
    combined_settings.update(api_settings)

    # Create settings dialog
    dialog = SettingsDialog(self, combined_settings)
    result = dialog.ShowModal()

    if result == wx.ID_OK:
        # Get updated settings
        updated_settings = dialog.get_settings()
        updated_api_settings = dialog.get_api_settings()

        # Check if Nationwide visibility changed
        old_show_nationwide = settings.get(SHOW_NATIONWIDE_KEY, True)
        new_show_nationwide = updated_settings.get(SHOW_NATIONWIDE_KEY, True)
        
        # Update config
        self.config["settings"] = updated_settings
        self.config["api_settings"] = updated_api_settings

        # Save config
        self._save_config()

        # Note: We can't update the contact info directly in the API client
        # as it doesn't have a setter method. The contact info will be used
        # the next time the app is started.

        # Update notifier settings
        # Note: Alert radius is stored in config and will be used
        # the next time alerts are fetched

        # If precise location setting changed, refresh alerts
        old_precise_setting = settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
        new_precise_setting = updated_settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
        if old_precise_setting != new_precise_setting:
            logger.info(
                f"Precise location setting changed from {old_precise_setting} "
                f"to {new_precise_setting}, refreshing alerts"
            )
            # Refresh weather data to apply new setting
            self.UpdateWeatherData()

        # If Nationwide visibility changed, update the location dropdown
        if old_show_nationwide != new_show_nationwide:
            logger.info(
                f"Nationwide visibility setting changed from {old_show_nationwide} "
                f"to {new_show_nationwide}, updating location dropdown"
            )
            # Update the location dropdown
            self.UpdateLocationDropdown()

        # If cache settings changed, update API client if possible
        old_cache_enabled = settings.get(CACHE_ENABLED_KEY, True)
        new_cache_enabled = updated_settings.get(CACHE_ENABLED_KEY, True)
        old_cache_ttl = settings.get(CACHE_TTL_KEY, 300)
        new_cache_ttl = updated_settings.get(CACHE_TTL_KEY, 300)

        if old_cache_enabled != new_cache_enabled or old_cache_ttl != new_cache_ttl:
            logger.info(
                f"Cache settings changed: enabled {old_cache_enabled} -> {new_cache_enabled}, "
                f"TTL {old_cache_ttl} -> {new_cache_ttl}"
            )
            # Note: We can't update the cache settings directly in the API client
            # as it doesn't have setter methods. The cache settings will be used
            # the next time the app is started.

    dialog.Destroy()
```

### 6. Update Default Config

Update the default config in both `WeatherApp` and `WeatherAppRefactored` classes to include the Nationwide visibility setting:

```python
def _load_config(self):
    """Load configuration from file

    Returns:
        Dict containing configuration or empty dict if not found
    """
    if os.path.exists(self._config_path):
        try:
            with open(self._config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")

    # Return default config structure
    return {
        "locations": {},
        "current": None,
        "settings": {
            UPDATE_INTERVAL_KEY: 30,
            ALERT_RADIUS_KEY: 25,
            PRECISE_LOCATION_ALERTS_KEY: True,  # Default to precise location alerts
            CACHE_ENABLED_KEY: True,  # Default to enabled caching
            CACHE_TTL_KEY: 300,  # Default to 5 minutes (300 seconds)
            SHOW_NATIONWIDE_KEY: True,  # Default to showing Nationwide location
        },
        "api_settings": {API_CONTACT_KEY: ""},  # Added default
    }
```

## Next Steps

After implementing the nationwide settings feature, all the required functionality for the Nationwide view will be complete. The next steps would be to:

1. Test all the features thoroughly
2. Fix any bugs or issues that arise during testing
3. Document the new features for users
