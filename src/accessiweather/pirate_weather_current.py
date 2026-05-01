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
from .utils.temperature_utils import TemperatureUnit, calculate_dewpoint
from .weather_client_parsers import convert_f_to_c, degrees_to_cardinal, describe_moon_phase


def parse_current_conditions(client: Any, data: dict) -> CurrentConditions:
    """Parse Pirate Weather ``currently`` block into CurrentConditions."""
    current = data.get("currently", {})

    # Temperature (PW returns °F in "us" units, °C otherwise)
    temp = current.get("temperature")
    using_us = client.units == "us"

    if using_us:
        temp_f = float(temp) if temp is not None else None
        temp_c = convert_f_to_c(temp_f)
    else:
        temp_c = float(temp) if temp is not None else None
        temp_f = (temp_c * 9 / 5 + 32) if temp_c is not None else None

    # Humidity (0-1 in PW → 0-100)
    humidity_raw = current.get("humidity")
    humidity = round(humidity_raw * 100) if humidity_raw is not None else None

    # Dew point
    dewpoint = current.get("dewPoint")
    if using_us:
        dewpoint_f = float(dewpoint) if dewpoint is not None else None
        dewpoint_c = convert_f_to_c(dewpoint_f)
        if dewpoint_f is None and temp_f is not None and humidity is not None:
            dewpoint_f = calculate_dewpoint(temp_f, humidity, unit=TemperatureUnit.FAHRENHEIT)
            dewpoint_c = convert_f_to_c(dewpoint_f)
    else:
        dewpoint_c = float(dewpoint) if dewpoint is not None else None
        dewpoint_f = (dewpoint_c * 9 / 5 + 32) if dewpoint_c is not None else None

    # Wind – PW "us" = mph, "si" = m/s, "ca" = km/h, "uk2" = mph
    wind_speed_raw = current.get("windSpeed")
    if using_us or client.units == "uk2":
        wind_speed_mph = float(wind_speed_raw) if wind_speed_raw is not None else None
        wind_speed_kph = wind_speed_mph * 1.60934 if wind_speed_mph is not None else None
    elif client.units == "ca":
        wind_speed_kph = float(wind_speed_raw) if wind_speed_raw is not None else None
        wind_speed_mph = wind_speed_kph / 1.60934 if wind_speed_kph is not None else None
    else:  # si: m/s
        wind_mps = float(wind_speed_raw) if wind_speed_raw is not None else None
        wind_speed_mph = wind_mps * 2.23694 if wind_mps is not None else None
        wind_speed_kph = wind_mps * 3.6 if wind_mps is not None else None

    wind_direction = current.get("windBearing")  # degrees

    # Pressure – PW returns mb in all unit groups
    pressure_mb = current.get("pressure")
    pressure_in = pressure_mb / 33.8639 if pressure_mb is not None else None

    # Visibility – PW "us" = miles, others = km
    visibility_raw = current.get("visibility")
    if using_us or client.units == "uk2":
        visibility_miles = float(visibility_raw) if visibility_raw is not None else None
        visibility_km = visibility_miles * 1.60934 if visibility_miles is not None else None
    else:
        visibility_km = float(visibility_raw) if visibility_raw is not None else None
        visibility_miles = visibility_km / 1.60934 if visibility_km is not None else None

    # Feels like (apparent temperature)
    apparent = current.get("apparentTemperature")
    if using_us:
        feels_like_f = float(apparent) if apparent is not None else None
        feels_like_c = convert_f_to_c(feels_like_f)
    else:
        feels_like_c = float(apparent) if apparent is not None else None
        feels_like_f = (feels_like_c * 9 / 5 + 32) if feels_like_c is not None else None

    # Wind gust
    wind_gust_raw = current.get("windGust")
    if using_us or client.units == "uk2":
        wind_gust_mph = float(wind_gust_raw) if wind_gust_raw is not None else None
        wind_gust_kph = wind_gust_mph * 1.60934 if wind_gust_mph is not None else None
    elif client.units == "ca":
        wind_gust_kph = float(wind_gust_raw) if wind_gust_raw is not None else None
        wind_gust_mph = wind_gust_kph / 1.60934 if wind_gust_kph is not None else None
    else:
        wind_gust_mps = float(wind_gust_raw) if wind_gust_raw is not None else None
        wind_gust_mph = wind_gust_mps * 2.23694 if wind_gust_mps is not None else None
        wind_gust_kph = wind_gust_mps * 3.6 if wind_gust_mps is not None else None

    # Precipitation intensity – PW "us" = in/hr, others = mm/hr
    precip_intensity = current.get("precipIntensity")
    if using_us:
        precip_in = float(precip_intensity) if precip_intensity is not None else None
        precip_mm = precip_in * 25.4 if precip_in is not None else None
    else:
        precip_mm = float(precip_intensity) if precip_intensity is not None else None
        precip_in = precip_mm / 25.4 if precip_mm is not None else None

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
        temperature_f=temp_f,
        temperature_c=temp_c,
        condition=condition_str,
        humidity=humidity,
        dewpoint_f=dewpoint_f,
        dewpoint_c=dewpoint_c,
        wind_speed_mph=wind_speed_mph,
        wind_speed_kph=wind_speed_kph,
        wind_direction=degrees_to_cardinal(wind_direction),
        pressure_in=pressure_in,
        pressure_mb=pressure_mb,
        feels_like_f=feels_like_f,
        feels_like_c=feels_like_c,
        visibility_miles=visibility_miles,
        visibility_km=visibility_km,
        uv_index=uv_index,
        cloud_cover=cloud_cover,
        wind_gust_mph=wind_gust_mph,
        wind_gust_kph=wind_gust_kph,
        precipitation_in=precip_in,
        precipitation_mm=precip_mm,
        precipitation_type=precipitation_type,
        sunrise_time=sunrise_time,
        sunset_time=sunset_time,
        moon_phase=moon_phase,
    )
