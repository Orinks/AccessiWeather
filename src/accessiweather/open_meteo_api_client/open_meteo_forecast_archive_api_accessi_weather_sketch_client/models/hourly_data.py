import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="HourlyData")


@_attrs_define
class HourlyData:
    """
    Attributes:
        time (Union[Unset, list[datetime.datetime]]):
        temperature_2m (Union[Unset, list[float]]):
        weather_code (Union[Unset, list[int]]):
        wind_speed_10m (Union[Unset, list[float]]):
        wind_direction_10m (Union[Unset, list[float]]):
        pressure_msl (Union[Unset, list[float]]):
        surface_pressure (Union[Unset, list[float]]):
        relative_humidity_2m (Union[Unset, list[float]]):
        apparent_temperature (Union[Unset, list[float]]):
        precipitation (Union[Unset, list[float]]):
        precipitation_probability (Union[Unset, list[float]]):
        cloud_cover (Union[Unset, list[float]]):
        wind_gusts_10m (Union[Unset, list[float]]):
        is_day (Union[Unset, list[int]]):
    """

    time: Union[Unset, list[datetime.datetime]] = UNSET
    temperature_2m: Union[Unset, list[float]] = UNSET
    weather_code: Union[Unset, list[int]] = UNSET
    wind_speed_10m: Union[Unset, list[float]] = UNSET
    wind_direction_10m: Union[Unset, list[float]] = UNSET
    pressure_msl: Union[Unset, list[float]] = UNSET
    surface_pressure: Union[Unset, list[float]] = UNSET
    relative_humidity_2m: Union[Unset, list[float]] = UNSET
    apparent_temperature: Union[Unset, list[float]] = UNSET
    precipitation: Union[Unset, list[float]] = UNSET
    precipitation_probability: Union[Unset, list[float]] = UNSET
    cloud_cover: Union[Unset, list[float]] = UNSET
    wind_gusts_10m: Union[Unset, list[float]] = UNSET
    is_day: Union[Unset, list[int]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        time: Union[Unset, list[str]] = UNSET
        if not isinstance(self.time, Unset):
            time = []
            for time_item_data in self.time:
                time_item = time_item_data.isoformat()
                time.append(time_item)

        temperature_2m: Union[Unset, list[float]] = UNSET
        if not isinstance(self.temperature_2m, Unset):
            temperature_2m = self.temperature_2m

        weather_code: Union[Unset, list[int]] = UNSET
        if not isinstance(self.weather_code, Unset):
            weather_code = self.weather_code

        wind_speed_10m: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_speed_10m, Unset):
            wind_speed_10m = self.wind_speed_10m

        wind_direction_10m: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_direction_10m, Unset):
            wind_direction_10m = self.wind_direction_10m

        pressure_msl: Union[Unset, list[float]] = UNSET
        if not isinstance(self.pressure_msl, Unset):
            pressure_msl = self.pressure_msl

        surface_pressure: Union[Unset, list[float]] = UNSET
        if not isinstance(self.surface_pressure, Unset):
            surface_pressure = self.surface_pressure

        relative_humidity_2m: Union[Unset, list[float]] = UNSET
        if not isinstance(self.relative_humidity_2m, Unset):
            relative_humidity_2m = self.relative_humidity_2m

        apparent_temperature: Union[Unset, list[float]] = UNSET
        if not isinstance(self.apparent_temperature, Unset):
            apparent_temperature = self.apparent_temperature

        precipitation: Union[Unset, list[float]] = UNSET
        if not isinstance(self.precipitation, Unset):
            precipitation = self.precipitation

        precipitation_probability: Union[Unset, list[float]] = UNSET
        if not isinstance(self.precipitation_probability, Unset):
            precipitation_probability = self.precipitation_probability

        cloud_cover: Union[Unset, list[float]] = UNSET
        if not isinstance(self.cloud_cover, Unset):
            cloud_cover = self.cloud_cover

        wind_gusts_10m: Union[Unset, list[float]] = UNSET
        if not isinstance(self.wind_gusts_10m, Unset):
            wind_gusts_10m = self.wind_gusts_10m

        is_day: Union[Unset, list[int]] = UNSET
        if not isinstance(self.is_day, Unset):
            is_day = self.is_day

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
        if surface_pressure is not UNSET:
            field_dict["surface_pressure"] = surface_pressure
        if relative_humidity_2m is not UNSET:
            field_dict["relative_humidity_2m"] = relative_humidity_2m
        if apparent_temperature is not UNSET:
            field_dict["apparent_temperature"] = apparent_temperature
        if precipitation is not UNSET:
            field_dict["precipitation"] = precipitation
        if precipitation_probability is not UNSET:
            field_dict["precipitation_probability"] = precipitation_probability
        if cloud_cover is not UNSET:
            field_dict["cloud_cover"] = cloud_cover
        if wind_gusts_10m is not UNSET:
            field_dict["wind_gusts_10m"] = wind_gusts_10m
        if is_day is not UNSET:
            field_dict["is_day"] = is_day

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        time = []
        _time = d.pop("time", UNSET)
        for time_item_data in _time or []:
            time_item = isoparse(time_item_data)

            time.append(time_item)

        temperature_2m = cast(list[float], d.pop("temperature_2m", UNSET))

        weather_code = cast(list[int], d.pop("weather_code", UNSET))

        wind_speed_10m = cast(list[float], d.pop("wind_speed_10m", UNSET))

        wind_direction_10m = cast(list[float], d.pop("wind_direction_10m", UNSET))

        pressure_msl = cast(list[float], d.pop("pressure_msl", UNSET))

        surface_pressure = cast(list[float], d.pop("surface_pressure", UNSET))

        relative_humidity_2m = cast(list[float], d.pop("relative_humidity_2m", UNSET))

        apparent_temperature = cast(list[float], d.pop("apparent_temperature", UNSET))

        precipitation = cast(list[float], d.pop("precipitation", UNSET))

        precipitation_probability = cast(list[float], d.pop("precipitation_probability", UNSET))

        cloud_cover = cast(list[float], d.pop("cloud_cover", UNSET))

        wind_gusts_10m = cast(list[float], d.pop("wind_gusts_10m", UNSET))

        is_day = cast(list[int], d.pop("is_day", UNSET))

        hourly_data = cls(
            time=time,
            temperature_2m=temperature_2m,
            weather_code=weather_code,
            wind_speed_10m=wind_speed_10m,
            wind_direction_10m=wind_direction_10m,
            pressure_msl=pressure_msl,
            surface_pressure=surface_pressure,
            relative_humidity_2m=relative_humidity_2m,
            apparent_temperature=apparent_temperature,
            precipitation=precipitation,
            precipitation_probability=precipitation_probability,
            cloud_cover=cloud_cover,
            wind_gusts_10m=wind_gusts_10m,
            is_day=is_day,
        )

        hourly_data.additional_properties = d
        return hourly_data

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
