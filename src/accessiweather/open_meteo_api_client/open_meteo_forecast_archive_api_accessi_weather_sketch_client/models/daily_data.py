import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="DailyData")


@_attrs_define
class DailyData:
    """
    Attributes:
        time (Union[Unset, list[datetime.date]]):
        weather_code (Union[Unset, list[int]]):
        temperature_2m_max (Union[Unset, list[float]]):
        temperature_2m_min (Union[Unset, list[float]]):
        temperature_2m_mean (Union[Unset, list[float]]):
        uv_index_max (Union[Unset, list[float]]):
        sunrise (Union[Unset, list[datetime.datetime]]):
        sunset (Union[Unset, list[datetime.datetime]]):
        wind_speed_10m_max (Union[Unset, list[float]]):
        wind_direction_10m_dominant (Union[Unset, list[float]]):
        apparent_temperature_max (Union[Unset, list[float]]):
        apparent_temperature_min (Union[Unset, list[float]]):
        precipitation_sum (Union[Unset, list[float]]):
        precipitation_probability_max (Union[Unset, list[float]]):
        wind_gusts_10m_max (Union[Unset, list[float]]):
    """

    time: Union[Unset, list[datetime.date]] = UNSET
    weather_code: Union[Unset, list[int]] = UNSET
    temperature_2m_max: Union[Unset, list[float]] = UNSET
    temperature_2m_min: Union[Unset, list[float]] = UNSET
    temperature_2m_mean: Union[Unset, list[float]] = UNSET
    uv_index_max: Union[Unset, list[float]] = UNSET
    sunrise: Union[Unset, list[datetime.datetime]] = UNSET
    sunset: Union[Unset, list[datetime.datetime]] = UNSET
    wind_speed_10m_max: Union[Unset, list[float]] = UNSET
    wind_direction_10m_dominant: Union[Unset, list[float]] = UNSET
    apparent_temperature_max: Union[Unset, list[float]] = UNSET
    apparent_temperature_min: Union[Unset, list[float]] = UNSET
    precipitation_sum: Union[Unset, list[float]] = UNSET
    precipitation_probability_max: Union[Unset, list[float]] = UNSET
    wind_gusts_10m_max: Union[Unset, list[float]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        time: Union[Unset, list[str]] = UNSET
        if not isinstance(self.time, Unset):
            time = []
            for time_item_data in self.time:
                time_item = time_item_data.isoformat()
                time.append(time_item)

        weather_code: Union[Unset, list[int]] = UNSET
        if not isinstance(self.weather_code, Unset):
            weather_code = self.weather_code

        temperature_2m_max: Union[Unset, list[float]] = UNSET
        if not isinstance(self.temperature_2m_max, Unset):
            temperature_2m_max = self.temperature_2m_max

        temperature_2m_min: Union[Unset, list[float]] = UNSET
        if not isinstance(self.temperature_2m_min, Unset):
            temperature_2m_min = self.temperature_2m_min

        temperature_2m_mean: Union[Unset, list[float]] = UNSET
        if not isinstance(self.temperature_2m_mean, Unset):
            temperature_2m_mean = self.temperature_2m_mean

        uv_index_max: Union[Unset, list[float]] = UNSET
        if not isinstance(self.uv_index_max, Unset):
            uv_index_max = self.uv_index_max

        sunrise: Union[Unset, list[str]] = UNSET
        if not isinstance(self.sunrise, Unset):
            sunrise = []
            for sunrise_item_data in self.sunrise:
                sunrise_item = sunrise_item_data.isoformat()
                sunrise.append(sunrise_item)

        sunset: Union[Unset, list[str]] = UNSET
        if not isinstance(self.sunset, Unset):
            sunset = []
            for sunset_item_data in self.sunset:
                sunset_item = sunset_item_data.isoformat()
                sunset.append(sunset_item)

        wind_speed_10m_max: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_speed_10m_max, Unset):
            wind_speed_10m_max = self.wind_speed_10m_max

        wind_direction_10m_dominant: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_direction_10m_dominant, Unset):
            wind_direction_10m_dominant = self.wind_direction_10m_dominant

        apparent_temperature_max: Union[Unset, list[float]] = UNSET
        if not isinstance(self.apparent_temperature_max, Unset):
            apparent_temperature_max = self.apparent_temperature_max

        apparent_temperature_min: Union[Unset, list[float]] = UNSET
        if not isinstance(self.apparent_temperature_min, Unset):
            apparent_temperature_min = self.apparent_temperature_min

        precipitation_sum: Union[Unset, list[float]] = UNSET
        if not isinstance(self.precipitation_sum, Unset):
            precipitation_sum = self.precipitation_sum

        precipitation_probability_max: Union[Unset, list[float]] = UNSET
        if not isinstance(self.precipitation_probability_max, Unset):
            precipitation_probability_max = self.precipitation_probability_max

        wind_gusts_10m_max: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_gusts_10m_max, Unset):
            wind_gusts_10m_max = self.wind_gusts_10m_max

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if time is not UNSET:
            field_dict["time"] = time
        if weather_code is not UNSET:
            field_dict["weather_code"] = weather_code
        if temperature_2m_max is not UNSET:
            field_dict["temperature_2m_max"] = temperature_2m_max
        if temperature_2m_min is not UNSET:
            field_dict["temperature_2m_min"] = temperature_2m_min
        if temperature_2m_mean is not UNSET:
            field_dict["temperature_2m_mean"] = temperature_2m_mean
        if uv_index_max is not UNSET:
            field_dict["uv_index_max"] = uv_index_max
        if sunrise is not UNSET:
            field_dict["sunrise"] = sunrise
        if sunset is not UNSET:
            field_dict["sunset"] = sunset
        if wind_speed_10m_max is not UNSET:
            field_dict["wind_speed_10m_max"] = wind_speed_10m_max
        if wind_direction_10m_dominant is not UNSET:
            field_dict["wind_direction_10m_dominant"] = wind_direction_10m_dominant
        if apparent_temperature_max is not UNSET:
            field_dict["apparent_temperature_max"] = apparent_temperature_max
        if apparent_temperature_min is not UNSET:
            field_dict["apparent_temperature_min"] = apparent_temperature_min
        if precipitation_sum is not UNSET:
            field_dict["precipitation_sum"] = precipitation_sum
        if precipitation_probability_max is not UNSET:
            field_dict["precipitation_probability_max"] = precipitation_probability_max
        if wind_gusts_10m_max is not UNSET:
            field_dict["wind_gusts_10m_max"] = wind_gusts_10m_max

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        time = []
        _time = d.pop("time", UNSET)
        for time_item_data in _time or []:
            time_item = isoparse(time_item_data).date()

            time.append(time_item)

        weather_code = cast(list[int], d.pop("weather_code", UNSET))

        temperature_2m_max = cast(list[float], d.pop("temperature_2m_max", UNSET))

        temperature_2m_min = cast(list[float], d.pop("temperature_2m_min", UNSET))

        temperature_2m_mean = cast(list[float], d.pop("temperature_2m_mean", UNSET))

        uv_index_max = cast(list[float], d.pop("uv_index_max", UNSET))

        sunrise = []
        _sunrise = d.pop("sunrise", UNSET)
        for sunrise_item_data in _sunrise or []:
            sunrise_item = isoparse(sunrise_item_data)

            sunrise.append(sunrise_item)

        sunset = []
        _sunset = d.pop("sunset", UNSET)
        for sunset_item_data in _sunset or []:
            sunset_item = isoparse(sunset_item_data)

            sunset.append(sunset_item)

        wind_speed_10m_max = cast(list[float], d.pop("wind_speed_10m_max", UNSET))

        wind_direction_10m_dominant = cast(list[float], d.pop("wind_direction_10m_dominant", UNSET))

        apparent_temperature_max = cast(list[float], d.pop("apparent_temperature_max", UNSET))

        apparent_temperature_min = cast(list[float], d.pop("apparent_temperature_min", UNSET))

        precipitation_sum = cast(list[float], d.pop("precipitation_sum", UNSET))

        precipitation_probability_max = cast(list[float], d.pop("precipitation_probability_max", UNSET))

        wind_gusts_10m_max = cast(list[float], d.pop("wind_gusts_10m_max", UNSET))

        daily_data = cls(
            time=time,
            weather_code=weather_code,
            temperature_2m_max=temperature_2m_max,
            temperature_2m_min=temperature_2m_min,
            temperature_2m_mean=temperature_2m_mean,
            uv_index_max=uv_index_max,
            sunrise=sunrise,
            sunset=sunset,
            wind_speed_10m_max=wind_speed_10m_max,
            wind_direction_10m_dominant=wind_direction_10m_dominant,
            apparent_temperature_max=apparent_temperature_max,
            apparent_temperature_min=apparent_temperature_min,
            precipitation_sum=precipitation_sum,
            precipitation_probability_max=precipitation_probability_max,
            wind_gusts_10m_max=wind_gusts_10m_max,
        )

        daily_data.additional_properties = d
        return daily_data

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
