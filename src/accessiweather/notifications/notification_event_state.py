"""State containers and persistence shape adapters for notification events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NotificationEvent:
    """Represents a notification event to be sent."""

    event_type: str
    title: str
    message: str
    sound_event: str


@dataclass
class NotificationState:
    """Tracks state for notification change detection."""

    last_discussion_issuance_time: datetime | None = None
    last_discussion_text: str | None = None
    last_severe_risk: int | None = None
    last_minutely_transition_signature: str | None = None
    last_minutely_likelihood_signature: str | None = None
    last_check_time: datetime | None = None
    last_hwo_issuance_time: datetime | None = None
    last_hwo_text: str | None = None
    last_hwo_summary_signature: str | None = None
    last_sps_product_ids: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        return {
            "last_discussion_issuance_time": (
                self.last_discussion_issuance_time.isoformat()
                if self.last_discussion_issuance_time
                else None
            ),
            "last_discussion_text": self.last_discussion_text,
            "last_severe_risk": self.last_severe_risk,
            "last_minutely_transition_signature": self.last_minutely_transition_signature,
            "last_minutely_likelihood_signature": self.last_minutely_likelihood_signature,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "last_hwo_issuance_time": (
                self.last_hwo_issuance_time.isoformat() if self.last_hwo_issuance_time else None
            ),
            "last_hwo_text": self.last_hwo_text,
            "last_hwo_summary_signature": self.last_hwo_summary_signature,
            "last_sps_product_ids": sorted(self.last_sps_product_ids),
        }

    @classmethod
    def from_dict(cls, data: dict) -> NotificationState:
        """Create from dictionary."""
        last_check = data.get("last_check_time")
        last_issuance = data.get("last_discussion_issuance_time")
        last_hwo_issuance = data.get("last_hwo_issuance_time")
        sps_ids = data.get("last_sps_product_ids") or []
        return cls(
            last_discussion_issuance_time=(
                datetime.fromisoformat(last_issuance) if last_issuance else None
            ),
            last_discussion_text=data.get("last_discussion_text"),
            last_severe_risk=data.get("last_severe_risk"),
            last_minutely_transition_signature=data.get("last_minutely_transition_signature"),
            last_minutely_likelihood_signature=data.get("last_minutely_likelihood_signature"),
            last_check_time=datetime.fromisoformat(last_check) if last_check else None,
            last_hwo_issuance_time=(
                datetime.fromisoformat(last_hwo_issuance) if last_hwo_issuance else None
            ),
            last_hwo_text=data.get("last_hwo_text"),
            last_hwo_summary_signature=data.get("last_hwo_summary_signature"),
            last_sps_product_ids=set(sps_ids),
        )


def runtime_section_to_legacy_shape(section: dict) -> dict:
    """Convert unified runtime state to the legacy notification-state shape."""
    discussion = section.get("discussion", {})
    severe_risk = section.get("severe_risk", {})
    minutely_precipitation = section.get("minutely_precipitation", {})
    hwo = section.get("hwo", {})
    sps = section.get("sps", {})
    return {
        "last_discussion_issuance_time": discussion.get("last_issuance_time"),
        "last_discussion_text": discussion.get("last_text"),
        "last_severe_risk": severe_risk.get("last_value"),
        "last_minutely_transition_signature": minutely_precipitation.get(
            "last_transition_signature"
        ),
        "last_minutely_likelihood_signature": minutely_precipitation.get(
            "last_likelihood_signature"
        ),
        "last_check_time": discussion.get("last_check_time")
        or severe_risk.get("last_check_time")
        or minutely_precipitation.get("last_check_time"),
        "last_hwo_issuance_time": hwo.get("last_issuance_time"),
        "last_hwo_text": hwo.get("last_text"),
        "last_hwo_summary_signature": hwo.get("last_summary_signature"),
        "last_sps_product_ids": list(sps.get("last_product_ids") or []),
    }


def legacy_shape_to_runtime_section(data: dict) -> dict:
    """Convert legacy notification-state payloads to the unified section shape."""
    last_check_time = data.get("last_check_time")
    sps_ids = data.get("last_sps_product_ids") or []
    return {
        "discussion": {
            "last_issuance_time": data.get("last_discussion_issuance_time"),
            "last_text": data.get("last_discussion_text"),
            "last_check_time": last_check_time,
        },
        "severe_risk": {
            "last_value": data.get("last_severe_risk"),
            "last_check_time": last_check_time,
        },
        "minutely_precipitation": {
            "last_transition_signature": data.get("last_minutely_transition_signature"),
            "last_likelihood_signature": data.get("last_minutely_likelihood_signature"),
            "last_check_time": last_check_time,
        },
        "hwo": {
            "last_issuance_time": data.get("last_hwo_issuance_time"),
            "last_text": data.get("last_hwo_text"),
            "last_summary_signature": data.get("last_hwo_summary_signature"),
            "last_check_time": last_check_time,
        },
        "sps": {
            "last_product_ids": sorted(sps_ids),
            "last_check_time": last_check_time,
        },
    }
