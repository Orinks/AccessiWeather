import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.nws_center_weather_service_unit_id import NWSCenterWeatherServiceUnitId
from ..types import UNSET, Unset

T = TypeVar("T", bound="CenterWeatherAdvisory")


@_attrs_define
class CenterWeatherAdvisory:
    """
    Attributes:
        id (Union[Unset, str]):
        issue_time (Union[Unset, datetime.datetime]):
        cwsu (Union[Unset, NWSCenterWeatherServiceUnitId]): Three-letter identifier for a Center Weather Service Unit
            (CWSU).
        sequence (Union[Unset, int]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        observed_property (Union[Unset, str]):
        text (Union[Unset, str]):
    """

    id: Union[Unset, str] = UNSET
    issue_time: Union[Unset, datetime.datetime] = UNSET
    cwsu: Union[Unset, NWSCenterWeatherServiceUnitId] = UNSET
    sequence: Union[Unset, int] = UNSET
    start: Union[Unset, datetime.datetime] = UNSET
    end: Union[Unset, datetime.datetime] = UNSET
    observed_property: Union[Unset, str] = UNSET
    text: Union[Unset, str] = UNSET

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        issue_time: Union[Unset, str] = UNSET
        if not isinstance(self.issue_time, Unset):
            issue_time = self.issue_time.isoformat()

        cwsu: Union[Unset, str] = UNSET
        if not isinstance(self.cwsu, Unset):
            cwsu = self.cwsu.value

        sequence = self.sequence

        start: Union[Unset, str] = UNSET
        if not isinstance(self.start, Unset):
            start = self.start.isoformat()

        end: Union[Unset, str] = UNSET
        if not isinstance(self.end, Unset):
            end = self.end.isoformat()

        observed_property = self.observed_property

        text = self.text

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if issue_time is not UNSET:
            field_dict["issueTime"] = issue_time
        if cwsu is not UNSET:
            field_dict["cwsu"] = cwsu
        if sequence is not UNSET:
            field_dict["sequence"] = sequence
        if start is not UNSET:
            field_dict["start"] = start
        if end is not UNSET:
            field_dict["end"] = end
        if observed_property is not UNSET:
            field_dict["observedProperty"] = observed_property
        if text is not UNSET:
            field_dict["text"] = text

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        _issue_time = d.pop("issueTime", UNSET)
        issue_time: Union[Unset, datetime.datetime]
        if isinstance(_issue_time, Unset):
            issue_time = UNSET
        else:
            issue_time = isoparse(_issue_time)

        _cwsu = d.pop("cwsu", UNSET)
        cwsu: Union[Unset, NWSCenterWeatherServiceUnitId]
        if isinstance(_cwsu, Unset):
            cwsu = UNSET
        else:
            cwsu = NWSCenterWeatherServiceUnitId(_cwsu)

        sequence = d.pop("sequence", UNSET)

        _start = d.pop("start", UNSET)
        start: Union[Unset, datetime.datetime]
        if isinstance(_start, Unset):
            start = UNSET
        else:
            start = isoparse(_start)

        _end = d.pop("end", UNSET)
        end: Union[Unset, datetime.datetime]
        if isinstance(_end, Unset):
            end = UNSET
        else:
            end = isoparse(_end)

        observed_property = d.pop("observedProperty", UNSET)

        text = d.pop("text", UNSET)

        center_weather_advisory = cls(
            id=id,
            issue_time=issue_time,
            cwsu=cwsu,
            sequence=sequence,
            start=start,
            end=end,
            observed_property=observed_property,
            text=text,
        )

        return center_weather_advisory
