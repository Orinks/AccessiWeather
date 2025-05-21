from enum import Enum


class GeoJSONMultiPointType(str, Enum):
    MULTIPOINT = "MultiPoint"

    def __str__(self) -> str:
        return str(self.value)
