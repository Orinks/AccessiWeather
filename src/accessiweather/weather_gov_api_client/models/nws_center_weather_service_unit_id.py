from enum import Enum


class NWSCenterWeatherServiceUnitId(str, Enum):
    ZAB = "ZAB"
    ZAN = "ZAN"
    ZAU = "ZAU"
    ZBW = "ZBW"
    ZDC = "ZDC"
    ZDV = "ZDV"
    ZFA = "ZFA"
    ZFW = "ZFW"
    ZHU = "ZHU"
    ZID = "ZID"
    ZJX = "ZJX"
    ZKC = "ZKC"
    ZLA = "ZLA"
    ZLC = "ZLC"
    ZMA = "ZMA"
    ZME = "ZME"
    ZMP = "ZMP"
    ZNY = "ZNY"
    ZOA = "ZOA"
    ZOB = "ZOB"
    ZSE = "ZSE"
    ZTL = "ZTL"

    def __str__(self) -> str:
        return str(self.value)
