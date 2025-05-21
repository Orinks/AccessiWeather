from enum import Enum


class AlertMessageType(str, Enum):
    ACK = "Ack"
    ALERT = "Alert"
    CANCEL = "Cancel"
    ERROR = "Error"
    UPDATE = "Update"

    def __str__(self) -> str:
        return str(self.value)
