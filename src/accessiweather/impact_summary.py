"""
Rule-based weather impact summaries for outdoor, driving, and allergy guidance.

All rules are fully documented and unit-testable — no AI or opaque logic.

Rule sets
---------
Outdoor
    Based on feels-like (or actual) temperature, UV index, and active precipitation.

Driving
    Based on visibility, precipitation type, near-freezing temperature, and wind.

Allergy
    Based on pollen category/index, primary allergen, wind dispersion, and air quality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CurrentConditions, EnvironmentalConditions, ForecastPeriod


@dataclass(slots=True)
class ImpactSummary:
    """Human-readable impact guidance for three lifestyle contexts."""

    outdoor: str | None = None
    driving: str | None = None
    allergy: str | None = None

    def has_content(self) -> bool:
        """Return True when at least one impact area has guidance."""
        return any([self.outdoor, self.driving, self.allergy])


# ── Outdoor guidance ──────────────────────────────────────────────────────────

# Temperature comfort bands (Fahrenheit, applied to feels-like or actual temp)
# Each entry: (upper_exclusive, label)
_OUTDOOR_TEMP_BANDS: list[tuple[float, str]] = [
    (0, "Dangerous cold - avoid prolonged outdoor exposure"),
    (15, "Extreme cold - dress in heavy layers, limit time outside"),
    (25, "Very cold - heavy winter clothing required"),
    (32, "Cold - wear a heavy coat"),
    (50, "Cool - coat or warm jacket recommended"),
    (60, "Mild - light jacket may be needed"),
    (78, "Comfortable - good conditions for outdoor activities"),
    (85, "Warm - pleasant for most outdoor activities"),
    (95, "Hot - stay hydrated and seek shade during peak hours"),
    (105, "Very hot - limit strenuous outdoor activity"),
    (float("inf"), "Extreme heat - avoid outdoor exertion"),
]

_PRECIP_CONDITION_KEYWORDS = frozenset(
    ["rain", "snow", "storm", "drizzle", "shower", "sleet", "hail", "flurr"]
)


def _outdoor_from_conditions(
    feels_like_f: float | None,
    temp_f: float | None,
    uv_index: float | None,
    condition: str | None,
) -> str | None:
    """
    Return concise outdoor guidance from current conditions.

    Rules (in order of application):
    1. Selects comfort band from feels-like temperature (falls back to actual temp).
    2. Appends UV protection note when UV index >= 6.
    3. Appends precipitation warning when condition text implies active precipitation.
    """
    ref_temp = feels_like_f if feels_like_f is not None else temp_f
    if ref_temp is None:
        return None

    comfort = next(label for upper, label in _OUTDOOR_TEMP_BANDS if ref_temp < upper)

    modifiers: list[str] = []

    if uv_index is not None:
        if uv_index >= 8:
            modifiers.append("UV very high - sun protection essential")
        elif uv_index >= 6:
            modifiers.append("wear sunscreen")

    condition_lower = (condition or "").lower()
    if any(kw in condition_lower for kw in _PRECIP_CONDITION_KEYWORDS):
        modifiers.append("active precipitation - bring appropriate gear")

    if modifiers:
        return f"{comfort}; {'; '.join(modifiers)}"
    return comfort


# ── Driving guidance ──────────────────────────────────────────────────────────

_ICE_KEYWORDS = frozenset(["ice", "freezing", "sleet", "glaze"])
_SNOW_KEYWORDS = frozenset(["snow", "blizzard", "flurr"])
_RAIN_KEYWORDS = frozenset(["rain", "downpour", "drizzle", "shower"])
_THUNDER_KEYWORDS = frozenset(["thunder", "storm", "lightning"])


def _has_keyword(text: str, keywords: frozenset[str]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _driving_from_conditions(
    visibility_miles: float | None,
    wind_speed_mph: float | None,
    wind_gust_mph: float | None,
    temp_f: float | None,
    condition: str | None,
    precipitation_type: list[str] | None,
) -> str | None:
    """
    Return concise driving guidance from current conditions.

    Rules (in order of priority):
    1. Visibility: < 0.25 mi → near-zero; < 1 mi → very low; < 3 mi → reduced.
    2. Precipitation type (explicit list or condition text):
       ice/freezing > snow > thunderstorm > rain.
    3. Near-freezing temperature (25–36 °F) with any moisture hints → black-ice warning.
    4. Wind: >= 45 mph → dangerous; >= 30 → high; >= 20 → gusty.
    """
    issues: list[str] = []

    # 1. Visibility
    if visibility_miles is not None:
        if visibility_miles < 0.25:
            issues.append("near-zero visibility - do not drive unless essential")
        elif visibility_miles < 1.0:
            issues.append("very low visibility - drive with extreme caution")
        elif visibility_miles < 3.0:
            issues.append("reduced visibility - drive carefully")

    # 2. Precipitation type
    precip_text = " ".join(precipitation_type or []) + " " + (condition or "")
    if _has_keyword(precip_text, _ICE_KEYWORDS):
        issues.append("ice possible - slow down, allow extra stopping distance")
    elif _has_keyword(precip_text, _SNOW_KEYWORDS):
        issues.append("snow on roads - reduce speed and increase following distance")
    elif _has_keyword(precip_text, _THUNDER_KEYWORDS):
        issues.append("thunderstorms - avoid driving if possible")
    elif _has_keyword(precip_text, _RAIN_KEYWORDS):
        issues.append("wet roads - allow extra stopping distance")

    # 3. Near-freezing black-ice risk (only if no ice warning already added)
    if temp_f is not None and 25 <= temp_f <= 36:
        cond_lower = (condition or "").lower()
        moisture_present = any(
            kw in cond_lower
            for kw in ["rain", "drizzle", "snow", "sleet", "cloud", "fog", "mist", "overcast"]
        )
        if moisture_present and not any("ice" in issue for issue in issues):
            issues.append("near-freezing temperatures - watch for black ice")

    # 4. Wind
    effective_wind = max(wind_speed_mph or 0.0, wind_gust_mph or 0.0)
    if effective_wind >= 45:
        issues.append("dangerous winds - high-profile vehicles at serious risk")
    elif effective_wind >= 30:
        issues.append("high winds - caution especially for tall vehicles")
    elif effective_wind >= 20:
        issues.append("gusty winds - minor effect on steering")

    if not issues:
        return "Normal driving conditions"
    return "Caution: " + "; ".join(issues)


# ── Allergy guidance ──────────────────────────────────────────────────────────

# Higher rank = more severe pollen risk
_POLLEN_CATEGORY_RANK: dict[str, int] = {
    "None": 0,
    "Very Low": 1,
    "Low": 2,
    "Moderate": 3,
    "High": 4,
    "Very High": 5,
    "Extreme": 6,
}

_AQ_CATEGORY_RANK: dict[str, int] = {
    "Good": 1,
    "Moderate": 2,
    "Unhealthy for Sensitive Groups": 3,
    "Unhealthy": 4,
    "Very Unhealthy": 5,
    "Hazardous": 6,
}


def _allergy_from_conditions(
    pollen_index: float | None,
    pollen_category: str | None,
    pollen_primary_allergen: str | None,
    wind_speed_mph: float | None,
    air_quality_category: str | None,
) -> str | None:
    """
    Return allergy/outdoor air guidance.

    Rules:
    1. Pollen category maps to a severity band; allergen name appended when available.
    2. Wind >= 15 mph with moderate-or-higher pollen triggers a dispersion note.
    3. Unhealthy (or worse) AQI adds an exposure-limit note.
    """
    parts: list[str] = []

    category_rank = _POLLEN_CATEGORY_RANK.get(pollen_category or "", -1)
    allergen_note = f" ({pollen_primary_allergen})" if pollen_primary_allergen else ""

    if pollen_category is not None:
        if category_rank >= 5:
            parts.append(f"Very high pollen{allergen_note} - take allergy precautions")
        elif category_rank == 4:
            parts.append(
                f"High pollen{allergen_note} - sensitive individuals should limit exposure"
            )
        elif category_rank == 3:
            parts.append(
                f"Moderate pollen{allergen_note} - sensitive individuals may experience symptoms"
            )
        elif category_rank in (1, 2):
            parts.append(f"Low pollen{allergen_note}")
        else:
            parts.append(f"Pollen: {pollen_category}{allergen_note}")
    elif pollen_index is not None:
        if pollen_index >= 10:
            parts.append("High pollen index - allergy precautions recommended")
        elif pollen_index >= 5:
            parts.append("Moderate pollen index")
        else:
            parts.append("Low pollen index")

    # Wind dispersion note
    if parts and wind_speed_mph is not None and wind_speed_mph >= 15 and category_rank >= 3:
        parts.append("wind increasing pollen dispersion")

    # Air quality note
    aq_rank = _AQ_CATEGORY_RANK.get(air_quality_category or "", 0)
    if aq_rank >= 4:
        parts.append(f"air quality {air_quality_category} - limit outdoor exposure")
    elif aq_rank == 3:
        parts.append("air quality unhealthy for sensitive groups")

    return "; ".join(parts) if parts else None


# ── Public API ─────────────────────────────────────────────────────────────────


def build_impact_summary(
    current: CurrentConditions | None,
    environmental: EnvironmentalConditions | None = None,
) -> ImpactSummary:
    """
    Derive impact summaries from current conditions and environmental data.

    Args:
        current: Current weather conditions.  Returns an empty summary when None.
        environmental: Optional environmental conditions (pollen, AQI).

    Returns:
        An ImpactSummary with outdoor, driving, and allergy fields populated
        where sufficient data is available.

    """
    if not current:
        return ImpactSummary()

    outdoor = _outdoor_from_conditions(
        feels_like_f=current.feels_like_f,
        temp_f=current.temperature_f,
        uv_index=current.uv_index,
        condition=current.condition,
    )

    driving = _driving_from_conditions(
        visibility_miles=current.visibility_miles,
        wind_speed_mph=current.wind_speed_mph,
        wind_gust_mph=current.wind_gust_mph,
        temp_f=current.temperature_f,
        condition=current.condition,
        precipitation_type=current.precipitation_type,
    )

    allergy = _allergy_from_conditions(
        pollen_index=environmental.pollen_index if environmental else None,
        pollen_category=environmental.pollen_category if environmental else None,
        pollen_primary_allergen=environmental.pollen_primary_allergen if environmental else None,
        wind_speed_mph=current.wind_speed_mph,
        air_quality_category=environmental.air_quality_category if environmental else None,
    )

    return ImpactSummary(outdoor=outdoor, driving=driving, allergy=allergy)


def build_forecast_impact_summary(
    period: ForecastPeriod,
) -> ImpactSummary:
    """
    Derive impact summaries from a forecast period.

    Args:
        period: A single forecast period from the daily or hourly forecast.

    Returns:
        An ImpactSummary derived from the period's temperature, wind, and conditions.

    """
    # Normalise temperature to Fahrenheit
    temp_f: float | None = None
    if period.temperature is not None:
        temp_f = (
            float(period.temperature) * 9 / 5 + 32
            if getattr(period, "temperature_unit", "F") == "C"
            else float(period.temperature)
        )

    # Approximate feels-like from feels_like_high, falling back to temp
    feels_f = (
        period.feels_like_high if getattr(period, "feels_like_high", None) is not None else temp_f
    )

    outdoor = _outdoor_from_conditions(
        feels_like_f=feels_f,
        temp_f=temp_f,
        uv_index=getattr(period, "uv_index_max", None) or period.uv_index,
        condition=period.short_forecast,
    )

    # Extract a numeric wind speed from the string, e.g. "15 mph" or "15 to 25 mph"
    wind_mph: float | None = None
    wind_str = period.wind_speed or ""
    nums = re.findall(r"\d+(?:\.\d+)?", wind_str)
    if nums:
        wind_mph = max(float(n) for n in nums)

    driving = _driving_from_conditions(
        visibility_miles=None,
        wind_speed_mph=wind_mph,
        wind_gust_mph=None,
        temp_f=temp_f,
        condition=period.short_forecast,
        precipitation_type=getattr(period, "precipitation_type", None),
    )

    allergy = _allergy_from_conditions(
        pollen_index=None,
        pollen_category=getattr(period, "pollen_forecast", None),
        pollen_primary_allergen=None,
        wind_speed_mph=wind_mph,
        air_quality_category=None,
    )

    return ImpactSummary(outdoor=outdoor, driving=driving, allergy=allergy)
