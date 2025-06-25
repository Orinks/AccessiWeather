"""Settings dialog for AccessiWeather Toga application.

This module provides a comprehensive settings dialog with tabbed interface
matching the functionality of the wxPython version.
"""

import logging

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from ..models import AppSettings

logger = logging.getLogger(__name__)


class SettingsDialog:
    """Settings dialog with tabbed interface for configuration options."""

    def __init__(self, app: toga.App, config_manager):
        self.app = app
        self.config_manager = config_manager
        self.window = None  # Will be created fresh each time dialog is shown
        self.future = None  # Will be created fresh each time dialog is shown

        # Current settings (working copy)
        self.current_settings = None

        # UI components
        self.option_container = None
        self.general_tab = None
        self.display_tab = None
        self.advanced_tab = None
        self.updates_tab = None

        # General tab controls
        self.data_source_selection = None
        self.update_interval_input = None
        self.show_detailed_forecast_switch = None
        self.enable_alerts_switch = None

        # Display tab controls
        self.temperature_unit_selection = None

        # Advanced tab controls
        self.minimize_to_tray_switch = None

        # Updates tab controls (placeholder for future implementation)
        self.auto_update_switch = None

    def __await__(self):
        """Make the dialog awaitable for modal behavior."""
        if self.future is None:
            raise RuntimeError("Dialog future not initialized. Call show_and_prepare() first.")
        return self.future.__await__()

    def show_and_prepare(self):
        """Prepare and show the settings dialog."""
        logger.info("Showing settings dialog")

        try:
            # Create a fresh future for this dialog session
            self.future = self.app.loop.create_future()

            # Create a fresh window instance
            self.window = toga.Window(
                title="AccessiWeather Settings",
                size=(600, 500),
                resizable=True,
                minimizable=False,
                closable=False,  # Prevent closing via X button to enforce modal behavior
            )

            # Load current settings
            self.current_settings = self.config_manager.get_settings()
            logger.debug(f"Loaded settings: {self.current_settings}")

            # Create dialog content
            self._create_dialog_content()

            # Show the dialog
            self.window.show()

            # Set initial focus to the first interactive control for accessibility
            self._set_initial_focus()

        except Exception as e:
            logger.error(f"Failed to show settings dialog: {e}", exc_info=True)
            if self.future and not self.future.done():
                self.future.set_exception(e)

    def _create_dialog_content(self):
        """Create the settings dialog content."""
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Create tabbed interface
        self.option_container = toga.OptionContainer(style=Pack(flex=1))

        # Create tabs
        self._create_general_tab()
        self._create_display_tab()
        self._create_advanced_tab()
        self._create_updates_tab()

        main_box.add(self.option_container)

        # Button row
        button_box = toga.Box(style=Pack(direction=ROW, margin_top=10))

        # Add flexible space to push buttons to the right
        button_box.add(toga.Box(style=Pack(flex=1)))

        # Cancel button
        cancel_button = toga.Button(
            "Cancel", on_press=self._on_cancel, style=Pack(margin_right=10), id="cancel_button"
        )
        button_box.add(cancel_button)

        # OK button
        ok_button = toga.Button(
            "OK", on_press=self._on_ok, style=Pack(margin_right=0), id="ok_button"
        )
        button_box.add(ok_button)

        main_box.add(button_box)

        # Set window content
        self.window.content = main_box

    def _create_general_tab(self):
        """Create the General settings tab."""
        general_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Data Source Selection
        general_box.add(toga.Label("Weather Data Source:", style=Pack(margin_bottom=5)))

        # Define data source options
        data_source_options = [
            "Automatic (NWS for US, Open-Meteo for non-US)",
            "National Weather Service (NWS)",
            "Open-Meteo (International)",
        ]

        self.data_source_selection = toga.Selection(
            items=data_source_options,
            style=Pack(margin_bottom=15),
            id="data_source_selection",
        )

        # Set current value based on stored configuration
        data_source_map = {
            "auto": 0,
            "nws": 1,
            "openmeteo": 2,
        }

        try:
            current_data_source = self.current_settings.data_source
            selected_index = data_source_map.get(current_data_source, 0)
            self.data_source_selection.value = data_source_options[selected_index]
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to set data source selection: {e}, using default")
            self.data_source_selection.value = data_source_options[0]

        general_box.add(self.data_source_selection)

        # Update Interval
        general_box.add(toga.Label("Update Interval (minutes):", style=Pack(margin_bottom=5)))
        self.update_interval_input = toga.NumberInput(
            value=self.current_settings.update_interval_minutes,
            style=Pack(margin_bottom=15),
            id="update_interval_input",
        )
        general_box.add(self.update_interval_input)

        # Show Detailed Forecast
        self.show_detailed_forecast_switch = toga.Switch(
            "Show detailed forecast information",
            value=self.current_settings.show_detailed_forecast,
            style=Pack(margin_bottom=10),
            id="show_detailed_forecast_switch",
        )
        general_box.add(self.show_detailed_forecast_switch)

        # Enable Alerts
        self.enable_alerts_switch = toga.Switch(
            "Enable weather alerts",
            value=self.current_settings.enable_alerts,
            style=Pack(margin_bottom=10),
            id="enable_alerts_switch",
        )
        general_box.add(self.enable_alerts_switch)

        # Add tab to container
        self.option_container.content.append("General", general_box)

    def _create_display_tab(self):
        """Create the Display settings tab."""
        display_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Temperature Unit Selection
        display_box.add(toga.Label("Temperature Display:", style=Pack(margin_bottom=5)))

        # Define temperature unit options
        temp_unit_options = [
            "Fahrenheit only",
            "Celsius only",
            "Both (Fahrenheit and Celsius)",
        ]

        self.temperature_unit_selection = toga.Selection(
            items=temp_unit_options,
            style=Pack(margin_bottom=15),
            id="temperature_unit_selection",
        )

        # Set current value based on stored configuration
        temp_unit_map = {
            "f": 0,
            "c": 1,
            "both": 2,
        }

        try:
            current_temp_unit = self.current_settings.temperature_unit
            selected_index = temp_unit_map.get(current_temp_unit, 2)
            self.temperature_unit_selection.value = temp_unit_options[selected_index]
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to set temperature unit selection: {e}, using default")
            self.temperature_unit_selection.value = temp_unit_options[2]  # Default to "Both"

        display_box.add(self.temperature_unit_selection)

        # Add placeholder for future display options
        display_box.add(
            toga.Label(
                "Additional display options will be added in future versions.",
                style=Pack(margin_top=20, font_style="italic"),
            )
        )

        # Add tab to container
        self.option_container.content.append("Display", display_box)

    def _create_advanced_tab(self):
        """Create the Advanced settings tab."""
        advanced_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Minimize to Tray (note: not applicable to all platforms)
        self.minimize_to_tray_switch = toga.Switch(
            "Minimize to system tray when closing (Windows only)",
            value=self.current_settings.minimize_to_tray,
            style=Pack(margin_bottom=10),
            id="minimize_to_tray_switch",
        )
        advanced_box.add(self.minimize_to_tray_switch)

        # Add placeholder for future advanced options
        advanced_box.add(
            toga.Label(
                "Additional advanced options will be added in future versions.",
                style=Pack(margin_top=20, font_style="italic"),
            )
        )

        # Add tab to container
        self.option_container.content.append("Advanced", advanced_box)

    def _create_updates_tab(self):
        """Create the Updates settings tab."""
        updates_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Auto-update placeholder
        self.auto_update_switch = toga.Switch(
            "Check for updates automatically (not yet implemented)",
            value=False,
            enabled=False,
            style=Pack(margin_bottom=10),
        )
        updates_box.add(self.auto_update_switch)

        # Add placeholder text
        updates_box.add(
            toga.Label(
                "Update functionality will be implemented in future versions.",
                style=Pack(margin_top=20, font_style="italic"),
            )
        )

        # Add tab to container
        self.option_container.content.append("Updates", updates_box)

    def _set_initial_focus(self):
        """Set initial focus to the first interactive control for accessibility."""
        try:
            # Set focus to the first interactive control (data source selection)
            # This ensures keyboard and screen reader users start at a logical point
            if self.data_source_selection:
                self.data_source_selection.focus()
                logger.debug("Set initial focus to data source selection")
            else:
                logger.warning("Data source selection not available for focus")
        except Exception as e:
            logger.warning(f"Failed to set initial focus: {e}")
            # Fallback: try to focus the option container itself
            try:
                if self.option_container:
                    self.option_container.focus()
                    logger.debug("Set fallback focus to option container")
            except Exception as fallback_error:
                logger.warning(f"Fallback focus also failed: {fallback_error}")

    def _return_focus_to_trigger(self):
        """Return focus to the element that triggered the dialog."""
        try:
            # In Toga, we can't directly control focus return to menu items,
            # but we can ensure the main window gets focus
            if self.app.main_window:
                self.app.main_window.focus()
                logger.debug("Returned focus to main window")
        except Exception as e:
            logger.warning(f"Failed to return focus: {e}")

    async def _on_ok(self, widget):
        """Handle OK button press - save settings and close dialog."""
        logger.info("Settings dialog OK button pressed")

        try:
            # Collect settings from UI
            new_settings = self._collect_settings_from_ui()

            # Update configuration
            success = self.config_manager.update_settings(**new_settings.to_dict())

            if success:
                logger.info("Settings saved successfully")
                # Set result and close dialog
                if self.future and not self.future.done():
                    self.future.set_result(True)
                if self.window:
                    self.window.close()
                    self.window = None  # Clear reference to help with cleanup
                # No confirmation dialog - let focus return directly to main window
            else:
                logger.error("Failed to save settings")
                await self.app.main_window.error_dialog(
                    "Settings Error", "Failed to save settings."
                )

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            # Don't close dialog on error, let user try again or cancel
            await self.app.main_window.error_dialog("Settings Error", f"Error saving settings: {e}")

    async def _on_cancel(self, widget):
        """Handle Cancel button press - close dialog without saving."""
        logger.info("Settings dialog cancelled")
        if self.future and not self.future.done():
            self.future.set_result(False)
        if self.window:
            self.window.close()
            self.window = None  # Clear reference to help with cleanup

    def _collect_settings_from_ui(self) -> AppSettings:
        """Collect current settings from UI controls."""
        # Map data source selection back to internal values
        data_source_reverse_map = {
            0: "auto",
            1: "nws",
            2: "openmeteo",
        }

        try:
            # Get the selected value and map it directly to internal values
            selected_value = str(self.data_source_selection.value)
            if "Automatic" in selected_value:
                data_source = "auto"
            elif "National Weather Service" in selected_value:
                data_source = "nws"
            elif "Open-Meteo" in selected_value:
                data_source = "openmeteo"
            else:
                data_source = "auto"  # Default fallback
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get data source selection: {e}, using default")
            data_source = "auto"

        # Map temperature unit selection back to internal values
        temp_unit_reverse_map = {
            0: "f",
            1: "c",
            2: "both",
        }

        try:
            # Get the selected value and map it directly to internal values
            selected_value = str(self.temperature_unit_selection.value)
            if "Fahrenheit only" in selected_value:
                temperature_unit = "f"
            elif "Celsius only" in selected_value:
                temperature_unit = "c"
            elif "Both" in selected_value:
                temperature_unit = "both"
            else:
                temperature_unit = "both"  # Default fallback
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get temperature unit selection: {e}, using default")
            temperature_unit = "both"

        # Validate and get update interval
        try:
            update_interval = int(self.update_interval_input.value)
            # Ensure it's within reasonable bounds (1 minute to 24 hours)
            update_interval = max(1, min(1440, update_interval))
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid update interval value: {e}, using default")
            update_interval = 10  # Default to 10 minutes

        return AppSettings(
            temperature_unit=temperature_unit,
            update_interval_minutes=update_interval,
            show_detailed_forecast=self.show_detailed_forecast_switch.value,
            enable_alerts=self.enable_alerts_switch.value,
            minimize_to_tray=self.minimize_to_tray_switch.value,
            data_source=data_source,
        )
