"""Settings handlers for the WeatherApp class

This module contains the settings-related handlers for the WeatherApp class.
"""

import logging

import wx

from ..settings_dialog import (
    API_CONTACT_KEY,
    CACHE_ENABLED_KEY,
    CACHE_TTL_KEY,
    MINIMIZE_ON_STARTUP_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    SHOW_NATIONWIDE_KEY,
)
from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppSettingsHandlers(WeatherAppHandlerBase):
    """Settings handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides settings-related event handlers for the WeatherApp class.
    """

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

        # Use ShowSettingsDialog from DialogHandlers
        result, updated_settings, updated_api_settings = self.ShowSettingsDialog(combined_settings)

        if result == wx.ID_OK and updated_settings and updated_api_settings:
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

            # If show nationwide setting changed, update location manager
            old_show_nationwide = settings.get(SHOW_NATIONWIDE_KEY, True)
            new_show_nationwide = updated_settings.get(SHOW_NATIONWIDE_KEY, True)
            if old_show_nationwide != new_show_nationwide:
                logger.info(
                    f"Show nationwide setting changed from {old_show_nationwide} "
                    f"to {new_show_nationwide}"
                )
                # Update the location manager with the new setting
                self.location_service.location_manager.set_show_nationwide(new_show_nationwide)
                # Update the location dropdown to reflect the change
                self.UpdateLocationDropdown()

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

            # If minimize on startup setting changed, log it
            old_minimize_setting = settings.get(MINIMIZE_ON_STARTUP_KEY, False)
            new_minimize_setting = updated_settings.get(MINIMIZE_ON_STARTUP_KEY, False)
            if old_minimize_setting != new_minimize_setting:
                logger.info(
                    f"Minimize on startup setting changed from {old_minimize_setting} "
                    f"to {new_minimize_setting}"
                )

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

    def _check_api_contact_configured(self):
        """Check if API contact information is configured and prompt if not"""
        # Check if api_settings section exists
        if "api_settings" not in self.config:
            logger.warning("API settings section missing from config")
            self.config["api_settings"] = {}

        # Check if api_contact is set
        api_contact = self.config.get("api_settings", {}).get(API_CONTACT_KEY, "")
        if not api_contact:
            logger.warning("API contact information not configured")

            # Use ShowConfirmDialog from DialogHandlers
            confirmed = self.ShowConfirmDialog(
                "API contact information is required for NOAA API access. "
                "Would you like to configure it now?",
                "API Configuration Required",
            )

            if confirmed:
                # Open settings dialog
                self.OnSettings(None)
