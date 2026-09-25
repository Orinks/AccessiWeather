"""
Golden parity data for the Rust `aw-notify` crate.

Drives the Python AlertManager / AlertNotificationSystem, the main-window
event notification flow (NotificationEventManager, HWO/SPS/CLI checks,
Event Center text), the alert sound mapper and mute handling, toast
formatting, activation tokens and the debug helpers with fixed inputs and a
frozen clock, and writes inputs plus results to
`rust/testdata/golden/notify/*.json`.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/notify.py
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ["ACCESSIWEATHER_TEST_MODE"] = "1"

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "notify"

# ---------------------------------------------------------------------------
# Frozen clock. Patched before the app is imported so every
# `from datetime import datetime` inside it sees the frozen class.
# ---------------------------------------------------------------------------

_RealDatetime = _dt.datetime
UTC = _dt.UTC
# `datetime.now()` (naive local time) is reported in this fixed offset so the
# goldens do not depend on the machine's time zone. Rust gets the same offset.
LOCAL_OFFSET = _dt.timezone(_dt.timedelta(hours=-4))


class Clock:
    utc = _RealDatetime(2026, 9, 25, 16, 0, 0, tzinfo=UTC)


class FrozenDatetime(_RealDatetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return Clock.utc.astimezone(LOCAL_OFFSET).replace(tzinfo=None)
        return Clock.utc.astimezone(tz)

    @classmethod
    def utcnow(cls):
        return Clock.utc.replace(tzinfo=None)


_dt.datetime = FrozenDatetime
time.time = lambda: Clock.utc.timestamp()


def set_now(iso: str) -> str:
    Clock.utc = _RealDatetime.fromisoformat(iso).astimezone(UTC)
    return local_now_iso()


def local_now_iso() -> str:
    return Clock.utc.astimezone(LOCAL_OFFSET).isoformat()


import wx  # noqa: E402

from accessiweather.alert_lifecycle import (  # noqa: E402
    AlertChange,
    AlertChangeKind,
    AlertLifecycleDiff,
)
from accessiweather.alert_manager import AlertManager  # noqa: E402
from accessiweather.alert_manager_state import AlertState  # noqa: E402
from accessiweather.alert_notification_formatting import format_accessible_message  # noqa: E402
from accessiweather.alert_notification_system import AlertNotificationSystem  # noqa: E402
from accessiweather.models import (  # noqa: E402
    AppSettings,
    CurrentConditions,
    Location,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
    TextProduct,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.notification_activation import (  # noqa: E402
    NotificationActivationRequest,
    extract_activation_request_from_argv,
    serialize_activation_request,
    write_activation_request_handoff,
)
from accessiweather.notifications import alert_sound_mapper  # noqa: E402
from accessiweather.notifications import sound_player  # noqa: E402
from accessiweather.notifications.toast_notifier import _DesktopNotifierBackend  # noqa: E402
from accessiweather.paths import RuntimeStoragePaths  # noqa: E402
from accessiweather.runtime_state import RuntimeStateManager  # noqa: E402
from accessiweather.ui import main_window_notification_events as mwne  # noqa: E402
from accessiweather.ui.dialogs.debug_alert_dialog import ALERT_PRESETS, DebugAlertDialog  # noqa: E402
from accessiweather.ui.main_window_commands import MainWindowCommandMixin  # noqa: E402
from accessiweather.ui.system_tray import SystemTrayIcon  # noqa: E402

T0 = "2026-09-25T16:00:00+00:00"
MISSING_PACK = "golden-missing-pack"


def at(minutes: float = 0, *, days: float = 0) -> str:
    base = _RealDatetime.fromisoformat(T0)
    return (base + _dt.timedelta(minutes=minutes, days=days)).isoformat()


# ---------------------------------------------------------------------------
# Builders: plain dicts (shared with Rust) -> Python model objects.
# ---------------------------------------------------------------------------


def _parse(value):
    return _RealDatetime.fromisoformat(value) if value else None


def mk_alert(d: dict) -> WeatherAlert:
    kw = dict(d)
    for key in ("onset", "expires", "sent", "effective"):
        if key in kw:
            kw[key] = _parse(kw[key])
    return WeatherAlert(**kw)


def mk_location(d: dict) -> Location:
    return Location(**d)


def mk_product(d: dict) -> TextProduct:
    kw = dict(d)
    kw["issuance_time"] = _parse(kw.get("issuance_time"))
    return TextProduct(**kw)


def mk_change(d: dict) -> AlertChange:
    return AlertChange(
        kind=AlertChangeKind(d["kind"]),
        alert=mk_alert(d["alert"]) if d.get("alert") else None,
        alert_id=d.get("alert_id", ""),
        title=d.get("title", ""),
        old_severity=d.get("old_severity"),
        new_severity=d.get("new_severity"),
    )


def mk_diff(d: dict | None) -> AlertLifecycleDiff | None:
    if d is None:
        return None
    return AlertLifecycleDiff(
        **{
            key: [mk_change(c) for c in d.get(key, [])]
            for key in (
                "new_alerts",
                "updated_alerts",
                "escalated_alerts",
                "extended_alerts",
                "cancelled_alerts",
            )
        }
    )


def mk_weather(d: dict) -> WeatherData:
    data = WeatherData(location=mk_location(d["location"]))
    data.discussion = d.get("discussion")
    data.discussion_issuance_time = _parse(d.get("discussion_issuance_time"))
    if d.get("current") is not None:
        data.current = CurrentConditions(**d["current"])
    if d.get("minutely_precipitation") is not None:
        points = []
        for p in d["minutely_precipitation"]["points"]:
            kw = dict(p)
            kw["time"] = _parse(kw["time"])
            points.append(MinutelyPrecipitationPoint(**kw))
        data.minutely_precipitation = MinutelyPrecipitationForecast(points=points)
    if d.get("alerts") is not None:
        data.alerts = WeatherAlerts(alerts=[mk_alert(a) for a in d["alerts"]["alerts"]])
    data.alert_lifecycle_diff = mk_diff(d.get("alert_lifecycle_diff"))
    return data


def mk_settings(overrides: dict) -> AppSettings:
    return AppSettings(**overrides)


def alert(aid: str, event: str, severity: str = "Severe", **kw) -> dict:
    d = {
        "id": aid,
        "title": kw.pop("title", event),
        "description": kw.pop("description", f"{event} description."),
        "severity": severity,
        "urgency": kw.pop("urgency", "Immediate"),
        "certainty": "Observed",
        "event": event,
        "headline": kw.pop("headline", f"{event} in effect"),
        "expires": kw.pop("expires", "2026-10-30T18:00:00-04:00"),
        "areas": kw.pop("areas", ["Test County"]),
    }
    d.update(kw)
    return d


class RecordingNotifier:
    def __init__(self):
        self.calls: list[dict] = []

    def send_notification(
        self,
        title,
        message,
        timeout=10,
        *,
        sound_event=None,
        sound_candidates=None,
        play_sound=True,
        activation_arguments=None,
    ):
        self.calls.append(
            {
                "title": title,
                "message": message,
                "timeout": timeout,
                "sound_event": sound_event,
                "sound_candidates": sound_candidates,
                "play_sound": play_sound,
                "activation_arguments": activation_arguments,
            }
        )
        return True

    def take(self) -> list[dict]:
        calls, self.calls = self.calls, []
        return calls


def state_text(config_dir: Path) -> str | None:
    path = config_dir / "state" / "runtime_state.json"
    return path.read_text(encoding="utf-8") if path.exists() else None


def write_json(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / name}")


# ---------------------------------------------------------------------------
# Alerts: AlertManager + AlertNotificationSystem
# ---------------------------------------------------------------------------


class FakeRadio:
    def __init__(self):
        self.tuned: list[str] = []

    def tune_for_alerts(self, alerts):
        self.tuned.extend(a.get_unique_id() for a in alerts)


def run_alert_scenario(name: str, settings: dict, steps: list[dict], seed=None) -> dict:
    config_dir = Path(tempfile.mkdtemp(prefix="aw-golden-alerts-"))
    try:
        seed_files = {}
        if seed is not None:
            seed_files = seed(config_dir)
        start = steps[0]["now"]
        set_now(start)
        app_settings = mk_settings(settings)
        manager = AlertManager(
            str(config_dir),
            app_settings.to_alert_settings(),
            runtime_state_manager=RuntimeStateManager(config_dir),
        )
        notifier = RecordingNotifier()
        popups: list[str] = []
        radio = FakeRadio()
        system = AlertNotificationSystem(
            manager,
            notifier,
            app_settings,
            on_alerts_popup=lambda alerts: popups.extend(a.get_unique_id() for a in alerts),
            radio_auto_tuner=radio,
        )
        results = []
        for step in steps:
            set_now(step["now"])
            kind = step["kind"]
            sent = None
            if kind == "process":
                alerts = WeatherAlerts(alerts=[mk_alert(a) for a in step["alerts"]])
                sent = asyncio.run(system.process_and_notify(alerts))
            elif kind == "lifecycle":
                sent = asyncio.run(system.notify_lifecycle_changes(mk_diff(step["diff"])))
            elif kind == "poll":
                window = _PollWindow(system)
                mwne.on_notification_event_data_received(window, mk_weather(step["data"]))
            elif kind == "update_settings":
                new_settings = mk_settings(step["settings"])
                system.settings = new_settings
                system.update_settings(new_settings.to_alert_settings())
            results.append(
                {
                    "sent": sent,
                    "toasts": notifier.take(),
                    "popups": popups[:],
                    "radio": radio.tuned[:],
                    "tokens": round(manager._rate_limit_tokens, 9),
                    "notifications_this_hour": manager.notifications_this_hour,
                    "state": state_text(config_dir),
                }
            )
            popups.clear()
            radio.tuned.clear()
        return {
            "name": name,
            "settings": settings,
            "seed_files": seed_files,
            "steps": steps,
            "results": results,
        }
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


class _PollApp:
    def __init__(self, system):
        self.alert_notification_system = system

    @staticmethod
    def run_async(coro):
        return asyncio.run(coro)


class _PollWindow:
    def __init__(self, system):
        self.app = _PollApp(system)


def seed_unified_fresh(config_dir: Path) -> dict:
    set_now(at(0))
    fresh = mk_alert(FRESH_ALERT)
    stale = mk_alert(STALE_ALERT)
    states = []
    for a, notified in ((fresh, None), (stale, None)):
        s = AlertState(
            alert_id=a.get_unique_id(),
            content_hash=a.get_content_hash(),
            first_seen=Clock.utc - _dt.timedelta(hours=1),
            last_notified=notified,
            severity_priority=a.get_severity_priority(),
        )
        states.append(s.to_dict())
    rsm = RuntimeStateManager(config_dir)
    rsm.save_section("alerts", {"alert_states": states, "last_global_notification": None})
    return {"state/runtime_state.json": state_text(config_dir)}


def seed_legacy(config_dir: Path) -> dict:
    set_now(at(0))
    a = mk_alert(LEGACY_ALERT)
    s = AlertState(
        alert_id=a.get_unique_id(),
        content_hash=a.get_content_hash(),
        first_seen=Clock.utc - _dt.timedelta(hours=2),
        last_notified=Clock.utc - _dt.timedelta(minutes=30),
        notification_count=1,
        severity_priority=a.get_severity_priority(),
    )
    payload = {
        "alert_states": [
            s.to_dict(),
            {"alert_id": "old-format", "content_hash": "abc", "first_seen": at(-60)},
        ],
        "last_global_notification": at(-30),
    }
    text = json.dumps(payload)
    (config_dir / "alert_state.json").write_text(text, encoding="utf-8")
    return {"alert_state.json": text}


FRESH_ALERT = alert(
    "fresh-1", "Flood Warning", "Severe", sent="2026-09-25T11:55:00-04:00"
)
STALE_ALERT = alert(
    "stale-1", "Wind Advisory", "Moderate", sent="2026-09-25T11:00:00-04:00"
)
LEGACY_ALERT = alert("legacy-1", "Winter Storm Warning", "Severe")


def alert_scenarios() -> list[dict]:
    a1 = alert("a1", "Flood Watch", "Moderate", message_type="Alert", urgency="Expected")
    a2 = alert("a2", "Tornado Warning", "Extreme", message_type="Alert", areas=["A", "B", "C", "D"])
    a3 = alert("a3", "Severe Thunderstorm Warning", "Severe", message_type="Update")
    a4 = alert("a4", "Frost Advisory", "Minor")
    a5 = alert("a5", "Dense Fog Advisory", "Moderate", expires="2026-09-25T11:00:00-04:00")
    a6 = alert("a6", "Wind Advisory", "Moderate", sent="2026-09-25T12:01:00-04:00")
    a2_changed = dict(a2, description="Tornado Warning description, updated with a much longer text " * 3)
    a1_esc = dict(a1, severity="Severe", headline="Flood Watch upgraded")
    a1_back = dict(a1, severity="Moderate", headline="Flood Watch downgraded")
    no_id = alert(None, "Heat Advisory", "Moderate", areas=["Z", "Y"], source="NWS")
    basic = run_alert_scenario(
        "basic",
        {"sound_pack": MISSING_PACK},
        [
            {"kind": "process", "now": at(0), "alerts": [a1, a2, a3, a4, a5]},
            {"kind": "process", "now": at(2), "alerts": [a1, a2, a3, a6]},
            {"kind": "process", "now": at(10), "alerts": [a1, a2_changed, a3, a6, no_id]},
            {"kind": "process", "now": at(20), "alerts": [a1_esc, a2_changed]},
            {"kind": "process", "now": at(30), "alerts": [a1_back]},
            {"kind": "process", "now": at(40), "alerts": []},
            {"kind": "process", "now": at(0, days=8), "alerts": [a1_back]},
            {"kind": "process", "now": at(10, days=8), "alerts": [a1_back]},
        ],
    )
    fresh = run_alert_scenario(
        "fresh",
        {"sound_pack": MISSING_PACK},
        [{"kind": "process", "now": at(0), "alerts": [FRESH_ALERT, STALE_ALERT]}],
        seed=seed_unified_fresh,
    )
    legacy = run_alert_scenario(
        "legacy_migration",
        {"sound_pack": MISSING_PACK},
        [
            {"kind": "process", "now": at(0), "alerts": [LEGACY_ALERT]},
            {"kind": "process", "now": at(40), "alerts": [LEGACY_ALERT, alert("n1", "Flood Warning")]},
        ],
        seed=seed_legacy,
    )
    burst = [alert(f"r{i}", f"Event {i}", "Severe") for i in range(5)]
    rate = run_alert_scenario(
        "rate_limit",
        {
            "sound_pack": MISSING_PACK,
            "alert_max_notifications_per_hour": 2,
            "alert_global_cooldown_minutes": 0,
        },
        [
            {"kind": "process", "now": at(0), "alerts": burst},
            {"kind": "process", "now": at(1), "alerts": burst},
            {"kind": "process", "now": at(31), "alerts": burst},
            {
                "kind": "update_settings",
                "now": at(31.5),
                "settings": {
                    "sound_pack": MISSING_PACK,
                    "alert_max_notifications_per_hour": 4,
                    "alert_global_cooldown_minutes": 0,
                },
            },
            {"kind": "process", "now": at(62), "alerts": burst},
            {"kind": "process", "now": at(125), "alerts": burst},
        ],
    )
    specific_settings = {
        "sound_pack": "golden-specific",
        "specific_alert_sound_packs": ["golden-specific"],
        "immediate_alert_details_popups": True,
        "alert_notify_minor": True,
        "alert_ignored_categories": ["heat advisory"],
        "time_display_mode": "both",
        "show_timezone_suffix": True,
        "time_format_12hour": False,
    }
    settings_run = run_alert_scenario(
        "settings",
        specific_settings,
        [
            {
                "kind": "process",
                "now": at(0),
                "alerts": [
                    alert("s1", "Frost Advisory", "Minor", urgency="Future"),
                    alert("s2", "Heat Advisory", "Severe"),
                    alert("s3", "Air Quality Alert", "Unknown"),
                    alert("s4", "Special Weather Statement", "Moderate", description="Issued by the office. Ice possible."),
                    alert("s5", "Hurricane Force Wind Warning", "Extreme", message_type="alert "),
                ],
            },
            {
                "kind": "update_settings",
                "now": at(1),
                "settings": dict(specific_settings, alert_notifications_enabled=False),
            },
            {"kind": "process", "now": at(20), "alerts": [alert("s6", "Tornado Warning", "Extreme")]},
            {
                "kind": "lifecycle",
                "now": at(21),
                "diff": {"cancelled_alerts": [{"kind": "cancelled", "alert_id": "x", "title": "Tornado Warning"}]},
            },
        ],
    )
    lifecycle = run_alert_scenario(
        "lifecycle",
        {"sound_pack": MISSING_PACK},
        [
            {"kind": "lifecycle", "now": at(0), "diff": {}},
            {
                "kind": "lifecycle",
                "now": at(1),
                "diff": {"new_alerts": [{"kind": "new", "alert": a1, "alert_id": "a1", "title": "Flood Watch"}]},
            },
            {
                "kind": "lifecycle",
                "now": at(2),
                "diff": {
                    "updated_alerts": [
                        {"kind": "updated", "alert": a1, "alert_id": "a1", "title": "Flood Watch"},
                        {"kind": "updated", "alert": None, "alert_id": "gone", "title": "Gone"},
                    ],
                    "escalated_alerts": [
                        {
                            "kind": "escalated",
                            "alert": a1_esc,
                            "alert_id": "a1",
                            "title": "Flood Watch",
                            "old_severity": "Moderate",
                            "new_severity": "Severe",
                        }
                    ],
                    "extended_alerts": [
                        {"kind": "extended", "alert": a4, "alert_id": "a4", "title": "Frost Advisory"}
                    ],
                    "cancelled_alerts": [
                        {"kind": "cancelled", "alert_id": "a3", "title": "Winter Storm Warning"},
                        {"kind": "cancelled", "alert_id": "a9", "title": ""},
                    ],
                },
            },
        ],
    )
    poll = run_alert_scenario(
        "poll",
        {"sound_pack": MISSING_PACK},
        [
            {
                "kind": "poll",
                "now": at(0),
                "data": {
                    "location": {"name": "Home", "latitude": 40.0, "longitude": -75.0},
                    "alerts": {"alerts": [a2]},
                    "alert_lifecycle_diff": {
                        "new_alerts": [{"kind": "new", "alert": a2, "alert_id": "a2", "title": "Tornado Warning"}],
                        "cancelled_alerts": [{"kind": "cancelled", "alert_id": "a3", "title": "Flood Watch"}],
                    },
                },
            },
            {
                "kind": "poll",
                "now": at(1),
                "data": {
                    "location": {"name": "Home", "latitude": 40.0, "longitude": -75.0},
                    "alerts": {"alerts": []},
                    "alert_lifecycle_diff": {
                        "updated_alerts": [{"kind": "updated", "alert": a2_changed, "alert_id": "a2", "title": "Tornado Warning"}]
                    },
                },
            },
        ],
    )
    return [basic, fresh, legacy, rate, settings_run, lifecycle, poll]


# ---------------------------------------------------------------------------
# Formatting and sounds
# ---------------------------------------------------------------------------


def formatting_cases() -> list[dict]:
    long_desc = "x" * 99 + "é" + "tail"
    base = alert("f1", "Winter Storm Warning", "Severe", expires="2026-09-26T06:05:00-05:00")
    alerts = [
        base,
        dict(base, severity="", event=None, urgency="Future"),
        dict(base, headline=None, title="", urgency="EXPECTED"),
        dict(base, headline=None, title="Title only", description=long_desc),
        dict(base, description="y" * 100, areas=["A"]),
        dict(base, description="", areas=[]),
        dict(base, areas=["A", "B"], expires="2026-09-25T23:30:00+00:00"),
        dict(base, areas=["A", "B", "C", "D", "E"], expires=None),
        dict(base, expires="2026-09-25T09:00:00+05:30"),
    ]
    settings_variants = [
        None,
        {},
        {"time_display_mode": "utc", "show_timezone_suffix": True},
        {"time_display_mode": "utc", "time_format_12hour": False},
        {"time_display_mode": "both", "show_timezone_suffix": False},
        {"time_display_mode": "both", "show_timezone_suffix": True, "time_format_12hour": False},
        {"time_display_mode": "local", "show_timezone_suffix": True},
    ]
    reasons = ["new_alert", "escalation", "content_changed", "reminder", "extended", "fresh_alert"]
    cases = []
    for i, a in enumerate(alerts):
        for j, s in enumerate(settings_variants):
            reason = reasons[(i + j) % len(reasons)]
            include_areas = (i + j) % 3 != 2
            include_expiration = (i + j) % 4 != 3
            title, message = format_accessible_message(
                mk_alert(a),
                reason,
                include_areas=include_areas,
                include_expiration=include_expiration,
                settings=mk_settings(s) if s is not None else None,
            )
            cases.append(
                {
                    "alert": a,
                    "reason": reason,
                    "include_areas": include_areas,
                    "include_expiration": include_expiration,
                    "settings": s,
                    "title": title,
                    "message": message,
                }
            )
    return cases


def sound_cases() -> dict:
    events = [
        ("Tornado Warning", "Extreme"),
        ("Tornado Watch", "Moderate"),
        ("Severe Thunderstorm Warning", "Severe"),
        ("Severe Thunderstorm Watch", "severe"),
        ("Excessive Heat Watch", "Unknown"),
        ("Air Quality Alert", "Unknown"),
        ("Special Weather Statement", "Minor"),
        ("Red Flag Warning", "critical"),
        ("Winter Weather Advisory", "medium"),
        ("Blizzard Warning", "high"),
        ("Hurricane Force Wind Warning", "Extreme"),
        ("Dense Fog Advisory", "low"),
        ("Coastal Flood Statement", ""),
        ("Freeze Watch", "  Moderate  "),
        ("Rip Current Statement", "weird"),
        (None, "Severe"),
        ("Ice Storm Warning (Test) #2", "Severe"),
    ]
    candidates = []
    for i, (event, severity) in enumerate(events):
        a = alert(f"snd{i}", event or "", severity, title=f"{event or 'Untitled'} issued")
        a["event"] = event
        if i % 3 == 0:
            a["description"] = "Blowing dust and smoke with freezing rain; notice from the office."
        if event is None:
            a["headline"] = None
        for specific in (False, True):
            for reason in (None, "new_alert", "content_changed", "updated", "escalation"):
                candidates.append(
                    {
                        "alert": a,
                        "include_specific": specific,
                        "reason": reason,
                        "candidates": alert_sound_mapper.get_candidate_sound_events(
                            mk_alert(a),
                            include_specific_events=specific,
                            notification_reason=reason,
                        ),
                    }
                )

    looked_up: list = []
    sound_player.get_sound_entry_for_candidates = lambda c, pack: (looked_up.append(list(c)), (None, 1.0))[1]
    sound_player.get_sound_entry = lambda e, pack: (looked_up.append([e]), (None, 1.0))[1]
    mute_cases = []
    for sound_event, cands, muted in [
        (None, ["extreme", "alert", "notify"], []),
        (None, ["alert_updated", "moderate", "alert", "notify"], ["alert_updated"]),
        (None, ["moderate", "alert_updated", "alert", "notify"], ["alert_updated", "alert"]),
        ("notify", ["moderate", "alert"], ["moderate"]),
        ("moderate", ["moderate", "alert"], ["moderate"]),
        (None, ["alert", "notify"], ["alert", "notify"]),
        ("discussion_update", None, ["discussion_update"]),
        ("discussion_update", None, [" data_updated ", ""]),
        (None, None, []),
        (None, [], ["alert"]),
        ("severe_risk", [], []),
    ]:
        looked_up.clear()
        fake = type("N", (), {"soundpack": "default", "muted_sound_events": muted})()
        _DesktopNotifierBackend._play_sound(fake, sound_event, cands)
        mute_cases.append(
            {
                "sound_event": sound_event,
                "candidates": cands,
                "muted": muted,
                "keys": looked_up[0] if looked_up else None,
            }
        )
    return {"candidates": candidates, "mute": mute_cases}


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------


def activation_cases() -> dict:
    requests = [
        {"kind": "discussion", "alert_id": None},
        {"kind": "generic_fallback", "alert_id": None},
        {"kind": "alert_details", "alert_id": "urn:oid:2.49.0.1.840.0.abc.001.1"},
        {"kind": "alert_details", "alert_id": "https://api.weather.gov/alerts/urn:oid:1?x=1&y=2"},
        {"kind": "alert_details", "alert_id": "flood_watch-moderate-flood watch in effect-nws-a,b"},
        {"kind": "alert_details", "alert_id": "ünïcode ~ + % / 100%"},
        {"kind": "discussion", "alert_id": "ignored-but-kept"},
    ]
    serialized = []
    for r in requests:
        req = NotificationActivationRequest(**r)
        serialized.append({"request": r, "token": serialize_activation_request(req)})
    argvs = [
        ["app.exe"],
        ["app.exe", "--debug"],
        ["app.exe", "accessiweather-toast:kind=discussion"],
        ["app.exe", "accessiweather-toast:kind=alert_details&alert_id=a%20b+c"],
        ["app.exe", "accessiweather-toast:kind=alert_details"],
        ["app.exe", "accessiweather-toast:kind=alert_details&alert_id="],
        ["app.exe", "accessiweather-toast:kind=bogus", "accessiweather-toast:kind=discussion"],
        ["app.exe", "accessiweather-toast:alert_id=1&kind=generic_fallback&kind=discussion"],
        ["app.exe", "accessiweather-toast:kind=alert_details&alert_id=%zz%41&junk"],
        ["app.exe", "accessiweather-toast:"],
        ["app.exe", "ACCESSIWEATHER-TOAST:kind=discussion"],
        ["app.exe", "accessiweather-toast:kind=generic_fallback;x=1"],
        ["accessiweather-toast:kind=alert_details&alert_id=%E2%9C%93"],
    ]
    extracted = []
    for argv in argvs:
        req = extract_activation_request_from_argv(argv)
        extracted.append(
            {
                "argv": argv,
                "request": None if req is None else {"kind": req.kind, "alert_id": req.alert_id},
            }
        )
    handoffs = []
    tmp = Path(tempfile.mkdtemp(prefix="aw-golden-handoff-"))
    try:
        paths = RuntimeStoragePaths(config_root=tmp)
        for r in requests:
            write_activation_request_handoff(paths, NotificationActivationRequest(**r))
            handoffs.append(
                {"request": r, "text": paths.activation_request_file.read_text(encoding="utf-8")}
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"serialize": serialized, "extract": extracted, "handoff": handoffs}


# ---------------------------------------------------------------------------
# Events: the main-window flow with a fake window
# ---------------------------------------------------------------------------


class _Cache:
    def __init__(self):
        self.entries: dict = {}

    def has_key(self, key):
        return key in self.entries

    def get(self, key):
        return self.entries[key]


class _ProductService:
    def __init__(self):
        self._cache = _Cache()
        self.stations: list[str] = []

    def daily_climate_station_candidates(self, location):
        return list(self.stations)


class _ConfigManager:
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.settings = AppSettings()
        self.location = None

    def get_settings(self):
        return self.settings

    def get_current_location(self):
        return self.location


class _EventApp:
    def __init__(self, config_dir):
        self.config_manager = _ConfigManager(config_dir)
        self.notifier = RecordingNotifier()
        self.current_weather_data = None


class _EventWindow:
    def __init__(self, config_dir):
        self.app = _EventApp(config_dir)
        self._forecast_product_service = _ProductService()
        self._suppress_startup_text_product_notifications = True
        self._notification_event_manager = None
        self.event_center: list[dict] = []

    def append_event_center_entry(self, text, *, category=None):
        if text:
            self.event_center.append({"category": category, "text": text})


def run_event_scenario(name: str, steps: list[dict], seed_files: dict | None = None) -> dict:
    config_dir = Path(tempfile.mkdtemp(prefix="aw-golden-events-"))
    try:
        for rel, text in (seed_files or {}).items():
            path = config_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        window = _EventWindow(config_dir)
        results = []
        for step in steps:
            local = set_now(step["now"])
            app = window.app
            app.config_manager.settings = mk_settings(step["settings"])
            app.config_manager.location = mk_location(step["location"]) if step.get("location") else None
            cache = window._forecast_product_service._cache
            cache.entries = {}
            cwa = (step.get("location") or {}).get("cwa_office")
            if "hwo" in step:
                cache.entries[f"nws_text_product:HWO:{cwa}"] = (
                    mk_product(step["hwo"]) if step["hwo"] else None
                )
            if "sps" in step:
                cache.entries[f"nws_text_product:SPS:{cwa}"] = [mk_product(p) for p in step["sps"]]
            window._forecast_product_service.stations = step.get("cli_stations", [])
            for station, product in step.get("cli_cache", {}).items():
                cache.entries[f"iem_text_product:CLI:{station}:latest"] = (
                    mk_product(product) if product else None
                )
            active = step.get("active_alerts")
            app.current_weather_data = (
                None
                if active is None
                else WeatherData(
                    location=Location("x", 0, 0),
                    alerts=WeatherAlerts(alerts=[mk_alert(a) for a in active]),
                )
            )
            if "suppress_startup" in step:
                window._suppress_startup_text_product_notifications = step["suppress_startup"]
            mwne.process_notification_events(window, mk_weather(step["weather"]))
            results.append(
                {
                    "local_now": local,
                    "toasts": app.notifier.take(),
                    "event_center": window.event_center[:],
                    "suppress_after": window._suppress_startup_text_product_notifications,
                    "state": state_text(config_dir),
                }
            )
            window.event_center.clear()
        return {"name": name, "seed_files": seed_files or {}, "steps": steps, "results": results}
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


HOME = {
    "name": "Lumberton",
    "latitude": 39.96,
    "longitude": -74.8,
    "country_code": "US",
    "cwa_office": "PHI",
    "forecast_zone_id": "https://api.weather.gov/zones/forecast/NJZ017",
    "county_zone_id": "NJC005",
    "fire_zone_id": "NJZ017/",
}

ALL_ON = {
    "notify_discussion_update": True,
    "notify_severe_risk_change": True,
    "notify_minutely_precipitation_start": True,
    "notify_minutely_precipitation_stop": True,
    "notify_precipitation_likelihood": True,
    "notify_hwo_update": True,
    "notify_sps_issued": True,
    "notify_daily_climate_report_update": True,
    "sound_enabled": True,
}

AFD_1 = (
    "\n000\nFXUS61 KPHI 290645\nAFDPHI\n\nArea Forecast Discussion\n"
    "National Weather Service Mount Holly NJ\n245 AM EDT Wed Sep 25 2026\n\n"
    ".KEY MESSAGES...\n1) Rain late.\n\n&&\n\n.NEAR TERM...\nClouds increase.\n$$\n"
)
AFD_2 = (
    "\n000\nFXUS61 KPHI 291732\nAFDPHI\n\nArea Forecast Discussion\n"
    "National Weather Service Mount Holly NJ\n132 PM EDT Wed Sep 25 2026\n\n"
    ".WHAT HAS CHANGED...\nRain arrives earlier; totals raised.\n\n&&\n"
    ".KEY MESSAGES...\n1) Rain late.\n\n&&\n"
)
AFD_3 = (
    "\n000\nFXUS61 KPHI 292100\nAFDPHI\n\nArea Forecast Discussion\n"
    "National Weather Service Mount Holly NJ\n500 PM EDT Wed Sep 25 2026\n\n"
    ".WHAT HAS CHANGED...\nNo significant changes.\n\n&&\n.KEY MESSAGES...\n1) Rain late.\n\n&&\n"
)
AFD_4 = "Discussion without a header\nNew line here\n$$"


def hwo(text: str, issued: str) -> dict:
    return {
        "product_type": "HWO",
        "product_id": f"HWO-{issued}",
        "cwa_office": "PHI",
        "issuance_time": issued,
        "product_text": text,
        "headline": None,
    }


def sps(pid: str, text: str, headline: str | None, issued: str = "2026-09-25T15:00:00+00:00") -> dict:
    return {
        "product_type": "SPS",
        "product_id": pid,
        "cwa_office": "PHI",
        "issuance_time": issued,
        "product_text": text,
        "headline": headline,
    }


def cli(text: str, issued: str, station: str = "PHL") -> dict:
    return {
        "product_type": "CLI",
        "product_id": f"CLI-{issued}",
        "cwa_office": station,
        "issuance_time": issued,
        "product_text": text,
        "headline": None,
    }


def minutely(start: str, values: list[tuple]) -> dict:
    base = _RealDatetime.fromisoformat(start)
    points = []
    for i, (intensity, prob, kind) in enumerate(values):
        p = {"time": (base + _dt.timedelta(minutes=i)).isoformat()}
        if intensity is not None:
            p["precipitation_intensity"] = intensity
        if prob is not None:
            p["precipitation_probability"] = prob
        if kind is not None:
            p["precipitation_type"] = kind
        points.append(p)
    return {"points": points}


def weather(**kw) -> dict:
    d = {"location": HOME}
    d.update(kw)
    return d


def event_scenarios() -> list[dict]:
    dry = [(0.0, 0.0, None)] * 30
    rain_in_5 = [(0.0, 0.1, None)] * 5 + [(0.8, 0.9, "rain")] * 25
    rain_in_20 = [(0.0, 0.2, None)] * 20 + [(0.8, 0.75, "rain")] * 10
    snow_stops = [(0.5, 0.9, "snow")] * 3 + [(0.001, 0.1, None)] * 27
    sps_local = sps(
        "SPS-LOCAL",
        "\nNJZ017-018-252000-\nBurlington NJ-\n...Fire weather concerns this afternoon...\n",
        "Elevated fire weather concerns this afternoon",
    )
    sps_other = sps(
        "SPS-OTHER",
        "\nPAZ070>071-252000-\nBucks PA-\n...Strong thunderstorm near Doylestown...\n",
        "Strong thunderstorm near Doylestown",
    )
    sps_event = sps(
        "SPS-EVENT",
        "\nNJZ017-252000-\nStrong thunderstorm impacting central counties.\n",
        "Strong thunderstorm impacting central counties",
    )
    sps_noheadline = sps(
        "SPS-NOHEAD",
        "\n\n   " + "A very long first line of text about gusty winds " * 5 + "\nsecond line",
        None,
    )
    sps_alert = alert(
        "sps-alert",
        "Special Weather Statement",
        "Moderate",
        headline="Strong thunderstorm impacting central counties",
        description="Strong thunderstorm impacting central counties with hail.",
    )
    cli_1 = cli(
        "CLIMATE REPORT\nTEMPERATURE (F)\n  MAXIMUM   71\n  MINIMUM   55\nPRECIPITATION (IN)\n  TODAY 0.00\n",
        "2026-09-25T10:00:00+00:00",
    )
    cli_2 = cli(
        "CLIMATE REPORT\nTEMPERATURE (F)\n  MAXIMUM   74\n  MINIMUM   55\nPRECIPITATION (IN)\n  TODAY 0.12\nSNOWFALL 0.0\nAVERAGE 63\n",
        "2026-09-25T20:00:00+00:00",
    )
    hwo_1 = hwo("HAZARDOUS WEATHER OUTLOOK\n.DAY ONE...\nNo hazardous weather is expected.\n$$", "2026-09-25T09:00:00+00:00")
    hwo_2 = hwo(
        "HAZARDOUS WEATHER OUTLOOK\n.DAY ONE...\nNo hazardous weather is expected.\n"
        "Thunderstorms with damaging winds are possible this evening.\n$$",
        "2026-09-25T19:00:00+00:00",
    )
    hwo_3 = hwo(hwo_2["product_text"] + "\nShort.", "2026-09-25T19:40:00+00:00")
    hwo_4 = hwo("HAZARDOUS WEATHER OUTLOOK\nOk.", "2026-09-25T21:00:00+00:00")

    full = run_event_scenario(
        "full_flow",
        [
            {  # startup: everything baselines, suppression consumed
                "now": at(0),
                "settings": ALL_ON,
                "location": HOME,
                "weather": weather(
                    discussion=AFD_1,
                    discussion_issuance_time="2026-09-25T06:45:00+00:00",
                    current={"severe_weather_risk": 25},
                    minutely_precipitation=minutely(at(0), dry),
                ),
                "hwo": hwo_1,
                "sps": [sps_other],
                "cli_stations": ["PHL", "ILG"],
                "cli_cache": {"PHL": None, "ILG": cli_1},
                "active_alerts": [],
            },
            {  # discussion update with WHAT HAS CHANGED, risk jump, rain in 5, HWO change, SPS local
                "now": at(10),
                "settings": ALL_ON,
                "location": HOME,
                "weather": weather(
                    discussion=AFD_2,
                    discussion_issuance_time="2026-09-25T17:32:00+00:00",
                    current={"severe_weather_risk": 65},
                    minutely_precipitation=minutely(at(10), rain_in_5),
                ),
                "hwo": hwo_2,
                "sps": [sps_other, sps_local, sps_event],
                "cli_stations": ["PHL", "ILG"],
                "cli_cache": {"ILG": cli(cli_2["product_text"], "2026-09-25T20:00:00+00:00", "ILG")},
                "active_alerts": [sps_alert],
            },
            {  # no-change AFD, risk down, countdown no renotify, HWO rate limited, SPS rate limited
                "now": at(20),
                "settings": ALL_ON,
                "location": HOME,
                "weather": weather(
                    discussion=AFD_3,
                    discussion_issuance_time="2026-09-25T21:00:00+00:00",
                    current={"severe_weather_risk": 10},
                    minutely_precipitation=minutely(at(20), rain_in_5[2:]),
                ),
                "hwo": hwo_3,
                "sps": [sps_local, sps_noheadline],
                "cli_stations": ["ILG"],
                "cli_cache": {"ILG": cli(cli_2["product_text"], "2026-09-25T20:00:00+00:00", "ILG")},
                "active_alerts": [sps_alert],
            },
            {  # metadata-time AFD fallback, far-off rain (pending), snow stop, HWO after window
                "now": at(60),
                "settings": dict(ALL_ON, sound_enabled=False),
                "location": HOME,
                "weather": weather(
                    discussion=AFD_4,
                    discussion_issuance_time="2026-09-25T22:15:00-04:00",
                    current={"severe_weather_risk": 85},
                    minutely_precipitation=minutely(at(60), rain_in_20),
                ),
                "hwo": hwo_4,
                "sps": [],
                "active_alerts": None,
            },
            {
                "now": at(70),
                "settings": dict(ALL_ON, precipitation_sensitivity="moderate"),
                "location": HOME,
                "weather": weather(minutely_precipitation=minutely(at(70), snow_stops)),
                "sps": [sps_noheadline, dict(sps_local, product_id="SPS-LOCAL-2")],
            },
            {
                "now": at(80),
                "settings": dict(
                    ALL_ON,
                    notify_minutely_precipitation_stop=False,
                    precipitation_likelihood_threshold=0.95,
                ),
                "location": HOME,
                "weather": weather(minutely_precipitation=minutely(at(80), dry)),
            },
            {  # every toggle off: nothing runs, no state write
                "now": at(90),
                "settings": {k: False for k in ALL_ON},
                "location": HOME,
                "weather": weather(discussion="x", discussion_issuance_time="2026-09-26T00:00:00+00:00"),
            },
            {  # no location
                "now": at(91),
                "settings": ALL_ON,
                "location": None,
                "weather": weather(),
            },
        ],
    )

    no_cwa = dict(HOME, cwa_office=None)
    startup_suppression = run_event_scenario(
        "startup_suppression",
        [
            {
                "now": at(0),
                "settings": {"notify_discussion_update": True, "notify_daily_climate_report_update": True},
                "location": HOME,
                "weather": weather(discussion=AFD_1, discussion_issuance_time="2026-09-25T06:45:00+00:00"),
                "hwo": hwo_1,
                "sps": [],
                "suppress_startup": False,
            },
            {  # suppression turned on again (e.g. a restart): newer products baseline silently
                "now": at(5),
                "settings": {"notify_discussion_update": True, "notify_daily_climate_report_update": True},
                "location": HOME,
                "weather": weather(discussion=AFD_2, discussion_issuance_time="2026-09-25T17:32:00+00:00"),
                "hwo": hwo_2,
                "sps": [sps_local],
                "cli_stations": ["PHL"],
                "cli_cache": {"PHL": cli_1},
                "suppress_startup": True,
            },
            {
                "now": at(6),
                "settings": {"notify_discussion_update": True, "notify_daily_climate_report_update": True},
                "location": HOME,
                "weather": weather(discussion=AFD_3, discussion_issuance_time="2026-09-25T21:00:00+00:00"),
                "cli_stations": ["PHL"],
                "cli_cache": {"PHL": cli_2},
            },
            {
                "now": at(7),
                "settings": {"notify_hwo_update": True, "notify_sps_issued": False},
                "location": no_cwa,
                "weather": weather(location=no_cwa),
                "hwo": hwo_4,
                "sps": [sps_other],
            },
        ],
    )

    legacy_seed = {
        "notification_event_state.json": json.dumps(
            {
                "last_discussion_issuance_time": "2026-09-25T06:45:00+00:00",
                "last_discussion_text": AFD_1,
                "last_severe_risk": 35,
                "last_check_time": "2026-09-25T02:50:00",
            }
        )
    }
    legacy = run_event_scenario(
        "legacy_migration",
        [
            {
                "now": at(0),
                "settings": {"notify_discussion_update": True, "notify_severe_risk_change": True},
                "location": HOME,
                "weather": weather(
                    discussion=AFD_2,
                    discussion_issuance_time="2026-09-25T17:32:00+00:00",
                    current={"severe_weather_risk": 38},
                ),
                "suppress_startup": False,
            }
        ],
        legacy_seed,
    )
    return [full, startup_suppression, legacy]


# ---------------------------------------------------------------------------
# Debug helpers
# ---------------------------------------------------------------------------


def debug_data() -> dict:
    set_now(at(0))
    presets = []
    for preset in ALERT_PRESETS:
        fake = type("D", (), {})()
        a = DebugAlertDialog._make_alert(fake, preset)
        cands = alert_sound_mapper.get_candidate_sound_events(a)
        presets.append(
            {
                "label": preset.label,
                "id": a.id,
                "expires": a.expires.isoformat(),
                "candidates_text": " → ".join(cands),
                "title": f"{preset.severity.upper()} ALERT: {preset.event}",
                "message": preset.headline + (f"\n{preset.description}" if preset.description else ""),
            }
        )

    boxes: list = []
    wx.MessageBox = lambda message, caption="", style=0, *a, **k: boxes.append(
        {"message": message, "caption": caption}
    )
    app = type("A", (), {})()
    app.config_manager = _ConfigManager(Path(tempfile.gettempdir()))
    app.config_manager.location = Location("Home Town", 40.0, -75.0)
    fake = type("W", (), {})()
    fake.app = app
    MainWindowCommandMixin._on_test_notifications(fake)
    SystemTrayIcon._on_test_notifications_menu(fake, None)
    return {"local_now": local_now_iso(), "presets": presets, "menu": boxes[0], "tray": boxes[1]}


def main() -> int:
    write_json("alerts.json", alert_scenarios())
    write_json("formatting.json", formatting_cases())
    write_json("sounds.json", sound_cases())
    write_json("activation.json", activation_cases())
    write_json("events.json", event_scenarios())
    write_json("debug.json", debug_data())
    return 0


if __name__ == "__main__":
    sys.exit(main())
