from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.gridpoint_quantitative_value_layer_values_item import (
        GridpointQuantitativeValueLayerValuesItem,
    )


T = TypeVar("T", bound="GridpointQuantitativeValueLayer")


@_attrs_define
class GridpointQuantitativeValueLayer:
    """A gridpoint layer consisting of quantitative values (numeric values with associated units of measure).

    Attributes:
        values (list['GridpointQuantitativeValueLayerValuesItem']):
        uom (Union[Unset, str]): A string denoting a unit of measure, expressed in the format "{unit}" or
            "{namespace}:{unit}".
            Units with the namespace "wmo" or "wmoUnit" are defined in the World Meteorological Organization Codes Registry
            at http://codes.wmo.int/common/unit and should be canonically resolvable to
            http://codes.wmo.int/common/unit/{unit}.
            Units with the namespace "nwsUnit" are currently custom and do not align to any standard.
            Units with no namespace or the namespace "uc" are compliant with the Unified Code for Units of Measure syntax
            defined at https://unitsofmeasure.org/. This also aligns with recent versions of the Geographic Markup Language
            (GML) standard, the IWXXM standard, and OGC Observations and Measurements v2.0 (ISO/DIS 19156).
            Namespaced units are considered deprecated. We will be aligning API to use the same standards as GML/IWXXM in
            the future.
    """

    values: list["GridpointQuantitativeValueLayerValuesItem"]
    uom: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        values = []
        for values_item_data in self.values:
            values_item = values_item_data.to_dict()
            values.append(values_item)

        uom = self.uom

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "values": values,
            }
        )
        if uom is not UNSET:
            field_dict["uom"] = uom

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.gridpoint_quantitative_value_layer_values_item import (
            GridpointQuantitativeValueLayerValuesItem,
        )

        d = dict(src_dict)
        values = []
        _values = d.pop("values")
        for values_item_data in _values:
            values_item = GridpointQuantitativeValueLayerValuesItem.from_dict(values_item_data)

            values.append(values_item)

        uom = d.pop("uom", UNSET)

        gridpoint_quantitative_value_layer = cls(
            values=values,
            uom=uom,
        )

        gridpoint_quantitative_value_layer.additional_properties = d
        return gridpoint_quantitative_value_layer

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
