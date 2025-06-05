from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.nws_forecast_office_id import NWSForecastOfficeId
from ..models.point_type import PointType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.relative_location_geo_json import RelativeLocationGeoJson
    from ..models.relative_location_json_ld import RelativeLocationJsonLd


T = TypeVar("T", bound="PointJsonLd")


@_attrs_define
class PointJsonLd:
    """
    Attributes:
        context (Union['JsonLdContextType1', list[Any]]):
        geometry (Union[None, str]): A geometry represented in Well-Known Text (WKT) format.
        id (Union[Unset, str]):
        type_ (Union[Unset, PointType]):
        cwa (Union[Unset, NWSForecastOfficeId]): Three-letter identifier for a NWS office.
        forecast_office (Union[Unset, str]):
        grid_id (Union[Unset, NWSForecastOfficeId]): Three-letter identifier for a NWS office.
        grid_x (Union[Unset, int]):
        grid_y (Union[Unset, int]):
        forecast (Union[Unset, str]):
        forecast_hourly (Union[Unset, str]):
        forecast_grid_data (Union[Unset, str]):
        observation_stations (Union[Unset, str]):
        relative_location (Union['RelativeLocationGeoJson', 'RelativeLocationJsonLd', Unset]):
        forecast_zone (Union[Unset, str]):
        county (Union[Unset, str]):
        fire_weather_zone (Union[Unset, str]):
        time_zone (Union[Unset, str]):
        radar_station (Union[Unset, str]):
    """

    context: Union["JsonLdContextType1", list[Any]]
    geometry: Union[None, str]
    id: Union[Unset, str] = UNSET
    type_: Union[Unset, PointType] = UNSET
    cwa: Union[Unset, NWSForecastOfficeId] = UNSET
    forecast_office: Union[Unset, str] = UNSET
    grid_id: Union[Unset, NWSForecastOfficeId] = UNSET
    grid_x: Union[Unset, int] = UNSET
    grid_y: Union[Unset, int] = UNSET
    forecast: Union[Unset, str] = UNSET
    forecast_hourly: Union[Unset, str] = UNSET
    forecast_grid_data: Union[Unset, str] = UNSET
    observation_stations: Union[Unset, str] = UNSET
    relative_location: Union["RelativeLocationGeoJson", "RelativeLocationJsonLd", Unset] = UNSET
    forecast_zone: Union[Unset, str] = UNSET
    county: Union[Unset, str] = UNSET
    fire_weather_zone: Union[Unset, str] = UNSET
    time_zone: Union[Unset, str] = UNSET
    radar_station: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.relative_location_geo_json import RelativeLocationGeoJson

        context: Union[dict[str, Any], list[Any]]
        if isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        geometry: Union[None, str]
        geometry = self.geometry

        id = self.id

        type_: Union[Unset, str] = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        cwa: Union[Unset, str] = UNSET
        if not isinstance(self.cwa, Unset):
            cwa = self.cwa.value

        forecast_office = self.forecast_office

        grid_id: Union[Unset, str] = UNSET
        if not isinstance(self.grid_id, Unset):
            grid_id = self.grid_id.value

        grid_x = self.grid_x

        grid_y = self.grid_y

        forecast = self.forecast

        forecast_hourly = self.forecast_hourly

        forecast_grid_data = self.forecast_grid_data

        observation_stations = self.observation_stations

        relative_location: Union[Unset, dict[str, Any]]
        if isinstance(self.relative_location, Unset):
            relative_location = UNSET
        elif isinstance(self.relative_location, RelativeLocationGeoJson):
            relative_location = self.relative_location.to_dict()
        else:
            relative_location = self.relative_location.to_dict()

        forecast_zone = self.forecast_zone

        county = self.county

        fire_weather_zone = self.fire_weather_zone

        time_zone = self.time_zone

        radar_station = self.radar_station

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "@context": context,
                "geometry": geometry,
            }
        )
        if id is not UNSET:
            field_dict["@id"] = id
        if type_ is not UNSET:
            field_dict["@type"] = type_
        if cwa is not UNSET:
            field_dict["cwa"] = cwa
        if forecast_office is not UNSET:
            field_dict["forecastOffice"] = forecast_office
        if grid_id is not UNSET:
            field_dict["gridId"] = grid_id
        if grid_x is not UNSET:
            field_dict["gridX"] = grid_x
        if grid_y is not UNSET:
            field_dict["gridY"] = grid_y
        if forecast is not UNSET:
            field_dict["forecast"] = forecast
        if forecast_hourly is not UNSET:
            field_dict["forecastHourly"] = forecast_hourly
        if forecast_grid_data is not UNSET:
            field_dict["forecastGridData"] = forecast_grid_data
        if observation_stations is not UNSET:
            field_dict["observationStations"] = observation_stations
        if relative_location is not UNSET:
            field_dict["relativeLocation"] = relative_location
        if forecast_zone is not UNSET:
            field_dict["forecastZone"] = forecast_zone
        if county is not UNSET:
            field_dict["county"] = county
        if fire_weather_zone is not UNSET:
            field_dict["fireWeatherZone"] = fire_weather_zone
        if time_zone is not UNSET:
            field_dict["timeZone"] = time_zone
        if radar_station is not UNSET:
            field_dict["radarStation"] = radar_station

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.relative_location_geo_json import RelativeLocationGeoJson
        from ..models.relative_location_json_ld import RelativeLocationJsonLd

        d = dict(src_dict)

        def _parse_context(data: object) -> Union["JsonLdContextType1", list[Any]]:
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

        context = _parse_context(d.pop("@context"))

        def _parse_geometry(data: object) -> Union[None, str]:
            if data is None:
                return data
            return cast(Union[None, str], data)

        geometry = _parse_geometry(d.pop("geometry"))

        id = d.pop("@id", UNSET)

        _type_ = d.pop("@type", UNSET)
        type_: Union[Unset, PointType]
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = PointType(_type_)

        _cwa = d.pop("cwa", UNSET)
        cwa: Union[Unset, NWSForecastOfficeId]
        if isinstance(_cwa, Unset):
            cwa = UNSET
        else:
            cwa = NWSForecastOfficeId(_cwa)

        forecast_office = d.pop("forecastOffice", UNSET)

        _grid_id = d.pop("gridId", UNSET)
        grid_id: Union[Unset, NWSForecastOfficeId]
        if isinstance(_grid_id, Unset):
            grid_id = UNSET
        else:
            grid_id = NWSForecastOfficeId(_grid_id)

        grid_x = d.pop("gridX", UNSET)

        grid_y = d.pop("gridY", UNSET)

        forecast = d.pop("forecast", UNSET)

        forecast_hourly = d.pop("forecastHourly", UNSET)

        forecast_grid_data = d.pop("forecastGridData", UNSET)

        observation_stations = d.pop("observationStations", UNSET)

        def _parse_relative_location(
            data: object,
        ) -> Union["RelativeLocationGeoJson", "RelativeLocationJsonLd", Unset]:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                relative_location_type_0 = RelativeLocationGeoJson.from_dict(data)

                return relative_location_type_0
            except:  # noqa: E722
                pass
            if not isinstance(data, dict):
                raise TypeError()
            relative_location_type_1 = RelativeLocationJsonLd.from_dict(data)

            return relative_location_type_1

        relative_location = _parse_relative_location(d.pop("relativeLocation", UNSET))

        forecast_zone = d.pop("forecastZone", UNSET)

        county = d.pop("county", UNSET)

        fire_weather_zone = d.pop("fireWeatherZone", UNSET)

        time_zone = d.pop("timeZone", UNSET)

        radar_station = d.pop("radarStation", UNSET)

        point_json_ld = cls(
            context=context,
            geometry=geometry,
            id=id,
            type_=type_,
            cwa=cwa,
            forecast_office=forecast_office,
            grid_id=grid_id,
            grid_x=grid_x,
            grid_y=grid_y,
            forecast=forecast,
            forecast_hourly=forecast_hourly,
            forecast_grid_data=forecast_grid_data,
            observation_stations=observation_stations,
            relative_location=relative_location,
            forecast_zone=forecast_zone,
            county=county,
            fire_weather_zone=fire_weather_zone,
            time_zone=time_zone,
            radar_station=radar_station,
        )

        point_json_ld.additional_properties = d
        return point_json_ld

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
