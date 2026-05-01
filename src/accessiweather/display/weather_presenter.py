"""
Weather presentation helpers for AccessiWeather.

Provides structured view models for current conditions, forecasts, and alerts while
maintaining accessible fallback text for screen reader users.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from accessiweather.alert_lifecycle import AlertLifecycleDiff

    from ..forecast_confidence import ForecastConfidence

from ..models import (
    AppSettings,
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    HourlyForecast,
    Location,
    MarineForecast,
    TrendInsight,
    WeatherAlerts,
    WeatherData,
)
from ..services.mobility_briefing import build_mobility_briefing
from ..units import resolve_display_unit_system, resolve_temperature_unit_preference
from ..utils import TemperatureUnit
from .presentation.aviation import build_aviation
from .presentation.environmental import AirQualityPresentation, build_air_quality_panel
from .presentation.models import (
    AlertPresentation,
    AlertsPresentation,
    AviationPresentation,
    CurrentConditionsPresentation,
    ForecastPeriodPresentation,
    ForecastPresentation,
    HourlyPeriodPresentation,
    Metric,
    SourceAttributionPresentation,
    WeatherPresentation,
)
from .presentation.source_attribution import build_source_attribution

__all__ = [
    "AlertPresentation",
    "AlertsPresentation",
    "AviationPresentation",
    "CurrentConditionsPresentation",
    "ForecastPeriodPresentation",
    "ForecastPresentation",
    "HourlyPeriodPresentation",
    "Metric",
    "SourceAttributionPresentation",
    "WeatherPresentation",
    "WeatherPresenter",
]


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
        unit_pref, unit_system = self._resolve_unit_preferences(weather_data.location)

        air_quality_panel = (
            build_air_quality_panel(
                weather_data.location, weather_data.environmental, settings=self.settings
            )
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
                minutely_precipitation=weather_data.minutely_precipitation,
                air_quality=air_quality_panel,
                alerts=weather_data.alerts,
                unit_system=unit_system,
                anomaly_callout=getattr(weather_data, "anomaly_callout", None),
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
                marine=weather_data.marine,
                confidence=weather_data.forecast_confidence,
                mobility_briefing=build_mobility_briefing(weather_data),
            )
            if weather_data.forecast
            else None
        )
        alerts = (
            self._build_alerts(
                weather_data.alerts,
                weather_data.location,
                lifecycle_diff=weather_data.alert_lifecycle_diff,
            )
            if weather_data.alerts
            else None
        )
        aviation = self._build_aviation(weather_data.aviation, weather_data.location)
        summary_text = self._build_summary(weather_data, unit_pref)
        trend_summary = format_trend_lines(
            weather_data.trend_insights,
            current=weather_data.current,
            hourly_forecast=weather_data.hourly_forecast,
            include_pressure=getattr(self.settings, "show_pressure_trend", True),
        )
        status_messages = self._build_status_messages(weather_data)
        source_attribution = self._build_source_attribution(weather_data)

        return WeatherPresentation(
            location_name=weather_data.location.name,
            summary_text=summary_text,
            current_conditions=current,
            forecast=forecast,
            alerts=alerts,
            air_quality=air_quality_panel,
            aviation=aviation,
            trend_summary=trend_summary,
            status_messages=status_messages,
            source_attribution=source_attribution,
        )

    def present_current(
        self,
        current: CurrentConditions | None,
        location: Location,
        *,
        environmental: EnvironmentalConditions | None = None,
        trends: Iterable[TrendInsight] | None = None,
        hourly_forecast: HourlyForecast | None = None,
        alerts: WeatherAlerts | None = None,
    ) -> CurrentConditionsPresentation | None:
        if not current or not current.has_data():
            return None
        unit_pref, unit_system = self._resolve_unit_preferences(location)
        air_quality_panel = (
            build_air_quality_panel(location, environmental, settings=self.settings)
            if environmental
            else None
        )
        return self._build_current_conditions(
            current,
            location,
            unit_pref,
            settings=self.settings,
            environmental=environmental,
            trends=trends,
            hourly_forecast=hourly_forecast,
            minutely_precipitation=None,
            air_quality=air_quality_panel,
            alerts=alerts,
            unit_system=unit_system,
        )

    def present_forecast(
        self,
        forecast: Forecast | None,
        location: Location,
        hourly_forecast: HourlyForecast | None = None,
        marine: MarineForecast | None = None,
        confidence: ForecastConfidence | None = None,
        mobility_briefing: str | None = None,
    ) -> ForecastPresentation | None:
        if not forecast or not forecast.has_data():
            return None
        unit_pref, _unit_system = self._resolve_unit_preferences(location)
        return self._build_forecast(
            forecast,
            hourly_forecast,
            location,
            unit_pref,
            confidence=confidence,
            mobility_briefing=mobility_briefing,
            marine=marine,
        )

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
        minutely_precipitation=None,
        air_quality: AirQualityPresentation | None = None,
        alerts: WeatherAlerts | None = None,
        unit_system=None,
        anomaly_callout=None,
    ) -> CurrentConditionsPresentation:
        return build_current_conditions(
            current,
            location,
            unit_pref,
            settings=settings or self.settings,
            environmental=environmental,
            trends=trends,
            hourly_forecast=hourly_forecast,
            minutely_precipitation=minutely_precipitation,
            air_quality=air_quality,
            alerts=alerts,
            unit_system=unit_system,
            anomaly_callout=anomaly_callout,
        )

    def _build_forecast(
        self,
        forecast: Forecast,
        hourly_forecast: HourlyForecast | None,
        location: Location,
        unit_pref: TemperatureUnit,
        marine: MarineForecast | None = None,
        confidence: ForecastConfidence | None = None,
        mobility_briefing: str | None = None,
    ) -> ForecastPresentation:
        return build_forecast(
            forecast,
            hourly_forecast,
            location,
            unit_pref,
            settings=self.settings,
            marine=marine,
            confidence=confidence,
            mobility_briefing=mobility_briefing,
        )

    def _build_alerts(
        self,
        alerts: WeatherAlerts,
        location: Location,
        lifecycle_diff: AlertLifecycleDiff | None = None,
    ) -> AlertsPresentation:
        return build_alerts(alerts, location, settings=self.settings, lifecycle_diff=lifecycle_diff)

    def _build_aviation(
        self, aviation: AviationData | None, location: Location
    ) -> AviationPresentation | None:
        return build_aviation(aviation, location, self._format_timestamp)

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

    def _build_source_attribution(
        self, weather_data: WeatherData
    ) -> SourceAttributionPresentation | None:
        return build_source_attribution(weather_data)

    def _resolve_unit_preferences(
        self, location: Location
    ) -> tuple[TemperatureUnit, object | None]:
        preference = getattr(self.settings, "temperature_unit", "both")
        return (
            resolve_temperature_unit_preference(preference, location),
            resolve_display_unit_system(preference, location),
        )

    def _format_timestamp(self, value: datetime) -> str:
        mode = getattr(self.settings, "time_display_mode", "local")
        use_12hour = getattr(self.settings, "time_format_12hour", True)
        show_timezone = getattr(self.settings, "show_timezone_suffix", False)

        return format_display_datetime(
            value,
            time_display_mode=mode,
            use_12hour=use_12hour,
            show_timezone=show_timezone,
        )


from .presentation.alerts import build_alerts  # noqa: E402
from .presentation.current_conditions import (  # noqa: E402
    build_current_conditions,
    format_trend_lines,
)
from .presentation.forecast import build_forecast  # noqa: E402
from .presentation.formatters import (  # noqa: E402
    format_display_datetime,
    format_temperature_pair,
)
