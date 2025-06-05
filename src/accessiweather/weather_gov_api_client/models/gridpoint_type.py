from enum import Enum


class GridpointType(str, Enum):
    WXGRIDPOINT = "wx:Gridpoint"

    def __str__(self) -> str:
        return str(self.value)
