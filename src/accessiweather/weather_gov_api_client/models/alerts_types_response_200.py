from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertsTypesResponse200")


@_attrs_define
class AlertsTypesResponse200:
    """
    Attributes:
        event_types (Union[Unset, list[str]]): A list of recognized event types
    """

    event_types: Union[Unset, list[str]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        event_types: Union[Unset, list[str]] = UNSET
        if not isinstance(self.event_types, Unset):
            event_types = self.event_types

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if event_types is not UNSET:
            field_dict["eventTypes"] = event_types

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        event_types = cast(list[str], d.pop("eventTypes", UNSET))

        alerts_types_response_200 = cls(
            event_types=event_types,
        )

        alerts_types_response_200.additional_properties = d
        return alerts_types_response_200

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
