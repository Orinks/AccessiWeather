from enum import Enum


class GetForecastWindSpeedUnit(str, Enum):
    KMH = "kmh"
    KN = "kn"
    MPH = "mph"
    MS = "ms"

    def __str__(self) -> str:
        return str(self.value)
