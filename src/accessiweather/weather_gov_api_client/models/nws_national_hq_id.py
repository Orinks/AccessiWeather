from enum import Enum


class NWSNationalHQId(str, Enum):
    NWS = "NWS"

    def __str__(self) -> str:
        return str(self.value)
