"""
Tests for HWO/SPS fields on :class:`NotificationState`.

Unit 9 adds four new fields to the dataclass — see
``notification_event_manager.py``. These tests lock in:

- Full round-trip of all four new fields through ``to_dict`` /
  ``from_dict``, including the ``set[str]`` <-> ``list[str]`` conversion for
  ``last_sps_product_ids``.
- Legacy payloads (no HWO/SPS keys) load with the documented defaults and
  never raise.
"""

from __future__ import annotations

from datetime import UTC, datetime

from accessiweather.notifications.notification_event_manager import NotificationState


def test_default_state_has_hwo_sps_defaults() -> None:
    """New fields default to None / empty set."""
    state = NotificationState()
    assert state.last_hwo_issuance_time is None
    assert state.last_hwo_text is None
    assert state.last_hwo_summary_signature is None
    assert state.last_sps_product_ids == set()


def test_to_dict_includes_hwo_sps_fields() -> None:
    """``to_dict`` emits all four new fields with stable keys."""
    issuance = datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)
    state = NotificationState(
        last_hwo_issuance_time=issuance,
        last_hwo_text="HWO body text",
        last_hwo_summary_signature="sig-abc-123",
        last_sps_product_ids={"sps-b", "sps-a", "sps-c"},
    )

    data = state.to_dict()

    assert data["last_hwo_issuance_time"] == issuance.isoformat()
    assert data["last_hwo_text"] == "HWO body text"
    assert data["last_hwo_summary_signature"] == "sig-abc-123"
    # Sorted for deterministic output — important for JSON diffs.
    assert data["last_sps_product_ids"] == ["sps-a", "sps-b", "sps-c"]


def test_full_round_trip_preserves_hwo_sps_fields() -> None:
    """Populated HWO/SPS fields round-trip through dict form unchanged."""
    issuance = datetime(2026, 4, 20, 12, 30, 0, tzinfo=UTC)
    original = NotificationState(
        last_hwo_issuance_time=issuance,
        last_hwo_text="HWO text",
        last_hwo_summary_signature="sig-xyz",
        last_sps_product_ids={"sps-1", "sps-2"},
    )

    restored = NotificationState.from_dict(original.to_dict())

    assert restored.last_hwo_issuance_time == issuance
    assert restored.last_hwo_text == "HWO text"
    assert restored.last_hwo_summary_signature == "sig-xyz"
    # Round-trips back to a set so identity-insensitive membership still works.
    assert isinstance(restored.last_sps_product_ids, set)
    assert restored.last_sps_product_ids == {"sps-1", "sps-2"}


def test_legacy_payload_without_new_fields_loads_with_defaults() -> None:
    """State files written before Unit 9 load cleanly with default HWO/SPS values."""
    legacy_payload = {
        "last_discussion_issuance_time": None,
        "last_discussion_text": None,
        "last_severe_risk": 25,
        "last_minutely_transition_signature": None,
        "last_minutely_likelihood_signature": None,
        "last_check_time": None,
        # No HWO/SPS keys — the key compatibility property.
    }

    state = NotificationState.from_dict(legacy_payload)

    assert state.last_severe_risk == 25
    assert state.last_hwo_issuance_time is None
    assert state.last_hwo_text is None
    assert state.last_hwo_summary_signature is None
    assert state.last_sps_product_ids == set()


def test_from_dict_handles_null_sps_list() -> None:
    """``None`` for ``last_sps_product_ids`` is treated as empty — defensive."""
    state = NotificationState.from_dict({"last_sps_product_ids": None})
    assert state.last_sps_product_ids == set()
