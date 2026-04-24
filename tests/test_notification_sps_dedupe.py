"""
Tests for Unit 11 — SPS (Special Weather Statement) informational notifications.

Covers ``NotificationEventManager._check_sps_new``:

1. Cold start — first fetch records all IDs silently.
2. Case B (informational) — SPS with no matching active alert → dispatch.
3. Case A (event-style) — SPS whose headline text is echoed by an active
   "Special Weather Statement" alert → suppressed, ID still recorded.
4. Expiration — previously-seen SPS disappears → silently removed from state.
5. Headline null fallback — body uses first non-empty line of product_text,
   truncated at 160 chars with ellipsis.
6. Rate limited — new Case B within 30 min → state advances, dispatch suppressed.
7. Disabled — ``notify_sps_issued = False`` → no dispatch ever.
8. Mixed — Case A + Case B in same fetch → only Case B notifies; both stored.
9. Realistic replay — fire-weather SPS plus unrelated SPS alert → fire-weather
   notifies (Case B), the alert-matching product does not (Case A).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from accessiweather.models import AppSettings, Location, TextProduct, WeatherAlert
from accessiweather.notifications.notification_event_manager import (
    NotificationEventManager,
)


def _location(name: str = "Test City", cwa: str | None = "PHI") -> Location:
    return Location(
        name=name,
        latitude=40.0,
        longitude=-74.0,
        country_code="US",
        cwa_office=cwa,
    )


def _sps(
    product_id: str = "SPS-PHI-1",
    headline: str | None = "FIRE WEATHER PLANNING FORECAST",
    product_text: str = "...Fire weather planning forecast for the region...",
    issuance_time: datetime | None = None,
    cwa: str = "PHI",
) -> TextProduct:
    if issuance_time is None:
        issuance_time = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
    return TextProduct(
        product_type="SPS",
        product_id=product_id,
        cwa_office=cwa,
        issuance_time=issuance_time,
        product_text=product_text,
        headline=headline,
    )


def _alert(
    event: str = "Special Weather Statement",
    headline: str | None = "Strong thunderstorm in effect",
    description: str = "Strong thunderstorm in effect for the area",
    expires: datetime | None = None,
) -> WeatherAlert:
    if expires is None:
        expires = datetime(2099, 1, 1, tzinfo=UTC)
    return WeatherAlert(
        title=headline or "Alert",
        description=description,
        event=event,
        headline=headline,
        expires=expires,
    )


@pytest.fixture
def manager():
    return NotificationEventManager(state_file=None)


@pytest.fixture
def settings_sps_enabled():
    s = AppSettings()
    s.notify_sps_issued = True  # type: ignore[attr-defined]
    return s


@pytest.fixture
def settings_sps_disabled():
    s = AppSettings()
    s.notify_sps_issued = False  # type: ignore[attr-defined]
    return s


# ------------------------------------------------------------------
# 1. Cold start — record all IDs silently
# ------------------------------------------------------------------


def test_cold_start_records_ids_no_dispatch(manager, settings_sps_enabled):
    loc = _location()
    products = [
        _sps(product_id="SPS-1", headline="FIRE WEATHER"),
        _sps(product_id="SPS-2", headline="POLLEN FORECAST"),
        _sps(product_id="SPS-3", headline="COORDINATION STATEMENT"),
    ]

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    manager._check_sps_new(loc, products, [], settings_sps_enabled)

    assert dispatched == []
    assert manager.state.last_sps_product_ids == {"SPS-1", "SPS-2", "SPS-3"}


# ------------------------------------------------------------------
# 2. Case B (informational) — no matching alert → dispatch
# ------------------------------------------------------------------


def test_case_b_informational_dispatches(manager, settings_sps_enabled):
    loc = _location()

    # Cold-start with empty list so we're past cold-start on the next call.
    manager._check_sps_new(loc, [], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    new = _sps(
        product_id="SPS-FIRE",
        headline="FIRE WEATHER PLANNING FORECAST",
        product_text="...FIRE WEATHER PLANNING FORECAST...\nElevated fire weather conditions.",
    )
    manager._check_sps_new(loc, [new], [], settings_sps_enabled)

    assert len(dispatched) == 1
    payload = dispatched[0]
    assert payload["location"] is loc
    assert payload["product"] is new
    assert "FIRE WEATHER PLANNING FORECAST" in payload["message"]
    assert "PHI" in payload["message"]
    assert "SPS-FIRE" in manager.state.last_sps_product_ids


# ------------------------------------------------------------------
# 3. Case A (event-style) — alert headline echoes product text → suppressed
# ------------------------------------------------------------------


def test_case_a_event_style_suppressed(manager, settings_sps_enabled):
    loc = _location()
    manager._check_sps_new(loc, [], [], settings_sps_enabled)  # past cold-start

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    alert = _alert(
        headline="Strong thunderstorm producing pea size hail",
        description="Strong thunderstorm producing pea size hail in Central County",
    )
    product = _sps(
        product_id="SPS-TSTM",
        headline="Strong thunderstorm producing pea size hail",
        product_text=(
            "...SPECIAL WEATHER STATEMENT...\n"
            "Strong thunderstorm producing pea size hail near town.\n"
            "Move indoors."
        ),
    )

    manager._check_sps_new(loc, [product], [alert], settings_sps_enabled)

    assert dispatched == []
    # Case A still records the ID so we don't re-evaluate next cycle.
    assert "SPS-TSTM" in manager.state.last_sps_product_ids


# ------------------------------------------------------------------
# 4. Expiration — previously-seen SPS disappears
# ------------------------------------------------------------------


def test_expired_product_silently_removed(manager, settings_sps_enabled):
    loc = _location()
    # Seed state with three SPS ids.
    seed = [
        _sps(product_id="SPS-A"),
        _sps(product_id="SPS-B"),
        _sps(product_id="SPS-C"),
    ]
    manager._check_sps_new(loc, seed, [], settings_sps_enabled)
    assert manager.state.last_sps_product_ids == {"SPS-A", "SPS-B", "SPS-C"}

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # Next fetch: only A remains.
    manager._check_sps_new(loc, [_sps(product_id="SPS-A")], [], settings_sps_enabled)

    assert dispatched == []
    assert manager.state.last_sps_product_ids == {"SPS-A"}


# ------------------------------------------------------------------
# 5. Headline null — falls back to first line of product_text, truncated
# ------------------------------------------------------------------


def test_headline_null_fallback_truncation(manager, settings_sps_enabled):
    loc = _location()
    manager._check_sps_new(loc, [], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # First non-empty line is a very long sentence that must be truncated.
    long_line = "A" * 400
    product = _sps(
        product_id="SPS-LONG",
        headline=None,
        product_text=f"\n\n{long_line}\nSecond line content.",
    )
    manager._check_sps_new(loc, [product], [], settings_sps_enabled)

    assert len(dispatched) == 1
    message = dispatched[0]["message"]
    assert len(message) <= 160
    assert message.endswith("...")
    # Ensure the truncation comes from the first line (A's), not the fallback.
    assert message.startswith("A")


def test_headline_null_short_first_line(manager, settings_sps_enabled):
    loc = _location()
    manager._check_sps_new(loc, [], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    product = _sps(
        product_id="SPS-SHORT",
        headline=None,
        product_text="\n\nShort summary line.\nLater details.",
    )
    manager._check_sps_new(loc, [product], [], settings_sps_enabled)

    assert len(dispatched) == 1
    assert dispatched[0]["message"].startswith("Short summary line.")
    assert not dispatched[0]["message"].endswith("...")


# ------------------------------------------------------------------
# 6. Rate limited — state advances, no dispatch
# ------------------------------------------------------------------


def test_rate_limited_suppresses_within_window(manager, settings_sps_enabled):
    loc = _location()
    manager._check_sps_new(loc, [], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # First Case B dispatches.
    first = _sps(product_id="SPS-1", headline="FIRE WEATHER FORECAST")
    manager._check_sps_new(loc, [first], [], settings_sps_enabled)
    assert len(dispatched) == 1

    # Second Case B within 30 min — state advances, no dispatch.
    second = _sps(product_id="SPS-2", headline="POLLEN OUTLOOK")
    manager._check_sps_new(loc, [first, second], [], settings_sps_enabled)

    assert len(dispatched) == 1
    assert manager.state.last_sps_product_ids == {"SPS-1", "SPS-2"}


def test_rate_limit_releases_after_30_minutes(manager, settings_sps_enabled):
    loc = _location()
    manager._check_sps_new(loc, [], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    first = _sps(product_id="SPS-1", headline="FIRE WEATHER FORECAST")
    manager._check_sps_new(loc, [first], [], settings_sps_enabled)
    assert len(dispatched) == 1

    # Rewind the rate-limit bucket by 31 min.
    key = ("SPS", loc.name)
    manager._last_product_notified_at[key] -= timedelta(minutes=31)

    second = _sps(product_id="SPS-2", headline="POLLEN OUTLOOK")
    manager._check_sps_new(loc, [first, second], [], settings_sps_enabled)

    assert len(dispatched) == 2


# ------------------------------------------------------------------
# 7. Disabled — never dispatches
# ------------------------------------------------------------------


def test_disabled_setting_no_dispatch(manager, settings_sps_disabled):
    loc = _location()
    manager._check_sps_new(loc, [], [], settings_sps_disabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    product = _sps(product_id="SPS-1", headline="FIRE WEATHER FORECAST")
    manager._check_sps_new(loc, [product], [], settings_sps_disabled)

    assert dispatched == []
    # State still advances so re-enabling the toggle doesn't spam.
    assert "SPS-1" in manager.state.last_sps_product_ids


def test_missing_setting_attribute_defaults_to_true(manager):
    loc = _location()
    settings = MagicMock(spec=[])  # no notify_sps_issued attr
    manager._check_sps_new(loc, [], [], settings)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    product = _sps(product_id="SPS-1", headline="FIRE WEATHER FORECAST")
    manager._check_sps_new(loc, [product], [], settings)

    assert len(dispatched) == 1


# ------------------------------------------------------------------
# 8. Mixed Case A + Case B in same fetch
# ------------------------------------------------------------------


def test_mixed_case_a_and_case_b(manager, settings_sps_enabled):
    loc = _location()
    manager._check_sps_new(loc, [], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # Case A: product text contains alert's headline.
    case_a_alert = _alert(headline="Dense fog advisory in effect")
    case_a = _sps(
        product_id="SPS-FOG",
        headline="Dense fog advisory in effect",
        product_text="...Dense fog advisory in effect until 9 AM...",
    )
    # Case B: no matching alert event.
    case_b = _sps(
        product_id="SPS-FIRE",
        headline="FIRE WEATHER PLANNING FORECAST",
        product_text="...FIRE WEATHER PLANNING FORECAST for the region...",
    )

    manager._check_sps_new(loc, [case_a, case_b], [case_a_alert], settings_sps_enabled)

    assert len(dispatched) == 1
    assert dispatched[0]["product"].product_id == "SPS-FIRE"
    assert manager.state.last_sps_product_ids == {"SPS-FOG", "SPS-FIRE"}


# ------------------------------------------------------------------
# 9. Realistic replay — PHI fire-weather + unrelated active SPS alert
# ------------------------------------------------------------------


def test_realistic_phi_fire_weather_replay(manager, settings_sps_enabled):
    loc = _location(name="Philadelphia", cwa="PHI")
    manager._check_sps_new(loc, [], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    fire_weather = _sps(
        product_id="PHI-SPS-FW-20260416",
        headline="Fire Weather Planning Forecast",
        product_text=(
            "SPECIAL WEATHER STATEMENT\n"
            "Fire Weather Planning Forecast\n"
            "Relative humidity values of 25 to 30 percent will develop...\n"
        ),
        issuance_time=datetime(2026, 4, 16, 15, 0, tzinfo=UTC),
        cwa="PHI",
    )
    tstm_event_product = _sps(
        product_id="PHI-SPS-TSTM-20260416",
        headline="Strong thunderstorm impacting central counties",
        product_text=(
            "SPECIAL WEATHER STATEMENT\n"
            "Strong thunderstorm impacting central counties.\n"
            "Hail up to pea size and wind gusts to 40 mph.\n"
        ),
        issuance_time=datetime(2026, 4, 16, 16, 0, tzinfo=UTC),
        cwa="PHI",
    )
    # Active alert mirrors the tstm product (Case A).
    matching_alert = _alert(
        event="Special Weather Statement",
        headline="Strong thunderstorm impacting central counties",
        description="Strong thunderstorm impacting central counties with hail.",
    )

    manager._check_sps_new(
        loc,
        [fire_weather, tstm_event_product],
        [matching_alert],
        settings_sps_enabled,
    )

    # Only fire-weather dispatches; tstm is Case A.
    assert len(dispatched) == 1
    assert dispatched[0]["product"].product_id == "PHI-SPS-FW-20260416"
    # Both IDs recorded.
    assert manager.state.last_sps_product_ids == {
        "PHI-SPS-FW-20260416",
        "PHI-SPS-TSTM-20260416",
    }


# ------------------------------------------------------------------
# Misc — non-US / no cwa no-ops + empty list mid-lifecycle
# ------------------------------------------------------------------


def test_empty_products_after_cold_start_no_op(manager, settings_sps_enabled):
    loc = _location()
    # Seed some IDs.
    manager._check_sps_new(loc, [_sps(product_id="SPS-1")], [], settings_sps_enabled)

    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # Empty fetch: all prior IDs expire silently.
    manager._check_sps_new(loc, [], [], settings_sps_enabled)
    assert dispatched == []
    assert manager.state.last_sps_product_ids == set()


def test_none_products_list_is_no_op(manager, settings_sps_enabled):
    """Defensive: fetcher returned None → treat as empty, no crash."""
    loc = _location()
    dispatched: list[dict] = []
    manager._dispatch_sps_notification = lambda **kw: dispatched.append(kw)  # type: ignore[attr-defined]

    # Passing None should be tolerated and treated like [].
    manager._check_sps_new(loc, None, [], settings_sps_enabled)  # type: ignore[arg-type]
    assert dispatched == []
