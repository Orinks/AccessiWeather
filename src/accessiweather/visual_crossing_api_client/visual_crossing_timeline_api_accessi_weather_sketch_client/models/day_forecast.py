from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="DayForecast")


@_attrs_define
class DayForecast:
    """
    Attributes:
        datetime_ (Union[Unset, str]): Date for the forecast period (YYYY-MM-DD).
        tempmax (Union[Unset, float]):
        tempmin (Union[Unset, float]):
        temp (Union[Unset, float]):
        humidity (Union[Unset, float]):
        precipprob (Union[Unset, float]):
        preciptype (Union[Unset, list[str]]):
        windspeed (Union[Unset, float]):
        winddir (Union[Unset, float]):
        description (Union[Unset, str]):
        conditions (Union[Unset, str]):
        icon (Union[Unset, str]):
    """

    datetime_: Union[Unset, str] = UNSET
    tempmax: Union[Unset, float] = UNSET
    tempmin: Union[Unset, float] = UNSET
    temp: Union[Unset, float] = UNSET
    humidity: Union[Unset, float] = UNSET
    precipprob: Union[Unset, float] = UNSET
    preciptype: Union[Unset, list[str]] = UNSET
    windspeed: Union[Unset, float] = UNSET
    winddir: Union[Unset, float] = UNSET
    description: Union[Unset, str] = UNSET
    conditions: Union[Unset, str] = UNSET
    icon: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        datetime_ = self.datetime_

        tempmax = self.tempmax

        tempmin = self.tempmin

        temp = self.temp

        humidity = self.humidity

        precipprob = self.precipprob

        preciptype: Union[Unset, list[str]] = UNSET
        if not isinstance(self.preciptype, Unset):
            preciptype = self.preciptype

        windspeed = self.windspeed

        winddir = self.winddir

        description = self.description

        conditions = self.conditions

        icon = self.icon

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if datetime_ is not UNSET:
            field_dict["datetime"] = datetime_
        if tempmax is not UNSET:
            field_dict["tempmax"] = tempmax
        if tempmin is not UNSET:
            field_dict["tempmin"] = tempmin
        if temp is not UNSET:
            field_dict["temp"] = temp
        if humidity is not UNSET:
            field_dict["humidity"] = humidity
        if precipprob is not UNSET:
            field_dict["precipprob"] = precipprob
        if preciptype is not UNSET:
            field_dict["preciptype"] = preciptype
        if windspeed is not UNSET:
            field_dict["windspeed"] = windspeed
        if winddir is not UNSET:
            field_dict["winddir"] = winddir
        if description is not UNSET:
            field_dict["description"] = description
        if conditions is not UNSET:
            field_dict["conditions"] = conditions
        if icon is not UNSET:
            field_dict["icon"] = icon

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        datetime_ = d.pop("datetime", UNSET)

        tempmax = d.pop("tempmax", UNSET)

        tempmin = d.pop("tempmin", UNSET)

        temp = d.pop("temp", UNSET)

        humidity = d.pop("humidity", UNSET)

        precipprob = d.pop("precipprob", UNSET)

        preciptype = cast(list[str], d.pop("preciptype", UNSET))

        windspeed = d.pop("windspeed", UNSET)

        winddir = d.pop("winddir", UNSET)

        description = d.pop("description", UNSET)

        conditions = d.pop("conditions", UNSET)

        icon = d.pop("icon", UNSET)

        day_forecast = cls(
            datetime_=datetime_,
            tempmax=tempmax,
            tempmin=tempmin,
            temp=temp,
            humidity=humidity,
            precipprob=precipprob,
            preciptype=preciptype,
            windspeed=windspeed,
            winddir=winddir,
            description=description,
            conditions=conditions,
            icon=icon,
        )

        day_forecast.additional_properties = d
        return day_forecast

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
