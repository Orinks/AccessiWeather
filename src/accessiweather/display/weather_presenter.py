"""Weather presentation helpers for AccessiWeather.

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
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from ..utils import (
    TemperatureUnit,
    calculate_dewpoint,
    convert_wind_direction_to_cardinal,
    format_pressure,
    format_temperature,
    format_visibility,
    format_wind_speed,
)


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
    current: CurrentConditionsPresentation | None = None
    forecast: ForecastPresentation | None = None
    alerts: AlertsPresentation | None = None
    trend_summary: list[str] = field(default_factory=list)
    status_messages: list[str] = field(default_factory=list)


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

        current = (
            self._build_current_conditions(
                weather_data.current,
                weather_data.location,
                unit_pref,
                weather_data.environmental,
                weather_data.trend_insights,
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
        trend_summary = self._format_trend_lines(weather_data.trend_insights)
        status_messages = self._build_status_messages(weather_data)

        return WeatherPresentation(
            location_name=weather_data.location.name,
            summary_text=summary_text,
            current=current,
            forecast=forecast,
            alerts=alerts,
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
    ) -> CurrentConditionsPresentation | None:
        if not current or not current.has_data():
            return None
        unit_pref = self._get_temperature_unit_preference()
        return self._build_current_conditions(current, location, unit_pref, environmental, trends)

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
        environmental: EnvironmentalConditions | None = None,
        trends: Iterable[TrendInsight] | None = None,
    ) -> CurrentConditionsPresentation:
        title = f"Current conditions for {location.name}"
        description = current.condition or "Unknown"
        precision = self._get_temperature_precision(unit_pref)

        temperature_str = self._format_temperature_pair(
            current.temperature_f, current.temperature_c, unit_pref, precision
        )
        metrics: list[Metric] = [Metric("Temperature", temperature_str)]

        if current.feels_like_f is not None or current.feels_like_c is not None:
            feels_like = self._format_temperature_pair(
                current.feels_like_f, current.feels_like_c, unit_pref, precision
            )
            if feels_like:
                metrics.append(Metric("Feels like", feels_like))

        if current.humidity is not None:
            metrics.append(Metric("Humidity", f"{current.humidity:.0f}%"))

        wind_value = self._format_wind(current, unit_pref)
        if wind_value:
            metrics.append(Metric("Wind", wind_value))

        dewpoint_value = self._format_dewpoint(current, unit_pref, precision)
        if dewpoint_value:
            metrics.append(Metric("Dewpoint", dewpoint_value))

        pressure_value = self._format_pressure(current, unit_pref)
        if pressure_value:
            metrics.append(Metric("Pressure", pressure_value))

        visibility_value = self._format_visibility(current, unit_pref)
        if visibility_value:
            metrics.append(Metric("Visibility", visibility_value))

        if current.uv_index is not None:
            uv_desc = self._get_uv_description(current.uv_index)
            metrics.append(Metric("UV Index", f"{current.uv_index} ({uv_desc})"))

        if current.last_updated:
            timestamp = current.last_updated
            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone()
            metrics.append(Metric("Last updated", timestamp.strftime("%I:%M %p")))

        if environmental:
            if environmental.air_quality_index is not None:
                aq_label = (
                    f"{environmental.air_quality_index:.0f}"
                    if environmental.air_quality_index is not None
                    else ""
                )
                if environmental.air_quality_category:
                    aq_label = f"{aq_label} ({environmental.air_quality_category})" if aq_label else environmental.air_quality_category
                if environmental.air_quality_pollutant:
                    pollutant = environmental.air_quality_pollutant
                    aq_label = f"{aq_label} – {pollutant}" if aq_label else pollutant
                metrics.append(Metric("Air Quality", aq_label or "Data unavailable"))
            if environmental.pollen_index is not None or environmental.pollen_primary_allergen:
                pollen_value = (
                    f"{environmental.pollen_index:.0f}" if environmental.pollen_index is not None else ""
                )
                if environmental.pollen_category:
                    pollen_value = (
                        f"{pollen_value} ({environmental.pollen_category})"
                        if pollen_value
                        else environmental.pollen_category
                    )
                if environmental.pollen_primary_allergen:
                    pollen_value = (
                        f"{pollen_value} – {environmental.pollen_primary_allergen}"
                        if pollen_value
                        else environmental.pollen_primary_allergen
                    )
                metrics.append(Metric("Pollen", pollen_value or "Data unavailable"))

        if trends:
            for trend in trends:
                summary = trend.summary or self._describe_trend(trend)
                metrics.append(Metric(f"{trend.metric.title()} trend", summary))

        fallback_lines = [f"Current Conditions: {description}", f"Temperature: {temperature_str}"]
        for metric in metrics[1:]:  # already added temperature
            fallback_lines.append(f"{metric.label}: {metric.value}")
        fallback_text = "\n".join(fallback_lines)

        return CurrentConditionsPresentation(
            title=title,
            description=description,
            metrics=metrics,
            fallback_text=fallback_text,
        )

    def _build_forecast(
        self,
        forecast: Forecast,
        hourly_forecast: HourlyForecast | None,
        location: Location,
        unit_pref: TemperatureUnit,
    ) -> ForecastPresentation:
        title = f"Forecast for {location.name}"
        precision = self._get_temperature_precision(unit_pref)

        periods: list[ForecastPeriodPresentation] = []
        fallback_lines = [f"Forecast for {location.name}:\n"]

        if hourly_forecast and hourly_forecast.has_data():
            hourly = self._build_hourly_summary(hourly_forecast, unit_pref)
        else:
            hourly = []

        for period in forecast.periods[:14]:
            temp_pair = self._format_forecast_temperature(period, unit_pref, precision)
            wind_value = self._format_period_wind(period)
            details = (
                period.detailed_forecast
                if period.detailed_forecast and period.detailed_forecast != period.short_forecast
                else None
            )
            periods.append(
                ForecastPeriodPresentation(
                    name=period.name or "Unknown",
                    temperature=temp_pair,
                    conditions=period.short_forecast,
                    wind=wind_value,
                    details=details,
                )
            )

            fallback_lines.append(f"{period.name or 'Unknown'}: {temp_pair or 'N/A'}")
            if period.short_forecast:
                fallback_lines.append(f"  Conditions: {period.short_forecast}")
            if wind_value:
                fallback_lines.append(f"  Wind: {wind_value}")
            if details:
                fallback_lines.append(f"  Details: {self._wrap_text(details, 80)}")

        generated_at = forecast.generated_at.strftime("%I:%M %p") if forecast.generated_at else None
        if generated_at:
            fallback_lines.append(f"\nForecast generated: {generated_at}")

        if hourly:
            fallback_lines.insert(1, self._render_hourly_fallback(hourly))

        fallback_text = "\n".join(fallback_lines).rstrip()

        return ForecastPresentation(
            title=title,
            periods=periods,
            hourly_periods=hourly,
            generated_at=generated_at,
            fallback_text=fallback_text,
        )

    def _build_alerts(self, alerts: WeatherAlerts, location: Location) -> AlertsPresentation:
        title = f"Weather alerts for {location.name}"
        if not alerts.has_alerts():
            return AlertsPresentation(
                title=title, fallback_text=f"{title}:\nNo active weather alerts."
            )

        active = alerts.get_active_alerts()
        if not active:
            return AlertsPresentation(
                title=title, fallback_text=f"{title}:\nNo active weather alerts."
            )

        presentations: list[AlertPresentation] = []
        fallback_lines = [title + ":"]

        for idx, alert in enumerate(active, start=1):
            presentation = self._build_single_alert(alert, idx)
            presentations.append(presentation)
            fallback_lines.append(presentation.fallback_text)

        fallback_text = "\n\n".join(fallback_lines)
        return AlertsPresentation(title=title, alerts=presentations, fallback_text=fallback_text)

    def _build_single_alert(self, alert: WeatherAlert, index: int) -> AlertPresentation:
        severity = alert.severity if alert.severity != "Unknown" else None
        urgency = alert.urgency if alert.urgency != "Unknown" else None
        areas = alert.areas[:3] if alert.areas else []
        expires = alert.expires.strftime("%m/%d %I:%M %p") if alert.expires else None

        description = None
        if alert.description:
            description = self._truncate(alert.description, 200)
        instruction = None
        if alert.instruction:
            instruction = self._truncate(alert.instruction, 150)

        parts: list[str] = [f"Alert {index}: {alert.title}" if alert.title else f"Alert {index}"]
        if severity or urgency:
            sev_bits = []
            if severity:
                sev_bits.append(f"Severity: {severity}")
            if urgency:
                sev_bits.append(f"Urgency: {urgency}")
            parts.append("  " + ", ".join(sev_bits))
        if alert.event:
            parts.append(f"  Event: {alert.event}")
        if areas:
            remaining = len(alert.areas) - len(areas)
            area_text = ", ".join(areas)
            if remaining > 0:
                area_text += f" and {remaining} more"
            parts.append(f"  Areas: {area_text}")
        if expires:
            parts.append(f"  Expires: {expires}")
        if description:
            parts.append(f"  Description: {self._wrap_text(description, 80)}")
        if instruction:
            parts.append(f"  Instructions: {self._wrap_text(instruction, 80)}")

        fallback_text = "\n".join(parts)
        return AlertPresentation(
            title=alert.title or alert.event or f"Alert {index}",
            severity=severity,
            urgency=urgency,
            event=alert.event,
            areas=alert.areas or [],
            expires=expires,
            description=description,
            instructions=instruction,
            fallback_text=fallback_text,
        )

    def _build_summary(self, weather_data: WeatherData, unit_pref: TemperatureUnit) -> str:
        if not weather_data.has_any_data():
            return f"No weather data available for {weather_data.location.name}"

        parts: list[str] = [weather_data.location.name]

        current = weather_data.current
        if current and current.has_data():
            temp = self._format_temperature_pair(
                current.temperature_f, current.temperature_c, unit_pref, 0
            )
            if temp:
                parts.append(temp)
            if current.condition:
                parts.append(current.condition)

        if weather_data.alerts and weather_data.alerts.has_alerts():
            active_count = len(weather_data.alerts.get_active_alerts())
            if active_count > 0:
                parts.append(f"{active_count} alert{'s' if active_count != 1 else ''}")


        trend_lines = self._format_trend_lines(weather_data.trend_insights)
        if trend_lines:
            parts.append(trend_lines[0])

        if weather_data.stale:
            stale_message = "Cached data"
            if weather_data.stale_since:
                stale_message = f"Cached {self._format_timestamp(weather_data.stale_since)}"
            parts.append(stale_message)
        return " - ".join(parts)


    def _format_trend_lines(self, trends: Iterable[TrendInsight] | None) -> list[str]:
        lines: list[str] = []
        if not trends:
            return lines
        for trend in trends:
            summary = trend.summary or self._describe_trend(trend)
            if trend.sparkline:
                summary = f"{summary} {trend.sparkline}".strip()
            if summary:
                lines.append(summary)
        return lines

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

    def _format_timestamp(self, value: datetime) -> str:
        ref = value.astimezone() if value.tzinfo else value
        return ref.strftime("%b %d %I:%M %p")

    def _describe_trend(self, trend: TrendInsight) -> str:
        direction = (trend.direction or "steady").capitalize()
        timeframe = trend.timeframe_hours or 24
        change_text = ""
        if trend.change is not None:
            if trend.unit in {"°F", "°C"}:
                change_text = f"{trend.change:+.1f}{trend.unit}"
            elif trend.unit:
                change_text = f"{trend.change:+.2f}{trend.unit}"
            else:
                change_text = f"{trend.change:+.1f}"
        pieces = [direction]
        if change_text:
            pieces.append(change_text)
        pieces.append(f"over {timeframe}h")
        return " ".join(pieces)
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_temperature_pair(
        self,
        temp_f: float | None,
        temp_c: float | None,
        unit_pref: TemperatureUnit,
        precision: int,
    ) -> str | None:
        if temp_f is None and temp_c is None:
            return None
        return format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=precision)

    def _format_wind(self, current: CurrentConditions, unit_pref: TemperatureUnit) -> str | None:
        if (
            current.wind_speed_mph is None
            and current.wind_speed_kph is None
            and current.wind_direction is None
        ):
            return None

        speed_mph = current.wind_speed_mph
        if speed_mph is None and current.wind_speed_kph is not None:
            speed_mph = current.wind_speed_kph * 0.621371

        if speed_mph is not None and abs(speed_mph) < 0.5:
            return "Calm"

        direction = None
        if current.wind_direction is not None:
            if isinstance(current.wind_direction, (int, float)):
                direction = convert_wind_direction_to_cardinal(current.wind_direction)
            else:
                direction = str(current.wind_direction)

        speed = format_wind_speed(
            current.wind_speed_mph,
            unit_pref,
            wind_speed_kph=current.wind_speed_kph,
            precision=1,
        )
        if direction and speed:
            return f"{direction} at {speed}"
        if speed:
            return speed
        return direction

    def _format_dewpoint(
        self,
        current: CurrentConditions,
        unit_pref: TemperatureUnit,
        precision: int,
    ) -> str | None:
        dewpoint_f = current.dewpoint_f
        dewpoint_c = current.dewpoint_c

        if dewpoint_f is None and dewpoint_c is None:
            if current.temperature_f is None or current.humidity is None:
                return None
            dewpoint_f = calculate_dewpoint(
                current.temperature_f,
                current.humidity,
                unit=TemperatureUnit.FAHRENHEIT,
            )
            if dewpoint_f is None:
                return None
            dewpoint_c = (dewpoint_f - 32) * 5 / 9

        return format_temperature(
            dewpoint_f,
            unit_pref,
            temperature_c=dewpoint_c,
            precision=precision,
        )

    def _format_pressure(
        self,
        current: CurrentConditions,
        unit_pref: TemperatureUnit,
    ) -> str | None:
        if current.pressure_in is None and current.pressure_mb is None:
            return None
        pressure_in = current.pressure_in
        pressure_mb = current.pressure_mb
        if pressure_in is None and pressure_mb is not None:
            pressure_in = pressure_mb / 33.8639
        return format_pressure(pressure_in, unit_pref, pressure_mb=pressure_mb, precision=0)

    def _format_visibility(
        self,
        current: CurrentConditions,
        unit_pref: TemperatureUnit,
    ) -> str | None:
        if current.visibility_miles is None and current.visibility_km is None:
            return None
        return format_visibility(
            current.visibility_miles,
            unit_pref,
            visibility_km=current.visibility_km,
            precision=1,
        )

    def _format_forecast_temperature(
        self,
        period: ForecastPeriod,
        unit_pref: TemperatureUnit,
        precision: int,
    ) -> str | None:
        if period.temperature is None:
            return None
        temp = period.temperature
        unit = (period.temperature_unit or "F").upper()
        if unit == "F":
            temp_f = temp
            temp_c = (temp - 32) * 5 / 9
        else:
            temp_c = temp
            temp_f = (temp * 9 / 5) + 32
        return format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=precision)

    def _format_period_wind(self, period: ForecastPeriod) -> str | None:
        if not period.wind_speed and not period.wind_direction:
            return None
        parts: list[str] = []
        if period.wind_direction:
            parts.append(period.wind_direction)
        if period.wind_speed:
            parts.append(period.wind_speed)
        return " ".join(parts) if parts else None

    def _build_hourly_summary(
        self,
        hourly_forecast: HourlyForecast,
        unit_pref: TemperatureUnit,
    ) -> list[HourlyPeriodPresentation]:
        precision = self._get_temperature_precision(unit_pref)
        summary: list[HourlyPeriodPresentation] = []
        for period in hourly_forecast.get_next_hours(6):
            if not period.has_data():
                continue
            temperature = self._format_period_temperature(period, unit_pref, precision)
            wind = None
            if period.wind_speed and period.wind_direction:
                wind = f"{period.wind_direction} at {period.wind_speed}"
            summary.append(
                HourlyPeriodPresentation(
                    time=self._format_hour_time(period.start_time),
                    temperature=temperature,
                    conditions=period.short_forecast,
                    wind=wind,
                )
            )
        return summary

    def _format_period_temperature(
        self,
        period: HourlyForecastPeriod,
        unit_pref: TemperatureUnit,
        precision: int,
    ) -> str | None:
        if period.temperature is None:
            return None
        temp = period.temperature
        unit = (period.temperature_unit or "F").upper()
        if unit == "F":
            temp_f = temp
            temp_c = (temp - 32) * 5 / 9
        else:
            temp_c = temp
            temp_f = (temp * 9 / 5) + 32
        return format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=precision)

    def _render_hourly_fallback(self, hourly: Iterable[HourlyPeriodPresentation]) -> str:
        lines = ["Next 6 Hours:"]
        for period in hourly:
            parts = [period.time]
            if period.temperature:
                parts.append(period.temperature)
            if period.conditions:
                parts.append(period.conditions)
            if period.wind:
                parts.append(f"Wind {period.wind}")
            lines.append("  " + " - ".join(parts))
        return "\n".join(lines)

    def _get_temperature_unit_preference(self) -> TemperatureUnit:
        unit_pref = (self.settings.temperature_unit or "both").lower()
        if unit_pref in {"fahrenheit", "f"}:
            return TemperatureUnit.FAHRENHEIT
        if unit_pref in {"celsius", "c"}:
            return TemperatureUnit.CELSIUS
        return TemperatureUnit.BOTH

    def _get_temperature_precision(self, unit_pref: TemperatureUnit) -> int:
        return 0 if unit_pref == TemperatureUnit.BOTH else 1

    @staticmethod
    def _wrap_text(text: str, width: int) -> str:
        words = text.split()
        if not words:
            return text
        lines: list[str] = []
        current_line: list[str] = []
        current_length = 0
        for word in words:
            if current_length + len(word) + (1 if current_line else 0) > width:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + (1 if current_line[:-1] else 0)
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    @staticmethod
    def _format_hour_time(start_time: datetime | None) -> str:
        if not start_time:
            return "Unknown"
        return start_time.strftime("%I:%M %p")

    @staticmethod
    def _get_uv_description(uv_index: float) -> str:
        if uv_index < 3:
            return "Low"
        if uv_index < 6:
            return "Moderate"
        if uv_index < 8:
            return "High"
        if uv_index < 11:
            return "Very High"
        return "Extreme"
