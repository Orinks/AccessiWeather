from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="PaginationInfo")


@_attrs_define
class PaginationInfo:
    """Links for retrieving more data from paged data sets

    Attributes:
        next_ (str): A link to the next page of records
    """

    next_: str

    def to_dict(self) -> dict[str, Any]:
        next_ = self.next_

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "next": next_,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        next_ = d.pop("next")

        pagination_info = cls(
            next_=next_,
        )

        return pagination_info
