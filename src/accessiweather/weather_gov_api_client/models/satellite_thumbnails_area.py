from enum import Enum


class SatelliteThumbnailsArea(str, Enum):
    A = "a"
    E = "e"
    G = "g"
    H = "h"
    P = "p"
    S = "s"
    W = "w"

    def __str__(self) -> str:
        return str(self.value)
