from enum import Enum


class MarineRegionCode(str, Enum):
    AL = "AL"
    AT = "AT"
    GL = "GL"
    GM = "GM"
    PA = "PA"
    PI = "PI"

    def __str__(self) -> str:
        return str(self.value)
