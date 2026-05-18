"""Shared sound pack manager models and category metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...sound_events import FRIENDLY_SOUND_EVENT_CHOICES

# Sound events users can map through the normal manager UI. The legacy name is
# kept for existing imports in the manager and wizard modules.
FRIENDLY_ALERT_CATEGORIES: list[tuple[str, str]] = list(FRIENDLY_SOUND_EVENT_CHOICES)


@dataclass
class SoundPackInfo:
    """Information about a sound pack."""

    pack_id: str
    name: str
    author: str
    description: str
    path: Path
    sounds: dict[str, str]
