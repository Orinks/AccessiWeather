"""Timer management module for AccessiWeather.

This module handles timer-based operations for the WeatherApp,
including periodic weather data updates and interval management.
"""

import logging
import time

from .settings_dialog import UPDATE_INTERVAL_KEY

logger = logging.getLogger(__name__)


class TimerManager:
    """Handles timer-based operations for the WeatherApp."""

    def __init__(self, app_instance):
        """Initialize the TimerManager.

        Args:
            app_instance: The WeatherApp instance
        """
        self.app = app_instance
        self.logger = logger

    def on_timer(self, event):
        """Handle timer event for periodic updates.

        Args:
            event: Timer event
        """
        # Get update interval from config (default to 10 minutes)
        settings = self.app.config.get("settings", {})
        update_interval_minutes = settings.get(UPDATE_INTERVAL_KEY, 10)
        update_interval_seconds = update_interval_minutes * 60

        # Calculate time since last update
        now = time.time()
        time_since_last_update = now - self.app.last_update
        next_update_in = update_interval_seconds - time_since_last_update

        # Enhanced logging in debug mode
        if self.app.debug_mode:
            self.logger.info(
                f"[DEBUG] Timer check: interval={update_interval_minutes}min, "
                f"time_since_last={time_since_last_update:.1f}s, "
                f"next_update_in={next_update_in:.1f}s"
            )
        else:
            # Regular debug logging
            self.logger.debug(
                f"Timer check: interval={update_interval_minutes}min, "
                f"time_since_last={time_since_last_update:.1f}s, "
                f"next_update_in={next_update_in:.1f}s"
            )

        # Check if it's time to update
        if time_since_last_update >= update_interval_seconds:
            if not self.app.updating:
                self.logger.info(
                    f"Timer triggered weather update. "
                    f"Interval: {update_interval_minutes} minutes, "
                    f"Time since last update: {time_since_last_update:.1f} seconds"
                )
                self.app.UpdateWeatherData()
            else:
                self.logger.debug("Timer skipped update: already updating.")

    def get_update_interval_info(self):
        """Get detailed information about the update interval.

        Returns:
            Dict containing update interval information
        """
        settings = self.app.config.get("settings", {})
        update_interval_minutes = settings.get(UPDATE_INTERVAL_KEY, 10)
        update_interval_seconds = update_interval_minutes * 60

        now = time.time()
        time_since_last_update = now - self.app.last_update
        next_update_in = update_interval_seconds - time_since_last_update

        return {
            "interval_minutes": update_interval_minutes,
            "interval_seconds": update_interval_seconds,
            "last_update": self.app.last_update,
            "current_time": now,
            "time_since_last": time_since_last_update,
            "next_update_in": next_update_in,
            "update_due": time_since_last_update >= update_interval_seconds,
        }

    def verify_update_interval(self):
        """Verify the unified update interval by logging detailed information.

        This method is only available in debug mode.
        """
        if not self.app.debug_mode:
            self.logger.warning("verify_update_interval called but debug mode is not enabled")
            return

        info = self.get_update_interval_info()

        # Log detailed information
        self.logger.info(
            f"[DEBUG] Update interval verification:\n"
            f"  - Configured interval: {info['interval_minutes']} minutes ({info['interval_seconds']} seconds)\n"
            f"  - Last update timestamp: {info['last_update']} ({time.ctime(info['last_update'])})\n"
            f"  - Current timestamp: {info['current_time']} ({time.ctime(info['current_time'])})\n"
            f"  - Time since last update: {info['time_since_last']:.1f} seconds\n"
            f"  - Next update in: {info['next_update_in']:.1f} seconds\n"
            f"  - Update due: {'Yes' if info['update_due'] else 'No'}"
        )
