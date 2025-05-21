from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_ld_context_type_1 import JsonLdContextType1
    from ..models.text_product_location_collection_locations import (
        TextProductLocationCollectionLocations,
    )


T = TypeVar("T", bound="TextProductLocationCollection")


@_attrs_define
class TextProductLocationCollection:
    """
    Attributes:
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        locations (Union[Unset, TextProductLocationCollectionLocations]):
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    locations: Union[Unset, "TextProductLocationCollectionLocations"] = UNSET

    def to_dict(self) -> dict[str, Any]:
        context: Union[Unset, dict[str, Any], list[Any]]
        if isinstance(self.context, Unset):
            context = UNSET
        elif isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        locations: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.locations, Unset):
            locations = self.locations.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if context is not UNSET:
            field_dict["@context"] = context
        if locations is not UNSET:
            field_dict["locations"] = locations

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.json_ld_context_type_1 import JsonLdContextType1
        from ..models.text_product_location_collection_locations import (
            TextProductLocationCollectionLocations,
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

        _locations = d.pop("locations", UNSET)
        locations: Union[Unset, TextProductLocationCollectionLocations]
        if isinstance(_locations, Unset):
            locations = UNSET
        else:
            locations = TextProductLocationCollectionLocations.from_dict(_locations)

        text_product_location_collection = cls(
            context=context,
            locations=locations,
        )

        return text_product_location_collection
