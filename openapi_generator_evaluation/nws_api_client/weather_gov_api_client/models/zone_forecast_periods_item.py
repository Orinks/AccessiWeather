from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="ZoneForecastPeriodsItem")


@_attrs_define
class ZoneForecastPeriodsItem:
    """
    Attributes:
        number (int): A sequential identifier number.
        name (str): A textual description of the period. Example: This Afternoon.
        detailed_forecast (str): A detailed textual forecast for the period.
    """

    number: int
    name: str
    detailed_forecast: str

    def to_dict(self) -> dict[str, Any]:
        number = self.number

        name = self.name

        detailed_forecast = self.detailed_forecast

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "number": number,
                "name": name,
                "detailedForecast": detailed_forecast,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        number = d.pop("number")

        name = d.pop("name")

        detailed_forecast = d.pop("detailedForecast")

        zone_forecast_periods_item = cls(
            number=number,
            name=name,
            detailed_forecast=detailed_forecast,
        )

        return zone_forecast_periods_item
