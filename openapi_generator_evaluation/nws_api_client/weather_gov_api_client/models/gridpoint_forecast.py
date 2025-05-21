import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.gridpoint_forecast_units import GridpointForecastUnits
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.gridpoint_forecast_period import GridpointForecastPeriod
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.quantitative_value import QuantitativeValue


T = TypeVar("T", bound="GridpointForecast")


@_attrs_define
class GridpointForecast:
    """A multi-day forecast for a 2.5km grid square.

    Attributes:
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        geometry (Union[None, Unset, str]): A geometry represented in Well-Known Text (WKT) format.
        units (Union[Unset, GridpointForecastUnits]): Denotes the units used in the textual portions of the forecast.
        forecast_generator (Union[Unset, str]): The internal generator class used to create the forecast text (used for
            NWS debugging).
        generated_at (Union[Unset, datetime.datetime]): The time this forecast data was generated.
        update_time (Union[Unset, datetime.datetime]): The last update time of the data this forecast was generated
            from.
        valid_times (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        elevation (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        periods (Union[Unset, list['GridpointForecastPeriod']]): An array of forecast periods.
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    geometry: Union[None, Unset, str] = UNSET
    units: Union[Unset, GridpointForecastUnits] = UNSET
    forecast_generator: Union[Unset, str] = UNSET
    generated_at: Union[Unset, datetime.datetime] = UNSET
    update_time: Union[Unset, datetime.datetime] = UNSET
    valid_times: Union[Unset, str] = UNSET
    elevation: Union[Unset, "QuantitativeValue"] = UNSET
    periods: Union[Unset, list["GridpointForecastPeriod"]] = UNSET

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

        units: Union[Unset, str] = UNSET
        if not isinstance(self.units, Unset):
            units = self.units.value

        forecast_generator = self.forecast_generator

        generated_at: Union[Unset, str] = UNSET
        if not isinstance(self.generated_at, Unset):
            generated_at = self.generated_at.isoformat()

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

        periods: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.periods, Unset):
            periods = []
            for periods_item_data in self.periods:
                periods_item = periods_item_data.to_dict()
                periods.append(periods_item)

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if context is not UNSET:
            field_dict["@context"] = context
        if geometry is not UNSET:
            field_dict["geometry"] = geometry
        if units is not UNSET:
            field_dict["units"] = units
        if forecast_generator is not UNSET:
            field_dict["forecastGenerator"] = forecast_generator
        if generated_at is not UNSET:
            field_dict["generatedAt"] = generated_at
        if update_time is not UNSET:
            field_dict["updateTime"] = update_time
        if valid_times is not UNSET:
            field_dict["validTimes"] = valid_times
        if elevation is not UNSET:
            field_dict["elevation"] = elevation
        if periods is not UNSET:
            field_dict["periods"] = periods

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.gridpoint_forecast_period import GridpointForecastPeriod
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

        _units = d.pop("units", UNSET)
        units: Union[Unset, GridpointForecastUnits]
        if isinstance(_units, Unset):
            units = UNSET
        else:
            units = GridpointForecastUnits(_units)

        forecast_generator = d.pop("forecastGenerator", UNSET)

        _generated_at = d.pop("generatedAt", UNSET)
        generated_at: Union[Unset, datetime.datetime]
        if isinstance(_generated_at, Unset):
            generated_at = UNSET
        else:
            generated_at = isoparse(_generated_at)

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

        periods = []
        _periods = d.pop("periods", UNSET)
        for periods_item_data in _periods or []:
            periods_item = GridpointForecastPeriod.from_dict(periods_item_data)

            periods.append(periods_item)

        gridpoint_forecast = cls(
            context=context,
            geometry=geometry,
            units=units,
            forecast_generator=forecast_generator,
            generated_at=generated_at,
            update_time=update_time,
            valid_times=valid_times,
            elevation=elevation,
            periods=periods,
        )

        return gridpoint_forecast
