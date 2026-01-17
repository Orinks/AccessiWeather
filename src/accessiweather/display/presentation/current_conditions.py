"""Builders for current conditions presentation objects."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from ...models import (
    AppSettings,
    CurrentConditions,
    EnvironmentalConditions,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
    WeatherAlerts,
)
from ...utils import TemperatureUnit
from ..priority_engine import PriorityEngine, WeatherCategory
from ..weather_presenter import CurrentConditionsPresentation, Metric
from .environmental import AirQualityPresentation
from .formatters import (
    format_dewpoint,
    format_pressure_value,
    format_sun_time,
    format_temperature_with_feels_like,
    format_visibility_value,
    format_wind,
    get_temperature_precision,
    get_uv_description,
)

logger = logging.getLogger(__name__)


def _build_basic_metrics(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: int,
    show_dewpoint: bool,
    show_visibility: bool,
    show_uv_index: bool,
) -> list[Metric]:
    """Build basic weather metrics (temperature, feels like, humidity, wind, dewpoint, etc.)."""
    # Format temperature with inline feels-like when there's a significant difference
    temperature_value, feels_like_reason = format_temperature_with_feels_like(
        current, unit_pref, precision
    )
    metrics: list[Metric] = [Metric("Temperature", temperature_value)]

    # Add reason as a separate metric if available (for accessibility)
    if feels_like_reason:
        metrics.append(Metric("Feels different", feels_like_reason.capitalize()))

    if current.humidity is not None:
        metrics.append(Metric("Humidity", f"{current.humidity:.0f}%"))

    wind_value = format_wind(current, unit_pref)
    if wind_value:
        metrics.append(Metric("Wind", wind_value))

    dewpoint_value = format_dewpoint(current, unit_pref, precision)
    if show_dewpoint and dewpoint_value:
        metrics.append(Metric("Dewpoint", dewpoint_value))

    pressure_value = format_pressure_value(current, unit_pref)
    if pressure_value:
        metrics.append(Metric("Pressure", pressure_value))

    visibility_value = format_visibility_value(current, unit_pref)
    if show_visibility and visibility_value:
        metrics.append(Metric("Visibility", visibility_value))

    if show_uv_index and current.uv_index is not None:
        uv_desc = get_uv_description(current.uv_index)
        metrics.append(Metric("UV Index", f"{current.uv_index} ({uv_desc})"))

    return metrics


def _build_astronomical_metrics(
    current: CurrentConditions,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> list[Metric]:
    """Build astronomical metrics (sunrise, sunset, moon phase, moonrise, moonset)."""
    metrics: list[Metric] = []

    # Common kwargs for format_sun_time
    time_kwargs = {
        "time_display_mode": time_display_mode,
        "use_12hour": use_12hour,
        "show_timezone": show_timezone,
    }

    logger.info(
        f"Building astronomical metrics - sunrise_time: {current.sunrise_time}, sunset_time: {current.sunset_time}"
    )

    sunrise_str = format_sun_time(current.sunrise_time, **time_kwargs)
    if sunrise_str:
        logger.info(f"Formatted sunrise: {sunrise_str}")
        metrics.append(Metric("Sunrise", sunrise_str))

    sunset_str = format_sun_time(current.sunset_time, **time_kwargs)
    if sunset_str:
        logger.info(f"Formatted sunset: {sunset_str}")
        metrics.append(Metric("Sunset", sunset_str))

    if current.moon_phase:
        metrics.append(Metric("Moon phase", current.moon_phase))

    moonrise_str = format_sun_time(current.moonrise_time, **time_kwargs)
    if moonrise_str:
        metrics.append(Metric("Moonrise", moonrise_str))

    moonset_str = format_sun_time(current.moonset_time, **time_kwargs)
    if moonset_str:
        metrics.append(Metric("Moonset", moonset_str))

    return metrics


def _build_environmental_metrics(
    environmental: EnvironmentalConditions | None,
    air_quality: AirQualityPresentation | None,
) -> list[Metric]:
    """Build environmental metrics (air quality, pollen)."""
    metrics: list[Metric] = []

    if not environmental:
        return metrics

    # Air Quality
    aq_value_parts: list[str] = []
    summary_value: str | None = None
    if air_quality and air_quality.summary:
        summary_value = air_quality.summary
    elif environmental.air_quality_index is not None:
        aq_label = f"{environmental.air_quality_index:.0f}"
        if environmental.air_quality_category:
            aq_label = f"{aq_label} ({environmental.air_quality_category})"
        if environmental.air_quality_pollutant:
            aq_label = f"{aq_label} – {environmental.air_quality_pollutant}"
        summary_value = aq_label
    if summary_value:
        aq_value_parts.append(summary_value)
    if air_quality and air_quality.guidance:
        aq_value_parts.append(f"Advice: {air_quality.guidance}")
    if aq_value_parts:
        metrics.append(Metric("Air Quality", " | ".join(aq_value_parts)))

    # Pollen
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

    return metrics


def _build_trend_metrics(
    trends: Iterable[TrendInsight] | None,
    current: CurrentConditions,
    hourly_forecast: HourlyForecast | None,
    show_pressure_trend: bool,
) -> list[Metric]:
    """Build trend metrics (temperature, pressure, etc. trends)."""
    metrics: list[Metric] = []
    pressure_trend_present = False

    if trends:
        for trend in trends:
            summary = trend.summary or describe_trend(trend)
            if trend.sparkline:
                summary = f"{summary} {trend.sparkline}".strip()
            metric_name = getattr(trend, "metric", "")
            is_pressure = isinstance(metric_name, str) and metric_name.lower() == "pressure"
            if is_pressure and not show_pressure_trend:
                continue
            metrics.append(Metric(f"{trend.metric.title()} trend", summary))
            if is_pressure:
                pressure_trend_present = True

    if show_pressure_trend and not pressure_trend_present:
        legacy_pressure_trend = compute_pressure_trend_from_hourly(current, hourly_forecast)
        if legacy_pressure_trend:
            metrics.append(Metric("Pressure trend", legacy_pressure_trend["value"]))

    return metrics


def _build_seasonal_metrics(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: int,
) -> list[Metric]:
    """Build seasonal weather metrics (snow depth, wind chill, heat index, etc.)."""
    metrics: list[Metric] = []

    # Winter metrics
    if current.snow_depth_in is not None and current.snow_depth_in > 0:
        if unit_pref == TemperatureUnit.CELSIUS:
            snow_depth_cm = current.snow_depth_cm or current.snow_depth_in * 2.54
            metrics.append(Metric("Snow on ground", f"{snow_depth_cm:.1f} cm"))
        elif unit_pref == TemperatureUnit.FAHRENHEIT:
            metrics.append(Metric("Snow on ground", f"{current.snow_depth_in:.1f} in"))
        else:
            snow_depth_cm = current.snow_depth_cm or current.snow_depth_in * 2.54
            metrics.append(
                Metric("Snow on ground", f"{current.snow_depth_in:.1f} in ({snow_depth_cm:.1f} cm)")
            )

    if current.wind_chill_f is not None:
        # Only show wind chill if significantly different from temperature
        temp_f = current.temperature_f
        if temp_f is None or abs(current.wind_chill_f - temp_f) >= 3:
            wind_chill_c = current.wind_chill_c
            if wind_chill_c is None and current.wind_chill_f is not None:
                wind_chill_c = (current.wind_chill_f - 32) * 5 / 9
            wc_str = format_temperature_value(
                current.wind_chill_f, wind_chill_c, unit_pref, precision
            )
            if wc_str:
                metrics.append(Metric("Wind chill", wc_str))

    if current.freezing_level_ft is not None:
        if unit_pref == TemperatureUnit.CELSIUS:
            freezing_m = current.freezing_level_m or current.freezing_level_ft * 0.3048
            metrics.append(Metric("Freezing level", f"{freezing_m:.0f} m"))
        elif unit_pref == TemperatureUnit.FAHRENHEIT:
            metrics.append(Metric("Freezing level", f"{current.freezing_level_ft:.0f} ft"))
        else:
            freezing_m = current.freezing_level_m or current.freezing_level_ft * 0.3048
            metrics.append(
                Metric("Freezing level", f"{current.freezing_level_ft:.0f} ft ({freezing_m:.0f} m)")
            )

    # Summer metrics
    if current.heat_index_f is not None:
        # Only show heat index if significantly different from temperature
        temp_f = current.temperature_f
        if temp_f is None or abs(current.heat_index_f - temp_f) >= 3:
            heat_index_c = current.heat_index_c
            if heat_index_c is None and current.heat_index_f is not None:
                heat_index_c = (current.heat_index_f - 32) * 5 / 9
            hi_str = format_temperature_value(
                current.heat_index_f, heat_index_c, unit_pref, precision
            )
            if hi_str:
                metrics.append(Metric("Heat index", hi_str))

    # Spring/Fall metrics
    if current.frost_risk is not None and current.frost_risk.lower() != "none":
        metrics.append(Metric("Frost risk", current.frost_risk))

    # Year-round metrics - only show precipitation type when there's active precipitation
    # Check for active precipitation indicators: precipitation amount, or condition suggests precip
    has_active_precip = False
    if current.precipitation_type and len(current.precipitation_type) > 0:
        # Check if condition indicates active precipitation
        condition_lower = (current.condition or "").lower()
        precip_keywords = ["rain", "snow", "drizzle", "shower", "storm", "sleet", "hail", "precip"]
        has_active_precip = any(keyword in condition_lower for keyword in precip_keywords)

    if has_active_precip and current.precipitation_type:
        precip_types = ", ".join(current.precipitation_type)
        metrics.append(Metric("Precipitation type", precip_types.title()))

    if current.severe_weather_risk is not None and current.severe_weather_risk > 0:
        risk_level = _get_severe_risk_description(current.severe_weather_risk)
        metrics.append(
            Metric("Severe weather risk", f"{current.severe_weather_risk}% ({risk_level})")
        )

    return metrics


def format_temperature_value(
    temp_f: float | None,
    temp_c: float | None,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Format a temperature value based on unit preference."""
    if temp_f is None and temp_c is None:
        return None

    if unit_pref == TemperatureUnit.FAHRENHEIT:
        if temp_f is not None:
            return f"{temp_f:.{precision}f}°F"
        return None
    if unit_pref == TemperatureUnit.CELSIUS:
        if temp_c is not None:
            return f"{temp_c:.{precision}f}°C"
        if temp_f is not None:
            temp_c = (temp_f - 32) * 5 / 9
            return f"{temp_c:.{precision}f}°C"
        return None
    # BOTH
    if temp_f is not None:
        if temp_c is None:
            temp_c = (temp_f - 32) * 5 / 9
        return f"{temp_f:.{precision}f}°F ({temp_c:.{precision}f}°C)"
    return None


def _get_severe_risk_description(risk: int) -> str:
    """Get a description for severe weather risk percentage."""
    if risk >= 80:
        return "Extreme"
    if risk >= 60:
        return "High"
    if risk >= 40:
        return "Moderate"
    if risk >= 20:
        return "Low"
    return "Minimal"


def _categorize_metric(label: str) -> WeatherCategory:
    """Map a metric label to its weather category."""
    label_lower = label.lower()

    # Temperature category
    if any(
        kw in label_lower for kw in ["temperature", "feels", "dewpoint", "heat index", "wind chill"]
    ):
        return WeatherCategory.TEMPERATURE

    # Wind category
    if "wind" in label_lower and "chill" not in label_lower:
        return WeatherCategory.WIND

    # Precipitation category
    if any(kw in label_lower for kw in ["precipitation", "snow", "rain"]):
        return WeatherCategory.PRECIPITATION

    # Humidity/Pressure category
    if any(kw in label_lower for kw in ["humidity", "pressure"]):
        return WeatherCategory.HUMIDITY_PRESSURE

    # Visibility/Clouds category
    if any(kw in label_lower for kw in ["visibility", "cloud"]):
        return WeatherCategory.VISIBILITY_CLOUDS

    # UV Index category
    if "uv" in label_lower:
        return WeatherCategory.UV_INDEX

    # Default to temperature for uncategorized metrics
    return WeatherCategory.TEMPERATURE


def _order_metrics_by_priority(
    metrics: list[Metric],
    ordered_categories: list[WeatherCategory],
) -> list[Metric]:
    """Reorder metrics according to category priority order."""
    # Group metrics by category
    categorized: dict[WeatherCategory, list[Metric]] = {cat: [] for cat in WeatherCategory}

    for metric in metrics:
        category = _categorize_metric(metric.label)
        categorized[category].append(metric)

    # Build ordered list
    ordered: list[Metric] = []
    for category in ordered_categories:
        ordered.extend(categorized[category])

    return ordered


def build_current_conditions(
    current: CurrentConditions,
    location: Location,
    unit_pref: TemperatureUnit,
    *,
    settings: AppSettings | None = None,
    environmental: EnvironmentalConditions | None = None,
    trends: Iterable[TrendInsight] | None = None,
    hourly_forecast: HourlyForecast | None = None,
    air_quality: AirQualityPresentation | None = None,
    alerts: WeatherAlerts | None = None,
) -> CurrentConditionsPresentation:
    """Create a structured presentation for the current weather using helper functions."""
    title = f"Current conditions for {location.name}"
    description = current.condition or "Unknown"
    precision = get_temperature_precision(unit_pref)

    # Extract settings preferences
    show_dewpoint = getattr(settings, "show_dewpoint", True) if settings else True
    show_visibility = getattr(settings, "show_visibility", True) if settings else True
    show_uv_index = getattr(settings, "show_uv_index", True) if settings else True
    show_pressure_trend = getattr(settings, "show_pressure_trend", True) if settings else True
    show_seasonal_data = getattr(settings, "show_seasonal_data", True) if settings else True

    # Time display preferences
    time_display_mode = getattr(settings, "time_display_mode", "local") if settings else "local"
    use_12hour = getattr(settings, "time_format_12hour", True) if settings else True
    show_timezone = getattr(settings, "show_timezone_suffix", False) if settings else False

    # Priority engine setup
    verbosity_level = getattr(settings, "verbosity_level", "standard") if settings else "standard"
    category_order = getattr(settings, "category_order", None) if settings else None
    severe_weather_override = (
        getattr(settings, "severe_weather_override", True) if settings else True
    )

    priority_engine = PriorityEngine(
        verbosity_level=verbosity_level,
        category_order=category_order,
        severe_weather_override=severe_weather_override,
    )
    ordered_categories = priority_engine.get_category_order(alerts=alerts)

    # Build metrics by category
    metrics: list[Metric] = []
    metrics.extend(
        _build_basic_metrics(
            current, unit_pref, precision, show_dewpoint, show_visibility, show_uv_index
        )
    )

    # Add seasonal metrics if enabled
    if show_seasonal_data:
        metrics.extend(_build_seasonal_metrics(current, unit_pref, precision))

    # Reorder metrics by priority before adding non-reorderable metrics
    metrics = _order_metrics_by_priority(metrics, ordered_categories)

    # Add astronomical metrics (these don't need reordering - always at end)
    metrics.extend(
        _build_astronomical_metrics(current, time_display_mode, use_12hour, show_timezone)
    )

    metrics.extend(_build_environmental_metrics(environmental, air_quality))
    metrics.extend(_build_trend_metrics(trends, current, hourly_forecast, show_pressure_trend))

    # Build fallback text
    temperature_value = metrics[0].value if metrics else "N/A"
    fallback_lines = [f"Current Conditions: {description}"]
    fallback_lines.append(f"Temperature: {temperature_value}")
    for metric in metrics[1:]:  # already added temperature
        fallback_lines.append(f"{metric.label}: {metric.value}")
    fallback_text = "\n".join(fallback_lines)

    # Build trend lines
    trend_lines = format_trend_lines(
        trends,
        current=current,
        hourly_forecast=hourly_forecast,
        include_pressure=show_pressure_trend,
    )

    return CurrentConditionsPresentation(
        title=title,
        description=description,
        metrics=metrics,
        fallback_text=fallback_text,
        trends=trend_lines,
    )


def format_trend_lines(
    trends: Iterable[TrendInsight] | None,
    *,
    current: CurrentConditions | None = None,
    hourly_forecast: HourlyForecast | None = None,
    include_pressure: bool = True,
) -> list[str]:
    """Generate human readable summaries for trend insights."""
    lines: list[str] = []
    pressure_present = False

    if trends:
        for trend in trends:
            summary = trend.summary or describe_trend(trend)
            if trend.sparkline:
                summary = f"{summary} {trend.sparkline}".strip()
            metric_name = getattr(trend, "metric", "")
            is_pressure = isinstance(metric_name, str) and metric_name.lower() == "pressure"
            if is_pressure and not include_pressure:
                continue
            if summary:
                lines.append(summary)
            if is_pressure:
                pressure_present = True

    if include_pressure and (not pressure_present) and current and hourly_forecast:
        legacy_pressure = compute_pressure_trend_from_hourly(current, hourly_forecast)
        if legacy_pressure:
            summary = legacy_pressure["summary"]
            if summary and summary not in lines:
                lines.append(summary)

    return lines


def describe_trend(trend: TrendInsight) -> str:
    """Describe a trend insight when it lacks a canned summary."""
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


def compute_pressure_trend_from_hourly(
    current: CurrentConditions,
    hourly_forecast: HourlyForecast | None,
) -> dict[str, str] | None:
    """Approximate a pressure trend using upcoming hourly data."""
    if not hourly_forecast or not hourly_forecast.has_data():
        return None

    next_hours = hourly_forecast.get_next_hours(6)
    if not next_hours:
        return None

    target: HourlyForecastPeriod | None = None
    for period in reversed(next_hours):
        if not period:
            continue
        if period.pressure_in is not None or period.pressure_mb is not None:
            target = period
            break

    if target is None:
        return None

    base_in = current.pressure_in
    base_mb = current.pressure_mb
    future_in = target.pressure_in
    future_mb = target.pressure_mb

    descriptor: str | None = None
    magnitude: str | None = None
    change: float | None = None

    if base_in is not None and future_in is not None:
        change = future_in - base_in
        descriptor = direction_descriptor(change, minor=0.02, strong=0.05)
        magnitude = f"{change:+.2f} inHg"
    elif base_mb is not None and future_mb is not None:
        change = future_mb - base_mb
        descriptor = direction_descriptor(change, minor=0.5, strong=1.5)
        magnitude = f"{change:+.1f} mb"

    if descriptor is None or magnitude is None or change is None:
        return None

    direction_word, arrow = split_direction_descriptor(descriptor)
    window_hours = 6
    arrow_part = f" {arrow}" if arrow else ""
    value = f"{direction_word.title()}{arrow_part} {magnitude} over next {window_hours}h".strip()
    summary = f"Pressure {descriptor} {magnitude} over next {window_hours}h".strip()

    return {"summary": summary, "value": value}


def direction_descriptor(change: float, *, minor: float, strong: float) -> str:
    """Classify change magnitude into rising/falling/steady buckets with arrows."""
    if change >= strong:
        return "rising ⬆⬆"
    if change >= minor:
        return "rising ⬆"
    if change <= -strong:
        return "falling ⬇⬇"
    if change <= -minor:
        return "falling ⬇"
    return "steady →"


def split_direction_descriptor(descriptor: str) -> tuple[str, str]:
    """Return the textual direction and accompanying arrow glyphs."""
    if not descriptor:
        return "steady", ""
    if " " in descriptor:
        direction, arrow = descriptor.split(" ", 1)
        return direction, arrow.strip()
    return descriptor, ""
