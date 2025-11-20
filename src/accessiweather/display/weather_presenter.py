"""
Weather presentation helpers for AccessiWeather.

Provides structured view models for current conditions, forecasts, and alerts while
maintaining accessible fallback text for screen reader users.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..models import (
    AppSettings,
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    HourlyForecast,
    Location,
    TrendInsight,
    WeatherAlerts,
    WeatherData,
)
from ..utils import TemperatureUnit, decode_taf_text
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
class AviationPresentation:
    """Structured aviation weather presentation."""

    title: str
    airport_name: str | None = None
    station_id: str | None = None
    taf_summary: str | None = None
    raw_taf: str | None = None
    sigmets: list[str] = field(default_factory=list)
    cwas: list[str] = field(default_factory=list)
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
    aviation: AviationPresentation | None = None
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
        aviation = self._build_aviation(weather_data.aviation, weather_data.location)
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
            aviation=aviation,
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
        return build_forecast(
            forecast, hourly_forecast, location, unit_pref, settings=self.settings
        )

    def _build_alerts(self, alerts: WeatherAlerts, location: Location) -> AlertsPresentation:
        return build_alerts(alerts, location, settings=self.settings)

    def _build_aviation(
        self, aviation: AviationData | None, location: Location
    ) -> AviationPresentation | None:
        if aviation is None:
            return None

        has_advisories = bool(aviation.active_sigmets or aviation.active_cwas)
        taf_available = bool(
            (aviation.raw_taf and aviation.raw_taf.strip())
            or (aviation.decoded_taf and aviation.decoded_taf.strip())
        )
        if not (taf_available or has_advisories):
            return None

        station_label = aviation.airport_name or aviation.station_id
        header_location = (
            f"{station_label} near {location.name}"
            if station_label and station_label.lower() != location.name.lower()
            else station_label or location.name
        )
        header = f"Aviation weather for {header_location}."

        taf_summary = aviation.decoded_taf
        if not taf_summary and aviation.raw_taf:
            taf_summary = decode_taf_text(aviation.raw_taf)

        sigmet_lines = [
            summary
            for summary in (self._summarize_sigmet(entry) for entry in aviation.active_sigmets[:5])
            if summary
        ]
        cwa_lines = [
            summary
            for summary in (self._summarize_cwa(entry) for entry in aviation.active_cwas[:5])
            if summary
        ]

        fallback_lines: list[str] = [header]
        if taf_summary:
            fallback_lines.append("Terminal Aerodrome Forecast:")
            fallback_lines.append(taf_summary)
            if aviation.raw_taf and aviation.raw_taf.strip():
                fallback_lines.append("Raw TAF message:")
                fallback_lines.append(aviation.raw_taf.strip())
        elif aviation.raw_taf and aviation.raw_taf.strip():
            fallback_lines.append("Raw Terminal Aerodrome Forecast:")
            fallback_lines.append(aviation.raw_taf.strip())
        else:
            fallback_lines.append("No Terminal Aerodrome Forecast available.")

        if sigmet_lines:
            fallback_lines.append("SIGMET and AIRMET advisories:")
            fallback_lines.extend(f"• {line}" for line in sigmet_lines)
        if cwa_lines:
            fallback_lines.append("Center Weather Advisories:")
            fallback_lines.extend(f"• {line}" for line in cwa_lines)

        return AviationPresentation(
            title="Aviation Weather",
            airport_name=aviation.airport_name,
            station_id=aviation.station_id,
            taf_summary=taf_summary,
            raw_taf=aviation.raw_taf,
            sigmets=sigmet_lines,
            cwas=cwa_lines,
            fallback_text="\n".join(fallback_lines),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_aviation_time(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            sanitized = value.replace("Z", "+00:00") if value.endswith("Z") else value
            timestamp = datetime.fromisoformat(sanitized)
        except ValueError:
            return value
        return self._format_timestamp(timestamp)

    def _summarize_sigmet(self, data: Any) -> str | None:
        if not isinstance(data, dict):
            return None

        name = (
            data.get("name")
            or data.get("event")
            or data.get("hazard")
            or data.get("phenomenon")
            or "SIGMET"
        )
        severity = data.get("severity") or data.get("intensity")
        area = data.get("fir") or data.get("area") or data.get("regions") or data.get("airspace")
        if isinstance(area, list):
            area = ", ".join(str(item) for item in area if item)

        start = self._format_aviation_time(
            data.get("startTime")
            or data.get("beginTime")
            or data.get("validTimeStart")
            or data.get("issueTime")
        )
        end = self._format_aviation_time(
            data.get("endTime")
            or data.get("expires")
            or data.get("validTimeEnd")
            or data.get("validUntil")
        )
        description = data.get("description") or data.get("text") or data.get("summary")

        summary_parts = [name]
        if severity:
            summary_parts.append(f"severity {severity}")
        summary = " ".join(summary_parts)

        detail_parts: list[str] = []
        if area:
            detail_parts.append(f"Area: {area}")
        if start or end:
            if start and end:
                detail_parts.append(f"Valid {start} to {end}")
            elif end:
                detail_parts.append(f"Valid until {end}")
            elif start:
                detail_parts.append(f"Effective {start}")
        if description:
            detail_parts.append(description)

        details = "; ".join(detail_parts)
        return f"{summary}; {details}" if details else summary

    def _summarize_cwa(self, data: Any) -> str | None:
        if not isinstance(data, dict):
            return None

        name = (
            data.get("event")
            or data.get("phenomenon")
            or data.get("hazard")
            or data.get("productType")
            or "Center Weather Advisory"
        )
        cwsu = data.get("cwsu") or data.get("issuingOffice")
        area = data.get("area") or data.get("regions") or data.get("airspace") or cwsu
        if isinstance(area, list):
            area = ", ".join(str(item) for item in area if item)

        start = self._format_aviation_time(data.get("startTime") or data.get("issueTime"))
        end = self._format_aviation_time(data.get("endTime") or data.get("expires"))
        description = data.get("description") or data.get("text") or data.get("summary")

        summary_parts = [name]
        if cwsu and cwsu not in summary_parts:
            summary_parts.append(f"({cwsu})")
        summary = " ".join(summary_parts)

        detail_parts: list[str] = []
        if area and area not in summary:
            detail_parts.append(f"Area: {area}")
        if start or end:
            if start and end:
                detail_parts.append(f"Valid {start} to {end}")
            elif end:
                detail_parts.append(f"Valid until {end}")
            elif start:
                detail_parts.append(f"Issued {start}")
        if description:
            detail_parts.append(description)

        details = "; ".join(detail_parts)
        return f"{summary}; {details}" if details else summary

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
