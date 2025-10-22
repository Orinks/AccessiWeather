from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.current_conditions import CurrentConditions
    from ..models.day_forecast import DayForecast
    from ..models.hour_forecast import HourForecast
    from ..models.weather_alert import WeatherAlert


T = TypeVar("T", bound="TimelineResponse")


@_attrs_define
class TimelineResponse:
    """Primary payload returned by the Visual Crossing timeline endpoint. Only fields currently consumed by AccessiWeather
    are modeled here.

        Attributes:
            resolved_address (str): Canonicalized location label.
            timezone (str): IANA timezone identifier for the location.
            current_conditions (Union[Unset, CurrentConditions]):
            days (Union[Unset, list['DayForecast']]):
            hours (Union[Unset, list['HourForecast']]):
            alerts (Union[Unset, list['WeatherAlert']]): Weather alerts associated with the location.
    """

    resolved_address: str
    timezone: str
    current_conditions: Union[Unset, "CurrentConditions"] = UNSET
    days: Union[Unset, list["DayForecast"]] = UNSET
    hours: Union[Unset, list["HourForecast"]] = UNSET
    alerts: Union[Unset, list["WeatherAlert"]] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        resolved_address = self.resolved_address

        timezone = self.timezone

        current_conditions: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.current_conditions, Unset):
            current_conditions = self.current_conditions.to_dict()

        days: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.days, Unset):
            days = []
            for days_item_data in self.days:
                days_item = days_item_data.to_dict()
                days.append(days_item)

        hours: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.hours, Unset):
            hours = []
            for hours_item_data in self.hours:
                hours_item = hours_item_data.to_dict()
                hours.append(hours_item)

        alerts: Union[Unset, list[dict[str, Any]]] = UNSET
        if not isinstance(self.alerts, Unset):
            alerts = []
            for alerts_item_data in self.alerts:
                alerts_item = alerts_item_data.to_dict()
                alerts.append(alerts_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "resolvedAddress": resolved_address,
                "timezone": timezone,
            }
        )
        if current_conditions is not UNSET:
            field_dict["currentConditions"] = current_conditions
        if days is not UNSET:
            field_dict["days"] = days
        if hours is not UNSET:
            field_dict["hours"] = hours
        if alerts is not UNSET:
            field_dict["alerts"] = alerts

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.current_conditions import CurrentConditions
        from ..models.day_forecast import DayForecast
        from ..models.hour_forecast import HourForecast
        from ..models.weather_alert import WeatherAlert

        d = dict(src_dict)
        resolved_address = d.pop("resolvedAddress")

        timezone = d.pop("timezone")

        _current_conditions = d.pop("currentConditions", UNSET)
        current_conditions: Union[Unset, CurrentConditions]
        if isinstance(_current_conditions, Unset):
            current_conditions = UNSET
        else:
            current_conditions = CurrentConditions.from_dict(_current_conditions)

        days = []
        _days = d.pop("days", UNSET)
        for days_item_data in _days or []:
            days_item = DayForecast.from_dict(days_item_data)

            days.append(days_item)

        hours = []
        _hours = d.pop("hours", UNSET)
        for hours_item_data in _hours or []:
            hours_item = HourForecast.from_dict(hours_item_data)

            hours.append(hours_item)

        alerts = []
        _alerts = d.pop("alerts", UNSET)
        for alerts_item_data in _alerts or []:
            alerts_item = WeatherAlert.from_dict(alerts_item_data)

            alerts.append(alerts_item)

        timeline_response = cls(
            resolved_address=resolved_address,
            timezone=timezone,
            current_conditions=current_conditions,
            days=days,
            hours=hours,
            alerts=alerts,
        )

        timeline_response.additional_properties = d
        return timeline_response

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
