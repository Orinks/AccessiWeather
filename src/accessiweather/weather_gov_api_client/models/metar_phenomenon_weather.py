from enum import Enum


class MetarPhenomenonWeather(str, Enum):
    DRIZZLE = "drizzle"
    DUST = "dust"
    DUST_STORM = "dust_storm"
    DUST_WHIRLS = "dust_whirls"
    FOG = "fog"
    FOG_MIST = "fog_mist"
    FUNNEL_CLOUD = "funnel_cloud"
    HAIL = "hail"
    HAZE = "haze"
    ICE_CRYSTALS = "ice_crystals"
    ICE_PELLETS = "ice_pellets"
    RAIN = "rain"
    SAND = "sand"
    SAND_STORM = "sand_storm"
    SMOKE = "smoke"
    SNOW = "snow"
    SNOW_GRAINS = "snow_grains"
    SNOW_PELLETS = "snow_pellets"
    SPRAY = "spray"
    SQUALLS = "squalls"
    THUNDERSTORMS = "thunderstorms"
    UNKNOWN = "unknown"
    VOLCANIC_ASH = "volcanic_ash"

    def __str__(self) -> str:
        return str(self.value)
