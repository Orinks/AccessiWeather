from enum import Enum


class GridpointForecastPeriodWindDirection(str, Enum):
    E = "E"
    ENE = "ENE"
    ESE = "ESE"
    N = "N"
    NE = "NE"
    NNE = "NNE"
    NNW = "NNW"
    NW = "NW"
    S = "S"
    SE = "SE"
    SSE = "SSE"
    SSW = "SSW"
    SW = "SW"
    W = "W"
    WNW = "WNW"
    WSW = "WSW"

    def __str__(self) -> str:
        return str(self.value)
