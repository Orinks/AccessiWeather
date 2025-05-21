from enum import Enum


class GeoJsonFeatureType(str, Enum):
    FEATURE = "Feature"

    def __str__(self) -> str:
        return str(self.value)
