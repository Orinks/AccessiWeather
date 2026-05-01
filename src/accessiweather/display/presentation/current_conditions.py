"""Builders for current conditions presentation objects."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from ...impact_summary import ImpactSummary, build_impact_summary
from ...models import (
    AppSettings,
    CurrentConditions,
    EnvironmentalConditions,
    HourlyForecast,
    Location,
    MinutelyPrecipitationForecast,
    TrendInsight,
    WeatherAlerts,
)
from ...units import DisplayUnitSystem
from ...utils import TemperatureUnit
from ...utils.unit_utils import format_precipitation, format_wind_speed
from ...weather_anomaly import AnomalyCallout
from ..priority_engine import PriorityEngine, WeatherCategory
from .current_condition_seasonal import (
    _build_seasonal_metrics,
    _get_severe_risk_description,
    format_temperature_value,
)
from .current_condition_trends import (
    _adapt_temperature_trend_summary,
    compute_pressure_trend_from_hourly,
    describe_trend,
    direction_descriptor,
    format_trend_lines,
    split_direction_descriptor,
)
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
from .models import CurrentConditionsPresentation, Metric

logger = logging.getLogger(__name__)

__all__ = [
    "_build_seasonal_metrics",
    "_get_severe_risk_description",
    "build_current_conditions",
    "compute_pressure_trend_from_hourly",
    "describe_trend",
    "direction_descriptor",
    "format_temperature_value",
    "format_trend_lines",
    "split_direction_descriptor",
]


def _normalize_metric_wind_units(value: str, *, unit_system: DisplayUnitSystem | str | None) -> str:
    """Keep current-conditions metric wording aligned with the screen's spoken style."""
    if unit_system is None:
        return value.replace("km/h", "kph")
    return value


def _build_basic_metrics(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: int,
    show_dewpoint: bool,
    show_visibility: bool,
    show_uv_index: bool,
    *,
    unit_system: DisplayUnitSystem | str | None = None,
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

    wind_value = format_wind(current, unit_pref, precision=precision, unit_system=unit_system)
    if wind_value:
        wind_value = _normalize_metric_wind_units(wind_value, unit_system=unit_system)

    gust_value: str | None = None
    if current.wind_gust_mph is not None:
        gust_value = format_wind_speed(
            current.wind_gust_mph,
            unit=unit_pref,
            wind_speed_kph=current.wind_gust_kph,
            precision=0,
            unit_system=unit_system,
        )
        gust_value = _normalize_metric_wind_units(gust_value, unit_system=unit_system)

    if wind_value and gust_value:
        metrics.append(Metric("Wind", f"{wind_value}, gusting to {gust_value}"))
    elif wind_value:
        metrics.append(Metric("Wind", wind_value))
    elif gust_value:
        metrics.append(Metric("Wind gusts", gust_value))

    dewpoint_value = format_dewpoint(current, unit_pref, precision)
    if show_dewpoint and dewpoint_value:
        metrics.append(Metric("Dewpoint", dewpoint_value))

    pressure_value = format_pressure_value(
        current,
        unit_pref,
        precision=precision,
        unit_system=unit_system,
    )
    if pressure_value:
        metrics.append(Metric("Pressure", pressure_value))

    visibility_value = format_visibility_value(
        current,
        unit_pref,
        precision=precision,
        unit_system=unit_system,
    )
    if show_visibility and visibility_value:
        metrics.append(Metric("Visibility", visibility_value))

    if show_uv_index and current.uv_index is not None:
        uv_desc = get_uv_description(current.uv_index)
        metrics.append(Metric("UV Index", f"{current.uv_index} ({uv_desc})"))

    if current.cloud_cover is not None:
        metrics.append(Metric("Cloud cover", f"{current.cloud_cover:.0f}%"))

    if current.precipitation_in is not None and current.precipitation_in > 0:
        precip_value = format_precipitation(
            current.precipitation_in,
            unit=unit_pref,
            precipitation_mm=current.precipitation_mm,
            precision=precision,
            unit_system=unit_system,
        )
        metrics.append(Metric("Precipitation", precip_value))

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
        if pollen_value:
            metrics.append(Metric("Pollen", pollen_value))

    return metrics


def _build_trend_metrics(
    trends: Iterable[TrendInsight] | None,
    current: CurrentConditions,
    hourly_forecast: HourlyForecast | None,
    show_pressure_trend: bool,
    unit_pref: TemperatureUnit = TemperatureUnit.FAHRENHEIT,
) -> list[Metric]:
    """Build trend metrics (temperature, pressure, etc. trends)."""
    metrics: list[Metric] = []
    pressure_trend_present = False

    if trends:
        for trend in trends:
            metric_name = getattr(trend, "metric", "")
            if isinstance(metric_name, str) and metric_name.lower() == "daily_trend":
                continue
            is_pressure = isinstance(metric_name, str) and metric_name.lower() == "pressure"
            if is_pressure and not show_pressure_trend:
                continue

            is_temperature = isinstance(metric_name, str) and metric_name.lower() == "temperature"
            if is_temperature:
                summary = _adapt_temperature_trend_summary(trend, unit_pref)
            else:
                summary = trend.summary or describe_trend(trend)

            if trend.sparkline:
                summary = f"{summary} {trend.sparkline}".strip()
            label = (
                "Pressure outlook"
                if is_pressure
                else f"{trend.metric.replace('_', ' ').title()} trend"
            )
            metrics.append(Metric(label, summary))
            if is_pressure:
                pressure_trend_present = True

    if show_pressure_trend and not pressure_trend_present:
        legacy_pressure_trend = compute_pressure_trend_from_hourly(current, hourly_forecast)
        if legacy_pressure_trend:
            metrics.append(Metric("Pressure trend", legacy_pressure_trend["value"]))

    return metrics


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
    minutely_precipitation: MinutelyPrecipitationForecast | None = None,
    air_quality: AirQualityPresentation | None = None,
    alerts: WeatherAlerts | None = None,
    unit_system: DisplayUnitSystem | str | None = None,
    anomaly_callout: AnomalyCallout | None = None,
) -> CurrentConditionsPresentation:
    """Create a structured presentation for the current weather using helper functions."""
    title = f"Current conditions for {location.name}"
    description = current.condition or "Unknown"
    round_values = getattr(settings, "round_values", False) if settings else False
    precision = 0 if round_values else get_temperature_precision(unit_pref)

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
            current,
            unit_pref,
            precision,
            show_dewpoint,
            show_visibility,
            show_uv_index,
            unit_system=unit_system,
        )
    )

    # Add seasonal metrics if enabled
    if show_seasonal_data:
        metrics.extend(_build_seasonal_metrics(current, unit_pref, precision))

    # Reorder metrics by priority before adding non-reorderable metrics
    metrics = _order_metrics_by_priority(metrics, ordered_categories)

    if minutely_precipitation and minutely_precipitation.summary:
        metrics.insert(0, Metric("Precipitation outlook", minutely_precipitation.summary))

    # Add astronomical metrics (these don't need reordering - always at end)
    metrics.extend(
        _build_astronomical_metrics(current, time_display_mode, use_12hour, show_timezone)
    )

    metrics.extend(_build_environmental_metrics(environmental, air_quality))
    metrics.extend(
        _build_trend_metrics(trends, current, hourly_forecast, show_pressure_trend, unit_pref)
    )

    if anomaly_callout is not None:
        metrics.append(Metric("Historical context", anomaly_callout.temp_anomaly_description))

    # Build impact summary and append as metrics (only when opt-in setting is enabled)
    show_impact_summaries = getattr(settings, "show_impact_summaries", False) if settings else False
    impact = (
        build_impact_summary(current, environmental) if show_impact_summaries else ImpactSummary()
    )
    if show_impact_summaries:
        if impact.outdoor is not None:
            metrics.append(Metric("Impact: Outdoor", impact.outdoor))
        if impact.driving is not None:
            metrics.append(Metric("Impact: Driving", impact.driving))
        if impact.allergy is not None:
            metrics.append(Metric("Impact: Allergy", impact.allergy))

    # Build fallback text
    # Use metric.label for all metrics — after priority reordering, metrics[0]
    # may no longer be the Temperature metric (e.g. Visibility moves first during fog alerts)
    fallback_lines = [f"Current conditions for {location.name}: {description}"]
    for metric in metrics:
        fallback_lines.append(f"{metric.label}: {metric.value}")
    fallback_text = "\n".join(fallback_lines)

    # Build trend lines
    trend_lines = format_trend_lines(
        trends,
        current=current,
        hourly_forecast=hourly_forecast,
        include_pressure=show_pressure_trend,
        unit_pref=unit_pref,
    )

    return CurrentConditionsPresentation(
        title=title,
        description=description,
        metrics=metrics,
        fallback_text=fallback_text,
        trends=trend_lines,
        impact_summary=impact,
    )
