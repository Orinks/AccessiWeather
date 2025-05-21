from enum import Enum


class ObservationType(str, Enum):
    WXOBSERVATIONSTATION = "wx:ObservationStation"

    def __str__(self) -> str:
        return str(self.value)
