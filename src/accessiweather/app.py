"""
Simple AccessiWeather Toga application.

This module provides the main Toga application class following BeeWare best practices,
with a simplified architecture that avoids complex service layers and threading issues.
"""

from __future__ import annotations

import asyncio
import logging
import sys
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

# Configure logging for when running with briefcase dev (bypasses main.py)
# Only configure if no handlers are already set up (avoid double initialization)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

logger = logging.getLogger(__name__)


class AccessiWeatherApp(toga.App):
    """Simple AccessiWeather application using Toga."""

    def __init__(self, *args, config_dir: str | None = None, portable_mode: bool = False, **kwargs):
        """
        Initialize the AccessiWeather application.

        Args:
            *args: Positional arguments passed to toga.App
            config_dir: Optional custom configuration directory path
            portable_mode: If True, use portable mode (config in app directory)
            **kwargs: Keyword arguments passed to toga.App

        """
        super().__init__(*args, **kwargs)

        # Store config parameters for later use
        self._config_dir = config_dir
        self._portable_mode = portable_mode

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
        self.aviation_dialog = None

        # Background update task
        self.update_task: asyncio.Task | None = None
        self.is_updating: bool = False
        self.current_refresh_task: asyncio.Task | None = None  # Track active foreground refresh

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
                logger.info("Another instance is already running, exiting silently")
                # Create a minimal main window to satisfy Toga's requirements
                self.main_window = toga.MainWindow(title=self.formal_name)
                self.main_window.content = toga.Box()
                # Exit silently without showing intrusive dialog
                self.request_exit()
                return

            # Initialize core components
            self._initialize_components()

            # Create main UI
            ui_builder.create_main_ui(self)

            # Create menu system
            ui_builder.create_menu_system(self)

            # Note: System tray is initialized conditionally in app_initialization.py
            # based on minimize_to_tray setting to avoid duplicate initialization

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

    def refresh_runtime_settings(self) -> None:
        """
        Refresh runtime components with current settings.

        Call this after settings are saved to ensure all app components
        use the updated configuration without requiring an app restart.
        """
        try:
            settings = self.config_manager.get_settings()
            logger.info("Refreshing runtime settings")

            # Update WeatherClient settings
            if self.weather_client:
                self.weather_client.settings = settings
                self.weather_client.data_source = settings.data_source
                self.weather_client.alerts_enabled = bool(settings.enable_alerts)
                self.weather_client.trend_insights_enabled = bool(settings.trend_insights_enabled)
                self.weather_client.trend_hours = max(1, int(settings.trend_hours or 24))
                self.weather_client.air_quality_enabled = bool(settings.air_quality_enabled)
                self.weather_client.pollen_enabled = bool(settings.pollen_enabled)
                # Update Visual Crossing API key if changed
                self.weather_client.visual_crossing_api_key = getattr(
                    settings, "visual_crossing_api_key", ""
                )
                logger.debug("Updated WeatherClient settings")

            # Update WeatherPresenter settings (handles temperature_unit, etc.)
            if self.presenter:
                self.presenter.settings = settings
                logger.debug("Updated WeatherPresenter settings")

            # Update notifier settings
            if self._notifier:
                self._notifier.sound_enabled = bool(getattr(settings, "sound_enabled", True))
                self._notifier.soundpack = getattr(settings, "sound_pack", "default")
                logger.debug("Updated notifier settings")

            # Update alert notification system settings
            if self.alert_notification_system:
                self.alert_notification_system.settings = settings
                # Also update the alert manager with new alert settings
                if self.alert_manager:
                    alert_settings = settings.to_alert_settings()
                    self.alert_manager.update_settings(alert_settings)
                logger.debug("Updated AlertNotificationSystem settings")

            # Handle minimize_to_tray toggle (create/destroy system tray)
            self._update_system_tray_state(settings)

            # Update system tray tooltip with current weather data
            if hasattr(self, "status_icon") and self.status_icon:
                ui_builder.update_tray_icon_tooltip(self, self.current_weather_data)

            # Update AI explanation cache TTL
            if hasattr(self, "ai_explanation_cache") and self.ai_explanation_cache:
                ai_cache_ttl = getattr(settings, "ai_cache_ttl", 300)
                self.ai_explanation_cache.default_ttl = ai_cache_ttl

            # Update AI explanation button visibility
            self._update_ai_button_visibility(settings.enable_ai_explanations)

            # Update debug logging level
            self._update_debug_logging(settings)

            # Update weather history service state
            self._update_weather_history_service(settings)

            logger.info("Runtime settings refreshed successfully")

        except Exception as exc:
            logger.error(f"Failed to refresh runtime settings: {exc}")

    def _update_system_tray_state(self, settings) -> None:
        """
        Create or destroy system tray based on minimize_to_tray setting.

        This allows toggling the system tray without restarting the app.
        """
        try:
            minimize_to_tray = bool(getattr(settings, "minimize_to_tray", False))
            has_tray = getattr(self, "status_icon", None) is not None

            if minimize_to_tray and not has_tray:
                # User enabled minimize_to_tray - create system tray
                logger.info("Creating system tray (minimize_to_tray enabled)")
                ui_builder.initialize_system_tray(self)
            elif not minimize_to_tray and has_tray:
                # User disabled minimize_to_tray - remove system tray
                logger.info("Removing system tray (minimize_to_tray disabled)")
                self._remove_system_tray()

        except Exception as exc:
            logger.warning(f"Failed to update system tray state: {exc}")

    def _remove_system_tray(self) -> None:
        """Remove the system tray icon and associated commands."""
        import contextlib

        try:
            if hasattr(self, "status_icon") and self.status_icon:
                # Remove from status_icons collection
                if hasattr(self, "status_icons"):
                    with contextlib.suppress(Exception):
                        self.status_icons.discard(self.status_icon)
                self.status_icon = None
                self.system_tray_available = False
                logger.debug("System tray removed")
        except Exception as exc:
            logger.warning(f"Error removing system tray: {exc}")

    def _update_debug_logging(self, settings) -> None:
        """Update logging level based on debug_mode setting."""
        try:
            import logging as log_module

            debug_enabled = bool(getattr(settings, "debug_mode", False))
            log_level = log_module.DEBUG if debug_enabled else log_module.INFO

            root_logger = log_module.getLogger()
            if root_logger.level != log_level:
                root_logger.setLevel(log_level)
                for handler in root_logger.handlers:
                    handler.setLevel(log_level)
                logger.debug(f"Logging level set to {'DEBUG' if debug_enabled else 'INFO'}")
        except Exception as exc:
            logger.warning(f"Failed to update debug logging: {exc}")

    def _update_weather_history_service(self, settings) -> None:
        """Enable or disable weather history service based on settings."""
        try:
            history_enabled = bool(getattr(settings, "weather_history_enabled", False))
            has_service = self.weather_history_service is not None

            if history_enabled and not has_service:
                # Enable weather history
                from .weather_history import WeatherHistoryService

                self.weather_history_service = WeatherHistoryService()
                logger.info("Weather history service enabled")
            elif not history_enabled and has_service:
                # Disable weather history
                self.weather_history_service = None
                logger.info("Weather history service disabled")
        except Exception as exc:
            logger.warning(f"Failed to update weather history service: {exc}")

    def _update_ai_button_visibility(self, ai_enabled: bool) -> None:
        """
        Update the visibility of the AI explanation button based on settings.

        Args:
            ai_enabled: Whether AI explanations are enabled in settings

        """
        try:
            if ai_enabled and not hasattr(self, "explain_weather_button"):
                # AI was just enabled - add the button
                self._add_ai_explanation_button()
            elif (
                not ai_enabled
                and hasattr(self, "explain_weather_button")
                and self.explain_weather_button
            ):
                # AI was just disabled - remove the button
                self._remove_ai_explanation_button()
        except Exception as exc:
            logger.warning(f"Failed to update AI button visibility: {exc}")

    def _add_ai_explanation_button(self) -> None:
        """Add the AI explanation button to the weather display."""
        try:
            from .ai_explainer import create_explain_weather_button
            from .handlers.ai_handlers import on_explain_weather_pressed

            self.explain_weather_button = create_explain_weather_button(
                on_press=lambda widget: asyncio.create_task(
                    on_explain_weather_pressed(self, widget)
                )
            )

            # Find the weather box and add the button before the discussion button
            if hasattr(self, "main_window") and self.main_window and self.main_window.content:
                weather_box = self._find_weather_box(self.main_window.content)
                if weather_box and hasattr(self, "discussion_button") and self.discussion_button:
                    # Insert before discussion button
                    children = list(weather_box.children)
                    discussion_index = children.index(self.discussion_button)
                    weather_box.insert(discussion_index, self.explain_weather_button)
                    logger.info("Added AI explanation button to weather display")

        except Exception as exc:
            logger.warning(f"Failed to add AI explanation button: {exc}")

    def _remove_ai_explanation_button(self) -> None:
        """Remove the AI explanation button from the weather display."""
        try:
            if hasattr(self, "explain_weather_button") and self.explain_weather_button:
                # Find the parent container and remove the button
                if hasattr(self, "main_window") and self.main_window and self.main_window.content:
                    weather_box = self._find_weather_box(self.main_window.content)
                    if weather_box and self.explain_weather_button in weather_box.children:
                        weather_box.remove(self.explain_weather_button)
                        logger.info("Removed AI explanation button from weather display")

                self.explain_weather_button = None

        except Exception as exc:
            logger.warning(f"Failed to remove AI explanation button: {exc}")

    def _find_weather_box(self, container) -> toga.Box | None:
        """Recursively find the weather display box in the UI hierarchy."""
        if hasattr(container, "children"):
            for child in container.children:
                # Look for the box that contains the discussion button
                if (
                    hasattr(child, "children")
                    and hasattr(self, "discussion_button")
                    and self.discussion_button in child.children
                ):
                    return child
                # Recursively search child containers
                result = self._find_weather_box(child)
                if result:
                    return result
        return None


def main(config_dir: str | None = None, portable_mode: bool = False):
    """
    Provide main entry point for the simplified AccessiWeather application.

    Args:
        config_dir: Optional custom configuration directory path
        portable_mode: If True, use portable mode (config in app directory)

    """
    return AccessiWeatherApp(
        "AccessiWeather",
        "net.orinks.accessiweather.simple",
        description="Simple, accessible weather application",
        home_page="https://github.com/Orinks/AccessiWeather",
        author="Orinks",
        config_dir=config_dir,
        portable_mode=portable_mode,
    )
