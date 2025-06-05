from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alert_atom_entry import AlertAtomEntry
    from ..models.alert_atom_feed_author import AlertAtomFeedAuthor


T = TypeVar("T", bound="AlertAtomFeed")


@_attrs_define
class AlertAtomFeed:
    """An alert feed in Atom format

    Attributes:
        id (Union[Unset, str]):
        generator (Union[Unset, str]):
        updated (Union[Unset, str]):
        author (Union[Unset, AlertAtomFeedAuthor]):
        title (Union[Unset, str]):
        entry (Union[Unset, list['AlertAtomEntry']]):
    """

    id: Union[Unset, str] = UNSET
    generator: Union[Unset, str] = UNSET
    updated: Union[Unset, str] = UNSET
    author: Union[Unset, "AlertAtomFeedAuthor"] = UNSET
    title: Union[Unset, str] = UNSET
    entry: Union[Unset, list["AlertAtomEntry"]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        generator = self.generator

        updated = self.updated

        author: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.author, Unset):
            author = self.author.to_dict()

        title = self.title

        entry: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.entry, Unset):
            entry = []
            for entry_item_data in self.entry:
                entry_item = entry_item_data.to_dict()
                entry.append(entry_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if generator is not UNSET:
            field_dict["generator"] = generator
        if updated is not UNSET:
            field_dict["updated"] = updated
        if author is not UNSET:
            field_dict["author"] = author
        if title is not UNSET:
            field_dict["title"] = title
        if entry is not UNSET:
            field_dict["entry"] = entry

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alert_atom_entry import AlertAtomEntry
        from ..models.alert_atom_feed_author import AlertAtomFeedAuthor

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        generator = d.pop("generator", UNSET)

        updated = d.pop("updated", UNSET)

        _author = d.pop("author", UNSET)
        author: Union[Unset, AlertAtomFeedAuthor]
        if isinstance(_author, Unset):
            author = UNSET
        else:
            author = AlertAtomFeedAuthor.from_dict(_author)

        title = d.pop("title", UNSET)

        entry = []
        _entry = d.pop("entry", UNSET)
        for entry_item_data in _entry or []:
            entry_item = AlertAtomEntry.from_dict(entry_item_data)

            entry.append(entry_item)

        alert_atom_feed = cls(
            id=id,
            generator=generator,
            updated=updated,
            author=author,
            title=title,
            entry=entry,
        )

        alert_atom_feed.additional_properties = d
        return alert_atom_feed

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
