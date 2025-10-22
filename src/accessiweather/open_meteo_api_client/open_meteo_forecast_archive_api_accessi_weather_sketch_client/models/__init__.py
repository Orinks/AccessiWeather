"""Contains all the data models used in inputs/outputs"""

from .archive_daily_data import ArchiveDailyData
from .archive_daily_units import ArchiveDailyUnits
from .archive_response import ArchiveResponse
from .current_data import CurrentData
from .current_units import CurrentUnits
from .daily_data import DailyData
from .daily_units import DailyUnits
from .forecast_response import ForecastResponse
from .get_archive_temperature_unit import GetArchiveTemperatureUnit
from .get_forecast_precipitation_unit import GetForecastPrecipitationUnit
from .get_forecast_temperature_unit import GetForecastTemperatureUnit
from .get_forecast_wind_speed_unit import GetForecastWindSpeedUnit
from .hourly_data import HourlyData
from .hourly_units import HourlyUnits
from .open_meteo_error import OpenMeteoError

__all__ = (
    "ArchiveDailyData",
    "ArchiveDailyUnits",
    "ArchiveResponse",
    "CurrentData",
    "CurrentUnits",
    "DailyData",
    "DailyUnits",
    "ForecastResponse",
    "GetArchiveTemperatureUnit",
    "GetForecastPrecipitationUnit",
    "GetForecastTemperatureUnit",
    "GetForecastWindSpeedUnit",
    "HourlyData",
    "HourlyUnits",
    "OpenMeteoError",
)
