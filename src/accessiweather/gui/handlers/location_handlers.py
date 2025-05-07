"""Location handlers for the WeatherApp class

This module contains the location-related handlers for the WeatherApp class.
"""

import logging

import wx

from accessiweather.location import NATIONWIDE_LOCATION_NAME

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppLocationHandlers(WeatherAppHandlerBase):
    """Location handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides location-related event handlers for the WeatherApp class.
    """

    def OnLocationChange(self, event):  # event is required by wx
        """Handle location change event from dropdown

        Args:
            event: Choice event
        """
        selected_index = self.location_choice.GetSelection()
        if selected_index == wx.NOT_FOUND:
            logger.warning("OnLocationChange called but no location selected")
            return

        selected_location_name = self.location_choice.GetString(selected_index)
        logger.info(f"OnLocationChange: Selected location: '{selected_location_name}'")

        # Check if this is the nationwide location
        if self.location_service.is_nationwide_location(selected_location_name):
            logger.info("OnLocationChange: Identified as Nationwide location")
            self._select_nationwide_location()  # This sets _in_nationwide_mode = True
            logger.info(
                f"OnLocationChange: After _select_nationwide_location, _in_nationwide_mode = {self._in_nationwide_mode}"
            )
        else:
            # This part is for regular locations
            logger.info("OnLocationChange: Identified as regular location")
            self.location_service.set_current_location(selected_location_name)
            self._in_nationwide_mode = False
            logger.info(f"OnLocationChange: _in_nationwide_mode set to {self._in_nationwide_mode}")

            # Enable remove button for regular locations
            if hasattr(self, "remove_btn"):
                self.remove_btn.Enable()

            # Enable discussion button if lat/lon are available
            if hasattr(self, "discussion_btn"):
                _, lat, lon = self.location_service.get_location(selected_location_name)
                if lat is not None and lon is not None:
                    self.discussion_btn.Enable()
                else:
                    self.discussion_btn.Disable()

        # Update weather data for the new location
        self.UpdateWeatherData()

        # Save current location to config
        self._save_config()

    def OnAddLocation(self, event):  # event is required by wx
        """Handle add location button click

        Args:
            event: Button event
        """
        # Use ShowLocationDialog from DialogHandlers
        result, location_data = self.ShowLocationDialog()

        if result == wx.ID_OK and location_data:
            name, lat, lon = location_data
            # Add location to service
            self.location_service.add_location(name, lat, lon)

            # Update dropdown and select new location
            self.UpdateLocationDropdown()
            self.location_choice.SetStringSelection(name)

            # Trigger location change to update weather data
            self.OnLocationChange(event)

    def OnRemoveLocation(self, event):  # event is required by wx
        """Handle remove location button click

        Args:
            event: Button event
        """
        # Get current location
        current_name = self.location_service.get_current_location_name()
        if not current_name:
            return

        # Don't allow removing the Nationwide location
        if self.location_service.is_nationwide_location(current_name):
            wx.MessageBox(
                "The Nationwide location cannot be removed.",
                "Cannot Remove Location",
                wx.OK | wx.ICON_ERROR,
            )
            return

        # Use ShowConfirmDialog from DialogHandlers
        confirmed = self.ShowConfirmDialog(
            f"Are you sure you want to remove {current_name}?",
            "Confirm Remove Location",
        )

        if confirmed:
            # Remove location from service
            self.location_service.remove_location(current_name)

            # Update dropdown
            self.UpdateLocationDropdown()

            # Update weather data for new selection
            self.UpdateWeatherData()

    def UpdateLocationDropdown(self):
        """Update the location dropdown with current locations"""
        # Get all location names from the service
        names = (
            self.location_service.get_all_locations()
        )  # Changed from get_all_location_names to get_all_locations

        # Clear and update the choice control
        self.location_choice.Clear()
        self.location_choice.Append(names)

        # Get current selection name
        current_selection_name = self.location_service.get_current_location_name()

        # Set selection if we have one
        if current_selection_name and current_selection_name in names:
            logger.info(f"UpdateLocationDropdown: Setting selection to '{current_selection_name}'")
            self.location_choice.SetStringSelection(current_selection_name)
            # Manually trigger the logic that OnLocationChange would handle for the initial load
            # This avoids redundant UpdateWeatherData calls if OnLocationChange also calls it.
            if self.location_service.is_nationwide_location(current_selection_name):
                logger.info("UpdateLocationDropdown: Identified as Nationwide location")
                self._select_nationwide_location()  # Sets _in_nationwide_mode = True
                logger.info(
                    f"UpdateLocationDropdown: After _select_nationwide_location, _in_nationwide_mode = {self._in_nationwide_mode}"
                )
            else:
                logger.info("UpdateLocationDropdown: Identified as regular location")
                self._in_nationwide_mode = False
                logger.info(
                    f"UpdateLocationDropdown: _in_nationwide_mode set to {self._in_nationwide_mode}"
                )
                # For regular locations, ensure remove button is enabled if a location is selected
                if hasattr(self, "remove_btn"):
                    self.remove_btn.Enable()

    def _select_nationwide_location(self):
        """Select the Nationwide location and update UI accordingly."""
        logger.info("_select_nationwide_location: Setting nationwide location")
        self.location_service.set_current_location(
            NATIONWIDE_LOCATION_NAME
        )  # Changed from set_current_location_to_nationwide
        self._in_nationwide_mode = True
        logger.info(
            f"_select_nationwide_location: _in_nationwide_mode set to {self._in_nationwide_mode}"
        )

        # Disable remove button for nationwide location
        if hasattr(self, "remove_btn"):
            self.remove_btn.Disable()

        # Enable discussion button for nationwide location
        if hasattr(self, "discussion_btn"):
            self.discussion_btn.Enable()
