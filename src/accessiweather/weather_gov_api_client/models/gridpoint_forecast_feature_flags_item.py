from enum import Enum


class GridpointForecastFeatureFlagsItem(str, Enum):
    FORECAST_TEMPERATURE_QV = "forecast_temperature_qv"
    FORECAST_WIND_SPEED_QV = "forecast_wind_speed_qv"

    def __str__(self) -> str:
        return str(self.value)
