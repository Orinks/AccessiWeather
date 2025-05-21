import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="Sigmet")


@_attrs_define
class Sigmet:
    """
    Attributes:
        id (Union[Unset, str]):
        issue_time (Union[Unset, datetime.datetime]):
        fir (Union[None, Unset, str]):
        atsu (Union[Unset, str]): ATSU Identifier
        sequence (Union[None, Unset, str]):
        phenomenon (Union[None, Unset, str]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
    """

    id: Union[Unset, str] = UNSET
    issue_time: Union[Unset, datetime.datetime] = UNSET
    fir: Union[None, Unset, str] = UNSET
    atsu: Union[Unset, str] = UNSET
    sequence: Union[None, Unset, str] = UNSET
    phenomenon: Union[None, Unset, str] = UNSET
    start: Union[Unset, datetime.datetime] = UNSET
    end: Union[Unset, datetime.datetime] = UNSET

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        issue_time: Union[Unset, str] = UNSET
        if not isinstance(self.issue_time, Unset):
            issue_time = self.issue_time.isoformat()

        fir: Union[None, Unset, str]
        if isinstance(self.fir, Unset):
            fir = UNSET
        else:
            fir = self.fir

        atsu = self.atsu

        sequence: Union[None, Unset, str]
        if isinstance(self.sequence, Unset):
            sequence = UNSET
        else:
            sequence = self.sequence

        phenomenon: Union[None, Unset, str]
        if isinstance(self.phenomenon, Unset):
            phenomenon = UNSET
        else:
            phenomenon = self.phenomenon

        start: Union[Unset, str] = UNSET
        if not isinstance(self.start, Unset):
            start = self.start.isoformat()

        end: Union[Unset, str] = UNSET
        if not isinstance(self.end, Unset):
            end = self.end.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if issue_time is not UNSET:
            field_dict["issueTime"] = issue_time
        if fir is not UNSET:
            field_dict["fir"] = fir
        if atsu is not UNSET:
            field_dict["atsu"] = atsu
        if sequence is not UNSET:
            field_dict["sequence"] = sequence
        if phenomenon is not UNSET:
            field_dict["phenomenon"] = phenomenon
        if start is not UNSET:
            field_dict["start"] = start
        if end is not UNSET:
            field_dict["end"] = end

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

        def _parse_fir(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        fir = _parse_fir(d.pop("fir", UNSET))

        atsu = d.pop("atsu", UNSET)

        def _parse_sequence(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        sequence = _parse_sequence(d.pop("sequence", UNSET))

        def _parse_phenomenon(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        phenomenon = _parse_phenomenon(d.pop("phenomenon", UNSET))

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

        sigmet = cls(
            id=id,
            issue_time=issue_time,
            fir=fir,
            atsu=atsu,
            sequence=sequence,
            phenomenon=phenomenon,
            start=start,
            end=end,
        )

        return sigmet
