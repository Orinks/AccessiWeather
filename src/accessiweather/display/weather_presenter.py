"""
Weather presentation helpers for AccessiWeather.

Provides structured view models for current conditions, forecasts, and alerts while
maintaining accessible fallback text for screen reader users.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from ..models import (
    AppSettings,
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    HourlyForecast,
    Location,
    TrendInsight,
    WeatherAlerts,
    WeatherData,
)
from ..utils import TemperatureUnit
from .presentation.environmental import AirQualityPresentation, build_air_quality_panel


@dataclass(slots=True)
class Metric:
    """Key-value pair used for presenting weather measurements."""

    label: str
    value: str


@dataclass(slots=True)
class HourlyPeriodPresentation:
    """Simplified hourly forecast period for structured display."""

    time: str
    temperature: str | None
    conditions: str | None
    wind: str | None


@dataclass(slots=True)
class ForecastPeriodPresentation:
    """Daily forecast period presentation."""

    name: str
    temperature: str | None
    conditions: str | None
    wind: str | None
    details: str | None


@dataclass(slots=True)
class CurrentConditionsPresentation:
    """Structured view of the current conditions."""

    title: str
    description: str
    metrics: list[Metric] = field(default_factory=list)
    fallback_text: str = ""
    trends: list[str] = field(default_factory=list)

    @property
    def trend_summary(self) -> list[str]:  # pragma: no cover - backward compatibility
        """Alias for legacy callers expecting ``trend_summary``."""
        return self.trends


@dataclass(slots=True)
class ForecastPresentation:
    """Structured forecast view including hourly highlights."""

    title: str
    periods: list[ForecastPeriodPresentation] = field(default_factory=list)
    hourly_periods: list[HourlyPeriodPresentation] = field(default_factory=list)
    generated_at: str | None = None
    fallback_text: str = ""


@dataclass(slots=True)
class AlertPresentation:
    """Structured weather alert presentation."""

    title: str
    severity: str | None = None
    urgency: str | None = None
    event: str | None = None
    areas: list[str] = field(default_factory=list)
    expires: str | None = None
    description: str | None = None
    instructions: str | None = None
    fallback_text: str = ""


@dataclass(slots=True)
class AlertsPresentation:
    """Collection of alert presentations with fallback text."""

    title: str
    alerts: list[AlertPresentation] = field(default_factory=list)
    fallback_text: str = ""


@dataclass(slots=True)
class WeatherPresentation:
    """Top-level presentation for all weather content."""

    location_name: str
    summary_text: str
    current_conditions: CurrentConditionsPresentation | None = None
    forecast: ForecastPresentation | None = None
    alerts: AlertsPresentation | None = None
    air_quality: AirQualityPresentation | None = None
    trend_summary: list[str] = field(default_factory=list)
    status_messages: list[str] = field(default_factory=list)

    @property
    def current(self) -> CurrentConditionsPresentation | None:  # pragma: no cover - compat
        """Backward-compatible alias for older presentation attribute name."""
        return self.current_conditions

    @current.setter
    def current(
        self, value: CurrentConditionsPresentation | None
    ) -> None:  # pragma: no cover - compat
        self.current_conditions = value


class WeatherPresenter:
    """Create structured and accessible representations of weather data."""

    def __init__(self, settings: AppSettings):
        """Store the active application settings for presentation decisions."""
        self.settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def present(self, weather_data: WeatherData) -> WeatherPresentation:
        """Build a structured presentation for the given weather data."""
        unit_pref = self._get_temperature_unit_preference()

        air_quality_panel = (
            build_air_quality_panel(weather_data.location, weather_data.environmental)
            if weather_data.environmental
            else None
        )

        current = (
            self._build_current_conditions(
                weather_data.current,
                weather_data.location,
                unit_pref,
                settings=self.settings,
                environmental=weather_data.environmental,
                trends=weather_data.trend_insights,
                hourly_forecast=weather_data.hourly_forecast,
                air_quality=air_quality_panel,
            )
            if weather_data.current
            else None
        )
        forecast = (
            self._build_forecast(
                weather_data.forecast,
                weather_data.hourly_forecast,
                weather_data.location,
                unit_pref,
            )
            if weather_data.forecast
            else None
        )
        alerts = (
            self._build_alerts(weather_data.alerts, weather_data.location)
            if weather_data.alerts
            else None
        )
        summary_text = self._build_summary(weather_data, unit_pref)
        trend_summary = format_trend_lines(
            weather_data.trend_insights,
            current=weather_data.current,
            hourly_forecast=weather_data.hourly_forecast,
            include_pressure=getattr(self.settings, "show_pressure_trend", True),
        )
        status_messages = self._build_status_messages(weather_data)

        return WeatherPresentation(
            location_name=weather_data.location.name,
            summary_text=summary_text,
            current_conditions=current,
            forecast=forecast,
            alerts=alerts,
            air_quality=air_quality_panel,
            trend_summary=trend_summary,
            status_messages=status_messages,
        )

    def present_current(
        self,
        current: CurrentConditions | None,
        location: Location,
        *,
        environmental: EnvironmentalConditions | None = None,
        trends: Iterable[TrendInsight] | None = None,
        hourly_forecast: HourlyForecast | None = None,
    ) -> CurrentConditionsPresentation | None:
        if not current or not current.has_data():
            return None
        unit_pref = self._get_temperature_unit_preference()
        air_quality_panel = (
            build_air_quality_panel(location, environmental) if environmental else None
        )
        return self._build_current_conditions(
            current,
            location,
            unit_pref,
            settings=self.settings,
            environmental=environmental,
            trends=trends,
            hourly_forecast=hourly_forecast,
            air_quality=air_quality_panel,
        )

    def present_forecast(
        self,
        forecast: Forecast | None,
        location: Location,
        hourly_forecast: HourlyForecast | None = None,
    ) -> ForecastPresentation | None:
        if not forecast or not forecast.has_data():
            return None
        unit_pref = self._get_temperature_unit_preference()
        return self._build_forecast(forecast, hourly_forecast, location, unit_pref)

    def present_alerts(
        self, alerts: WeatherAlerts | None, location: Location
    ) -> AlertsPresentation | None:
        if not alerts:
            return None
        return self._build_alerts(alerts, location)

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _build_current_conditions(
        self,
        current: CurrentConditions,
        location: Location,
        unit_pref: TemperatureUnit,
        *,
        settings: AppSettings | None = None,
        environmental: EnvironmentalConditions | None = None,
        trends: Iterable[TrendInsight] | None = None,
        hourly_forecast: HourlyForecast | None = None,
        air_quality: AirQualityPresentation | None = None,
    ) -> CurrentConditionsPresentation:
        return build_current_conditions(
            current,
            location,
            unit_pref,
            settings=settings or self.settings,
            environmental=environmental,
            trends=trends,
            hourly_forecast=hourly_forecast,
            air_quality=air_quality,
        )

    def _build_forecast(
        self,
        forecast: Forecast,
        hourly_forecast: HourlyForecast | None,
        location: Location,
        unit_pref: TemperatureUnit,
    ) -> ForecastPresentation:
        return build_forecast(forecast, hourly_forecast, location, unit_pref)

    def _build_alerts(self, alerts: WeatherAlerts, location: Location) -> AlertsPresentation:
        return build_alerts(alerts, location)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_summary(self, weather_data: WeatherData, unit_pref: TemperatureUnit) -> str:
        if not weather_data.has_any_data():
            return f"No weather data available for {weather_data.location.name}"

        parts: list[str] = [weather_data.location.name]

        current = weather_data.current
        if current and current.has_data():
            temp = format_temperature_pair(
                current.temperature_f,
                current.temperature_c,
                unit_pref,
                precision=0,
            )
            if temp:
                parts.append(temp)
            if current.condition:
                parts.append(current.condition)

        if weather_data.alerts and weather_data.alerts.has_alerts():
            active_count = len(weather_data.alerts.get_active_alerts())
            if active_count > 0:
                parts.append(f"{active_count} alert{'s' if active_count != 1 else ''}")

        trend_lines = format_trend_lines(
            weather_data.trend_insights,
            current=weather_data.current,
            hourly_forecast=weather_data.hourly_forecast,
        )
        if trend_lines:
            parts.append(trend_lines[0])

        if weather_data.stale:
            stale_message = "Cached data"
            if weather_data.stale_since:
                stale_message = f"Cached {self._format_timestamp(weather_data.stale_since)}"
            parts.append(stale_message)
        return " - ".join(parts)

    def _build_status_messages(self, weather_data: WeatherData) -> list[str]:
        messages: list[str] = []
        if weather_data.stale:
            timestamp = (
                self._format_timestamp(weather_data.stale_since)
                if weather_data.stale_since
                else None
            )
            reason = weather_data.stale_reason or "cached data"
            if timestamp:
                messages.append(f"Showing cached data from {timestamp} ({reason}).")
            else:
                messages.append(f"Showing cached weather data ({reason}).")
        return messages

    def _get_temperature_unit_preference(self) -> TemperatureUnit:
        unit_pref = (self.settings.temperature_unit or "both").lower()
        if unit_pref in {"fahrenheit", "f"}:
            return TemperatureUnit.FAHRENHEIT
        if unit_pref in {"celsius", "c"}:
            return TemperatureUnit.CELSIUS
        return TemperatureUnit.BOTH

    def _format_timestamp(self, value: datetime) -> str:
        ref = value.astimezone() if value.tzinfo else value
        return ref.strftime("%b %d %I:%M %p")


from .presentation.alerts import build_alerts  # noqa: E402
from .presentation.current_conditions import (  # noqa: E402
    build_current_conditions,
    format_trend_lines,
)
from .presentation.forecast import build_forecast  # noqa: E402
from .presentation.formatters import format_temperature_pair  # noqa: E402
