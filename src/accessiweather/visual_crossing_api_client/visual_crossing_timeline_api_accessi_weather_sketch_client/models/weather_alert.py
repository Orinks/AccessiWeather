import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="WeatherAlert")


@_attrs_define
class WeatherAlert:
    """
    Attributes:
        event (Union[Unset, str]): Alert title or event name.
        headline (Union[Unset, str]):
        severity (Union[Unset, str]):
        description (Union[Unset, str]):
        onset (Union[Unset, datetime.datetime]):
        ends (Union[Unset, datetime.datetime]):
        id (Union[Unset, str]):
        effective (Union[Unset, datetime.datetime]):
    """

    event: Union[Unset, str] = UNSET
    headline: Union[Unset, str] = UNSET
    severity: Union[Unset, str] = UNSET
    description: Union[Unset, str] = UNSET
    onset: Union[Unset, datetime.datetime] = UNSET
    ends: Union[Unset, datetime.datetime] = UNSET
    id: Union[Unset, str] = UNSET
    effective: Union[Unset, datetime.datetime] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        event = self.event

        headline = self.headline

        severity = self.severity

        description = self.description

        onset: Union[Unset, str] = UNSET
        if not isinstance(self.onset, Unset):
            onset = self.onset.isoformat()

        ends: Union[Unset, str] = UNSET
        if not isinstance(self.ends, Unset):
            ends = self.ends.isoformat()

        id = self.id

        effective: Union[Unset, str] = UNSET
        if not isinstance(self.effective, Unset):
            effective = self.effective.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if event is not UNSET:
            field_dict["event"] = event
        if headline is not UNSET:
            field_dict["headline"] = headline
        if severity is not UNSET:
            field_dict["severity"] = severity
        if description is not UNSET:
            field_dict["description"] = description
        if onset is not UNSET:
            field_dict["onset"] = onset
        if ends is not UNSET:
            field_dict["ends"] = ends
        if id is not UNSET:
            field_dict["id"] = id
        if effective is not UNSET:
            field_dict["effective"] = effective

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        event = d.pop("event", UNSET)

        headline = d.pop("headline", UNSET)

        severity = d.pop("severity", UNSET)

        description = d.pop("description", UNSET)

        _onset = d.pop("onset", UNSET)
        onset: Union[Unset, datetime.datetime]
        if isinstance(_onset, Unset):
            onset = UNSET
        else:
            onset = isoparse(_onset)

        _ends = d.pop("ends", UNSET)
        ends: Union[Unset, datetime.datetime]
        if isinstance(_ends, Unset):
            ends = UNSET
        else:
            ends = isoparse(_ends)

        id = d.pop("id", UNSET)

        _effective = d.pop("effective", UNSET)
        effective: Union[Unset, datetime.datetime]
        if isinstance(_effective, Unset):
            effective = UNSET
        else:
            effective = isoparse(_effective)

        weather_alert = cls(
            event=event,
            headline=headline,
            severity=severity,
            description=description,
            onset=onset,
            ends=ends,
            id=id,
            effective=effective,
        )

        weather_alert.additional_properties = d
        return weather_alert

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
