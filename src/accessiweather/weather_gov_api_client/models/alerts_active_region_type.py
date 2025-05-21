from enum import Enum


class AlertsActiveRegionType(str, Enum):
    LAND = "land"
    MARINE = "marine"

    def __str__(self) -> str:
        return str(self.value)
