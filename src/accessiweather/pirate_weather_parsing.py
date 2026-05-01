"""Parsing helpers for Pirate Weather API payloads."""

from __future__ import annotations

import hashlib
import logging
from datetime import (
    UTC,
    date,
    datetime,
    time as datetime_time,
    timedelta,
    timezone,
)
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import (
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    WeatherAlert,
    WeatherAlerts,
)
from .utils.temperature_utils import TemperatureUnit, calculate_dewpoint
from .weather_client_parsers import convert_f_to_c, degrees_to_cardinal

logger = logging.getLogger(__name__)

_PW_MIN_INCLUDED_SEVERITIES = frozenset({"Severe", "Extreme"})

# Pirate Weather icon -> human-readable condition mapping
_ICON_TO_CONDITION: dict[str, str] = {
    "clear-day": "Clear",
    "clear-night": "Clear",
    "rain": "Rain",
    "snow": "Snow",
    "sleet": "Sleet",
    "wind": "Windy",
    "fog": "Fog",
    "cloudy": "Cloudy",
    "partly-cloudy-day": "Partly Cloudy",
    "partly-cloudy-night": "Partly Cloudy",
    "thunderstorm": "Thunderstorm",
    "hail": "Hail",
    "tornado": "Tornado",
    "ice": "Freezing Rain",
    "mixed": "Wintry Mix",
}

_PRECIP_TYPE_TO_CONDITION: dict[str, str] = {
    "rain": "Rain",
    "snow": "Snow",
    "sleet": "Sleet",
    "hail": "Hail",
    "ice": "Freezing Rain",
    "mixed": "Wintry Mix",
}


def _icon_to_condition(icon: str | None) -> str | None:
    """Map a Pirate Weather icon string to a human-readable condition."""
    if not icon:
        return None
    return _ICON_TO_CONDITION.get(icon, icon.replace("-", " ").title())


def _normalize_precipitation_type(precip_type: object) -> list[str] | None:
    """Normalize Pirate Weather precipType values for model fields."""
    if isinstance(precip_type, str):
        raw_types = [precip_type]
    elif isinstance(precip_type, list | tuple | set):
        raw_types = [str(value) for value in precip_type]
    else:
        return None

    normalized: list[str] = []
    for raw_type in raw_types:
        name = raw_type.strip().lower()
        if not name or name in {"none", "null"} or name in normalized:
            continue
        normalized.append(name)

    return normalized or None


def _precip_type_to_condition(precip_type: object) -> str | None:
    """Return a plain-English condition from Pirate Weather precipType."""
    normalized = _normalize_precipitation_type(precip_type)
    if not normalized:
        return None

    return ", ".join(
        _PRECIP_TYPE_TO_CONDITION.get(name, name.replace("-", " ").title()) for name in normalized
    )


def _data_point_condition(data_point: dict[str, object]) -> str | None:
    """Resolve the best display condition for a Pirate Weather data point."""
    summary = data_point.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary

    icon = data_point.get("icon")
    if isinstance(icon, str):
        return _icon_to_condition(icon)

    return _precip_type_to_condition(data_point.get("precipType"))


def _build_alert_id(alert_data: dict[str, object]) -> str:
    """Build a deterministic lifecycle ID for Pirate Weather / WMO alerts."""
    title = str(alert_data.get("title") or "Weather Alert").strip().lower()
    severity = str(alert_data.get("severity") or "").strip().lower()
    onset = str(alert_data.get("time") or "")
    regions = alert_data.get("regions")
    normalized_regions: list[str] = []
    if isinstance(regions, list):
        normalized_regions = sorted(str(region).strip().lower() for region in regions if region)

    fingerprint = "|".join([title, severity, onset, ",".join(normalized_regions)])
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"pw-wmo-{digest}"


def _normalize_regions(regions: object) -> list[str]:
    """Return a cleaned list of regional area names from the PW payload."""
    if not isinstance(regions, list):
        return []
    normalized: list[str] = []
    for region in regions:
        region_name = str(region).strip()
        if region_name:
            normalized.append(region_name)
    return normalized


def _resolve_response_timezone(data: dict) -> timezone | ZoneInfo:
    """Resolve the response timezone, preferring IANA names over fixed offsets."""
    timezone_name = data.get("timezone")
    if isinstance(timezone_name, str) and timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            logger.warning(
                "Unknown Pirate Weather timezone '%s'; falling back to offset", timezone_name
            )

    tz_offset = data.get("offset", 0)
    return timezone(timedelta(hours=tz_offset))


def _normalize_daily_start_time(
    timestamp: int | float,
    response_tz: timezone | ZoneInfo,
) -> tuple[date, datetime]:
    """Convert a Pirate Weather daily timestamp into the local calendar date at noon."""
    local_dt = datetime.fromtimestamp(timestamp, tz=response_tz)
    local_date = local_dt.date()
    normalized = datetime.combine(local_date, datetime_time(hour=12), tzinfo=response_tz)
    return local_date, normalized


def parse_forecast(client: Any, data: dict, days: int | None = None) -> Forecast | None:
    """
    Parse Pirate Weather ``daily`` block into a Forecast.

    All available daily periods are returned so that the display layer
    (``_select_periods_by_day_window``) can apply the user's configured
    ``forecast_duration_days`` setting without being constrained here.
    The ``days`` parameter is kept for backward compatibility but is no
    longer used to limit the output.
    """
    daily_data = data.get("daily", {}).get("data", [])
    location_tz = _resolve_response_timezone(data)
    using_us = client.units == "us"

    periods: list[ForecastPeriod] = []
    parsed_dates: list[date] = []
    for i, day in enumerate(daily_data):
        time_val = day.get("time")
        if time_val:
            local_date, start_time = _normalize_daily_start_time(time_val, location_tz)
            parsed_dates.append(local_date)
            if i == 0:
                name = "Today"
            elif i == 1:
                name = "Tomorrow"
            else:
                name = start_time.strftime("%A")
        else:
            name = f"Day {i + 1}"
            start_time = None

        temp_high = day.get("temperatureHigh") if using_us else day.get("temperatureMax")
        temp_low = day.get("temperatureLow") if using_us else day.get("temperatureMin")

        # Wind speed formatting
        wind_raw = day.get("windSpeed")
        if wind_raw is not None:
            if using_us or client.units == "uk2":
                wind_str = f"{round(wind_raw)} mph"
            elif client.units == "ca":
                wind_str = f"{round(wind_raw)} km/h"
            else:
                wind_str = f"{round(wind_raw)} m/s"
        else:
            wind_str = None

        wind_gust_raw = day.get("windGust")
        if wind_gust_raw is not None:
            if using_us or client.units == "uk2":
                wind_gust_str = f"{round(wind_gust_raw)} mph"
            elif client.units == "ca":
                wind_gust_str = f"{round(wind_gust_raw)} km/h"
            else:
                wind_gust_str = f"{round(wind_gust_raw)} m/s"
        else:
            wind_gust_str = None

        precip_prob_raw = day.get("precipProbability")
        precip_prob = round(precip_prob_raw * 100) if precip_prob_raw is not None else None

        precip_intensity = day.get("precipIntensity")
        if precip_intensity is not None:
            precip_amount = precip_intensity if using_us else precip_intensity / 25.4
        else:
            precip_amount = None

        cloud_cover_raw = day.get("cloudCover")
        cloud_cover = round(cloud_cover_raw * 100) if cloud_cover_raw is not None else None

        uv_index = day.get("uvIndex")

        condition = _data_point_condition(day)
        precipitation_type = _normalize_precipitation_type(day.get("precipType"))

        period = ForecastPeriod(
            name=name,
            temperature=temp_high,
            temperature_low=temp_low,
            temperature_unit="F" if using_us else "C",
            short_forecast=condition,
            detailed_forecast=condition,
            wind_speed=wind_str,
            wind_direction=degrees_to_cardinal(day.get("windBearing")),
            precipitation_probability=precip_prob,
            uv_index=uv_index,
            cloud_cover=cloud_cover,
            wind_gust=wind_gust_str,
            precipitation_amount=precip_amount,
            precipitation_type=precipitation_type,
            start_time=start_time,
        )
        periods.append(period)

    if parsed_dates:
        expected_dates = [parsed_dates[0] + timedelta(days=i) for i in range(len(parsed_dates))]
        if parsed_dates != expected_dates or len(parsed_dates) != len(set(parsed_dates)):
            logger.warning(
                "Rejecting Pirate Weather daily forecast with non-consecutive local dates: %s",
                [day.isoformat() for day in parsed_dates],
            )
            return None

    daily_summary = data.get("daily", {}).get("summary")
    return Forecast(periods=periods, generated_at=datetime.now(UTC), summary=daily_summary)


def parse_hourly_forecast(client: Any, data: dict) -> HourlyForecast:
    """Parse Pirate Weather ``hourly`` block into an HourlyForecast."""
    hourly_items = data.get("hourly", {}).get("data", [])
    location_tz = _resolve_response_timezone(data)
    using_us = client.units == "us"

    periods: list[HourlyForecastPeriod] = []
    for hour in hourly_items:
        time_val = hour.get("time")
        if time_val:
            start_time = datetime.fromtimestamp(time_val, tz=location_tz)
        else:
            start_time = datetime.now(UTC)

        temp = hour.get("temperature")
        if using_us:
            temp_f = float(temp) if temp is not None else None
        else:
            temp_c = float(temp) if temp is not None else None
            temp_f = (temp_c * 9 / 5 + 32) if temp_c is not None else temp_c

        humidity_raw = hour.get("humidity")
        humidity = round(humidity_raw * 100) if humidity_raw is not None else None

        dewpoint = hour.get("dewPoint")
        if using_us:
            dewpoint_f = float(dewpoint) if dewpoint is not None else None
            dewpoint_c = convert_f_to_c(dewpoint_f)
            if dewpoint_f is None and temp_f is not None and humidity is not None:
                dewpoint_f = calculate_dewpoint(
                    temp_f,
                    humidity,
                    unit=TemperatureUnit.FAHRENHEIT,
                )
                dewpoint_c = convert_f_to_c(dewpoint_f)
        else:
            dewpoint_c = float(dewpoint) if dewpoint is not None else None
            dewpoint_f = (dewpoint_c * 9 / 5 + 32) if dewpoint_c is not None else None

        # Pressure in mb (all unit groups)
        pressure_mb = hour.get("pressure")
        pressure_in = pressure_mb / 33.8639 if pressure_mb is not None else None

        wind_raw = hour.get("windSpeed")
        wind_speed_mph: float | None = None
        if wind_raw is not None:
            if using_us or client.units == "uk2":
                wind_str = f"{round(wind_raw)} mph"
                wind_speed_mph = float(wind_raw)
            elif client.units == "ca":
                wind_str = f"{round(wind_raw)} km/h"
                wind_speed_mph = float(wind_raw) / 1.60934
            else:
                wind_str = f"{round(wind_raw)} m/s"
                wind_speed_mph = float(wind_raw) * 2.23694
        else:
            wind_str = None

        wind_gust_raw = hour.get("windGust")
        wind_gust_mph: float | None = None
        if wind_gust_raw is not None:
            if using_us or client.units == "uk2":
                wind_gust_mph = float(wind_gust_raw)
            elif client.units == "ca":
                wind_gust_mph = float(wind_gust_raw) / 1.60934
            else:
                wind_gust_mph = float(wind_gust_raw) * 2.23694

        precip_prob_raw = hour.get("precipProbability")
        precip_prob = round(precip_prob_raw * 100) if precip_prob_raw is not None else None

        precip_intensity = hour.get("precipIntensity")
        if precip_intensity is not None:
            precip_amount = precip_intensity if using_us else precip_intensity / 25.4
        else:
            precip_amount = None

        cloud_cover_raw = hour.get("cloudCover")
        cloud_cover = round(cloud_cover_raw * 100) if cloud_cover_raw is not None else None

        uv_index = hour.get("uvIndex")

        visibility_raw = hour.get("visibility")
        if visibility_raw is not None:
            if using_us or client.units == "uk2":
                visibility_miles = float(visibility_raw)
                visibility_km = visibility_miles * 1.60934
            else:
                visibility_km = float(visibility_raw)
                visibility_miles = visibility_km / 1.60934
        else:
            visibility_miles = None
            visibility_km = None

        apparent = hour.get("apparentTemperature")
        if using_us:
            feels_like_f = float(apparent) if apparent is not None else None
        else:
            feels_like_c = float(apparent) if apparent is not None else None
            feels_like_f = (feels_like_c * 9 / 5 + 32) if feels_like_c is not None else None

        condition = _data_point_condition(hour)
        precipitation_type = _normalize_precipitation_type(hour.get("precipType"))

        period = HourlyForecastPeriod(
            start_time=start_time,
            temperature=temp_f,
            temperature_unit="F",
            short_forecast=condition,
            wind_speed=wind_str,
            wind_speed_mph=wind_speed_mph,
            wind_direction=degrees_to_cardinal(hour.get("windBearing")),
            humidity=humidity,
            dewpoint_f=dewpoint_f,
            dewpoint_c=dewpoint_c,
            pressure_mb=pressure_mb,
            pressure_in=pressure_in,
            precipitation_probability=precip_prob,
            uv_index=uv_index,
            cloud_cover=cloud_cover,
            wind_gust_mph=wind_gust_mph,
            precipitation_amount=precip_amount,
            precipitation_type=precipitation_type,
            feels_like=feels_like_f,
            visibility_miles=visibility_miles,
            visibility_km=visibility_km,
        )
        periods.append(period)

    hourly_summary = data.get("hourly", {}).get("summary")
    return HourlyForecast(
        periods=periods,
        generated_at=datetime.now(UTC),
        summary=hourly_summary if isinstance(hourly_summary, str) else None,
    )


def parse_alerts(client: Any, data: dict) -> WeatherAlerts:
    """Parse Pirate Weather ``alerts`` list into WeatherAlerts."""
    raw_alerts = data.get("alerts", [])
    alerts: list[WeatherAlert] = []

    location_tz = _resolve_response_timezone(data)

    for _i, alert_data in enumerate(raw_alerts):
        title = alert_data.get("title") or "Weather Alert"
        description = alert_data.get("description") or title
        severity = client._map_severity(alert_data.get("severity"))
        if severity not in _PW_MIN_INCLUDED_SEVERITIES:
            logger.info(
                "Skipping lower-severity Pirate Weather regional alert '%s' (severity=%s)",
                title,
                severity,
            )
            continue
        alert_id = _build_alert_id(alert_data)

        onset_raw = alert_data.get("time")
        expires_raw_val = alert_data.get("expires")

        onset = datetime.fromtimestamp(onset_raw, tz=location_tz) if onset_raw else None
        expires = (
            datetime.fromtimestamp(expires_raw_val, tz=location_tz) if expires_raw_val else None
        )

        areas = _normalize_regions(alert_data.get("regions"))

        alert = WeatherAlert(
            id=alert_id,
            title=title,
            description=description,
            severity=severity,
            urgency="Unknown",
            certainty="Possible",
            event=title,
            headline=title,
            instruction=None,
            areas=areas,
            onset=onset,
            expires=expires,
            sent=onset,
            effective=onset,
            source="PirateWeather",
        )
        alerts.append(alert)

    logger.info(f"Parsed {len(alerts)} Pirate Weather alerts")
    return WeatherAlerts(alerts=alerts)
