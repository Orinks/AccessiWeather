from enum import Enum


class AlertsActiveMessageTypeItem(str, Enum):
    ALERT = "alert"
    CANCEL = "cancel"
    UPDATE = "update"

    def __str__(self) -> str:
        return str(self.value)
