from enum import Enum


class GridpointForecastPeriodTemperatureUnit(str, Enum):
    C = "C"
    F = "F"

    def __str__(self) -> str:
        return str(self.value)
