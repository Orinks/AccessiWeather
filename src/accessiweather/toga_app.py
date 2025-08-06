"""Simple AccessiWeather Toga application.

This module provides the main Toga application class following BeeWare best practices,
with a simplified architecture that avoids complex service layers and threading issues.
"""

import asyncio
import logging

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from .alert_manager import AlertManager
from .alert_notification_system import AlertNotificationSystem
from .dialogs import AddLocationDialog, SettingsDialog
from .dialogs.discussion import ForecastDiscussionDialog
from .display import WxStyleWeatherFormatter
from .location_manager import LocationManager
from .models import WeatherData
from .simple_config import ConfigManager
from .single_instance import SingleInstanceManager
from .weather_client import WeatherClient

logger = logging.getLogger(__name__)


class AccessiWeatherApp(toga.App):
    """Simple AccessiWeather application using Toga."""

    def __init__(self, *args, **kwargs):
        """Initialize the AccessiWeather application."""
        super().__init__(*args, **kwargs)

        # Core components
        self.config_manager: ConfigManager | None = None
        self.weather_client: WeatherClient | None = None
        self.location_manager: LocationManager | None = None
        self.formatter: WxStyleWeatherFormatter | None = None
        self.update_service = None  # Will be initialized after config_manager
        self.single_instance_manager = None  # Will be initialized in startup

        # UI components
        self.location_selection: toga.Selection | None = None
        self.current_conditions_display: toga.MultilineTextInput | None = None
        self.forecast_display: toga.MultilineTextInput | None = None
        self.alerts_display: toga.MultilineTextInput | None = None
        self.refresh_button: toga.Button | None = None
        self.status_label: toga.Label | None = None

        # Background update task
        self.update_task: asyncio.Task | None = None
        self.is_updating: bool = False

        # Weather data storage
        self.current_weather_data: WeatherData | None = None

        # Alert management system
        self.alert_manager: AlertManager | None = None
        self.alert_notification_system: AlertNotificationSystem | None = None

        # Notification system
        self._notifier = None  # Will be initialized in startup

    def startup(self):
        """Initialize the application."""
        logger.info("Starting AccessiWeather application")

        try:
            # Check for single instance before initializing anything else
            self.single_instance_manager = SingleInstanceManager(self)
            if not self.single_instance_manager.try_acquire_lock():
                logger.info("Another instance is already running, showing dialog and exiting")
                # Create a minimal main window to satisfy Toga's requirements
                self.main_window = toga.MainWindow(title=self.formal_name)
                self.main_window.content = toga.Box()
                asyncio.create_task(self._handle_already_running())
                return

            # Initialize core components
            self._initialize_components()

            # Create main UI
            self._create_main_ui()

            # Create menu system
            self._create_menu_system()

            # Load initial data
            self._load_initial_data()

            logger.info("AccessiWeather application started successfully")

        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            # Create a minimal main window to satisfy Toga's requirements
            if not hasattr(self, "main_window") or self.main_window is None:
                self.main_window = toga.MainWindow(title=self.formal_name)
                self.main_window.content = toga.Box()
            self._show_error_dialog("Startup Error", f"Failed to start application: {e}")

    async def _handle_already_running(self):
        """Handle the case when another instance is already running."""
        try:
            await self.single_instance_manager.show_already_running_dialog()
        except Exception as e:
            logger.error(f"Failed to show already running dialog: {e}")
        finally:
            # Use request_exit to allow proper cleanup through on_exit handler
            self.request_exit()

    async def on_running(self):
        """Start background tasks when the app starts running."""
        logger.info("Application is now running, starting background tasks")

        try:
            # Set initial focus for accessibility after app is fully loaded
            # Small delay to ensure UI is fully rendered before setting focus
            await asyncio.sleep(0.1)
            if self.location_selection:
                try:
                    self.location_selection.focus()
                    logger.info("Set initial focus to location dropdown for accessibility")
                except Exception as e:
                    logger.warning(f"Could not set focus to location dropdown: {e}")
                    # Try focusing on the refresh button as fallback
                    if self.refresh_button:
                        try:
                            self.refresh_button.focus()
                            logger.info(
                                "Set initial focus to refresh button as fallback for accessibility"
                            )
                        except Exception as e2:
                            logger.warning(f"Could not set focus to any widget: {e2}")

            # Start periodic weather updates
            await self._start_background_updates()

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    def _initialize_components(self):
        """Initialize core application components."""
        logger.info("Initializing application components")

        # Configuration manager
        self.config_manager = ConfigManager(self)
        config = self.config_manager.load_config()

        # Initialize update service
        try:
            from .services import TUFUpdateService

            self.update_service = TUFUpdateService(
                app_name="AccessiWeather",
                config_dir=self.config_manager.config_dir if self.config_manager else None,
            )
            logger.info("Update service initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize update service: {e}")
            self.update_service = None

        # Weather client with data source and API keys from config
        data_source = config.settings.data_source if config.settings else "auto"
        visual_crossing_api_key = config.settings.visual_crossing_api_key if config.settings else ""
        self.weather_client = WeatherClient(
            user_agent="AccessiWeather/2.0",
            data_source=data_source,
            visual_crossing_api_key=visual_crossing_api_key,
        )

        # Location manager
        self.location_manager = LocationManager()

        # Formatter
        config = self.config_manager.get_config()
        self.formatter = WxStyleWeatherFormatter(config.settings)

        # Notification system
        from .notifications.toast_notifier import SafeDesktopNotifier

        self._notifier = SafeDesktopNotifier()

        # Initialize alert management system
        from .alert_manager import AlertManager
        from .alert_notification_system import AlertNotificationSystem

        config_dir = str(self.paths.config)
        alert_settings = config.settings.to_alert_settings()
        self.alert_manager = AlertManager(config_dir, alert_settings)
        self.alert_notification_system = AlertNotificationSystem(self.alert_manager, self._notifier)

        # Initialize system tray
        self._initialize_system_tray()

        logger.info("Application components initialized")

        # Add test alert command for debugging
        if config.settings.debug_mode:
            test_alert_command = toga.Command(
                self._test_alert_notification,
                text="Test Alert Notification",
                tooltip="Send a test alert notification",
                group=toga.Group.COMMANDS,
            )
            self.commands.add(test_alert_command)

    def _initialize_system_tray(self):
        """Initialize system tray functionality."""
        try:
            logger.info("Initializing system tray")

            # Create a menu-based status icon for AccessiWeather
            self.status_icon = toga.MenuStatusIcon(
                id="accessiweather_main",
                icon=self.icon,  # Use the app's icon
                text="AccessiWeather",
            )

            # Create system tray commands
            self._create_system_tray_commands()

            # Add the status icon to the app
            self.status_icons.add(self.status_icon)

            logger.info("System tray initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize system tray: {e}")
            # Don't fail app startup if system tray fails
            self.status_icon = None

    def _create_system_tray_commands(self):
        """Create commands for the system tray menu."""
        try:
            # Show/Hide main window command
            self.show_hide_command = toga.Command(
                self._on_show_hide_window,
                text="Show AccessiWeather",
                group=self.status_icon,
                tooltip="Show or hide the main window",
            )

            # Refresh weather command
            self.refresh_command = toga.Command(
                self._on_tray_refresh,
                text="Refresh Weather",
                group=self.status_icon,
                tooltip="Refresh weather data for current location",
            )

            # Settings command
            self.tray_settings_command = toga.Command(
                self._on_tray_settings,
                text="Settings",
                group=self.status_icon,
                tooltip="Open application settings",
            )

            # Separator group for organization
            self.tray_separator_group = toga.Group("Actions", parent=self.status_icon)

            # Create a system tray exit command using the standard exit command pattern
            self.tray_exit_command = toga.Command(
                self._on_tray_exit,
                text="Exit AccessiWeather",
                group=self.tray_separator_group,
                tooltip="Exit the application",
            )

            # Add commands to the status icons command set
            self.status_icons.commands.add(
                self.show_hide_command,
                self.refresh_command,
                self.tray_settings_command,
                self.tray_exit_command,
            )

            logger.info("System tray commands created")

        except Exception as e:
            logger.error(f"Failed to create system tray commands: {e}")

    def _create_main_ui(self):
        """Create the main user interface."""
        logger.info("Creating main UI")

        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # Title
        title_label = toga.Label(
            "AccessiWeather",
            style=Pack(text_align="center", font_size=18, font_weight="bold", padding_bottom=10),
        )
        main_box.add(title_label)

        # Status label
        self.status_label = toga.Label("Ready", style=Pack(padding_bottom=10, font_style="italic"))
        main_box.add(self.status_label)

        # Location selection section
        location_box = self._create_location_section()
        main_box.add(location_box)

        # Weather display sections
        weather_box = self._create_weather_display_section()
        main_box.add(weather_box)

        # Control buttons section (matching wx interface)
        buttons_box = self._create_control_buttons_section()
        main_box.add(buttons_box)

        # Debug/Test button (only if debug mode is enabled)
        debug_mode = False
        try:
            debug_mode = self.config_manager.get_settings().debug_mode
        except Exception as e:
            logger.warning(f"Could not read debug_mode from settings: {e}")
        if debug_mode:
            self.test_notification_button = toga.Button(
                "Send Test Notification",
                on_press=self._on_test_notification_pressed,
                style=Pack(padding_top=10, background_color="#e0e0e0"),
            )
            main_box.add(self.test_notification_button)

        # Set up main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box

        # Set up window close handler for system tray functionality
        self.main_window.on_close = self._on_window_close

        self.main_window.show()

        logger.info("Main UI created successfully")

    def _create_location_section(self) -> toga.Box:
        """Create the location selection section."""
        location_box = toga.Box(style=Pack(direction=ROW, padding_bottom=10))

        location_label = toga.Label("Location:", style=Pack(width=80, padding_right=10))

        # Get location choices
        location_names = self._get_location_choices()

        self.location_selection = toga.Selection(
            items=location_names, style=Pack(flex=1), on_change=self._on_location_changed
        )

        # Set current location if available
        current_location = self.config_manager.get_current_location()
        if current_location and current_location.name in location_names:
            self.location_selection.value = current_location.name

        location_box.add(location_label)
        location_box.add(self.location_selection)

        return location_box

    def _create_weather_display_section(self) -> toga.Box:
        """Create the weather display section."""
        weather_box = toga.Box(style=Pack(direction=COLUMN, flex=1))

        # Current conditions
        conditions_label = toga.Label(
            "Current Conditions:", style=Pack(font_weight="bold", padding_top=10, padding_bottom=5)
        )
        weather_box.add(conditions_label)

        self.current_conditions_display = toga.MultilineTextInput(
            readonly=True, style=Pack(height=120, padding_bottom=10)
        )
        self.current_conditions_display.value = "No current conditions data available."
        weather_box.add(self.current_conditions_display)

        # Forecast
        forecast_label = toga.Label("Forecast:", style=Pack(font_weight="bold", padding_bottom=5))
        weather_box.add(forecast_label)

        self.forecast_display = toga.MultilineTextInput(
            readonly=True, style=Pack(height=200, padding_bottom=10)
        )
        self.forecast_display.value = "No forecast data available."
        weather_box.add(self.forecast_display)

        # Forecast discussion button
        self.discussion_button = toga.Button(
            "View Forecast Discussion",
            on_press=self._on_discussion_pressed,
            style=Pack(padding_bottom=10),
        )
        weather_box.add(self.discussion_button)

        # Alerts
        alerts_label = toga.Label(
            "Weather Alerts:", style=Pack(font_weight="bold", padding_bottom=5)
        )
        weather_box.add(alerts_label)

        self.alerts_table = toga.Table(
            headings=["Event", "Severity", "Headline"],
            data=[],
            style=Pack(height=150, padding_bottom=10),
            on_select=self._on_alert_selected,
        )
        weather_box.add(self.alerts_table)

        # Alert details button
        self.alert_details_button = toga.Button(
            "View Alert Details",
            on_press=self._on_alert_details_pressed,
            style=Pack(padding_bottom=10),
            enabled=False,  # Disabled until an alert is selected
        )
        weather_box.add(self.alert_details_button)

        return weather_box

    def _create_control_buttons_section(self) -> toga.Box:
        """Create the control buttons section (matching wx interface)."""
        buttons_box = toga.Box(style=Pack(direction=ROW, padding_top=10))

        # Add location button
        self.add_button = toga.Button(
            "Add", on_press=self._on_add_location_pressed, style=Pack(padding_right=5)
        )
        buttons_box.add(self.add_button)

        # Remove location button
        self.remove_button = toga.Button(
            "Remove", on_press=self._on_remove_location_pressed, style=Pack(padding_right=5)
        )
        buttons_box.add(self.remove_button)

        # Refresh button
        self.refresh_button = toga.Button(
            "Refresh", on_press=self._on_refresh_pressed, style=Pack(padding_right=5)
        )
        buttons_box.add(self.refresh_button)

        # Settings button
        self.settings_button = toga.Button(
            "Settings", on_press=self._on_settings_pressed, style=Pack()
        )
        buttons_box.add(self.settings_button)

        return buttons_box

    def _create_menu_system(self):
        """Create the application menu system."""
        logger.info("Creating menu system")

        # Use built-in File group to avoid duplicate File menus
        settings_cmd = toga.Command(
            self._on_settings_pressed,
            text="Settings",
            tooltip="Open application settings",
            group=toga.Group.FILE,
        )

        # Add Exit command to File menu
        exit_cmd = toga.Command(
            lambda widget: self.request_exit(),
            text="Exit",
            tooltip="Exit the application",
            group=toga.Group.FILE,
            section=1,  # Put in a separate section after Settings
        )

        # Location menu (custom group)
        location_group = toga.Group("Location")
        add_location_cmd = toga.Command(
            self._on_add_location_pressed,
            text="Add Location",
            tooltip="Add a new location",
            group=location_group,
        )

        # Use built-in View group to avoid duplicate View menus
        refresh_cmd = toga.Command(
            self._on_refresh_pressed,
            text="Refresh",
            tooltip="Refresh weather data",
            group=toga.Group.VIEW,
        )

        # Help menu commands - Update checking is now in Settings > Updates tab
        # check_updates_cmd = toga.Command(
        #     self._on_check_updates_pressed,
        #     text="Check for Updates",
        #     tooltip="Check for application updates",
        #     group=toga.Group.HELP,
        # )

        # Add commands to app (About command is automatically provided by Toga)
        self.commands.add(settings_cmd, exit_cmd, add_location_cmd, refresh_cmd)

        # Override the default About command to use our custom handler
        if toga.Command.ABOUT in self.commands:
            self.commands[toga.Command.ABOUT].action = self._on_about_pressed

        # Override the default Exit command to use request_exit (if it exists)
        if toga.Command.EXIT in self.commands:
            self.commands[toga.Command.EXIT].action = lambda widget: self.request_exit()

        logger.info("Menu system created")

    def _load_initial_data(self):
        """Load initial configuration and data."""
        logger.info("Loading initial data")

        try:
            # Load configuration
            config = self.config_manager.get_config()

            # If no locations exist, add some common ones
            if not config.locations:
                logger.info("No locations found, adding default locations")
                # Add both US and international test locations
                asyncio.create_task(self._add_initial_locations())
            else:
                # Refresh weather for current location
                if config.current_location:
                    asyncio.create_task(self._refresh_weather_data())

        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")

    async def _add_initial_locations(self):
        """Add initial locations for first-time users (both US and international)."""
        try:
            # Try to get location from IP first
            location = await self.location_manager.get_current_location_from_ip()

            if location:
                self.config_manager.add_location(
                    location.name, location.latitude, location.longitude
                )
                logger.info(f"Added current location from IP: {location.name}")

            # Add some test locations to demonstrate Open-Meteo integration
            test_locations = [
                # US locations (will use NWS)
                ("New York, NY", 40.7128, -74.0060),
                ("Los Angeles, CA", 34.0522, -118.2437),
                # International locations (will use Open-Meteo)
                ("Tokyo, Japan", 35.6762, 139.6503),
                ("London, UK", 51.5074, -0.1278),
                ("Sydney, Australia", -33.8688, 151.2093),
                ("Paris, France", 48.8566, 2.3522),
            ]

            for name, lat, lon in test_locations:
                self.config_manager.add_location(name, lat, lon)
                logger.info(f"Added test location: {name}")

            # Set the first location as current
            if location:
                self.config_manager.set_current_location(location.name)
            else:
                self.config_manager.set_current_location(
                    "Tokyo, Japan"
                )  # Start with international to test Open-Meteo

            self._update_location_selection()
            await self._refresh_weather_data()

        except Exception as e:
            logger.error(f"Failed to add initial locations: {e}")

    def _get_location_choices(self) -> list[str]:
        """Get list of location names for the selection widget."""
        try:
            location_names = self.config_manager.get_location_names()
            return location_names if location_names else ["No locations available"]
        except Exception as e:
            logger.error(f"Failed to get location choices: {e}")
            return ["Error loading locations"]

    def _update_location_selection(self):
        """Update the location selection widget with current locations."""
        try:
            location_names = self._get_location_choices()
            self.location_selection.items = location_names

            # Set current location if available
            current_location = self.config_manager.get_current_location()
            if current_location and current_location.name in location_names:
                self.location_selection.value = current_location.name

        except Exception as e:
            logger.error(f"Failed to update location selection: {e}")

    def _update_status(self, message: str):
        """Update the status label."""
        if self.status_label:
            self.status_label.text = message
            logger.info(f"Status: {message}")

    # Event handlers
    async def _on_location_changed(self, widget):
        """Handle location selection change."""
        if not widget.value or widget.value == "No locations available":
            return

        logger.info(f"Location changed to: {widget.value}")

        try:
            # Set current location
            self.config_manager.set_current_location(widget.value)

            # Refresh weather data
            await self._refresh_weather_data()

        except Exception as e:
            logger.error(f"Failed to handle location change: {e}")
            self._update_status(f"Error changing location: {e}")

    async def _on_refresh_pressed(self, widget):
        """Handle refresh button press."""
        logger.info("Refresh button pressed")
        await self._refresh_weather_data()

    async def _on_settings_pressed(self, widget):
        """Handle settings menu item."""
        logger.info("Settings menu pressed")

        try:
            # Create a fresh settings dialog instance each time
            # This avoids the "Window is already associated with an App" error
            settings_saved = await self._show_settings_dialog()

            if settings_saved:
                # Refresh UI after settings change
                self._update_location_selection()
                logger.info("Settings updated successfully")

        except Exception as e:
            logger.error(f"Failed to show settings dialog: {e}")
            await self.main_window.error_dialog("Settings Error", f"Failed to open settings: {e}")

    async def _show_settings_dialog(self) -> bool:
        """Show the settings dialog and return whether settings were saved."""
        # Create a completely fresh dialog instance each time to avoid
        # "Window is already associated with an App" errors
        settings_dialog = SettingsDialog(self, self.config_manager, self.update_service)
        settings_dialog.show_and_prepare()

        # Wait for dialog result - the dialog handles its own cleanup
        return await settings_dialog

    async def _on_add_location_pressed(self, widget):
        """Handle add location menu item."""
        logger.info("Add location menu pressed")

        try:
            # Create and show the add location dialog
            add_dialog = AddLocationDialog(self, self.config_manager)

            # Wait for dialog result
            location_added = await add_dialog.show_and_wait()

            if location_added:
                # Refresh the location selection and weather data
                self._update_location_selection()
                await self._refresh_weather_data()
                logger.info("Location added successfully")
            else:
                logger.info("Add location cancelled")

        except Exception as e:
            logger.error(f"Failed to show add location dialog: {e}")
            await self.main_window.error_dialog(
                "Add Location Error", f"Failed to open add location dialog: {e}"
            )

    async def _on_remove_location_pressed(self, widget):
        """Handle remove location button press."""
        logger.info("Remove location button pressed")

        try:
            # Get current location selection
            if not self.location_selection or not self.location_selection.value:
                await self.main_window.info_dialog(
                    "No Selection", "Please select a location to remove from the dropdown."
                )
                return

            selected_location = self.location_selection.value

            # Check if this is the only location
            location_names = self.config_manager.get_location_names()
            if len(location_names) <= 1:
                await self.main_window.info_dialog(
                    "Cannot Remove",
                    "You cannot remove the last location. At least one location must remain.",
                )
                return

            # Show confirmation dialog
            confirmed = await self._show_remove_confirmation_dialog(selected_location)

            if confirmed:
                # Remove the location
                success = self.config_manager.remove_location(selected_location)

                if success:
                    # Update the location selection dropdown
                    self._update_location_selection()

                    # Refresh weather data for the new current location
                    await self._refresh_weather_data()

                    logger.info(f"Successfully removed location: {selected_location}")
                else:
                    await self.main_window.error_dialog(
                        "Remove Failed", f"Failed to remove location '{selected_location}'."
                    )
            else:
                logger.info("Location removal cancelled by user")

        except Exception as e:
            logger.error(f"Failed to remove location: {e}")
            await self.main_window.error_dialog(
                "Remove Location Error", f"Failed to remove location: {e}"
            )

    async def _show_remove_confirmation_dialog(self, location_name: str) -> bool:
        """Show confirmation dialog for removing a location.

        Args:
            location_name: Name of the location to remove

        Returns:
            True if user confirmed removal, False if cancelled

        """
        try:
            # Use Toga's confirm dialog for confirmation
            return await self.main_window.confirm_dialog(
                "Remove Location",
                f"Are you sure you want to remove '{location_name}' from your locations?\n\n"
                f"This action cannot be undone.",
            )
        except Exception as e:
            logger.error(f"Error showing confirmation dialog: {e}")
            # Fallback to a simple info dialog if question dialog fails
            await self.main_window.info_dialog(
                "Confirmation Error",
                "Unable to show confirmation dialog. Location removal cancelled for safety.",
            )
            return False

    async def _on_discussion_pressed(self, widget):
        """Handle forecast discussion button press."""
        logger.info("Forecast discussion button pressed")

        try:
            # Check if we have current weather data
            if not self.current_weather_data:
                await self.main_window.info_dialog(
                    "No Data Available",
                    "Please refresh weather data first to view the forecast discussion.",
                )
                return

            # Check if discussion data is available
            discussion_text = self.current_weather_data.discussion
            if not discussion_text or discussion_text.strip() == "":
                await self.main_window.info_dialog(
                    "Discussion Not Available",
                    "Forecast discussion is not available for this location. "
                    "This may occur for locations outside the US or when using backup weather data.",
                )
                return

            # Create and show the forecast discussion dialog
            location_name = (
                self.current_weather_data.location.name
                if self.current_weather_data.location
                else "Unknown Location"
            )
            dialog = ForecastDiscussionDialog(self, discussion_text, location_name)
            await dialog.show_and_focus()
            logger.info("Forecast discussion dialog shown successfully")

        except Exception as e:
            logger.error(f"Failed to show forecast discussion: {e}")
            await self.main_window.error_dialog(
                "Discussion Error", f"Failed to show forecast discussion: {e}"
            )

    async def _on_alert_details_pressed(self, widget):
        """Handle alert details button press."""
        logger.info("Alert details button pressed")

        try:
            # Call the existing working implementation
            await self.on_view_alert_details(widget)
        except Exception as e:
            logger.error(f"Failed to show alert details: {e}")
            await self.main_window.error_dialog(
                "Alert Details Error", f"Failed to show alert details: {e}"
            )

    def _on_alert_selected(self, widget):
        """Handle alert table selection to enable/disable the details button."""
        try:
            # Enable the alert details button when an alert is selected
            if self.alert_details_button:
                has_selection = widget.selection is not None
                self.alert_details_button.enabled = has_selection
                logger.debug(f"Alert details button {'enabled' if has_selection else 'disabled'}")
        except Exception as e:
            logger.error(f"Error handling alert selection: {e}")

    async def _on_about_pressed(self, widget):
        """Handle about menu item."""
        await self.main_window.info_dialog(
            "About AccessiWeather",
            "AccessiWeather - Simple, accessible weather application\n\n"
            "Built with BeeWare/Toga for cross-platform compatibility.\n"
            "Designed with accessibility in mind for screen reader users.\n\n"
            "Version 2.0 - Simplified Architecture",
        )

    async def _on_check_updates_pressed(self, widget):
        """Handle check for updates menu item."""
        if not self.update_service:
            await self.main_window.error_dialog(
                "Update Service Unavailable",
                "The update service is not available. Please check your internet connection and try again.",
            )
            return

        try:
            # Show checking dialog
            self._update_status("Checking for updates...")

            # Check for updates
            update_info = await self.update_service.check_for_updates()

            if update_info:
                # Update available
                message = (
                    f"Update Available: Version {update_info.version}\n\n"
                    f"Current version: 2.0\n"
                    f"New version: {update_info.version}\n\n"
                )

                if update_info.release_notes:
                    message += f"Release Notes:\n{update_info.release_notes[:500]}"
                    if len(update_info.release_notes) > 500:
                        message += "..."

                # Ask user if they want to download
                should_download = await self.main_window.question_dialog(
                    "Update Available", message + "\n\nWould you like to download this update?"
                )

                if should_download:
                    await self._download_update(update_info)
                else:
                    self._update_status("Update check completed")
            else:
                # No updates available
                await self.main_window.info_dialog(
                    "No Updates Available", "You are running the latest version of AccessiWeather."
                )
                self._update_status("No updates available")

        except Exception as e:
            logger.error(f"Update check failed: {e}")
            await self.main_window.error_dialog(
                "Update Check Failed",
                f"Failed to check for updates: {str(e)}\n\n"
                "Please check your internet connection and try again.",
            )
            self._update_status("Update check failed")

    async def _download_update(self, update_info):
        """Download an available update."""
        try:
            self._update_status(f"Downloading update {update_info.version}...")

            # Download the update
            downloaded_file = await self.update_service.download_update(update_info)

            if downloaded_file:
                await self.main_window.info_dialog(
                    "Update Downloaded",
                    f"Update {update_info.version} has been downloaded successfully.\n\n"
                    f"Location: {downloaded_file}\n\n"
                    "Please close the application and run the installer to complete the update.",
                )
                self._update_status(f"Update {update_info.version} downloaded")
            else:
                await self.main_window.error_dialog(
                    "Download Failed", "Failed to download the update. Please try again later."
                )
                self._update_status("Update download failed")

        except Exception as e:
            logger.error(f"Update download failed: {e}")
            await self.main_window.error_dialog(
                "Download Failed", f"Failed to download update: {str(e)}"
            )
            self._update_status("Update download failed")

    # Weather data methods
    async def _refresh_weather_data(self):
        """Refresh weather data for the current location."""
        if self.is_updating:
            logger.info("Update already in progress, skipping")
            return

        current_location = self.config_manager.get_current_location()
        if not current_location:
            self._update_status("No location selected")
            return

        self.is_updating = True
        self._update_status(f"Updating weather for {current_location.name}...")

        try:
            # Disable refresh button during update
            if self.refresh_button:
                self.refresh_button.enabled = False

            # Fetch weather data
            weather_data = await self.weather_client.get_weather_data(current_location)
            self.current_weather_data = weather_data

            # Update displays
            await self._update_weather_displays(weather_data)

            self._update_status(f"Updated at {weather_data.last_updated.strftime('%I:%M %p')}")
            logger.info(f"Successfully updated weather for {current_location.name}")

        except Exception as e:
            logger.error(f"Failed to refresh weather data: {e}")
            self._update_status(f"Update failed: {e}")
            self._show_error_displays(str(e))

        finally:
            self.is_updating = False
            if self.refresh_button:
                self.refresh_button.enabled = True

    async def _update_weather_displays(self, weather_data: WeatherData):
        """Update the weather display widgets with new data."""
        try:
            # Format weather data
            current_text = self.formatter.format_current_conditions(
                weather_data.current, weather_data.location
            )
            forecast_text = self.formatter.format_forecast(
                weather_data.forecast, weather_data.location, weather_data.hourly_forecast
            )
            # For alerts, we need to handle the table format differently
            # The WxStyleWeatherFormatter returns a string, but we need table data
            if self.alerts_table:
                # Convert alerts data to table format for the simple app
                alerts_table_data = self._convert_alerts_to_table_data(weather_data.alerts)
                self.alerts_table.data = alerts_table_data
                self.current_alerts_data = weather_data.alerts
                if self.alert_details_button:
                    self.alert_details_button.enabled = len(alerts_table_data) > 0
                # Trigger notifications for new alerts
                await self._notify_new_alerts(weather_data.alerts)

            # Update displays
            if self.current_conditions_display:
                self.current_conditions_display.value = current_text

            if self.forecast_display:
                self.forecast_display.value = forecast_text

            logger.info("Weather displays updated successfully")

        except Exception as e:
            logger.error(f"Failed to update weather displays: {e}")
            self._show_error_displays(f"Display error: {e}")

    def _convert_alerts_to_table_data(self, alerts):
        """Convert WeatherAlerts to table data format."""
        if not alerts or not alerts.has_alerts():
            return []

        table_data = []
        active_alerts = alerts.get_active_alerts()

        for alert in active_alerts[:10]:  # Limit to 10 alerts
            event = alert.event or "Weather Alert"
            severity = alert.severity or "Unknown"
            headline = alert.headline or "No headline available"

            # Truncate headline if too long for table display
            if len(headline) > 80:
                headline = headline[:77] + "..."

            table_data.append((event, severity, headline))

        return table_data

    async def _notify_new_alerts(self, alerts):
        """Send system notifications for new or changed alerts using the enhanced alert system."""
        if not alerts or not alerts.has_alerts():
            return

        try:
            # Use the new alert notification system
            if self.alert_notification_system:
                notifications_sent = await self.alert_notification_system.process_and_notify(alerts)
                if notifications_sent > 0:
                    logger.info(f"Sent {notifications_sent} alert notifications")
            else:
                logger.warning("Alert notification system not initialized")
        except Exception as e:
            logger.error(f"Failed to process alert notifications: {e}")
            # Fallback to simple notification for critical alerts
            try:
                active_alerts = alerts.get_active_alerts()
                for alert in active_alerts[:1]:  # Only notify for first alert as fallback
                    if alert.severity.lower() in ["extreme", "severe"]:
                        title = alert.event or "Weather Alert"
                        message = alert.headline or "A new weather alert has been issued."
                        self._notifier.send_notification(title=title, message=message)
                        logger.info(f"Fallback notification sent: {title}")
                        break
            except Exception as fallback_error:
                logger.error(f"Fallback notification also failed: {fallback_error}")

    async def _test_alert_notification(self, widget):
        """Test the alert notification system (debug mode only)."""
        try:
            if self.alert_notification_system:
                success = await self.alert_notification_system.test_notification("Severe")
                if success:
                    await self.main_window.info_dialog(
                        "Test Alert",
                        "Test alert notification sent successfully! Check your system notifications.",
                    )
                else:
                    await self.main_window.error_dialog(
                        "Test Alert Failed",
                        "Failed to send test alert notification. Check the logs for details.",
                    )
            else:
                await self.main_window.error_dialog(
                    "Alert System Error", "Alert notification system is not initialized."
                )
        except Exception as e:
            logger.error(f"Error testing alert notification: {e}")
            await self.main_window.error_dialog(
                "Test Error", f"Error testing alert notification: {e}"
            )

    def _show_error_displays(self, error_message: str):
        """Show error message in weather displays."""
        error_text = f"Error loading weather data: {error_message}"

        if self.current_conditions_display:
            self.current_conditions_display.value = error_text

        if self.forecast_display:
            self.forecast_display.value = error_text

        if self.alerts_table:
            self.alerts_table.data = [("Error", "N/A", "No alerts available due to error")]
            self.current_alerts_data = None

        # Disable the view details button during errors
        if self.alert_details_button:
            self.alert_details_button.enabled = False

    async def _start_background_updates(self):
        """Start background weather updates."""
        try:
            if not self.config_manager:
                logger.warning("Config manager not available, skipping background updates")
                return

            config = self.config_manager.get_config()
            update_interval = config.settings.update_interval_minutes * 60  # Convert to seconds

            logger.info(
                f"Starting background updates every {config.settings.update_interval_minutes} minutes"
            )

            while True:
                await asyncio.sleep(update_interval)

                # Only update if we have a current location and not already updating
                if (
                    not self.is_updating
                    and self.config_manager
                    and self.config_manager.get_current_location()
                ):
                    logger.info("Performing background weather update")
                    await self._refresh_weather_data()

        except asyncio.CancelledError:
            logger.info("Background updates cancelled")
        except Exception as e:
            logger.error(f"Background update error: {e}")

    async def on_view_alert_details(self, widget):
        """Handle the View Alert Details button press."""
        try:
            if not self.alerts_table.selection or not self.current_alerts_data:
                await self.main_window.info_dialog(
                    "No Selection", "Please select an alert from the table first."
                )
                return

            # Get the selected row index
            selected_row = self.alerts_table.selection
            alert_index = self.alerts_table.data.index(selected_row)

            # Get the alert from the original alerts data
            active_alerts = self.current_alerts_data.get_active_alerts()
            if alert_index >= len(active_alerts):
                await self.main_window.error_dialog(
                    "Error", "Selected alert is no longer available."
                )
                return

            alert = active_alerts[alert_index]

            # Create and show the comprehensive alert details dialog
            from .alert_details_dialog import AlertDetailsDialog

            title = f"Alert Details - {alert.event or 'Weather Alert'}"
            dialog = AlertDetailsDialog(self, title, alert)
            await dialog.show()

        except Exception as e:
            logger.error(f"Error showing alert details: {e}")
            await self.main_window.error_dialog("Error", f"Failed to show alert details: {e}")

    def _show_error_dialog(self, title: str, message: str):
        """Show an error dialog (synchronous fallback)."""
        try:
            # Try to show dialog if main window exists
            if hasattr(self, "main_window") and self.main_window:
                # Use the old synchronous API as fallback
                self.main_window.error_dialog(title, message)
            else:
                # Fallback to logging if no window
                logger.error(f"{title}: {message}")
        except Exception as e:
            logger.error(f"Failed to show error dialog: {e}")
            logger.error(f"Original error - {title}: {message}")

    # System Tray Event Handlers

    async def _on_window_close(self, widget):
        """Handle main window close event - minimize to tray instead of closing."""
        try:
            if self.status_icon:
                # Hide window to system tray instead of closing
                logger.info("Window close requested - minimizing to system tray")
                self.main_window.hide()
                if hasattr(self.show_hide_command, "text"):
                    self.show_hide_command.text = "Show AccessiWeather"
                return False  # Prevent default close behavior
            # No system tray available, allow normal close
            logger.info("No system tray available - allowing normal close")
            return True
        except Exception as e:
            logger.error(f"Error handling window close: {e}")
            return True  # Allow close on error

    async def _on_show_hide_window(self, widget):
        """Toggle main window visibility from system tray."""
        try:
            if self.main_window.visible:
                # Hide the window to system tray
                self.main_window.hide()
                if self.status_icon and hasattr(self.show_hide_command, "text"):
                    self.show_hide_command.text = "Show AccessiWeather"
                logger.info("Main window hidden to system tray")
            else:
                # Show and bring window to front
                self.main_window.show()
                if self.status_icon and hasattr(self.show_hide_command, "text"):
                    self.show_hide_command.text = "Hide AccessiWeather"
                logger.info("Main window restored from system tray")
        except Exception as e:
            logger.error(f"Failed to toggle window visibility: {e}")

    async def _on_tray_refresh(self, widget):
        """Refresh weather data from system tray."""
        try:
            logger.info("Refreshing weather data from system tray")
            await self._refresh_weather_data()
        except Exception as e:
            logger.error(f"Failed to refresh weather from system tray: {e}")

    async def _on_tray_settings(self, widget):
        """Open settings dialog from system tray."""
        try:
            logger.info("Opening settings from system tray")
            await self._on_settings_clicked(widget)
        except Exception as e:
            logger.error(f"Failed to open settings from system tray: {e}")

    async def _on_tray_exit(self, widget):
        """Exit application from system tray."""
        try:
            logger.info("Exiting application from system tray")
            # Use request_exit to allow proper cleanup through on_exit handler
            self.request_exit()
        except Exception as e:
            logger.error(f"Failed to exit from system tray: {e}")

    def on_exit(self):
        """Handle application exit - perform cleanup and return True to allow exit."""
        try:
            logger.info("Application exit requested - performing cleanup")

            # Release single instance lock before exiting
            if self.single_instance_manager:
                logger.debug("Releasing single instance lock")
                self.single_instance_manager.release_lock()

            # Perform any other cleanup here
            logger.info("Application cleanup completed successfully")
            return True  # Allow exit to proceed

        except Exception as e:
            logger.error(f"Error during application exit cleanup: {e}")
            return True  # Still allow exit even if cleanup fails

    def _on_test_notification_pressed(self, widget):
        """Send a test notification using desktop-notifier."""
        try:
            self._notifier.send_notification(
                title="Test Notification",
                message="This is a test notification from AccessiWeather (Debug Mode)",
            )
            logger.info("Test notification sent successfully.")
            self._update_status("Test notification sent.")
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}")
            self._update_status(f"Failed to send test notification: {e}")


def main():
    """Provide main entry point for the simplified AccessiWeather application."""
    return AccessiWeatherApp(
        "AccessiWeather",
        "net.orinks.accessiweather.simple",
        description="Simple, accessible weather application",
        home_page="https://github.com/Orinks/AccessiWeather",
        author="Orinks",
    )
