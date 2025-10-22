from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="DailyUnits")


@_attrs_define
class DailyUnits:
    """
    Attributes:
        time (Union[Unset, str]):
        temperature_2m_max (Union[Unset, str]):
        temperature_2m_min (Union[Unset, str]):
        temperature_2m_mean (Union[Unset, str]):
        uv_index_max (Union[Unset, str]):
        sunrise (Union[Unset, str]):
        sunset (Union[Unset, str]):
        wind_speed_10m_max (Union[Unset, str]):
        wind_direction_10m_dominant (Union[Unset, str]):
        weather_code (Union[Unset, str]):
        apparent_temperature_max (Union[Unset, str]):
        apparent_temperature_min (Union[Unset, str]):
        precipitation_sum (Union[Unset, str]):
        precipitation_probability_max (Union[Unset, str]):
        wind_gusts_10m_max (Union[Unset, str]):
    """

    time: Union[Unset, str] = UNSET
    temperature_2m_max: Union[Unset, str] = UNSET
    temperature_2m_min: Union[Unset, str] = UNSET
    temperature_2m_mean: Union[Unset, str] = UNSET
    uv_index_max: Union[Unset, str] = UNSET
    sunrise: Union[Unset, str] = UNSET
    sunset: Union[Unset, str] = UNSET
    wind_speed_10m_max: Union[Unset, str] = UNSET
    wind_direction_10m_dominant: Union[Unset, str] = UNSET
    weather_code: Union[Unset, str] = UNSET
    apparent_temperature_max: Union[Unset, str] = UNSET
    apparent_temperature_min: Union[Unset, str] = UNSET
    precipitation_sum: Union[Unset, str] = UNSET
    precipitation_probability_max: Union[Unset, str] = UNSET
    wind_gusts_10m_max: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        time = self.time

        temperature_2m_max = self.temperature_2m_max

        temperature_2m_min = self.temperature_2m_min

        temperature_2m_mean = self.temperature_2m_mean

        uv_index_max = self.uv_index_max

        sunrise = self.sunrise

        sunset = self.sunset

        wind_speed_10m_max = self.wind_speed_10m_max

        wind_direction_10m_dominant = self.wind_direction_10m_dominant

        weather_code = self.weather_code

        apparent_temperature_max = self.apparent_temperature_max

        apparent_temperature_min = self.apparent_temperature_min

        precipitation_sum = self.precipitation_sum

        precipitation_probability_max = self.precipitation_probability_max

        wind_gusts_10m_max = self.wind_gusts_10m_max

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if time is not UNSET:
            field_dict["time"] = time
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
        if weather_code is not UNSET:
            field_dict["weather_code"] = weather_code
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
        time = d.pop("time", UNSET)

        temperature_2m_max = d.pop("temperature_2m_max", UNSET)

        temperature_2m_min = d.pop("temperature_2m_min", UNSET)

        temperature_2m_mean = d.pop("temperature_2m_mean", UNSET)

        uv_index_max = d.pop("uv_index_max", UNSET)

        sunrise = d.pop("sunrise", UNSET)

        sunset = d.pop("sunset", UNSET)

        wind_speed_10m_max = d.pop("wind_speed_10m_max", UNSET)

        wind_direction_10m_dominant = d.pop("wind_direction_10m_dominant", UNSET)

        weather_code = d.pop("weather_code", UNSET)

        apparent_temperature_max = d.pop("apparent_temperature_max", UNSET)

        apparent_temperature_min = d.pop("apparent_temperature_min", UNSET)

        precipitation_sum = d.pop("precipitation_sum", UNSET)

        precipitation_probability_max = d.pop("precipitation_probability_max", UNSET)

        wind_gusts_10m_max = d.pop("wind_gusts_10m_max", UNSET)

        daily_units = cls(
            time=time,
            temperature_2m_max=temperature_2m_max,
            temperature_2m_min=temperature_2m_min,
            temperature_2m_mean=temperature_2m_mean,
            uv_index_max=uv_index_max,
            sunrise=sunrise,
            sunset=sunset,
            wind_speed_10m_max=wind_speed_10m_max,
            wind_direction_10m_dominant=wind_direction_10m_dominant,
            weather_code=weather_code,
            apparent_temperature_max=apparent_temperature_max,
            apparent_temperature_min=apparent_temperature_min,
            precipitation_sum=precipitation_sum,
            precipitation_probability_max=precipitation_probability_max,
            wind_gusts_10m_max=wind_gusts_10m_max,
        )

        daily_units.additional_properties = d
        return daily_units

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
