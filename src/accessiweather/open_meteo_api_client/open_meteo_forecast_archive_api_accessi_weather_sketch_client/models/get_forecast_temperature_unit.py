from enum import Enum


class GetForecastTemperatureUnit(str, Enum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"

    def __str__(self) -> str:
        return str(self.value)
