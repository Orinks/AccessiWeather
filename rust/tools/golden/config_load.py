"""Golden parity data for loading accessiweather.json (config_manager.load_config).

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/config_load.py

Feeds legacy and hand-edited config files through the real
ConfigManager.load_config (keyring access stubbed out) and records what
Python loads: the resulting AppConfig.to_dict() and whether the build-aware
update channel default was applied. Writes
rust/testdata/golden/config_load/cases.json.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from accessiweather.config.config_manager import ConfigManager

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "config_load" / "cases.json"

LOC = {"name": "Home", "latitude": 40.0, "longitude": -75.0}

CASES = [
    (
        "loose_booleans",
        None,
        {
            "settings": {
                "update_channel": "stable",
                "enable_alerts": "no",
                "minimize_to_tray": " Yes ",
                "sound_enabled": 0,
                "startup_enabled": "on",
                "show_dewpoint": "maybe",
                "round_values": 1,
                "time_format_12hour": None,
                "alert_notify_minor": "TRUE",
                "show_timezone_suffix": [1],
            },
            "locations": [LOC],
        },
    ),
    (
        "legacy_specific_alert_sounds",
        None,
        {
            "settings": {
                "update_channel": "stable",
                "sound_pack": " chimes ",
                "specific_alert_sounds_enabled": "true",
            },
            "locations": [],
        },
    ),
    (
        "legacy_specific_alert_sounds_blank_pack",
        None,
        {
            "settings": {
                "update_channel": "stable",
                "sound_pack": "",
                "specific_alert_sounds_enabled": True,
            },
        },
    ),
    (
        "specific_packs_win_over_legacy",
        None,
        {
            "settings": {
                "update_channel": "stable",
                "specific_alert_sounds_enabled": True,
                "specific_alert_sound_packs": [" a ", "a", "", 3],
            },
        },
    ),
    (
        "floats_and_validation",
        None,
        {
            "settings": {
                "update_channel": "stable",
                "precipitation_likelihood_threshold": " 0.7 ",
                "parallel_fetch_timeout": "90",
                "auto_mode_api_budget": "bogus",
                "alert_display_style": "combined",
                "location_sort_order": "nowhere",
                "date_format": "xx",
                "data_source": "visualcrossing",
                "source_priority_us": ["nws", "visualcrossing", 5],
                "auto_sources_international": ["foo"],
                "auto_tune_weather_radio_duration_minutes": 0,
                "noaa_radio_hotkey": None,
            },
        },
    ),
    (
        "float_from_int_and_kept_values",
        None,
        {
            "settings": {
                "update_channel": "beta",
                "parallel_fetch_timeout": 5,
                "precipitation_likelihood_threshold": "not a number",
                "auto_tune_weather_radio_duration_minutes": 30,
                "shortcut_show_main_window": "Ctrl+Shift+W",
                "shortcut_hide_main_window": "ctrl+alt+shift+h",
                "github_backend_url": "https://example.test/api",
            },
        },
    ),
    ("missing_channel_stable_build", None, {"settings": {"temperature_unit": "f"}}),
    (
        "missing_channel_nightly_build",
        "nightly-20260901",
        {"settings": {"temperature_unit": "c"}},
    ),
    ("no_settings_object_nightly_build", "nightly-20260901", {"locations": [LOC]}),
    (
        "marine_mode_truthiness",
        None,
        {
            "settings": {"update_channel": "stable"},
            "locations": [
                {**LOC, "marine_mode": 1},
                {**LOC, "name": "Coast", "marine_mode": "false"},
                {**LOC, "name": "Inland", "marine_mode": 0},
            ],
            "current_location": {**LOC, "name": "Coast", "marine_mode": "false"},
        },
    ),
]


def load(build_tag: str | None, data: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "accessiweather.json").write_text(json.dumps(data), encoding="utf-8")
        app = SimpleNamespace(build_tag=build_tag, _portable_mode=False)
        manager = ConfigManager(app, config_dir=tmp)
        manager._load_secure_keys = lambda: None  # never touch the real keyring
        saved = []
        original_save = manager.save_config
        manager.save_config = lambda: saved.append(True) or original_save()
        config = manager.load_config()
        return {"config": config.to_dict(), "saved": bool(saved)}


def main() -> None:
    cases = []
    for name, build_tag, data in CASES:
        result = load(build_tag, data)
        cases.append(
            {
                "name": name,
                "build_tag": build_tag,
                "input": json.dumps(data),
                "config": result["config"],
                "saved": result["saved"],
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {OUT}")


if __name__ == "__main__":
    main()
