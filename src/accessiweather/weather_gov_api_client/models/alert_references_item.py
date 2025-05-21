import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="AlertReferencesItem")


@_attrs_define
class AlertReferencesItem:
    """
    Attributes:
        id (Union[Unset, str]): An API link to the prior alert.
        identifier (Union[Unset, str]): The identifier of the alert message.
        sender (Union[Unset, str]): The sender of the prior alert.
        sent (Union[Unset, datetime.datetime]): The time the prior alert was sent.
    """

    id: Union[Unset, str] = UNSET
    identifier: Union[Unset, str] = UNSET
    sender: Union[Unset, str] = UNSET
    sent: Union[Unset, datetime.datetime] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        identifier = self.identifier

        sender = self.sender

        sent: Union[Unset, str] = UNSET
        if not isinstance(self.sent, Unset):
            sent = self.sent.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["@id"] = id
        if identifier is not UNSET:
            field_dict["identifier"] = identifier
        if sender is not UNSET:
            field_dict["sender"] = sender
        if sent is not UNSET:
            field_dict["sent"] = sent

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("@id", UNSET)

        identifier = d.pop("identifier", UNSET)

        sender = d.pop("sender", UNSET)

        _sent = d.pop("sent", UNSET)
        sent: Union[Unset, datetime.datetime]
        if isinstance(_sent, Unset):
            sent = UNSET
        else:
            sent = isoparse(_sent)

        alert_references_item = cls(
            id=id,
            identifier=identifier,
            sender=sender,
            sent=sent,
        )

        alert_references_item.additional_properties = d
        return alert_references_item

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
