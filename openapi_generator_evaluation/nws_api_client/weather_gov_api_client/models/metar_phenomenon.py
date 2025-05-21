from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define

from ..models.metar_phenomenon_intensity import MetarPhenomenonIntensity
from ..models.metar_phenomenon_modifier import MetarPhenomenonModifier
from ..models.metar_phenomenon_weather import MetarPhenomenonWeather
from ..types import UNSET, Unset

T = TypeVar("T", bound="MetarPhenomenon")


@_attrs_define
class MetarPhenomenon:
    """An object representing a decoded METAR phenomenon string.

    Attributes:
        intensity (MetarPhenomenonIntensity):
        modifier (MetarPhenomenonModifier):
        weather (MetarPhenomenonWeather):
        raw_string (str):
        in_vicinity (Union[Unset, bool]):
    """

    intensity: MetarPhenomenonIntensity
    modifier: MetarPhenomenonModifier
    weather: MetarPhenomenonWeather
    raw_string: str
    in_vicinity: Union[Unset, bool] = UNSET

    def to_dict(self) -> dict[str, Any]:
        intensity = self.intensity.value

        modifier = self.modifier.value

        weather = self.weather.value

        raw_string = self.raw_string

        in_vicinity = self.in_vicinity

        field_dict: dict[str, Any] = {}
        field_dict.update(
            {
                "intensity": intensity,
                "modifier": modifier,
                "weather": weather,
                "rawString": raw_string,
            }
        )
        if in_vicinity is not UNSET:
            field_dict["inVicinity"] = in_vicinity

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        intensity = MetarPhenomenonIntensity(d.pop("intensity"))

        modifier = MetarPhenomenonModifier(d.pop("modifier"))

        weather = MetarPhenomenonWeather(d.pop("weather"))

        raw_string = d.pop("rawString")

        in_vicinity = d.pop("inVicinity", UNSET)

        metar_phenomenon = cls(
            intensity=intensity,
            modifier=modifier,
            weather=weather,
            raw_string=raw_string,
            in_vicinity=in_vicinity,
        )

        return metar_phenomenon
