from enum import Enum


class GridpointForecastUnits(str, Enum):
    SI = "si"
    US = "us"

    def __str__(self) -> str:
        return str(self.value)
