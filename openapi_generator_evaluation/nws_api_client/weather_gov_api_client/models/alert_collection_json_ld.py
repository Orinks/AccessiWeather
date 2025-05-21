import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alert import Alert
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.pagination_info import PaginationInfo


T = TypeVar("T", bound="AlertCollectionJsonLd")


@_attrs_define
class AlertCollectionJsonLd:
    """
    Attributes:
        title (Union[Unset, str]): A title describing the alert collection
        updated (Union[Unset, datetime.datetime]): The last time a change occurred to this collection
        pagination (Union[Unset, PaginationInfo]): Links for retrieving more data from paged data sets
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        graph (Union[Unset, list['Alert']]):
    """

    title: Union[Unset, str] = UNSET
    updated: Union[Unset, datetime.datetime] = UNSET
    pagination: Union[Unset, "PaginationInfo"] = UNSET
    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    graph: Union[Unset, list["Alert"]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        title = self.title

        updated: Union[Unset, str] = UNSET
        if not isinstance(self.updated, Unset):
            updated = self.updated.isoformat()

        pagination: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.pagination, Unset):
            pagination = self.pagination.to_dict()

        context: Union[Unset, dict[str, Any], list[Any]]
        if isinstance(self.context, Unset):
            context = UNSET
        elif isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        graph: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.graph, Unset):
            graph = []
            for graph_item_data in self.graph:
                graph_item = graph_item_data.to_dict()
                graph.append(graph_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if title is not UNSET:
            field_dict["title"] = title
        if updated is not UNSET:
            field_dict["updated"] = updated
        if pagination is not UNSET:
            field_dict["pagination"] = pagination
        if context is not UNSET:
            field_dict["@context"] = context
        if graph is not UNSET:
            field_dict["@graph"] = graph

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alert import Alert
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.pagination_info import PaginationInfo

        d = dict(src_dict)
        title = d.pop("title", UNSET)

        _updated = d.pop("updated", UNSET)
        updated: Union[Unset, datetime.datetime]
        if isinstance(_updated, Unset):
            updated = UNSET
        else:
            updated = isoparse(_updated)

        _pagination = d.pop("pagination", UNSET)
        pagination: Union[Unset, PaginationInfo]
        if isinstance(_pagination, Unset):
            pagination = UNSET
        else:
            pagination = PaginationInfo.from_dict(_pagination)

        def _parse_context(data: object) -> Union["JsonLdContextType1", Unset, list[Any]]:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_json_ld_context_type_0 = cast(list[Any], data)

                return componentsschemas_json_ld_context_type_0
            except:  # noqa: E722
                pass
            if not isinstance(data, dict):
                raise TypeError()
            componentsschemas_json_ld_context_type_1 = JsonLdContextType1.from_dict(data)

            return componentsschemas_json_ld_context_type_1

        context = _parse_context(d.pop("@context", UNSET))

        graph = []
        _graph = d.pop("@graph", UNSET)
        for graph_item_data in _graph or []:
            graph_item = Alert.from_dict(graph_item_data)

            graph.append(graph_item)

        alert_collection_json_ld = cls(
            title=title,
            updated=updated,
            pagination=pagination,
            context=context,
            graph=graph,
        )

        alert_collection_json_ld.additional_properties = d
        return alert_collection_json_ld

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
