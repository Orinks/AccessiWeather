from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CurrentConditions")


@_attrs_define
class CurrentConditions:
    """
    Attributes:
        datetime_ (Union[Unset, str]): Local timestamp of the observation.
        temp (Union[Unset, float]):
        feelslike (Union[Unset, float]):
        humidity (Union[Unset, float]):
        windspeed (Union[Unset, float]):
        winddir (Union[Unset, float]):
        pressure (Union[Unset, float]):
        conditions (Union[Unset, str]):
        icon (Union[Unset, str]):
    """

    datetime_: Union[Unset, str] = UNSET
    temp: Union[Unset, float] = UNSET
    feelslike: Union[Unset, float] = UNSET
    humidity: Union[Unset, float] = UNSET
    windspeed: Union[Unset, float] = UNSET
    winddir: Union[Unset, float] = UNSET
    pressure: Union[Unset, float] = UNSET
    conditions: Union[Unset, str] = UNSET
    icon: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        datetime_ = self.datetime_

        temp = self.temp

        feelslike = self.feelslike

        humidity = self.humidity

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
        if feelslike is not UNSET:
            field_dict["feelslike"] = feelslike
        if humidity is not UNSET:
            field_dict["humidity"] = humidity
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

        feelslike = d.pop("feelslike", UNSET)

        humidity = d.pop("humidity", UNSET)

        windspeed = d.pop("windspeed", UNSET)

        winddir = d.pop("winddir", UNSET)

        pressure = d.pop("pressure", UNSET)

        conditions = d.pop("conditions", UNSET)

        icon = d.pop("icon", UNSET)

        current_conditions = cls(
            datetime_=datetime_,
            temp=temp,
            feelslike=feelslike,
            humidity=humidity,
            windspeed=windspeed,
            winddir=winddir,
            pressure=pressure,
            conditions=conditions,
            icon=icon,
        )

        current_conditions.additional_properties = d
        return current_conditions

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
