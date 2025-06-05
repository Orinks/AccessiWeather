from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="TextProductTypeCollectionGraphItem")


@_attrs_define
class TextProductTypeCollectionGraphItem:
    """
    Attributes:
        product_code (str):
        product_name (str):
    """

    product_code: str
    product_name: str

    def to_dict(self) -> dict[str, Any]:
        product_code = self.product_code

        product_name = self.product_name

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "productCode": product_code,
                "productName": product_name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        product_code = d.pop("productCode")

        product_name = d.pop("productName")

        text_product_type_collection_graph_item = cls(
            product_code=product_code,
            product_name=product_name,
        )

        return text_product_type_collection_graph_item
