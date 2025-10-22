import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

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
        status (Union[Unset, str]):
        message_type (Union[Unset, str]):
        source (Union[Unset, str]):
        regions (Union[Unset, list[str]]):
        countries (Union[Unset, list[str]]):
        states (Union[Unset, list[str]]):
        zones (Union[Unset, list[str]]):
        areas (Union[Unset, list[str]]):
        instruction (Union[Unset, str]):
        response (Union[Unset, str]):
        certainty (Union[Unset, str]):
        urgency (Union[Unset, str]):
        sent (Union[Unset, datetime.datetime]):
        onset_epoch (Union[Unset, int]):
        ends_epoch (Union[Unset, int]):
        effective_epoch (Union[Unset, int]):
        expires_epoch (Union[Unset, int]):
        references (Union[Unset, list[str]]):
        source_url (Union[Unset, str]):
        expires (Union[Unset, datetime.datetime]):
    """

    event: Union[Unset, str] = UNSET
    headline: Union[Unset, str] = UNSET
    severity: Union[Unset, str] = UNSET
    description: Union[Unset, str] = UNSET
    onset: Union[Unset, datetime.datetime] = UNSET
    ends: Union[Unset, datetime.datetime] = UNSET
    id: Union[Unset, str] = UNSET
    effective: Union[Unset, datetime.datetime] = UNSET
    status: Union[Unset, str] = UNSET
    message_type: Union[Unset, str] = UNSET
    source: Union[Unset, str] = UNSET
    regions: Union[Unset, list[str]] = UNSET
    countries: Union[Unset, list[str]] = UNSET
    states: Union[Unset, list[str]] = UNSET
    zones: Union[Unset, list[str]] = UNSET
    areas: Union[Unset, list[str]] = UNSET
    instruction: Union[Unset, str] = UNSET
    response: Union[Unset, str] = UNSET
    certainty: Union[Unset, str] = UNSET
    urgency: Union[Unset, str] = UNSET
    sent: Union[Unset, datetime.datetime] = UNSET
    onset_epoch: Union[Unset, int] = UNSET
    ends_epoch: Union[Unset, int] = UNSET
    effective_epoch: Union[Unset, int] = UNSET
    expires_epoch: Union[Unset, int] = UNSET
    references: Union[Unset, list[str]] = UNSET
    source_url: Union[Unset, str] = UNSET
    expires: Union[Unset, datetime.datetime] = UNSET
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

        status = self.status

        message_type = self.message_type

        source = self.source

        regions: Union[Unset, list[str]] = UNSET
        if not isinstance(self.regions, Unset):
            regions = self.regions

        countries: Union[Unset, list[str]] = UNSET
        if not isinstance(self.countries, Unset):
            countries = self.countries

        states: Union[Unset, list[str]] = UNSET
        if not isinstance(self.states, Unset):
            states = self.states

        zones: Union[Unset, list[str]] = UNSET
        if not isinstance(self.zones, Unset):
            zones = self.zones

        areas: Union[Unset, list[str]] = UNSET
        if not isinstance(self.areas, Unset):
            areas = self.areas

        instruction = self.instruction

        response = self.response

        certainty = self.certainty

        urgency = self.urgency

        sent: Union[Unset, str] = UNSET
        if not isinstance(self.sent, Unset):
            sent = self.sent.isoformat()

        onset_epoch = self.onset_epoch

        ends_epoch = self.ends_epoch

        effective_epoch = self.effective_epoch

        expires_epoch = self.expires_epoch

        references: Union[Unset, list[str]] = UNSET
        if not isinstance(self.references, Unset):
            references = self.references

        source_url = self.source_url

        expires: Union[Unset, str] = UNSET
        if not isinstance(self.expires, Unset):
            expires = self.expires.isoformat()

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
        if status is not UNSET:
            field_dict["status"] = status
        if message_type is not UNSET:
            field_dict["messageType"] = message_type
        if source is not UNSET:
            field_dict["source"] = source
        if regions is not UNSET:
            field_dict["regions"] = regions
        if countries is not UNSET:
            field_dict["countries"] = countries
        if states is not UNSET:
            field_dict["states"] = states
        if zones is not UNSET:
            field_dict["zones"] = zones
        if areas is not UNSET:
            field_dict["areas"] = areas
        if instruction is not UNSET:
            field_dict["instruction"] = instruction
        if response is not UNSET:
            field_dict["response"] = response
        if certainty is not UNSET:
            field_dict["certainty"] = certainty
        if urgency is not UNSET:
            field_dict["urgency"] = urgency
        if sent is not UNSET:
            field_dict["sent"] = sent
        if onset_epoch is not UNSET:
            field_dict["onsetEpoch"] = onset_epoch
        if ends_epoch is not UNSET:
            field_dict["endsEpoch"] = ends_epoch
        if effective_epoch is not UNSET:
            field_dict["effectiveEpoch"] = effective_epoch
        if expires_epoch is not UNSET:
            field_dict["expiresEpoch"] = expires_epoch
        if references is not UNSET:
            field_dict["references"] = references
        if source_url is not UNSET:
            field_dict["sourceUrl"] = source_url
        if expires is not UNSET:
            field_dict["expires"] = expires

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

        status = d.pop("status", UNSET)

        message_type = d.pop("messageType", UNSET)

        source = d.pop("source", UNSET)

        regions = cast(list[str], d.pop("regions", UNSET))

        countries = cast(list[str], d.pop("countries", UNSET))

        states = cast(list[str], d.pop("states", UNSET))

        zones = cast(list[str], d.pop("zones", UNSET))

        areas = cast(list[str], d.pop("areas", UNSET))

        instruction = d.pop("instruction", UNSET)

        response = d.pop("response", UNSET)

        certainty = d.pop("certainty", UNSET)

        urgency = d.pop("urgency", UNSET)

        _sent = d.pop("sent", UNSET)
        sent: Union[Unset, datetime.datetime]
        if isinstance(_sent, Unset):
            sent = UNSET
        else:
            sent = isoparse(_sent)

        onset_epoch = d.pop("onsetEpoch", UNSET)

        ends_epoch = d.pop("endsEpoch", UNSET)

        effective_epoch = d.pop("effectiveEpoch", UNSET)

        expires_epoch = d.pop("expiresEpoch", UNSET)

        references = cast(list[str], d.pop("references", UNSET))

        source_url = d.pop("sourceUrl", UNSET)

        _expires = d.pop("expires", UNSET)
        expires: Union[Unset, datetime.datetime]
        if isinstance(_expires, Unset):
            expires = UNSET
        else:
            expires = isoparse(_expires)

        weather_alert = cls(
            event=event,
            headline=headline,
            severity=severity,
            description=description,
            onset=onset,
            ends=ends,
            id=id,
            effective=effective,
            status=status,
            message_type=message_type,
            source=source,
            regions=regions,
            countries=countries,
            states=states,
            zones=zones,
            areas=areas,
            instruction=instruction,
            response=response,
            certainty=certainty,
            urgency=urgency,
            sent=sent,
            onset_epoch=onset_epoch,
            ends_epoch=ends_epoch,
            effective_epoch=effective_epoch,
            expires_epoch=expires_epoch,
            references=references,
            source_url=source_url,
            expires=expires,
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
