from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alerts_active_count_response_200_areas import AlertsActiveCountResponse200Areas
    from ..models.alerts_active_count_response_200_regions import (
        AlertsActiveCountResponse200Regions,
    )
    from ..models.alerts_active_count_response_200_zones import AlertsActiveCountResponse200Zones


T = TypeVar("T", bound="AlertsActiveCountResponse200")


@_attrs_define
class AlertsActiveCountResponse200:
    """
    Attributes:
        total (Union[Unset, int]): The total number of active alerts
        land (Union[Unset, int]): The total number of active alerts affecting land zones
        marine (Union[Unset, int]): The total number of active alerts affecting marine zones
        regions (Union[Unset, AlertsActiveCountResponse200Regions]): Active alerts by marine region
        areas (Union[Unset, AlertsActiveCountResponse200Areas]): Active alerts by area (state/territory)
        zones (Union[Unset, AlertsActiveCountResponse200Zones]): Active alerts by NWS public zone or county code
    """

    total: Union[Unset, int] = UNSET
    land: Union[Unset, int] = UNSET
    marine: Union[Unset, int] = UNSET
    regions: Union[Unset, "AlertsActiveCountResponse200Regions"] = UNSET
    areas: Union[Unset, "AlertsActiveCountResponse200Areas"] = UNSET
    zones: Union[Unset, "AlertsActiveCountResponse200Zones"] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        total = self.total

        land = self.land

        marine = self.marine

        regions: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.regions, Unset):
            regions = self.regions.to_dict()

        areas: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.areas, Unset):
            areas = self.areas.to_dict()

        zones: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.zones, Unset):
            zones = self.zones.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if total is not UNSET:
            field_dict["total"] = total
        if land is not UNSET:
            field_dict["land"] = land
        if marine is not UNSET:
            field_dict["marine"] = marine
        if regions is not UNSET:
            field_dict["regions"] = regions
        if areas is not UNSET:
            field_dict["areas"] = areas
        if zones is not UNSET:
            field_dict["zones"] = zones

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alerts_active_count_response_200_areas import (
            AlertsActiveCountResponse200Areas,
        )
        from ..models.alerts_active_count_response_200_regions import (
            AlertsActiveCountResponse200Regions,
        )
        from ..models.alerts_active_count_response_200_zones import (
            AlertsActiveCountResponse200Zones,
        )

        d = dict(src_dict)
        total = d.pop("total", UNSET)

        land = d.pop("land", UNSET)

        marine = d.pop("marine", UNSET)

        _regions = d.pop("regions", UNSET)
        regions: Union[Unset, AlertsActiveCountResponse200Regions]
        if isinstance(_regions, Unset):
            regions = UNSET
        else:
            regions = AlertsActiveCountResponse200Regions.from_dict(_regions)

        _areas = d.pop("areas", UNSET)
        areas: Union[Unset, AlertsActiveCountResponse200Areas]
        if isinstance(_areas, Unset):
            areas = UNSET
        else:
            areas = AlertsActiveCountResponse200Areas.from_dict(_areas)

        _zones = d.pop("zones", UNSET)
        zones: Union[Unset, AlertsActiveCountResponse200Zones]
        if isinstance(_zones, Unset):
            zones = UNSET
        else:
            zones = AlertsActiveCountResponse200Zones.from_dict(_zones)

        alerts_active_count_response_200 = cls(
            total=total,
            land=land,
            marine=marine,
            regions=regions,
            areas=areas,
            zones=zones,
        )

        alerts_active_count_response_200.additional_properties = d
        return alerts_active_count_response_200

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
