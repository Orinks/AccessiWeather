from enum import Enum


class AlertStatus(str, Enum):
    ACTUAL = "Actual"
    DRAFT = "Draft"
    EXERCISE = "Exercise"
    SYSTEM = "System"
    TEST = "Test"

    def __str__(self) -> str:
        return str(self.value)
