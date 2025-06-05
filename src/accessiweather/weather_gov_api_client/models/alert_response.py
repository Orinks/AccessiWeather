from enum import Enum


class AlertResponse(str, Enum):
    ALLCLEAR = "AllClear"
    ASSESS = "Assess"
    AVOID = "Avoid"
    EVACUATE = "Evacuate"
    EXECUTE = "Execute"
    MONITOR = "Monitor"
    NONE = "None"
    PREPARE = "Prepare"
    SHELTER = "Shelter"

    def __str__(self) -> str:
        return str(self.value)
