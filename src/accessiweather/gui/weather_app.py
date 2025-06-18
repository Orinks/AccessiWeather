"""Main application window for AccessiWeather

This module provides the main application window and integrates all components
using the service layer for business logic.
"""

import logging
import os

import wx
import wx.adv

from accessiweather.config_utils import get_config_dir

from .handlers import (
    WeatherAppAlertHandlers,
    WeatherAppBaseHandlers,
    WeatherAppConfigHandlers,
    WeatherAppDebugHandlers,
    WeatherAppDialogHandlers,
    WeatherAppDiscussionHandlers,
    WeatherAppLocationHandlers,
    WeatherAppMenuHandlers,
    WeatherAppRefreshHandlers,
    WeatherAppSettingsHandlers,
    WeatherAppSystemHandlers,
    WeatherAppTimerHandlers,
    WeatherAppUpdateHandlers,
)
from .settings_dialog import UPDATE_INTERVAL_KEY
from .system_tray import TaskBarIcon
from .ui_manager import UIManager
from .weather_app_modules.core import WeatherAppCore
from .weather_app_modules.event_handlers import WeatherAppEventHandlers
from .weather_app_modules.service_coordination import WeatherAppServiceCoordination
from .weather_app_modules.ui_management import WeatherAppUIManagement

logger = logging.getLogger(__name__)

# Constants
CONFIG_DIR = get_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


class WeatherApp(
    wx.Frame,
    WeatherAppBaseHandlers,
    WeatherAppLocationHandlers,
    WeatherAppAlertHandlers,
    WeatherAppDebugHandlers,
    WeatherAppDialogHandlers,
    WeatherAppDiscussionHandlers,
    WeatherAppMenuHandlers,
    WeatherAppRefreshHandlers,
    WeatherAppSettingsHandlers,
    WeatherAppSystemHandlers,
    WeatherAppTimerHandlers,
    WeatherAppConfigHandlers,
    WeatherAppUpdateHandlers,
):
    """Main application window for AccessiWeather."""

    def __init__(
        self,
        parent=None,
        weather_service=None,
        location_service=None,
        notification_service=None,
        api_client=None,  # For backward compatibility
        config=None,
        config_path=None,
        debug_mode=False,
    ):
        """Initialize the weather app

        Args:
            parent: Parent window
            weather_service: WeatherService instance
            location_service: LocationService instance
            notification_service: NotificationService instance
            api_client: NoaaApiClient instance (for backward compatibility)
            config: Configuration dictionary (optional)
            config_path: Custom path to config file (optional)
            debug_mode: Whether to enable debug mode with additional logging and alert testing features (default: False)
        """
        super().__init__(parent, title="AccessiWeather", size=(800, 600))

        # Initialize core module and delegate core initialization
        self.core = WeatherAppCore(self)
        self.core.initialize_app(
            parent=parent,
            weather_service=weather_service,
            location_service=location_service,
            notification_service=notification_service,
            api_client=api_client,
            config=config,
            config_path=config_path,
            debug_mode=debug_mode,
        )

        # Initialize event handlers module
        self.event_handlers = WeatherAppEventHandlers(self)

        # Initialize service coordination module
        self.service_coordination = WeatherAppServiceCoordination(self)

        # Initialize UI management module
        self.ui_management = WeatherAppUIManagement(self)

        # Initialize UI using UIManager
        # UI elements are now attached to self by UIManager
        self.ui_manager = UIManager(self, self.notification_service.notifier)

        # Set up status bar using UI management module
        self.ui_management.setup_status_bar()

        # Start update timer
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.event_handlers.OnTimer, self.timer)
        # Bind Close event here as it's frame-level, not UI-element specific
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_ICONIZE, self.OnMinimize)

        # Bind character hook for global keyboard shortcuts
        self.Bind(wx.EVT_CHAR_HOOK, self.event_handlers.OnCharHook)

        # Log the update interval from config
        update_interval = self.config.get("settings", {}).get(UPDATE_INTERVAL_KEY, 10)
        logger.debug(f"Starting timer with update interval: {update_interval} minutes")

        self.timer.Start(1000)  # Check every 1 second for updates

        # Create system tray icon - cleanup any existing instance first
        TaskBarIcon.cleanup_existing_instance()
        self.taskbar_icon = TaskBarIcon(self)

        # Register with accessibility system using UI management module
        self.ui_management.setup_accessibility()

        # Create menu bar
        self.event_handlers._create_menu_bar()

        # Initialize UI with location data
        self.UpdateLocationDropdown()

        # Update UI elements based on initial weather source (show/hide Open-Meteo incompatible elements)
        if hasattr(self, "ui_manager") and self.ui_manager:
            self.ui_manager.update_ui_for_location_change()

        self.UpdateWeatherData()

        # Initialize update service (from WeatherAppUpdateHandlers)
        self.core.initialize_update_service()

    def _on_update_available(self, update_info):
        """Handle update available notification - delegate to update handlers."""
        from .handlers.update_handlers import WeatherAppUpdateHandlers

        WeatherAppUpdateHandlers._on_update_available(self, update_info)

    def _on_update_progress(self, progress):
        """Handle update progress - delegate to update handlers."""
        from .handlers.update_handlers import WeatherAppUpdateHandlers

        WeatherAppUpdateHandlers._on_update_progress(self, progress)

    def _load_update_settings(self):
        """Load update settings - delegate to update handlers."""
        from .handlers.update_handlers import WeatherAppUpdateHandlers

        WeatherAppUpdateHandlers._load_update_settings(self)

    # UpdateLocationDropdown is now implemented in WeatherAppLocationHandlers

    # UpdateWeatherData, UpdateAlerts, _FetchWeatherData, and _check_update_complete
    # are now implemented in WeatherAppRefreshHandlers

    # OnClose, OnMinimize, and _stop_fetcher_threads are now implemented in WeatherAppSystemHandlers

    def _on_national_forecast_fetched(self, forecast_data):
        """Handle the fetched national forecast in the main thread - delegate to service coordination."""
        return self.service_coordination._on_national_forecast_fetched(forecast_data)

    def _on_current_conditions_fetched(self, conditions_data):
        """Handle the fetched current conditions in the main thread - delegate to service coordination."""
        return self.service_coordination._on_current_conditions_fetched(conditions_data)

    def _on_current_conditions_error(self, error):
        """Handle current conditions fetch error - delegate to service coordination."""
        return self.service_coordination._on_current_conditions_error(error)

    def _on_hourly_forecast_fetched(self, hourly_forecast_data):
        """Handle the fetched hourly forecast in the main thread - delegate to service coordination."""
        return self.service_coordination._on_hourly_forecast_fetched(hourly_forecast_data)

    def _on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread - delegate to service coordination."""
        return self.service_coordination._on_forecast_fetched(forecast_data)

    def _on_forecast_error(self, error):
        """Handle forecast fetch error - delegate to service coordination."""
        return self.service_coordination._on_forecast_error(error)

    def _on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread - delegate to service coordination."""
        return self.service_coordination._on_alerts_fetched(alerts_data)

    def _on_alerts_error(self, error):
        """Handle alerts fetch error - delegate to service coordination."""
        return self.service_coordination._on_alerts_error(error)

    def _on_discussion_fetched(self, discussion_text, name, loading_dialog):
        """Handle the fetched discussion in the main thread - delegate to service coordination."""
        return self.service_coordination._on_discussion_fetched(
            discussion_text, name, loading_dialog
        )

    def _on_discussion_error(self, error_message, name, loading_dialog):
        """Handle discussion fetch error in the main thread - delegate to service coordination."""
        return self.service_coordination._on_discussion_error(error_message, name, loading_dialog)

    # For backward compatibility with WeatherAppHandlers
    @property
    def location_manager(self):
        """Provide backward compatibility with the location_manager property."""
        return self.core.location_manager

    @property
    def notifier(self):
        """Provide backward compatibility with the notifier property."""
        return self.core.notifier

    def _handle_data_source_change(self):
        """Handle changes to the data source or API settings - delegate to core module."""
        self.core.handle_data_source_change()

    def test_alert_update(self):
        """Manually trigger an alert update for testing purposes - delegate to UI management module."""
        self.ui_management.test_alert_update()

    def verify_update_interval(self):
        """Verify the unified update interval by logging detailed information - delegate to UI management module."""
        self.ui_management.verify_update_interval()
