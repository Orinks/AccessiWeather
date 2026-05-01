"""State model for the sound pack creation wizard."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WizardState:
    """State container for the wizard."""

    pack_name: str = ""
    author: str = ""
    description: str = ""
    selected_alert_keys: list[str] = field(default_factory=list)
    sound_mappings: dict[str, str] = field(default_factory=dict)
