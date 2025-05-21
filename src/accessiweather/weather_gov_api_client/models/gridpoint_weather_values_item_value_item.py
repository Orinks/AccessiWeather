from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.gridpoint_weather_values_item_value_item_attributes_item import (
    GridpointWeatherValuesItemValueItemAttributesItem,
)
from ..models.gridpoint_weather_values_item_value_item_coverage import (
    GridpointWeatherValuesItemValueItemCoverage,
)
from ..models.gridpoint_weather_values_item_value_item_intensity import (
    GridpointWeatherValuesItemValueItemIntensity,
)
from ..models.gridpoint_weather_values_item_value_item_weather import (
    GridpointWeatherValuesItemValueItemWeather,
)

if TYPE_CHECKING:
    from ..models.quantitative_value import QuantitativeValue


T = TypeVar("T", bound="GridpointWeatherValuesItemValueItem")


@_attrs_define
class GridpointWeatherValuesItemValueItem:
    """A value object representing expected weather phenomena.

    Attributes:
        coverage (GridpointWeatherValuesItemValueItemCoverage):
        weather (GridpointWeatherValuesItemValueItemWeather):
        intensity (GridpointWeatherValuesItemValueItemIntensity):
        visibility (QuantitativeValue): A structured value representing a measurement and its unit of measure. This
            object is a slighly modified version of the schema.org definition at https://schema.org/QuantitativeValue
        attributes (list[GridpointWeatherValuesItemValueItemAttributesItem]):
    """

    coverage: GridpointWeatherValuesItemValueItemCoverage
    weather: GridpointWeatherValuesItemValueItemWeather
    intensity: GridpointWeatherValuesItemValueItemIntensity
    visibility: "QuantitativeValue"
    attributes: list[GridpointWeatherValuesItemValueItemAttributesItem]

    def to_dict(self) -> dict[str, Any]:
        coverage = self.coverage.value

        weather = self.weather.value

        intensity = self.intensity.value

        visibility = self.visibility.to_dict()

        attributes = []
        for attributes_item_data in self.attributes:
            attributes_item = attributes_item_data.value
            attributes.append(attributes_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "coverage": coverage,
                "weather": weather,
                "intensity": intensity,
                "visibility": visibility,
                "attributes": attributes,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.quantitative_value import QuantitativeValue

        d = dict(src_dict)
        coverage = GridpointWeatherValuesItemValueItemCoverage(d.pop("coverage"))

        weather = GridpointWeatherValuesItemValueItemWeather(d.pop("weather"))

        intensity = GridpointWeatherValuesItemValueItemIntensity(d.pop("intensity"))

        visibility = QuantitativeValue.from_dict(d.pop("visibility"))

        attributes = []
        _attributes = d.pop("attributes")
        for attributes_item_data in _attributes:
            attributes_item = GridpointWeatherValuesItemValueItemAttributesItem(
                attributes_item_data
            )

            attributes.append(attributes_item)

        gridpoint_weather_values_item_value_item = cls(
            coverage=coverage,
            weather=weather,
            intensity=intensity,
            visibility=visibility,
            attributes=attributes,
        )

        return gridpoint_weather_values_item_value_item
