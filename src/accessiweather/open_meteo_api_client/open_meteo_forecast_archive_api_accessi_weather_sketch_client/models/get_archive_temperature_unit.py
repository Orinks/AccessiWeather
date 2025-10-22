from enum import Enum


class GetArchiveTemperatureUnit(str, Enum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"

    def __str__(self) -> str:
        return str(self.value)
