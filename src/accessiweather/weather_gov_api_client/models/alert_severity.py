from enum import Enum


class AlertSeverity(str, Enum):
    EXTREME = "Extreme"
    MINOR = "Minor"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
