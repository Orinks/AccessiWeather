from enum import Enum


class AlertsQueryMessageTypeItem(str, Enum):
    ALERT = "alert"
    CANCEL = "cancel"
    UPDATE = "update"

    def __str__(self) -> str:
        return str(self.value)
