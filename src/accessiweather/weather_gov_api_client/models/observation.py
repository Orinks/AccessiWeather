import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.observation_type import ObservationType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.metar_phenomenon import MetarPhenomenon
    from ..models.observation_cloud_layers_type_0_item import ObservationCloudLayersType0Item
    from ..models.quantitative_value import QuantitativeValue


T = TypeVar("T", bound="Observation")


@_attrs_define
class Observation:
    """
    Attributes:
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        geometry (Union[None, Unset, str]): A geometry represented in Well-Known Text (WKT) format.
        id (Union[Unset, str]):
        type_ (Union[Unset, ObservationType]):
        elevation (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        station (Union[Unset, str]):
        timestamp (Union[Unset, datetime.datetime]):
        raw_message (Union[Unset, str]):
        text_description (Union[Unset, str]):
        icon (Union[None, Unset, str]):
        present_weather (Union[Unset, list['MetarPhenomenon']]):
        temperature (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        dewpoint (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        wind_direction (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        wind_speed (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        wind_gust (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        barometric_pressure (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its
            unit of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        sea_level_pressure (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit
            of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        visibility (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        max_temperature_last_24_hours (Union[Unset, QuantitativeValue]): A structured value representing a measurement
            and its unit of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        min_temperature_last_24_hours (Union[Unset, QuantitativeValue]): A structured value representing a measurement
            and its unit of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        precipitation_last_hour (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its
            unit of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        precipitation_last_3_hours (Union[Unset, QuantitativeValue]): A structured value representing a measurement and
            its unit of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        precipitation_last_6_hours (Union[Unset, QuantitativeValue]): A structured value representing a measurement and
            its unit of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        relative_humidity (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit
            of measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        wind_chill (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        heat_index (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        cloud_layers (Union[None, Unset, list['ObservationCloudLayersType0Item']]):
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    geometry: Union[None, Unset, str] = UNSET
    id: Union[Unset, str] = UNSET
    type_: Union[Unset, ObservationType] = UNSET
    elevation: Union[Unset, "QuantitativeValue"] = UNSET
    station: Union[Unset, str] = UNSET
    timestamp: Union[Unset, datetime.datetime] = UNSET
    raw_message: Union[Unset, str] = UNSET
    text_description: Union[Unset, str] = UNSET
    icon: Union[None, Unset, str] = UNSET
    present_weather: Union[Unset, list["MetarPhenomenon"]] = UNSET
    temperature: Union[Unset, "QuantitativeValue"] = UNSET
    dewpoint: Union[Unset, "QuantitativeValue"] = UNSET
    wind_direction: Union[Unset, "QuantitativeValue"] = UNSET
    wind_speed: Union[Unset, "QuantitativeValue"] = UNSET
    wind_gust: Union[Unset, "QuantitativeValue"] = UNSET
    barometric_pressure: Union[Unset, "QuantitativeValue"] = UNSET
    sea_level_pressure: Union[Unset, "QuantitativeValue"] = UNSET
    visibility: Union[Unset, "QuantitativeValue"] = UNSET
    max_temperature_last_24_hours: Union[Unset, "QuantitativeValue"] = UNSET
    min_temperature_last_24_hours: Union[Unset, "QuantitativeValue"] = UNSET
    precipitation_last_hour: Union[Unset, "QuantitativeValue"] = UNSET
    precipitation_last_3_hours: Union[Unset, "QuantitativeValue"] = UNSET
    precipitation_last_6_hours: Union[Unset, "QuantitativeValue"] = UNSET
    relative_humidity: Union[Unset, "QuantitativeValue"] = UNSET
    wind_chill: Union[Unset, "QuantitativeValue"] = UNSET
    heat_index: Union[Unset, "QuantitativeValue"] = UNSET
    cloud_layers: Union[None, Unset, list["ObservationCloudLayersType0Item"]] = UNSET

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

        elevation: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.elevation, Unset):
            elevation = self.elevation.to_dict()

        station = self.station

        timestamp: Union[Unset, str] = UNSET
        if not isinstance(self.timestamp, Unset):
            timestamp = self.timestamp.isoformat()

        raw_message = self.raw_message

        text_description = self.text_description

        icon: Union[None, Unset, str]
        if isinstance(self.icon, Unset):
            icon = UNSET
        else:
            icon = self.icon

        present_weather: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.present_weather, Unset):
            present_weather = []
            for present_weather_item_data in self.present_weather:
                present_weather_item = present_weather_item_data.to_dict()
                present_weather.append(present_weather_item)

        temperature: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.temperature, Unset):
            temperature = self.temperature.to_dict()

        dewpoint: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.dewpoint, Unset):
            dewpoint = self.dewpoint.to_dict()

        wind_direction: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.wind_direction, Unset):
            wind_direction = self.wind_direction.to_dict()

        wind_speed: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.wind_speed, Unset):
            wind_speed = self.wind_speed.to_dict()

        wind_gust: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.wind_gust, Unset):
            wind_gust = self.wind_gust.to_dict()

        barometric_pressure: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.barometric_pressure, Unset):
            barometric_pressure = self.barometric_pressure.to_dict()

        sea_level_pressure: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.sea_level_pressure, Unset):
            sea_level_pressure = self.sea_level_pressure.to_dict()

        visibility: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.visibility, Unset):
            visibility = self.visibility.to_dict()

        max_temperature_last_24_hours: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.max_temperature_last_24_hours, Unset):
            max_temperature_last_24_hours = self.max_temperature_last_24_hours.to_dict()

        min_temperature_last_24_hours: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.min_temperature_last_24_hours, Unset):
            min_temperature_last_24_hours = self.min_temperature_last_24_hours.to_dict()

        precipitation_last_hour: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.precipitation_last_hour, Unset):
            precipitation_last_hour = self.precipitation_last_hour.to_dict()

        precipitation_last_3_hours: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.precipitation_last_3_hours, Unset):
            precipitation_last_3_hours = self.precipitation_last_3_hours.to_dict()

        precipitation_last_6_hours: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.precipitation_last_6_hours, Unset):
            precipitation_last_6_hours = self.precipitation_last_6_hours.to_dict()

        relative_humidity: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.relative_humidity, Unset):
            relative_humidity = self.relative_humidity.to_dict()

        wind_chill: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.wind_chill, Unset):
            wind_chill = self.wind_chill.to_dict()

        heat_index: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.heat_index, Unset):
            heat_index = self.heat_index.to_dict()

        cloud_layers: Union[None, Unset, list[dict[str, Any]]]
        if isinstance(self.cloud_layers, Unset):
            cloud_layers = UNSET
        elif isinstance(self.cloud_layers, list):
            cloud_layers = []
            for cloud_layers_type_0_item_data in self.cloud_layers:
                cloud_layers_type_0_item = cloud_layers_type_0_item_data.to_dict()
                cloud_layers.append(cloud_layers_type_0_item)

        else:
            cloud_layers = self.cloud_layers

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if context is not UNSET:
            field_dict["@context"] = context
        if geometry is not UNSET:
            field_dict["geometry"] = geometry
        if id is not UNSET:
            field_dict["@id"] = id
        if type_ is not UNSET:
            field_dict["@type"] = type_
        if elevation is not UNSET:
            field_dict["elevation"] = elevation
        if station is not UNSET:
            field_dict["station"] = station
        if timestamp is not UNSET:
            field_dict["timestamp"] = timestamp
        if raw_message is not UNSET:
            field_dict["rawMessage"] = raw_message
        if text_description is not UNSET:
            field_dict["textDescription"] = text_description
        if icon is not UNSET:
            field_dict["icon"] = icon
        if present_weather is not UNSET:
            field_dict["presentWeather"] = present_weather
        if temperature is not UNSET:
            field_dict["temperature"] = temperature
        if dewpoint is not UNSET:
            field_dict["dewpoint"] = dewpoint
        if wind_direction is not UNSET:
            field_dict["windDirection"] = wind_direction
        if wind_speed is not UNSET:
            field_dict["windSpeed"] = wind_speed
        if wind_gust is not UNSET:
            field_dict["windGust"] = wind_gust
        if barometric_pressure is not UNSET:
            field_dict["barometricPressure"] = barometric_pressure
        if sea_level_pressure is not UNSET:
            field_dict["seaLevelPressure"] = sea_level_pressure
        if visibility is not UNSET:
            field_dict["visibility"] = visibility
        if max_temperature_last_24_hours is not UNSET:
            field_dict["maxTemperatureLast24Hours"] = max_temperature_last_24_hours
        if min_temperature_last_24_hours is not UNSET:
            field_dict["minTemperatureLast24Hours"] = min_temperature_last_24_hours
        if precipitation_last_hour is not UNSET:
            field_dict["precipitationLastHour"] = precipitation_last_hour
        if precipitation_last_3_hours is not UNSET:
            field_dict["precipitationLast3Hours"] = precipitation_last_3_hours
        if precipitation_last_6_hours is not UNSET:
            field_dict["precipitationLast6Hours"] = precipitation_last_6_hours
        if relative_humidity is not UNSET:
            field_dict["relativeHumidity"] = relative_humidity
        if wind_chill is not UNSET:
            field_dict["windChill"] = wind_chill
        if heat_index is not UNSET:
            field_dict["heatIndex"] = heat_index
        if cloud_layers is not UNSET:
            field_dict["cloudLayers"] = cloud_layers

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.metar_phenomenon import MetarPhenomenon
        from ..models.observation_cloud_layers_type_0_item import ObservationCloudLayersType0Item
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
        type_: Union[Unset, ObservationType]
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = ObservationType(_type_)

        _elevation = d.pop("elevation", UNSET)
        elevation: Union[Unset, QuantitativeValue]
        if isinstance(_elevation, Unset):
            elevation = UNSET
        else:
            elevation = QuantitativeValue.from_dict(_elevation)

        station = d.pop("station", UNSET)

        _timestamp = d.pop("timestamp", UNSET)
        timestamp: Union[Unset, datetime.datetime]
        if isinstance(_timestamp, Unset):
            timestamp = UNSET
        else:
            timestamp = isoparse(_timestamp)

        raw_message = d.pop("rawMessage", UNSET)

        text_description = d.pop("textDescription", UNSET)

        def _parse_icon(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        icon = _parse_icon(d.pop("icon", UNSET))

        present_weather = []
        _present_weather = d.pop("presentWeather", UNSET)
        for present_weather_item_data in _present_weather or []:
            present_weather_item = MetarPhenomenon.from_dict(present_weather_item_data)

            present_weather.append(present_weather_item)

        _temperature = d.pop("temperature", UNSET)
        temperature: Union[Unset, QuantitativeValue]
        if isinstance(_temperature, Unset):
            temperature = UNSET
        else:
            temperature = QuantitativeValue.from_dict(_temperature)

        _dewpoint = d.pop("dewpoint", UNSET)
        dewpoint: Union[Unset, QuantitativeValue]
        if isinstance(_dewpoint, Unset):
            dewpoint = UNSET
        else:
            dewpoint = QuantitativeValue.from_dict(_dewpoint)

        _wind_direction = d.pop("windDirection", UNSET)
        wind_direction: Union[Unset, QuantitativeValue]
        if isinstance(_wind_direction, Unset):
            wind_direction = UNSET
        else:
            wind_direction = QuantitativeValue.from_dict(_wind_direction)

        _wind_speed = d.pop("windSpeed", UNSET)
        wind_speed: Union[Unset, QuantitativeValue]
        if isinstance(_wind_speed, Unset):
            wind_speed = UNSET
        else:
            wind_speed = QuantitativeValue.from_dict(_wind_speed)

        _wind_gust = d.pop("windGust", UNSET)
        wind_gust: Union[Unset, QuantitativeValue]
        if isinstance(_wind_gust, Unset):
            wind_gust = UNSET
        else:
            wind_gust = QuantitativeValue.from_dict(_wind_gust)

        _barometric_pressure = d.pop("barometricPressure", UNSET)
        barometric_pressure: Union[Unset, QuantitativeValue]
        if isinstance(_barometric_pressure, Unset):
            barometric_pressure = UNSET
        else:
            barometric_pressure = QuantitativeValue.from_dict(_barometric_pressure)

        _sea_level_pressure = d.pop("seaLevelPressure", UNSET)
        sea_level_pressure: Union[Unset, QuantitativeValue]
        if isinstance(_sea_level_pressure, Unset):
            sea_level_pressure = UNSET
        else:
            sea_level_pressure = QuantitativeValue.from_dict(_sea_level_pressure)

        _visibility = d.pop("visibility", UNSET)
        visibility: Union[Unset, QuantitativeValue]
        if isinstance(_visibility, Unset):
            visibility = UNSET
        else:
            visibility = QuantitativeValue.from_dict(_visibility)

        _max_temperature_last_24_hours = d.pop("maxTemperatureLast24Hours", UNSET)
        max_temperature_last_24_hours: Union[Unset, QuantitativeValue]
        if isinstance(_max_temperature_last_24_hours, Unset):
            max_temperature_last_24_hours = UNSET
        else:
            max_temperature_last_24_hours = QuantitativeValue.from_dict(
                _max_temperature_last_24_hours
            )

        _min_temperature_last_24_hours = d.pop("minTemperatureLast24Hours", UNSET)
        min_temperature_last_24_hours: Union[Unset, QuantitativeValue]
        if isinstance(_min_temperature_last_24_hours, Unset):
            min_temperature_last_24_hours = UNSET
        else:
            min_temperature_last_24_hours = QuantitativeValue.from_dict(
                _min_temperature_last_24_hours
            )

        _precipitation_last_hour = d.pop("precipitationLastHour", UNSET)
        precipitation_last_hour: Union[Unset, QuantitativeValue]
        if isinstance(_precipitation_last_hour, Unset):
            precipitation_last_hour = UNSET
        else:
            precipitation_last_hour = QuantitativeValue.from_dict(_precipitation_last_hour)

        _precipitation_last_3_hours = d.pop("precipitationLast3Hours", UNSET)
        precipitation_last_3_hours: Union[Unset, QuantitativeValue]
        if isinstance(_precipitation_last_3_hours, Unset):
            precipitation_last_3_hours = UNSET
        else:
            precipitation_last_3_hours = QuantitativeValue.from_dict(_precipitation_last_3_hours)

        _precipitation_last_6_hours = d.pop("precipitationLast6Hours", UNSET)
        precipitation_last_6_hours: Union[Unset, QuantitativeValue]
        if isinstance(_precipitation_last_6_hours, Unset):
            precipitation_last_6_hours = UNSET
        else:
            precipitation_last_6_hours = QuantitativeValue.from_dict(_precipitation_last_6_hours)

        _relative_humidity = d.pop("relativeHumidity", UNSET)
        relative_humidity: Union[Unset, QuantitativeValue]
        if isinstance(_relative_humidity, Unset):
            relative_humidity = UNSET
        else:
            relative_humidity = QuantitativeValue.from_dict(_relative_humidity)

        _wind_chill = d.pop("windChill", UNSET)
        wind_chill: Union[Unset, QuantitativeValue]
        if isinstance(_wind_chill, Unset):
            wind_chill = UNSET
        else:
            wind_chill = QuantitativeValue.from_dict(_wind_chill)

        _heat_index = d.pop("heatIndex", UNSET)
        heat_index: Union[Unset, QuantitativeValue]
        if isinstance(_heat_index, Unset):
            heat_index = UNSET
        else:
            heat_index = QuantitativeValue.from_dict(_heat_index)

        def _parse_cloud_layers(
            data: object,
        ) -> Union[None, Unset, list["ObservationCloudLayersType0Item"]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                cloud_layers_type_0 = []
                _cloud_layers_type_0 = data
                for cloud_layers_type_0_item_data in _cloud_layers_type_0:
                    cloud_layers_type_0_item = ObservationCloudLayersType0Item.from_dict(
                        cloud_layers_type_0_item_data
                    )

                    cloud_layers_type_0.append(cloud_layers_type_0_item)

                return cloud_layers_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list["ObservationCloudLayersType0Item"]], data)

        cloud_layers = _parse_cloud_layers(d.pop("cloudLayers", UNSET))

        observation = cls(
            context=context,
            geometry=geometry,
            id=id,
            type_=type_,
            elevation=elevation,
            station=station,
            timestamp=timestamp,
            raw_message=raw_message,
            text_description=text_description,
            icon=icon,
            present_weather=present_weather,
            temperature=temperature,
            dewpoint=dewpoint,
            wind_direction=wind_direction,
            wind_speed=wind_speed,
            wind_gust=wind_gust,
            barometric_pressure=barometric_pressure,
            sea_level_pressure=sea_level_pressure,
            visibility=visibility,
            max_temperature_last_24_hours=max_temperature_last_24_hours,
            min_temperature_last_24_hours=min_temperature_last_24_hours,
            precipitation_last_hour=precipitation_last_hour,
            precipitation_last_3_hours=precipitation_last_3_hours,
            precipitation_last_6_hours=precipitation_last_6_hours,
            relative_humidity=relative_humidity,
            wind_chill=wind_chill,
            heat_index=heat_index,
            cloud_layers=cloud_layers,
        )

        return observation
