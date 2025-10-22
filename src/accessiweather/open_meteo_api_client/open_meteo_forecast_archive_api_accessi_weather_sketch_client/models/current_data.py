import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="CurrentData")


@_attrs_define
class CurrentData:
    """
    Attributes:
        time (Union[Unset, datetime.datetime]):
        interval (Union[Unset, int]):
        temperature_2m (Union[Unset, float]):
        relative_humidity_2m (Union[Unset, float]):
        apparent_temperature (Union[Unset, float]):
        is_day (Union[Unset, int]):
        precipitation (Union[Unset, float]):
        weather_code (Union[Unset, int]):
        cloud_cover (Union[Unset, float]):
        pressure_msl (Union[Unset, float]):
        surface_pressure (Union[Unset, float]):
        wind_speed_10m (Union[Unset, float]):
        wind_direction_10m (Union[Unset, float]):
        wind_gusts_10m (Union[Unset, float]):
    """

    time: Union[Unset, datetime.datetime] = UNSET
    interval: Union[Unset, int] = UNSET
    temperature_2m: Union[Unset, float] = UNSET
    relative_humidity_2m: Union[Unset, float] = UNSET
    apparent_temperature: Union[Unset, float] = UNSET
    is_day: Union[Unset, int] = UNSET
    precipitation: Union[Unset, float] = UNSET
    weather_code: Union[Unset, int] = UNSET
    cloud_cover: Union[Unset, float] = UNSET
    pressure_msl: Union[Unset, float] = UNSET
    surface_pressure: Union[Unset, float] = UNSET
    wind_speed_10m: Union[Unset, float] = UNSET
    wind_direction_10m: Union[Unset, float] = UNSET
    wind_gusts_10m: Union[Unset, float] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        time: Union[Unset, str] = UNSET
        if not isinstance(self.time, Unset):
            time = self.time.isoformat()

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
        _time = d.pop("time", UNSET)
        time: Union[Unset, datetime.datetime]
        if isinstance(_time, Unset):
            time = UNSET
        else:
            time = isoparse(_time)

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

        current_data = cls(
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

        current_data.additional_properties = d
        return current_data

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
