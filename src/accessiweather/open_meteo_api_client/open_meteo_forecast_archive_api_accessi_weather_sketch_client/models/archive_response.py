from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.archive_daily_data import ArchiveDailyData
    from ..models.archive_daily_units import ArchiveDailyUnits


T = TypeVar("T", bound="ArchiveResponse")


@_attrs_define
class ArchiveResponse:
    """Historical daily data payload.

    Attributes:
        latitude (Union[Unset, float]):
        longitude (Union[Unset, float]):
        generationtime_ms (Union[Unset, float]):
        utc_offset_seconds (Union[Unset, int]):
        timezone (Union[Unset, str]):
        timezone_abbreviation (Union[Unset, str]):
        elevation (Union[Unset, float]):
        daily_units (Union[Unset, ArchiveDailyUnits]):
        daily (Union[Unset, ArchiveDailyData]):
    """

    latitude: Union[Unset, float] = UNSET
    longitude: Union[Unset, float] = UNSET
    generationtime_ms: Union[Unset, float] = UNSET
    utc_offset_seconds: Union[Unset, int] = UNSET
    timezone: Union[Unset, str] = UNSET
    timezone_abbreviation: Union[Unset, str] = UNSET
    elevation: Union[Unset, float] = UNSET
    daily_units: Union[Unset, "ArchiveDailyUnits"] = UNSET
    daily: Union[Unset, "ArchiveDailyData"] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        latitude = self.latitude

        longitude = self.longitude

        generationtime_ms = self.generationtime_ms

        utc_offset_seconds = self.utc_offset_seconds

        timezone = self.timezone

        timezone_abbreviation = self.timezone_abbreviation

        elevation = self.elevation

        daily_units: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.daily_units, Unset):
            daily_units = self.daily_units.to_dict()

        daily: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.daily, Unset):
            daily = self.daily.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if latitude is not UNSET:
            field_dict["latitude"] = latitude
        if longitude is not UNSET:
            field_dict["longitude"] = longitude
        if generationtime_ms is not UNSET:
            field_dict["generationtime_ms"] = generationtime_ms
        if utc_offset_seconds is not UNSET:
            field_dict["utc_offset_seconds"] = utc_offset_seconds
        if timezone is not UNSET:
            field_dict["timezone"] = timezone
        if timezone_abbreviation is not UNSET:
            field_dict["timezone_abbreviation"] = timezone_abbreviation
        if elevation is not UNSET:
            field_dict["elevation"] = elevation
        if daily_units is not UNSET:
            field_dict["daily_units"] = daily_units
        if daily is not UNSET:
            field_dict["daily"] = daily

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.archive_daily_data import ArchiveDailyData
        from ..models.archive_daily_units import ArchiveDailyUnits

        d = dict(src_dict)
        latitude = d.pop("latitude", UNSET)

        longitude = d.pop("longitude", UNSET)

        generationtime_ms = d.pop("generationtime_ms", UNSET)

        utc_offset_seconds = d.pop("utc_offset_seconds", UNSET)

        timezone = d.pop("timezone", UNSET)

        timezone_abbreviation = d.pop("timezone_abbreviation", UNSET)

        elevation = d.pop("elevation", UNSET)

        _daily_units = d.pop("daily_units", UNSET)
        daily_units: Union[Unset, ArchiveDailyUnits]
        if isinstance(_daily_units, Unset):
            daily_units = UNSET
        else:
            daily_units = ArchiveDailyUnits.from_dict(_daily_units)

        _daily = d.pop("daily", UNSET)
        daily: Union[Unset, ArchiveDailyData]
        if isinstance(_daily, Unset):
            daily = UNSET
        else:
            daily = ArchiveDailyData.from_dict(_daily)

        archive_response = cls(
            latitude=latitude,
            longitude=longitude,
            generationtime_ms=generationtime_ms,
            utc_offset_seconds=utc_offset_seconds,
            timezone=timezone,
            timezone_abbreviation=timezone_abbreviation,
            elevation=elevation,
            daily_units=daily_units,
            daily=daily,
        )

        archive_response.additional_properties = d
        return archive_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
