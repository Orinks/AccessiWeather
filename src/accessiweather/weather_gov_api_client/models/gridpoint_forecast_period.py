import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.gridpoint_forecast_period_temperature_trend import (
    GridpointForecastPeriodTemperatureTrend,
)
from ..models.gridpoint_forecast_period_temperature_unit import (
    GridpointForecastPeriodTemperatureUnit,
)
from ..models.gridpoint_forecast_period_wind_direction import GridpointForecastPeriodWindDirection
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.quantitative_value import QuantitativeValue


T = TypeVar("T", bound="GridpointForecastPeriod")


@_attrs_define
class GridpointForecastPeriod:
    """An object containing forecast information for a specific time period (generally 12-hour or 1-hour).

    Attributes:
        number (Union[Unset, int]): Sequential period number.
        name (Union[Unset, str]): A textual identifier for the period. This value will not be present for hourly
            forecasts.
             Example: Tuesday Night.
        start_time (Union[Unset, datetime.datetime]): The starting time that this forecast period is valid for.
        end_time (Union[Unset, datetime.datetime]): The ending time that this forecast period is valid for.
        is_daytime (Union[Unset, bool]): Indicates whether this period is daytime or nighttime.
        temperature (Union['QuantitativeValue', Unset, int]): High/low temperature for the period, depending on whether
            the period is day or night.
            This property as an integer value is deprecated. Future versions will express this value as a quantitative value
            object. To make use of the future standard format now, set the "forecast_temperature_qv" feature flag on the
            request.
        temperature_unit (Union[Unset, GridpointForecastPeriodTemperatureUnit]): The unit of the temperature value
            (Fahrenheit or Celsius).
            This property is deprecated. Future versions will indicate the unit within the quantitative value object for the
            temperature property. To make use of the future standard format now, set the "forecast_temperature_qv" feature
            flag on the request.
        temperature_trend (Union[Unset, GridpointForecastPeriodTemperatureTrend]): If not null, indicates a non-diurnal
            temperature trend for the period (either rising temperature overnight, or falling temperature during the day)
        probability_of_precipitation (Union[Unset, QuantitativeValue]): A structured value representing a measurement
            and its unit of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        dewpoint (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        relative_humidity (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit
            of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        wind_speed (Union['QuantitativeValue', Unset, str]): Wind speed for the period.
            This property as an string value is deprecated. Future versions will express this value as a quantitative value
            object. To make use of the future standard format now, set the "forecast_wind_speed_qv" feature flag on the
            request.
        wind_gust (Union['QuantitativeValue', None, Unset, str]): Peak wind gust for the period.
            This property as an string value is deprecated. Future versions will express this value as a quantitative value
            object. To make use of the future standard format now, set the "forecast_wind_speed_qv" feature flag on the
            request.
        wind_direction (Union[Unset, GridpointForecastPeriodWindDirection]): The prevailing direction of the wind for
            the period, using a 16-point compass.
        icon (Union[Unset, str]): A link to an icon representing the forecast summary.
        short_forecast (Union[Unset, str]): A brief textual forecast summary for the period.
        detailed_forecast (Union[Unset, str]): A detailed textual forecast for the period.
    """

    number: Union[Unset, int] = UNSET
    name: Union[Unset, str] = UNSET
    start_time: Union[Unset, datetime.datetime] = UNSET
    end_time: Union[Unset, datetime.datetime] = UNSET
    is_daytime: Union[Unset, bool] = UNSET
    temperature: Union["QuantitativeValue", Unset, int] = UNSET
    temperature_unit: Union[Unset, GridpointForecastPeriodTemperatureUnit] = UNSET
    temperature_trend: Union[Unset, GridpointForecastPeriodTemperatureTrend] = UNSET
    probability_of_precipitation: Union[Unset, "QuantitativeValue"] = UNSET
    dewpoint: Union[Unset, "QuantitativeValue"] = UNSET
    relative_humidity: Union[Unset, "QuantitativeValue"] = UNSET
    wind_speed: Union["QuantitativeValue", Unset, str] = UNSET
    wind_gust: Union["QuantitativeValue", None, Unset, str] = UNSET
    wind_direction: Union[Unset, GridpointForecastPeriodWindDirection] = UNSET
    icon: Union[Unset, str] = UNSET
    short_forecast: Union[Unset, str] = UNSET
    detailed_forecast: Union[Unset, str] = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.quantitative_value import QuantitativeValue

        number = self.number

        name = self.name

        start_time: Union[Unset, str] = UNSET
        if not isinstance(self.start_time, Unset):
            start_time = self.start_time.isoformat()

        end_time: Union[Unset, str] = UNSET
        if not isinstance(self.end_time, Unset):
            end_time = self.end_time.isoformat()

        is_daytime = self.is_daytime

        temperature: Union[Unset, dict[str, Any], int]
        if isinstance(self.temperature, Unset):
            temperature = UNSET
        elif isinstance(self.temperature, QuantitativeValue):
            temperature = self.temperature.to_dict()
        else:
            temperature = self.temperature

        temperature_unit: Union[Unset, str] = UNSET
        if not isinstance(self.temperature_unit, Unset):
            temperature_unit = self.temperature_unit.value

        temperature_trend: Union[Unset, str] = UNSET
        if not isinstance(self.temperature_trend, Unset):
            temperature_trend = self.temperature_trend.value

        probability_of_precipitation: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.probability_of_precipitation, Unset):
            probability_of_precipitation = self.probability_of_precipitation.to_dict()

        dewpoint: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.dewpoint, Unset):
            dewpoint = self.dewpoint.to_dict()

        relative_humidity: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.relative_humidity, Unset):
            relative_humidity = self.relative_humidity.to_dict()

        wind_speed: Union[Unset, dict[str, Any], str]
        if isinstance(self.wind_speed, Unset):
            wind_speed = UNSET
        elif isinstance(self.wind_speed, QuantitativeValue):
            wind_speed = self.wind_speed.to_dict()
        else:
            wind_speed = self.wind_speed

        wind_gust: Union[None, Unset, dict[str, Any], str]
        if isinstance(self.wind_gust, Unset):
            wind_gust = UNSET
        elif isinstance(self.wind_gust, QuantitativeValue):
            wind_gust = self.wind_gust.to_dict()
        else:
            wind_gust = self.wind_gust

        wind_direction: Union[Unset, str] = UNSET
        if not isinstance(self.wind_direction, Unset):
            wind_direction = self.wind_direction.value

        icon = self.icon

        short_forecast = self.short_forecast

        detailed_forecast = self.detailed_forecast

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if number is not UNSET:
            field_dict["number"] = number
        if name is not UNSET:
            field_dict["name"] = name
        if start_time is not UNSET:
            field_dict["startTime"] = start_time
        if end_time is not UNSET:
            field_dict["endTime"] = end_time
        if is_daytime is not UNSET:
            field_dict["isDaytime"] = is_daytime
        if temperature is not UNSET:
            field_dict["temperature"] = temperature
        if temperature_unit is not UNSET:
            field_dict["temperatureUnit"] = temperature_unit
        if temperature_trend is not UNSET:
            field_dict["temperatureTrend"] = temperature_trend
        if probability_of_precipitation is not UNSET:
            field_dict["probabilityOfPrecipitation"] = probability_of_precipitation
        if dewpoint is not UNSET:
            field_dict["dewpoint"] = dewpoint
        if relative_humidity is not UNSET:
            field_dict["relativeHumidity"] = relative_humidity
        if wind_speed is not UNSET:
            field_dict["windSpeed"] = wind_speed
        if wind_gust is not UNSET:
            field_dict["windGust"] = wind_gust
        if wind_direction is not UNSET:
            field_dict["windDirection"] = wind_direction
        if icon is not UNSET:
            field_dict["icon"] = icon
        if short_forecast is not UNSET:
            field_dict["shortForecast"] = short_forecast
        if detailed_forecast is not UNSET:
            field_dict["detailedForecast"] = detailed_forecast

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.quantitative_value import QuantitativeValue

        d = dict(src_dict)
        number = d.pop("number", UNSET)

        name = d.pop("name", UNSET)

        _start_time = d.pop("startTime", UNSET)
        start_time: Union[Unset, datetime.datetime]
        if isinstance(_start_time, Unset):
            start_time = UNSET
        else:
            start_time = isoparse(_start_time)

        _end_time = d.pop("endTime", UNSET)
        end_time: Union[Unset, datetime.datetime]
        if isinstance(_end_time, Unset):
            end_time = UNSET
        else:
            end_time = isoparse(_end_time)

        is_daytime = d.pop("isDaytime", UNSET)

        def _parse_temperature(data: object) -> Union["QuantitativeValue", Unset, int]:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                temperature_type_0 = QuantitativeValue.from_dict(data)

                return temperature_type_0
            except:  # noqa: E722
                pass
            return cast(Union["QuantitativeValue", Unset, int], data)

        temperature = _parse_temperature(d.pop("temperature", UNSET))

        _temperature_unit = d.pop("temperatureUnit", UNSET)
        temperature_unit: Union[Unset, GridpointForecastPeriodTemperatureUnit]
        if isinstance(_temperature_unit, Unset):
            temperature_unit = UNSET
        else:
            temperature_unit = GridpointForecastPeriodTemperatureUnit(_temperature_unit)

        _temperature_trend = d.pop("temperatureTrend", UNSET)
        temperature_trend: Union[Unset, GridpointForecastPeriodTemperatureTrend]
        if isinstance(_temperature_trend, Unset):
            temperature_trend = UNSET
        else:
            temperature_trend = GridpointForecastPeriodTemperatureTrend(_temperature_trend)

        _probability_of_precipitation = d.pop("probabilityOfPrecipitation", UNSET)
        probability_of_precipitation: Union[Unset, QuantitativeValue]
        if isinstance(_probability_of_precipitation, Unset):
            probability_of_precipitation = UNSET
        else:
            probability_of_precipitation = QuantitativeValue.from_dict(
                _probability_of_precipitation
            )

        _dewpoint = d.pop("dewpoint", UNSET)
        dewpoint: Union[Unset, QuantitativeValue]
        if isinstance(_dewpoint, Unset):
            dewpoint = UNSET
        else:
            dewpoint = QuantitativeValue.from_dict(_dewpoint)

        _relative_humidity = d.pop("relativeHumidity", UNSET)
        relative_humidity: Union[Unset, QuantitativeValue]
        if isinstance(_relative_humidity, Unset):
            relative_humidity = UNSET
        else:
            relative_humidity = QuantitativeValue.from_dict(_relative_humidity)

        def _parse_wind_speed(data: object) -> Union["QuantitativeValue", Unset, str]:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                wind_speed_type_0 = QuantitativeValue.from_dict(data)

                return wind_speed_type_0
            except:  # noqa: E722
                pass
            return cast(Union["QuantitativeValue", Unset, str], data)

        wind_speed = _parse_wind_speed(d.pop("windSpeed", UNSET))

        def _parse_wind_gust(data: object) -> Union["QuantitativeValue", None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                wind_gust_type_0 = QuantitativeValue.from_dict(data)

                return wind_gust_type_0
            except:  # noqa: E722
                pass
            return cast(Union["QuantitativeValue", None, Unset, str], data)

        wind_gust = _parse_wind_gust(d.pop("windGust", UNSET))

        _wind_direction = d.pop("windDirection", UNSET)
        wind_direction: Union[Unset, GridpointForecastPeriodWindDirection]
        if isinstance(_wind_direction, Unset):
            wind_direction = UNSET
        else:
            wind_direction = GridpointForecastPeriodWindDirection(_wind_direction)

        icon = d.pop("icon", UNSET)

        short_forecast = d.pop("shortForecast", UNSET)

        detailed_forecast = d.pop("detailedForecast", UNSET)

        gridpoint_forecast_period = cls(
            number=number,
            name=name,
            start_time=start_time,
            end_time=end_time,
            is_daytime=is_daytime,
            temperature=temperature,
            temperature_unit=temperature_unit,
            temperature_trend=temperature_trend,
            probability_of_precipitation=probability_of_precipitation,
            dewpoint=dewpoint,
            relative_humidity=relative_humidity,
            wind_speed=wind_speed,
            wind_gust=wind_gust,
            wind_direction=wind_direction,
            icon=icon,
            short_forecast=short_forecast,
            detailed_forecast=detailed_forecast,
        )

        return gridpoint_forecast_period
