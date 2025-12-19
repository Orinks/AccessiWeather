"""
Location dialog for AccessiWeather Simple.

This module provides dialogs for adding and managing locations in the Toga application.
"""
# Advanced coordinates dialog work is tracked in #315.

import asyncio
import logging

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from ..location_manager import LocationManager

logger = logging.getLogger(__name__)


class AddLocationDialog:
    """Dialog for adding a new location with search functionality."""

    def __init__(self, app, config_manager):
        """
        Initialize the add location dialog.

        Args:
        ----
            app: The main application instance
            config_manager: Configuration manager instance

        """
        self.app = app
        self.config_manager = config_manager
        self.location_manager = LocationManager()

        # Dialog state
        self.dialog_window = None
        self.search_results = []
        self.selected_location = None
        self.is_searching = False

        # UI components
        self.name_input = None
        self.search_input = None
        self.search_button = None
        self.results_table = None
        self.coordinates_input = ""  # Track coordinates internally
        self.status_label = None
        self.save_button = None
        self.cancel_button = None
        self.advanced_button = None

        # Result future for async dialog handling
        self._result_future = None

    async def show_and_wait(self):
        """Show the dialog and wait for user interaction."""
        self._create_dialog()

        # Ensure window is registered with app before showing
        if self.dialog_window not in self.app.windows:
            self.app.windows.add(self.dialog_window)

        self.dialog_window.show()

        # Set initial focus for accessibility after dialog is shown
        # Small delay to ensure dialog is fully rendered before setting focus
        await asyncio.sleep(0.1)
        if self.name_input:
            self.name_input.focus()
            logger.info("Set initial focus to location name input for accessibility")

        # Create future for result
        self._result_future = asyncio.Future()

        # Wait for the result
        try:
            return await self._result_future
        except asyncio.CancelledError:
            return False

    def _create_dialog(self):
        """Create the dialog UI."""
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=15))

        # Title
        title_label = toga.Label(
            "Add New Location", style=Pack(font_size=16, font_weight="bold", margin_bottom=15)
        )
        main_box.add(title_label)

        # Location name section
        name_section = self._create_name_section()
        main_box.add(name_section)

        # Search section
        search_section = self._create_search_section()
        main_box.add(search_section)

        # Results section
        results_section = self._create_results_section()
        main_box.add(results_section)

        # Status section
        status_section = self._create_status_section()
        main_box.add(status_section)

        # Buttons section
        buttons_section = self._create_buttons_section()
        main_box.add(buttons_section)

        # Create dialog window
        self.dialog_window = toga.Window(
            title="Add Location", content=main_box, size=(600, 500), resizable=True
        )

    def _create_name_section(self) -> toga.Box:
        """Create the location name input section."""
        section = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))

        name_label = toga.Label("Location Name:", style=Pack(font_weight="bold", margin_bottom=5))
        section.add(name_label)

        self.name_input = toga.TextInput(
            placeholder="Enter a descriptive name for this location",
            style=Pack(width=400, margin_bottom=5),
        )
        section.add(self.name_input)

        help_text = toga.Label(
            "This name will appear in your location list",
            style=Pack(font_style="italic", font_size=10, margin_bottom=10),
        )
        section.add(help_text)

        return section

    def _create_search_section(self) -> toga.Box:
        """Create the location search section."""
        section = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))

        search_label = toga.Label(
            "Search for Location:", style=Pack(font_weight="bold", margin_bottom=5)
        )
        section.add(search_label)

        search_box = toga.Box(style=Pack(direction=ROW, margin_bottom=5))

        self.search_input = toga.TextInput(
            placeholder="City name or ZIP/postal code", style=Pack(flex=1, margin_right=10)
        )
        search_box.add(self.search_input)

        self.search_button = toga.Button(
            "Search", on_press=self._on_search_pressed, style=Pack(width=80)
        )

        search_box.add(self.search_button)

        section.add(search_box)

        search_help = toga.Label(
            "Examples: 'New York', '10001', 'London'",
            style=Pack(font_style="italic", font_size=10, margin_bottom=10),
        )
        section.add(search_help)

        return section

    def _create_results_section(self) -> toga.Box:
        """Create the search results section."""
        section = toga.Box(style=Pack(direction=COLUMN, margin_bottom=10))

        results_label = toga.Label(
            "Search Results:", style=Pack(font_weight="bold", margin_bottom=5)
        )
        section.add(results_label)

        self.results_table = toga.Table(
            headings=["Location", "Coordinates"],
            data=[],
            style=Pack(height=150, margin_bottom=10),
            on_select=self._on_result_selected,
        )
        section.add(self.results_table)

        return section

    def _create_status_section(self) -> toga.Box:
        """Create the status display section."""
        section = toga.Box(style=Pack(direction=COLUMN, margin_bottom=15))

        self.status_label = toga.Label(
            "Ready to add location", style=Pack(font_style="italic", margin_bottom=5)
        )
        section.add(self.status_label)

        return section

    def _create_buttons_section(self) -> toga.Box:
        """Create the dialog buttons section."""
        section = toga.Box(style=Pack(direction=ROW, margin_top=10))

        # Spacer to push buttons to the right
        spacer = toga.Box(style=Pack(flex=1))
        section.add(spacer)

        self.cancel_button = toga.Button(
            "Cancel", on_press=self._on_cancel_pressed, style=Pack(margin_right=10)
        )

        section.add(self.cancel_button)

        self.save_button = toga.Button(
            "Save Location", on_press=self._on_save_pressed, style=Pack()
        )

        section.add(self.save_button)

        return section

    async def _on_search_pressed(self, widget):
        """Handle search button press."""
        query = self.search_input.value.strip()
        if not query:
            self._update_status("Please enter a search term")
            return

        if self.is_searching:
            self._update_status("Search already in progress...")
            return

        self.is_searching = True
        self.search_button.enabled = False
        self._update_status(f"Searching for '{query}'...")

        try:
            # Clear previous results
            self.results_table.data = []
            self.search_results = []

            # Perform search
            locations = await self.location_manager.search_locations(query, limit=10)

            if locations:
                # Populate results table
                table_data = []
                for location in locations:
                    coords_str = self.location_manager.format_coordinates(
                        location.latitude, location.longitude
                    )
                    table_data.append((location.name, coords_str))

                self.results_table.data = table_data
                self.search_results = locations
                self._update_status(f"Found {len(locations)} locations")

                # Auto-fill name if empty
                if not self.name_input.value.strip() and locations:
                    self.name_input.value = locations[0].name
            else:
                self._update_status("No locations found. Try a different search term.")

        except Exception as e:
            logger.error(f"Search failed: {e}")
            self._update_status(f"Search failed: {e}")

        finally:
            self.is_searching = False
            self.search_button.enabled = True

    def _on_result_selected(self, widget):
        """Handle selection of a search result."""
        if not widget.selection or not self.search_results:
            return

        try:
            # Get selected row index
            selected_row = widget.selection
            row_index = widget.data.index(selected_row)

            if 0 <= row_index < len(self.search_results):
                self.selected_location = self.search_results[row_index]

                # Update name to match the selected location
                self.name_input.value = self.selected_location.name

                # Update coordinates internally
                self.coordinates_input = (
                    f"{self.selected_location.latitude}, {self.selected_location.longitude}"
                )

                self._update_status(f"Selected: {self.selected_location.name}")

        except Exception as e:
            logger.error(f"Error selecting result: {e}")
            self._update_status("Error selecting location")

    async def _on_advanced_pressed(self, widget):
        """Handle advanced coordinates button press."""
        await self._show_coordinates_dialog()

    async def _show_coordinates_dialog(self):
        """Show a dialog for manual coordinate entry."""
        # Create dialog content
        dialog_box = toga.Box(style=Pack(direction=COLUMN, margin=15))

        # Instructions
        instructions = toga.Label(
            "Enter coordinates manually.\n"
            "Accepted formats: decimal degrees with or without "
            "degree symbols and N/S/E/W suffixes\n"
            "Examples: 40.7128, -74.0060 or 40.7128°N, 74.0060°W",
            style=Pack(margin_bottom=15, font_size=10),
        )
        dialog_box.add(instructions)

        # Coordinates input
        coords_input = toga.TextInput(
            placeholder="e.g., 40.7128, -74.0060",
            value=self.coordinates_input if self.coordinates_input else "",
            style=Pack(width=300, margin_bottom=15),
        )
        dialog_box.add(coords_input)

        # Buttons
        button_box = toga.Box(style=Pack(direction=ROW, margin_top=15))
        spacer = toga.Box(style=Pack(flex=1))
        button_box.add(spacer)

        cancel_btn = toga.Button("Cancel", style=Pack(margin_right=10))
        save_btn = toga.Button("Save Coordinates")

        button_box.add(cancel_btn)
        button_box.add(save_btn)
        dialog_box.add(button_box)

        # Create and show dialog window
        coords_dialog = toga.Window(title="Enter Coordinates", content=dialog_box, size=(400, 200))

        # Handle button actions
        def on_save(widget):
            coords_text = coords_input.value.strip()
            if coords_text:
                coords = self.location_manager.parse_coordinates(coords_text)
                if coords:
                    latitude, longitude = coords
                    self.coordinates_input = f"{latitude}, {longitude}"
                    self.selected_location = None  # Clear auto-selected location
                    self._update_status("Coordinates updated")
                    coords_dialog.close()
                else:
                    self._update_status("Invalid coordinate format")
            else:
                coords_dialog.close()

        def on_cancel(widget):
            coords_dialog.close()

        save_btn.on_press = on_save
        cancel_btn.on_press = on_cancel

        coords_dialog.show()

    async def _on_save_pressed(self, widget):
        """Handle save button press."""
        # Validate inputs
        name = self.name_input.value.strip()
        if not name:
            self._update_status("Please enter a location name")
            return

        # Get coordinates
        coords = None
        if self.selected_location:
            coords = (self.selected_location.latitude, self.selected_location.longitude)
        else:
            # Try to parse manual coordinates
            coords_text = (
                self.coordinates_input.strip() if isinstance(self.coordinates_input, str) else ""
            )
            if coords_text:
                coords = self.location_manager.parse_coordinates(coords_text)

        if not coords:
            self._update_status("Please search for a location or enter coordinates manually")
            return

        latitude, longitude = coords

        # Validate coordinates
        if not self.location_manager.validate_coordinates(latitude, longitude):
            self._update_status(
                "Invalid coordinates. Latitude must be -90 to 90, longitude -180 to 180"
            )
            return

        # Check if location already exists
        existing_names = self.config_manager.get_location_names()
        if name in existing_names:
            self._update_status("A location with this name already exists")
            return

        try:
            country_code = None
            if self.selected_location and getattr(self.selected_location, "country_code", None):
                country_code = self.selected_location.country_code
            elif not self.selected_location:
                try:
                    reverse_location = await self.location_manager.reverse_geocode(
                        latitude, longitude
                    )
                    if reverse_location and reverse_location.country_code:
                        country_code = reverse_location.country_code
                except Exception as geo_exc:  # pragma: no cover - best effort enrichment
                    logger.debug("Reverse geocoding for country code failed: %s", geo_exc)

            # Add location
            success = self.config_manager.add_location(
                name, latitude, longitude, country_code=country_code
            )

            if success:
                self._update_status("Location saved successfully!")
                # Close dialog with the name of the added location
                self._close_dialog(name)
            else:
                self._update_status("Failed to save location")

        except Exception as e:
            logger.error(f"Failed to save location: {e}")
            self._update_status(f"Error saving location: {e}")

    async def _on_cancel_pressed(self, widget):
        """Handle cancel button press."""
        self._close_dialog(None)

    def _update_status(self, message: str):
        """Update the status label."""
        if self.status_label:
            self.status_label.text = message
            logger.info(f"Location dialog status: {message}")

    def _close_dialog(self, result: str | None):
        """
        Close the dialog and set the result.

        Args:
            result: The name of the added location, or None if cancelled.

        """
        if self._result_future and not self._result_future.done():
            self._result_future.set_result(result)

        if self.dialog_window:
            self.dialog_window.close()
