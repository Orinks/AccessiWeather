from enum import Enum


class MetarPhenomenonIntensity(str, Enum):
    HEAVY = "heavy"
    LIGHT = "light"

    def __str__(self) -> str:
        return str(self.value)
