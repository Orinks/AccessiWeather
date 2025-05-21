from enum import Enum


class MetarSkyCoverage(str, Enum):
    BKN = "BKN"
    CLR = "CLR"
    FEW = "FEW"
    OVC = "OVC"
    SCT = "SCT"
    SKC = "SKC"
    VV = "VV"

    def __str__(self) -> str:
        return str(self.value)
