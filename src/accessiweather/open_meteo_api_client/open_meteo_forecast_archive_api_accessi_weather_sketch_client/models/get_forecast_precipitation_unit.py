from enum import Enum


class GetForecastPrecipitationUnit(str, Enum):
    INCH = "inch"
    MM = "mm"

    def __str__(self) -> str:
        return str(self.value)
