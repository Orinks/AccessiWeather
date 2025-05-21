from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.geo_json_multi_line_string_type import GeoJSONMultiLineStringType
from ..types import UNSET, Unset

T = TypeVar("T", bound="GeoJSONMultiLineString")


@_attrs_define
class GeoJSONMultiLineString:
    """
    Attributes:
        type_ (GeoJSONMultiLineStringType):
        coordinates (list[list[list[float]]]):
        bbox (Union[Unset, list[float]]): A GeoJSON bounding box. Please refer to IETF RFC 7946 for information on the
            GeoJSON format.
    """

    type_: GeoJSONMultiLineStringType
    coordinates: list[list[list[float]]]
    bbox: Union[Unset, list[float]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        coordinates = []
        for coordinates_item_data in self.coordinates:
            coordinates_item = []
            for componentsschemas_geo_json_line_string_item_data in coordinates_item_data:
                componentsschemas_geo_json_line_string_item = (
                    componentsschemas_geo_json_line_string_item_data
                )

                coordinates_item.append(componentsschemas_geo_json_line_string_item)

            coordinates.append(coordinates_item)

        bbox: Union[Unset, list[float]] = UNSET
        if not isinstance(self.bbox, Unset):
            bbox = self.bbox

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "coordinates": coordinates,
            }
        )
        if bbox is not UNSET:
            field_dict["bbox"] = bbox

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = GeoJSONMultiLineStringType(d.pop("type"))

        coordinates = []
        _coordinates = d.pop("coordinates")
        for coordinates_item_data in _coordinates:
            coordinates_item = []
            _coordinates_item = coordinates_item_data
            for componentsschemas_geo_json_line_string_item_data in _coordinates_item:
                componentsschemas_geo_json_line_string_item = cast(
                    list[float], componentsschemas_geo_json_line_string_item_data
                )

                coordinates_item.append(componentsschemas_geo_json_line_string_item)

            coordinates.append(coordinates_item)

        bbox = cast(list[float], d.pop("bbox", UNSET))

        geo_json_multi_line_string = cls(
            type_=type_,
            coordinates=coordinates,
            bbox=bbox,
        )

        geo_json_multi_line_string.additional_properties = d
        return geo_json_multi_line_string

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
