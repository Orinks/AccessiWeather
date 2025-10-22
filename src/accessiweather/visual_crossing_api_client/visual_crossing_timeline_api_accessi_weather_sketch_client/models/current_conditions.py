from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CurrentConditions")


@_attrs_define
class CurrentConditions:
    """
    Attributes:
        datetime_ (Union[Unset, str]): Local timestamp of the observation.
        datetime_epoch (Union[Unset, int]): Epoch seconds for the observation time.
        temp (Union[Unset, float]):
        feelslike (Union[Unset, float]):
        humidity (Union[Unset, float]):
        dew (Union[Unset, float]):
        precip (Union[Unset, float]):
        precipprob (Union[Unset, float]):
        preciptype (Union[Unset, list[str]]):
        snow (Union[Unset, float]):
        snowdepth (Union[Unset, float]):
        windgust (Union[Unset, float]):
        windspeed (Union[Unset, float]):
        winddir (Union[Unset, float]):
        pressure (Union[Unset, float]):
        visibility (Union[Unset, float]):
        cloudcover (Union[Unset, float]):
        solarradiation (Union[Unset, float]):
        solarenergy (Union[Unset, float]):
        uvindex (Union[Unset, float]):
        conditions (Union[Unset, str]):
        stations (Union[Unset, list[str]]):
        icon (Union[Unset, str]):
        sunrise (Union[Unset, str]):
        sunrise_epoch (Union[Unset, int]):
        sunset (Union[Unset, str]):
        sunset_epoch (Union[Unset, int]):
        source (Union[Unset, str]):
    """

    datetime_: Union[Unset, str] = UNSET
    datetime_epoch: Union[Unset, int] = UNSET
    temp: Union[Unset, float] = UNSET
    feelslike: Union[Unset, float] = UNSET
    humidity: Union[Unset, float] = UNSET
    dew: Union[Unset, float] = UNSET
    precip: Union[Unset, float] = UNSET
    precipprob: Union[Unset, float] = UNSET
    preciptype: Union[Unset, list[str]] = UNSET
    snow: Union[Unset, float] = UNSET
    snowdepth: Union[Unset, float] = UNSET
    windgust: Union[Unset, float] = UNSET
    windspeed: Union[Unset, float] = UNSET
    winddir: Union[Unset, float] = UNSET
    pressure: Union[Unset, float] = UNSET
    visibility: Union[Unset, float] = UNSET
    cloudcover: Union[Unset, float] = UNSET
    solarradiation: Union[Unset, float] = UNSET
    solarenergy: Union[Unset, float] = UNSET
    uvindex: Union[Unset, float] = UNSET
    conditions: Union[Unset, str] = UNSET
    stations: Union[Unset, list[str]] = UNSET
    icon: Union[Unset, str] = UNSET
    sunrise: Union[Unset, str] = UNSET
    sunrise_epoch: Union[Unset, int] = UNSET
    sunset: Union[Unset, str] = UNSET
    sunset_epoch: Union[Unset, int] = UNSET
    source: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        datetime_ = self.datetime_

        datetime_epoch = self.datetime_epoch

        temp = self.temp

        feelslike = self.feelslike

        humidity = self.humidity

        dew = self.dew

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

        visibility = self.visibility

        cloudcover = self.cloudcover

        solarradiation = self.solarradiation

        solarenergy = self.solarenergy

        uvindex = self.uvindex

        conditions = self.conditions

        stations: Union[Unset, list[str]] = UNSET
        if not isinstance(self.stations, Unset):
            stations = self.stations

        icon = self.icon

        sunrise = self.sunrise

        sunrise_epoch = self.sunrise_epoch

        sunset = self.sunset

        sunset_epoch = self.sunset_epoch

        source = self.source

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
        if humidity is not UNSET:
            field_dict["humidity"] = humidity
        if dew is not UNSET:
            field_dict["dew"] = dew
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
        if visibility is not UNSET:
            field_dict["visibility"] = visibility
        if cloudcover is not UNSET:
            field_dict["cloudcover"] = cloudcover
        if solarradiation is not UNSET:
            field_dict["solarradiation"] = solarradiation
        if solarenergy is not UNSET:
            field_dict["solarenergy"] = solarenergy
        if uvindex is not UNSET:
            field_dict["uvindex"] = uvindex
        if conditions is not UNSET:
            field_dict["conditions"] = conditions
        if stations is not UNSET:
            field_dict["stations"] = stations
        if icon is not UNSET:
            field_dict["icon"] = icon
        if sunrise is not UNSET:
            field_dict["sunrise"] = sunrise
        if sunrise_epoch is not UNSET:
            field_dict["sunriseEpoch"] = sunrise_epoch
        if sunset is not UNSET:
            field_dict["sunset"] = sunset
        if sunset_epoch is not UNSET:
            field_dict["sunsetEpoch"] = sunset_epoch
        if source is not UNSET:
            field_dict["source"] = source

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        datetime_ = d.pop("datetime", UNSET)

        datetime_epoch = d.pop("datetimeEpoch", UNSET)

        temp = d.pop("temp", UNSET)

        feelslike = d.pop("feelslike", UNSET)

        humidity = d.pop("humidity", UNSET)

        dew = d.pop("dew", UNSET)

        precip = d.pop("precip", UNSET)

        precipprob = d.pop("precipprob", UNSET)

        preciptype = cast(list[str], d.pop("preciptype", UNSET))

        snow = d.pop("snow", UNSET)

        snowdepth = d.pop("snowdepth", UNSET)

        windgust = d.pop("windgust", UNSET)

        windspeed = d.pop("windspeed", UNSET)

        winddir = d.pop("winddir", UNSET)

        pressure = d.pop("pressure", UNSET)

        visibility = d.pop("visibility", UNSET)

        cloudcover = d.pop("cloudcover", UNSET)

        solarradiation = d.pop("solarradiation", UNSET)

        solarenergy = d.pop("solarenergy", UNSET)

        uvindex = d.pop("uvindex", UNSET)

        conditions = d.pop("conditions", UNSET)

        stations = cast(list[str], d.pop("stations", UNSET))

        icon = d.pop("icon", UNSET)

        sunrise = d.pop("sunrise", UNSET)

        sunrise_epoch = d.pop("sunriseEpoch", UNSET)

        sunset = d.pop("sunset", UNSET)

        sunset_epoch = d.pop("sunsetEpoch", UNSET)

        source = d.pop("source", UNSET)

        current_conditions = cls(
            datetime_=datetime_,
            datetime_epoch=datetime_epoch,
            temp=temp,
            feelslike=feelslike,
            humidity=humidity,
            dew=dew,
            precip=precip,
            precipprob=precipprob,
            preciptype=preciptype,
            snow=snow,
            snowdepth=snowdepth,
            windgust=windgust,
            windspeed=windspeed,
            winddir=winddir,
            pressure=pressure,
            visibility=visibility,
            cloudcover=cloudcover,
            solarradiation=solarradiation,
            solarenergy=solarenergy,
            uvindex=uvindex,
            conditions=conditions,
            stations=stations,
            icon=icon,
            sunrise=sunrise,
            sunrise_epoch=sunrise_epoch,
            sunset=sunset,
            sunset_epoch=sunset_epoch,
            source=source,
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
