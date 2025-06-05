from enum import Enum


class MetarPhenomenonModifier(str, Enum):
    BLOWING = "blowing"
    FREEZING = "freezing"
    LOW_DRIFTING = "low_drifting"
    PARTIAL = "partial"
    PATCHES = "patches"
    SHALLOW = "shallow"
    SHOWERS = "showers"

    def __str__(self) -> str:
        return str(self.value)
