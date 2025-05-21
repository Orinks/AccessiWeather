from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alert import Alert


T = TypeVar("T", bound="AlertJsonLd")


@_attrs_define
class AlertJsonLd:
    """
    Attributes:
        graph (Union[Unset, list['Alert']]):
    """

    graph: Union[Unset, list["Alert"]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        graph: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.graph, Unset):
            graph = []
            for graph_item_data in self.graph:
                graph_item = graph_item_data.to_dict()
                graph.append(graph_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if graph is not UNSET:
            field_dict["@graph"] = graph

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alert import Alert

        d = dict(src_dict)
        graph = []
        _graph = d.pop("@graph", UNSET)
        for graph_item_data in _graph or []:
            graph_item = Alert.from_dict(graph_item_data)

            graph.append(graph_item)

        alert_json_ld = cls(
            graph=graph,
        )

        alert_json_ld.additional_properties = d
        return alert_json_ld

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
