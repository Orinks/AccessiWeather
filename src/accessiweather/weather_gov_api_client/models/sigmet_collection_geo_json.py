from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.geo_json_feature_collection_type import GeoJsonFeatureCollectionType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.geo_json_feature import GeoJsonFeature
    from ..models.json_ld_context_type_1 import JsonLdContextType1


T = TypeVar("T", bound="SigmetCollectionGeoJson")


@_attrs_define
class SigmetCollectionGeoJson:
    """
    Attributes:
        type_ (GeoJsonFeatureCollectionType):
        features (list['GeoJsonFeature']):
        context (Union['JsonLdContextType1', Unset, list[Any]]):
    """

    type_: GeoJsonFeatureCollectionType
    features: list["GeoJsonFeature"]
    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        features = []
        for features_item_data in self.features:
            features_item = features_item_data.to_dict()
            features.append(features_item)

        context: Union[Unset, dict[str, Any], list[Any]]
        if isinstance(self.context, Unset):
            context = UNSET
        elif isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "features": features,
            }
        )
        if context is not UNSET:
            field_dict["@context"] = context

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.geo_json_feature import GeoJsonFeature
        from ..models.json_ld_context_type_1 import JsonLdContextType1

        d = dict(src_dict)
        type_ = GeoJsonFeatureCollectionType(d.pop("type"))

        features = []
        _features = d.pop("features")
        for features_item_data in _features:
            features_item = GeoJsonFeature.from_dict(features_item_data)

            features.append(features_item)

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

        sigmet_collection_geo_json = cls(
            type_=type_,
            features=features,
            context=context,
        )

        sigmet_collection_geo_json.additional_properties = d
        return sigmet_collection_geo_json

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
