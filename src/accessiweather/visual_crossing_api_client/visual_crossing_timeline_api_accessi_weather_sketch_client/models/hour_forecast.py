from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="HourForecast")


@_attrs_define
class HourForecast:
    """
    Attributes:
        datetime_ (Union[Unset, str]): ISO 8601 timestamp for the hour.
        temp (Union[Unset, float]):
        humidity (Union[Unset, float]):
        precipprob (Union[Unset, float]):
        windspeed (Union[Unset, float]):
        winddir (Union[Unset, float]):
        pressure (Union[Unset, float]):
        conditions (Union[Unset, str]):
        icon (Union[Unset, str]):
    """

    datetime_: Union[Unset, str] = UNSET
    temp: Union[Unset, float] = UNSET
    humidity: Union[Unset, float] = UNSET
    precipprob: Union[Unset, float] = UNSET
    windspeed: Union[Unset, float] = UNSET
    winddir: Union[Unset, float] = UNSET
    pressure: Union[Unset, float] = UNSET
    conditions: Union[Unset, str] = UNSET
    icon: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        datetime_ = self.datetime_

        temp = self.temp

        humidity = self.humidity

        precipprob = self.precipprob

        windspeed = self.windspeed

        winddir = self.winddir

        pressure = self.pressure

        conditions = self.conditions

        icon = self.icon

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if datetime_ is not UNSET:
            field_dict["datetime"] = datetime_
        if temp is not UNSET:
            field_dict["temp"] = temp
        if humidity is not UNSET:
            field_dict["humidity"] = humidity
        if precipprob is not UNSET:
            field_dict["precipprob"] = precipprob
        if windspeed is not UNSET:
            field_dict["windspeed"] = windspeed
        if winddir is not UNSET:
            field_dict["winddir"] = winddir
        if pressure is not UNSET:
            field_dict["pressure"] = pressure
        if conditions is not UNSET:
            field_dict["conditions"] = conditions
        if icon is not UNSET:
            field_dict["icon"] = icon

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        datetime_ = d.pop("datetime", UNSET)

        temp = d.pop("temp", UNSET)

        humidity = d.pop("humidity", UNSET)

        precipprob = d.pop("precipprob", UNSET)

        windspeed = d.pop("windspeed", UNSET)

        winddir = d.pop("winddir", UNSET)

        pressure = d.pop("pressure", UNSET)

        conditions = d.pop("conditions", UNSET)

        icon = d.pop("icon", UNSET)

        hour_forecast = cls(
            datetime_=datetime_,
            temp=temp,
            humidity=humidity,
            precipprob=precipprob,
            windspeed=windspeed,
            winddir=winddir,
            pressure=pressure,
            conditions=conditions,
            icon=icon,
        )

        hour_forecast.additional_properties = d
        return hour_forecast

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
