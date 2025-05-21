from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.gridpoint_hazards_values_item_value_item import (
        GridpointHazardsValuesItemValueItem,
    )


T = TypeVar("T", bound="GridpointHazardsValuesItem")


@_attrs_define
class GridpointHazardsValuesItem:
    """
    Attributes:
        valid_time (str): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        value (list['GridpointHazardsValuesItemValueItem']):
    """

    valid_time: str
    value: list["GridpointHazardsValuesItemValueItem"]

    def to_dict(self) -> dict[str, Any]:
        valid_time: str
        valid_time = self.valid_time

        value = []
        for value_item_data in self.value:
            value_item = value_item_data.to_dict()
            value.append(value_item)

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
        from ..models.gridpoint_hazards_values_item_value_item import (
            GridpointHazardsValuesItemValueItem,
        )

        d = dict(src_dict)

        def _parse_valid_time(data: object) -> str:
            return cast(str, data)

        valid_time = _parse_valid_time(d.pop("validTime"))

        value = []
        _value = d.pop("value")
        for value_item_data in _value:
            value_item = GridpointHazardsValuesItemValueItem.from_dict(value_item_data)

            value.append(value_item)

        gridpoint_hazards_values_item = cls(
            valid_time=valid_time,
            value=value,
        )

        return gridpoint_hazards_values_item
