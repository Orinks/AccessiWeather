from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="HourForecast")


@_attrs_define
class HourForecast:
    """
    Attributes:
        datetime_ (Union[Unset, str]): ISO 8601 timestamp for the hour.
        datetime_epoch (Union[Unset, int]):
        temp (Union[Unset, float]):
        feelslike (Union[Unset, float]):
        dew (Union[Unset, float]):
        humidity (Union[Unset, float]):
        precip (Union[Unset, float]):
        precipprob (Union[Unset, float]):
        preciptype (Union[Unset, list[str]]):
        snow (Union[Unset, float]):
        snowdepth (Union[Unset, float]):
        windgust (Union[Unset, float]):
        windspeed (Union[Unset, float]):
        winddir (Union[Unset, float]):
        pressure (Union[Unset, float]):
        conditions (Union[Unset, str]):
        icon (Union[Unset, str]):
        cloudcover (Union[Unset, float]):
        visibility (Union[Unset, float]):
        solarradiation (Union[Unset, float]):
        solarenergy (Union[Unset, float]):
        uvindex (Union[Unset, float]):
        stations (Union[Unset, list[str]]):
    """

    datetime_: Union[Unset, str] = UNSET
    datetime_epoch: Union[Unset, int] = UNSET
    temp: Union[Unset, float] = UNSET
    feelslike: Union[Unset, float] = UNSET
    dew: Union[Unset, float] = UNSET
    humidity: Union[Unset, float] = UNSET
    precip: Union[Unset, float] = UNSET
    precipprob: Union[Unset, float] = UNSET
    preciptype: Union[Unset, list[str]] = UNSET
    snow: Union[Unset, float] = UNSET
    snowdepth: Union[Unset, float] = UNSET
    windgust: Union[Unset, float] = UNSET
    windspeed: Union[Unset, float] = UNSET
    winddir: Union[Unset, float] = UNSET
    pressure: Union[Unset, float] = UNSET
    conditions: Union[Unset, str] = UNSET
    icon: Union[Unset, str] = UNSET
    cloudcover: Union[Unset, float] = UNSET
    visibility: Union[Unset, float] = UNSET
    solarradiation: Union[Unset, float] = UNSET
    solarenergy: Union[Unset, float] = UNSET
    uvindex: Union[Unset, float] = UNSET
    stations: Union[Unset, list[str]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        datetime_ = self.datetime_

        datetime_epoch = self.datetime_epoch

        temp = self.temp

        feelslike = self.feelslike

        dew = self.dew

        humidity = self.humidity

        precip = self.precip

        precipprob = self.precipprob

        preciptype: Union[Unset, list[str]] = UNSET
        if not isinstance(self.preciptype, Unset):
            preciptype = self.preciptype

        snow = self.snow

        snowdepth = self.snowdepth

        windgust = self.windgust

        windspeed = self.windspeed

        winddir = self.winddir

        pressure = self.pressure

        conditions = self.conditions

        icon = self.icon

        cloudcover = self.cloudcover

        visibility = self.visibility

        solarradiation = self.solarradiation

        solarenergy = self.solarenergy

        uvindex = self.uvindex

        stations: Union[Unset, list[str]] = UNSET
        if not isinstance(self.stations, Unset):
            stations = self.stations

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if datetime_ is not UNSET:
            field_dict["datetime"] = datetime_
        if datetime_epoch is not UNSET:
            field_dict["datetimeEpoch"] = datetime_epoch
        if temp is not UNSET:
            field_dict["temp"] = temp
        if feelslike is not UNSET:
            field_dict["feelslike"] = feelslike
        if dew is not UNSET:
            field_dict["dew"] = dew
        if humidity is not UNSET:
            field_dict["humidity"] = humidity
        if precip is not UNSET:
            field_dict["precip"] = precip
        if precipprob is not UNSET:
            field_dict["precipprob"] = precipprob
        if preciptype is not UNSET:
            field_dict["preciptype"] = preciptype
        if snow is not UNSET:
            field_dict["snow"] = snow
        if snowdepth is not UNSET:
            field_dict["snowdepth"] = snowdepth
        if windgust is not UNSET:
            field_dict["windgust"] = windgust
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
        if cloudcover is not UNSET:
            field_dict["cloudcover"] = cloudcover
        if visibility is not UNSET:
            field_dict["visibility"] = visibility
        if solarradiation is not UNSET:
            field_dict["solarradiation"] = solarradiation
        if solarenergy is not UNSET:
            field_dict["solarenergy"] = solarenergy
        if uvindex is not UNSET:
            field_dict["uvindex"] = uvindex
        if stations is not UNSET:
            field_dict["stations"] = stations

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        datetime_ = d.pop("datetime", UNSET)

        datetime_epoch = d.pop("datetimeEpoch", UNSET)

        temp = d.pop("temp", UNSET)

        feelslike = d.pop("feelslike", UNSET)

        dew = d.pop("dew", UNSET)

        humidity = d.pop("humidity", UNSET)

        precip = d.pop("precip", UNSET)

        precipprob = d.pop("precipprob", UNSET)

        preciptype = cast(list[str], d.pop("preciptype", UNSET))

        snow = d.pop("snow", UNSET)

        snowdepth = d.pop("snowdepth", UNSET)

        windgust = d.pop("windgust", UNSET)

        windspeed = d.pop("windspeed", UNSET)

        winddir = d.pop("winddir", UNSET)

        pressure = d.pop("pressure", UNSET)

        conditions = d.pop("conditions", UNSET)

        icon = d.pop("icon", UNSET)

        cloudcover = d.pop("cloudcover", UNSET)

        visibility = d.pop("visibility", UNSET)

        solarradiation = d.pop("solarradiation", UNSET)

        solarenergy = d.pop("solarenergy", UNSET)

        uvindex = d.pop("uvindex", UNSET)

        stations = cast(list[str], d.pop("stations", UNSET))

        hour_forecast = cls(
            datetime_=datetime_,
            datetime_epoch=datetime_epoch,
            temp=temp,
            feelslike=feelslike,
            dew=dew,
            humidity=humidity,
            precip=precip,
            precipprob=precipprob,
            preciptype=preciptype,
            snow=snow,
            snowdepth=snowdepth,
            windgust=windgust,
            windspeed=windspeed,
            winddir=winddir,
            pressure=pressure,
            conditions=conditions,
            icon=icon,
            cloudcover=cloudcover,
            visibility=visibility,
            solarradiation=solarradiation,
            solarenergy=solarenergy,
            uvindex=uvindex,
            stations=stations,
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
