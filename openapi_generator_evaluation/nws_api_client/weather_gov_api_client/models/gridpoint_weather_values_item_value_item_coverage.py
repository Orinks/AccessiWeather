from enum import Enum


class GridpointWeatherValuesItemValueItemCoverage(str, Enum):
    AREAS = "areas"
    BRIEF = "brief"
    CHANCE = "chance"
    DEFINITE = "definite"
    FEW = "few"
    FREQUENT = "frequent"
    INTERMITTENT = "intermittent"
    ISOLATED = "isolated"
    LIKELY = "likely"
    NUMEROUS = "numerous"
    OCCASIONAL = "occasional"
    PATCHY = "patchy"
    PERIODS = "periods"
    SCATTERED = "scattered"
    SLIGHT_CHANCE = "slight_chance"
    WIDESPREAD = "widespread"

    def __str__(self) -> str:
        return str(self.value)
