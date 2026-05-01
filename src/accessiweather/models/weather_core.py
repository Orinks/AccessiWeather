"""Core weather model helpers and location/source attribution dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Season(Enum):
    """Enumeration of seasons."""

    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"


def get_hemisphere(latitude: float) -> str:
    """
    Determine hemisphere based on latitude.

    Args:
        latitude: Location latitude (-90 to 90)

    Returns:
        "northern" for positive latitudes, "southern" for negative

    """
    return "northern" if latitude >= 0 else "southern"


def get_season(date: datetime, latitude: float) -> Season:
    """
    Determine the season based on date and hemisphere.

    Args:
        date: The current date
        latitude: Location latitude (determines hemisphere)

    Returns:
        The current season

    """
    hemisphere = get_hemisphere(latitude)
    month = date.month

    # Determine base season from month (Northern Hemisphere)
    if month in (12, 1, 2):
        base_season = Season.WINTER
    elif month in (3, 4, 5):
        base_season = Season.SPRING
    elif month in (6, 7, 8):
        base_season = Season.SUMMER
    else:  # 9, 10, 11
        base_season = Season.FALL

    # Flip season for Southern Hemisphere
    if hemisphere == "southern":
        season_flip = {
            Season.WINTER: Season.SUMMER,
            Season.SPRING: Season.FALL,
            Season.SUMMER: Season.WINTER,
            Season.FALL: Season.SPRING,
        }
        return season_flip[base_season]

    return base_season


@dataclass
class DataConflict:
    """Records a conflict between sources during data fusion."""

    field_name: str
    values: dict[str, Any]  # source -> value
    selected_source: str
    selected_value: Any


@dataclass
class SourceAttribution:
    """Tracks source attribution for merged data."""

    # Field name -> source name
    field_sources: dict[str, str] = field(default_factory=dict)

    # Conflicts detected during merge
    conflicts: list[DataConflict] = field(default_factory=list)

    # Sources that contributed to this data
    contributing_sources: set[str] = field(default_factory=set)

    # Sources that failed
    failed_sources: set[str] = field(default_factory=set)


@dataclass
class Location:
    """Simple location data."""

    name: str
    latitude: float
    longitude: float
    timezone: str | None = None
    country_code: str | None = None
    marine_mode: bool = False
    # NWS zone metadata (populated for US locations on save/refresh)
    forecast_zone_id: str | None = None
    cwa_office: str | None = None
    county_zone_id: str | None = None
    fire_zone_id: str | None = None
    radar_station: str | None = None

    def __str__(self) -> str:
        return self.name

    def __post_init__(self) -> None:
        if self.country_code:
            self.country_code = self.country_code.upper()
