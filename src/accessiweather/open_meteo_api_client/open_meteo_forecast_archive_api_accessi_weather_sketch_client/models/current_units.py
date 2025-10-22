from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CurrentUnits")


@_attrs_define
class CurrentUnits:
    """
    Attributes:
        time (Union[Unset, str]):
        interval (Union[Unset, str]):
        temperature_2m (Union[Unset, str]):
        relative_humidity_2m (Union[Unset, str]):
        apparent_temperature (Union[Unset, str]):
        is_day (Union[Unset, str]):
        precipitation (Union[Unset, str]):
        weather_code (Union[Unset, str]):
        cloud_cover (Union[Unset, str]):
        pressure_msl (Union[Unset, str]):
        surface_pressure (Union[Unset, str]):
        wind_speed_10m (Union[Unset, str]):
        wind_direction_10m (Union[Unset, str]):
        wind_gusts_10m (Union[Unset, str]):
    """

    time: Union[Unset, str] = UNSET
    interval: Union[Unset, str] = UNSET
    temperature_2m: Union[Unset, str] = UNSET
    relative_humidity_2m: Union[Unset, str] = UNSET
    apparent_temperature: Union[Unset, str] = UNSET
    is_day: Union[Unset, str] = UNSET
    precipitation: Union[Unset, str] = UNSET
    weather_code: Union[Unset, str] = UNSET
    cloud_cover: Union[Unset, str] = UNSET
    pressure_msl: Union[Unset, str] = UNSET
    surface_pressure: Union[Unset, str] = UNSET
    wind_speed_10m: Union[Unset, str] = UNSET
    wind_direction_10m: Union[Unset, str] = UNSET
    wind_gusts_10m: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        time = self.time

        interval = self.interval

        temperature_2m = self.temperature_2m

        relative_humidity_2m = self.relative_humidity_2m

        apparent_temperature = self.apparent_temperature

        is_day = self.is_day

        precipitation = self.precipitation

        weather_code = self.weather_code

        cloud_cover = self.cloud_cover

        pressure_msl = self.pressure_msl

        surface_pressure = self.surface_pressure

        wind_speed_10m = self.wind_speed_10m

        wind_direction_10m = self.wind_direction_10m

        wind_gusts_10m = self.wind_gusts_10m

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if time is not UNSET:
            field_dict["time"] = time
        if interval is not UNSET:
            field_dict["interval"] = interval
        if temperature_2m is not UNSET:
            field_dict["temperature_2m"] = temperature_2m
        if relative_humidity_2m is not UNSET:
            field_dict["relative_humidity_2m"] = relative_humidity_2m
        if apparent_temperature is not UNSET:
            field_dict["apparent_temperature"] = apparent_temperature
        if is_day is not UNSET:
            field_dict["is_day"] = is_day
        if precipitation is not UNSET:
            field_dict["precipitation"] = precipitation
        if weather_code is not UNSET:
            field_dict["weather_code"] = weather_code
        if cloud_cover is not UNSET:
            field_dict["cloud_cover"] = cloud_cover
        if pressure_msl is not UNSET:
            field_dict["pressure_msl"] = pressure_msl
        if surface_pressure is not UNSET:
            field_dict["surface_pressure"] = surface_pressure
        if wind_speed_10m is not UNSET:
            field_dict["wind_speed_10m"] = wind_speed_10m
        if wind_direction_10m is not UNSET:
            field_dict["wind_direction_10m"] = wind_direction_10m
        if wind_gusts_10m is not UNSET:
            field_dict["wind_gusts_10m"] = wind_gusts_10m

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        time = d.pop("time", UNSET)

        interval = d.pop("interval", UNSET)

        temperature_2m = d.pop("temperature_2m", UNSET)

        relative_humidity_2m = d.pop("relative_humidity_2m", UNSET)

        apparent_temperature = d.pop("apparent_temperature", UNSET)

        is_day = d.pop("is_day", UNSET)

        precipitation = d.pop("precipitation", UNSET)

        weather_code = d.pop("weather_code", UNSET)

        cloud_cover = d.pop("cloud_cover", UNSET)

        pressure_msl = d.pop("pressure_msl", UNSET)

        surface_pressure = d.pop("surface_pressure", UNSET)

        wind_speed_10m = d.pop("wind_speed_10m", UNSET)

        wind_direction_10m = d.pop("wind_direction_10m", UNSET)

        wind_gusts_10m = d.pop("wind_gusts_10m", UNSET)

        current_units = cls(
            time=time,
            interval=interval,
            temperature_2m=temperature_2m,
            relative_humidity_2m=relative_humidity_2m,
            apparent_temperature=apparent_temperature,
            is_day=is_day,
            precipitation=precipitation,
            weather_code=weather_code,
            cloud_cover=cloud_cover,
            pressure_msl=pressure_msl,
            surface_pressure=surface_pressure,
            wind_speed_10m=wind_speed_10m,
            wind_direction_10m=wind_direction_10m,
            wind_gusts_10m=wind_gusts_10m,
        )

        current_units.additional_properties = d
        return current_units

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
