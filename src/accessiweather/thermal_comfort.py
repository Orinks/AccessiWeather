"""Sanity helpers for apparent temperature, wind chill, and heat index readings."""

from __future__ import annotations

from dataclasses import dataclass

WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F = 3.0
HEAT_INDEX_COHERENCE_TOLERANCE_F = 2.5
APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_BASE_F = 4.0
APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_MAX_F = 5.5
APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_PER_DEGREE_F = 0.15
HEAT_INDEX_MIN_TEMP_F = 80.0
HEAT_INDEX_MIN_HUMIDITY = 40


@dataclass(frozen=True)
class ThermalComfortReadings:
    """Normalized and sanity-checked apparent-temperature readings."""

    feels_like_f: float | None = None
    feels_like_c: float | None = None
    wind_chill_f: float | None = None
    wind_chill_c: float | None = None
    heat_index_f: float | None = None
    heat_index_c: float | None = None


def sanitize_thermal_comfort_readings(
    *,
    temperature_f: float | None,
    temperature_c: float | None = None,
    humidity: int | float | None,
    feels_like_f: float | None = None,
    feels_like_c: float | None = None,
    wind_chill_f: float | None = None,
    wind_chill_c: float | None = None,
    heat_index_f: float | None = None,
    heat_index_c: float | None = None,
) -> ThermalComfortReadings:
    """
    Normalize and discard internally inconsistent thermal-comfort readings.

    Literal heat-index readings must remain coherent with the standard heat-index
    envelope. Provider apparent temperatures get a small extra warm allowance for
    non-humidity effects such as sun exposure. Cold apparent temperatures are
    preserved so existing wind-chill behavior remains intact.
    """
    temp_f = _to_fahrenheit(temperature_f, temperature_c)
    feels_f = _to_fahrenheit(feels_like_f, feels_like_c)
    chill_f = _to_fahrenheit(wind_chill_f, wind_chill_c)
    heat_f = _to_fahrenheit(heat_index_f, heat_index_c)

    if not warm_apparent_temperature_is_coherent(temp_f, humidity, feels_f):
        feels_f = None
    if not warm_heat_index_is_coherent(temp_f, humidity, heat_f):
        heat_f = None

    if temp_f is not None:
        if heat_f is not None and heat_f <= temp_f:
            heat_f = None
        if chill_f is not None and chill_f >= temp_f:
            chill_f = None

    if feels_f is not None and temp_f is not None:
        if (
            feels_f > temp_f
            and heat_f is None
            and warm_heat_index_is_coherent(temp_f, humidity, feels_f)
        ):
            heat_f = feels_f
        elif feels_f < temp_f and chill_f is None:
            chill_f = feels_f

    if feels_f is None and temp_f is not None:
        if chill_f is not None and chill_f < temp_f:
            feels_f = chill_f
        elif heat_f is not None and heat_f > temp_f:
            feels_f = heat_f

    return ThermalComfortReadings(
        feels_like_f=feels_f,
        feels_like_c=_to_celsius(feels_f),
        wind_chill_f=chill_f,
        wind_chill_c=_to_celsius(chill_f),
        heat_index_f=heat_f,
        heat_index_c=_to_celsius(heat_f),
    )


def calculate_heat_index_f(temperature_f: float, humidity: int | float) -> float | None:
    """
    Calculate the NOAA/NWS Rothfusz heat index in Fahrenheit when applicable.

    Returns None outside the standard warm/humid heat-index range. This is used
    as a sanity envelope, not as a replacement for source-provided readings.
    """
    if temperature_f < HEAT_INDEX_MIN_TEMP_F or humidity < HEAT_INDEX_MIN_HUMIDITY:
        return None

    heat_index = (
        -42.379
        + 2.04901523 * temperature_f
        + 10.14333127 * humidity
        - 0.22475541 * temperature_f * humidity
        - 0.00683783 * temperature_f * temperature_f
        - 0.05481717 * humidity * humidity
        + 0.00122874 * temperature_f * temperature_f * humidity
        + 0.00085282 * temperature_f * humidity * humidity
        - 0.00000199 * temperature_f * temperature_f * humidity * humidity
    )

    if humidity > 85 and 80 <= temperature_f <= 87:
        heat_index += ((humidity - 85) / 10) * ((87 - temperature_f) / 5)

    return heat_index


def warm_apparent_temperature_is_coherent(
    temperature_f: float | None,
    humidity: int | float | None,
    apparent_f: float | None,
) -> bool:
    """Return whether a warm provider apparent temperature is plausible."""
    if temperature_f is None or apparent_f is None or apparent_f <= temperature_f:
        return True

    if apparent_f - temperature_f < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F:
        return True

    if humidity is None:
        return True

    max_coherent = temperature_f + _solar_apparent_temperature_allowance_f(temperature_f)
    heat_index = calculate_heat_index_f(temperature_f, humidity)
    if heat_index is not None:
        max_coherent = max(
            max_coherent,
            max(temperature_f, heat_index) + HEAT_INDEX_COHERENCE_TOLERANCE_F,
        )

    return apparent_f <= max_coherent


def warm_heat_index_is_coherent(
    temperature_f: float | None,
    humidity: int | float | None,
    heat_index_f: float | None,
) -> bool:
    """Return whether a literal or inferred heat-index reading is plausible."""
    if temperature_f is None or heat_index_f is None or heat_index_f <= temperature_f:
        return True

    if heat_index_f - temperature_f < WARM_FEELS_LIKE_DISPLAY_THRESHOLD_F:
        return True

    if humidity is None:
        return True

    heat_index = calculate_heat_index_f(temperature_f, humidity)
    if heat_index is None:
        return False

    max_coherent = max(temperature_f, heat_index) + HEAT_INDEX_COHERENCE_TOLERANCE_F
    return heat_index_f <= max_coherent


def _solar_apparent_temperature_allowance_f(temperature_f: float) -> float:
    allowance = APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_BASE_F
    if temperature_f > HEAT_INDEX_MIN_TEMP_F:
        allowance += (
            temperature_f - HEAT_INDEX_MIN_TEMP_F
        ) * APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_PER_DEGREE_F
    return min(allowance, APPARENT_TEMPERATURE_SOLAR_ALLOWANCE_MAX_F)


def _to_fahrenheit(value_f: float | None, value_c: float | None) -> float | None:
    if value_f is not None:
        return float(value_f)
    if value_c is not None:
        return (float(value_c) * 9 / 5) + 32
    return None


def _to_celsius(value_f: float | None) -> float | None:
    if value_f is None:
        return None
    return (value_f - 32) * 5 / 9
