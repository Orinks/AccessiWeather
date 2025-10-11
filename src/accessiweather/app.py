"""
Simple AccessiWeather Toga application.

This module provides the main Toga application class following BeeWare best practices,
with a simplified architecture that avoids complex service layers and threading issues.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import toga

from . import app_helpers, app_initialization, background_tasks, ui_builder
from .config import ConfigManager
from .models import WeatherData
from .single_instance import SingleInstanceManager

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .alert_manager import AlertManager
    from .alert_notification_system import AlertNotificationSystem
    from .display import WeatherPresenter
    from .location_manager import LocationManager
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
        self.weather_history_service = None  # Weather history comparison service

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
            app_helpers.show_error_dialog(
                self, "Startup Error", f"Failed to start application: {e}"
            )

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
            await app_helpers.play_startup_sound(self)

            # Start periodic weather updates as a background task and retain handle for cleanup
            self.update_task = asyncio.create_task(background_tasks.start_background_updates(self))
            # Ensure exceptions are consumed to avoid "Task exception was never retrieved"
            self.update_task.add_done_callback(background_tasks.task_done_callback)

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}")

    def _initialize_components(self):
        """Initialize core application components."""
        app_initialization.initialize_components(self)

    def _load_initial_data(self):
        """Load initial configuration and data."""
        app_initialization.load_initial_data(self)

    def _on_window_close(self, widget):
        """Delegate window-close behavior to helper logic."""
        return app_helpers.handle_window_close(self, widget)

    def on_exit(self):
        """Delegate shutdown cleanup to helper logic."""
        return app_helpers.handle_exit(self)


def main():
    """Provide main entry point for the simplified AccessiWeather application."""
    return AccessiWeatherApp(
        "AccessiWeather",
        "net.orinks.accessiweather.simple",
        description="Simple, accessible weather application",
        home_page="https://github.com/Orinks/AccessiWeather",
        author="Orinks",
    )
