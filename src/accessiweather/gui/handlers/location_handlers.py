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
                # Get coordinates using get_location_coordinates method
                coords = self.location_service.get_location_coordinates(selected_location_name)
                if coords is not None:
                    lat, lon = coords
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
        # Show a message box to confirm we're in the right method (only in debug mode)
        # Add debug print to check if debug_mode is set
        has_attr = hasattr(self, "debug_mode")
        debug_mode_value = getattr(self, "debug_mode", False)
        print(
            f"DEBUG CHECK: has debug_mode attribute: {has_attr}, debug_mode value: {debug_mode_value}"
        )

        if has_attr and debug_mode_value:
            wx.MessageBox(
                "Remove location button clicked",
                "Debug Info",
                wx.OK | wx.ICON_INFORMATION,
            )

        # Get current location
        current_name = self.location_service.get_current_location_name()
        logger.debug(f"OnRemoveLocation: Current location name: '{current_name}'")

        if not current_name:
            logger.warning("OnRemoveLocation: No current location to remove")
            # Show error message (not debug-specific)
            wx.MessageBox(
                "No current location to remove",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
            return

        # Don't allow removing the Nationwide location
        if self.location_service.is_nationwide_location(current_name):
            logger.info("OnRemoveLocation: Cannot remove Nationwide location")
            wx.MessageBox(
                "The Nationwide location cannot be removed.",
                "Cannot Remove Location",
                wx.OK | wx.ICON_ERROR,
            )
            return

        # Use ShowConfirmDialog from DialogHandlers
        logger.debug(f"OnRemoveLocation: Showing confirmation dialog for '{current_name}'")

        # Direct confirmation instead of using ShowConfirmDialog
        dialog = wx.MessageDialog(
            self,
            f"Are you sure you want to remove {current_name}?",
            "Confirm Remove Location",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        result = dialog.ShowModal()
        confirmed = result == wx.ID_YES
        dialog.Destroy()

        # Show the confirmation result (only in debug mode)
        # Add debug print to check if debug_mode is set
        has_attr = hasattr(self, "debug_mode")
        debug_mode_value = getattr(self, "debug_mode", False)
        print(
            f"DEBUG CHECK 2: has debug_mode attribute: {has_attr}, debug_mode value: {debug_mode_value}"
        )

        if has_attr and debug_mode_value:
            wx.MessageBox(
                f"Confirmation result: {confirmed}",
                "Debug Info",
                wx.OK | wx.ICON_INFORMATION,
            )

        logger.debug(f"OnRemoveLocation: Confirmation result: {confirmed}")

        if confirmed:
            # Get all locations before removal for comparison
            locations_before = self.location_service.get_all_locations()
            logger.debug(f"OnRemoveLocation: Locations before removal: {locations_before}")

            # Show locations before removal (only in debug mode)
            if hasattr(self, "debug_mode") and self.debug_mode:
                wx.MessageBox(
                    f"Locations before removal: {locations_before}",
                    "Debug Info",
                    wx.OK | wx.ICON_INFORMATION,
                )

            # Remove location from service
            result = self.location_service.remove_location(current_name)
            logger.debug(f"OnRemoveLocation: Remove location result: {result}")

            # Show removal result (only in debug mode)
            if hasattr(self, "debug_mode") and self.debug_mode:
                wx.MessageBox(
                    f"Remove location result: {result}",
                    "Debug Info",
                    wx.OK | wx.ICON_INFORMATION,
                )

            # Get all locations after removal for comparison
            locations_after = self.location_service.get_all_locations()
            logger.debug(f"OnRemoveLocation: Locations after removal: {locations_after}")

            # Show locations after removal (only in debug mode)
            if hasattr(self, "debug_mode") and self.debug_mode:
                wx.MessageBox(
                    f"Locations after removal: {locations_after}",
                    "Debug Info",
                    wx.OK | wx.ICON_INFORMATION,
                )

            # Verify the location was actually removed
            if current_name in locations_after:
                logger.error(f"OnRemoveLocation: Failed to remove location '{current_name}'")
                wx.MessageBox(
                    f"Failed to remove location '{current_name}'.",
                    "Error",
                    wx.OK | wx.ICON_ERROR,
                )
                return

            # Update dropdown
            logger.debug("OnRemoveLocation: Updating location dropdown")
            self.UpdateLocationDropdown()

            # Get the new current location after removal
            new_current_name = self.location_service.get_current_location_name()
            logger.info(
                f"OnRemoveLocation: New current location after removal: '{new_current_name}'"
            )

            # Show new current location (only in debug mode)
            if hasattr(self, "debug_mode") and self.debug_mode:
                wx.MessageBox(
                    f"New current location: '{new_current_name}'",
                    "Debug Info",
                    wx.OK | wx.ICON_INFORMATION,
                )

            if new_current_name:
                # Ensure the dropdown selection matches the new current location
                logger.debug(
                    f"OnRemoveLocation: Setting dropdown selection to '{new_current_name}'"
                )
                self.location_choice.SetStringSelection(new_current_name)

                # Verify the selection was set correctly
                selected_index = self.location_choice.GetSelection()
                if selected_index != wx.NOT_FOUND:
                    selected_name = self.location_choice.GetString(selected_index)
                    logger.debug(f"OnRemoveLocation: Selection verified as '{selected_name}'")
                else:
                    logger.warning("OnRemoveLocation: Failed to set selection in dropdown")

                # Explicitly trigger the location change event to update weather data
                # Create a dummy event to pass to OnLocationChange
                logger.debug("OnRemoveLocation: Creating dummy event for OnLocationChange")
                dummy_event = wx.CommandEvent(wx.EVT_CHOICE.typeId, self.location_choice.GetId())
                self.OnLocationChange(dummy_event)
            else:
                # If no location is available, just update the weather data display
                logger.debug(
                    "OnRemoveLocation: No current location, updating weather data directly"
                )
                self.UpdateWeatherData()

    def UpdateLocationDropdown(self):
        """Update the location dropdown with current locations"""
        # Get all location names from the service
        names = (
            self.location_service.get_all_locations()
        )  # Changed from get_all_location_names to get_all_locations

        # Log the state before updating
        logger.debug(
            f"UpdateLocationDropdown: Current dropdown items: {[self.location_choice.GetString(i) for i in range(self.location_choice.GetCount())]}"
        )
        logger.debug(
            f"UpdateLocationDropdown: Current selection index: {self.location_choice.GetSelection()}"
        )

        # Clear and update the choice control
        self.location_choice.Clear()
        self.location_choice.Append(names)

        # Log after clearing and appending
        logger.debug(
            f"UpdateLocationDropdown: After Clear/Append dropdown items: {[self.location_choice.GetString(i) for i in range(self.location_choice.GetCount())]}"
        )

        # Get current selection name
        current_selection_name = self.location_service.get_current_location_name()

        # Log the available locations and current selection
        logger.info(f"UpdateLocationDropdown: Available locations: {names}")
        logger.info(
            f"UpdateLocationDropdown: Current location from service: '{current_selection_name}'"
        )

        # Set selection if we have one
        if current_selection_name and current_selection_name in names:
            logger.info(f"UpdateLocationDropdown: Setting selection to '{current_selection_name}'")
            self.location_choice.SetStringSelection(current_selection_name)

            # Verify the selection was set correctly
            selected_index = self.location_choice.GetSelection()
            if selected_index != wx.NOT_FOUND:
                selected_name = self.location_choice.GetString(selected_index)
                logger.info(f"UpdateLocationDropdown: Selection verified as '{selected_name}'")
            else:
                logger.warning("UpdateLocationDropdown: Failed to set selection in dropdown")
                # Try to set by index if string selection failed
                try:
                    name_index = names.index(current_selection_name)
                    logger.debug(
                        f"UpdateLocationDropdown: Trying to set selection by index {name_index}"
                    )
                    self.location_choice.SetSelection(name_index)

                    # Verify again
                    selected_index = self.location_choice.GetSelection()
                    if selected_index != wx.NOT_FOUND:
                        selected_name = self.location_choice.GetString(selected_index)
                        logger.info(
                            f"UpdateLocationDropdown: Selection by index verified as '{selected_name}'"
                        )
                    else:
                        logger.error("UpdateLocationDropdown: Failed to set selection by index")
                except ValueError:
                    logger.error(
                        f"UpdateLocationDropdown: Could not find '{current_selection_name}' in names list"
                    )

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
