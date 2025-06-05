from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alert_atom_entry_author import AlertAtomEntryAuthor
    from ..models.alert_xml_parameter import AlertXMLParameter


T = TypeVar("T", bound="AlertAtomEntry")


@_attrs_define
class AlertAtomEntry:
    """An alert entry in an Atom feed

    Attributes:
        id (Union[Unset, str]):
        updated (Union[Unset, str]):
        published (Union[Unset, str]):
        author (Union[Unset, AlertAtomEntryAuthor]):
        summary (Union[Unset, str]):
        event (Union[Unset, str]):
        sent (Union[Unset, str]):
        effective (Union[Unset, str]):
        expires (Union[Unset, str]):
        status (Union[Unset, str]):
        msg_type (Union[Unset, str]):
        category (Union[Unset, str]):
        urgency (Union[Unset, str]):
        severity (Union[Unset, str]):
        certainty (Union[Unset, str]):
        area_desc (Union[Unset, str]):
        polygon (Union[Unset, str]):
        geocode (Union[Unset, list['AlertXMLParameter']]):
        parameter (Union[Unset, list['AlertXMLParameter']]):
    """

    id: Union[Unset, str] = UNSET
    updated: Union[Unset, str] = UNSET
    published: Union[Unset, str] = UNSET
    author: Union[Unset, "AlertAtomEntryAuthor"] = UNSET
    summary: Union[Unset, str] = UNSET
    event: Union[Unset, str] = UNSET
    sent: Union[Unset, str] = UNSET
    effective: Union[Unset, str] = UNSET
    expires: Union[Unset, str] = UNSET
    status: Union[Unset, str] = UNSET
    msg_type: Union[Unset, str] = UNSET
    category: Union[Unset, str] = UNSET
    urgency: Union[Unset, str] = UNSET
    severity: Union[Unset, str] = UNSET
    certainty: Union[Unset, str] = UNSET
    area_desc: Union[Unset, str] = UNSET
    polygon: Union[Unset, str] = UNSET
    geocode: Union[Unset, list["AlertXMLParameter"]] = UNSET
    parameter: Union[Unset, list["AlertXMLParameter"]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        updated = self.updated

        published = self.published

        author: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.author, Unset):
            author = self.author.to_dict()

        summary = self.summary

        event = self.event

        sent = self.sent

        effective = self.effective

        expires = self.expires

        status = self.status

        msg_type = self.msg_type

        category = self.category

        urgency = self.urgency

        severity = self.severity

        certainty = self.certainty

        area_desc = self.area_desc

        polygon = self.polygon

        geocode: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.geocode, Unset):
            geocode = []
            for geocode_item_data in self.geocode:
                geocode_item = geocode_item_data.to_dict()
                geocode.append(geocode_item)

        parameter: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.parameter, Unset):
            parameter = []
            for parameter_item_data in self.parameter:
                parameter_item = parameter_item_data.to_dict()
                parameter.append(parameter_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if updated is not UNSET:
            field_dict["updated"] = updated
        if published is not UNSET:
            field_dict["published"] = published
        if author is not UNSET:
            field_dict["author"] = author
        if summary is not UNSET:
            field_dict["summary"] = summary
        if event is not UNSET:
            field_dict["event"] = event
        if sent is not UNSET:
            field_dict["sent"] = sent
        if effective is not UNSET:
            field_dict["effective"] = effective
        if expires is not UNSET:
            field_dict["expires"] = expires
        if status is not UNSET:
            field_dict["status"] = status
        if msg_type is not UNSET:
            field_dict["msgType"] = msg_type
        if category is not UNSET:
            field_dict["category"] = category
        if urgency is not UNSET:
            field_dict["urgency"] = urgency
        if severity is not UNSET:
            field_dict["severity"] = severity
        if certainty is not UNSET:
            field_dict["certainty"] = certainty
        if area_desc is not UNSET:
            field_dict["areaDesc"] = area_desc
        if polygon is not UNSET:
            field_dict["polygon"] = polygon
        if geocode is not UNSET:
            field_dict["geocode"] = geocode
        if parameter is not UNSET:
            field_dict["parameter"] = parameter

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alert_atom_entry_author import AlertAtomEntryAuthor
        from ..models.alert_xml_parameter import AlertXMLParameter

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        updated = d.pop("updated", UNSET)

        published = d.pop("published", UNSET)

        _author = d.pop("author", UNSET)
        author: Union[Unset, AlertAtomEntryAuthor]
        if isinstance(_author, Unset):
            author = UNSET
        else:
            author = AlertAtomEntryAuthor.from_dict(_author)

        summary = d.pop("summary", UNSET)

        event = d.pop("event", UNSET)

        sent = d.pop("sent", UNSET)

        effective = d.pop("effective", UNSET)

        expires = d.pop("expires", UNSET)

        status = d.pop("status", UNSET)

        msg_type = d.pop("msgType", UNSET)

        category = d.pop("category", UNSET)

        urgency = d.pop("urgency", UNSET)

        severity = d.pop("severity", UNSET)

        certainty = d.pop("certainty", UNSET)

        area_desc = d.pop("areaDesc", UNSET)

        polygon = d.pop("polygon", UNSET)

        geocode = []
        _geocode = d.pop("geocode", UNSET)
        for geocode_item_data in _geocode or []:
            geocode_item = AlertXMLParameter.from_dict(geocode_item_data)

            geocode.append(geocode_item)

        parameter = []
        _parameter = d.pop("parameter", UNSET)
        for parameter_item_data in _parameter or []:
            parameter_item = AlertXMLParameter.from_dict(parameter_item_data)

            parameter.append(parameter_item)

        alert_atom_entry = cls(
            id=id,
            updated=updated,
            published=published,
            author=author,
            summary=summary,
            event=event,
            sent=sent,
            effective=effective,
            expires=expires,
            status=status,
            msg_type=msg_type,
            category=category,
            urgency=urgency,
            severity=severity,
            certainty=certainty,
            area_desc=area_desc,
            polygon=polygon,
            geocode=geocode,
            parameter=parameter,
        )

        alert_atom_entry.additional_properties = d
        return alert_atom_entry

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
