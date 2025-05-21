from enum import Enum


class AlertsActiveStatusItem(str, Enum):
    ACTUAL = "actual"
    DRAFT = "draft"
    EXERCISE = "exercise"
    SYSTEM = "system"
    TEST = "test"

    def __str__(self) -> str:
        return str(self.value)
