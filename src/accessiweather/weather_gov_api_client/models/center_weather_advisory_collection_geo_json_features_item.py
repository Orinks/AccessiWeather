from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.center_weather_advisory import CenterWeatherAdvisory


T = TypeVar("T", bound="CenterWeatherAdvisoryCollectionGeoJsonFeaturesItem")


@_attrs_define
class CenterWeatherAdvisoryCollectionGeoJsonFeaturesItem:
    """
    Attributes:
        properties (Union[Unset, CenterWeatherAdvisory]):
    """

    properties: Union[Unset, "CenterWeatherAdvisory"] = UNSET
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
        from ..models.center_weather_advisory import CenterWeatherAdvisory

        d = dict(src_dict)
        _properties = d.pop("properties", UNSET)
        properties: Union[Unset, CenterWeatherAdvisory]
        if isinstance(_properties, Unset):
            properties = UNSET
        else:
            properties = CenterWeatherAdvisory.from_dict(_properties)

        center_weather_advisory_collection_geo_json_features_item = cls(
            properties=properties,
        )

        center_weather_advisory_collection_geo_json_features_item.additional_properties = d
        return center_weather_advisory_collection_geo_json_features_item

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
