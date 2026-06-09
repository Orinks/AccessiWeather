"""Current-condition parsing for Pirate Weather payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import CurrentConditions
from .pirate_weather_parsing import (
    _data_point_condition,
    _normalize_precipitation_type,
    _resolve_response_timezone,
)
from .provider_normalization import (
    normalize_dewpoint_pair,
    normalize_humidity_percent,
    normalize_millibars,
    normalize_speed_pair,
    normalize_temperature_pair,
    normalize_visibility_pair,
    pirate_temperature_unit,
    pirate_visibility_unit,
    pirate_wind_unit,
)
from .thermal_comfort import sanitize_thermal_comfort_readings
from .weather_client_parsers import degrees_to_cardinal, describe_moon_phase


def parse_current_conditions(client: Any, data: dict) -> CurrentConditions:
    """Parse Pirate Weather ``currently`` block into CurrentConditions."""
    current = data.get("currently", {})

    temperature_unit = pirate_temperature_unit(client.units)
    wind_unit = pirate_wind_unit(client.units)
    visibility_unit = pirate_visibility_unit(client.units)
    temperature = normalize_temperature_pair(current.get("temperature"), temperature_unit)

    humidity = normalize_humidity_percent(current.get("humidity"), fraction=True)

    dewpoint = normalize_dewpoint_pair(
        current.get("dewPoint"),
        temperature_unit,
        fallback_temperature_f=temperature.fahrenheit,
        humidity_percent=humidity,
    )

    wind_speed = normalize_speed_pair(current.get("windSpeed"), wind_unit)

    wind_direction = current.get("windBearing")  # degrees

    pressure = normalize_millibars(current.get("pressure"))

    visibility = normalize_visibility_pair(current.get("visibility"), visibility_unit)

    feels_like = normalize_temperature_pair(current.get("apparentTemperature"), temperature_unit)

    comfort = sanitize_thermal_comfort_readings(
        temperature_f=temperature.fahrenheit,
        temperature_c=temperature.celsius,
        humidity=humidity,
        feels_like_f=feels_like.fahrenheit,
        feels_like_c=feels_like.celsius,
    )

    wind_gust = normalize_speed_pair(current.get("windGust"), wind_unit)

    # Current-condition model fields represent accumulated amount. Pirate Weather's
    # current precipIntensity is a rate, so leave amount fields blank.
    precip_in = None
    precip_mm = None

    cloud_cover_raw = current.get("cloudCover")
    cloud_cover = round(cloud_cover_raw * 100) if cloud_cover_raw is not None else None

    uv_index = current.get("uvIndex")

    # Sunrise/sunset come from the first daily entry
    sunrise_time = None
    sunset_time = None
    moon_phase = None
    daily_data = data.get("daily", {}).get("data", [])
    if daily_data:
        today = daily_data[0]
        location_tz = _resolve_response_timezone(data)
        sr = today.get("sunriseTime")
        ss = today.get("sunsetTime")
        if sr:
            sunrise_time = datetime.fromtimestamp(sr, tz=location_tz)
        if ss:
            sunset_time = datetime.fromtimestamp(ss, tz=location_tz)
        moon_phase = describe_moon_phase(today.get("moonPhase"))

    condition_str = _data_point_condition(current)
    precipitation_type = _normalize_precipitation_type(current.get("precipType"))

    return CurrentConditions(
        temperature_f=temperature.fahrenheit,
        temperature_c=temperature.celsius,
        condition=condition_str,
        humidity=humidity,
        dewpoint_f=dewpoint.fahrenheit,
        dewpoint_c=dewpoint.celsius,
        wind_speed_mph=wind_speed.mph,
        wind_speed_kph=wind_speed.kph,
        wind_direction=degrees_to_cardinal(wind_direction),
        pressure_in=pressure.inches,
        pressure_mb=pressure.millibars,
        feels_like_f=comfort.feels_like_f,
        feels_like_c=comfort.feels_like_c,
        visibility_miles=visibility.miles,
        visibility_km=visibility.kilometers,
        uv_index=uv_index,
        cloud_cover=cloud_cover,
        wind_gust_mph=wind_gust.mph,
        wind_gust_kph=wind_gust.kph,
        precipitation_in=precip_in,
        precipitation_mm=precip_mm,
        precipitation_type=precipitation_type,
        sunrise_time=sunrise_time,
        sunset_time=sunset_time,
        moon_phase=moon_phase,
        wind_chill_f=comfort.wind_chill_f,
        wind_chill_c=comfort.wind_chill_c,
        heat_index_f=comfort.heat_index_f,
        heat_index_c=comfort.heat_index_c,
    )
