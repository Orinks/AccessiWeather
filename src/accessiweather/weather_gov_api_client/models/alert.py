import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.alert_category import AlertCategory
from ..models.alert_certainty import AlertCertainty
from ..models.alert_message_type import AlertMessageType
from ..models.alert_response import AlertResponse
from ..models.alert_severity import AlertSeverity
from ..models.alert_status import AlertStatus
from ..models.alert_urgency import AlertUrgency
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alert_geocode import AlertGeocode
    from ..models.alert_parameters import AlertParameters
    from ..models.alert_references_item import AlertReferencesItem


T = TypeVar("T", bound="Alert")


@_attrs_define
class Alert:
    """An object representing a public alert message.
    Unless otherwise noted, the fields in this object correspond to the National Weather Service CAP v1.2 specification,
    which extends the OASIS Common Alerting Protocol (CAP) v1.2 specification and USA Integrated Public Alert and
    Warning System (IPAWS) Profile v1.0. Refer to this documentation for more complete information.
    http://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.html http://docs.oasis-open.org/emergency/cap/v1.2/ipaws-
    profile/v1.0/cs01/cap-v1.2-ipaws-profile-cs01.html https://alerts.weather.gov/#technical-notes-v12

        Attributes:
            id (Union[Unset, str]): The identifier of the alert message.
            area_desc (Union[Unset, str]): A textual description of the area affected by the alert.
            geocode (Union[Unset, AlertGeocode]): Lists of codes for NWS public zones and counties affected by the alert.
            affected_zones (Union[Unset, list[str]]): An array of API links for zones affected by the alert. This is an API-
                specific extension field and is not part of the CAP specification.
            references (Union[Unset, list['AlertReferencesItem']]): A list of prior alerts that this alert updates or
                replaces.
            sent (Union[Unset, datetime.datetime]): The time of the origination of the alert message.
            effective (Union[Unset, datetime.datetime]): The effective time of the information of the alert message.
            onset (Union[None, Unset, datetime.datetime]): The expected time of the beginning of the subject event of the
                alert message.
            expires (Union[Unset, datetime.datetime]): The expiry time of the information of the alert message.
            ends (Union[None, Unset, datetime.datetime]): The expected end time of the subject event of the alert message.
            status (Union[Unset, AlertStatus]):
            message_type (Union[Unset, AlertMessageType]):
            category (Union[Unset, AlertCategory]): The code denoting the category of the subject event of the alert
                message.
            severity (Union[Unset, AlertSeverity]):
            certainty (Union[Unset, AlertCertainty]):
            urgency (Union[Unset, AlertUrgency]):
            event (Union[Unset, str]): The text denoting the type of the subject event of the alert message.
            sender (Union[Unset, str]): Email address of the NWS webmaster.
            sender_name (Union[Unset, str]): The text naming the originator of the alert message.
            headline (Union[None, Unset, str]): The text headline of the alert message.
            description (Union[Unset, str]): The text describing the subject event of the alert message.
            instruction (Union[None, Unset, str]): The text describing the recommended action to be taken by recipients of
                the alert message.
            response (Union[Unset, AlertResponse]): The code denoting the type of action recommended for the target
                audience.
                This corresponds to responseType in the CAP specification.
            parameters (Union[Unset, AlertParameters]): System-specific additional parameters associated with the alert
                message.
                The keys in this object correspond to parameter definitions in the NWS CAP specification.
    """

    id: Union[Unset, str] = UNSET
    area_desc: Union[Unset, str] = UNSET
    geocode: Union[Unset, "AlertGeocode"] = UNSET
    affected_zones: Union[Unset, list[str]] = UNSET
    references: Union[Unset, list["AlertReferencesItem"]] = UNSET
    sent: Union[Unset, datetime.datetime] = UNSET
    effective: Union[Unset, datetime.datetime] = UNSET
    onset: Union[None, Unset, datetime.datetime] = UNSET
    expires: Union[Unset, datetime.datetime] = UNSET
    ends: Union[None, Unset, datetime.datetime] = UNSET
    status: Union[Unset, AlertStatus] = UNSET
    message_type: Union[Unset, AlertMessageType] = UNSET
    category: Union[Unset, AlertCategory] = UNSET
    severity: Union[Unset, AlertSeverity] = UNSET
    certainty: Union[Unset, AlertCertainty] = UNSET
    urgency: Union[Unset, AlertUrgency] = UNSET
    event: Union[Unset, str] = UNSET
    sender: Union[Unset, str] = UNSET
    sender_name: Union[Unset, str] = UNSET
    headline: Union[None, Unset, str] = UNSET
    description: Union[Unset, str] = UNSET
    instruction: Union[None, Unset, str] = UNSET
    response: Union[Unset, AlertResponse] = UNSET
    parameters: Union[Unset, "AlertParameters"] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        area_desc = self.area_desc

        geocode: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.geocode, Unset):
            geocode = self.geocode.to_dict()

        affected_zones: Union[Unset, list[str]] = UNSET
        if not isinstance(self.affected_zones, Unset):
            affected_zones = self.affected_zones

        references: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.references, Unset):
            references = []
            for references_item_data in self.references:
                references_item = references_item_data.to_dict()
                references.append(references_item)

        sent: Union[Unset, str] = UNSET
        if not isinstance(self.sent, Unset):
            sent = self.sent.isoformat()

        effective: Union[Unset, str] = UNSET
        if not isinstance(self.effective, Unset):
            effective = self.effective.isoformat()

        onset: Union[None, Unset, str]
        if isinstance(self.onset, Unset):
            onset = UNSET
        elif isinstance(self.onset, datetime.datetime):
            onset = self.onset.isoformat()
        else:
            onset = self.onset

        expires: Union[Unset, str] = UNSET
        if not isinstance(self.expires, Unset):
            expires = self.expires.isoformat()

        ends: Union[None, Unset, str]
        if isinstance(self.ends, Unset):
            ends = UNSET
        elif isinstance(self.ends, datetime.datetime):
            ends = self.ends.isoformat()
        else:
            ends = self.ends

        status: Union[Unset, str] = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        message_type: Union[Unset, str] = UNSET
        if not isinstance(self.message_type, Unset):
            message_type = self.message_type.value

        category: Union[Unset, str] = UNSET
        if not isinstance(self.category, Unset):
            category = self.category.value

        severity: Union[Unset, str] = UNSET
        if not isinstance(self.severity, Unset):
            severity = self.severity.value

        certainty: Union[Unset, str] = UNSET
        if not isinstance(self.certainty, Unset):
            certainty = self.certainty.value

        urgency: Union[Unset, str] = UNSET
        if not isinstance(self.urgency, Unset):
            urgency = self.urgency.value

        event = self.event

        sender = self.sender

        sender_name = self.sender_name

        headline: Union[None, Unset, str]
        if isinstance(self.headline, Unset):
            headline = UNSET
        else:
            headline = self.headline

        description = self.description

        instruction: Union[None, Unset, str]
        if isinstance(self.instruction, Unset):
            instruction = UNSET
        else:
            instruction = self.instruction

        response: Union[Unset, str] = UNSET
        if not isinstance(self.response, Unset):
            response = self.response.value

        parameters: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.parameters, Unset):
            parameters = self.parameters.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if area_desc is not UNSET:
            field_dict["areaDesc"] = area_desc
        if geocode is not UNSET:
            field_dict["geocode"] = geocode
        if affected_zones is not UNSET:
            field_dict["affectedZones"] = affected_zones
        if references is not UNSET:
            field_dict["references"] = references
        if sent is not UNSET:
            field_dict["sent"] = sent
        if effective is not UNSET:
            field_dict["effective"] = effective
        if onset is not UNSET:
            field_dict["onset"] = onset
        if expires is not UNSET:
            field_dict["expires"] = expires
        if ends is not UNSET:
            field_dict["ends"] = ends
        if status is not UNSET:
            field_dict["status"] = status
        if message_type is not UNSET:
            field_dict["messageType"] = message_type
        if category is not UNSET:
            field_dict["category"] = category
        if severity is not UNSET:
            field_dict["severity"] = severity
        if certainty is not UNSET:
            field_dict["certainty"] = certainty
        if urgency is not UNSET:
            field_dict["urgency"] = urgency
        if event is not UNSET:
            field_dict["event"] = event
        if sender is not UNSET:
            field_dict["sender"] = sender
        if sender_name is not UNSET:
            field_dict["senderName"] = sender_name
        if headline is not UNSET:
            field_dict["headline"] = headline
        if description is not UNSET:
            field_dict["description"] = description
        if instruction is not UNSET:
            field_dict["instruction"] = instruction
        if response is not UNSET:
            field_dict["response"] = response
        if parameters is not UNSET:
            field_dict["parameters"] = parameters

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alert_geocode import AlertGeocode
        from ..models.alert_parameters import AlertParameters
        from ..models.alert_references_item import AlertReferencesItem

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        area_desc = d.pop("areaDesc", UNSET)

        _geocode = d.pop("geocode", UNSET)
        geocode: Union[Unset, AlertGeocode]
        if isinstance(_geocode, Unset):
            geocode = UNSET
        else:
            geocode = AlertGeocode.from_dict(_geocode)

        affected_zones = cast(list[str], d.pop("affectedZones", UNSET))

        references = []
        _references = d.pop("references", UNSET)
        for references_item_data in _references or []:
            references_item = AlertReferencesItem.from_dict(references_item_data)

            references.append(references_item)

        _sent = d.pop("sent", UNSET)
        sent: Union[Unset, datetime.datetime]
        if isinstance(_sent, Unset):
            sent = UNSET
        else:
            sent = isoparse(_sent)

        _effective = d.pop("effective", UNSET)
        effective: Union[Unset, datetime.datetime]
        if isinstance(_effective, Unset):
            effective = UNSET
        else:
            effective = isoparse(_effective)

        def _parse_onset(data: object) -> Union[None, Unset, datetime.datetime]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                onset_type_0 = isoparse(data)

                return onset_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, datetime.datetime], data)

        onset = _parse_onset(d.pop("onset", UNSET))

        _expires = d.pop("expires", UNSET)
        expires: Union[Unset, datetime.datetime]
        if isinstance(_expires, Unset):
            expires = UNSET
        else:
            expires = isoparse(_expires)

        def _parse_ends(data: object) -> Union[None, Unset, datetime.datetime]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                ends_type_0 = isoparse(data)

                return ends_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, datetime.datetime], data)

        ends = _parse_ends(d.pop("ends", UNSET))

        _status = d.pop("status", UNSET)
        status: Union[Unset, AlertStatus]
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = AlertStatus(_status)

        _message_type = d.pop("messageType", UNSET)
        message_type: Union[Unset, AlertMessageType]
        if isinstance(_message_type, Unset):
            message_type = UNSET
        else:
            message_type = AlertMessageType(_message_type)

        _category = d.pop("category", UNSET)
        category: Union[Unset, AlertCategory]
        if isinstance(_category, Unset):
            category = UNSET
        else:
            category = AlertCategory(_category)

        _severity = d.pop("severity", UNSET)
        severity: Union[Unset, AlertSeverity]
        if isinstance(_severity, Unset):
            severity = UNSET
        else:
            severity = AlertSeverity(_severity)

        _certainty = d.pop("certainty", UNSET)
        certainty: Union[Unset, AlertCertainty]
        if isinstance(_certainty, Unset):
            certainty = UNSET
        else:
            certainty = AlertCertainty(_certainty)

        _urgency = d.pop("urgency", UNSET)
        urgency: Union[Unset, AlertUrgency]
        if isinstance(_urgency, Unset):
            urgency = UNSET
        else:
            urgency = AlertUrgency(_urgency)

        event = d.pop("event", UNSET)

        sender = d.pop("sender", UNSET)

        sender_name = d.pop("senderName", UNSET)

        def _parse_headline(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        headline = _parse_headline(d.pop("headline", UNSET))

        description = d.pop("description", UNSET)

        def _parse_instruction(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        instruction = _parse_instruction(d.pop("instruction", UNSET))

        _response = d.pop("response", UNSET)
        response: Union[Unset, AlertResponse]
        if isinstance(_response, Unset):
            response = UNSET
        else:
            response = AlertResponse(_response)

        _parameters = d.pop("parameters", UNSET)
        parameters: Union[Unset, AlertParameters]
        if isinstance(_parameters, Unset):
            parameters = UNSET
        else:
            parameters = AlertParameters.from_dict(_parameters)

        alert = cls(
            id=id,
            area_desc=area_desc,
            geocode=geocode,
            affected_zones=affected_zones,
            references=references,
            sent=sent,
            effective=effective,
            onset=onset,
            expires=expires,
            ends=ends,
            status=status,
            message_type=message_type,
            category=category,
            severity=severity,
            certainty=certainty,
            urgency=urgency,
            event=event,
            sender=sender,
            sender_name=sender_name,
            headline=headline,
            description=description,
            instruction=instruction,
            response=response,
            parameters=parameters,
        )

        alert.additional_properties = d
        return alert

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
