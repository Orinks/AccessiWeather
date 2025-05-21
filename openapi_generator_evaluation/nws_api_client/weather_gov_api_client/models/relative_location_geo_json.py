from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.geo_json_feature_type import GeoJsonFeatureType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.geo_json_feature_properties import GeoJsonFeatureProperties
    from ..models.geo_json_line_string import GeoJSONLineString
    from ..models.geo_json_multi_line_string import GeoJSONMultiLineString
    from ..models.geo_json_multi_point import GeoJSONMultiPoint
    from ..models.geo_json_multi_polygon import GeoJSONMultiPolygon
    from ..models.geo_json_point import GeoJSONPoint
    from ..models.geo_json_polygon import GeoJSONPolygon
    from ..models.json_ld_context_type_1 import JsonLdContextType1


T = TypeVar("T", bound="RelativeLocationGeoJson")


@_attrs_define
class RelativeLocationGeoJson:
    """
    Attributes:
        type_ (GeoJsonFeatureType):
        geometry (Union['GeoJSONLineString', 'GeoJSONMultiLineString', 'GeoJSONMultiPoint', 'GeoJSONMultiPolygon',
            'GeoJSONPoint', 'GeoJSONPolygon', None]): A GeoJSON geometry object. Please refer to IETF RFC 7946 for
            information on the GeoJSON format.
        properties (GeoJsonFeatureProperties):
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        id (Union[Unset, str]):
    """

    type_: GeoJsonFeatureType
    geometry: Union[
        "GeoJSONLineString",
        "GeoJSONMultiLineString",
        "GeoJSONMultiPoint",
        "GeoJSONMultiPolygon",
        "GeoJSONPoint",
        "GeoJSONPolygon",
        None,
    ]
    properties: "GeoJsonFeatureProperties"
    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    id: Union[Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.geo_json_line_string import GeoJSONLineString
        from ..models.geo_json_multi_line_string import GeoJSONMultiLineString
        from ..models.geo_json_multi_point import GeoJSONMultiPoint
        from ..models.geo_json_multi_polygon import GeoJSONMultiPolygon
        from ..models.geo_json_point import GeoJSONPoint
        from ..models.geo_json_polygon import GeoJSONPolygon

        type_ = self.type_.value

        geometry: Union[None, dict[str, Any]]
        if isinstance(self.geometry, GeoJSONPoint):
            geometry = self.geometry.to_dict()
        elif isinstance(self.geometry, GeoJSONLineString):
            geometry = self.geometry.to_dict()
        elif isinstance(self.geometry, GeoJSONPolygon):
            geometry = self.geometry.to_dict()
        elif isinstance(self.geometry, GeoJSONMultiPoint):
            geometry = self.geometry.to_dict()
        elif isinstance(self.geometry, GeoJSONMultiLineString):
            geometry = self.geometry.to_dict()
        elif isinstance(self.geometry, GeoJSONMultiPolygon):
            geometry = self.geometry.to_dict()
        else:
            geometry = self.geometry

        properties = self.properties.to_dict()

        context: Union[Unset, dict[str, Any], list[Any]]
        if isinstance(self.context, Unset):
            context = UNSET
        elif isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "geometry": geometry,
                "properties": properties,
            }
        )
        if context is not UNSET:
            field_dict["@context"] = context
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.geo_json_feature_properties import GeoJsonFeatureProperties
        from ..models.geo_json_line_string import GeoJSONLineString
        from ..models.geo_json_multi_line_string import GeoJSONMultiLineString
        from ..models.geo_json_multi_point import GeoJSONMultiPoint
        from ..models.geo_json_multi_polygon import GeoJSONMultiPolygon
        from ..models.geo_json_point import GeoJSONPoint
        from ..models.geo_json_polygon import GeoJSONPolygon
        from ..models.json_ld_context_type_1 import JsonLdContextType1

        d = dict(src_dict)
        type_ = GeoJsonFeatureType(d.pop("type"))

        def _parse_geometry(
            data: object,
        ) -> Union[
            "GeoJSONLineString",
            "GeoJSONMultiLineString",
            "GeoJSONMultiPoint",
            "GeoJSONMultiPolygon",
            "GeoJSONPoint",
            "GeoJSONPolygon",
            None,
        ]:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_geo_json_geometry_type_0 = GeoJSONPoint.from_dict(data)

                return componentsschemas_geo_json_geometry_type_0
            except:  # noqa: E722
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_geo_json_geometry_type_1 = GeoJSONLineString.from_dict(data)

                return componentsschemas_geo_json_geometry_type_1
            except:  # noqa: E722
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_geo_json_geometry_type_2 = GeoJSONPolygon.from_dict(data)

                return componentsschemas_geo_json_geometry_type_2
            except:  # noqa: E722
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_geo_json_geometry_type_3 = GeoJSONMultiPoint.from_dict(data)

                return componentsschemas_geo_json_geometry_type_3
            except:  # noqa: E722
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_geo_json_geometry_type_4 = GeoJSONMultiLineString.from_dict(data)

                return componentsschemas_geo_json_geometry_type_4
            except:  # noqa: E722
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_geo_json_geometry_type_5 = GeoJSONMultiPolygon.from_dict(data)

                return componentsschemas_geo_json_geometry_type_5
            except:  # noqa: E722
                pass
            return cast(
                Union[
                    "GeoJSONLineString",
                    "GeoJSONMultiLineString",
                    "GeoJSONMultiPoint",
                    "GeoJSONMultiPolygon",
                    "GeoJSONPoint",
                    "GeoJSONPolygon",
                    None,
                ],
                data,
            )

        geometry = _parse_geometry(d.pop("geometry"))

        properties = GeoJsonFeatureProperties.from_dict(d.pop("properties"))

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

        id = d.pop("id", UNSET)

        relative_location_geo_json = cls(
            type_=type_,
            geometry=geometry,
            properties=properties,
            context=context,
            id=id,
        )

        relative_location_geo_json.additional_properties = d
        return relative_location_geo_json

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
