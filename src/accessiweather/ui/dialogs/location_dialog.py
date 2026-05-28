"""Location dialog for adding and managing locations using wxPython."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import wx

from ...current_location import CurrentLocationService, LocationDetectionStatus

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp
    from ...models import Location

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EditLocationResult:
    """Editable values returned by the edit location dialog."""

    display_name: str
    latitude: float
    longitude: float
    country_code: str | None
    marine_mode: bool


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


def show_edit_location_dialog(
    parent,
    app: AccessiWeatherApp,
    location,
) -> EditLocationResult | None:
    """
    Show a small edit dialog for an existing location.

    Returns the chosen editable values on OK, or ``None`` if the user cancelled.
    """
    try:
        dlg = EditLocationDialog(parent, app, location)
        result = dlg.ShowModal()

        if result == wx.ID_OK:
            new_value = dlg.get_result()
            dlg.Destroy()
            return new_value

        dlg.Destroy()
        return None

    except Exception as e:
        logger.error(f"Failed to show edit location dialog: {e}")
        wx.MessageBox(
            f"Failed to open edit location dialog: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return None


_ZONE_NOT_RESOLVED_MSG = "Not yet resolved - will populate after next weather refresh"


def _edit_location_is_us(location) -> bool:
    """
    Determine whether a location should display NWS zone information.

    Uses the country_code fast path first, then falls back to coordinate bounds
    consistent with ``accessiweather.display.presentation.forecast._is_us_location``.
    """
    country_code = getattr(location, "country_code", None)
    if country_code:
        return str(country_code).upper() == "US"

    lat = getattr(location, "latitude", None)
    lon = getattr(location, "longitude", None)
    if lat is None or lon is None:
        return False
    in_continental_bounds = 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0
    in_alaska_bounds = 51.0 <= lat <= 71.5 and -172.0 <= lon <= -130.0
    in_hawaii_bounds = 18.0 <= lat <= 23.0 and -161.0 <= lon <= -154.0
    return in_continental_bounds or in_alaska_bounds or in_hawaii_bounds


class EditLocationDialog(wx.Dialog):
    """Dialog for editing an existing location."""

    def __init__(self, parent, app: AccessiWeatherApp, location: Location):
        """Initialize with the location being edited."""
        super().__init__(
            parent,
            title=f"Edit Location: {location.name}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.app = app
        self._location = location
        self._selected_location: Location | None = None
        self._search_results: list[Location] = []
        self._is_searching = False
        self._is_detecting_current_location = False

        from ...location_manager import LocationManager

        self.location_manager = LocationManager()
        self.current_location_service = CurrentLocationService()

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        name_sizer = wx.BoxSizer(wx.VERTICAL)
        name_label = wx.StaticText(panel, label="Location Name:")
        name_sizer.Add(name_label, 0, wx.BOTTOM, 5)
        self.name_input = wx.TextCtrl(panel, value=location.name, size=wx.Size(400, -1))
        self.name_input.SetHint("Enter a descriptive name for this location")
        self.name_input.SetName("Location name input")
        name_sizer.Add(self.name_input, 0, wx.EXPAND)
        sizer.Add(name_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.current_coordinates_label = wx.StaticText(
            panel,
            label=(
                "Current coordinates: "
                f"{self.location_manager.format_coordinates(location.latitude, location.longitude)}"
            ),
        )
        sizer.Add(self.current_coordinates_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.marine_checkbox = wx.CheckBox(
            panel,
            label="Enable Marine Mode for this location (coastal essentials only)",
        )
        self.marine_checkbox.SetValue(bool(getattr(location, "marine_mode", False)))
        self.marine_checkbox.SetToolTip(
            "Adds nearby NWS marine zone summary, wind and wave highlights, and marine advisories."
        )
        self.marine_checkbox.SetName("Enable Marine Mode for this location")
        sizer.Add(self.marine_checkbox, 0, wx.ALL | wx.EXPAND, 10)

        address_box = wx.StaticBox(panel, label="Update Coordinates from Address")
        address_sizer = wx.StaticBoxSizer(address_box, wx.VERTICAL)
        address_parent = address_box

        address_label = wx.StaticText(
            address_parent,
            label="Search for a US street address to update this saved location:",
        )
        address_sizer.Add(address_label, 0, wx.ALL, 5)

        search_row = wx.BoxSizer(wx.HORIZONTAL)
        self.address_input = wx.TextCtrl(address_parent, style=wx.TE_PROCESS_ENTER)
        self.address_input.SetHint("Street address, city, state, and ZIP")
        self.address_input.SetName("Address lookup for saved location coordinates")
        self.address_input.Bind(wx.EVT_TEXT_ENTER, self._on_address_search)
        search_row.Add(self.address_input, 1, wx.RIGHT, 8)

        self.address_search_button = wx.Button(address_parent, label="Search")
        self.address_search_button.Bind(wx.EVT_BUTTON, self._on_address_search)
        search_row.Add(self.address_search_button, 0)
        address_sizer.Add(search_row, 0, wx.EXPAND | wx.ALL, 5)

        self.current_location_button = wx.Button(
            address_parent,
            label="Use my current location",
        )
        self.current_location_button.SetToolTip(
            "Ask the operating system once for your current coordinates. "
            "The existing coordinates stay available if this is unavailable or denied."
        )
        self.current_location_button.SetName("Use my current location for this saved location")
        self.current_location_button.Bind(wx.EVT_BUTTON, self._on_use_current_location)
        address_sizer.Add(self.current_location_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        self.address_results_list = wx.ListCtrl(
            address_parent,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
            size=(-1, 110),
        )
        self.address_results_list.SetName("Address lookup results")
        self.address_results_list.InsertColumn(0, "Matched Address", width=320)
        self.address_results_list.InsertColumn(1, "Coordinates", width=180)
        self.address_results_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_address_selected)
        address_sizer.Add(self.address_results_list, 0, wx.EXPAND | wx.ALL, 5)

        self.coordinate_comparison_label = wx.StaticText(
            address_parent,
            label="No address selected. Existing coordinates will be kept.",
        )
        self.coordinate_comparison_label.SetName("Coordinate comparison")
        address_sizer.Add(self.coordinate_comparison_label, 0, wx.ALL, 5)
        sizer.Add(address_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # NWS Zone Information section (US locations only, snapshot at open).
        self._zone_info_box = wx.StaticBox(panel, label="NWS Zone Information")
        zone_sizer = wx.StaticBoxSizer(self._zone_info_box, wx.VERTICAL)

        zone_parent = self._zone_info_box
        zone_id = getattr(location, "forecast_zone_id", None)
        office = getattr(location, "cwa_office", None)

        forecast_zone_text = (
            f"Forecast Zone: {zone_id}" if zone_id else f"Forecast Zone: {_ZONE_NOT_RESOLVED_MSG}"
        )
        office_text = f"NWS Office: {office}" if office else f"NWS Office: {_ZONE_NOT_RESOLVED_MSG}"

        self._forecast_zone_label = wx.StaticText(zone_parent, label=forecast_zone_text)
        self._cwa_office_label = wx.StaticText(zone_parent, label=office_text)
        zone_sizer.Add(self._forecast_zone_label, 0, wx.ALL, 5)
        zone_sizer.Add(self._cwa_office_label, 0, wx.ALL, 5)
        sizer.Add(zone_sizer, 0, wx.ALL | wx.EXPAND, 10)

        if not _edit_location_is_us(location):
            # Hide the entire box for non-US locations (no "N/A" fallback).
            self._zone_info_box.Show(False)

        button_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK, "&Save")
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.AddButton(ok_button)
        button_sizer.AddButton(cancel_button)
        button_sizer.Realize()
        sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(sizer)
        ok_button.SetDefault()

        # Fit to content, but keep a baseline minimum width.
        self.SetMinSize(wx.Size(640, -1))
        self.Fit()

    def _on_address_search(self, event) -> None:
        """Handle address search button press."""
        query = self.address_input.GetValue().strip()
        if not query:
            self._set_coordinate_comparison("Enter an address to search.", is_error=True)
            return

        if self._is_searching:
            self._set_coordinate_comparison("Search already in progress.", is_error=True)
            return

        self._is_searching = True
        self.address_search_button.Disable()
        self._set_coordinate_comparison(f"Searching for '{query}'...")
        self.address_results_list.DeleteAllItems()
        self._search_results = []
        self._selected_location = None

        self.app.run_async(self._do_address_search(query))

    def _on_use_current_location(self, event) -> None:
        """Handle one-time current-location detection for an existing location."""
        if self._is_detecting_current_location:
            self._set_coordinate_comparison(
                "Current location detection is already in progress.",
                is_error=True,
            )
            return

        self._is_detecting_current_location = True
        self.current_location_button.Disable()
        self._set_coordinate_comparison(
            "Requesting current location. Your system may ask for permission now..."
        )
        self.app.run_async(self._do_current_location_detection())

    async def _do_current_location_detection(self) -> None:
        """Run native location detection once."""
        result = await self.current_location_service.detect_once()
        if result.status is LocationDetectionStatus.SUCCESS and result.location is not None:
            location = await self._resolve_detected_location(result.location)
            wx.CallAfter(self._on_current_location_detected, location)
            return
        wx.CallAfter(self._on_current_location_error, result.message)

    async def _resolve_detected_location(self, location: Location) -> Location:
        """Prefer a reverse-geocoded label and metadata for detected coordinates."""
        try:
            resolved = await self.location_manager.reverse_geocode_coordinates(
                location.latitude,
                location.longitude,
            )
        except Exception as exc:  # noqa: BLE001 - fallback label remains editable
            logger.debug("Detected-location reverse geocoding failed: %s", exc)
            return location
        return resolved or location

    def _on_current_location_detected(self, location: Location) -> None:
        """Apply detected coordinates as the pending coordinate update."""
        self._is_detecting_current_location = False
        self.current_location_button.Enable()
        self._selected_location = location
        self._search_results = [location]
        self.address_results_list.DeleteAllItems()
        coords = self.location_manager.format_coordinates(location.latitude, location.longitude)
        index = self.address_results_list.InsertItem(0, location.name)
        self.address_results_list.SetItem(index, 1, coords)
        self.name_input.SetValue(location.name)
        distance = self.location_manager.calculate_distance(self._location, location)
        self._set_coordinate_comparison(
            f"Detected current location as {location.name}: {coords}. "
            f"Difference from saved coordinates: {distance:.2f} miles. "
            "Review the editable name, then save it."
        )

    def _on_current_location_error(self, message: str) -> None:
        """Handle unavailable, denied, unsupported, or timed-out detection."""
        self._is_detecting_current_location = False
        self.current_location_button.Enable()
        self._set_coordinate_comparison(message, is_error=True)

    async def _do_address_search(self, query: str) -> None:
        """Perform the address lookup."""
        try:
            locations = await self.location_manager.search_locations(query, limit=5)
            wx.CallAfter(self._on_address_search_complete, locations)
        except Exception as e:
            logger.error(f"Address lookup failed: {e}")
            wx.CallAfter(self._on_address_search_error, str(e))

    def _on_address_search_complete(self, locations: list[Location]) -> None:
        """Handle address lookup completion."""
        self._is_searching = False
        self.address_search_button.Enable()

        if not locations:
            self._set_coordinate_comparison("No address matches found.", is_error=True)
            return

        self._search_results = locations
        for location in locations:
            coords = self.location_manager.format_coordinates(
                location.latitude,
                location.longitude,
            )
            index = self.address_results_list.InsertItem(
                self.address_results_list.GetItemCount(),
                location.name,
            )
            self.address_results_list.SetItem(index, 1, coords)

        self._set_coordinate_comparison(
            f"Found {len(locations)} matches. Select one to compare coordinates."
        )

    def _on_address_search_error(self, error: str) -> None:
        """Handle address lookup failure."""
        self._is_searching = False
        self.address_search_button.Enable()
        self._set_coordinate_comparison(f"Address search failed: {error}", is_error=True)

    def _on_address_selected(self, event) -> None:
        """Handle address result selection."""
        index = event.GetIndex()
        if not 0 <= index < len(self._search_results):
            return

        selected_location = self._search_results[index]
        self._selected_location = selected_location
        distance = self.location_manager.calculate_distance(
            self._location,
            selected_location,
        )
        current_coords = self.location_manager.format_coordinates(
            self._location.latitude,
            self._location.longitude,
        )
        new_coords = self.location_manager.format_coordinates(
            selected_location.latitude,
            selected_location.longitude,
        )
        self.name_input.SetValue(selected_location.name)
        self._set_coordinate_comparison(
            f"Current: {current_coords}. New: {new_coords}. Difference: {distance:.2f} miles."
        )

    def _set_coordinate_comparison(self, message: str, is_error: bool = False) -> None:
        """Update the coordinate comparison label."""
        self.coordinate_comparison_label.SetLabel(message)
        colour = wx.SystemSettings.GetColour(
            wx.SYS_COLOUR_GRAYTEXT if is_error else wx.SYS_COLOUR_WINDOWTEXT
        )
        self.coordinate_comparison_label.SetForegroundColour(colour)
        self.coordinate_comparison_label.Wrap(580)
        self.Layout()
        self.Fit()

    def get_result(self) -> EditLocationResult:
        """Return the editable values chosen in the dialog."""
        selected = self._selected_location
        return EditLocationResult(
            display_name=self.name_input.GetValue().strip(),
            latitude=selected.latitude if selected else self._location.latitude,
            longitude=selected.longitude if selected else self._location.longitude,
            country_code=(selected.country_code if selected else self._location.country_code),
            marine_mode=self.marine_checkbox.GetValue(),
        )


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
        self._is_detecting_current_location = False

        # Import LocationManager
        from ...location_manager import LocationManager

        self.location_manager = LocationManager()
        self.current_location_service = CurrentLocationService()

        self._create_ui()
        self._setup_accessibility()
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

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
        help_text.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        name_sizer.Add(help_text, 0, wx.TOP, 5)

        self.marine_mode_checkbox = wx.CheckBox(
            panel,
            label="Enable Marine Mode for this location (coastal essentials only)",
        )
        self.marine_mode_checkbox.SetToolTip(
            "Adds nearby NWS marine zone summary, wind and wave highlights, and marine advisories."
        )
        name_sizer.Add(self.marine_mode_checkbox, 0, wx.TOP, 8)

        main_sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Search section
        search_sizer = wx.BoxSizer(wx.VERTICAL)
        search_label = wx.StaticText(
            panel,
            label="Search for Location (city, ZIP/postal code, or US address):",
        )
        search_sizer.Add(search_label, 0, wx.BOTTOM, 5)

        search_row = wx.BoxSizer(wx.HORIZONTAL)
        self.search_input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_input.SetHint("City, ZIP/postal code, or US street address")
        self.search_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        search_row.Add(self.search_input, 1, wx.RIGHT, 10)

        self.search_button = wx.Button(panel, label="Search")
        self.search_button.Bind(wx.EVT_BUTTON, self._on_search)
        search_row.Add(self.search_button, 0)

        search_sizer.Add(search_row, 0, wx.EXPAND)

        self.current_location_button = wx.Button(panel, label="Use my current location")
        self.current_location_button.SetToolTip(
            "Ask the operating system once for your current coordinates. "
            "Manual search stays available if this is unavailable or denied."
        )
        self.current_location_button.Bind(wx.EVT_BUTTON, self._on_use_current_location)
        search_sizer.Add(self.current_location_button, 0, wx.TOP, 8)

        search_help = wx.StaticText(
            panel,
            label="Examples: 'London', 'New York', '10001', or '123 Main St, Carrollton, TX'",
        )
        search_help.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
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
        self.status_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        self.save_button = wx.Button(panel, wx.ID_OK, "Save Location")
        self.save_button.Bind(wx.EVT_BUTTON, self._on_save)
        button_sizer.Add(self.save_button, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(cancel_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)

        # Set initial focus
        self.name_input.SetFocus()

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        self.name_input.SetName("Location name input")
        self.search_input.SetName("Search for location")
        self.results_list.SetName("Search results")
        self.marine_mode_checkbox.SetName("Enable Marine Mode for this location")
        self.current_location_button.SetName("Use my current location")

    def _on_key(self, event: wx.KeyEvent) -> None:
        """Handle key events."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _update_status(self, message: str, is_error: bool = False):
        """Update the status label."""
        self.status_label.SetLabel(message)
        if is_error:
            self.status_label.SetForegroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
            )
        else:
            self.status_label.SetForegroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
            )
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

    def _on_use_current_location(self, event) -> None:
        """Handle one-time current-location detection button press."""
        if self._is_detecting_current_location:
            self._update_status("Current location detection is already in progress.", is_error=True)
            return

        self._is_detecting_current_location = True
        self.current_location_button.Disable()
        self._update_status(
            "Requesting current location. Your system may ask for permission now..."
        )
        self.app.run_async(self._do_current_location_detection())

    async def _do_current_location_detection(self) -> None:
        """Run native location detection once."""
        result = await self.current_location_service.detect_once()
        if result.status is LocationDetectionStatus.SUCCESS and result.location is not None:
            location = await self._resolve_detected_location(result.location)
            wx.CallAfter(self._on_current_location_detected, location)
            return
        wx.CallAfter(self._on_current_location_error, result.message)

    async def _resolve_detected_location(self, location: Location) -> Location:
        """Prefer a reverse-geocoded label and metadata for detected coordinates."""
        try:
            resolved = await self.location_manager.reverse_geocode_coordinates(
                location.latitude,
                location.longitude,
            )
        except Exception as exc:  # noqa: BLE001 - fallback label remains editable
            logger.debug("Detected-location reverse geocoding failed: %s", exc)
            return location
        return resolved or location

    def _on_current_location_detected(self, location: Location) -> None:
        """Handle successful current-location detection."""
        self._is_detecting_current_location = False
        self.current_location_button.Enable()
        self._apply_detected_location(location)

    def _apply_detected_location(self, location: Location) -> None:
        """Populate the normal add-location fields from detected coordinates."""
        self._selected_location = location
        self._search_results = [location]
        self.results_list.DeleteAllItems()
        coords_str = self.location_manager.format_coordinates(
            location.latitude,
            location.longitude,
        )
        index = self.results_list.InsertItem(0, location.name)
        self.results_list.SetItem(index, 1, coords_str)
        if not self.name_input.GetValue().strip():
            self.name_input.SetValue(location.name)
        self._update_status("Detected current location. Review the editable name, then save it.")

    def _on_current_location_error(self, message: str) -> None:
        """Handle unavailable, denied, unsupported, or timed-out detection."""
        self._is_detecting_current_location = False
        self.current_location_button.Enable()
        self._update_status(message, is_error=True)

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
                name,
                latitude,
                longitude,
                country_code=country_code,
                marine_mode=self.marine_mode_checkbox.GetValue(),
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
