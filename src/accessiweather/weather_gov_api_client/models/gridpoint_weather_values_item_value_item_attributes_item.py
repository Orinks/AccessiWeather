from enum import Enum


class GridpointWeatherValuesItemValueItemAttributesItem(str, Enum):
    DAMAGING_WIND = "damaging_wind"
    DRY_THUNDERSTORMS = "dry_thunderstorms"
    FLOODING = "flooding"
    GUSTY_WIND = "gusty_wind"
    HEAVY_RAIN = "heavy_rain"
    LARGE_HAIL = "large_hail"
    SMALL_HAIL = "small_hail"
    TORNADOES = "tornadoes"

    def __str__(self) -> str:
        return str(self.value)
