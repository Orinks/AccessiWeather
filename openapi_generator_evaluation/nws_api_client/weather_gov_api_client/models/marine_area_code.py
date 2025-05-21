from enum import Enum


class MarineAreaCode(str, Enum):
    AM = "AM"
    AN = "AN"
    GM = "GM"
    LC = "LC"
    LE = "LE"
    LH = "LH"
    LM = "LM"
    LO = "LO"
    LS = "LS"
    PH = "PH"
    PK = "PK"
    PM = "PM"
    PS = "PS"
    PZ = "PZ"
    SL = "SL"

    def __str__(self) -> str:
        return str(self.value)
