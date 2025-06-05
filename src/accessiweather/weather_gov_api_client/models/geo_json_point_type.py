from enum import Enum


class GeoJSONPointType(str, Enum):
    POINT = "Point"

    def __str__(self) -> str:
        return str(self.value)
