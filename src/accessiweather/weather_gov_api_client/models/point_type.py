from enum import Enum


class PointType(str, Enum):
    WXPOINT = "wx:Point"

    def __str__(self) -> str:
        return str(self.value)
