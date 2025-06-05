from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="IconsSummaryResponse200IconsAdditionalProperty")


@_attrs_define
class IconsSummaryResponse200IconsAdditionalProperty:
    """
    Attributes:
        description (str):
    """

    description: str

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "description": description,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        description = d.pop("description")

        icons_summary_response_200_icons_additional_property = cls(
            description=description,
        )

        return icons_summary_response_200_icons_additional_property
