"""Legacy-compatible text formatter wrappers.

These thin wrappers keep existing call-sites working while the application migrates
to the structured :class:`WeatherPresenter` API.
"""

from __future__ import annotations

from .display import WeatherPresenter
from .models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlerts,
    WeatherData,
)


class WeatherFormatter:
    """Adapter that exposes text formatting from the structured presenter."""

    def __init__(self, settings: AppSettings):
        """Create the adapter for compatibility layers."""
        self.presenter = WeatherPresenter(settings)

    def format_current_conditions(
        self, current: CurrentConditions | None, location: Location
    ) -> str:
        presentation = self.presenter.present_current(current, location)
        if presentation is None:
            return f"Current conditions for {location.name}:\nNo current weather data available."
        return presentation.fallback_text

    def format_forecast(
        self,
        forecast: Forecast | None,
        location: Location,
        hourly_forecast: HourlyForecast | None = None,
    ) -> str:
        presentation = self.presenter.present_forecast(forecast, location, hourly_forecast)
        if presentation is None:
            return f"Forecast for {location.name}:\nNo forecast data available."
        return presentation.fallback_text

    def format_alerts(self, alerts: WeatherAlerts | None, location: Location) -> str:
        presentation = self.presenter.present_alerts(alerts, location)
        if presentation is None:
            return f"Weather alerts for {location.name}:\nNo active weather alerts."
        return presentation.fallback_text

    def format_weather_summary(self, weather_data: WeatherData) -> str:
        presentation = self.presenter.present(weather_data)
        return presentation.summary_text
