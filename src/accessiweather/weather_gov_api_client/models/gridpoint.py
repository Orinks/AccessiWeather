import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.gridpoint_type import GridpointType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.gridpoint_hazards import GridpointHazards
    from ..models.gridpoint_quantitative_value_layer import GridpointQuantitativeValueLayer
    from ..models.gridpoint_weather import GridpointWeather
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.quantitative_value import QuantitativeValue


T = TypeVar("T", bound="Gridpoint")


@_attrs_define
class Gridpoint:
    """Raw forecast data for a 2.5km grid square.
    This is a list of all potential data layers that may appear. Some layers may not be present in all areas.
    * temperature
    * dewpoint
    * maxTemperature
    * minTemperature
    * relativeHumidity
    * apparentTemperature
    * heatIndex
    * windChill
    * wetBulbGlobeTemperature
    * skyCover
    * windDirection
    * windSpeed
    * windGust
    * weather
    * hazards: Watch and advisory products in effect
    * probabilityOfPrecipitation
    * quantitativePrecipitation
    * iceAccumulation
    * snowfallAmount
    * snowLevel
    * ceilingHeight
    * visibility
    * transportWindSpeed
    * transportWindDirection
    * mixingHeight
    * hainesIndex
    * lightningActivityLevel
    * twentyFootWindSpeed
    * twentyFootWindDirection
    * waveHeight
    * wavePeriod
    * waveDirection
    * primarySwellHeight
    * primarySwellDirection
    * secondarySwellHeight
    * secondarySwellDirection
    * wavePeriod2
    * windWaveHeight
    * dispersionIndex
    * pressure: Barometric pressure
    * probabilityOfTropicalStormWinds
    * probabilityOfHurricaneWinds
    * potentialOf15mphWinds
    * potentialOf25mphWinds
    * potentialOf35mphWinds
    * potentialOf45mphWinds
    * potentialOf20mphWindGusts
    * potentialOf30mphWindGusts
    * potentialOf40mphWindGusts
    * potentialOf50mphWindGusts
    * potentialOf60mphWindGusts
    * grasslandFireDangerIndex
    * probabilityOfThunder
    * davisStabilityIndex
    * atmosphericDispersionIndex
    * lowVisibilityOccurrenceRiskIndex
    * stability
    * redFlagThreatIndex

        Attributes:
            context (Union['JsonLdContextType1', Unset, list[Any]]):
            geometry (Union[None, Unset, str]): A geometry represented in Well-Known Text (WKT) format.
            id (Union[Unset, str]):
            type_ (Union[Unset, GridpointType]):
            update_time (Union[Unset, datetime.datetime]):
            valid_times (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                    1. Start and end time
                    2. Start time and duration
                    3. Duration and end time
                The string "NOW" can also be used in place of a start/end time.
            elevation (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
                measure. This object is a slighly modified version of the schema.org definition at
                https://schema.org/QuantitativeValue
            forecast_office (Union[Unset, str]):
            grid_id (Union[Unset, str]):
            grid_x (Union[Unset, int]):
            grid_y (Union[Unset, int]):
            weather (Union[Unset, GridpointWeather]):
            hazards (Union[Unset, GridpointHazards]):
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    geometry: Union[None, Unset, str] = UNSET
    id: Union[Unset, str] = UNSET
    type_: Union[Unset, GridpointType] = UNSET
    update_time: Union[Unset, datetime.datetime] = UNSET
    valid_times: Union[Unset, str] = UNSET
    elevation: Union[Unset, "QuantitativeValue"] = UNSET
    forecast_office: Union[Unset, str] = UNSET
    grid_id: Union[Unset, str] = UNSET
    grid_x: Union[Unset, int] = UNSET
    grid_y: Union[Unset, int] = UNSET
    weather: Union[Unset, "GridpointWeather"] = UNSET
    hazards: Union[Unset, "GridpointHazards"] = UNSET
    additional_properties: dict[str, "GridpointQuantitativeValueLayer"] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        context: Union[Unset, dict[str, Any], list[Any]]
        if isinstance(self.context, Unset):
            context = UNSET
        elif isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        geometry: Union[None, Unset, str]
        if isinstance(self.geometry, Unset):
            geometry = UNSET
        else:
            geometry = self.geometry

        id = self.id

        type_: Union[Unset, str] = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        update_time: Union[Unset, str] = UNSET
        if not isinstance(self.update_time, Unset):
            update_time = self.update_time.isoformat()

        valid_times: Union[Unset, str]
        if isinstance(self.valid_times, Unset):
            valid_times = UNSET
        else:
            valid_times = self.valid_times

        elevation: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.elevation, Unset):
            elevation = self.elevation.to_dict()

        forecast_office = self.forecast_office

        grid_id = self.grid_id

        grid_x = self.grid_x

        grid_y = self.grid_y

        weather: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.weather, Unset):
            weather = self.weather.to_dict()

        hazards: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.hazards, Unset):
            hazards = self.hazards.to_dict()

        field_dict: dict[str, Any] = {}
        for prop_name, prop in self.additional_properties.items():
            field_dict[prop_name] = prop.to_dict()
        field_dict.update({})
        if context is not UNSET:
            field_dict["@context"] = context
        if geometry is not UNSET:
            field_dict["geometry"] = geometry
        if id is not UNSET:
            field_dict["@id"] = id
        if type_ is not UNSET:
            field_dict["@type"] = type_
        if update_time is not UNSET:
            field_dict["updateTime"] = update_time
        if valid_times is not UNSET:
            field_dict["validTimes"] = valid_times
        if elevation is not UNSET:
            field_dict["elevation"] = elevation
        if forecast_office is not UNSET:
            field_dict["forecastOffice"] = forecast_office
        if grid_id is not UNSET:
            field_dict["gridId"] = grid_id
        if grid_x is not UNSET:
            field_dict["gridX"] = grid_x
        if grid_y is not UNSET:
            field_dict["gridY"] = grid_y
        if weather is not UNSET:
            field_dict["weather"] = weather
        if hazards is not UNSET:
            field_dict["hazards"] = hazards

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.gridpoint_hazards import GridpointHazards
        from ..models.gridpoint_quantitative_value_layer import GridpointQuantitativeValueLayer
        from ..models.gridpoint_weather import GridpointWeather
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.quantitative_value import QuantitativeValue

        d = dict(src_dict)

        def _parse_context(data: object) -> Union["JsonLdContextType1", Unset, list[Any]]:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_json_ld_context_type_0 = cast(list[Any], data)

                return componentsschemas_json_ld_context_type_0
            except:  # noqa: E722
                pass
            if not isinstance(data, dict):
                raise TypeError()
            componentsschemas_json_ld_context_type_1 = JsonLdContextType1.from_dict(data)

            return componentsschemas_json_ld_context_type_1

        context = _parse_context(d.pop("@context", UNSET))

        def _parse_geometry(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        geometry = _parse_geometry(d.pop("geometry", UNSET))

        id = d.pop("@id", UNSET)

        _type_ = d.pop("@type", UNSET)
        type_: Union[Unset, GridpointType]
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = GridpointType(_type_)

        _update_time = d.pop("updateTime", UNSET)
        update_time: Union[Unset, datetime.datetime]
        if isinstance(_update_time, Unset):
            update_time = UNSET
        else:
            update_time = isoparse(_update_time)

        def _parse_valid_times(data: object) -> Union[Unset, str]:
            if isinstance(data, Unset):
                return data
            return cast(Union[Unset, str], data)

        valid_times = _parse_valid_times(d.pop("validTimes", UNSET))

        _elevation = d.pop("elevation", UNSET)
        elevation: Union[Unset, QuantitativeValue]
        if isinstance(_elevation, Unset):
            elevation = UNSET
        else:
            elevation = QuantitativeValue.from_dict(_elevation)

        forecast_office = d.pop("forecastOffice", UNSET)

        grid_id = d.pop("gridId", UNSET)

        grid_x = d.pop("gridX", UNSET)

        grid_y = d.pop("gridY", UNSET)

        _weather = d.pop("weather", UNSET)
        weather: Union[Unset, GridpointWeather]
        if isinstance(_weather, Unset):
            weather = UNSET
        else:
            weather = GridpointWeather.from_dict(_weather)

        _hazards = d.pop("hazards", UNSET)
        hazards: Union[Unset, GridpointHazards]
        if isinstance(_hazards, Unset):
            hazards = UNSET
        else:
            hazards = GridpointHazards.from_dict(_hazards)

        gridpoint = cls(
            context=context,
            geometry=geometry,
            id=id,
            type_=type_,
            update_time=update_time,
            valid_times=valid_times,
            elevation=elevation,
            forecast_office=forecast_office,
            grid_id=grid_id,
            grid_x=grid_x,
            grid_y=grid_y,
            weather=weather,
            hazards=hazards,
        )

        additional_properties = {}
        for prop_name, prop_dict in d.items():
            additional_property = GridpointQuantitativeValueLayer.from_dict(prop_dict)

            additional_properties[prop_name] = additional_property

        gridpoint.additional_properties = additional_properties
        return gridpoint

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> "GridpointQuantitativeValueLayer":
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: "GridpointQuantitativeValueLayer") -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
