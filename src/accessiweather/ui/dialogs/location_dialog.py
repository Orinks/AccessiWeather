"""Location dialog for adding and managing locations using gui_builder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class AddLocationDialog(forms.Dialog):
    """Dialog for adding a new location with search functionality using gui_builder."""

    # Title
    title_label = fields.StaticText(label="Add New Location")

    # Location name section
    name_label = fields.StaticText(label="Location Name:")
    name_input = fields.Text(label="Enter a descriptive name for this location")
    name_help = fields.StaticText(label="This name will appear in your location list")

    # Search section
    search_label = fields.StaticText(label="Search for Location (city/zipcode):")
    search_input = fields.Text(label="City name or ZIP/postal code")
    search_button = fields.Button(label="&Search")
    search_help = fields.StaticText(label="Examples: 'New York', '10001', 'London'")

    # Results section
    results_label = fields.StaticText(label="Search Results:")
    results_list = fields.ListBox(label="Search results")

    # Status
    status_label = fields.StaticText(label="Ready to add location")

    # Buttons
    cancel_button = fields.Button(label="&Cancel")
    save_button = fields.Button(label="&Save Location")

    def __init__(self, app: AccessiWeatherApp, **kwargs):
        """
        Initialize the add location dialog.

        Args:
            app: Application instance
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.app = app
        self.config_manager = app.config_manager
        self._added_location = None
        self._search_results = []
        self._selected_location = None
        self._is_searching = False

        # Import LocationManager
        from ...location_manager import LocationManager

        self.location_manager = LocationManager()

        kwargs.setdefault("title", "Add Location")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and set up components."""
        super().render(**kwargs)
        self._setup_accessibility()

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.name_input.set_accessible_label("Location name input")
        self.search_input.set_accessible_label("Search for location")
        self.results_list.set_accessible_label("Search results")

    def _update_status(self, message: str, is_error: bool = False) -> None:
        """Update the status label."""
        self.status_label.set_label(message)
        logger.info(f"Location dialog status: {message}")

    @search_button.add_callback
    def on_search(self):
        """Handle search button press."""
        query = self.search_input.get_value().strip()
        if not query:
            self._update_status("Please enter a search term", is_error=True)
            return

        if self._is_searching:
            self._update_status("Search already in progress...", is_error=True)
            return

        self._is_searching = True
        self.search_button.disable()
        self._update_status(f"Searching for '{query}'...")

        # Clear previous results
        self.results_list.set_items([])
        self._search_results = []

        # Run async search
        self.app.run_async(self._do_search(query))

    async def _do_search(self, query: str):
        """Perform the location search."""
        try:
            locations = await self.location_manager.search_locations(query, limit=10)

            # Update UI on main thread
            wx.CallAfter(self._on_search_complete, locations)

        except Exception as e:
            logger.error(f"Search failed: {e}")
            wx.CallAfter(self._on_search_error, str(e))

    def _on_search_complete(self, locations) -> None:
        """Handle search completion."""
        self._is_searching = False
        self.search_button.enable()

        if locations:
            self._search_results = locations

            items = []
            for location in locations:
                coords_str = self.location_manager.format_coordinates(
                    location.latitude, location.longitude
                )
                items.append(f"{location.name} ({coords_str})")

            self.results_list.set_items(items)
            self._update_status(f"Found {len(locations)} locations")

            # Auto-fill name if empty
            if not self.name_input.get_value().strip() and locations:
                self.name_input.set_value(locations[0].name)
        else:
            self._update_status("No locations found. Try a different search term.", is_error=True)

    def _on_search_error(self, error: str) -> None:
        """Handle search error."""
        self._is_searching = False
        self.search_button.enable()
        self._update_status(f"Search failed: {error}", is_error=True)

    @results_list.add_callback
    def on_result_selected(self):
        """Handle selection of a search result."""
        index = self.results_list.get_index()
        if index is not None and 0 <= index < len(self._search_results):
            self._selected_location = self._search_results[index]
            self.name_input.set_value(self._selected_location.name)
            self._update_status(f"Selected: {self._selected_location.name}")

    @save_button.add_callback
    def on_save(self):
        """Handle save button press."""
        name = self.name_input.get_value().strip()
        if not name:
            self._update_status("Please enter a location name", is_error=True)
            return

        # Get coordinates
        if not self._selected_location:
            self._update_status("Please search for and select a location", is_error=True)
            return

        latitude = self._selected_location.latitude
        longitude = self._selected_location.longitude

        # Validate coordinates
        if not self.location_manager.validate_coordinates(latitude, longitude):
            self._update_status(
                "Invalid coordinates. Latitude must be -90 to 90, longitude -180 to 180",
                is_error=True,
            )
            return

        # Check if location already exists
        existing_names = self.config_manager.get_location_names()
        if name in existing_names:
            self._update_status("A location with this name already exists", is_error=True)
            return

        try:
            country_code = getattr(self._selected_location, "country_code", None)

            # Add location
            success = self.config_manager.add_location(
                name, latitude, longitude, country_code=country_code
            )

            if success:
                self._added_location = name
                self._update_status("Location saved successfully!")
                self.widget.control.EndModal(wx.ID_OK)
            else:
                self._update_status("Failed to save location", is_error=True)

        except Exception as e:
            logger.error(f"Failed to save location: {e}")
            self._update_status(f"Error saving location: {e}", is_error=True)

    @cancel_button.add_callback
    def on_cancel(self):
        """Handle cancel button press."""
        self.widget.control.EndModal(wx.ID_CANCEL)

    def get_added_location(self) -> str | None:
        """Get the name of the added location."""
        return self._added_location


def show_add_location_dialog(parent, app: AccessiWeatherApp) -> str | None:
    """
    Show the add location dialog.

    Args:
        parent: Parent window (gui_builder widget)
        app: Application instance

    Returns:
        The name of the added location, or None if cancelled

    """
    try:
        # Get the underlying wx control if parent is a gui_builder widget
        parent_ctrl = getattr(parent, "control", parent)

        dlg = AddLocationDialog(app, parent=parent_ctrl)
        dlg.render()
        result = dlg.widget.control.ShowModal()

        if result == wx.ID_OK:
            location_name = dlg.get_added_location()
            dlg.widget.control.Destroy()
            return location_name

        dlg.widget.control.Destroy()
        return None

    except Exception as e:
        logger.error(f"Failed to show add location dialog: {e}")
        wx.MessageBox(
            f"Failed to open location dialog: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return None
