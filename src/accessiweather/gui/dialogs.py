"""Dialog components for AccessiWeather

This module provides dialog windows for user interaction.
"""

import logging
import threading

import wx

from accessiweather.geocoding import GeocodingService

from .ui_components import (
    AccessibleButton,
    AccessibleComboBox,
    AccessibleListCtrl,
    AccessibleStaticText,
    AccessibleTextCtrl,
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
            panel, value=str(lat) if lat is not None else "", label="Latitude"
        )
        lat_sizer.Add(lat_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lat_sizer.Add(self.lat_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lat_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Longitude field
        lon_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lon_label = AccessibleStaticText(panel, label="Longitude:")
        self.lon_ctrl = AccessibleTextCtrl(
            panel, value=str(lon) if lon is not None else "", label="Longitude"
        )
        lon_sizer.Add(lon_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        lon_sizer.Add(self.lon_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(lon_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Description for screen readers
        help_text = AccessibleStaticText(
            panel, label="Enter latitude and longitude in decimal format (e.g., 35.123, -80.456)"
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
                    wx.OK | wx.ICON_ERROR,
                )
                return

            if lon < -180 or lon > 180:
                wx.MessageBox(
                    "Longitude must be between -180 and 180 degrees",
                    "Validation Error",
                    wx.OK | wx.ICON_ERROR,
                )
                return

            # Continue with default handler
            event.Skip()

        except ValueError:
            wx.MessageBox(
                "Please enter valid numbers for latitude and longitude",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
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

    # Maximum number of items to keep in search history
    MAX_HISTORY_ITEMS = 10

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

        # Initialize geocoding service with increased timeout
        self.geocoding_service = GeocodingService(timeout=15)  # Increase timeout to 15 seconds
        self.latitude = lat
        self.longitude = lon
        self.search_history = []

        # Thread control for geocoding
        self.search_thread = None
        self.search_stop_event = threading.Event()

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

        # Location search (address or zip code) with combo box for history
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        search_label = AccessibleStaticText(panel, label="Search Location:")
        self.search_field = AccessibleComboBox(panel, label="Search by Address or ZIP Code")
        search_sizer.Add(search_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        search_sizer.Add(self.search_field, 1, wx.ALL | wx.EXPAND, 5)
        sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Search button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.search_button = AccessibleButton(panel, wx.ID_ANY, "Search")
        self.advanced_button = AccessibleButton(panel, wx.ID_ANY, "Advanced (Lat/Lon)")
        button_sizer.Add(self.search_button, 0, wx.ALL, 5)
        button_sizer.Add(self.advanced_button, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.CENTER, 5)

        # Search results list
        results_label = AccessibleStaticText(panel, label="Search Results:")
        sizer.Add(results_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.search_results_list = AccessibleListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            label="Search Results",
            size=(-1, 150),
        )
        # Set up columns for search results list
        self.search_results_list.InsertColumn(0, "Location")
        self.search_results_list.SetColumnWidth(0, 500)
        sizer.Add(self.search_results_list, 0, wx.ALL | wx.EXPAND, 10)

        # Result display
        self.result_text = AccessibleTextCtrl(
            panel, value="", style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 60)
        )
        self.result_text.set_label("Search Result")  # Use set_label instead of SetLabel
        sizer.Add(self.result_text, 0, wx.ALL | wx.EXPAND, 5)

        # Description for screen readers
        help_text = AccessibleStaticText(
            panel,
            label=(
                "Enter an address, city, or ZIP code to search for a location "
                "or select from recent searches"
            ),
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
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnSearchResultSelected, self.search_results_list)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # Bind combobox selection event
        self.search_field.Bind(wx.EVT_COMBOBOX, self._on_combobox_select)
        self._combobox_event_bound = True

    def OnSearchResultSelected(self, event):  # event is required by wx
        """Handle search result selection event

        Args:
            event: List item activated event
        """
        # Get selected item and perform search
        selected_index = event.GetIndex()
        if selected_index != -1:
            selected_value = self.search_results_list.GetItemText(selected_index, 0)
            if selected_value:
                self._perform_search(selected_value)

    def OnSearch(self, event):  # event is required by wx
        """Handle search button click

        Args:
            event: Button event
        """
        # Get search query
        query = self.search_field.GetValue().strip()
        if not query:
            wx.MessageBox(
                "Please enter an address, city, or ZIP code to search",
                "Search Error",
                wx.OK | wx.ICON_ERROR,
            )
            return

        # Perform the search
        self._perform_search(query)

        # Also get suggestions for the list
        self._fetch_search_suggestions(query)

    def _perform_search(self, query):
        """Perform location search

        Args:
            query: Search query string
        """
        # Update UI to show searching state
        self.result_text.SetValue(f"Searching for {query}...")

        # Add to search history immediately to update the combobox
        # This will be called again if the search is successful, but that's OK
        self._add_to_search_history(query)

        # Cancel any existing search
        if self.search_thread is not None and self.search_thread.is_alive():
            logger.debug("Cancelling in-progress location search")
            self.search_stop_event.set()
            # Don't join here as it may block the UI

        # Reset stop event for new search
        self.search_stop_event.clear()

        # Start a new thread to perform the search
        self.search_thread = threading.Thread(target=self._search_thread_func, args=(query,))
        self.search_thread.daemon = True
        self.search_thread.start()

    def _search_thread_func(self, query):
        """Thread function to perform location search

        Args:
            query: Search query string
        """
        try:
            # Check if we've been asked to stop
            if self.search_stop_event.is_set():
                logger.debug("Location search cancelled")
                return

            # Perform the geocoding
            logger.debug(f"Performing geocoding for query: {query}")
            result = self.geocoding_service.geocode_address(query)

            # Check again if we've been asked to stop before delivering results
            if self.search_stop_event.is_set():
                logger.debug("Location search completed but results discarded")
                return

            # Update the UI on the main thread
            wx.CallAfter(self._update_search_result, result, query)
        except Exception as e:
            if not self.search_stop_event.is_set():
                logger.error(f"Error during geocoding thread: {str(e)}")
                wx.CallAfter(self._update_search_error, str(e))

    def _create_detailed_location_name(self, address, query):
        """Create a more detailed location name from the full address

        Args:
            address: Full address from geocoding service
            query: Original search query

        Returns:
            A more detailed but concise location name
        """
        try:
            # If we have a full address, use it directly
            # This preserves all the useful context like county, state, country
            if address and ", " in address:
                return address
            else:
                # Fall back to the original query if no address is available
                return query
        except Exception as e:
            logger.error(f"Error creating detailed location name: {str(e)}")
            # Fall back to the original query
            return query

    def _update_search_result(self, result, query):
        """Update the UI with search results

        Args:
            result: Geocoding result (lat, lon, address) or None
            query: Original search query
        """
        try:
            if result:
                lat, lon, address = result
                self.latitude = lat
                self.longitude = lon
                self.result_text.SetValue(f"Found: {address}\nCoordinates: {lat}, {lon}")

                # Add to search history if not already in the list
                self._add_to_search_history(query)

                # Create a more detailed location name
                detailed_name = self._create_detailed_location_name(address, query)

                # Auto-populate name field if it's empty
                if not self.name_ctrl.GetValue().strip():
                    self.name_ctrl.SetValue(detailed_name)
            else:
                # Check if the query might be a ZIP code
                if self.geocoding_service.is_zip_code(query):
                    self.result_text.SetValue(
                        f"No results found for ZIP code: {query}\n\n"
                        f"Try adding city or state (e.g., '{query}, NY' or '{query}, Chicago')"
                    )
                else:
                    self.result_text.SetValue(
                        f"No results found for '{query}' or location is outside the US NWS coverage area."
                    )
                self.latitude = None
                self.longitude = None
        except Exception as e:
            logger.error(f"Error updating search result: {str(e)}")
            self._update_search_error(str(e))

    def _update_search_error(self, error_msg):
        """Update the UI with an error message

        Args:
            error_msg: Error message to display
        """
        # Check if it's a timeout error
        if "timeout" in str(error_msg).lower():
            self.result_text.SetValue(
                "Search timed out. The geocoding service may be busy.\n"
                "Please try again in a moment or try a more specific search term."
            )
        else:
            self.result_text.SetValue(f"Error during search: {error_msg}")

        self.latitude = None
        self.longitude = None

    def _fetch_search_suggestions(self, query):
        """Fetch location suggestions for the search list

        Args:
            query: Search query string
        """
        # Clear the list
        self.search_results_list.DeleteAllItems()

        # Get suggestions from geocoding service
        try:
            suggestions = self.geocoding_service.suggest_locations(query)
            self._update_search_results(suggestions)
        except Exception as e:
            logger.error(f"Error fetching search suggestions: {e}")

    def _update_search_results(self, suggestions):
        """Update the search results list with suggestions

        Args:
            suggestions: List of location suggestions
        """
        # Clear the list
        self.search_results_list.DeleteAllItems()

        # Add suggestions to the list
        for i, suggestion in enumerate(suggestions):
            # Use the full address for the search but display a more readable version
            # This ensures we still search with the complete address when selected
            display_name = self._create_detailed_location_name(suggestion, suggestion)
            self.search_results_list.InsertItem(i, display_name)

            # Store the full address as item data for later retrieval
            # We can't use SetItemData with strings, so we'll use the display name
            # and rely on the geocoding service to handle the search

    def _add_to_search_history(self, query):
        """Add query to search history

        Args:
            query: Search query to add
        """
        # Remove the query if it already exists in history
        if query in self.search_history:
            self.search_history.remove(query)

        # Add query to beginning of history list
        self.search_history.insert(0, query)

        # Limit the size of history
        if len(self.search_history) > self.MAX_HISTORY_ITEMS:
            self.search_history = self.search_history[: self.MAX_HISTORY_ITEMS]

        # Update the combobox with the current history
        self._update_search_field_choices()

    def _update_search_field_choices(self):
        """Update the search field combobox with the current search history"""
        # Clear the combobox
        self.search_field.Clear()

        # Add the search history items
        if self.search_history:
            self.search_field.Append(self.search_history)

    def _on_combobox_select(self, event):  # noqa: F841
        """Handle combobox selection event

        Args:
            event: Combobox event
        """
        # Get the selected item
        selection = self.search_field.GetSelection()
        if selection != wx.NOT_FOUND:
            selected_text = self.search_field.GetString(selection)
            # Perform search with the selected text
            self._perform_search(selected_text)

    def OnAdvanced(self, event):  # event is required by wx
        """Handle advanced button click to open manual lat/lon dialog

        Args:
            event: Button event
        """
        # Get current lat/lon if available
        current_lat = self.latitude
        current_lon = self.longitude

        # Create and show advanced dialog
        dialog = AdvancedLocationDialog(self, lat=current_lat, lon=current_lon)

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
                "Please enter a name for the location", "Validation Error", wx.OK | wx.ICON_ERROR
            )
            return

        if self.latitude is None or self.longitude is None:
            wx.MessageBox(
                "Please search for a location or enter coordinates manually",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
            )
            return

        # Continue with default handler
        event.Skip()

    def OnClose(self, event):
        """Handle dialog close event

        Args:
            event: Close event
        """
        # Stop any running search thread
        if self.search_thread is not None and self.search_thread.is_alive():
            logger.debug("Stopping search thread due to dialog close")
            self.search_stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.search_thread.join(0.5)

        # No need to stop autocomplete thread as we're not using autocomplete anymore

        # Continue with default close handler
        event.Skip()

    def Destroy(self):
        """Clean up resources before destroying the dialog"""
        # Stop any running search thread
        if self.search_thread is not None and self.search_thread.is_alive():
            logger.debug("Stopping search thread in Destroy")
            self.search_stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.search_thread.join(0.5)

        # No need to stop autocomplete thread as we're not using autocomplete anymore

        # Call the parent class Destroy method
        super().Destroy()

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

        # Log the discussion text for debugging
        logger.debug(
            f"Creating discussion dialog with text type: {type(text)}, length: {len(text)}"
        )
        if not text:
            logger.warning("Empty discussion text provided to dialog")
            text = "No discussion available"
        else:
            # Log a preview of the text
            preview = text[:100].replace("\n", "\\n")
            logger.debug(f"Text preview: {preview}...")

        try:
            logger.debug("Creating panel for discussion dialog")
            panel = wx.Panel(self)
            sizer = wx.BoxSizer(wx.VERTICAL)

            # Create a text control for the discussion
            logger.debug("Creating text control for discussion dialog")
            self.text_ctrl = wx.TextCtrl(
                panel, style=wx.TE_MULTILINE | wx.TE_READONLY  # Removed wx.TE_RICH2
            )

            # Set a monospace font for better readability of formatted text
            logger.debug("Setting font for text control")
            font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self.text_ctrl.SetFont(font)

            # Normalize line endings for consistent screen reader behavior
            if isinstance(text, str):
                text = text.replace("\r\n", "\n").replace("\r", "\n")

            # Set the text after setting the font
            logger.debug(f"Setting text value (length: {len(text)})")
            self.text_ctrl.SetValue(text)
            logger.debug("Text value set successfully")
        except Exception as e:
            logger.error(f"Error creating discussion dialog components: {e}")
            raise

        try:
            # Set accessible name and description
            logger.debug("Setting accessible name for text control")
            self.text_ctrl.SetName("Weather Discussion Text")

            # Get accessible object
            logger.debug("Getting accessible object for text control")
            accessible = self.text_ctrl.GetAccessible()
            if accessible:
                logger.debug("Setting accessible properties")
                accessible.SetName("Weather Discussion Text")
                accessible.SetRole(wx.ACC_ROLE_TEXT)

            # Add to sizer with expansion
            logger.debug("Adding text control to sizer")
            sizer.Add(self.text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

            # Close button
            logger.debug("Creating close button")
            close_button = AccessibleButton(panel, wx.ID_CLOSE, "Close")
            sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

            logger.debug("Setting panel sizer")
            panel.SetSizer(sizer)

            logger.debug("Setting dialog size")
            self.SetSize((800, 600))
            logger.debug("Dialog size set successfully")
        except Exception as e:
            logger.error(f"Error finalizing discussion dialog setup: {e}")
            raise

        try:
            # Center on parent
            logger.debug("Centering dialog on parent")
            self.CenterOnParent()

            # Bind events
            logger.debug("Binding close button event")
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CLOSE)

            # Set initial focus for accessibility
            logger.debug("Setting initial focus to text control")
            self.text_ctrl.SetFocus()
            logger.debug("WeatherDiscussionDialog initialization complete")
        except Exception as e:
            logger.error(f"Error in final dialog setup: {e}")

    def OnClose(self, event):  # event is required by wx
        """Handle close button event

        Args:
            event: Button event
        """
        logger.debug("Close button clicked, ending modal dialog")
        try:
            self.EndModal(wx.ID_CLOSE)
            logger.debug("Dialog closed successfully")
        except Exception as e:
            logger.error(f"Error closing dialog: {e}")


class NationalDiscussionDialog(wx.Dialog):
    """Dialog for displaying national forecast discussions with a tabbed interface for accessibility."""

    def __init__(self, parent, national_data):
        """Initialize the dialog.

        Args:
            parent: Parent window
            national_data: Dictionary with national forecast data containing WPC and SPC discussions
        """
        super().__init__(
            parent,
            title="National Weather Discussions",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(800, 600),
        )

        self.national_data = national_data
        self._init_ui()
        self.Center()

    def _init_ui(self):
        """Initialize the dialog UI with a tabbed interface for accessibility."""
        logger.debug("Initializing NationalDiscussionDialog UI")

        try:
            # Create main panel and sizer
            panel = wx.Panel(self)
            main_sizer = wx.BoxSizer(wx.VERTICAL)

            # Get the discussion data
            summaries = self.national_data.get("national_discussion_summaries", {})

            # Store the discussion texts for both sources
            self.wpc_text = summaries.get("wpc", {}).get(
                "short_range_full", "WPC discussion unavailable"
            )
            self.spc_text = summaries.get("spc", {}).get("day1_full", "SPC discussion unavailable")

            # Normalize line endings for both texts
            if isinstance(self.wpc_text, str):
                self.wpc_text = self.wpc_text.replace("\r\n", "\n").replace("\r", "\n")
            if isinstance(self.spc_text, str):
                self.spc_text = self.spc_text.replace("\r\n", "\n").replace("\r", "\n")

            # Create notebook (tabbed interface)
            self.notebook = wx.Notebook(panel)
            self.notebook.SetName("National Discussion Tabs")

            # Create WPC tab
            wpc_panel = wx.Panel(self.notebook)
            wpc_sizer = wx.BoxSizer(wx.VERTICAL)

            # Create text control for WPC discussion
            self.wpc_text_ctrl = wx.TextCtrl(
                wpc_panel,
                style=wx.TE_MULTILINE | wx.TE_READONLY,
                size=(-1, 450),
            )

            # Set accessible name and role
            self.wpc_text_ctrl.SetName("WPC Discussion Text")
            accessible = self.wpc_text_ctrl.GetAccessible()
            if accessible:
                accessible.SetName("Weather Prediction Center Discussion Text")
                accessible.SetRole(wx.ACC_ROLE_TEXT)

            # Set monospace font for better readability
            font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self.wpc_text_ctrl.SetFont(font)

            # Set the WPC discussion text
            self.wpc_text_ctrl.SetValue(self.wpc_text)

            # Add text control to WPC panel sizer
            wpc_sizer.Add(self.wpc_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
            wpc_panel.SetSizer(wpc_sizer)

            # Create SPC tab
            spc_panel = wx.Panel(self.notebook)
            spc_sizer = wx.BoxSizer(wx.VERTICAL)

            # Create text control for SPC discussion
            self.spc_text_ctrl = wx.TextCtrl(
                spc_panel,
                style=wx.TE_MULTILINE | wx.TE_READONLY,
                size=(-1, 450),
            )

            # Set accessible name and role
            self.spc_text_ctrl.SetName("SPC Discussion Text")
            accessible = self.spc_text_ctrl.GetAccessible()
            if accessible:
                accessible.SetName("Storm Prediction Center Discussion Text")
                accessible.SetRole(wx.ACC_ROLE_TEXT)

            # Set monospace font for better readability
            self.spc_text_ctrl.SetFont(font)

            # Set the SPC discussion text
            self.spc_text_ctrl.SetValue(self.spc_text)

            # Add text control to SPC panel sizer
            spc_sizer.Add(self.spc_text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
            spc_panel.SetSizer(spc_sizer)

            # Add tabs to notebook
            self.notebook.AddPage(wpc_panel, "Weather Prediction Center")
            self.notebook.AddPage(spc_panel, "Storm Prediction Center")

            # Add notebook to main sizer
            main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

            # Add close button
            close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
            close_btn.SetName("Close Button")
            main_sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)

            # Set the sizer for the panel
            panel.SetSizer(main_sizer)

            # Bind events
            self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)
            close_btn.Bind(wx.EVT_BUTTON, self.on_close)

            # Set initial focus to the notebook for accessibility
            # This allows users to tab to the text control
            self.notebook.SetFocus()

            # Store references for easier access
            self.close_btn = close_btn

            logger.debug("NationalDiscussionDialog UI initialization complete")
        except Exception as e:
            logger.error(f"Error initializing NationalDiscussionDialog UI: {e}")
            wx.MessageBox(
                f"Error creating national discussion dialog: {e}",
                "Dialog Error",
                wx.OK | wx.ICON_ERROR,
            )
            raise

    def on_tab_changed(self, event):
        """Handle tab selection change.

        Args:
            event: Notebook page changed event
        """
        # Simply allow the event to propagate
        # This lets the user tab to the text control instead of automatically setting focus to it
        event.Skip()

    def on_close(self, event):  # event is required by wx
        """Handle close button event.

        Args:
            event: Button event
        """
        logger.debug("Close button clicked, ending modal dialog")
        try:
            self.EndModal(wx.ID_CLOSE)
            logger.debug("Dialog closed successfully")
        except Exception as e:
            logger.error(f"Error closing dialog: {e}")
