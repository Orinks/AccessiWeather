from enum import Enum


class NWSRegionalHQId(str, Enum):
    ARH = "ARH"
    CRH = "CRH"
    ERH = "ERH"
    PRH = "PRH"
    SRH = "SRH"
    WRH = "WRH"

    def __str__(self) -> str:
        return str(self.value)
