from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.alert import Alert


T = TypeVar("T", bound="AlertCollectionGeoJsonFeaturesItem")


@_attrs_define
class AlertCollectionGeoJsonFeaturesItem:
    """
    Attributes:
        properties (Union[Unset, Alert]): An object representing a public alert message.
            Unless otherwise noted, the fields in this object correspond to the National Weather Service CAP v1.2
            specification, which extends the OASIS Common Alerting Protocol (CAP) v1.2 specification and USA Integrated
            Public Alert and Warning System (IPAWS) Profile v1.0. Refer to this documentation for more complete information.
            http://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.html http://docs.oasis-
            open.org/emergency/cap/v1.2/ipaws-profile/v1.0/cs01/cap-v1.2-ipaws-profile-cs01.html
            https://alerts.weather.gov/#technical-notes-v12
    """

    properties: Union[Unset, "Alert"] = UNSET
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
        from ..models.alert import Alert

        d = dict(src_dict)
        _properties = d.pop("properties", UNSET)
        properties: Union[Unset, Alert]
        if isinstance(_properties, Unset):
            properties = UNSET
        else:
            properties = Alert.from_dict(_properties)

        alert_collection_geo_json_features_item = cls(
            properties=properties,
        )

        alert_collection_geo_json_features_item.additional_properties = d
        return alert_collection_geo_json_features_item

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
