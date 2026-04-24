"""
Tests for Unit 10 — HWO (Hazardous Weather Outlook) update notifications.

These cover `NotificationEventManager._check_hwo_update`:

1. Cold-start baseline — first fetch stores state silently, no dispatch.
2. Content change — newer issuance_time + changed signature → dispatch.
3. Summarizer fallback — short/empty summarizer output → generic body.
4. Unchanged — same issuance_time + same signature → no-op.
5. Rate limit — change within 30 min of last dispatch → suppressed but state updates.
6. Disabled — ``notify_hwo_update = False`` → no dispatch regardless of change.
7. None product — no crash, no state update.
8. Multi-location — each location maintains its own 30-min rate-limit bucket.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from accessiweather.models import AppSettings, Location, TextProduct
from accessiweather.notifications.notification_event_manager import (
    NotificationEventManager,
)


def _dt(product: TextProduct) -> datetime:
    """Assert and narrow an issuance_time that the tests always set."""
    assert product.issuance_time is not None
    return product.issuance_time


def _location(name: str = "Test City", cwa: str | None = "OKX") -> Location:
    return Location(
        name=name,
        latitude=40.0,
        longitude=-74.0,
        country_code="US",
        cwa_office=cwa,
    )


def _hwo(
    text: str = "HAZARDOUS WEATHER OUTLOOK\nPatchy fog possible overnight.",
    issuance_time: datetime | None = None,
    cwa: str = "OKX",
    product_id: str = "HWO-OKX-1",
) -> TextProduct:
    if issuance_time is None:
        issuance_time = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
    return TextProduct(
        product_type="HWO",
        product_id=product_id,
        cwa_office=cwa,
        issuance_time=issuance_time,
        product_text=text,
        headline=None,
    )


@pytest.fixture
def manager():
    return NotificationEventManager(state_file=None)


@pytest.fixture
def settings_hwo_enabled():
    s = AppSettings()
    s.notify_hwo_update = True  # type: ignore[attr-defined]
    return s


@pytest.fixture
def settings_hwo_disabled():
    s = AppSettings()
    s.notify_hwo_update = False  # type: ignore[attr-defined]
    return s


# ------------------------------------------------------------------
# 1. Cold-start baseline
# ------------------------------------------------------------------


def test_cold_start_stores_baseline_no_dispatch(manager, settings_hwo_enabled):
    loc = _location()
    product = _hwo()
    dispatched: list[tuple] = []
    manager._dispatch_hwo_notification = lambda *a, **kw: dispatched.append((a, kw))  # type: ignore[attr-defined]

    manager._check_hwo_update(loc, product, settings_hwo_enabled)

    assert dispatched == []
    assert manager.state.last_hwo_issuance_time == product.issuance_time
    assert manager.state.last_hwo_text == product.product_text
    assert manager.state.last_hwo_summary_signature is not None


# ------------------------------------------------------------------
# 2. Content change → dispatch with summarizer output
# ------------------------------------------------------------------


def test_content_change_dispatches_summary(manager, settings_hwo_enabled, monkeypatch):
    loc = _location()

    # Baseline first.
    first = _hwo(
        text=("HAZARDOUS WEATHER OUTLOOK\nNothing hazardous expected through the period.\n"),
        issuance_time=datetime(2026, 4, 20, 5, 0, 0, tzinfo=UTC),
    )
    manager._check_hwo_update(loc, first, settings_hwo_enabled)

    # Patch summarizer to return a believably long sentence.
    summary = (
        "Strong thunderstorms expected Monday afternoon with damaging winds "
        "and isolated tornadoes possible across the region."
    )
    monkeypatch.setattr(
        "accessiweather.notifications.notification_event_manager.summarize_discussion_change",
        lambda _old, _new: summary,
    )

    dispatched: list[dict] = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    updated = _hwo(
        text=("HAZARDOUS WEATHER OUTLOOK\nStrong storms Monday afternoon with damaging winds.\n"),
        issuance_time=_dt(first) + timedelta(hours=6),
    )
    manager._check_hwo_update(loc, updated, settings_hwo_enabled)

    assert len(dispatched) == 1
    payload = dispatched[0]
    assert payload["message"] == summary
    assert payload["location"] is loc
    assert payload["product"] is updated
    # State advanced.
    assert manager.state.last_hwo_issuance_time == updated.issuance_time
    assert manager.state.last_hwo_text == updated.product_text


# ------------------------------------------------------------------
# 3. Summarizer falls back to generic message
# ------------------------------------------------------------------


@pytest.mark.parametrize("summary_output", [None, "", "   ", "tiny"])
def test_summarizer_fallback_to_generic(manager, settings_hwo_enabled, monkeypatch, summary_output):
    loc = _location(cwa="OKX")

    first = _hwo(issuance_time=datetime(2026, 4, 20, 5, 0, 0, tzinfo=UTC))
    manager._check_hwo_update(loc, first, settings_hwo_enabled)

    monkeypatch.setattr(
        "accessiweather.notifications.notification_event_manager.summarize_discussion_change",
        lambda _old, _new: summary_output,
    )

    dispatched: list[dict] = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    updated = _hwo(
        text="HAZARDOUS WEATHER OUTLOOK\nSlight change.\n",
        issuance_time=_dt(first) + timedelta(hours=6),
    )
    manager._check_hwo_update(loc, updated, settings_hwo_enabled)

    assert len(dispatched) == 1
    assert "Hazardous Weather Outlook updated for OKX" in dispatched[0]["message"]
    assert "tap to view" in dispatched[0]["message"]


# ------------------------------------------------------------------
# 4. Unchanged — no dispatch, no state update
# ------------------------------------------------------------------


def test_unchanged_issuance_no_op(manager, settings_hwo_enabled):
    loc = _location()
    product = _hwo(issuance_time=datetime(2026, 4, 20, 5, 0, 0, tzinfo=UTC))

    manager._check_hwo_update(loc, product, settings_hwo_enabled)
    first_signature = manager.state.last_hwo_summary_signature

    dispatched: list[dict] = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # Exact same product a second time.
    manager._check_hwo_update(loc, product, settings_hwo_enabled)

    assert dispatched == []
    assert manager.state.last_hwo_summary_signature == first_signature
    assert manager.state.last_hwo_issuance_time == product.issuance_time


# ------------------------------------------------------------------
# 5. Rate limited — state advances, dispatch suppressed
# ------------------------------------------------------------------


def test_rate_limited_suppresses_second_dispatch(manager, settings_hwo_enabled, monkeypatch):
    loc = _location()

    first = _hwo(issuance_time=datetime(2026, 4, 20, 5, 0, 0, tzinfo=UTC))
    manager._check_hwo_update(loc, first, settings_hwo_enabled)

    monkeypatch.setattr(
        "accessiweather.notifications.notification_event_manager.summarize_discussion_change",
        lambda _old, _new: "significant hazard update with relevant details here",
    )

    dispatched: list[dict] = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    second = _hwo(
        text="HAZARDOUS WEATHER OUTLOOK\nChanged once.\n",
        issuance_time=_dt(first) + timedelta(hours=1),
    )
    manager._check_hwo_update(loc, second, settings_hwo_enabled)
    assert len(dispatched) == 1

    third = _hwo(
        text="HAZARDOUS WEATHER OUTLOOK\nChanged twice.\n",
        issuance_time=_dt(second) + timedelta(minutes=5),
    )
    manager._check_hwo_update(loc, third, settings_hwo_enabled)

    # Still only one dispatch (second), but state reflects third.
    assert len(dispatched) == 1
    assert manager.state.last_hwo_issuance_time == third.issuance_time
    assert manager.state.last_hwo_text == third.product_text


def test_rate_limit_releases_after_30_minutes(manager, settings_hwo_enabled, monkeypatch):
    loc = _location()

    first = _hwo(issuance_time=datetime(2026, 4, 20, 5, 0, 0, tzinfo=UTC))
    manager._check_hwo_update(loc, first, settings_hwo_enabled)

    monkeypatch.setattr(
        "accessiweather.notifications.notification_event_manager.summarize_discussion_change",
        lambda _old, _new: "sufficiently long change summary for real delivery",
    )

    dispatched: list[dict] = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # First dispatch at t0.
    second = _hwo(text="Changed once", issuance_time=_dt(first) + timedelta(hours=1))
    manager._check_hwo_update(loc, second, settings_hwo_enabled)
    assert len(dispatched) == 1

    # Simulate 31 minutes later by rewinding the bucket timestamp.
    bucket_key = ("HWO", loc.name)
    old_time = manager._last_product_notified_at[bucket_key] - timedelta(minutes=31)
    manager._last_product_notified_at[bucket_key] = old_time

    third = _hwo(text="Changed twice", issuance_time=_dt(second) + timedelta(hours=1))
    manager._check_hwo_update(loc, third, settings_hwo_enabled)
    assert len(dispatched) == 2


# ------------------------------------------------------------------
# 6. Disabled — no dispatch regardless of change
# ------------------------------------------------------------------


def test_disabled_setting_no_dispatch(manager, settings_hwo_disabled, monkeypatch):
    loc = _location()

    first = _hwo(issuance_time=datetime(2026, 4, 20, 5, 0, 0, tzinfo=UTC))
    manager._check_hwo_update(loc, first, settings_hwo_disabled)

    monkeypatch.setattr(
        "accessiweather.notifications.notification_event_manager.summarize_discussion_change",
        lambda _old, _new: "significant hazard update with plenty of detail",
    )

    dispatched: list[dict] = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    updated = _hwo(
        text="HAZARDOUS WEATHER OUTLOOK\nChanged.\n",
        issuance_time=_dt(first) + timedelta(hours=6),
    )
    manager._check_hwo_update(loc, updated, settings_hwo_disabled)

    assert dispatched == []
    # State still advances so we don't spam after re-enable.
    assert manager.state.last_hwo_issuance_time == updated.issuance_time


def test_missing_setting_attribute_defaults_to_true(manager, monkeypatch):
    loc = _location()
    # AppSettings instance stripped of the attribute (simulate pre-Unit-12).
    settings = MagicMock(spec=[])  # no notify_hwo_update attribute

    first = _hwo(issuance_time=datetime(2026, 4, 20, 5, 0, 0, tzinfo=UTC))
    manager._check_hwo_update(loc, first, settings)

    monkeypatch.setattr(
        "accessiweather.notifications.notification_event_manager.summarize_discussion_change",
        lambda _old, _new: "significant change summary that exceeds the threshold length",
    )

    dispatched: list[dict] = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    updated = _hwo(text="Changed", issuance_time=_dt(first) + timedelta(hours=6))
    manager._check_hwo_update(loc, updated, settings)

    assert len(dispatched) == 1


# ------------------------------------------------------------------
# 7. None product and missing cwa_office
# ------------------------------------------------------------------


def test_none_product_is_no_op(manager, settings_hwo_enabled):
    loc = _location()
    dispatched: list = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    manager._check_hwo_update(loc, None, settings_hwo_enabled)

    assert dispatched == []
    assert manager.state.last_hwo_issuance_time is None
    assert manager.state.last_hwo_summary_signature is None


def test_missing_cwa_office_is_no_op(manager, settings_hwo_enabled):
    loc = _location(cwa=None)
    product = _hwo()
    dispatched: list = []
    manager._dispatch_hwo_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    manager._check_hwo_update(loc, product, settings_hwo_enabled)

    assert dispatched == []
    assert manager.state.last_hwo_issuance_time is None


# ------------------------------------------------------------------
# 8. Multi-location — independent buckets
# ------------------------------------------------------------------


def test_multi_location_independent_rate_limits(manager, settings_hwo_enabled, monkeypatch):
    loc_a = _location(name="City A", cwa="OKX")
    loc_b = _location(name="City B", cwa="PHI")

    # Baselines.
    base_a = _hwo(text="A initial", cwa="OKX", issuance_time=datetime(2026, 4, 20, 5, tzinfo=UTC))
    base_b = _hwo(text="B initial", cwa="PHI", issuance_time=datetime(2026, 4, 20, 5, tzinfo=UTC))
    manager._check_hwo_update(loc_a, base_a, settings_hwo_enabled)
    manager._check_hwo_update(loc_b, base_b, settings_hwo_enabled)
    # Baselines may have populated rate-limit buckets via the default
    # _dispatch_hwo_notification no-op path; clear them so the assertions
    # below observe only dispatches triggered by the update-phase calls.
    manager._last_product_notified_at.clear()

    # Multi-location requires per-location state. NotificationState tracks a
    # single last_hwo_*; for independent buckets we verify rate-limit dict
    # keys separate. Re-seed summarizer to always return a long string.
    monkeypatch.setattr(
        "accessiweather.notifications.notification_event_manager.summarize_discussion_change",
        lambda _old, _new: "plenty long summary to clear the 20 char threshold easily",
    )

    dispatched: list[str] = []
    manager._dispatch_hwo_notification = (  # type: ignore[attr-defined]
        lambda **kw: dispatched.append(kw["location"].name)
    )

    updated_a = _hwo(
        text="A changed",
        cwa="OKX",
        issuance_time=_dt(base_a) + timedelta(hours=1),
    )
    updated_b = _hwo(
        text="B changed",
        cwa="PHI",
        issuance_time=_dt(base_b) + timedelta(hours=1),
    )

    manager._check_hwo_update(loc_a, updated_a, settings_hwo_enabled)
    manager._check_hwo_update(loc_b, updated_b, settings_hwo_enabled)

    assert sorted(dispatched) == ["City A", "City B"]
    assert ("HWO", "City A") in manager._last_product_notified_at
    assert ("HWO", "City B") in manager._last_product_notified_at
