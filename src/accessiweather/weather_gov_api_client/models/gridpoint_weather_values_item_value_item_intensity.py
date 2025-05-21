from enum import Enum


class GridpointWeatherValuesItemValueItemIntensity(str, Enum):
    HEAVY = "heavy"
    LIGHT = "light"
    MODERATE = "moderate"
    VERY_LIGHT = "very_light"

    def __str__(self) -> str:
        return str(self.value)
