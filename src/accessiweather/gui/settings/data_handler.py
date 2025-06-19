"""
Settings data handling, validation, and persistence.

This module handles loading settings into UI controls, validating user input,
and retrieving settings data from the dialog for saving.
"""

import logging

import wx

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.utils.temperature_utils import TemperatureUnit

from .constants import (
    ALERT_RADIUS_KEY,
    AUTO_REFRESH_NATIONAL_KEY,
    AUTO_UPDATE_CHECK_KEY,
    CACHE_ENABLED_KEY,
    CACHE_TTL_KEY,
    DATA_SOURCE_AUTO,
    DATA_SOURCE_KEY,
    DATA_SOURCE_NWS,
    DATA_SOURCE_OPENMETEO,
    DEFAULT_AUTO_UPDATE_CHECK,
    DEFAULT_DATA_SOURCE,
    DEFAULT_TASKBAR_FORMAT,
    DEFAULT_TEMPERATURE_UNIT,
    DEFAULT_UPDATE_CHANNEL,
    DEFAULT_UPDATE_CHECK_INTERVAL,
    MIN_ALERT_RADIUS,
    MIN_CACHE_TTL,
    MIN_UPDATE_INTERVAL,
    MINIMIZE_TO_TRAY_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    SHOW_NATIONWIDE_KEY,
    TASKBAR_ICON_DYNAMIC_ENABLED_KEY,
    TASKBAR_ICON_TEXT_ENABLED_KEY,
    TASKBAR_ICON_TEXT_FORMAT_KEY,
    TEMPERATURE_UNIT_KEY,
    UPDATE_CHANNEL_KEY,
    UPDATE_CHECK_INTERVAL_KEY,
    UPDATE_INTERVAL_KEY,
)

logger = logging.getLogger(__name__)


class SettingsDataHandler:
    """Handles settings data loading, validation, and retrieval."""

    def __init__(self, dialog):
        self.dialog = dialog

    def load_settings(self, current_settings):
        """Load current settings into the UI controls."""
        try:
            # Load general settings
            update_interval = current_settings.get(UPDATE_INTERVAL_KEY, 10)
            alert_radius = current_settings.get(ALERT_RADIUS_KEY, 25)
            precise_alerts = current_settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
            show_nationwide = current_settings.get(SHOW_NATIONWIDE_KEY, True)
            auto_refresh_national = current_settings.get(AUTO_REFRESH_NATIONAL_KEY, True)

            # Load data source settings
            data_source = current_settings.get(DATA_SOURCE_KEY, DEFAULT_DATA_SOURCE)

            # Set data source dropdown
            if data_source == DATA_SOURCE_OPENMETEO:
                self.dialog.data_source_ctrl.SetSelection(1)  # Open-Meteo
            elif data_source == DATA_SOURCE_AUTO:
                self.dialog.data_source_ctrl.SetSelection(2)  # Automatic
            else:
                self.dialog.data_source_ctrl.SetSelection(0)  # NWS (default)

            self.dialog.update_interval_ctrl.SetValue(update_interval)
            self.dialog.alert_radius_ctrl.SetValue(alert_radius)
            self.dialog.precise_alerts_ctrl.SetValue(precise_alerts)
            self.dialog.show_nationwide_ctrl.SetValue(show_nationwide)
            self.dialog.auto_refresh_national_ctrl.SetValue(auto_refresh_national)

            # Load display settings
            taskbar_text_enabled = current_settings.get(TASKBAR_ICON_TEXT_ENABLED_KEY, False)
            taskbar_text_format = current_settings.get(
                TASKBAR_ICON_TEXT_FORMAT_KEY, DEFAULT_TASKBAR_FORMAT
            )
            taskbar_dynamic_enabled = current_settings.get(TASKBAR_ICON_DYNAMIC_ENABLED_KEY, True)

            self.dialog.taskbar_text_ctrl.SetValue(taskbar_text_enabled)
            self.dialog.taskbar_format_ctrl.SetValue(taskbar_text_format)
            self.dialog.dynamic_format_ctrl.SetValue(taskbar_dynamic_enabled)
            self.dialog.taskbar_format_ctrl.Enable(taskbar_text_enabled)
            self.dialog.dynamic_format_ctrl.Enable(taskbar_text_enabled)

            # Load advanced settings
            minimize_to_tray = current_settings.get(MINIMIZE_TO_TRAY_KEY, True)
            cache_enabled = current_settings.get(CACHE_ENABLED_KEY, True)
            cache_ttl = current_settings.get(CACHE_TTL_KEY, 300)

            self.dialog.minimize_to_tray_ctrl.SetValue(minimize_to_tray)
            self.dialog.cache_enabled_ctrl.SetValue(cache_enabled)
            self.dialog.cache_ttl_ctrl.SetValue(cache_ttl)

            # Load temperature unit setting
            temperature_unit = current_settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)
            # Set temperature unit dropdown
            if temperature_unit == TemperatureUnit.FAHRENHEIT.value:
                self.dialog.temp_unit_ctrl.SetSelection(0)  # Imperial (Fahrenheit)
            elif temperature_unit == TemperatureUnit.CELSIUS.value:
                self.dialog.temp_unit_ctrl.SetSelection(1)  # Metric (Celsius)
            elif temperature_unit == TemperatureUnit.BOTH.value:
                self.dialog.temp_unit_ctrl.SetSelection(2)  # Both
            else:
                # Default to Fahrenheit for unknown values
                self.dialog.temp_unit_ctrl.SetSelection(0)

            # Load update settings
            auto_update_check = current_settings.get(
                AUTO_UPDATE_CHECK_KEY, DEFAULT_AUTO_UPDATE_CHECK
            )
            update_check_interval = current_settings.get(
                UPDATE_CHECK_INTERVAL_KEY, DEFAULT_UPDATE_CHECK_INTERVAL
            )
            update_channel = current_settings.get(UPDATE_CHANNEL_KEY, DEFAULT_UPDATE_CHANNEL)

            self.dialog.auto_update_check_ctrl.SetValue(auto_update_check)
            self.dialog.update_check_interval_ctrl.SetValue(update_check_interval)
            self.dialog.update_check_interval_ctrl.Enable(auto_update_check)

            # Set update channel dropdown
            if update_channel == "dev":
                self.dialog.update_channel_ctrl.SetSelection(1)  # Development builds
            else:
                self.dialog.update_channel_ctrl.SetSelection(0)  # Stable releases (default)

            logger.debug("Settings loaded into dialog.")
        except Exception as e:
            logger.error(f"Error loading settings into dialog: {e}")
            wx.MessageBox(
                f"Error loading settings: {e}", "Error", wx.OK | wx.ICON_ERROR, self.dialog
            )

    def validate_settings(self):
        """Validate settings and return True if valid, False otherwise."""
        # Basic validation
        interval = self.dialog.update_interval_ctrl.GetValue()
        radius = self.dialog.alert_radius_ctrl.GetValue()
        cache_ttl = self.dialog.cache_ttl_ctrl.GetValue()

        if interval < MIN_UPDATE_INTERVAL:
            wx.MessageBox(
                f"Update interval must be at least {MIN_UPDATE_INTERVAL} minute.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self.dialog,
            )
            self.dialog.notebook.SetSelection(0)  # Switch to General tab
            self.dialog.update_interval_ctrl.SetFocus()
            return False

        if radius < MIN_ALERT_RADIUS:
            wx.MessageBox(
                f"Alert radius must be at least {MIN_ALERT_RADIUS} mile.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self.dialog,
            )
            self.dialog.notebook.SetSelection(0)  # Switch to General tab
            self.dialog.alert_radius_ctrl.SetFocus()
            return False

        if cache_ttl < MIN_CACHE_TTL:
            wx.MessageBox(
                f"Cache TTL must be at least {MIN_CACHE_TTL} seconds.",
                "Invalid Setting",
                wx.OK | wx.ICON_WARNING,
                self.dialog,
            )
            self.dialog.notebook.SetSelection(2)  # Switch to Advanced tab
            self.dialog.cache_ttl_ctrl.SetFocus()
            return False

        return True

    def get_settings(self):
        """
        Retrieve the modified settings from the UI controls.

        Returns:
            dict: A dictionary containing the updated settings.
        """
        # Determine data source
        selection = self.dialog.data_source_ctrl.GetSelection()
        if selection == 1:
            data_source = DATA_SOURCE_OPENMETEO
        elif selection == 2:
            data_source = DATA_SOURCE_AUTO
        else:
            data_source = DATA_SOURCE_NWS

        # Get temperature unit selection
        temp_unit_idx = self.dialog.temp_unit_ctrl.GetSelection()
        if temp_unit_idx == 0:
            temperature_unit = TemperatureUnit.FAHRENHEIT.value
        elif temp_unit_idx == 1:
            temperature_unit = TemperatureUnit.CELSIUS.value
        elif temp_unit_idx == 2:
            temperature_unit = TemperatureUnit.BOTH.value
        else:
            temperature_unit = DEFAULT_TEMPERATURE_UNIT

        # Validate taskbar format string if enabled
        taskbar_text_enabled = self.dialog.taskbar_text_ctrl.GetValue()
        taskbar_text_format = self.dialog.taskbar_format_ctrl.GetValue()
        taskbar_dynamic_enabled = self.dialog.dynamic_format_ctrl.GetValue()

        if taskbar_text_enabled and taskbar_text_format:
            # Validate the format string
            parser = FormatStringParser()
            is_valid, error = parser.validate_format_string(taskbar_text_format)
            if not is_valid:
                # If invalid, log the error but still save (will use default format)
                logger.warning(f"Invalid taskbar format string: {error}")

        return {
            # Data source setting
            DATA_SOURCE_KEY: data_source,
            # General settings
            UPDATE_INTERVAL_KEY: self.dialog.update_interval_ctrl.GetValue(),
            ALERT_RADIUS_KEY: self.dialog.alert_radius_ctrl.GetValue(),
            PRECISE_LOCATION_ALERTS_KEY: self.dialog.precise_alerts_ctrl.GetValue(),
            SHOW_NATIONWIDE_KEY: self.dialog.show_nationwide_ctrl.GetValue(),
            AUTO_REFRESH_NATIONAL_KEY: self.dialog.auto_refresh_national_ctrl.GetValue(),
            # Display settings
            TEMPERATURE_UNIT_KEY: temperature_unit,
            TASKBAR_ICON_TEXT_ENABLED_KEY: taskbar_text_enabled,
            TASKBAR_ICON_TEXT_FORMAT_KEY: taskbar_text_format,
            TASKBAR_ICON_DYNAMIC_ENABLED_KEY: taskbar_dynamic_enabled,
            # Advanced settings
            MINIMIZE_TO_TRAY_KEY: self.dialog.minimize_to_tray_ctrl.GetValue(),
            CACHE_ENABLED_KEY: self.dialog.cache_enabled_ctrl.GetValue(),
            CACHE_TTL_KEY: self.dialog.cache_ttl_ctrl.GetValue(),
            # Update settings
            AUTO_UPDATE_CHECK_KEY: self.dialog.auto_update_check_ctrl.GetValue(),
            UPDATE_CHECK_INTERVAL_KEY: self.dialog.update_check_interval_ctrl.GetValue(),
            UPDATE_CHANNEL_KEY: (
                "dev" if self.dialog.update_channel_ctrl.GetSelection() == 1 else "stable"
            ),
        }

    def get_api_settings(self):
        """
        Retrieve the API-specific settings from the UI controls.

        Returns:
            dict: A dictionary containing the updated API settings.
        """
        return {}

    def get_api_keys(self):
        """
        Retrieve the API keys from the UI controls.

        Returns:
            dict: A dictionary containing the updated API keys.
        """
        return {}
