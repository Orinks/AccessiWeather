from enum import Enum


class GridpointWeatherValuesItemValueItemWeather(str, Enum):
    BLOWING_DUST = "blowing_dust"
    BLOWING_SAND = "blowing_sand"
    BLOWING_SNOW = "blowing_snow"
    DRIZZLE = "drizzle"
    FOG = "fog"
    FREEZING_DRIZZLE = "freezing_drizzle"
    FREEZING_FOG = "freezing_fog"
    FREEZING_RAIN = "freezing_rain"
    FREEZING_SPRAY = "freezing_spray"
    FROST = "frost"
    HAIL = "hail"
    HAZE = "haze"
    ICE_CRYSTALS = "ice_crystals"
    ICE_FOG = "ice_fog"
    RAIN = "rain"
    RAIN_SHOWERS = "rain_showers"
    SLEET = "sleet"
    SMOKE = "smoke"
    SNOW = "snow"
    SNOW_SHOWERS = "snow_showers"
    THUNDERSTORMS = "thunderstorms"
    VOLCANIC_ASH = "volcanic_ash"
    WATER_SPOUTS = "water_spouts"

    def __str__(self) -> str:
        return str(self.value)
