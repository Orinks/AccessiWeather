from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.current_data import CurrentData
    from ..models.current_units import CurrentUnits
    from ..models.daily_data import DailyData
    from ..models.daily_units import DailyUnits
    from ..models.hourly_data import HourlyData
    from ..models.hourly_units import HourlyUnits


T = TypeVar("T", bound="ForecastResponse")


@_attrs_define
class ForecastResponse:
    """Forecast payload containing the requested sections.

    Attributes:
        latitude (Union[Unset, float]):
        longitude (Union[Unset, float]):
        generationtime_ms (Union[Unset, float]):
        utc_offset_seconds (Union[Unset, int]):
        timezone (Union[Unset, str]):
        timezone_abbreviation (Union[Unset, str]):
        elevation (Union[Unset, float]):
        current_units (Union[Unset, CurrentUnits]):
        current (Union[Unset, CurrentData]):
        hourly_units (Union[Unset, HourlyUnits]):
        hourly (Union[Unset, HourlyData]):
        daily_units (Union[Unset, DailyUnits]):
        daily (Union[Unset, DailyData]):
    """

    latitude: Union[Unset, float] = UNSET
    longitude: Union[Unset, float] = UNSET
    generationtime_ms: Union[Unset, float] = UNSET
    utc_offset_seconds: Union[Unset, int] = UNSET
    timezone: Union[Unset, str] = UNSET
    timezone_abbreviation: Union[Unset, str] = UNSET
    elevation: Union[Unset, float] = UNSET
    current_units: Union[Unset, "CurrentUnits"] = UNSET
    current: Union[Unset, "CurrentData"] = UNSET
    hourly_units: Union[Unset, "HourlyUnits"] = UNSET
    hourly: Union[Unset, "HourlyData"] = UNSET
    daily_units: Union[Unset, "DailyUnits"] = UNSET
    daily: Union[Unset, "DailyData"] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        latitude = self.latitude

        longitude = self.longitude

        generationtime_ms = self.generationtime_ms

        utc_offset_seconds = self.utc_offset_seconds

        timezone = self.timezone

        timezone_abbreviation = self.timezone_abbreviation

        elevation = self.elevation

        current_units: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.current_units, Unset):
            current_units = self.current_units.to_dict()

        current: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.current, Unset):
            current = self.current.to_dict()

        hourly_units: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.hourly_units, Unset):
            hourly_units = self.hourly_units.to_dict()

        hourly: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.hourly, Unset):
            hourly = self.hourly.to_dict()

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
        if current_units is not UNSET:
            field_dict["current_units"] = current_units
        if current is not UNSET:
            field_dict["current"] = current
        if hourly_units is not UNSET:
            field_dict["hourly_units"] = hourly_units
        if hourly is not UNSET:
            field_dict["hourly"] = hourly
        if daily_units is not UNSET:
            field_dict["daily_units"] = daily_units
        if daily is not UNSET:
            field_dict["daily"] = daily

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.current_data import CurrentData
        from ..models.current_units import CurrentUnits
        from ..models.daily_data import DailyData
        from ..models.daily_units import DailyUnits
        from ..models.hourly_data import HourlyData
        from ..models.hourly_units import HourlyUnits

        d = dict(src_dict)
        latitude = d.pop("latitude", UNSET)

        longitude = d.pop("longitude", UNSET)

        generationtime_ms = d.pop("generationtime_ms", UNSET)

        utc_offset_seconds = d.pop("utc_offset_seconds", UNSET)

        timezone = d.pop("timezone", UNSET)

        timezone_abbreviation = d.pop("timezone_abbreviation", UNSET)

        elevation = d.pop("elevation", UNSET)

        _current_units = d.pop("current_units", UNSET)
        current_units: Union[Unset, CurrentUnits]
        if isinstance(_current_units, Unset):
            current_units = UNSET
        else:
            current_units = CurrentUnits.from_dict(_current_units)

        _current = d.pop("current", UNSET)
        current: Union[Unset, CurrentData]
        if isinstance(_current, Unset):
            current = UNSET
        else:
            current = CurrentData.from_dict(_current)

        _hourly_units = d.pop("hourly_units", UNSET)
        hourly_units: Union[Unset, HourlyUnits]
        if isinstance(_hourly_units, Unset):
            hourly_units = UNSET
        else:
            hourly_units = HourlyUnits.from_dict(_hourly_units)

        _hourly = d.pop("hourly", UNSET)
        hourly: Union[Unset, HourlyData]
        if isinstance(_hourly, Unset):
            hourly = UNSET
        else:
            hourly = HourlyData.from_dict(_hourly)

        _daily_units = d.pop("daily_units", UNSET)
        daily_units: Union[Unset, DailyUnits]
        if isinstance(_daily_units, Unset):
            daily_units = UNSET
        else:
            daily_units = DailyUnits.from_dict(_daily_units)

        _daily = d.pop("daily", UNSET)
        daily: Union[Unset, DailyData]
        if isinstance(_daily, Unset):
            daily = UNSET
        else:
            daily = DailyData.from_dict(_daily)

        forecast_response = cls(
            latitude=latitude,
            longitude=longitude,
            generationtime_ms=generationtime_ms,
            utc_offset_seconds=utc_offset_seconds,
            timezone=timezone,
            timezone_abbreviation=timezone_abbreviation,
            elevation=elevation,
            current_units=current_units,
            current=current,
            hourly_units=hourly_units,
            hourly=hourly,
            daily_units=daily_units,
            daily=daily,
        )

        forecast_response.additional_properties = d
        return forecast_response

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
