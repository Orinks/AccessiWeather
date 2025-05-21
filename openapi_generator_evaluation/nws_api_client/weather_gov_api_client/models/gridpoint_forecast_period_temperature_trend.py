from enum import Enum


class GridpointForecastPeriodTemperatureTrend(str, Enum):
    FALLING = "falling"
    RISING = "rising"

    def __str__(self) -> str:
        return str(self.value)
