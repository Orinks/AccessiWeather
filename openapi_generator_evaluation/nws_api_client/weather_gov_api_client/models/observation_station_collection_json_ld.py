from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.observation_station import ObservationStation
    from ..models.pagination_info import PaginationInfo


T = TypeVar("T", bound="ObservationStationCollectionJsonLd")


@_attrs_define
class ObservationStationCollectionJsonLd:
    """
    Attributes:
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        graph (Union[Unset, list['ObservationStation']]):
        observation_stations (Union[Unset, list[str]]):
        pagination (Union[Unset, PaginationInfo]): Links for retrieving more data from paged data sets
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    graph: Union[Unset, list["ObservationStation"]] = UNSET
    observation_stations: Union[Unset, list[str]] = UNSET
    pagination: Union[Unset, "PaginationInfo"] = UNSET

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

        observation_stations: Union[Unset, list[str]] = UNSET
        if not isinstance(self.observation_stations, Unset):
            observation_stations = self.observation_stations

        pagination: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.pagination, Unset):
            pagination = self.pagination.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if context is not UNSET:
            field_dict["@context"] = context
        if graph is not UNSET:
            field_dict["@graph"] = graph
        if observation_stations is not UNSET:
            field_dict["observationStations"] = observation_stations
        if pagination is not UNSET:
            field_dict["pagination"] = pagination

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.observation_station import ObservationStation
        from ..models.pagination_info import PaginationInfo

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
            graph_item = ObservationStation.from_dict(graph_item_data)

            graph.append(graph_item)

        observation_stations = cast(list[str], d.pop("observationStations", UNSET))

        _pagination = d.pop("pagination", UNSET)
        pagination: Union[Unset, PaginationInfo]
        if isinstance(_pagination, Unset):
            pagination = UNSET
        else:
            pagination = PaginationInfo.from_dict(_pagination)

        observation_station_collection_json_ld = cls(
            context=context,
            graph=graph,
            observation_stations=observation_stations,
            pagination=pagination,
        )

        return observation_station_collection_json_ld
