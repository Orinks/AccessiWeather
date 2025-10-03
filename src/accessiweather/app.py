"""Simple AccessiWeather Toga application.

This module provides the main Toga application class following BeeWare best practices,
with a simplified architecture that avoids complex service layers and threading issues.
"""

import asyncio
import logging
from pathlib import Path

import toga

from . import background_tasks, event_handlers, ui_builder
from .alert_manager import AlertManager
from .alert_notification_system import AlertNotificationSystem
from .cache import WeatherDataCache
from .config import ConfigManager
from .display import WeatherPresenter
from .location_manager import LocationManager
from .models import WeatherData
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
        self.presenter: WeatherPresenter | None = None
        self.update_service = None  # Will be initialized after config_manager
        self.single_instance_manager = None  # Will be initialized in startup

        # UI components
        self.location_selection: toga.Selection | None = None
        self.current_conditions_display: toga.MultilineTextInput | None = None
        self.forecast_display: toga.MultilineTextInput | None = None
        self.alerts_table: toga.Table | None = None
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
                _task = asyncio.create_task(self._handle_already_running())
                _task.add_done_callback(background_tasks.task_done_callback)
                return

            # Initialize core components
            self._initialize_components()

            # Create main UI
            ui_builder.create_main_ui(self)

            # Create menu system
            ui_builder.create_menu_system(self)

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

            # Play startup sound after UI is ready but before background updates
            await self._play_startup_sound()

            # Start periodic weather updates as a background task and retain handle for cleanup
            self.update_task = asyncio.create_task(background_tasks.start_background_updates(self))
            # Ensure exceptions are consumed to avoid "Task exception was never retrieved"
            self.update_task.add_done_callback(background_tasks.task_done_callback)

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    async def _play_startup_sound(self):
        """Play the application startup sound."""
        try:
            # Get current soundpack from settings
            if not self.config_manager:
                logger.debug("Config manager unavailable; skipping startup sound")
                return
            config = self.config_manager.get_config()
            current_soundpack = getattr(config.settings, "sound_pack", "default")
            sound_enabled = getattr(config.settings, "sound_enabled", True)

            if sound_enabled:
                from .notifications.sound_player import play_startup_sound

                play_startup_sound(current_soundpack)
                logger.info(f"Played startup sound from pack: {current_soundpack}")
        except Exception as e:
            logger.error(f"Failed to play startup sound: {e}")

    def _initialize_components(self):
        """Initialize core application components."""
        logger.info("Initializing application components")

        # Configuration manager
        self.config_manager = ConfigManager(self)
        config = self.config_manager.load_config()

        # Initialize update service
        try:
            from .services import GitHubUpdateService

            self.update_service = GitHubUpdateService(
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
        config_dir_value = getattr(self.config_manager, "config_dir", None)
        cache_root: Path | None = None
        if config_dir_value is not None:
            try:
                cache_root = Path(config_dir_value)
            except (TypeError, ValueError):
                cache_root = None
        if cache_root is None:
            fallback_dir = getattr(self.paths, "config", None)
            try:
                cache_root = Path(fallback_dir) if fallback_dir is not None else Path.cwd()
            except (TypeError, ValueError):
                cache_root = Path.cwd()
        cache_dir = cache_root / "weather_cache"
        offline_cache = WeatherDataCache(cache_dir)
        self.weather_client = WeatherClient(
            user_agent="AccessiWeather/2.0",
            data_source=data_source,
            visual_crossing_api_key=visual_crossing_api_key,
            settings=config.settings,
            offline_cache=offline_cache,
        )

        # Location manager
        self.location_manager = LocationManager()

        # Formatter
        config = self.config_manager.get_config()
        self.presenter = WeatherPresenter(config.settings)

        # Notification system
        from .notifications.toast_notifier import SafeDesktopNotifier

        # Initialize notifier with sound preferences
        self._notifier = SafeDesktopNotifier(
            sound_enabled=bool(getattr(config.settings, "sound_enabled", True)),
            soundpack=getattr(config.settings, "sound_pack", "default"),
        )

        # Initialize alert management system
        from .alert_manager import AlertManager
        from .alert_notification_system import AlertNotificationSystem

        config_dir = str(self.paths.config)
        alert_settings = config.settings.to_alert_settings()
        self.alert_manager = AlertManager(config_dir, alert_settings)
        audio_settings = config.settings.to_alert_audio_settings()
        self.alert_notification_system = AlertNotificationSystem(
            self.alert_manager, self._notifier, audio_settings=audio_settings
        )

        # Initialize system tray (only if enabled in settings)
        try:
            if bool(getattr(config.settings, "minimize_to_tray", False)):
                ui_builder.initialize_system_tray(self)
            else:
                self.status_icon = None
        except Exception:
            # If something goes wrong, don't block startup; just disable tray
            self.status_icon = None

        logger.info("Application components initialized")

        # Add test alert command for debugging
        if config.settings.debug_mode:
            test_alert_command = toga.Command(
                lambda widget: asyncio.create_task(
                    event_handlers.test_alert_notification(self, widget)
                ),
                text="Test Alert Notification",
                tooltip="Send a test alert notification",
                group=toga.Group.COMMANDS,
            )
            self.commands.add(test_alert_command)

    def _load_initial_data(self):
        """Load initial configuration and data."""
        logger.info("Loading initial data")

        try:
            # Load configuration
            config = self.config_manager.get_config()

            # If no locations exist, add some common ones
            if not config.locations:
                logger.info("No locations found, adding default locations")
                task = asyncio.create_task(background_tasks.add_initial_locations(self))
                task.add_done_callback(background_tasks.task_done_callback)
            else:
                if config.current_location:
                    task = asyncio.create_task(event_handlers.refresh_weather_data(self))
                    task.add_done_callback(background_tasks.task_done_callback)

        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")

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

    def _on_window_close(self, widget):
        """Handle main window close event - honor minimize_to_tray setting.

        Note: This handler is synchronous to match Toga's expected on_close signature.
        """
        try:
            cfg = self.config_manager.get_config() if self.config_manager else None
            minimize_to_tray = (
                bool(getattr(cfg.settings, "minimize_to_tray", False)) if cfg else False
            )
            if minimize_to_tray and getattr(self, "status_icon", None):
                # Hide window to system tray instead of closing
                logger.info("Window close requested - minimizing to system tray")
                self.main_window.hide()
                if hasattr(self, "show_hide_command") and hasattr(self.show_hide_command, "text"):
                    self.show_hide_command.text = "Show AccessiWeather"
                return False  # Prevent default close behavior
            # Setting disabled or no tray available, allow normal close
            logger.info("Close requested - exiting application")
            return True
        except Exception as e:
            logger.error(f"Error handling window close: {e}")
            return True  # Allow close on error

    def on_exit(self):
        """Handle application exit - perform cleanup and return True to allow exit."""
        try:
            logger.info("Application exit requested - performing cleanup")

            # Cancel background update task if running
            try:
                if getattr(self, "update_task", None) and not self.update_task.done():
                    logger.info("Cancelling background update task")
                    self.update_task.cancel()
            except Exception as cancel_err:
                logger.debug(f"Background task cancel error (non-fatal): {cancel_err}")

            # Play exit sound before cleanup
            self._play_exit_sound()

            # Release single instance lock before exiting
            if getattr(self, "single_instance_manager", None):
                try:
                    logger.debug("Releasing single instance lock")
                    self.single_instance_manager.release_lock()
                except Exception as lock_err:
                    logger.debug(f"Single instance lock release error (non-fatal): {lock_err}")

            # Perform any other cleanup here
            logger.info("Application cleanup completed successfully")
            return True  # Allow exit to proceed

        except Exception as e:
            logger.error(f"Error during application exit cleanup: {e}")
            return True  # Still allow exit even if cleanup fails

    def _play_exit_sound(self):
        """Play the application exit sound."""
        try:
            # Get current soundpack from settings
            if not self.config_manager:
                logger.debug("Config manager unavailable; skipping exit sound")
                return
            config = self.config_manager.get_config()
            current_soundpack = getattr(config.settings, "sound_pack", "default")
            sound_enabled = getattr(config.settings, "sound_enabled", True)

            if sound_enabled:
                from .notifications.sound_player import play_exit_sound

                play_exit_sound(current_soundpack)
                logger.info(f"Played exit sound from pack: {current_soundpack}")
        except Exception as e:
            logger.debug(f"Failed to play exit sound: {e}")


def main():
    """Provide main entry point for the simplified AccessiWeather application."""
    return AccessiWeatherApp(
        "AccessiWeather",
        "net.orinks.accessiweather.simple",
        description="Simple, accessible weather application",
        home_page="https://github.com/Orinks/AccessiWeather",
        author="Orinks",
    )
