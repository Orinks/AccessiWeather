from enum import Enum


class GeoJSONMultiPolygonType(str, Enum):
    MULTIPOLYGON = "MultiPolygon"

    def __str__(self) -> str:
        return str(self.value)
