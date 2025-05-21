from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="GridpointQuantitativeValueLayerValuesItem")


@_attrs_define
class GridpointQuantitativeValueLayerValuesItem:
    """
    Attributes:
        valid_time (str): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        value (Union[None, float]):
    """

    valid_time: str
    value: Union[None, float]

    def to_dict(self) -> dict[str, Any]:
        valid_time: str
        valid_time = self.valid_time

        value: Union[None, float]
        value = self.value

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "validTime": valid_time,
                "value": value,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_valid_time(data: object) -> str:
            return cast(str, data)

        valid_time = _parse_valid_time(d.pop("validTime"))

        def _parse_value(data: object) -> Union[None, float]:
            if data is None:
                return data
            return cast(Union[None, float], data)

        value = _parse_value(d.pop("value"))

        gridpoint_quantitative_value_layer_values_item = cls(
            valid_time=valid_time,
            value=value,
        )

        return gridpoint_quantitative_value_layer_values_item
