from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.hour_forecast import HourForecast


T = TypeVar("T", bound="DayForecast")


@_attrs_define
class DayForecast:
    """
    Attributes:
        datetime_ (Union[Unset, str]): Date for the forecast period (YYYY-MM-DD).
        datetime_epoch (Union[Unset, int]):
        tempmax (Union[Unset, float]):
        tempmin (Union[Unset, float]):
        temp (Union[Unset, float]):
        feelslikemax (Union[Unset, float]):
        feelslikemin (Union[Unset, float]):
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
        cloudcover (Union[Unset, float]):
        visibility (Union[Unset, float]):
        solarradiation (Union[Unset, float]):
        solarenergy (Union[Unset, float]):
        uvindex (Union[Unset, float]):
        sunrise (Union[Unset, str]):
        sunrise_epoch (Union[Unset, int]):
        sunset (Union[Unset, str]):
        sunset_epoch (Union[Unset, int]):
        moonphase (Union[Unset, float]):
        description (Union[Unset, str]):
        conditions (Union[Unset, str]):
        icon (Union[Unset, str]):
        stations (Union[Unset, list[str]]):
        hours (Union[Unset, list['HourForecast']]):
    """

    datetime_: Union[Unset, str] = UNSET
    datetime_epoch: Union[Unset, int] = UNSET
    tempmax: Union[Unset, float] = UNSET
    tempmin: Union[Unset, float] = UNSET
    temp: Union[Unset, float] = UNSET
    feelslikemax: Union[Unset, float] = UNSET
    feelslikemin: Union[Unset, float] = UNSET
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
    cloudcover: Union[Unset, float] = UNSET
    visibility: Union[Unset, float] = UNSET
    solarradiation: Union[Unset, float] = UNSET
    solarenergy: Union[Unset, float] = UNSET
    uvindex: Union[Unset, float] = UNSET
    sunrise: Union[Unset, str] = UNSET
    sunrise_epoch: Union[Unset, int] = UNSET
    sunset: Union[Unset, str] = UNSET
    sunset_epoch: Union[Unset, int] = UNSET
    moonphase: Union[Unset, float] = UNSET
    description: Union[Unset, str] = UNSET
    conditions: Union[Unset, str] = UNSET
    icon: Union[Unset, str] = UNSET
    stations: Union[Unset, list[str]] = UNSET
    hours: Union[Unset, list["HourForecast"]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        datetime_ = self.datetime_

        datetime_epoch = self.datetime_epoch

        tempmax = self.tempmax

        tempmin = self.tempmin

        temp = self.temp

        feelslikemax = self.feelslikemax

        feelslikemin = self.feelslikemin

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

        cloudcover = self.cloudcover

        visibility = self.visibility

        solarradiation = self.solarradiation

        solarenergy = self.solarenergy

        uvindex = self.uvindex

        sunrise = self.sunrise

        sunrise_epoch = self.sunrise_epoch

        sunset = self.sunset

        sunset_epoch = self.sunset_epoch

        moonphase = self.moonphase

        description = self.description

        conditions = self.conditions

        icon = self.icon

        stations: Union[Unset, list[str]] = UNSET
        if not isinstance(self.stations, Unset):
            stations = self.stations

        hours: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.hours, Unset):
            hours = []
            for hours_item_data in self.hours:
                hours_item = hours_item_data.to_dict()
                hours.append(hours_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if datetime_ is not UNSET:
            field_dict["datetime"] = datetime_
        if datetime_epoch is not UNSET:
            field_dict["datetimeEpoch"] = datetime_epoch
        if tempmax is not UNSET:
            field_dict["tempmax"] = tempmax
        if tempmin is not UNSET:
            field_dict["tempmin"] = tempmin
        if temp is not UNSET:
            field_dict["temp"] = temp
        if feelslikemax is not UNSET:
            field_dict["feelslikemax"] = feelslikemax
        if feelslikemin is not UNSET:
            field_dict["feelslikemin"] = feelslikemin
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
        if sunrise is not UNSET:
            field_dict["sunrise"] = sunrise
        if sunrise_epoch is not UNSET:
            field_dict["sunriseEpoch"] = sunrise_epoch
        if sunset is not UNSET:
            field_dict["sunset"] = sunset
        if sunset_epoch is not UNSET:
            field_dict["sunsetEpoch"] = sunset_epoch
        if moonphase is not UNSET:
            field_dict["moonphase"] = moonphase
        if description is not UNSET:
            field_dict["description"] = description
        if conditions is not UNSET:
            field_dict["conditions"] = conditions
        if icon is not UNSET:
            field_dict["icon"] = icon
        if stations is not UNSET:
            field_dict["stations"] = stations
        if hours is not UNSET:
            field_dict["hours"] = hours

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.hour_forecast import HourForecast

        d = dict(src_dict)
        datetime_ = d.pop("datetime", UNSET)

        datetime_epoch = d.pop("datetimeEpoch", UNSET)

        tempmax = d.pop("tempmax", UNSET)

        tempmin = d.pop("tempmin", UNSET)

        temp = d.pop("temp", UNSET)

        feelslikemax = d.pop("feelslikemax", UNSET)

        feelslikemin = d.pop("feelslikemin", UNSET)

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

        cloudcover = d.pop("cloudcover", UNSET)

        visibility = d.pop("visibility", UNSET)

        solarradiation = d.pop("solarradiation", UNSET)

        solarenergy = d.pop("solarenergy", UNSET)

        uvindex = d.pop("uvindex", UNSET)

        sunrise = d.pop("sunrise", UNSET)

        sunrise_epoch = d.pop("sunriseEpoch", UNSET)

        sunset = d.pop("sunset", UNSET)

        sunset_epoch = d.pop("sunsetEpoch", UNSET)

        moonphase = d.pop("moonphase", UNSET)

        description = d.pop("description", UNSET)

        conditions = d.pop("conditions", UNSET)

        icon = d.pop("icon", UNSET)

        stations = cast(list[str], d.pop("stations", UNSET))

        hours = []
        _hours = d.pop("hours", UNSET)
        for hours_item_data in _hours or []:
            hours_item = HourForecast.from_dict(hours_item_data)

            hours.append(hours_item)

        day_forecast = cls(
            datetime_=datetime_,
            datetime_epoch=datetime_epoch,
            tempmax=tempmax,
            tempmin=tempmin,
            temp=temp,
            feelslikemax=feelslikemax,
            feelslikemin=feelslikemin,
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
            cloudcover=cloudcover,
            visibility=visibility,
            solarradiation=solarradiation,
            solarenergy=solarenergy,
            uvindex=uvindex,
            sunrise=sunrise,
            sunrise_epoch=sunrise_epoch,
            sunset=sunset,
            sunset_epoch=sunset_epoch,
            moonphase=moonphase,
            description=description,
            conditions=conditions,
            icon=icon,
            stations=stations,
            hours=hours,
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
