from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.quantitative_value import QuantitativeValue


T = TypeVar("T", bound="RelativeLocation")


@_attrs_define
class RelativeLocation:
    """
    Attributes:
        city (Union[Unset, str]):
        state (Union[Unset, str]):
        distance (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
        bearing (Union[Unset, QuantitativeValue]): A structured value representing a measurement and its unit of
            measure. This object is a slighly modified version of the schema.org definition at
            https://schema.org/QuantitativeValue
    """

    city: Union[Unset, str] = UNSET
    state: Union[Unset, str] = UNSET
    distance: Union[Unset, "QuantitativeValue"] = UNSET
    bearing: Union[Unset, "QuantitativeValue"] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        city = self.city

        state = self.state

        distance: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.distance, Unset):
            distance = self.distance.to_dict()

        bearing: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.bearing, Unset):
            bearing = self.bearing.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if city is not UNSET:
            field_dict["city"] = city
        if state is not UNSET:
            field_dict["state"] = state
        if distance is not UNSET:
            field_dict["distance"] = distance
        if bearing is not UNSET:
            field_dict["bearing"] = bearing

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.quantitative_value import QuantitativeValue

        d = dict(src_dict)
        city = d.pop("city", UNSET)

        state = d.pop("state", UNSET)

        _distance = d.pop("distance", UNSET)
        distance: Union[Unset, QuantitativeValue]
        if isinstance(_distance, Unset):
            distance = UNSET
        else:
            distance = QuantitativeValue.from_dict(_distance)

        _bearing = d.pop("bearing", UNSET)
        bearing: Union[Unset, QuantitativeValue]
        if isinstance(_bearing, Unset):
            bearing = UNSET
        else:
            bearing = QuantitativeValue.from_dict(_bearing)

        relative_location = cls(
            city=city,
            state=state,
            distance=distance,
            bearing=bearing,
        )

        relative_location.additional_properties = d
        return relative_location

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
