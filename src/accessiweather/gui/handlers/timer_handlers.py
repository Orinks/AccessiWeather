"""Timer handlers for the WeatherApp class

This module contains the timer-related handlers for the WeatherApp class.
"""

import logging
import time

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppTimerHandlers(WeatherAppHandlerBase):
    """Timer handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides timer-related event handlers for the WeatherApp class.
    """

    def OnTimer(self, event):  # event is required by wx
        """Handle timer event for periodic updates

        Args:
            event: Timer event
        """
        # Get update interval from config (default to 30 minutes)
        from ..settings_dialog import UPDATE_INTERVAL_KEY

        # Get settings section
        settings = self.config.get("settings", {})

        # Get update interval
        update_interval_minutes = settings.get(UPDATE_INTERVAL_KEY, 30)
        update_interval_seconds = update_interval_minutes * 60

        # Calculate time since last update
        now = time.time()
        time_since_last_update = now - self.last_update
        next_update_in = update_interval_seconds - time_since_last_update

        # Log timer status at debug level
        logger.debug(
            f"Timer check: interval={update_interval_minutes}min, "
            f"time_since_last={time_since_last_update:.1f}s, "
            f"next_update_in={next_update_in:.1f}s"
        )

        # Check if it's time to update
        if time_since_last_update >= update_interval_seconds:
            if not self.updating:
                logger.info(
                    f"Timer triggered weather update. "
                    f"Interval: {update_interval_minutes} minutes, "
                    f"Time since last update: {time_since_last_update:.1f} seconds"
                )
                # Update all weather data (forecasts and alerts)
                self.UpdateWeatherData()

                # If auto-refresh for national data is enabled and we're on the nationwide view, update that too
                current_location = self.location_service.get_current_location_name()
                if (
                    current_location
                    and self.location_service.is_nationwide_location(current_location)
                    and settings.get("auto_refresh_national", True)
                ):
                    logger.info("Timer triggered national data update for nationwide view")
                    self.UpdateNationalData()
            else:
                logger.debug("Timer skipped update: already updating.")
