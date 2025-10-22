from enum import Enum


class GetTimelineUnitGroup(str, Enum):
    METRIC = "metric"
    UK = "uk"
    US = "us"

    def __str__(self) -> str:
        return str(self.value)
