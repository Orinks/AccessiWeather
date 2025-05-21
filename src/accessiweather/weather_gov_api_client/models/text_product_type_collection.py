from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.text_product_type_collection_graph_item import TextProductTypeCollectionGraphItem


T = TypeVar("T", bound="TextProductTypeCollection")


@_attrs_define
class TextProductTypeCollection:
    """
    Attributes:
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        graph (Union[Unset, list['TextProductTypeCollectionGraphItem']]):
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    graph: Union[Unset, list["TextProductTypeCollectionGraphItem"]] = UNSET

    def to_dict(self) -> dict[str, Any]:
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
        field_dict.update({})
        if context is not UNSET:
            field_dict["@context"] = context
        if graph is not UNSET:
            field_dict["@graph"] = graph

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.text_product_type_collection_graph_item import (
            TextProductTypeCollectionGraphItem,
        )

        d = dict(src_dict)

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
            graph_item = TextProductTypeCollectionGraphItem.from_dict(graph_item_data)

            graph.append(graph_item)

        text_product_type_collection = cls(
            context=context,
            graph=graph,
        )

        return text_product_type_collection
