"""Location dialog for adding and managing locations using wxPython."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


def show_add_location_dialog(parent, app: AccessiWeatherApp) -> str | None:
    """
    Show the add location dialog.

    Args:
        parent: Parent window
        app: Application instance

    Returns:
        The name of the added location, or None if cancelled

    """
    try:
        parent_ctrl = parent

        dlg = AddLocationDialog(parent_ctrl, app)
        result = dlg.ShowModal()

        if result == wx.ID_OK:
            location_name = dlg.get_added_location()
            dlg.Destroy()
            return location_name

        dlg.Destroy()
        return None

    except Exception as e:
        logger.error(f"Failed to show add location dialog: {e}")
        wx.MessageBox(
            f"Failed to open location dialog: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return None


class AddLocationDialog(wx.Dialog):
    """Dialog for adding a new location with search functionality."""

    def __init__(self, parent, app: AccessiWeatherApp):
        """
        Initialize the add location dialog.

        Args:
            parent: Parent window
            app: Application instance

        """
        super().__init__(
            parent,
            title="Add Location",
            size=(600, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.app = app
        self.config_manager = app.config_manager
        self._added_location = None
        self._search_results = []
        self._selected_location = None
        self._is_searching = False

        # Import LocationManager
        from ...location_manager import LocationManager

        self.location_manager = LocationManager()

        self._create_ui()
        self._setup_accessibility()

    def _create_ui(self):
        """Create the dialog UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Add New Location")
        title.SetFont(title.GetFont().Bold())
        main_sizer.Add(title, 0, wx.ALL, 10)

        # Location name section
        name_sizer = wx.BoxSizer(wx.VERTICAL)
        name_label = wx.StaticText(panel, label="Location Name:")
        name_sizer.Add(name_label, 0, wx.BOTTOM, 5)

        self.name_input = wx.TextCtrl(panel, size=(400, -1))
        self.name_input.SetHint("Enter a descriptive name for this location")
        name_sizer.Add(self.name_input, 0, wx.EXPAND)

        help_text = wx.StaticText(panel, label="This name will appear in your location list")
        help_text.SetForegroundColour(wx.Colour(128, 128, 128))
        name_sizer.Add(help_text, 0, wx.TOP, 5)

        main_sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Search section
        search_sizer = wx.BoxSizer(wx.VERTICAL)
        search_label = wx.StaticText(panel, label="Search for Location (city/zipcode):")
        search_sizer.Add(search_label, 0, wx.BOTTOM, 5)

        search_row = wx.BoxSizer(wx.HORIZONTAL)
        self.search_input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_input.SetHint("City name or ZIP/postal code")
        self.search_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        search_row.Add(self.search_input, 1, wx.RIGHT, 10)

        self.search_button = wx.Button(panel, label="Search")
        self.search_button.Bind(wx.EVT_BUTTON, self._on_search)
        search_row.Add(self.search_button, 0)

        search_sizer.Add(search_row, 0, wx.EXPAND)

        search_help = wx.StaticText(panel, label="Examples: 'New York', '10001', 'London'")
        search_help.SetForegroundColour(wx.Colour(128, 128, 128))
        search_sizer.Add(search_help, 0, wx.TOP, 5)

        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Results section
        results_label = wx.StaticText(panel, label="Search Results:")
        main_sizer.Add(results_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.results_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self.results_list.InsertColumn(0, "Location", width=300)
        self.results_list.InsertColumn(1, "Coordinates", width=200)
        self.results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_result_selected)
        self.results_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_result_activated)
        main_sizer.Add(self.results_list, 1, wx.EXPAND | wx.ALL, 10)

        # Status section
        self.status_label = wx.StaticText(panel, label="Ready to add location")
        self.status_label.SetForegroundColour(wx.Colour(128, 128, 128))
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_btn, 0, wx.RIGHT, 10)

        self.save_button = wx.Button(panel, wx.ID_OK, "Save Location")
        self.save_button.Bind(wx.EVT_BUTTON, self._on_save)
        button_sizer.Add(self.save_button, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        # Set initial focus
        self.name_input.SetFocus()

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        self.name_input.SetName("Location name input")
        self.search_input.SetName("Search for location")
        self.results_list.SetName("Search results")

    def _update_status(self, message: str, is_error: bool = False):
        """Update the status label."""
        self.status_label.SetLabel(message)
        if is_error:
            self.status_label.SetForegroundColour(wx.Colour(192, 0, 0))
        else:
            self.status_label.SetForegroundColour(wx.Colour(0, 128, 0))
        logger.info(f"Location dialog status: {message}")

    def _on_search(self, event):
        """Handle search button press."""
        query = self.search_input.GetValue().strip()
        if not query:
            self._update_status("Please enter a search term", is_error=True)
            return

        if self._is_searching:
            self._update_status("Search already in progress...", is_error=True)
            return

        self._is_searching = True
        self.search_button.Disable()
        self._update_status(f"Searching for '{query}'...")

        # Clear previous results
        self.results_list.DeleteAllItems()
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

    def _on_search_complete(self, locations):
        """Handle search completion."""
        self._is_searching = False
        self.search_button.Enable()

        if locations:
            self._search_results = locations

            for location in locations:
                coords_str = self.location_manager.format_coordinates(
                    location.latitude, location.longitude
                )
                index = self.results_list.InsertItem(
                    self.results_list.GetItemCount(), location.name
                )
                self.results_list.SetItem(index, 1, coords_str)

            self._update_status(f"Found {len(locations)} locations")

            # Auto-fill name if empty
            if not self.name_input.GetValue().strip() and locations:
                self.name_input.SetValue(locations[0].name)
        else:
            self._update_status("No locations found. Try a different search term.", is_error=True)

    def _on_search_error(self, error: str):
        """Handle search error."""
        self._is_searching = False
        self.search_button.Enable()
        self._update_status(f"Search failed: {error}", is_error=True)

    def _on_result_selected(self, event):
        """Handle selection of a search result."""
        index = event.GetIndex()
        if 0 <= index < len(self._search_results):
            self._selected_location = self._search_results[index]
            self.name_input.SetValue(self._selected_location.name)
            self._update_status(f"Selected: {self._selected_location.name}")

    def _on_result_activated(self, event):
        """Handle double-click on a search result."""
        self._on_result_selected(event)
        self._on_save(event)

    def _on_save(self, event):
        """Handle save button press."""
        name = self.name_input.GetValue().strip()
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
                self.EndModal(wx.ID_OK)
            else:
                self._update_status("Failed to save location", is_error=True)

        except Exception as e:
            logger.error(f"Failed to save location: {e}")
            self._update_status(f"Error saving location: {e}", is_error=True)

    def get_added_location(self) -> str | None:
        """Get the name of the added location."""
        return self._added_location
