"""Toga-based AccessiWeather application.

This module provides the main Toga application class for AccessiWeather,
integrating with the existing service layer architecture.
"""

# Additional imports for async operations
import logging
import os
import time

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from accessiweather.config_utils import get_config_dir
from accessiweather.toga_data_transformer import TogaDataTransformer

logger = logging.getLogger(__name__)

# Constants
CONFIG_DIR = get_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


class AccessiWeatherToga(toga.App):
    """Main Toga application for AccessiWeather."""

    def __init__(self, *args, **kwargs):
        """Initialize the Toga application."""
        super().__init__(*args, **kwargs)

        # Service layer instances (will be initialized in startup)
        self.weather_service = None
        self.location_service = None
        self.notification_service = None
        self.config = {}

        # UI components (will be created in startup)
        self.location_selection = None
        self.current_conditions_display = None
        self.forecast_display = None
        self.alerts_table = None
        self.current_alerts_data = None
        self.refresh_button = None
        self.discussion_button = None
        self.view_alert_button = None
        self.add_button = None
        self.remove_button = None
        self.settings_button = None

        # Note: Removed background_tasks set since we avoid asyncio.create_task() due to Windows COM issues

    def startup(self):
        """Initialize the application UI and services."""
        logger.info("Starting AccessiWeather Toga application")

        try:
            # Create main UI first (before heavy service initialization)
            self._create_main_ui()

            # Set up menu system
            self._create_menu_system()

            # Initialize services (defer heavy operations)
            self._initialize_services_lightweight()

            # Start background update task
            self._start_background_updates()

            logger.info("AccessiWeather Toga application started successfully")

        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            raise

    def _initialize_services_lightweight(self):
        """Initialize services with minimal complexity to avoid crashes."""
        try:
            logger.info("Initializing lightweight services...")

            # Load configuration (minimal)
            self.config = self._load_config()

            # Initialize services on first use to avoid COM threading issues during startup
            self.weather_service = None  # Will be initialized on first refresh
            self.location_service = None  # Will be initialized on first refresh
            self.notification_service = None  # Will be initialized on first refresh

            logger.info("Lightweight services initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize lightweight services: {e}")
            # Just print error and continue with minimal functionality
            print(f"Failed to initialize services: {e}")
            self.config = {"settings": {"data_source": "auto"}}

    def _add_test_location(self):
        """Add test locations for development/testing (both US and international)."""
        try:
            # Initialize services first if not already done
            if not self.location_service:
                logger.info("Initializing services for test location...")
                self._initialize_services_full()

            if self.location_service:
                # Add Philadelphia as a test location (good for NWS API testing)
                success_philly = self.location_service.add_location("Philadelphia, PA", 39.9526, -75.1652)
                if success_philly:
                    logger.info("Added test location: Philadelphia, PA")

                # Add Tokyo as an international test location (good for Open-Meteo API testing)
                success_tokyo = self.location_service.add_location("Tokyo, Japan", 35.6762, 139.6503)
                if success_tokyo:
                    logger.info("Added test location: Tokyo, Japan")

                # Add London as another international test location
                success_london = self.location_service.add_location("London, UK", 51.5074, -0.1278)
                if success_london:
                    logger.info("Added test location: London, UK")

                # Set Tokyo as current location for testing Open-Meteo
                if success_tokyo:
                    self.location_service.set_current_location("Tokyo, Japan")
                    logger.info("Set Tokyo, Japan as current location for Open-Meteo testing")
                    current_test_location = "Tokyo, Japan"
                elif success_philly:
                    self.location_service.set_current_location("Philadelphia, PA")
                    logger.info("Set Philadelphia, PA as current location")
                    current_test_location = "Philadelphia, PA"
                else:
                    current_test_location = None

                # Update the location selection widget if it exists
                if hasattr(self, "location_selection") and self.location_selection and current_test_location:
                    locations = self._get_location_choices()
                    self.location_selection.items = locations
                    # Set the selection to the new location
                    if current_test_location in locations:
                        self.location_selection.value = current_test_location

                # Automatically refresh weather data for the new location
                if current_test_location:
                    logger.info(f"Automatically refreshing weather data for test location: {current_test_location}")
                    self._refresh_weather_data()
                else:
                    logger.warning("Failed to add any test locations")
        except Exception as e:
            logger.error(f"Error adding test location: {e}")

    def _initialize_services_full(self):
        """Initialize the full service layer (heavy operations)."""
        try:
            logger.info("Initializing services...")

            # Load configuration
            self.config = self._load_config()

            # Create NWS API client
            from accessiweather.api_wrapper import NoaaApiWrapper

            nws_client = NoaaApiWrapper(
                user_agent="AccessiWeather",
                enable_caching=True,
                cache_ttl=300,
            )

            # Create Open-Meteo API client
            from accessiweather.openmeteo_client import OpenMeteoApiClient

            openmeteo_client = OpenMeteoApiClient(user_agent="AccessiWeather")

            # Create location manager
            from accessiweather.location import LocationManager

            show_nationwide = self.config.get("settings", {}).get("show_nationwide_location", True)
            data_source = self.config.get("settings", {}).get("data_source", "auto")
            location_manager = LocationManager(
                CONFIG_DIR, show_nationwide=show_nationwide, data_source=data_source
            )

            # Create notifier
            from accessiweather.notifications import WeatherNotifier

            notifier = WeatherNotifier(config_dir=CONFIG_DIR, enable_persistence=True)

            # Create services
            from accessiweather.services.location_service import LocationService
            from accessiweather.services.notification_service import NotificationService
            from accessiweather.services.weather_service import WeatherService

            self.weather_service = WeatherService(
                nws_client=nws_client, openmeteo_client=openmeteo_client, config=self.config
            )
            self.location_service = LocationService(location_manager)
            self.notification_service = NotificationService(notifier)

            logger.info("Services initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            # Just print error and exit - main window doesn't exist yet
            print(f"Failed to initialize services: {e}")
            raise  # Re-raise to stop app startup

    def _ensure_initial_locations(self):
        """Ensure there are some initial locations available."""
        try:
            if not self.location_service:
                logger.warning("Location service not initialized, cannot add initial locations")
                return

            # Check if any locations exist
            existing_locations = self.location_service.get_all_locations()
            if (
                isinstance(existing_locations, dict)
                and existing_locations
                or isinstance(existing_locations, list)
                and existing_locations
            ):
                logger.info(f"Found {len(existing_locations)} existing locations")
                return

            # Add some default locations for testing
            logger.info("No existing locations found, adding default locations")
            default_locations = [
                ("Philadelphia, PA", 39.9526, -75.1652),
                ("New York, NY", 40.7128, -74.0060),
                ("Washington, DC", 38.9072, -77.0369),
                ("Boston, MA", 42.3601, -71.0589),
                ("Chicago, IL", 41.8781, -87.6298),
            ]

            for name, lat, lon in default_locations:
                try:
                    success = self.location_service.add_location(name, lat, lon)
                    if success:
                        logger.info(f"Added default location: {name}")
                    else:
                        logger.warning(f"Failed to add default location: {name}")
                except Exception as e:
                    logger.error(f"Error adding location {name}: {e}")

            # Set the first location as current
            if default_locations:
                try:
                    first_location = default_locations[0][0]
                    self.location_service.set_current_location(first_location)
                    logger.info(f"Set current location to: {first_location}")
                except Exception as e:
                    logger.error(f"Error setting current location: {e}")

            # Update the location selection widget
            if hasattr(self, "location_selection") and self.location_selection:
                locations = self._get_location_choices()
                self.location_selection.items = locations
                if locations and locations[0] != "No locations saved":
                    self.location_selection.value = locations[0]
                    logger.info(
                        f"Updated location selection widget with {len(locations)} locations"
                    )

        except Exception as e:
            logger.error(f"Failed to ensure initial locations: {e}")

    def _load_config(self):
        """Load configuration from file."""
        import json

        # from accessiweather.config_utils import ensure_config_defaults  # Not available

        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    config = json.load(f)
                    logger.debug(f"Configuration loaded from {CONFIG_PATH}")
                    return config
            except Exception as e:
                logger.error(f"Failed to load config: {str(e)}")

        # Return default config structure
        logger.info("Using default configuration")
        return {
            "settings": {
                "data_source": "auto",
                "show_nationwide_location": True,
                "update_interval_minutes": 10,
            },
            "api_keys": {},
            "api_settings": {},
        }

    def _create_main_ui(self):
        """Create the main user interface."""
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Title
        title_label = toga.Label(
            "AccessiWeather", style=Pack(margin=(0, 0, 10, 0), font_size=16, font_weight="bold")
        )
        main_box.add(title_label)

        # Location selection section
        location_box = toga.Box(style=Pack(direction=ROW, margin=(0, 0, 10, 0)))
        location_label = toga.Label("Location:", style=Pack(margin=(0, 10, 0, 0), width=80))

        # Get locations from location service
        locations = self._get_location_choices()
        self.location_selection = toga.Selection(
            items=locations, style=Pack(flex=1), on_change=self._on_location_changed
        )

        location_box.add(location_label)
        location_box.add(self.location_selection)
        main_box.add(location_box)

        # Current conditions display
        conditions_label = toga.Label(
            "Current Conditions:", style=Pack(margin=(0, 0, 5, 0), font_weight="bold")
        )
        main_box.add(conditions_label)

        self.current_conditions_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(height=100, margin=(0, 0, 10, 0)),
            value="Select a location to view current conditions",
        )
        main_box.add(self.current_conditions_display)

        # Forecast display
        forecast_label = toga.Label(
            "Forecast:", style=Pack(margin=(0, 0, 5, 0), font_weight="bold")
        )
        main_box.add(forecast_label)

        self.forecast_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(height=200, margin=(0, 0, 10, 0)),
            value="Select a location to view the forecast",
        )
        main_box.add(self.forecast_display)

        # Forecast discussion button
        self.discussion_button = toga.Button(
            "View Forecast Discussion",
            on_press=self._on_discussion_pressed,
            style=Pack(margin=(0, 0, 10, 0)),
        )
        main_box.add(self.discussion_button)

        # Weather alerts section
        alerts_label = toga.Label(
            "Weather Alerts:", style=Pack(margin=(0, 0, 5, 0), font_weight="bold")
        )
        main_box.add(alerts_label)

        self.alerts_table = toga.Table(
            headings=["Event", "Severity", "Headline"],
            data=[],
            style=Pack(height=150, margin=(0, 0, 10, 0)),
        )
        main_box.add(self.alerts_table)

        # Alert details button
        self.view_alert_button = toga.Button(
            "View Alert Details",
            on_press=self.on_view_alert_details,
            style=Pack(margin=(0, 0, 10, 0)),
            enabled=False,  # Disabled until an alert is selected
        )
        main_box.add(self.view_alert_button)

        # Control buttons section (matching wx interface)
        buttons_box = toga.Box(style=Pack(direction=ROW, margin=(0, 0, 10, 0)))

        # Add location button
        self.add_button = toga.Button(
            "Add", on_press=self._on_add_location_pressed, style=Pack(margin=(0, 5, 0, 0))
        )
        buttons_box.add(self.add_button)

        # Remove location button
        self.remove_button = toga.Button(
            "Remove", on_press=self._on_remove_location_pressed, style=Pack(margin=(0, 5, 0, 0))
        )
        buttons_box.add(self.remove_button)

        # Refresh button
        self.refresh_button = toga.Button(
            "Refresh", on_press=self._on_refresh_pressed, style=Pack(margin=(0, 5, 0, 0))
        )
        buttons_box.add(self.refresh_button)

        # Settings button
        self.settings_button = toga.Button(
            "Settings", on_press=self._on_settings_pressed, style=Pack(margin=(0, 0, 0, 0))
        )
        buttons_box.add(self.settings_button)

        main_box.add(buttons_box)

        # Store alerts data for detail view
        self.current_alerts_data = None

        # Set up main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

    def _get_location_choices(self):
        """Get list of available locations for the selection widget."""
        try:
            if self.location_service:
                locations = self.location_service.get_all_locations()
                # Handle both dict and list return types
                if isinstance(locations, dict):
                    location_names = list(locations.keys())
                    if location_names:
                        return location_names
                    return ["No locations saved"]
                if isinstance(locations, list):
                    if locations:
                        return locations
                    return ["No locations saved"]
                logger.warning(f"Unexpected location data type: {type(locations)}")
                return ["No locations available"]
            # Return placeholder when services not initialized
            return ["Services not initialized"]
        except Exception as e:
            logger.error(f"Failed to get location choices: {e}")
            return ["Error loading locations"]

    def _create_menu_system(self):
        """Create the application menu system."""
        # File menu
        file_menu = toga.Group("File")
        exit_command = toga.Command(
            lambda _: self.exit(), "Exit", group=file_menu, tooltip="Exit AccessiWeather"
        )

        # Help menu
        help_menu = toga.Group("Help")
        about_command = toga.Command(
            self._on_about_pressed, "About", group=help_menu, tooltip="About AccessiWeather"
        )

        # Add commands to the app
        self.commands.add(exit_command, about_command)

    def _start_background_updates(self):
        """Start background task for periodic weather updates."""
        # TODO: Implement background updates using asyncio
        logger.info("Background updates not yet implemented")

    # Event handlers
    def _on_location_changed(self, widget):
        """Handle location selection change."""
        if widget.value:
            logger.info(f"Location changed to: {widget.value}")
            # Set the current location in the service
            if self.location_service:
                self.location_service.set_current_location(widget.value)
            # Refresh weather data
            self._refresh_weather_data()

    def _on_refresh_pressed(self, widget):
        """Handle refresh button press (synchronous to avoid COM threading issues)."""
        logger.info("Refresh button pressed")

        # Initialize services on first use if not already done
        if not self.weather_service or not self.location_service:
            try:
                self.current_conditions_display.value = "Initializing services..."
                self._initialize_services_full()

                # Add initial locations if none exist
                self._ensure_initial_locations()

                self.current_conditions_display.value = (
                    "Services initialized. Loading weather data..."
                )
            except Exception as e:
                logger.error(f"Failed to initialize services: {e}")
                self.current_conditions_display.value = f"Service initialization failed: {e}"
                return

        # Use real weather data refresh (synchronous)
        self._refresh_weather_data()

    async def _on_test_asyncio_pressed(self, widget):
        """Test simple asyncio task without HTTP."""
        logger.info("Test Asyncio button pressed")

        try:
            # Update UI to show we're testing
            self.current_conditions_display.value = "Testing simple asyncio task..."

            # Simple asyncio task that just waits and prints
            await self._test_simple_asyncio()

            self.current_conditions_display.value = "✅ Simple asyncio task completed successfully!"
            logger.info("Simple asyncio test completed successfully")

        except Exception as e:
            logger.error(f"Simple asyncio test failed: {e}")
            self.current_conditions_display.value = f"❌ Simple asyncio test failed: {e}"

    async def _on_test_http_pressed(self, widget):
        """Test asyncio with HTTP operations."""
        logger.info("Test HTTP button pressed")

        try:
            # Update UI to show we're testing
            self.current_conditions_display.value = "Testing asyncio with HTTP..."

            # Test asyncio with HTTP
            result = await self._test_http_asyncio()

            self.current_conditions_display.value = (
                f"✅ HTTP asyncio test completed!\nResult: {result}"
            )
            logger.info("HTTP asyncio test completed successfully")

        except Exception as e:
            logger.error(f"HTTP asyncio test failed: {e}")
            self.current_conditions_display.value = f"❌ HTTP asyncio test failed: {e}"

    def _on_test_minimal_pressed(self, widget):
        """Test minimal operations without full service initialization."""
        logger.info("Test Minimal button pressed")

        try:
            # Update UI to show we're testing
            self.current_conditions_display.value = "Testing minimal operations..."

            # Test just the formatter without any network calls
            from accessiweather.toga_formatter import TogaWeatherFormatter

            formatter = TogaWeatherFormatter({"settings": {"temperature_unit": "both"}})

            # Test with mock data
            mock_current_conditions = {
                "temperature": 75,
                "temperature_c": 24,
                "condition": "Partly cloudy",
                "humidity": 65,
                "wind_speed": 8,
                "wind_direction": "SW",
                "pressure": 30.15,
                "feelslike": 78,
                "feelslike_c": 26,
            }

            mock_forecast = {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 78,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                    },
                    {
                        "name": "Tonight",
                        "temperature": 62,
                        "temperatureUnit": "F",
                        "shortForecast": "Clear",
                    },
                    {
                        "name": "Tomorrow",
                        "temperature": 82,
                        "temperatureUnit": "F",
                        "shortForecast": "Partly cloudy",
                    },
                ]
            }

            # Format the mock data
            formatted_current = formatter.format_current_conditions(
                mock_current_conditions, "Test Location"
            )
            formatted_forecast = formatter.format_forecast(mock_forecast, "Test Location")
            formatted_alerts = formatter.format_alerts(None, "Test Location")

            # Display results
            self.current_conditions_display.value = formatted_current
            self.forecast_display.value = formatted_forecast
            alerts_data, location_name = formatted_alerts
            if self.alerts_table:
                self.alerts_table.data = alerts_data
                self.current_alerts_data = None  # No real alerts data in test

            logger.info("✅ Minimal test completed successfully - no network calls made")

        except Exception as e:
            logger.error(f"Minimal test failed: {e}")
            self.current_conditions_display.value = f"❌ Minimal test failed: {e}"

    def _on_settings_pressed(self, widget):
        """Handle settings menu item."""
        logger.info("Settings menu pressed")
        # TODO: Implement settings dialog
        # Use old API to avoid async issues on Windows
        self.main_window.info_dialog(
            "Settings", "Settings dialog not yet implemented in Toga version."
        )

    def _on_add_location_pressed(self, widget):
        """Handle add location button press."""
        logger.info("Add location button pressed")
        # TODO: Implement add location dialog
        # Use old API to avoid async issues on Windows
        self.main_window.info_dialog(
            "Add Location", "Add location dialog not yet implemented in Toga version."
        )

    def _on_remove_location_pressed(self, widget):
        """Handle remove location button press."""
        logger.info("Remove location button pressed")
        # TODO: Implement remove location functionality
        # Use old API to avoid async issues on Windows
        self.main_window.info_dialog(
            "Remove Location", "Remove location functionality not yet implemented in Toga version."
        )

    def _on_discussion_pressed(self, widget):
        """Handle forecast discussion button press."""
        logger.info("Forecast discussion button pressed")
        # TODO: Implement forecast discussion dialog
        # Use old API to avoid async issues on Windows
        self.main_window.info_dialog(
            "Forecast Discussion", "Forecast discussion not yet implemented in Toga version."
        )

    def _on_about_pressed(self, widget):
        """Handle about menu item."""
        # Use old API to avoid async issues on Windows
        self.main_window.info_dialog(
            "About AccessiWeather",
            "AccessiWeather - An accessible weather application\n\n"
            "Built with Beeware/Toga framework for cross-platform compatibility.\n"
            "Designed with accessibility in mind for screen reader users.",
        )

    def _refresh_weather_data(self):
        """Refresh weather data from the service layer using synchronous calls."""
        try:
            logger.info("Starting weather data refresh")

            if not self.location_service or not self.weather_service:
                logger.warning("Services not initialized, cannot refresh weather data")
                logger.debug(
                    f"location_service: {self.location_service}, weather_service: {self.weather_service}"
                )
                self.current_conditions_display.value = "Services not initialized"
                self.forecast_display.value = "Services not initialized"
                if self.alerts_table:
                    self.alerts_table.data = [("Error", "N/A", "Services not initialized")]
                    self.current_alerts_data = None
                return

            # Get current location
            current_location = self.location_service.get_current_location()
            logger.debug(f"Current location from service: {current_location}")

            if not current_location:
                # Try to get all locations for debugging
                try:
                    all_locations = self.location_service.get_all_locations()
                    logger.debug(f"All available locations: {all_locations}")
                except Exception as e:
                    logger.debug(f"Error getting all locations: {e}")

                self.current_conditions_display.value = "No location selected"
                self.forecast_display.value = "No location selected"
                if self.alerts_table:
                    self.alerts_table.data = [("Info", "N/A", "No location selected")]
                    self.current_alerts_data = None
                return

            name, lat, lon = current_location
            logger.info(f"Refreshing weather data for {name} ({lat}, {lon})")

            # Update UI to show loading state
            self.current_conditions_display.value = "Loading current conditions..."
            self.forecast_display.value = "Loading forecast..."
            if self.alerts_table:
                self.alerts_table.data = [("Loading", "N/A", "Loading alerts...")]
                self.current_alerts_data = None

            # Fetch weather data synchronously to avoid Windows COM threading issues
            weather_data = self._fetch_weather_data_sync(name, lat, lon)

            # Update UI with weather data
            if weather_data:
                self.current_conditions_display.value = weather_data.get(
                    "current", "No current conditions available"
                )
                self.forecast_display.value = weather_data.get("forecast", "No forecast available")

                # Handle alerts data for table
                alerts_info = weather_data.get("alerts", "No alerts")
                if isinstance(alerts_info, tuple) and len(alerts_info) == 2:
                    alerts_data, location_name = alerts_info
                    if self.alerts_table:
                        self.alerts_table.data = alerts_data
                        # Note: We don't have the original alerts data here, so detail view won't work
                        self.current_alerts_data = None
                        # Enable/disable button based on alerts
                        if self.view_alert_button:
                            self.view_alert_button.enabled = len(alerts_data) > 0
                else:
                    # Fallback for old format
                    if self.alerts_table:
                        self.alerts_table.data = [("Info", "N/A", str(alerts_info))]
                        self.current_alerts_data = None
                        # Disable button for fallback format
                        if self.view_alert_button:
                            self.view_alert_button.enabled = False
            else:
                self.current_conditions_display.value = "Failed to load weather data"
                self.forecast_display.value = "Failed to load forecast"
                if self.alerts_table:
                    self.alerts_table.data = [("Error", "N/A", "Failed to load alerts")]
                    self.current_alerts_data = None
                    # Disable button on error
                    if self.view_alert_button:
                        self.view_alert_button.enabled = False

        except Exception as e:
            logger.error(f"Failed to refresh weather data: {e}")
            self.current_conditions_display.value = f"Error: {e}"
            self.forecast_display.value = f"Error: {e}"
            if self.alerts_table:
                self.alerts_table.data = [("Error", "N/A", f"Error: {e}")]
                self.current_alerts_data = None

    def _refresh_weather_data_threaded(self):
        """Refresh weather data in a separate thread to avoid COM issues."""
        import threading

        def weather_worker():
            """Worker function that runs in separate thread."""
            try:
                logger.info("Starting threaded weather data refresh")

                if not self.location_service or not self.weather_service:
                    self._safe_ui_update(
                        "Services not initialized",
                        "Services not initialized",
                        "Services not initialized",
                    )
                    return

                # Get current location
                current_location = self.location_service.get_current_location()
                if not current_location:
                    self._safe_ui_update(
                        "No location selected", "No location selected", "No location selected"
                    )
                    return

                name, lat, lon = current_location
                logger.info(f"Threaded refresh for {name} ({lat}, {lon})")

                # Show loading state
                self._safe_ui_update(
                    "Loading current conditions...", "Loading forecast...", "Loading alerts..."
                )

                # Fetch weather data with geocoding bypass to avoid COM issues
                weather_data = self._fetch_weather_data_no_geocoding(name, lat, lon)

                # Update UI safely from thread
                if weather_data:
                    self._safe_ui_update(
                        weather_data.get("current", "No current conditions available"),
                        weather_data.get("forecast", "No forecast available"),
                        weather_data.get("alerts", "No alerts"),
                    )
                else:
                    self._safe_ui_update(
                        "Failed to load weather data",
                        "Failed to load forecast",
                        "Failed to load alerts",
                    )

            except Exception as e:
                logger.error(f"Threaded weather refresh failed: {e}")
                self._safe_ui_update(f"Error: {e}", f"Error: {e}", f"Error: {e}")

        # Start the worker thread
        thread = threading.Thread(target=weather_worker, daemon=True)
        thread.start()

    def _safe_ui_update(self, current_text, forecast_text, alerts_text):
        """Safely update UI from a background thread."""
        try:
            # Use Toga's thread-safe UI update mechanism
            def update_ui():
                self.current_conditions_display.value = current_text
                self.forecast_display.value = forecast_text
                # Handle alerts data for table
                if isinstance(alerts_text, tuple) and len(alerts_text) == 2:
                    alerts_data, location_name = alerts_text
                    if self.alerts_table:
                        self.alerts_table.data = alerts_data
                        self.current_alerts_data = None
                else:
                    # Fallback for old format
                    if self.alerts_table:
                        self.alerts_table.data = [("Info", "N/A", str(alerts_text))]
                        self.current_alerts_data = None

            # Use Windows Forms compatible threading approach
            try:
                # Check if we're on the main thread
                import threading

                if threading.current_thread() == threading.main_thread():
                    # We're on main thread, update directly
                    update_ui()
                    logger.debug("UI updated directly on main thread")
                else:
                    # We're on background thread, use Windows Forms Invoke pattern
                    # Store update data and trigger main thread update
                    self._schedule_ui_update_safe(current_text, forecast_text, alerts_text)
                    logger.debug("UI update scheduled from background thread")
            except Exception as e:
                logger.warning(f"Threading check failed, trying direct update: {e}")
                # Fallback to direct update
                update_ui()

        except Exception as e:
            logger.error(f"Failed to update UI safely: {e}")
            # Fallback: try direct update (may cause issues but better than nothing)
            try:
                self.current_conditions_display.value = current_text
                self.forecast_display.value = forecast_text
                # Handle alerts data for table
                if isinstance(alerts_text, tuple) and len(alerts_text) == 2:
                    alerts_data, location_name = alerts_text
                    if self.alerts_table:
                        self.alerts_table.data = alerts_data
                        self.current_alerts_data = None
                else:
                    # Fallback for old format
                    if self.alerts_table:
                        self.alerts_table.data = [("Info", "N/A", str(alerts_text))]
                        self.current_alerts_data = None
            except Exception as e2:
                logger.error(f"Fallback UI update also failed: {e2}")

    def _fetch_weather_data_sync(self, name, lat, lon):
        """Fetch weather data synchronously using the existing WeatherService."""
        try:
            logger.info(f"Fetching weather data for {name} ({lat}, {lon})")

            # Check which API should be used for this location
            if hasattr(self.weather_service, 'weather_data_retrieval') and hasattr(self.weather_service.weather_data_retrieval, 'api_client_manager'):
                api_manager = self.weather_service.weather_data_retrieval.api_client_manager
                should_use_openmeteo = api_manager._should_use_openmeteo(lat, lon)
                api_name = "Open-Meteo" if should_use_openmeteo else "NWS"
                logger.info(f"Using {api_name} API for location {name} ({lat}, {lon})")

            # Create a data transformer that also handles formatting
            transformer = TogaDataTransformer(self.config)

            # Fetch current conditions
            current_conditions = None
            try:
                logger.info("Fetching current conditions...")
                raw_current_conditions = self.weather_service.get_current_conditions(lat, lon)
                logger.info(f"Successfully fetched current conditions using weather service")
                logger.debug(f"Raw current conditions data: {raw_current_conditions}")

                # Transform and format for display
                current_conditions = raw_current_conditions
                logger.debug(f"Raw current conditions: {current_conditions}")
            except Exception as e:
                logger.warning(f"Failed to fetch current conditions: {e}")

            # Fetch forecast
            forecast_data = None
            try:
                logger.info("Fetching forecast...")
                raw_forecast_data = self.weather_service.get_forecast(lat, lon)
                logger.info("Successfully fetched forecast using weather service")
                logger.debug(f"Raw forecast data: {raw_forecast_data}")

                # Transform and format for display
                forecast_data = raw_forecast_data
                logger.debug(f"Raw forecast data: {forecast_data}")
            except Exception as e:
                logger.warning(f"Failed to fetch forecast: {e}")

            # Fetch alerts
            alerts_data = None
            try:
                logger.info("Fetching alerts...")
                alerts_data = self.weather_service.get_alerts(lat, lon)
                logger.info("Successfully fetched alerts using weather service")
                logger.debug(f"Alerts data: {alerts_data}")
            except Exception as e:
                logger.warning(f"Failed to fetch alerts: {e}")

            # Format the data for display using transformer
            formatted_data = {
                "current": transformer.format_current_conditions(current_conditions, name) if current_conditions else f"Current conditions for {name}\n\nNo current weather data available",
                "forecast": transformer.format_forecast(forecast_data, name) if forecast_data else f"Forecast for {name}\n\nNo forecast data available",
                "alerts": f"Weather alerts for {name}\n\nNo alerts available" if not alerts_data else f"Weather alerts for {name}\n\nAlerts data available",
            }

            logger.info("Successfully fetched and formatted weather data")
            return formatted_data

        except Exception as e:
            logger.error(f"Failed to fetch weather data: {e}")
            return {
                "current": f"Error fetching current conditions: {e}",
                "forecast": f"Error fetching forecast: {e}",
                "alerts": f"Error fetching alerts: {e}",
            }

    async def _test_simple_asyncio(self):
        """Test simple asyncio operations without HTTP."""
        import asyncio

        logger.info("Starting simple asyncio test...")

        # Simple async sleep
        await asyncio.sleep(1)
        logger.info("✅ asyncio.sleep(1) completed")

        # Simple async task
        async def simple_task():
            await asyncio.sleep(0.5)
            return "Hello from simple asyncio task!"

        result = await simple_task()
        logger.info(f"✅ Simple task result: {result}")

        # Test asyncio.gather
        async def task1():
            await asyncio.sleep(0.3)
            return "Task 1"

        async def task2():
            await asyncio.sleep(0.2)
            return "Task 2"

        results = await asyncio.gather(task1(), task2())
        logger.info(f"✅ Gather results: {results}")

        return "Simple asyncio test completed successfully"

    async def _test_http_asyncio(self):
        """Test asyncio with HTTP operations."""
        import httpx

        logger.info("Starting HTTP asyncio test...")

        # Test simple HTTP request
        async with httpx.AsyncClient() as client:
            logger.info("Making HTTP request to httpbin.org...")
            response = await client.get("https://httpbin.org/json", timeout=10.0)
            data = response.json()
            logger.info(
                f"✅ HTTP request successful: {data.get('slideshow', {}).get('title', 'No title')}"
            )

        return f"HTTP test completed - Status: {response.status_code}"

    async def _async_ui_update(self, current_text, forecast_text, alerts_text):
        """Async UI update method for Toga 0.5.1."""
        self.current_conditions_display.value = current_text
        self.forecast_display.value = forecast_text
        # Handle alerts data for table
        if isinstance(alerts_text, tuple) and len(alerts_text) == 2:
            alerts_data, location_name = alerts_text
            if self.alerts_table:
                self.alerts_table.data = alerts_data
                self.current_alerts_data = None
        else:
            # Fallback for old format
            if self.alerts_table:
                self.alerts_table.data = [("Info", "N/A", str(alerts_text))]
                self.current_alerts_data = None

    def _fetch_weather_data_no_geocoding(self, name, lat, lon):
        """Fetch weather data bypassing geocoding validation to avoid COM issues."""
        try:
            logger.info(f"Fetching weather data (no geocoding) for {name} ({lat}, {lon})")

            # Create a data transformer that also handles formatting
            transformer = TogaDataTransformer(self.config)

            # For US coordinates, force use of NWS API to avoid geocoding
            # Philadelphia coordinates are definitely in US, so use NWS directly
            if self.weather_service and hasattr(self.weather_service, "weather_data_retrieval"):
                retrieval = self.weather_service.weather_data_retrieval

                # Fetch current conditions with timeout
                current_conditions = None
                try:
                    logger.info("Fetching current conditions with timeout...")
                    current_conditions = self._fetch_with_timeout(
                        lambda: self._get_current_conditions_direct(retrieval, lat, lon),
                        timeout_seconds=10,
                        operation_name="current conditions",
                    )
                    logger.debug(f"Current conditions result: {current_conditions}")
                except Exception as e:
                    logger.warning(f"Current conditions failed: {e}")
                    current_conditions = None

                # Fetch forecast with timeout
                forecast_data = None
                try:
                    logger.info("Fetching forecast with timeout...")
                    forecast_data = self._fetch_with_timeout(
                        lambda: self._get_forecast_direct(retrieval, lat, lon),
                        timeout_seconds=10,
                        operation_name="forecast",
                    )
                    logger.debug(f"Forecast result: {forecast_data}")
                except Exception as e:
                    logger.warning(f"Forecast failed: {e}")
                    forecast_data = None

                # Fetch alerts with timeout
                alerts_data = None
                try:
                    logger.info("Fetching alerts with timeout...")
                    alerts_data = self._fetch_with_timeout(
                        lambda: self._get_alerts_direct(retrieval, lat, lon),
                        timeout_seconds=5,
                        operation_name="alerts",
                    )
                    logger.debug(f"Alerts result: {alerts_data}")
                except Exception as e:
                    logger.warning(f"Alerts failed: {e}")
                    alerts_data = None

                # Format the data for display using transformer
                formatted_data = {
                    "current": transformer.format_current_conditions(current_conditions, name) if current_conditions else f"Current conditions for {name}\n\nNo current weather data available",
                    "forecast": transformer.format_forecast(forecast_data, name) if forecast_data else f"Forecast for {name}\n\nNo forecast data available",
                    "alerts": f"Weather alerts for {name}\n\nNo alerts available" if not alerts_data else f"Weather alerts for {name}\n\nAlerts data available",
                }

                logger.info("Successfully fetched and formatted weather data (no geocoding)")
                return formatted_data

            # Fallback to original method if direct access fails
            logger.warning("Direct API access failed, falling back to original method")
            return self._fetch_weather_data_sync(name, lat, lon)

        except Exception as e:
            logger.error(f"Failed to fetch weather data (no geocoding): {e}")
            return {
                "current": f"Error fetching current conditions: {e}",
                "forecast": f"Error fetching forecast: {e}",
                "alerts": f"Error fetching alerts: {e}",
            }

    def _fetch_with_timeout(self, func, timeout_seconds, operation_name):
        """Execute a function with a timeout to prevent hanging."""
        import threading

        result = [None]
        exception = [None]

        def worker():
            try:
                result[0] = func()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            logger.warning(f"{operation_name} timed out after {timeout_seconds} seconds")
            return None

        if exception[0]:
            raise exception[0]

        return result[0]

    def _get_current_conditions_direct(self, retrieval, lat, lon):
        """Get current conditions directly from API clients."""
        # Try NWS first
        if hasattr(retrieval, "nws_client"):
            try:
                logger.debug("Trying NWS for current conditions...")
                return retrieval.nws_client.get_current_conditions(lat, lon)
            except Exception as e:
                logger.debug(f"NWS current conditions failed: {e}")

        # Try OpenMeteo as fallback
        if hasattr(retrieval, "openmeteo_client"):
            try:
                logger.debug("Trying OpenMeteo for current conditions...")
                return retrieval.openmeteo_client.get_current_conditions(lat, lon)
            except Exception as e:
                logger.debug(f"OpenMeteo current conditions failed: {e}")

        return None

    def _get_forecast_direct(self, retrieval, lat, lon):
        """Get forecast directly from API clients."""
        # Try NWS first
        if hasattr(retrieval, "nws_client"):
            try:
                logger.debug("Trying NWS for forecast...")
                return retrieval.nws_client.get_forecast(lat, lon)
            except Exception as e:
                logger.debug(f"NWS forecast failed: {e}")

        # Try OpenMeteo as fallback
        if hasattr(retrieval, "openmeteo_client"):
            try:
                logger.debug("Trying OpenMeteo for forecast...")
                return retrieval.openmeteo_client.get_forecast(lat, lon)
            except Exception as e:
                logger.debug(f"OpenMeteo forecast failed: {e}")

        return None

    def _get_alerts_direct(self, retrieval, lat, lon):
        """Get alerts directly from API clients."""
        # Only NWS provides alerts
        if hasattr(retrieval, "nws_client"):
            try:
                logger.debug("Trying NWS for alerts...")
                return retrieval.nws_client.get_alerts(lat, lon)
            except Exception as e:
                logger.debug(f"NWS alerts failed: {e}")

        return None

    def _refresh_weather_data_mock(self):
        """Refresh weather data using mock data to avoid all network issues."""
        try:
            logger.info("Using mock weather data to avoid network/threading issues")

            # Get current location for display
            location_name = "Philadelphia, PA"
            if self.location_service:
                try:
                    current_location = self.location_service.get_current_location()
                    if current_location:
                        location_name = current_location[0]
                except Exception as e:
                    logger.warning(f"Could not get location name: {e}")

            # Create formatter
            from accessiweather.toga_formatter import TogaWeatherFormatter

            formatter = TogaWeatherFormatter(self.config)

            # Mock current conditions data
            mock_current = {
                "temperature": 75,
                "temperature_c": 24,
                "condition": "Partly cloudy",
                "humidity": 65,
                "wind_speed": 8,
                "wind_speed_kph": 13,
                "wind_direction": "SW",
                "pressure": 30.15,
                "pressure_mb": 1020,
                "feelslike": 78,
                "feelslike_c": 26,
            }

            # Mock forecast data
            mock_forecast = {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 78,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                    },
                    {
                        "name": "Tonight",
                        "temperature": 62,
                        "temperatureUnit": "F",
                        "shortForecast": "Clear",
                    },
                    {
                        "name": "Tomorrow",
                        "temperature": 82,
                        "temperatureUnit": "F",
                        "shortForecast": "Partly cloudy",
                    },
                    {
                        "name": "Tomorrow Night",
                        "temperature": 65,
                        "temperatureUnit": "F",
                        "shortForecast": "Mostly clear",
                    },
                    {
                        "name": "Wednesday",
                        "temperature": 85,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                    },
                    {
                        "name": "Wednesday Night",
                        "temperature": 68,
                        "temperatureUnit": "F",
                        "shortForecast": "Clear",
                    },
                    {
                        "name": "Thursday",
                        "temperature": 83,
                        "temperatureUnit": "F",
                        "shortForecast": "Scattered showers",
                    },
                ]
            }

            # Mock alerts (empty for now)
            mock_alerts = None

            # Format the mock data
            formatted_current = formatter.format_current_conditions(mock_current, location_name)
            formatted_forecast = formatter.format_forecast(mock_forecast, location_name)
            formatted_alerts = formatter.format_alerts(mock_alerts, location_name)

            # Update UI directly (no threading needed for mock data)
            self.current_conditions_display.value = formatted_current
            self.forecast_display.value = formatted_forecast
            # Handle alerts data for table
            if isinstance(formatted_alerts, tuple) and len(formatted_alerts) == 2:
                alerts_data, location_name = formatted_alerts
                if self.alerts_table:
                    self.alerts_table.data = alerts_data
                    self.current_alerts_data = None
            else:
                # Fallback for old format
                if self.alerts_table:
                    self.alerts_table.data = [("Info", "N/A", str(formatted_alerts))]
                    self.current_alerts_data = None

            logger.info("Successfully displayed mock weather data")

        except Exception as e:
            logger.error(f"Failed to display mock weather data: {e}")
            self.current_conditions_display.value = f"Error displaying mock data: {e}"
            self.forecast_display.value = f"Error displaying mock data: {e}"
            if self.alerts_table:
                self.alerts_table.data = [("Error", "N/A", f"Error displaying mock data: {e}")]
                self.current_alerts_data = None

    def _schedule_ui_update_safe(self, current_text, forecast_text, alerts_text):
        """Schedule UI update using Windows Forms compatible approach."""
        try:
            # Store the pending update data
            self._pending_ui_data = {
                "current": current_text,
                "forecast": forecast_text,
                "alerts": alerts_text,
                "timestamp": time.time(),
            }

            # Use a simple timer-based approach to trigger UI update on main thread
            # This avoids the COM threading issues with asyncio.create_task
            import threading

            def delayed_update():
                try:
                    # Small delay to ensure we're back on main thread context
                    time.sleep(0.1)
                    # Trigger the actual UI update
                    self._apply_pending_ui_update()
                except Exception as e:
                    logger.error(f"Delayed UI update failed: {e}")

            # Start timer thread (daemon so it doesn't prevent app exit)
            timer_thread = threading.Thread(target=delayed_update, daemon=True)
            timer_thread.start()

            logger.debug("UI update scheduled via timer thread")

        except Exception as e:
            logger.error(f"Failed to schedule UI update: {e}")
            # Last resort: try direct update
            try:
                self.current_conditions_display.value = current_text
                self.forecast_display.value = forecast_text
                # Handle alerts data for table
                if isinstance(alerts_text, tuple) and len(alerts_text) == 2:
                    alerts_data, location_name = alerts_text
                    if self.alerts_table:
                        self.alerts_table.data = alerts_data
                        self.current_alerts_data = None
                else:
                    # Fallback for old format
                    if self.alerts_table:
                        self.alerts_table.data = [("Info", "N/A", str(alerts_text))]
                        self.current_alerts_data = None
            except Exception as e2:
                logger.error(f"Direct UI update also failed: {e2}")

    def _apply_pending_ui_update(self):
        """Apply pending UI update if available."""
        try:
            if hasattr(self, "_pending_ui_data") and self._pending_ui_data:
                data = self._pending_ui_data
                self.current_conditions_display.value = data["current"]
                self.forecast_display.value = data["forecast"]
                # Handle alerts data for table
                alerts_info = data["alerts"]
                if isinstance(alerts_info, tuple) and len(alerts_info) == 2:
                    alerts_data, location_name = alerts_info
                    if self.alerts_table:
                        self.alerts_table.data = alerts_data
                        self.current_alerts_data = None
                else:
                    # Fallback for old format
                    if self.alerts_table:
                        self.alerts_table.data = [("Info", "N/A", str(alerts_info))]
                        self.current_alerts_data = None

                # Clear the pending data
                self._pending_ui_data = None
                logger.debug("Applied pending UI update successfully")

        except Exception as e:
            logger.error(f"Failed to apply pending UI update: {e}")

    def on_view_alert_details(self, widget):
        """Handle the View Alert Details button press."""
        try:
            if not self.alerts_table.selection or not self.current_alerts_data:
                self.main_window.info_dialog(
                    "No Selection", "Please select an alert from the table first."
                )
                return

            # Get the selected row index
            selected_row = self.alerts_table.selection
            alert_index = self.alerts_table.data.index(selected_row)

            # Get detailed alert information using the formatter
            from .toga_formatter import TogaWeatherFormatter

            formatter = TogaWeatherFormatter({})
            alert_details = formatter.get_alert_details(self.current_alerts_data, alert_index)

            if alert_details:
                # Format detailed alert information
                title = alert_details.get("event", "Weather Alert")
                description = alert_details.get("description", "No description available")
                instruction = alert_details.get("instruction", "")

                detail_text = f"Event: {title}\n\n"
                detail_text += f"Severity: {alert_details.get('severity', 'Unknown')}\n"
                detail_text += f"Urgency: {alert_details.get('urgency', 'Unknown')}\n"
                detail_text += f"Certainty: {alert_details.get('certainty', 'Unknown')}\n\n"

                if alert_details.get("headline"):
                    detail_text += f"Headline: {alert_details.get('headline')}\n\n"

                detail_text += f"Description:\n{description}\n\n"

                if instruction:
                    detail_text += f"Instructions:\n{instruction}"

                # Show alert details in a dialog
                self.main_window.info_dialog(title, detail_text)

        except Exception as e:
            logger.error(f"Error showing alert details: {e}")
            self.main_window.error_dialog("Error", f"Failed to show alert details: {e}")


def main():
    """Main entry point for the Toga application."""
    return AccessiWeatherToga("AccessiWeather", "net.orinks.accessiweather")
