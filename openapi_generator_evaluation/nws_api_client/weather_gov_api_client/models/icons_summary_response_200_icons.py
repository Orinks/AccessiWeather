from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.icons_summary_response_200_icons_additional_property import (
        IconsSummaryResponse200IconsAdditionalProperty,
    )


T = TypeVar("T", bound="IconsSummaryResponse200Icons")


@_attrs_define
class IconsSummaryResponse200Icons:
    """ """

    additional_properties: dict[str, "IconsSummaryResponse200IconsAdditionalProperty"] = (
        _attrs_field(init=False, factory=dict)
    )

    def to_dict(self) -> dict[str, Any]:
        field_dict: dict[str, Any] = {}
        for prop_name, prop in self.additional_properties.items():
            field_dict[prop_name] = prop.to_dict()

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.icons_summary_response_200_icons_additional_property import (
            IconsSummaryResponse200IconsAdditionalProperty,
        )

        d = dict(src_dict)
        icons_summary_response_200_icons = cls()

        additional_properties = {}
        for prop_name, prop_dict in d.items():
            additional_property = IconsSummaryResponse200IconsAdditionalProperty.from_dict(
                prop_dict
            )

            additional_properties[prop_name] = additional_property

        icons_summary_response_200_icons.additional_properties = additional_properties
        return icons_summary_response_200_icons

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> "IconsSummaryResponse200IconsAdditionalProperty":
        return self.additional_properties[key]

    def __setitem__(
        self, key: str, value: "IconsSummaryResponse200IconsAdditionalProperty"
    ) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
