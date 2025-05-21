from enum import Enum


class AlertUrgency(str, Enum):
    EXPECTED = "Expected"
    FUTURE = "Future"
    IMMEDIATE = "Immediate"
    PAST = "Past"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
