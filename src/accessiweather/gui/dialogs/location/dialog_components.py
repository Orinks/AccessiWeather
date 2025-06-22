"""Main dialog components for location input and management.

This module contains the primary dialog classes for location-related user
interactions, including manual coordinate entry and location search.
"""

import logging

import wx

from ...ui_components import (
    AccessibleButton,
    AccessibleComboBox,
    AccessibleListCtrl,
    AccessibleStaticText,
    AccessibleTextCtrl,
)
from .constants import (
    ADVANCED_BUTTON_TEXT,
    ADVANCED_DIALOG_TITLE,
    CANCEL_BUTTON_TEXT,
    DEFAULT_DATA_SOURCE,
    DEFAULT_LAT,
    DEFAULT_LOCATION_NAME,
    DEFAULT_LON,
    DIALOG_BORDER,
    LATITUDE_LABEL,
    LOCATION_DIALOG_TITLE,
    LOCATION_HELP_TEXT,
    LOCATION_NAME_LABEL,
    LONGITUDE_LABEL,
    SAVE_BUTTON_TEXT,
    SEARCH_BUTTON_TEXT,
    SEARCH_RESULTS_HEIGHT,
    SEARCH_RESULTS_LABEL,
    TEXT_CTRL_MIN_HEIGHT,
)
from .geocoding_manager import GeocodingSearchManager, LocationSearchResultProcessor
from .input_validators import AdvancedDialogValidator, LocationDialogValidator

logger = logging.getLogger(__name__)


class AdvancedLocationDialog(wx.Dialog):
    """Dialog for manually entering lat/lon coordinates."""

    def __init__(
        self,
        parent: wx.Window,
        title: str = ADVANCED_DIALOG_TITLE,
        lat: float | None = DEFAULT_LAT,
        lon: float | None = DEFAULT_LON,
    ):
        """Initialize the advanced location dialog.

        Args:
            parent: Parent window
            title: Dialog title
            lat: Initial latitude
            lon: Initial longitude

        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)

        self.validator: AdvancedDialogValidator | None = None
        self._init_ui(lat, lon)
        self._bind_events()

    def _init_ui(self, lat: float | None, lon: float | None) -> None:
        """Initialize the UI components.

        Args:
            lat: Initial latitude value
            lon: Initial longitude value

        """
        # Create main panel
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Latitude field
        lat_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lat_label = AccessibleStaticText(panel, label=LATITUDE_LABEL)
        self.lat_ctrl = AccessibleTextCtrl(
            panel, value=str(lat) if lat is not None else "", label="Latitude"
        )
        lat_sizer.Add(lat_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lat_sizer.Add(self.lat_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lat_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Longitude field
        lon_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lon_label = AccessibleStaticText(panel, label=LONGITUDE_LABEL)
        self.lon_ctrl = AccessibleTextCtrl(
            panel, value=str(lon) if lon is not None else "", label="Longitude"
        )
        lon_sizer.Add(lon_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lon_sizer.Add(self.lon_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lon_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Help text
        help_text = AccessibleStaticText(
            panel, label="Enter latitude and longitude in decimal format (e.g., 35.123, -80.456)"
        )
        sizer.Add(help_text, 0, wx.ALL, DIALOG_BORDER)

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = AccessibleButton(panel, wx.ID_OK, SAVE_BUTTON_TEXT)
        self.cancel_button = AccessibleButton(panel, wx.ID_CANCEL, CANCEL_BUTTON_TEXT)

        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, DIALOG_BORDER)

        panel.SetSizer(sizer)
        sizer.Fit(self)

        # Set initial focus for accessibility
        self.lat_ctrl.SetFocus()

        # Initialize validator
        self.validator = AdvancedDialogValidator(self.lat_ctrl, self.lon_ctrl)

    def _bind_events(self) -> None:
        """Bind event handlers."""
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)

    def OnOK(self, event: wx.CommandEvent) -> None:
        """Handle OK button event.

        Args:
            event: Button event

        """
        if self.validator:
            is_valid, lat, lon = self.validator.validate_and_get_coordinates()
            if is_valid:
                event.Skip()  # Continue with default handler

    def GetValues(self) -> tuple[float | None, float | None]:
        """Get the dialog values.

        Returns:
            Tuple of (latitude, longitude)

        """
        if self.validator:
            return self.validator.get_coordinates_safe()
        return None, None


class LocationDialog(wx.Dialog):
    """Dialog for adding or editing a location with search functionality."""

    def __init__(
        self,
        parent: wx.Window,
        title: str = LOCATION_DIALOG_TITLE,
        location_name: str = DEFAULT_LOCATION_NAME,
        lat: float | None = DEFAULT_LAT,
        lon: float | None = DEFAULT_LON,
        data_source: str = DEFAULT_DATA_SOURCE,
    ):
        """Initialize the location dialog.

        Args:
            parent: Parent window
            title: Dialog title
            location_name: Initial location name
            lat: Initial latitude
            lon: Initial longitude
            data_source: The data source to use ('nws', 'openmeteo', or 'auto')

        """
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE)

        # Initialize state
        self.latitude = lat
        self.longitude = lon

        # Initialize managers
        self.geocoding_manager = GeocodingSearchManager(
            data_source=data_source,
            result_callback=self._on_search_result,
            error_callback=self._on_search_error,
        )
        self.result_processor = LocationSearchResultProcessor(self.geocoding_manager)
        self.validator: LocationDialogValidator | None = None

        # Initialize UI
        self._init_ui(location_name, lat, lon)
        self._bind_events()

    def _init_ui(self, location_name: str, lat: float | None, lon: float | None) -> None:
        """Initialize the UI components.

        Args:
            location_name: Initial location name
            lat: Initial latitude
            lon: Initial longitude

        """
        # Create main panel
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Name field
        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_label = AccessibleStaticText(panel, label=LOCATION_NAME_LABEL)
        self.name_ctrl = AccessibleTextCtrl(panel, value=location_name, label="Location Name")
        name_sizer.Add(name_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        name_sizer.Add(self.name_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Search field with history
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = AccessibleStaticText(panel, label="Search:")
        self.search_field = AccessibleComboBox(
            panel, style=wx.CB_DROPDOWN, label="Search for location"
        )
        search_sizer.Add(search_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        search_sizer.Add(self.search_field, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Search buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_button = AccessibleButton(panel, wx.ID_ANY, SEARCH_BUTTON_TEXT)
        self.advanced_button = AccessibleButton(panel, wx.ID_ANY, ADVANCED_BUTTON_TEXT)
        button_sizer.Add(self.search_button, 0, wx.ALL, 5)
        button_sizer.Add(self.advanced_button, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.CENTER, 5)

        # Search results list
        results_label = AccessibleStaticText(panel, label=SEARCH_RESULTS_LABEL)
        sizer.Add(results_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, DIALOG_BORDER)
        self.search_results_list = AccessibleListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            label="Search Results",
            size=(-1, SEARCH_RESULTS_HEIGHT),
        )
        # Set up columns for search results list
        self.search_results_list.InsertColumn(0, "Location")
        self.search_results_list.SetColumnWidth(0, 500)
        sizer.Add(self.search_results_list, 0, wx.ALL | wx.EXPAND, DIALOG_BORDER)

        # Result display
        self.result_text = AccessibleTextCtrl(
            panel, value="", style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, TEXT_CTRL_MIN_HEIGHT)
        )
        self.result_text.set_label("Search Result")
        sizer.Add(self.result_text, 0, wx.ALL | wx.EXPAND, 5)

        # Help text
        help_text = AccessibleStaticText(panel, label=LOCATION_HELP_TEXT)
        sizer.Add(help_text, 0, wx.ALL, DIALOG_BORDER)

        # Dialog buttons
        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = AccessibleButton(panel, wx.ID_OK, SAVE_BUTTON_TEXT)
        self.cancel_button = AccessibleButton(panel, wx.ID_CANCEL, CANCEL_BUTTON_TEXT)

        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, DIALOG_BORDER)

        panel.SetSizer(sizer)
        sizer.Fit(self)

        # Set initial focus for accessibility
        self.name_ctrl.SetFocus()

        # Initialize validator
        self.validator = LocationDialogValidator(self.name_ctrl, self.latitude, self.longitude)

        # Show initial coordinates if provided
        if lat is not None and lon is not None:
            from .geocoding_manager import SearchResultHandler

            self.result_text.SetValue(SearchResultHandler.format_custom_coordinates(lat, lon))

    def _bind_events(self) -> None:
        """Bind event handlers."""
        self.Bind(wx.EVT_BUTTON, self.OnSearch, self.search_button)
        self.Bind(wx.EVT_BUTTON, self.OnAdvanced, self.advanced_button)
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
        self.Bind(wx.EVT_COMBOBOX, self._on_combobox_select, self.search_field)
        self.Bind(
            wx.EVT_LIST_ITEM_ACTIVATED, self._on_list_item_activated, self.search_results_list
        )
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnSearch(self, event: wx.CommandEvent) -> None:
        """Handle search button click.

        Args:
            event: Button event

        """
        query = self.search_field.GetValue().strip()
        if not query:
            from .input_validators import ValidationErrorHandler

            ValidationErrorHandler.show_search_error(
                self, "Please enter an address, city, or ZIP code to search"
            )
            return

        # Update UI to show searching state
        self.result_text.SetValue(f"Searching for {query}...")

        # Perform the search
        self.geocoding_manager.perform_search(query)

        # Update search field with history
        self._update_search_field_choices()

        # Get suggestions for the list
        self._fetch_search_suggestions(query)

    def OnAdvanced(self, event: wx.CommandEvent) -> None:
        """Handle advanced button click to open manual lat/lon dialog.

        Args:
            event: Button event

        """
        dialog = AdvancedLocationDialog(self, lat=self.latitude, lon=self.longitude)

        if dialog.ShowModal() == wx.ID_OK:
            lat, lon = dialog.GetValues()
            if lat is not None and lon is not None:
                self.latitude = lat
                self.longitude = lon
                if self.validator:
                    self.validator.update_coordinates(lat, lon)

                from .geocoding_manager import SearchResultHandler

                self.result_text.SetValue(SearchResultHandler.format_custom_coordinates(lat, lon))

        dialog.Destroy()

    def OnOK(self, event: wx.CommandEvent) -> None:
        """Handle OK button event.

        Args:
            event: Button event

        """
        if self.validator and self.validator.validate_for_save():
            event.Skip()  # Continue with default handler

    def OnClose(self, event: wx.CloseEvent) -> None:
        """Handle dialog close event.

        Args:
            event: Close event

        """
        self.geocoding_manager.stop_search()
        event.Skip()

    def Destroy(self) -> bool:
        """Clean up resources before destroying the dialog."""
        self.geocoding_manager.cleanup()
        result = super().Destroy()
        return bool(result)

    def GetValues(self) -> tuple[str, float | None, float | None]:
        """Get the dialog values.

        Returns:
            Tuple of (name, latitude, longitude)

        """
        return self.name_ctrl.GetValue().strip(), self.latitude, self.longitude

    def _on_search_result(self, result: tuple[float, float, str] | None, query: str) -> None:
        """Handle search result callback.

        Args:
            result: Geocoding result tuple or None
            query: Original search query

        """
        lat, lon, result_text, detailed_name = self.result_processor.process_search_result(
            result, query
        )

        self.latitude = lat
        self.longitude = lon
        if self.validator:
            self.validator.update_coordinates(lat, lon)

        self.result_text.SetValue(result_text)

        # Auto-populate name field if it's empty and we have a detailed name
        if detailed_name and not self.name_ctrl.GetValue().strip():
            self.name_ctrl.SetValue(detailed_name)

    def _on_search_error(self, error_msg: str) -> None:
        """Handle search error callback.

        Args:
            error_msg: Error message

        """
        result_text = self.result_processor.process_search_error(error_msg)
        self.result_text.SetValue(result_text)
        self.latitude = None
        self.longitude = None
        if self.validator:
            self.validator.update_coordinates(None, None)

    def _fetch_search_suggestions(self, query: str) -> None:
        """Fetch location suggestions for the search list.

        Args:
            query: Search query string

        """
        # Clear the list
        self.search_results_list.DeleteAllItems()

        # Get suggestions from geocoding manager
        suggestions = self.geocoding_manager.get_suggestions(query)
        self._update_search_results(suggestions)

    def _update_search_results(self, suggestions: list) -> None:
        """Update the search results list with suggestions.

        Args:
            suggestions: List of location suggestions

        """
        # Clear the list
        self.search_results_list.DeleteAllItems()

        # Add suggestions to the list
        for i, suggestion in enumerate(suggestions):
            from .geocoding_manager import SearchResultHandler

            # Use the full address for display
            display_name = SearchResultHandler.create_detailed_location_name(suggestion, suggestion)
            self.search_results_list.InsertItem(i, display_name)

    def _update_search_field_choices(self) -> None:
        """Update the search field combobox with the current search history."""
        # Clear the combobox
        self.search_field.Clear()

        # Add the search history items
        history = self.geocoding_manager.get_search_history()
        if history:
            self.search_field.Append(history)

    def _on_combobox_select(self, event: wx.CommandEvent) -> None:
        """Handle combobox selection event.

        Args:
            event: Combobox event

        """
        # Get the selected item
        selection = self.search_field.GetSelection()
        if selection != wx.NOT_FOUND:
            selected_text = self.search_field.GetString(selection)
            # Update UI to show searching state
            self.result_text.SetValue(f"Searching for {selected_text}...")
            # Perform search with the selected text
            self.geocoding_manager.perform_search(selected_text)

    def _on_list_item_activated(self, event: wx.ListEvent) -> None:
        """Handle list item activation (double-click or Enter).

        Args:
            event: List event

        """
        # Get the selected item
        selection = event.GetIndex()
        if selection != wx.NOT_FOUND:
            selected_text = self.search_results_list.GetItemText(selection)
            # Update UI to show searching state
            self.result_text.SetValue(f"Searching for {selected_text}...")
            # Perform search with the selected text
            self.geocoding_manager.perform_search(selected_text)
