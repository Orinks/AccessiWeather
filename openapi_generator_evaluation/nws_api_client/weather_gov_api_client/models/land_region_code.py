from enum import Enum


class LandRegionCode(str, Enum):
    AR = "AR"
    CR = "CR"
    ER = "ER"
    PR = "PR"
    SR = "SR"
    WR = "WR"

    def __str__(self) -> str:
        return str(self.value)
