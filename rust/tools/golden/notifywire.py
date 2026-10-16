"""
Golden parity data for the app's notification wiring (`ui/weather_events.rs`).

Runs the Python main-window glue end to end over sequences of WeatherData
snapshots: `_on_weather_data_received` (alert processing, the event checks
against the pre-warmed text-product cache, the refresh sound), the 60-second
`on_notification_event_data_received` poll, `_on_weather_error`, the
Forecaster Notes daily climate check, `refresh_runtime_settings` and the
immediate alert popups. The AlertNotificationSystem, NotificationEventManager,
sound selection and popup routing are the real ones; the notifier records
toasts instead of showing them, sound lookups are recorded instead of played,
dialogs and the radio are recorded, and the clock is frozen (see notify.py).
Writes `rust/testdata/golden/notifywire/sequences.json`.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/notifywire.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# Freezes the clock before the app is imported; shares the model builders.
import notify as nf
import wx
from common import write

from accessiweather import app as app_module
from accessiweather.alert_manager import AlertManager
from accessiweather.alert_notification_system import AlertNotificationSystem
from accessiweather.app import AccessiWeatherApp
from accessiweather.notifications import sound_player
from accessiweather.notifications.toast_notifier import _DesktopNotifierBackend
from accessiweather.runtime_state import RuntimeStateManager
from accessiweather.ui import main_window_notification_events as mwne
from accessiweather.ui.dialogs.forecast_products_dialog import ForecastProductsDialog
from accessiweather.ui.main_window_display import MainWindowDisplayMixin
from accessiweather.ui.main_window_refresh import MainWindowRefreshMixin

at = nf.at

# ---------------------------------------------------------------------------
# Recorders
# ---------------------------------------------------------------------------

SOUNDS: list[dict] = []
POPUPS: list[dict] = []
RADIO: list[list[str]] = []
DEFERRED: list = []

# The notifier and the window resolve sounds through these two lookups.
sound_player.get_sound_entry = lambda event, pack: (
    SOUNDS.append({"event": event, "pack": pack}),
    (None, 1.0),
)[1]
sound_player.get_sound_entry_for_candidates = lambda candidates, pack: (
    SOUNDS.append({"candidates": list(candidates), "pack": pack}),
    (None, 1.0),
)[1]
app_module.show_alert_dialog = lambda parent, alert, settings=None: POPUPS.append(
    {"details": alert.get_unique_id()}
)
app_module.show_alerts_summary_dialog = lambda parent, alerts: POPUPS.append(
    {"summary": [a.get_unique_id() for a in alerts]}
)
# `_queue_immediate_alert_popup` defers the dialog; run it after the step.
wx.CallAfter = lambda fn, *args, **kwargs: DEFERRED.append((fn, args, kwargs))


class Notifier:
    """`SafeDesktopNotifier` with the toast recorded instead of shown."""

    def __init__(self, settings):
        self.sound_enabled = bool(settings.sound_enabled)
        self.soundpack = settings.sound_pack
        self.muted_sound_events = list(settings.muted_sound_events)
        self.toasts: list[dict] = []

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
        # `_DesktopNotifierBackend.send_notification`: the sound, then the toast.
        if self.sound_enabled and play_sound:
            _DesktopNotifierBackend._play_sound(self, sound_event, sound_candidates)
        self.toasts.append(
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


class Radio:
    def tune_for_alerts(self, alerts):
        RADIO.append([a.get_unique_id() for a in alerts])


# ---------------------------------------------------------------------------
# The app and main window, reduced to what the notification glue touches
# ---------------------------------------------------------------------------


class _Widget:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _Presenter:
    @staticmethod
    def present(weather_data):
        return SimpleNamespace(
            current_conditions=None, source_attribution=None, status_messages=[], forecast=None
        )


class FakeApp:
    _queue_immediate_alert_popup = AccessiWeatherApp._queue_immediate_alert_popup
    _show_immediate_alert_popup = AccessiWeatherApp._show_immediate_alert_popup
    refresh_runtime_settings = AccessiWeatherApp.refresh_runtime_settings

    def __init__(self, config_dir: Path, settings, location):
        self.config_manager = nf._ConfigManager(config_dir)
        self.config_manager.settings = settings
        self.config_manager.location = location
        self.weather_client = None
        self.presenter = _Presenter()
        self.taskbar_icon_updater = None
        self.current_weather_data = None
        self.is_updating = False
        self._notifier = Notifier(settings)
        self.notifier = self._notifier
        self.alert_notification_system = AlertNotificationSystem(
            AlertManager(
                str(config_dir),
                settings.to_alert_settings(),
                runtime_state_manager=RuntimeStateManager(config_dir),
            ),
            self._notifier,
            settings,
            on_alerts_popup=self._queue_immediate_alert_popup,
            radio_auto_tuner=Radio(),
        )
        self.main_window = None

    run_async = staticmethod(asyncio.run)

    def update_tray_tooltip(self, weather_data, location_name):
        pass

    def refresh_global_hotkeys(self):
        pass

    def _setup_accelerators(self):
        pass

    def _start_auto_update_checks(self):
        pass

    def _start_background_updates(self):
        pass


class FakeWindow:
    _on_weather_data_received = MainWindowRefreshMixin._on_weather_data_received
    _on_weather_error = MainWindowDisplayMixin._on_weather_error

    def __init__(self, app: FakeApp):
        self.app = app
        app.main_window = self
        self._all_locations_active = False
        self._alert_lifecycle_labels: dict = {}
        self._suppress_startup_text_product_notifications = True
        self._notification_event_manager = None
        self._forecast_product_service = nf._ProductService()
        self.current_conditions = _Widget()
        self.stale_warning_label = _Widget()
        self.refresh_button = _Widget()
        self.event_center: list[dict] = []

    def append_event_center_entry(self, text, *, category=None):
        if text:
            self.event_center.append({"category": category, "text": text})

    def _process_notification_events(self, weather_data):
        mwne.process_notification_events(self, weather_data)

    def _get_notification_event_manager(self):
        return mwne.get_notification_event_manager(self)

    def _update_precipitation_timeline_menu_state(self, weather_data):
        pass

    def _set_forecast_sections(self, daily, hourly):
        pass

    def _update_alerts(self, alerts, lifecycle_labels=None):
        pass

    def _set_last_updated_status(self):
        pass

    def set_status(self, message):
        pass


def fill_product_cache(window: FakeWindow, step: dict) -> None:
    """The text products `_pre_warm_products_for_location` left in the cache."""
    service = window._forecast_product_service
    cache = service._cache
    cache.entries = {}
    cwa = (step.get("location") or {}).get("cwa_office")
    if "hwo" in step:
        cache.entries[f"nws_text_product:HWO:{cwa}"] = (
            nf.mk_product(step["hwo"]) if step["hwo"] else None
        )
    if "sps" in step:
        cache.entries[f"nws_text_product:SPS:{cwa}"] = [nf.mk_product(p) for p in step["sps"]]
    service.stations = step.get("cli_stations", [])
    for station, product in step.get("cli_cache", {}).items():
        cache.entries[f"iem_text_product:CLI:{station}:latest"] = (
            nf.mk_product(product) if product else None
        )


def run_sequence(name: str, settings: dict, location: dict, steps: list[dict]) -> dict:
    config_dir = Path(tempfile.mkdtemp(prefix="aw-golden-notifywire-"))
    try:
        nf.set_now(steps[0]["now"])
        current = nf.mk_settings(settings)
        app = FakeApp(config_dir, current, nf.mk_location(location))
        window = FakeWindow(app)
        results = []
        for step in steps:
            local = nf.set_now(step["now"])
            kind = step["kind"]
            if kind == "restart":
                app = FakeApp(config_dir, current, nf.mk_location(location))
                window = FakeWindow(app)
            elif kind == "settings":
                current = nf.mk_settings(step["settings"])
                app.config_manager.settings = current
                app.refresh_runtime_settings()
            elif kind == "displayed":
                app.config_manager.location = (
                    nf.mk_location(step["location"]) if step.get("location") else None
                )
                fill_product_cache(window, step)
                window._on_weather_data_received(
                    nf.mk_weather(step["weather"]),
                    play_refresh_sound=step["play_refresh_sound"],
                )
            elif kind == "poll":
                mwne.on_notification_event_data_received(window, nf.mk_weather(step["weather"]))
            elif kind == "error":
                window._on_weather_error("Request timed out")
            elif kind == "climate_dialog":
                dialog = SimpleNamespace(
                    _app=app,
                    _location=nf.mk_location(location),
                    GetParent=lambda window=window: window,
                )
                ForecastProductsDialog._check_daily_climate_notification(
                    dialog, nf.mk_product(step["product"])
                )
            while DEFERRED:
                fn, args, kwargs = DEFERRED.pop(0)
                fn(*args, **kwargs)
            results.append(
                {
                    "local_now": local,
                    "toasts": app._notifier.toasts[:],
                    "sounds": SOUNDS[:],
                    "popups": POPUPS[:],
                    "radio": RADIO[:],
                    "event_center": window.event_center[:],
                }
            )
            for recorded in (app._notifier.toasts, SOUNDS, POPUPS, RADIO, window.event_center):
                recorded.clear()
        return {
            "name": name,
            "settings": settings,
            "location": location,
            "steps": steps,
            "results": results,
        }
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

DRY = [(0.0, 0.0, None)] * 30
RAIN_IN_5 = [(0.0, 0.1, None)] * 5 + [(0.8, 0.9, "rain")] * 25
RAIN_STOPS = [(0.6, 0.9, "rain")] * 3 + [(0.0, 0.05, None)] * 27

SPS_LOCAL = nf.sps(
    "SPS-LOCAL",
    "\nNJZ017-018-252000-\nBurlington NJ-\n...Fire weather concerns this afternoon...\n",
    "Elevated fire weather concerns this afternoon",
)
SPS_OTHER = nf.sps(
    "SPS-OTHER",
    "\nPAZ070>071-252000-\nBucks PA-\n...Strong thunderstorm near Doylestown...\n",
    "Strong thunderstorm near Doylestown",
)
HWO_1 = nf.hwo(
    "HAZARDOUS WEATHER OUTLOOK\n.DAY ONE...\nNo hazardous weather is expected.\n$$",
    "2026-09-25T09:00:00+00:00",
)
HWO_2 = nf.hwo(
    "HAZARDOUS WEATHER OUTLOOK\n.DAY ONE...\nNo hazardous weather is expected.\n"
    "Thunderstorms with damaging winds are possible this evening.\n$$",
    "2026-09-25T19:00:00+00:00",
)
CLI_1 = nf.cli(
    "CLIMATE REPORT\nTEMPERATURE (F)\n  MAXIMUM   71\n  MINIMUM   55\n"
    "PRECIPITATION (IN)\n  TODAY 0.00\n",
    "2026-09-25T10:00:00+00:00",
    "ILG",
)
CLI_2 = nf.cli(
    "CLIMATE REPORT\nTEMPERATURE (F)\n  MAXIMUM   74\n  MINIMUM   55\n"
    "PRECIPITATION (IN)\n  TODAY 0.12\n",
    "2026-09-25T20:00:00+00:00",
    "ILG",
)
CLI_3 = nf.cli(
    "CLIMATE REPORT\nTEMPERATURE (F)\n  MAXIMUM   76\n  MINIMUM   57\n"
    "PRECIPITATION (IN)\n  TODAY 0.40\n",
    "2026-09-25T21:30:00+00:00",
    "ILG",
)

FLOOD = nf.alert(
    "flood-1", "Flood Watch", "Moderate", message_type="Alert", urgency="Expected", sent=at(-2)
)
FLOOD_UPDATED = dict(FLOOD, description="Flood Watch description, now through Saturday.")
FLOOD_ESCALATED = dict(FLOOD_UPDATED, severity="Severe", headline="Flood Watch upgraded")
TORNADO = nf.alert(
    "tornado-1", "Tornado Warning", "Extreme", message_type="Alert", areas=["A", "B", "C", "D"]
)
STORM = nf.alert("storm-1", "Severe Thunderstorm Warning", "Severe", message_type="Update")
STORM_EXTENDED = dict(STORM, expires="2026-10-31T18:00:00-04:00")
WIND = nf.alert("wind-1", "Wind Advisory", "Moderate", message_type="Alert")
RED_FLAG = nf.alert("fire-1", "Red Flag Warning", "Severe", message_type="Alert")


def alerts(*items: dict) -> dict:
    return {"alerts": list(items)}


def change(kind: str, alert: dict | None, title: str, alert_id: str) -> dict:
    return {"kind": kind, "alert": alert, "alert_id": alert_id, "title": title}


def diff(**changes: list) -> dict:
    return changes


HOME = nf.HOME
SESSION = dict(
    nf.ALL_ON,
    sound_pack=nf.MISSING_PACK,
    immediate_alert_details_popups=True,
    muted_sound_events=[],
)


def session() -> dict:
    """One app session: alerts appear, update, escalate and cancel between refreshes."""
    return run_sequence(
        "session",
        SESSION,
        HOME,
        [
            {  # startup refresh: first alert, event baselines, refresh sound
                "kind": "displayed",
                "now": at(0),
                "location": HOME,
                "play_refresh_sound": True,
                "weather": nf.weather(
                    alerts=alerts(FLOOD),
                    discussion=nf.AFD_1,
                    discussion_issuance_time="2026-09-25T06:45:00+00:00",
                    current={"severe_weather_risk": 25},
                    minutely_precipitation=nf.minutely(at(0), DRY),
                ),
                "hwo": HWO_1,
                "sps": [SPS_OTHER],
                "cli_stations": ["ILG"],
                "cli_cache": {"ILG": CLI_1},
            },
            {  # a new warning inside the global cooldown is dropped
                "kind": "poll",
                "now": at(1),
                "weather": nf.weather(
                    alerts=alerts(FLOOD, TORNADO),
                    alert_lifecycle_diff=diff(
                        new_alerts=[change("new", TORNADO, "Tornado Warning", "tornado-1")]
                    ),
                ),
            },
            {  # after the cooldown the next poll notifies it
                "kind": "poll",
                "now": at(6),
                "weather": nf.weather(alerts=alerts(FLOOD, TORNADO), alert_lifecycle_diff=diff()),
            },
            {  # an update and a new statement: one batch sound, a summary popup,
                # then the lifecycle toast for the same update
                "kind": "poll",
                "now": at(12),
                "weather": nf.weather(
                    alerts=alerts(FLOOD_UPDATED, TORNADO, STORM),
                    alert_lifecycle_diff=diff(
                        new_alerts=[change("new", STORM, "Severe Thunderstorm Warning", "storm-1")],
                        updated_alerts=[change("updated", FLOOD_UPDATED, "Flood Watch", "flood-1")],
                    ),
                ),
            },
            {  # full refresh: escalation plus every event check firing
                "kind": "displayed",
                "now": at(20),
                "location": HOME,
                "play_refresh_sound": True,
                "weather": nf.weather(
                    alerts=alerts(FLOOD_ESCALATED, TORNADO, STORM),
                    discussion=nf.AFD_2,
                    discussion_issuance_time="2026-09-25T17:32:00+00:00",
                    current={"severe_weather_risk": 65},
                    minutely_precipitation=nf.minutely(at(20), RAIN_IN_5),
                ),
                "hwo": HWO_2,
                "sps": [SPS_OTHER, SPS_LOCAL],
                "cli_stations": ["PHL", "ILG"],
                "cli_cache": {"PHL": None, "ILG": CLI_2},
            },
            {  # cancelled and extended
                "kind": "poll",
                "now": at(26),
                "weather": nf.weather(
                    alerts=alerts(FLOOD_ESCALATED, STORM_EXTENDED),
                    alert_lifecycle_diff=diff(
                        cancelled_alerts=[
                            change("cancelled", None, "Tornado Warning", "tornado-1")
                        ],
                        extended_alerts=[
                            change(
                                "extended", STORM_EXTENDED, "Severe Thunderstorm Warning", "storm-1"
                            )
                        ],
                    ),
                ),
            },
            {  # Settings saved: sound off, moderate alerts off, popups off
                "kind": "settings",
                "now": at(32),
                "settings": dict(
                    SESSION,
                    sound_enabled=False,
                    alert_notify_moderate=False,
                    immediate_alert_details_popups=False,
                ),
            },
            {
                "kind": "poll",
                "now": at(40),
                "weather": nf.weather(
                    alerts=alerts(FLOOD_ESCALATED, STORM_EXTENDED, WIND, RED_FLAG),
                    alert_lifecycle_diff=diff(
                        new_alerts=[
                            change("new", WIND, "Wind Advisory", "wind-1"),
                            change("new", RED_FLAG, "Red Flag Warning", "fire-1"),
                        ]
                    ),
                ),
            },
            {  # cached data shown on a location switch: no refresh sound
                "kind": "displayed",
                "now": at(45),
                "location": HOME,
                "play_refresh_sound": False,
                "weather": nf.weather(
                    alerts=alerts(FLOOD_ESCALATED, STORM_EXTENDED, WIND, RED_FLAG),
                    current={"severe_weather_risk": 65},
                    minutely_precipitation=nf.minutely(at(45), RAIN_STOPS),
                ),
            },
            {"kind": "error", "now": at(46)},
            {
                "kind": "settings",
                "now": at(47),
                "settings": dict(SESSION, muted_sound_events=["discussion_update"]),
            },
            {"kind": "error", "now": at(48)},
            {"kind": "climate_dialog", "now": at(50), "product": CLI_3},
            {  # no current location: alerts only
                "kind": "displayed",
                "now": at(55),
                "location": None,
                "play_refresh_sound": True,
                "weather": nf.weather(alerts=alerts()),
            },
        ],
    )


def restart() -> dict:
    """Text-product baselines survive a restart; the first refresh after it stays quiet."""
    settings = dict(nf.ALL_ON, sound_pack=nf.MISSING_PACK)
    first = {
        "kind": "displayed",
        "location": HOME,
        "play_refresh_sound": True,
        "hwo": HWO_1,
        "sps": [SPS_OTHER],
        "cli_stations": ["ILG"],
        "cli_cache": {"ILG": CLI_1},
    }
    return run_sequence(
        "restart",
        settings,
        HOME,
        [
            dict(
                first,
                now=at(0),
                weather=nf.weather(
                    discussion=nf.AFD_1,
                    discussion_issuance_time="2026-09-25T06:45:00+00:00",
                    current={"severe_weather_risk": 25},
                    minutely_precipitation=nf.minutely(at(0), DRY),
                ),
            ),
            {"kind": "restart", "now": at(10)},
            dict(
                first,
                now=at(11),
                weather=nf.weather(
                    discussion=nf.AFD_2,
                    discussion_issuance_time="2026-09-25T17:32:00+00:00",
                    current={"severe_weather_risk": 65},
                    minutely_precipitation=nf.minutely(at(11), RAIN_IN_5),
                ),
                hwo=HWO_2,
                sps=[SPS_LOCAL],
                cli_cache={"ILG": CLI_2},
            ),
            dict(
                first,
                now=at(21),
                weather=nf.weather(
                    discussion=nf.AFD_3,
                    discussion_issuance_time="2026-09-25T21:00:00+00:00",
                    current={"severe_weather_risk": 10},
                ),
                hwo=HWO_2,
                sps=[SPS_LOCAL],
                cli_cache={"ILG": CLI_3},
            ),
        ],
    )


def main() -> int:
    write("notifywire", "sequences", [session(), restart()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
