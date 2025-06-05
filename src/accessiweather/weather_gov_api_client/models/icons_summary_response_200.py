from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.icons_summary_response_200_icons import IconsSummaryResponse200Icons
    from ..models.json_ld_context_type_1 import JsonLdContextType1


T = TypeVar("T", bound="IconsSummaryResponse200")


@_attrs_define
class IconsSummaryResponse200:
    """
    Attributes:
        icons (IconsSummaryResponse200Icons):
        context (Union['JsonLdContextType1', Unset, list[Any]]):
    """

    icons: "IconsSummaryResponse200Icons"
    context: Union["JsonLdContextType1", Unset, list[Any]] = UNSET

    def to_dict(self) -> dict[str, Any]:
        icons = self.icons.to_dict()

        context: Union[Unset, dict[str, Any], list[Any]]
        if isinstance(self.context, Unset):
            context = UNSET
        elif isinstance(self.context, list):
            context = self.context

        else:
            context = self.context.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "icons": icons,
            }
        )
        if context is not UNSET:
            field_dict["@context"] = context

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.icons_summary_response_200_icons import IconsSummaryResponse200Icons
        from ..models.json_ld_context_type_1 import JsonLdContextType1

        d = dict(src_dict)
        icons = IconsSummaryResponse200Icons.from_dict(d.pop("icons"))

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

        icons_summary_response_200 = cls(
            icons=icons,
            context=context,
        )

        return icons_summary_response_200
