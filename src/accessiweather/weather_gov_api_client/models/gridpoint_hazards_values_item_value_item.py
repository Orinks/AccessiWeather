from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="GridpointHazardsValuesItemValueItem")


@_attrs_define
class GridpointHazardsValuesItemValueItem:
    """A value object representing an expected hazard.

    Attributes:
        phenomenon (str): Hazard code. This value will correspond to a P-VTEC phenomenon code as defined in NWS
            Directive 10-1703.
        significance (str): Significance code. This value will correspond to a P-VTEC significance code as defined in
            NWS Directive 10-1703.
            This will most frequently be "A" for a watch or "Y" for an advisory.
        event_number (Union[None, int]): Event number. If this hazard refers to a national or regional center product
            (such as a Storm Prediction Center convective watch), this value will be the sequence number of that product.
    """

    phenomenon: str
    significance: str
    event_number: Union[None, int]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        phenomenon = self.phenomenon

        significance = self.significance

        event_number: Union[None, int]
        event_number = self.event_number

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "phenomenon": phenomenon,
                "significance": significance,
                "event_number": event_number,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        phenomenon = d.pop("phenomenon")

        significance = d.pop("significance")

        def _parse_event_number(data: object) -> Union[None, int]:
            if data is None:
                return data
            return cast(Union[None, int], data)

        event_number = _parse_event_number(d.pop("event_number"))

        gridpoint_hazards_values_item_value_item = cls(
            phenomenon=phenomenon,
            significance=significance,
            event_number=event_number,
        )

        gridpoint_hazards_values_item_value_item.additional_properties = d
        return gridpoint_hazards_values_item_value_item

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
