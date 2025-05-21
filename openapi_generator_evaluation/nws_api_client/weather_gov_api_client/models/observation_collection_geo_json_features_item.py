from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.observation import Observation


T = TypeVar("T", bound="ObservationCollectionGeoJsonFeaturesItem")


@_attrs_define
class ObservationCollectionGeoJsonFeaturesItem:
    """
    Attributes:
        properties (Union[Unset, Observation]):
    """

    properties: Union[Unset, "Observation"] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        properties: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.properties, Unset):
            properties = self.properties.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if properties is not UNSET:
            field_dict["properties"] = properties

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.observation import Observation

        d = dict(src_dict)
        _properties = d.pop("properties", UNSET)
        properties: Union[Unset, Observation]
        if isinstance(_properties, Unset):
            properties = UNSET
        else:
            properties = Observation.from_dict(_properties)

        observation_collection_geo_json_features_item = cls(
            properties=properties,
        )

        observation_collection_geo_json_features_item.additional_properties = d
        return observation_collection_geo_json_features_item

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
