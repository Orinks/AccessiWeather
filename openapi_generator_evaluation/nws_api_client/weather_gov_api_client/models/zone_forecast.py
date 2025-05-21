import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.zone_forecast_periods_item import ZoneForecastPeriodsItem


T = TypeVar("T", bound="ZoneForecast")


@_attrs_define
class ZoneForecast:
    """An object representing a zone area forecast.

    Attributes:
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        geometry (Union[None, Unset, str]): A geometry represented in Well-Known Text (WKT) format.
        zone (Union[Unset, str]): An API link to the zone this forecast is for.
        updated (Union[Unset, datetime.datetime]): The time this zone forecast product was published.
        periods (Union[Unset, list['ZoneForecastPeriodsItem']]): An array of forecast periods.
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    geometry: Union[None, Unset, str] = UNSET
    zone: Union[Unset, str] = UNSET
    updated: Union[Unset, datetime.datetime] = UNSET
    periods: Union[Unset, list["ZoneForecastPeriodsItem"]] = UNSET

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

        zone = self.zone

        updated: Union[Unset, str] = UNSET
        if not isinstance(self.updated, Unset):
            updated = self.updated.isoformat()

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
        if zone is not UNSET:
            field_dict["zone"] = zone
        if updated is not UNSET:
            field_dict["updated"] = updated
        if periods is not UNSET:
            field_dict["periods"] = periods

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.zone_forecast_periods_item import ZoneForecastPeriodsItem

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

        zone = d.pop("zone", UNSET)

        _updated = d.pop("updated", UNSET)
        updated: Union[Unset, datetime.datetime]
        if isinstance(_updated, Unset):
            updated = UNSET
        else:
            updated = isoparse(_updated)

        periods = []
        _periods = d.pop("periods", UNSET)
        for periods_item_data in _periods or []:
            periods_item = ZoneForecastPeriodsItem.from_dict(periods_item_data)

            periods.append(periods_item)

        zone_forecast = cls(
            context=context,
            geometry=geometry,
            zone=zone,
            updated=updated,
            periods=periods,
        )

        return zone_forecast
