from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ArchiveDailyUnits")


@_attrs_define
class ArchiveDailyUnits:
    """
    Attributes:
        time (Union[Unset, str]):
        weather_code (Union[Unset, str]):
        temperature_2m_max (Union[Unset, str]):
        temperature_2m_min (Union[Unset, str]):
        temperature_2m_mean (Union[Unset, str]):
        wind_speed_10m_max (Union[Unset, str]):
        wind_direction_10m_dominant (Union[Unset, str]):
    """

    time: Union[Unset, str] = UNSET
    weather_code: Union[Unset, str] = UNSET
    temperature_2m_max: Union[Unset, str] = UNSET
    temperature_2m_min: Union[Unset, str] = UNSET
    temperature_2m_mean: Union[Unset, str] = UNSET
    wind_speed_10m_max: Union[Unset, str] = UNSET
    wind_direction_10m_dominant: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        time = self.time

        weather_code = self.weather_code

        temperature_2m_max = self.temperature_2m_max

        temperature_2m_min = self.temperature_2m_min

        temperature_2m_mean = self.temperature_2m_mean

        wind_speed_10m_max = self.wind_speed_10m_max

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
        time = d.pop("time", UNSET)

        weather_code = d.pop("weather_code", UNSET)

        temperature_2m_max = d.pop("temperature_2m_max", UNSET)

        temperature_2m_min = d.pop("temperature_2m_min", UNSET)

        temperature_2m_mean = d.pop("temperature_2m_mean", UNSET)

        wind_speed_10m_max = d.pop("wind_speed_10m_max", UNSET)

        wind_direction_10m_dominant = d.pop("wind_direction_10m_dominant", UNSET)

        archive_daily_units = cls(
            time=time,
            weather_code=weather_code,
            temperature_2m_max=temperature_2m_max,
            temperature_2m_min=temperature_2m_min,
            temperature_2m_mean=temperature_2m_mean,
            wind_speed_10m_max=wind_speed_10m_max,
            wind_direction_10m_dominant=wind_direction_10m_dominant,
        )

        archive_daily_units.additional_properties = d
        return archive_daily_units

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
