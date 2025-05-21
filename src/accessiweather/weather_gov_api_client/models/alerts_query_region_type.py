from enum import Enum


class AlertsQueryRegionType(str, Enum):
    LAND = "land"
    MARINE = "marine"

    def __str__(self) -> str:
        return str(self.value)
