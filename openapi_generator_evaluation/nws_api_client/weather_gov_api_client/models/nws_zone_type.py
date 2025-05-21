from enum import Enum


class NWSZoneType(str, Enum):
    COASTAL = "coastal"
    COUNTY = "county"
    FIRE = "fire"
    FORECAST = "forecast"
    LAND = "land"
    MARINE = "marine"
    OFFSHORE = "offshore"
    PUBLIC = "public"

    def __str__(self) -> str:
        return str(self.value)
