"""Channelized weather event pipeline primitives (Phase 1)."""

from __future__ import annotations

import json
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from .models import CurrentConditions
from .screen_reader import ScreenReaderAnnouncer

WeatherEventChannel = Literal["urgent", "now", "hourly", "daily", "discussion", "system"]


@dataclass(slots=True)
class WeatherEvent:
    """A lightweight event envelope for visible and non-visual weather flows."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    channel: WeatherEventChannel = "system"
    location: str = "Unknown"
    headline: str = ""
    speech_text: str = ""
    change_text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    read: bool = False


class WeatherEventStore:
    """In-memory ring buffer with unread accounting and cursor helpers."""

    def __init__(self, max_size: int = 300) -> None:
        """Create a ring buffer with configurable maximum size."""
        self.max_size = max(1, int(max_size))
        self._events: deque[WeatherEvent] = deque(maxlen=self.max_size)

    def append(self, event: WeatherEvent) -> WeatherEvent:
        if len(self._events) == self._events.maxlen and self._events and not self._events[0].read:
            # Item will be evicted unread; no per-event index to maintain, so just append.
            pass
        self._events.append(event)
        return event

    def latest(self, channel: WeatherEventChannel | None = None) -> WeatherEvent | None:
        for event in reversed(self._events):
            if channel is None or event.channel == channel:
                return event
        return None

    def get_after(self, cursor: str | None = None, channel: WeatherEventChannel | None = None) -> list[WeatherEvent]:
        seen_cursor = cursor is None
        out: list[WeatherEvent] = []
        for event in self._events:
            if not seen_cursor:
                if event.id == cursor:
                    seen_cursor = True
                continue
            if channel is None or event.channel == channel:
                out.append(event)
        return out

    def mark_read(self, event_id: str) -> bool:
        for event in self._events:
            if event.id == event_id:
                event.read = True
                return True
        return False

    def unread_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {
            "urgent": 0,
            "now": 0,
            "hourly": 0,
            "daily": 0,
            "discussion": 0,
            "system": 0,
            "total": 0,
        }
        for event in self._events:
            if not event.read:
                counts[event.channel] += 1
                counts["total"] += 1
        return counts


class WeatherEventDispatcher:
    """Centralized event writer + announcer + optional toast mirroring."""

    def __init__(self, store: WeatherEventStore, notifier: Any | None = None) -> None:
        """Create dispatcher with a store and optional toast notifier."""
        self.store = store
        self.notifier = notifier
        self.announcer = ScreenReaderAnnouncer()

    def dispatch_event(
        self,
        event: WeatherEvent,
        *,
        announce: bool = True,
        mirror_toast: bool = True,
    ) -> WeatherEvent:
        self.store.append(event)

        if announce and event.speech_text:
            self.announcer.announce(event.speech_text)

        if mirror_toast and self.notifier is not None:
            message = event.change_text or event.speech_text or self._serialize_payload(event.payload)
            self.notifier.send_notification(
                title=event.headline or "Weather Update",
                message=message,
                timeout=10,
                play_sound=False,
            )

        return event

    @staticmethod
    def _serialize_payload(payload: dict[str, Any]) -> str:
        if not payload:
            return ""
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return str(payload)


def should_emit_current_conditions_event(
    previous: CurrentConditions | None,
    current: CurrentConditions | None,
    *,
    temp_delta_threshold: float = 2.0,
    wind_delta_threshold: float = 5.0,
) -> tuple[bool, str]:
    """Return whether a current-conditions event should be emitted and why."""
    if current is None:
        return False, ""
    if previous is None:
        return True, "Initial current conditions"

    prev_temp = previous.temperature
    curr_temp = current.temperature
    if prev_temp is not None and curr_temp is not None:
        delta = abs(curr_temp - prev_temp)
        if delta >= temp_delta_threshold:
            return True, f"Temperature changed by {delta:.0f}°"

    prev_wind = previous.wind_speed
    curr_wind = current.wind_speed
    if prev_wind is not None and curr_wind is not None:
        wind_delta = abs(curr_wind - prev_wind)
        if wind_delta >= wind_delta_threshold:
            return True, f"Wind changed by {wind_delta:.0f}"

    prev_cond = (previous.condition or "").strip().lower()
    curr_cond = (current.condition or "").strip().lower()
    if prev_cond and curr_cond and prev_cond != curr_cond:
        return True, f"Conditions changed from {previous.condition} to {current.condition}"

    return False, ""
