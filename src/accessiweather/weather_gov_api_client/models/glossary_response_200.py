from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.glossary_response_200_glossary_item import GlossaryResponse200GlossaryItem
    from ..models.json_ld_context_type_1 import JsonLdContextType1


T = TypeVar("T", bound="GlossaryResponse200")


@_attrs_define
class GlossaryResponse200:
    """
    Attributes:
        context (Union['JsonLdContextType1', Unset, list[Any]]):
        glossary (Union[Unset, list['GlossaryResponse200GlossaryItem']]): A list of glossary terms
    """

    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET
    glossary: Union[Unset, list["GlossaryResponse200GlossaryItem"]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        context: Union[Unset, dict[str, Any], list[Any]]
        if isinstance(self.context, Unset):
            context = UNSET
        elif isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        glossary: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.glossary, Unset):
            glossary = []
            for glossary_item_data in self.glossary:
                glossary_item = glossary_item_data.to_dict()
                glossary.append(glossary_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if context is not UNSET:
            field_dict["@context"] = context
        if glossary is not UNSET:
            field_dict["glossary"] = glossary

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.glossary_response_200_glossary_item import GlossaryResponse200GlossaryItem
        from ..models.json_ld_context_type_1 import JsonLdContextType1

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

        glossary = []
        _glossary = d.pop("glossary", UNSET)
        for glossary_item_data in _glossary or []:
            glossary_item = GlossaryResponse200GlossaryItem.from_dict(glossary_item_data)

            glossary.append(glossary_item)

        glossary_response_200 = cls(
            context=context,
            glossary=glossary,
        )

        glossary_response_200.additional_properties = d
        return glossary_response_200

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
