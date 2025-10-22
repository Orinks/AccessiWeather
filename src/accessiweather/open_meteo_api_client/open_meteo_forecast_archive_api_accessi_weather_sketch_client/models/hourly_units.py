from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="HourlyUnits")


@_attrs_define
class HourlyUnits:
    """
    Attributes:
        time (Union[Unset, str]):
        temperature_2m (Union[Unset, str]):
        weather_code (Union[Unset, str]):
        wind_speed_10m (Union[Unset, str]):
        wind_direction_10m (Union[Unset, str]):
        pressure_msl (Union[Unset, str]):
        relative_humidity_2m (Union[Unset, str]):
        apparent_temperature (Union[Unset, str]):
    """

    time: Union[Unset, str] = UNSET
    temperature_2m: Union[Unset, str] = UNSET
    weather_code: Union[Unset, str] = UNSET
    wind_speed_10m: Union[Unset, str] = UNSET
    wind_direction_10m: Union[Unset, str] = UNSET
    pressure_msl: Union[Unset, str] = UNSET
    relative_humidity_2m: Union[Unset, str] = UNSET
    apparent_temperature: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        time = self.time

        temperature_2m = self.temperature_2m

        weather_code = self.weather_code

        wind_speed_10m = self.wind_speed_10m

        wind_direction_10m = self.wind_direction_10m

        pressure_msl = self.pressure_msl

        relative_humidity_2m = self.relative_humidity_2m

        apparent_temperature = self.apparent_temperature

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if time is not UNSET:
            field_dict["time"] = time
        if temperature_2m is not UNSET:
            field_dict["temperature_2m"] = temperature_2m
        if weather_code is not UNSET:
            field_dict["weather_code"] = weather_code
        if wind_speed_10m is not UNSET:
            field_dict["wind_speed_10m"] = wind_speed_10m
        if wind_direction_10m is not UNSET:
            field_dict["wind_direction_10m"] = wind_direction_10m
        if pressure_msl is not UNSET:
            field_dict["pressure_msl"] = pressure_msl
        if relative_humidity_2m is not UNSET:
            field_dict["relative_humidity_2m"] = relative_humidity_2m
        if apparent_temperature is not UNSET:
            field_dict["apparent_temperature"] = apparent_temperature

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        time = d.pop("time", UNSET)

        temperature_2m = d.pop("temperature_2m", UNSET)

        weather_code = d.pop("weather_code", UNSET)

        wind_speed_10m = d.pop("wind_speed_10m", UNSET)

        wind_direction_10m = d.pop("wind_direction_10m", UNSET)

        pressure_msl = d.pop("pressure_msl", UNSET)

        relative_humidity_2m = d.pop("relative_humidity_2m", UNSET)

        apparent_temperature = d.pop("apparent_temperature", UNSET)

        hourly_units = cls(
            time=time,
            temperature_2m=temperature_2m,
            weather_code=weather_code,
            wind_speed_10m=wind_speed_10m,
            wind_direction_10m=wind_direction_10m,
            pressure_msl=pressure_msl,
            relative_humidity_2m=relative_humidity_2m,
            apparent_temperature=apparent_temperature,
        )

        hourly_units.additional_properties = d
        return hourly_units

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
