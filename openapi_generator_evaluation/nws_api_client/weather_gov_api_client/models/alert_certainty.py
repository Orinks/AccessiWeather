from enum import Enum


class AlertCertainty(str, Enum):
    LIKELY = "Likely"
    OBSERVED = "Observed"
    POSSIBLE = "Possible"
    UNKNOWN = "Unknown"
    UNLIKELY = "Unlikely"

    def __str__(self) -> str:
        return str(self.value)
