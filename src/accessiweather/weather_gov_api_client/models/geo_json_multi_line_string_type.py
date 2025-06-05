from enum import Enum


class GeoJSONMultiLineStringType(str, Enum):
    MULTILINESTRING = "MultiLineString"

    def __str__(self) -> str:
        return str(self.value)
