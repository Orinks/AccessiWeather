"""Builders for forecast-related presentation objects."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, tzinfo

from ...forecast_confidence import ForecastConfidence
from ...models import AppSettings, Forecast, ForecastPeriod, HourlyForecast, Location
from ...utils import TemperatureUnit
from ..weather_presenter import (
    ForecastPeriodPresentation,
    ForecastPresentation,
    HourlyPeriodPresentation,
)
from .formatters import (
    format_display_time,
    format_forecast_temperature,
    format_hourly_wind,
    format_period_temperature,
    format_period_wind,
    format_timestamp,
    get_temperature_precision,
    get_uv_description,
    wrap_text,
)


def _is_us_location(location: Location) -> bool:
    """Determine whether a location should use US/NWS forecast limits."""
    country_code = getattr(location, "country_code", None)
    if country_code:
        return country_code.upper() == "US"

    lat = location.latitude
    lon = location.longitude
    in_continental_bounds = 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0
    in_alaska_bounds = 51.0 <= lat <= 71.5 and -172.0 <= lon <= -130.0
    in_hawaii_bounds = 18.0 <= lat <= 23.0 and -161.0 <= lon <= -154.0
    return in_continental_bounds or in_alaska_bounds or in_hawaii_bounds


def _looks_like_half_day_periods(forecast: Forecast) -> bool:
    """Heuristic: identify NWS-style day/night period lists."""
    periods = forecast.periods or []

    # If we have timestamped periods with ~12-hour spacing, treat as half-day periods.
    starts = [p.start_time for p in periods if p.start_time is not None]
    if len(starts) >= 3:
        diffs = []
        for i in range(1, len(starts)):
            diff_hours = abs((starts[i] - starts[i - 1]).total_seconds()) / 3600.0
            diffs.append(diff_hours)
        if diffs:
            avg = sum(diffs) / len(diffs)
            if avg <= 14:
                return True

    # Name fallback for common NWS period labels.
    nwsish_tokens = ("tonight", "overnight", "this afternoon", "this evening", "night ")
    return any(
        (p.name or "").strip().lower().find(tok) >= 0 for p in periods for tok in nwsish_tokens
    )


def _configured_forecast_days(settings: AppSettings | None) -> int:
    configured_days = getattr(settings, "forecast_duration_days", 7) if settings else 7
    if not isinstance(configured_days, int):
        configured_days = 7
    return max(3, min(configured_days, 16))


def _select_periods_by_day_window(forecast: Forecast, configured_days: int) -> list[ForecastPeriod]:
    """Select periods within a strict calendar-day window when timestamps are available."""
    periods = forecast.periods or []
    dated_periods = [p for p in periods if p.start_time is not None]

    # If timestamps are missing for most periods, fall back to count-based behavior.
    if len(dated_periods) < max(3, len(periods) // 2):
        if _looks_like_half_day_periods(forecast):
            return periods[: min(configured_days * 2, len(periods))]
        return periods[: min(configured_days, len(periods))]

    unique_days: list = []
    for p in sorted(dated_periods, key=lambda x: x.start_time):
        day = p.start_time.date()
        if day not in unique_days:
            unique_days.append(day)
        if len(unique_days) >= configured_days:
            break

    if not unique_days:
        return periods[: min(configured_days, len(periods))]

    allowed_days = set(unique_days)
    return [p for p in periods if p.start_time is not None and p.start_time.date() in allowed_days]


def build_forecast(
    forecast: Forecast,
    hourly_forecast: HourlyForecast | None,
    location: Location,
    unit_pref: TemperatureUnit,
    settings: AppSettings | None = None,
    *,
    confidence: ForecastConfidence | None = None,
) -> ForecastPresentation:
    """Create a structured forecast including optional hourly highlights."""
    title = f"Forecast for {location.name}"
    round_values = getattr(settings, "round_values", False) if settings else False
    precision = 0 if round_values else get_temperature_precision(unit_pref)

    periods: list[ForecastPeriodPresentation] = []
    summary_line = f"Overall: {forecast.summary}" if forecast.summary else None
    fallback_lines = [f"Forecast for {location.name}:\n"]
    if summary_line:
        fallback_lines.append(summary_line)

    if hourly_forecast and hourly_forecast.has_data():
        hourly = build_hourly_summary(hourly_forecast, unit_pref, settings=settings)
    else:
        hourly = []

    # Extract time display preferences and verbosity from settings
    if settings:
        time_display_mode = getattr(settings, "time_display_mode", "local")
        time_format_12hour = getattr(settings, "time_format_12hour", True)
        show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
        verbosity_level = getattr(settings, "verbosity_level", "standard")
    else:
        time_display_mode = "local"
        time_format_12hour = True
        show_timezone_suffix = False
        verbosity_level = "standard"

    # Determine which fields to include based on verbosity level
    # minimal: temperature, conditions only
    # standard: temperature, conditions, wind, precipitation
    # detailed: all available fields
    include_wind = verbosity_level in ("standard", "detailed")
    include_precipitation = verbosity_level in ("standard", "detailed")
    include_uv = verbosity_level == "detailed"
    include_snowfall = verbosity_level == "detailed"
    include_details = verbosity_level == "detailed"
    include_cloud_cover = verbosity_level == "detailed"
    include_wind_gust = verbosity_level == "detailed"
    configured_days = _configured_forecast_days(settings)
    selected_periods = _select_periods_by_day_window(forecast, configured_days)

    for period in selected_periods:
        temp_pair = format_forecast_temperature(period, unit_pref, precision)
        wind_value = format_period_wind(period) if include_wind else None
        details = (
            period.detailed_forecast
            if include_details
            and period.detailed_forecast
            and period.detailed_forecast != period.short_forecast
            else None
        )

        # Format extended fields based on verbosity
        precip_prob = (
            f"{int(period.precipitation_probability)}%"
            if include_precipitation and period.precipitation_probability is not None
            else None
        )
        snowfall_val = (
            f"{period.snowfall:.{precision}f} in"
            if include_snowfall and period.snowfall is not None and period.snowfall > 0
            else None
        )
        uv_val = (
            f"{period.uv_index:.0f} ({get_uv_description(period.uv_index)})"
            if include_uv and period.uv_index is not None
            else None
        )
        cloud_val = (
            f"{period.cloud_cover:.0f}%"
            if include_cloud_cover and period.cloud_cover is not None
            else None
        )
        gust_val = period.wind_gust if include_wind_gust and period.wind_gust else None
        precip_amt = (
            f"{period.precipitation_amount:.{precision}f} in"
            if include_precipitation
            and period.precipitation_amount is not None
            and period.precipitation_amount > 0
            else None
        )

        periods.append(
            ForecastPeriodPresentation(
                name=period.name or "Unknown",
                temperature=temp_pair,
                conditions=period.short_forecast,
                wind=wind_value,
                details=details,
                precipitation_probability=precip_prob,
                snowfall=snowfall_val,
                uv_index=uv_val,
                cloud_cover=cloud_val,
                wind_gust=gust_val,
                precipitation_amount=precip_amt,
            )
        )

        fallback_lines.append(f"{period.name or 'Unknown'}: {temp_pair or 'N/A'}")
        if period.short_forecast:
            fallback_lines.append(f"  Conditions: {period.short_forecast}")
        if wind_value:
            fallback_lines.append(f"  Wind: {wind_value}")
        if gust_val:
            fallback_lines.append(f"  Wind gusts: {gust_val}")
        if precip_prob:
            fallback_lines.append(f"  Precipitation: {precip_prob}")
        if precip_amt:
            fallback_lines.append(f"  Precipitation amount: {precip_amt}")
        if snowfall_val:
            fallback_lines.append(f"  Snowfall: {snowfall_val}")
        if cloud_val:
            fallback_lines.append(f"  Cloud cover: {cloud_val}")
        if uv_val:
            fallback_lines.append(f"  UV Index: {uv_val}")
        if details:
            fallback_lines.append(f"  Details: {wrap_text(details, 80)}")

    generated_at = (
        format_timestamp(
            forecast.generated_at,
            time_display_mode=time_display_mode,
            use_12hour=time_format_12hour,
            show_timezone=show_timezone_suffix,
        )
        if forecast.generated_at
        else None
    )
    if generated_at:
        fallback_lines.append(f"\nForecast generated: {generated_at}")

    if hourly:
        fallback_lines.append(render_hourly_fallback(hourly))

    # Append cross-source confidence summary when available
    confidence_label: str | None = None
    if confidence is not None:
        level_str = confidence.level.value  # 'High', 'Medium', 'Low'
        fallback_lines.append(f"\nForecast confidence: {level_str}. {confidence.rationale}.")
        confidence_label = f"Confidence: {level_str}"

    fallback_text = "\n".join(fallback_lines).rstrip()

    return ForecastPresentation(
        title=title,
        periods=periods,
        hourly_periods=hourly,
        generated_at=generated_at,
        fallback_text=fallback_text,
        confidence_label=confidence_label,
        summary=summary_line,
    )


def build_hourly_summary(
    hourly_forecast: HourlyForecast,
    unit_pref: TemperatureUnit,
    settings: AppSettings | None = None,
) -> list[HourlyPeriodPresentation]:
    """Generate the next six hours of simplified forecast data."""
    round_values = getattr(settings, "round_values", False) if settings else False
    precision = 0 if round_values else get_temperature_precision(unit_pref)
    summary: list[HourlyPeriodPresentation] = []

    # Extract time display preferences and verbosity from settings
    if settings:
        time_display_mode = getattr(settings, "time_display_mode", "local")
        time_format_12hour = getattr(settings, "time_format_12hour", True)
        show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
        forecast_time_reference = getattr(settings, "forecast_time_reference", "location")
        verbosity_level = getattr(settings, "verbosity_level", "standard")
    else:
        time_display_mode = "local"
        time_format_12hour = True
        show_timezone_suffix = False
        forecast_time_reference = "location"
        verbosity_level = "standard"

    # Determine which fields to include based on verbosity level
    # minimal: temperature, conditions only
    # standard: temperature, conditions, wind, precipitation
    # detailed: all available fields
    include_wind = verbosity_level in ("standard", "detailed")
    include_precipitation = verbosity_level in ("standard", "detailed")
    include_uv = verbosity_level == "detailed"
    include_snowfall = verbosity_level == "detailed"
    include_cloud_cover = verbosity_level == "detailed"
    include_wind_gust = verbosity_level == "detailed"

    hourly_hours = getattr(settings, "hourly_forecast_hours", 6) if settings else 6
    hourly_hours = max(1, min(hourly_hours, 168))
    for period in hourly_forecast.get_next_hours(hourly_hours):
        if not period.has_data():
            continue
        temperature = format_period_temperature(period, unit_pref, precision)
        wind = format_hourly_wind(period) if include_wind else None

        # Use enhanced time formatter with user preferences
        display_time = _resolve_forecast_display_time(
            period.start_time,
            forecast_time_reference=forecast_time_reference,
        )
        time_str = format_display_time(
            display_time,
            time_display_mode=time_display_mode,
            use_12hour=time_format_12hour,
            show_timezone=show_timezone_suffix,
        )

        # Format extended fields based on verbosity
        precip_prob = (
            f"{int(period.precipitation_probability)}%"
            if include_precipitation and period.precipitation_probability is not None
            else None
        )
        snowfall_val = (
            f"{period.snowfall:.{precision}f} in"
            if include_snowfall and period.snowfall is not None and period.snowfall > 0
            else None
        )
        uv_val = (
            f"{period.uv_index:.0f} ({get_uv_description(period.uv_index)})"
            if include_uv and period.uv_index is not None
            else None
        )
        cloud_val = (
            f"{period.cloud_cover:.0f}%"
            if include_cloud_cover and period.cloud_cover is not None
            else None
        )
        gust_val = (
            f"{period.wind_gust_mph:.0f} mph"
            if include_wind_gust and period.wind_gust_mph is not None
            else None
        )
        precip_amt = (
            f"{period.precipitation_amount:.{precision}f} in"
            if include_precipitation
            and period.precipitation_amount is not None
            and period.precipitation_amount > 0
            else None
        )

        summary.append(
            HourlyPeriodPresentation(
                time=time_str,
                temperature=temperature,
                conditions=period.short_forecast,
                wind=wind,
                precipitation_probability=precip_prob,
                snowfall=snowfall_val,
                uv_index=uv_val,
                cloud_cover=cloud_val,
                wind_gust=gust_val,
                precipitation_amount=precip_amt,
            )
        )
    return summary


def _resolve_forecast_display_time(
    start_time: datetime,
    *,
    forecast_time_reference: str,
    local_timezone: tzinfo | None = None,
) -> datetime:
    """
    Resolve forecast hour display time to the configured timezone reference.

    Location mode keeps the source timestamp unchanged. My-local mode converts
    timezone-aware values to the system's local timezone.
    """
    if forecast_time_reference != "user_local":
        return start_time
    if start_time.tzinfo is None:
        return start_time

    target_tz = local_timezone or datetime.now().astimezone().tzinfo
    if target_tz is None:
        return start_time.astimezone()
    return start_time.astimezone(target_tz)


def render_hourly_fallback(hourly: Iterable[HourlyPeriodPresentation]) -> str:
    """Render hourly periods into fallback text."""
    lines = ["Next 6 Hours:"]
    for period in hourly:
        parts = [period.time]
        if period.temperature:
            parts.append(period.temperature)
        if period.conditions:
            parts.append(period.conditions)
        if period.wind:
            parts.append(f"Wind {period.wind}")
        if period.precipitation_probability:
            parts.append(f"Precip {period.precipitation_probability}")
        if period.snowfall:
            parts.append(f"Snow {period.snowfall}")
        if period.cloud_cover:
            parts.append(f"Clouds {period.cloud_cover}")
        if period.wind_gust:
            parts.append(f"Gusts {period.wind_gust}")
        if period.precipitation_amount:
            parts.append(f"Precip amt {period.precipitation_amount}")
        if period.uv_index:
            parts.append(f"UV {period.uv_index}")
        lines.append("  " + " - ".join(parts))
    return "\n".join(lines)
