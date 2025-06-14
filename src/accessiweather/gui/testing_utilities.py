"""Testing utilities module for AccessiWeather.

This module contains debug and testing functionality for the WeatherApp,
including alert testing and update interval verification.
"""

import logging

from .settings_dialog import ALERT_RADIUS_KEY, PRECISE_LOCATION_ALERTS_KEY

logger = logging.getLogger(__name__)


class TestingUtilities:
    """Handles debug and testing functionality for the WeatherApp."""

    def __init__(self, app_instance):
        """Initialize the TestingUtilities.
        
        Args:
            app_instance: The WeatherApp instance
        """
        self.app = app_instance
        self.logger = logger

    def test_alert_update(self):
        """Manually trigger an alert update for testing purposes.

        This method is only available in debug mode.
        """
        if not self.app.debug_mode:
            self.logger.warning("test_alert_update called but debug mode is not enabled")
            return

        self.logger.info("[DEBUG] Manually triggering alert update")

        # Get current location
        location = self.app.location_service.get_current_location()
        if not location:
            self.logger.error("[DEBUG ALERTS] No location selected for alert testing")
            return

        # Extract coordinates
        _, lat, lon = location

        # Get alert settings from config
        settings = self.app.config.get("settings", {})
        precise_location = settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
        alert_radius = settings.get(ALERT_RADIUS_KEY, 25)

        # Log the alert fetch parameters
        self.logger.info(
            f"[DEBUG ALERTS] Fetching alerts for coordinates ({lat}, {lon}), "
            f"precise_location={precise_location}, radius={alert_radius}"
        )

        # Start alerts fetching thread
        self.app.alerts_fetcher.fetch(
            lat,
            lon,
            on_success=self.app.callback_handlers.on_alerts_fetched,
            on_error=self.app.callback_handlers.on_alerts_error,
            precise_location=precise_location,
            radius=alert_radius,
        )

    def verify_update_interval(self):
        """Verify the unified update interval by logging detailed information.

        This method is only available in debug mode.
        """
        if not self.app.debug_mode:
            self.logger.warning("verify_update_interval called but debug mode is not enabled")
            return

        # Delegate to timer manager for detailed verification
        if hasattr(self.app, 'timer_manager') and self.app.timer_manager:
            self.app.timer_manager.verify_update_interval()
        else:
            self.logger.error("Timer manager not available for update interval verification")

    def get_debug_info(self):
        """Get comprehensive debug information about the application state.
        
        Returns:
            Dict containing debug information
        """
        if not self.app.debug_mode:
            self.logger.warning("get_debug_info called but debug mode is not enabled")
            return {}

        debug_info = {
            "debug_mode": self.app.debug_mode,
            "current_location": None,
            "last_update": self.app.last_update,
            "updating": self.app.updating,
            "forecast_complete": self.app._forecast_complete,
            "alerts_complete": self.app._alerts_complete,
            "services": {
                "weather_service": self.app.weather_service is not None,
                "location_service": self.app.location_service is not None,
                "notification_service": self.app.notification_service is not None,
            },
            "fetchers": {
                "forecast_fetcher": self.app.forecast_fetcher is not None,
                "alerts_fetcher": self.app.alerts_fetcher is not None,
                "discussion_fetcher": self.app.discussion_fetcher is not None,
                "current_conditions_fetcher": self.app.current_conditions_fetcher is not None,
                "hourly_forecast_fetcher": self.app.hourly_forecast_fetcher is not None,
                "national_forecast_fetcher": self.app.national_forecast_fetcher is not None,
            }
        }

        # Get current location info
        try:
            location = self.app.location_service.get_current_location()
            if location:
                debug_info["current_location"] = {
                    "name": location[0],
                    "lat": location[1],
                    "lon": location[2]
                }
        except Exception as e:
            debug_info["current_location"] = f"Error getting location: {e}"

        # Get timer info if available
        if hasattr(self.app, 'timer_manager') and self.app.timer_manager:
            try:
                debug_info["timer_info"] = self.app.timer_manager.get_update_interval_info()
            except Exception as e:
                debug_info["timer_info"] = f"Error getting timer info: {e}"

        return debug_info

    def log_debug_info(self):
        """Log comprehensive debug information about the application state."""
        if not self.app.debug_mode:
            self.logger.warning("log_debug_info called but debug mode is not enabled")
            return

        debug_info = self.get_debug_info()
        
        self.logger.info("[DEBUG] Application State Information:")
        for key, value in debug_info.items():
            if isinstance(value, dict):
                self.logger.info(f"  {key}:")
                for sub_key, sub_value in value.items():
                    self.logger.info(f"    {sub_key}: {sub_value}")
            else:
                self.logger.info(f"  {key}: {value}")

    def test_weather_update(self):
        """Manually trigger a weather data update for testing purposes.

        This method is only available in debug mode.
        """
        if not self.app.debug_mode:
            self.logger.warning("test_weather_update called but debug mode is not enabled")
            return

        self.logger.info("[DEBUG] Manually triggering weather data update")
        self.app.UpdateWeatherData()

    def test_location_update(self):
        """Manually trigger a location dropdown update for testing purposes.

        This method is only available in debug mode.
        """
        if not self.app.debug_mode:
            self.logger.warning("test_location_update called but debug mode is not enabled")
            return

        self.logger.info("[DEBUG] Manually triggering location dropdown update")
        self.app.UpdateLocationDropdown()
