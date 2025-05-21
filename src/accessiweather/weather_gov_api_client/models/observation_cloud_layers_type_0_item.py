from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.metar_sky_coverage import MetarSkyCoverage

if TYPE_CHECKING:
    from ..models.quantitative_value import QuantitativeValue


T = TypeVar("T", bound="ObservationCloudLayersType0Item")


@_attrs_define
class ObservationCloudLayersType0Item:
    """
    Attributes:
        base (QuantitativeValue): A structured value representing a measurement and its unit of measure. This object is
            a slighly modified version of the schema.org definition at https://schema.org/QuantitativeValue
        amount (MetarSkyCoverage):
    """

    base: "QuantitativeValue"
    amount: MetarSkyCoverage

    def to_dict(self) -> dict[str, Any]:
        base = self.base.to_dict()

        amount = self.amount.value

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "base": base,
                "amount": amount,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.quantitative_value import QuantitativeValue

        d = dict(src_dict)
        base = QuantitativeValue.from_dict(d.pop("base"))

        amount = MetarSkyCoverage(d.pop("amount"))

        observation_cloud_layers_type_0_item = cls(
            base=base,
            amount=amount,
        )

        return observation_cloud_layers_type_0_item
