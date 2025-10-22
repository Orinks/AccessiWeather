import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="ArchiveDailyData")


@_attrs_define
class ArchiveDailyData:
    """
    Attributes:
        time (Union[Unset, list[datetime.date]]):
        weather_code (Union[Unset, list[int]]):
        temperature_2m_max (Union[Unset, list[float]]):
        temperature_2m_min (Union[Unset, list[float]]):
        temperature_2m_mean (Union[Unset, list[float]]):
        wind_speed_10m_max (Union[Unset, list[float]]):
        wind_direction_10m_dominant (Union[Unset, list[float]]):
    """

    time: Union[Unset, list[datetime.date]] = UNSET
    weather_code: Union[Unset, list[int]] = UNSET
    temperature_2m_max: Union[Unset, list[float]] = UNSET
    temperature_2m_min: Union[Unset, list[float]] = UNSET
    temperature_2m_mean: Union[Unset, list[float]] = UNSET
    wind_speed_10m_max: Union[Unset, list[float]] = UNSET
    wind_direction_10m_dominant: Union[Unset, list[float]] = UNSET
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

        wind_speed_10m_max: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_speed_10m_max, Unset):
            wind_speed_10m_max = self.wind_speed_10m_max

        wind_direction_10m_dominant: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_direction_10m_dominant, Unset):
            wind_direction_10m_dominant = self.wind_direction_10m_dominant

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
        if wind_speed_10m_max is not UNSET:
            field_dict["wind_speed_10m_max"] = wind_speed_10m_max
        if wind_direction_10m_dominant is not UNSET:
            field_dict["wind_direction_10m_dominant"] = wind_direction_10m_dominant

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

        wind_speed_10m_max = cast(list[float], d.pop("wind_speed_10m_max", UNSET))

        wind_direction_10m_dominant = cast(list[float], d.pop("wind_direction_10m_dominant", UNSET))

        archive_daily_data = cls(
            time=time,
            weather_code=weather_code,
            temperature_2m_max=temperature_2m_max,
            temperature_2m_min=temperature_2m_min,
            temperature_2m_mean=temperature_2m_mean,
            wind_speed_10m_max=wind_speed_10m_max,
            wind_direction_10m_dominant=wind_direction_10m_dominant,
        )

        archive_daily_data.additional_properties = d
        return archive_daily_data

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
