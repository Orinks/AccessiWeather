"""Element decoders for TAF wind, visibility, weather, and cloud tokens."""

from __future__ import annotations

from fractions import Fraction

from .taf_patterns import (
    CLOUD_RE,
    DESCRIPTORS,
    INTENSITY,
    KNOWN_PRECIP_CODES,
    PHENOMENA,
    WIND_RE,
)


def _decode_wind(token: str) -> str | None:
    match = WIND_RE.match(token)
    if not match:
        return None

    direction = match.group("dir")
    speed = match.group("speed")
    gust = match.group("gust")
    unit = match.group("unit")

    unit_text = {
        "KT": "knots",
        "MPS": "meters per second",
        "KMH": "kilometres per hour",
    }.get(unit, unit.lower())

    speed_value = int(speed)
    if direction == "000" and speed_value == 0:
        base = "Calm winds"
    elif direction == "VRB":
        base = f"Winds variable at {speed_value} {unit_text}"
    else:
        base = f"Winds from {direction} degrees at {speed_value} {unit_text}"

    if gust:
        gust_value = int(gust[1:])
        base += f" with gusts to {gust_value} {unit_text}"

    return f"{base} ({token})"


def _decode_visibility(token: str) -> str | None:
    working = token.strip()
    if not working:
        return None

    if working.endswith("SM"):
        return _decode_statute_mile_visibility(token, working)

    if len(working) == 4 and working.isdigit():
        distance_m = int(working)
        if distance_m == 9999:
            return "Visibility 10 kilometres or more (9999 meters)"
        distance_km = distance_m / 1000
        return f"Visibility {distance_km:.1f} kilometres ({working} meters)"

    return None


def _decode_statute_mile_visibility(token: str, working: str) -> str:
    magnitude = working[:-2].strip()
    prefix = None
    if magnitude.startswith(("P", "M")):
        prefix = magnitude[0]
        magnitude = magnitude[1:]

    whole_number = None
    fraction_part = magnitude
    if " " in magnitude:
        parts = magnitude.split()
        whole_number = parts[0]
        fraction_part = parts[-1]
    elif " " in token:
        parts = token.replace("SM", "").split()
        if len(parts) == 2:
            whole_number, fraction_part = parts

    decimal_value, display_value = _parse_visibility_magnitude(whole_number, fraction_part)
    descriptor = "Visibility"
    if prefix == "P":
        descriptor = "Visibility greater than"
    elif prefix == "M":
        descriptor = "Visibility less than"

    if decimal_value is not None:
        decimal_str = f"{decimal_value:.2f}".rstrip("0").rstrip(".")
        decimal_text = f" ({decimal_str} SM)"
    else:
        decimal_text = ""

    return f"{descriptor} {display_value} statute miles{decimal_text} ({token})"


def _parse_visibility_magnitude(
    whole_number: str | None, fraction_part: str
) -> tuple[float | None, str]:
    decimal_value: float | None = None
    display_value = fraction_part

    if whole_number is not None and "/" in fraction_part:
        try:
            fraction = Fraction(fraction_part)
            decimal_value = int(whole_number) + float(fraction)
            display_value = f"{whole_number} {fraction_part}"
        except (ValueError, ZeroDivisionError):
            display_value = f"{whole_number} {fraction_part}"
    elif "/" in fraction_part:
        try:
            fraction = Fraction(fraction_part)
            decimal_value = float(fraction)
            display_value = fraction_part
        except (ValueError, ZeroDivisionError):
            display_value = fraction_part
    else:
        try:
            decimal_value = float(fraction_part)
            display_value = fraction_part
        except ValueError:
            display_value = fraction_part

    return decimal_value, display_value


def _decode_weather(token: str) -> str | None:
    if not token:
        return None

    original = token
    qualifier = ""
    intensity = ""
    working = token

    if working.startswith("VC"):
        qualifier = "In the vicinity, "
        working = working[2:]

    if working and working[0] in INTENSITY:
        intensity = INTENSITY[working[0]]
        working = working[1:]

    descriptor_codes, descriptors, phenomenon_codes, phenomena, working = _consume_weather_codes(
        working
    )
    if "UP" in phenomenon_codes:
        phenomena = _replace_unknown_precipitation(descriptor_codes, phenomenon_codes, phenomena)

    if not descriptors and not phenomena and not intensity:
        return None

    descriptor_text = " ".join(descriptors).strip()
    phenomena_text = " and ".join(phenomena).strip()
    pieces = [part for part in [intensity, descriptor_text, phenomena_text] if part]
    if not pieces:
        pieces.append("weather conditions")

    description = " ".join(pieces).replace("  ", " ").strip()
    return f"{qualifier}{description} ({original})"


def _consume_weather_codes(
    working: str,
) -> tuple[list[str], list[str], list[str], list[str], str]:
    descriptor_codes: list[str] = []
    descriptors: list[str] = []
    phenomenon_codes: list[str] = []
    phenomena: list[str] = []

    while working:
        code = working[:2]
        if code in DESCRIPTORS:
            descriptor_codes.append(code)
            descriptors.append(DESCRIPTORS[code])
            working = working[2:]
            continue
        if code in PHENOMENA:
            phenomenon_codes.append(code)
            phenomena.append(PHENOMENA[code])
            working = working[2:]
            continue
        break

    return descriptor_codes, descriptors, phenomenon_codes, phenomena, working


def _replace_unknown_precipitation(
    descriptor_codes: list[str],
    phenomenon_codes: list[str],
    phenomena: list[str],
) -> list[str]:
    inferred = _infer_unknown_precipitation_label(descriptor_codes, phenomenon_codes)
    if inferred == "mixed precipitation":
        return [inferred]
    non_unknown = [
        value for code, value in zip(phenomenon_codes, phenomena, strict=False) if code != "UP"
    ]
    return non_unknown or [inferred]


def _infer_unknown_precipitation_label(
    descriptor_codes: list[str], phenomenon_codes: list[str]
) -> str:
    """Infer a friendlier precipitation label when TAF uses UP (unknown precipitation)."""
    has_known_precip = any(code in KNOWN_PRECIP_CODES for code in phenomenon_codes if code != "UP")
    if has_known_precip:
        return "mixed precipitation"
    if "FZ" in descriptor_codes:
        return "freezing precipitation"
    if "TS" in descriptor_codes:
        return "thunderstorm precipitation"
    if "SH" in descriptor_codes:
        return "showery precipitation"
    return "unidentified precipitation"


def _decode_cloud(token: str) -> str | None:
    if not token:
        return None

    if token in {"SKC", "CLR"}:
        return f"Sky clear ({token})"
    if token == "NSC":
        return "No significant clouds (NSC)"

    match = CLOUD_RE.match(token)
    if not match:
        return None

    cover = match.group(1)
    height = match.group(2)
    cloud_type = match.group(3)

    cover_text = {
        "FEW": "A few clouds",
        "SCT": "Scattered clouds",
        "BKN": "Broken clouds",
        "OVC": "Overcast",
        "VV": "Vertical visibility",
    }.get(cover, cover)

    if cover == "VV" and height and height.isdigit():
        altitude = int(height) * 100
        return f"Vertical visibility {altitude:,} feet ({token})"

    altitude_text = ""
    if height and height.isdigit():
        altitude = int(height) * 100
        altitude_text = f" at {altitude:,} feet"

    type_text = ""
    if cloud_type == "CB":
        type_text = " with cumulonimbus"
    elif cloud_type == "TCU":
        type_text = " with towering cumulus"

    return f"{cover_text}{altitude_text}{type_text} ({token})"
