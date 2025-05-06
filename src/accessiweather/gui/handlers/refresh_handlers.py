"""Refresh handlers for the WeatherApp class

This module contains the refresh-related handlers for the WeatherApp class.
"""

import logging
import time

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppRefreshHandlers(WeatherAppHandlerBase):
    """Refresh handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides refresh-related event handlers for the WeatherApp class.
    """

    def OnRefresh(self, event):  # event is required by wx
        """Handle refresh button click

        Args:
            event: Button event
        """
        # Trigger weather data update
        self.UpdateWeatherData()

    def UpdateWeatherData(self, event=None):
        """Update all weather data including forecasts and alerts.

        Args:
            event: Optional event parameter (required for wx event handlers)
        """
        # Even if updating is true, we still want to proceed if this is a
        # location change
        # This is to ensure that location changes always trigger a data refresh

        # Get current location from the location service
        location = self.location_service.get_current_location()
        if location is None:
            self.SetStatusText("No location selected")
            return

        # Always reset updating flag to ensure we can fetch for a new location
        # This is critical for location changes to work properly
        self.updating = True

        # Set status text to indicate update is in progress
        self.SetStatusText("Updating weather data...")

        # Fetch both forecast and alert data
        self._FetchWeatherData(location)

    def _FetchWeatherData(self, location):
        """Fetch weather data using the weather service

        Args:
            location: Tuple of (name, lat, lon)
        """
        name, lat, lon = location

        # Reset completion flags for this fetch cycle
        self._forecast_complete = False
        self._alerts_complete = False

        # Check if this is the nationwide location
        is_nationwide = self.location_service.is_nationwide_location(name)

        # Show loading state
        self.ui_manager.display_loading_state(name, is_nationwide)

        # Check if this is the nationwide location
        if is_nationwide:
            # Nationwide: Use the dedicated async fetcher
            logger.info("Initiating nationwide forecast fetch using NationalForecastFetcher")
            self.national_forecast_fetcher.fetch(
                on_success=self._on_national_forecast_fetched, on_error=self._on_forecast_error
            )
            return  # Return after initiating the fetch

        # For backward compatibility, use api_client directly if provided
        if self.api_client:
            # Start current conditions fetching thread
            self.current_conditions_fetcher.fetch(
                lat,
                lon,
                on_success=self._on_current_conditions_fetched,
                on_error=self._on_current_conditions_error,
            )

            # Start hourly forecast fetching thread
            self.hourly_forecast_fetcher.fetch(
                lat,
                lon,
                on_success=self._on_hourly_forecast_fetched,
                on_error=self._on_forecast_error,
            )

            # Start forecast fetching thread using api_client
            self.forecast_fetcher.fetch(
                lat, lon, on_success=self._on_forecast_fetched, on_error=self._on_forecast_error
            )

            # Get precise location setting from config
            from ..settings_dialog import ALERT_RADIUS_KEY, PRECISE_LOCATION_ALERTS_KEY

            precise_location = self.config.get("settings", {}).get(
                PRECISE_LOCATION_ALERTS_KEY, True
            )
            alert_radius = self.config.get("settings", {}).get(ALERT_RADIUS_KEY, 25)

            # Start alerts fetching thread with precise location setting using api_client
            self.alerts_fetcher.fetch(
                lat,
                lon,
                on_success=self._on_alerts_fetched,
                on_error=self._on_alerts_error,
                precise_location=precise_location,
                radius=alert_radius,
            )
        else:
            # Use weather service for newer code path
            try:
                # Get forecast data
                forecast_data = self.weather_service.get_forecast(lat, lon)
                self._on_forecast_fetched(forecast_data)

                # Get alerts data
                from ..settings_dialog import ALERT_RADIUS_KEY, PRECISE_LOCATION_ALERTS_KEY

                precise_location = self.config.get("settings", {}).get(
                    PRECISE_LOCATION_ALERTS_KEY, True
                )
                alert_radius = self.config.get("settings", {}).get(ALERT_RADIUS_KEY, 25)
                alerts_data = self.weather_service.get_alerts(
                    lat, lon, radius=alert_radius, precise_location=precise_location
                )
                self._on_alerts_fetched(alerts_data)
            except Exception as e:
                error_msg = f"Error fetching weather data: {str(e)}"
                logger.error(error_msg)
                self._on_forecast_error(error_msg)
                self._on_alerts_error(error_msg)

    def _check_update_complete(self):
        """Check if both forecast and alerts fetches are complete."""
        if self._forecast_complete and self._alerts_complete:
            # Update is complete, set updating flag to false
            self.updating = False

            # Update the last_update timestamp for both forecast and alerts
            current_time = time.time()
            self.last_update = current_time
            self.last_alerts_update = current_time

            # Format time for status bar
            formatted_time = time.strftime("%I:%M %p", time.localtime(current_time))
            self.SetStatusText(f"Weather data updated at {formatted_time}")

            # Update UI to ready state
            self.ui_manager.display_ready_state()
