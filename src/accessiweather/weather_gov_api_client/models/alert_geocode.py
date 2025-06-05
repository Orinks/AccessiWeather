from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertGeocode")


@_attrs_define
class AlertGeocode:
    """Lists of codes for NWS public zones and counties affected by the alert.

    Attributes:
        ugc (Union[Unset, list[str]]): A list of NWS public zone or county identifiers.
        same (Union[Unset, list[str]]): A list of SAME (Specific Area Message Encoding) codes for affected counties.
    """

    ugc: Union[Unset, list[str]] = UNSET
    same: Union[Unset, list[str]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ugc: Union[Unset, list[str]] = UNSET
        if not isinstance(self.ugc, Unset):
            ugc = self.ugc

        same: Union[Unset, list[str]] = UNSET
        if not isinstance(self.same, Unset):
            same = self.same

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if ugc is not UNSET:
            field_dict["UGC"] = ugc
        if same is not UNSET:
            field_dict["SAME"] = same

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        ugc = cast(list[str], d.pop("UGC", UNSET))

        same = cast(list[str], d.pop("SAME", UNSET))

        alert_geocode = cls(
            ugc=ugc,
            same=same,
        )

        alert_geocode.additional_properties = d
        return alert_geocode

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
