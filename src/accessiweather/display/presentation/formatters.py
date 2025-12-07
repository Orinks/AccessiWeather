"""Reusable formatting helpers for weather presentation output."""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime

from ...models import CurrentConditions, ForecastPeriod, HourlyForecastPeriod
from ...utils import (
    TemperatureUnit,
    calculate_dewpoint,
    convert_wind_direction_to_cardinal,
    format_pressure,
    format_temperature,
    format_visibility,
    format_wind_speed,
)


def format_temperature_pair(
    temp_f: float | None,
    temp_c: float | None,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Return a temperature string honoring the configured unit preference."""
    if temp_f is None and temp_c is None:
        return None
    return format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=precision)


def format_wind(current: CurrentConditions, unit_pref: TemperatureUnit) -> str | None:
    """Describe wind direction and speed or return calm when wind is negligible."""
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


def format_dewpoint(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Calculate or reuse dewpoint and format it using the active preference."""
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


def format_pressure_value(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
) -> str | None:
    """Format station pressure in the preferred unit, if available."""
    if current.pressure_in is None and current.pressure_mb is None:
        return None
    pressure_in = current.pressure_in
    pressure_mb = current.pressure_mb
    if pressure_in is None and pressure_mb is not None:
        pressure_in = pressure_mb / 33.8639
    return format_pressure(pressure_in, unit_pref, pressure_mb=pressure_mb, precision=0)


def format_visibility_value(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
) -> str | None:
    """Format horizontal visibility taking unit preference into account."""
    if current.visibility_miles is None and current.visibility_km is None:
        return None
    return format_visibility(
        current.visibility_miles,
        unit_pref,
        visibility_km=current.visibility_km,
        precision=1,
    )


def format_snow_depth(
    snow_depth_in: float | None,
    snow_depth_cm: float | None,
    unit_pref: TemperatureUnit,
) -> str | None:
    """
    Format snow depth for display.

    Args:
        snow_depth_in: Snow depth in inches
        snow_depth_cm: Snow depth in centimeters
        unit_pref: Unit preference (imperial/metric/both)

    Returns:
        Formatted string like "6 in" or "15 cm" or None if no data

    """
    if snow_depth_in is None and snow_depth_cm is None:
        return None

    # Convert if needed
    if snow_depth_in is None and snow_depth_cm is not None:
        snow_depth_in = snow_depth_cm / 2.54
    if snow_depth_cm is None and snow_depth_in is not None:
        snow_depth_cm = snow_depth_in * 2.54

    if unit_pref == TemperatureUnit.CELSIUS:
        return f"{snow_depth_cm:.1f} cm"
    if unit_pref == TemperatureUnit.BOTH:
        return f"{snow_depth_in:.1f} in ({snow_depth_cm:.1f} cm)"
    # Default: imperial
    return f"{snow_depth_in:.1f} in"


def format_frost_risk(frost_risk: str | None) -> str | None:
    """
    Format frost risk level for display.

    Args:
        frost_risk: Risk level ("None", "Low", "Moderate", "High")

    Returns:
        Formatted string or None if no data

    """
    if frost_risk is None or frost_risk.lower() == "none":
        return None
    return frost_risk


def select_feels_like_temperature(
    current: CurrentConditions,
) -> tuple[float | None, float | None, str | None]:
    """
    Select the appropriate feels-like temperature based on conditions.

    Logic:
    - If temp < 50°F and wind > 3 mph: use wind_chill
    - If temp > 80°F and humidity > 40%: use heat_index
    - Otherwise: use existing feels_like or actual temp

    Args:
        current: Current weather conditions

    Returns:
        Tuple of (feels_like_f, feels_like_c, reason)
        reason is "wind chill", "heat index", or None

    """
    temp_f = current.temperature_f
    if temp_f is None and current.temperature_c is not None:
        temp_f = (current.temperature_c * 9 / 5) + 32

    wind_mph = current.wind_speed_mph
    if wind_mph is None and current.wind_speed_kph is not None:
        wind_mph = current.wind_speed_kph * 0.621371

    humidity = current.humidity

    # Check for wind chill conditions: cold and windy
    if (
        temp_f is not None
        and temp_f < 50
        and wind_mph is not None
        and wind_mph > 3
        and current.wind_chill_f is not None
    ):
        wind_chill_c = current.wind_chill_c
        if wind_chill_c is None and current.wind_chill_f is not None:
            wind_chill_c = (current.wind_chill_f - 32) * 5 / 9
        return current.wind_chill_f, wind_chill_c, "wind chill"

    # Check for heat index conditions: hot and humid
    if (
        temp_f is not None
        and temp_f > 80
        and humidity is not None
        and humidity > 40
        and current.heat_index_f is not None
    ):
        heat_index_c = current.heat_index_c
        if heat_index_c is None and current.heat_index_f is not None:
            heat_index_c = (current.heat_index_f - 32) * 5 / 9
        return current.heat_index_f, heat_index_c, "heat index"

    # Fall back to existing feels_like or actual temperature
    if current.feels_like_f is not None or current.feels_like_c is not None:
        return current.feels_like_f, current.feels_like_c, None

    return current.temperature_f, current.temperature_c, None


def format_forecast_temperature(
    period: ForecastPeriod,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Format a forecast period temperature without mutating the period."""
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


def format_period_wind(period: ForecastPeriod) -> str | None:
    """Return a combined wind string for a forecast period, if available."""
    if not period.wind_speed and not period.wind_direction:
        return None
    parts: list[str] = []
    if period.wind_direction:
        parts.append(period.wind_direction)
    if period.wind_speed:
        parts.append(period.wind_speed)
    return " ".join(parts) if parts else None


def format_period_temperature(
    period: HourlyForecastPeriod,
    unit_pref: TemperatureUnit,
    precision: int,
) -> str | None:
    """Format an hourly forecast temperature with unit conversion."""
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


def format_display_time(
    start_time: datetime | None,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str:
    """
    Format time with user preferences for display mode, format, and timezone labels.

    Note: "local" mode shows the LOCATION'S local time (e.g., PST for LA weather),
    not the user's system timezone.

    Args:
    ----
        start_time: Datetime to format (should be in location's timezone)
        time_display_mode: One of "local", "utc", or "both"
        use_12hour: If True, use 12-hour format; if False, use 24-hour format
        show_timezone: If True, append timezone abbreviation

    Returns:
    -------
        Formatted time string according to preferences

    """
    if not start_time:
        return "Unknown"

    # Prepare time format
    # For 12-hour, we typically want to remove leading zero for hours (e.g., "6:00 PM" not "06:00 PM")
    # But strftime %I produces zero-padded. We'll handle stripping later if needed.
    time_format = "%I:%M %p" if use_12hour else "%H:%M"

    def _fmt(dt: datetime) -> str:
        s = dt.strftime(time_format)
        if use_12hour and s.startswith("0"):
            s = s[1:]
        return s

    if time_display_mode == "utc":
        # Show UTC time
        utc_time = start_time
        if start_time.tzinfo is not None:
            utc_time = start_time.astimezone(UTC)
        time_str = _fmt(utc_time)
        if show_timezone:
            time_str += " UTC"
        return time_str

    if time_display_mode == "both":
        # Show both location's local time and UTC: "3:00 PM PST (23:00 UTC)"
        # Keep time in location's timezone - don't convert to system timezone
        local_str = _fmt(start_time)

        # Get timezone abbreviation for location's time
        if show_timezone:
            tz_abbr = _get_timezone_abbreviation(start_time)
            if tz_abbr:
                local_str += f" {tz_abbr}"

        # Add UTC time in parentheses
        utc_time = start_time.astimezone(UTC) if start_time.tzinfo else start_time
        utc_str = _fmt(utc_time)
        return f"{local_str} ({utc_str} UTC)"

    # Default: location's local time only
    time_str = _fmt(start_time)
    if show_timezone:
        tz_abbr = _get_timezone_abbreviation(start_time)
        if tz_abbr:
            time_str += f" {tz_abbr}"
    return time_str


def format_hour_time(
    start_time: datetime | None,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str:
    """Render an hour label for hourly forecast output."""
    return format_display_time(
        start_time,
        time_display_mode=time_display_mode,
        use_12hour=use_12hour,
        show_timezone=show_timezone,
    )


def format_display_datetime(
    value: datetime,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
    date_format: str = "%b %d",
) -> str:
    """
    Format date and time with user preferences.

    Args:
    ----
        value: Datetime to format
        time_display_mode: Display mode preference
        use_12hour: 12/24 hour format preference
        show_timezone: Whether to show timezone suffix
        date_format: Strftime format for the date part

    """
    time_format = "%I:%M %p" if use_12hour else "%H:%M"

    def _fmt(dt: datetime) -> str:
        d_str = dt.strftime(date_format)
        t_str = dt.strftime(time_format)
        if use_12hour and t_str.startswith("0"):
            t_str = t_str[1:]
        return f"{d_str} {t_str}"

    if time_display_mode == "utc":
        utc_time = value
        if value.tzinfo is not None:
            utc_time = value.astimezone(UTC)
        s = _fmt(utc_time)
        if show_timezone:
            s += " UTC"
        return s

    if time_display_mode == "both":
        # Local
        local_str = _fmt(value)
        if show_timezone:
            tz_abbr = _get_timezone_abbreviation(value)
            if tz_abbr:
                local_str += f" {tz_abbr}"

        # UTC
        utc_time = value.astimezone(UTC) if value.tzinfo else value
        utc_str = _fmt(utc_time)
        return f"{local_str} ({utc_str} UTC)"

    # Local
    s = _fmt(value)
    if show_timezone:
        tz_abbr = _get_timezone_abbreviation(value)
        if tz_abbr:
            s += f" {tz_abbr}"
    return s


def format_timestamp(
    value: datetime,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str:
    """Return a timestamp suitable for metric labels."""
    return format_display_time(
        value,
        time_display_mode=time_display_mode,
        use_12hour=use_12hour,
        show_timezone=show_timezone,
    )


def get_uv_description(uv_index: float) -> str:
    """Describe a numeric UV index value."""
    if uv_index < 3:
        return "Low"
    if uv_index < 6:
        return "Moderate"
    if uv_index < 8:
        return "High"
    if uv_index < 11:
        return "Very High"
    return "Extreme"


def format_sun_time(
    sun_time: datetime | None,
    *,
    time_display_mode: str = "local",
    use_12hour: bool = True,
    show_timezone: bool = False,
) -> str | None:
    """
    Format sunrise or sunset time for display.

    Args:
    ----
        sun_time: Datetime object for sunrise or sunset (should be timezone-aware
                  in the location's local timezone)
        time_display_mode: Display mode preference
        use_12hour: 12/24 hour format preference
        show_timezone: Whether to show timezone suffix

    Returns:
    -------
        Formatted time string (e.g., "6:32 AM PST") or None if time is not available

    """
    if sun_time is None:
        return None
    return format_display_time(
        sun_time,
        time_display_mode=time_display_mode,
        use_12hour=use_12hour,
        show_timezone=show_timezone,
    )


def wrap_text(text: str, width: int) -> str:
    """Wrap long text blocks to make fallback text easier to read."""
    return textwrap.fill(text, width=width, break_long_words=False)


def truncate(text: str, max_length: int) -> str:
    """Trim text to a maximum length using an ellipsis when needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def get_temperature_precision(unit_pref: TemperatureUnit) -> int:
    """Return the decimal precision to use for temperature display."""
    return 0 if unit_pref == TemperatureUnit.BOTH else 1


def format_temperature_with_feels_like(
    current: CurrentConditions,
    unit_pref: TemperatureUnit,
    precision: int,
    *,
    difference_threshold: float = 3.0,
) -> tuple[str, str | None]:
    """
    Format temperature with inline feels-like comparison when significantly different.

    Returns a tuple of (temperature_string, feels_like_reason).
    The feels_like_reason explains why it feels different (humidity, wind, etc.)
    and is None if the difference is below threshold.

    Args:
    ----
        current: Current weather conditions
        unit_pref: Temperature unit preference
        precision: Decimal precision for display
        difference_threshold: Minimum difference in °F to show feels-like (default 3°F)

    Returns:
    -------
        Tuple of (formatted_temp, reason_or_none)
        Example: ("75°F (feels like 82°F)", "due to high humidity")

    """
    # Format base temperature
    temp_str = format_temperature_pair(
        current.temperature_f, current.temperature_c, unit_pref, precision
    )
    if temp_str is None:
        return "N/A", None

    # Check if we have feels-like data
    feels_f = current.feels_like_f
    feels_c = current.feels_like_c
    if feels_f is None and feels_c is None:
        return temp_str, None

    # Calculate difference (use Fahrenheit for threshold comparison)
    actual_f = current.temperature_f
    if actual_f is None and current.temperature_c is not None:
        actual_f = (current.temperature_c * 9 / 5) + 32
    if feels_f is None and feels_c is not None:
        feels_f = (feels_c * 9 / 5) + 32

    if actual_f is None or feels_f is None:
        return temp_str, None

    diff = feels_f - actual_f

    # Only show feels-like if difference exceeds threshold
    if abs(diff) < difference_threshold:
        return temp_str, None

    # Format feels-like temperature
    feels_str = format_temperature_pair(feels_f, feels_c, unit_pref, precision)
    if feels_str is None:
        return temp_str, None

    # Build the combined string
    combined = f"{temp_str} (feels like {feels_str})"

    # Determine the reason for the difference
    reason = _get_feels_like_reason(current, diff)

    return combined, reason


def _get_feels_like_reason(current: CurrentConditions, diff_f: float) -> str | None:
    """
    Determine why the apparent temperature differs from actual.

    Args:
    ----
        current: Current weather conditions
        diff_f: Difference in Fahrenheit (positive = feels warmer)

    Returns:
    -------
        Human-readable reason or None

    """
    humidity = current.humidity
    wind_mph = current.wind_speed_mph
    temp_f = current.temperature_f

    if diff_f > 0:
        # Feels warmer - likely heat index (humidity effect)
        if humidity is not None and humidity >= 40:
            if humidity >= 70:
                return "due to high humidity"
            return "due to humidity"
        return None
    # Feels colder - likely wind chill
    if wind_mph is not None and wind_mph >= 3:
        if wind_mph >= 15:
            return "due to strong wind"
        return "due to wind"
    # Could also be low humidity in cold weather
    if temp_f is not None and temp_f < 50 and humidity is not None and humidity < 30:
        return "due to dry air"
    return None


def format_hourly_wind(period: HourlyForecastPeriod) -> str | None:
    """Return wind description for hourly periods when both pieces are present."""
    if not period.wind_direction or not period.wind_speed:
        return None
    return f"{period.wind_direction} at {period.wind_speed}"


# Backwards compatibility alias if needed, though ideally should be removed/replaced
format_hour_time_with_preferences = format_display_time


def _get_timezone_abbreviation(dt: datetime) -> str:
    """
    Get timezone abbreviation for a datetime, handling cross-platform differences.

    Returns consistent abbreviations like 'EST', 'PST', 'UTC' instead of platform-specific
    names like 'Eastern Standard Time' on Windows.
    """
    if dt.tzinfo is None:
        return ""

    # Try to get tzname from the datetime
    tzname = dt.strftime("%Z")
    if not tzname:
        return ""

    # Handle common full timezone names and convert to abbreviations
    # This ensures consistency across Windows and Unix systems
    timezone_map = {
        "Eastern Standard Time": "EST",
        "Eastern Daylight Time": "EDT",
        "Central Standard Time": "CST",
        "Central Daylight Time": "CDT",
        "Mountain Standard Time": "MST",
        "Mountain Daylight Time": "MDT",
        "Pacific Standard Time": "PST",
        "Pacific Daylight Time": "PDT",
        "Coordinated Universal Time": "UTC",
    }

    # Return mapped abbreviation or original if already abbreviated
    return timezone_map.get(tzname, tzname)
