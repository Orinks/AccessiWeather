from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define

from ..models.quantitative_value_quality_control import QuantitativeValueQualityControl
from ..types import UNSET, Unset

T = TypeVar("T", bound="QuantitativeValue")


@_attrs_define
class QuantitativeValue:
    """A structured value representing a measurement and its unit of measure. This object is a slighly modified version of
    the schema.org definition at https://schema.org/QuantitativeValue

        Attributes:
            value (Union[None, Unset, float]): A measured value
            max_value (Union[Unset, float]): The maximum value of a range of measured values
            min_value (Union[Unset, float]): The minimum value of a range of measured values
            unit_code (Union[Unset, str]): A string denoting a unit of measure, expressed in the format "{unit}" or
                "{namespace}:{unit}".
                Units with the namespace "wmo" or "wmoUnit" are defined in the World Meteorological Organization Codes Registry
                at http://codes.wmo.int/common/unit and should be canonically resolvable to
                http://codes.wmo.int/common/unit/{unit}.
                Units with the namespace "nwsUnit" are currently custom and do not align to any standard.
                Units with no namespace or the namespace "uc" are compliant with the Unified Code for Units of Measure syntax
                defined at https://unitsofmeasure.org/. This also aligns with recent versions of the Geographic Markup Language
                (GML) standard, the IWXXM standard, and OGC Observations and Measurements v2.0 (ISO/DIS 19156).
                Namespaced units are considered deprecated. We will be aligning API to use the same standards as GML/IWXXM in
                the future.
            quality_control (Union[Unset, QuantitativeValueQualityControl]): For values in observation records, the quality
                control flag from the MADIS system. The definitions of these flags can be found at
                https://madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml
    """

    value: Union[None, Unset, float] = UNSET
    max_value: Union[Unset, float] = UNSET
    min_value: Union[Unset, float] = UNSET
    unit_code: Union[Unset, str] = UNSET
    quality_control: Union[Unset, QuantitativeValueQualityControl] = UNSET

    def to_dict(self) -> dict[str, Any]:
        value: Union[None, Unset, float]
        if isinstance(self.value, Unset):
            value = UNSET
        else:
            value = self.value

        max_value = self.max_value

        min_value = self.min_value

        unit_code = self.unit_code

        quality_control: Union[Unset, str] = UNSET
        if not isinstance(self.quality_control, Unset):
            quality_control = self.quality_control.value

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if value is not UNSET:
            field_dict["value"] = value
        if max_value is not UNSET:
            field_dict["maxValue"] = max_value
        if min_value is not UNSET:
            field_dict["minValue"] = min_value
        if unit_code is not UNSET:
            field_dict["unitCode"] = unit_code
        if quality_control is not UNSET:
            field_dict["qualityControl"] = quality_control

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_value(data: object) -> Union[None, Unset, float]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, float], data)

        value = _parse_value(d.pop("value", UNSET))

        max_value = d.pop("maxValue", UNSET)

        min_value = d.pop("minValue", UNSET)

        unit_code = d.pop("unitCode", UNSET)

        _quality_control = d.pop("qualityControl", UNSET)
        quality_control: Union[Unset, QuantitativeValueQualityControl]
        if isinstance(_quality_control, Unset):
            quality_control = UNSET
        else:
            quality_control = QuantitativeValueQualityControl(_quality_control)

        quantitative_value = cls(
            value=value,
            max_value=max_value,
            min_value=min_value,
            unit_code=unit_code,
            quality_control=quality_control,
        )

        return quantitative_value
