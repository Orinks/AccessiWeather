"""
Golden outputs for the aw-services crate (update checks, launch at login,
activation, import/export, portable copy, Report Issue, onboarding).

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/services.py
Writes rust/testdata/golden/services/*.json.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import tempfile
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import wx

RUST = Path(__file__).resolve().parents[2]
OUT = RUST / "testdata" / "golden" / "services"
RELEASES = json.loads((RUST / "testdata" / "services" / "github_releases.json").read_text("utf-8"))


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print("wrote", OUT / name)


# --------------------------------------------------------------------------
# Updates
# --------------------------------------------------------------------------


def updates() -> None:
    from accessiweather.services import simple_update as su
    from accessiweather.services import update_restart
    from accessiweather.services.update_integrity import find_checksum_asset, parse_checksum_file
    from accessiweather.ui.dialogs.update_dialog import format_release_notes_for_dialog

    tags = [
        "v0.10.1", "v0.10.0", "0.9.0", "v1.0.0rc1", "v1.0.0", "v1.0", "vv2.0", "V1.2",
        "v1.0.0-beta.2", "v1.0.post1", "v1.0.dev3", "v2!0.1", "v1.0+local.7", "junk",
        "v0.11.0-rust.1", "nightly-20260925", "Nightly-20260101", "build-nightly-20251231-x",
        "nightly-2026", "",
    ]
    currents = ["0.10.1", "0.10.0", "v0.9.0", "1.0.0", "1.0.0rc1", "1.0", "0.11.0", "abc", ""]
    nightlies = [None, "20260924", "20260925"]
    versions = []
    for tag in tags:
        release = {"tag_name": tag}
        for current in currents:
            for nightly in nightlies:
                versions.append(
                    {
                        "tag": tag,
                        "current_version": current,
                        "current_nightly_date": nightly,
                        "available": su.is_update_available(release, current, nightly),
                    }
                )
    tag_info = {}
    for tag in tags:
        identifier, kind = su.get_release_identifier({"tag_name": tag})
        tag_info[tag] = {
            "nightly_date": su.parse_nightly_date(tag),
            "is_nightly": su.is_nightly_release({"tag_name": tag}),
            "identifier": identifier,
            "type": kind,
        }

    notes = [r.get("body") or "" for r in RELEASES] + [
        "Changelog\n\nCommit: ABCDEF1234567890",
        "commit hash = deadbeefcafe",
        "Built from 1a2b3c4d on main",
        "Nothing here",
        "facade1 and 0123456789abcdef0123456789abcdef01234567",
        "COMMIT:1234567",
        "commit: 123456",
    ]
    commit_hashes = [{"notes": n, "hash": su.parse_commit_hash(n)} for n in notes]

    selection = []
    for channel in ["stable", "nightly", "dev", "STABLE", "Nightly"]:
        for current, nightly in [
            ("0.10.1", None),
            ("0.10.0", None),
            ("0.9.0", None),
            ("0.10.1", "20260922"),
            ("0.10.1", "20260925"),
            ("0.11.0", None),
        ]:
            latest = su.select_latest_release(RELEASES, channel)
            update = None
            if latest and su.is_update_available(latest, current, nightly):
                identifier, kind = su.get_release_identifier(latest)
                update = {
                    "version": identifier,
                    "is_nightly": kind == "nightly",
                    "is_prerelease": bool(latest.get("prerelease")),
                    "commit_hash": su.parse_commit_hash(latest.get("body") or ""),
                    "release_notes": latest.get("body") or "",
                }
            selection.append(
                {
                    "channel": channel,
                    "current_version": current,
                    "current_nightly_date": nightly,
                    "selected_tag": latest["tag_name"] if latest else None,
                    "update": update,
                }
            )
    synthetic = [
        {"tag_name": "v1.0.0", "prerelease": False, "published_at": "2025-01-01T00:00:00Z"},
        {"tag_name": "v1.1.0", "prerelease": True, "published_at": "2025-02-01T00:00:00Z"},
        {"tag_name": "nightly-20250202", "published_at": "2025-02-02T00:00:00Z"},
        {"tag_name": "v0.9.0", "published_at": None, "created_at": "2025-03-01T00:00:00Z"},
        {"tag_name": "v0.8.0", "published_at": "2025-03-01T00:00:00Z"},
        {"tag_name": "nightly-20250101", "prerelease": 0, "published_at": "2025-02-02T00:00:00Z"},
    ]
    synthetic_selection = {
        channel: (su.select_latest_release(synthetic, channel) or {}).get("tag_name")
        for channel in ["stable", "nightly", "dev", "beta"]
    }

    note_inputs = [r.get("body") or "" for r in RELEASES] + [
        "## Added\n- **National Products** now use `IEM AFOS` text.\n"
        "- See [CHANGELOG.md](https://example.com/changelog) for details.\n\n"
        "## Fixed\n- Pirate Weather handles _freezing rain_ correctly.\n",
        "",
        "   \n\t\n",
        "### Changed\n1. First numbered item.\n* Second starred item.\n+ Plus item\n",
        "\n\n\nText\r\n\r\n\r\nMore   spaced\ttext\rOld mac line\n",
        "####### Seven hashes\n#NoSpace\n__bold__ and *em* and snake_case_name and 2*3*4",
        "- [link](url) [not a link] `code` ``double``",
    ]
    release_notes = [{"raw": n, "formatted": format_release_notes_for_dialog(n)} for n in note_inputs]

    h256 = "a" * 64
    h512 = "B" * 128
    md5 = "c" * 32
    parse_cases = [
        (h256, "any.zip"),
        (f"{h256}\n", "any.zip"),
        (f"{h256}  accessiweather-windows-x86_64.zip\n", "accessiweather-windows-x86_64.zip"),
        (f"{h256} *ACCESSIWEATHER-WINDOWS-X86_64.ZIP", "accessiweather-windows-x86_64.zip"),
        (f"{h256}  other.zip\n{h512}  app.zip\n", "app.zip"),
        (f"{h256}  other.zip\n", "app.zip"),
        (f"{md5}  app.zip", "app.zip"),
        (f"xyz  app.zip\n{h256}\tapp.zip", "app.zip"),
        (f"{h256}\n{h512}", "app.zip"),
        ("", "app.zip"),
        (f"\n\n  {h256}   app name.zip  \n", "app name.zip"),
    ]
    checksum_parse = []
    for content, artifact in parse_cases:
        parsed = parse_checksum_file(content, artifact)
        checksum_parse.append(
            {"content": content, "artifact": artifact, "result": list(parsed) if parsed else None}
        )
    find_cases = [
        (["app.zip", "app.zip.sha256", "checksums.txt"], "app.zip"),
        (["app.zip", "checksums.txt", "APP.ZIP.SHA512"], "App.zip"),
        (["app.zip", "SHA256SUMS"], "app.zip"),
        (["app.zip", "other.zip.sha256"], "app.zip"),
        (["app.zip", "checksums.sha512", "checksums.sha256"], "app.zip"),
    ]
    checksum_find = []
    for names, artifact in find_cases:
        found = find_checksum_asset({"assets": [{"name": n} for n in names]}, artifact)
        checksum_find.append({"assets": names, "artifact": artifact, "found": found["name"] if found else None})
    for release in RELEASES:
        for asset in release["assets"]:
            found = find_checksum_asset(release, asset["name"])
            checksum_find.append(
                {
                    "assets": [a["name"] for a in release["assets"]],
                    "artifact": asset["name"],
                    "found": found["name"] if found else None,
                }
            )

    update_restart.os.getpid = lambda: 4242
    portable_script = {
        "zip_path": r"C:\Users\Test User\AppData\Local\Temp\accessiweather-windows-x86_64.zip",
        "target_dir": r"D:\Apps\AccessiWeather",
        "exe_path": r"D:\Apps\AccessiWeather\AccessiWeather.exe",
        "pid": 4242,
    }
    portable_script["text"] = update_restart.build_portable_update_script(
        Path(portable_script["zip_path"]),
        Path(portable_script["target_dir"]),
        Path(portable_script["exe_path"]),
    )
    macos_scripts = []
    for update_path, app_path in [
        ("/tmp/accessiweather-macos-arm64.zip", "/Applications/AccessiWeather.app"),
        ("/Users/me/Down loads/it's.dmg", "/Users/me/My Apps/AccessiWeather.app"),
    ]:
        macos_scripts.append(
            {
                "update_path": update_path,
                "app_path": app_path,
                "text": update_restart.build_macos_update_script(
                    PurePosixPath(update_path), PurePosixPath(app_path)
                ),
            }
        )

    write(
        "updates.json",
        {
            "versions": versions,
            "tags": tag_info,
            "commit_hashes": commit_hashes,
            "selection": selection,
            "synthetic_releases": synthetic,
            "synthetic_selection": synthetic_selection,
            "release_notes": release_notes,
            "checksum_parse": checksum_parse,
            "checksum_find": checksum_find,
            "portable_script": portable_script,
            "macos_scripts": macos_scripts,
        },
    )


# --------------------------------------------------------------------------
# Launch at login
# --------------------------------------------------------------------------


def startup() -> None:
    import subprocess

    from accessiweather.services import startup_utils
    from accessiweather.services.startup_utils import StartupManager

    cmdlines = [
        [r"C:\Program Files\AccessiWeather\AccessiWeather.exe", "--startup"],
        [r"C:\Apps\AccessiWeather.exe", "--startup"],
        [r"C:\a b\c\\", 'say "hi"', "", "tab\there", r"back\\slash"],
    ]
    list2cmdline = [{"args": a, "command": subprocess.list2cmdline(a)} for a in cmdlines]

    def manager_for(exe: str, platform_name: str) -> StartupManager:
        detector = SimpleNamespace(
            get_platform_info=lambda: SimpleNamespace(
                platform=platform_name, app_directory=PurePosixPath(exe).parent
            )
        )
        manager = StartupManager(platform_detector=detector)
        manager._get_launch_command = lambda *, for_startup=False: (
            PurePosixPath(exe),
            ["--startup"] if for_startup else [],
        )
        manager._get_app_executable = lambda: PurePosixPath(exe)
        return manager

    desktop = []
    for exe in ["/opt/accessiweather/accessiweather", '/home/me/My "Apps"/aw/accessiweather']:
        desktop.append({"executable": exe, "text": manager_for(exe, "linux")._build_desktop_entry()})

    plists = []
    startup_utils.is_compiled_runtime = lambda: True
    startup_utils.subprocess.run = lambda *a, **k: None
    with tempfile.TemporaryDirectory() as tmp:
        for exe in [
            "/Applications/AccessiWeather.app/Contents/MacOS/AccessiWeather",
            "/Users/me/A & B <x>.app/Contents/MacOS/AccessiWeather",
        ]:
            manager = manager_for(exe, "macos")
            plist = Path(tmp) / "agent.plist"
            manager._get_macos_plist_path = lambda plist=plist: plist
            assert manager._enable_macos_startup()
            plists.append({"executable": exe, "text": plist.read_text("utf-8")})

    run_commands = []
    for exe in [r"C:\Program Files\AccessiWeather\AccessiWeather.exe", r"C:\Tools\aw.exe"]:
        manager = StartupManager(platform_detector=SimpleNamespace())
        manager._get_launch_command = lambda *, for_startup=False, exe=exe: (
            Path(exe),
            ["--startup"] if for_startup else [],
        )
        run_commands.append({"executable": exe, "command": manager._get_windows_run_command()})

    write(
        "startup.json",
        {
            "list2cmdline": list2cmdline,
            "desktop_entries": desktop,
            "plists": plists,
            "windows_run_commands": run_commands,
        },
    )


# --------------------------------------------------------------------------
# Activation
# --------------------------------------------------------------------------


def activation() -> None:
    from accessiweather.notification_activation import (
        NotificationActivationRequest,
        extract_activation_request_from_argv,
        serialize_activation_request,
        write_activation_request_handoff,
    )
    from accessiweather.paths import RuntimeStoragePaths
    from accessiweather.single_instance import SingleInstanceManager

    requests = [
        ("discussion", None),
        ("generic_fallback", None),
        ("alert_details", "urn:oid:2.49.0.1.840.0.abc.001.1"),
        ("alert_details", "id with spaces & ampersands/é"),
        ("discussion", "extra"),
    ]
    tokens = []
    with tempfile.TemporaryDirectory() as tmp:
        paths = RuntimeStoragePaths(config_root=Path(tmp))
        for kind, alert_id in requests:
            request = NotificationActivationRequest(kind=kind, alert_id=alert_id)
            write_activation_request_handoff(paths, request)
            tokens.append(
                {
                    "kind": kind,
                    "alert_id": alert_id,
                    "token": serialize_activation_request(request),
                    "handoff": paths.activation_request_file.read_text("utf-8"),
                }
            )
    argvs = [
        ["app.exe"],
        ["app.exe", "--debug", "accessiweather-toast:kind=discussion"],
        ["accessiweather-toast:kind=alert_details&alert_id=a%2Fb+c"],
        ["accessiweather-toast:kind=alert_details"],
        ["accessiweather-toast:kind=alert_details&alert_id="],
        ["accessiweather-toast:kind=bogus", "accessiweather-toast:kind=discussion"],
        ["accessiweather-toast:alert_id=x&kind=generic_fallback&kind=discussion"],
        ["accessiweather-toast:kind", "x"],
        ["accessiweather-toast:"],
    ]
    extracted = []
    for argv in argvs:
        request = extract_activation_request_from_argv(argv)
        extracted.append(
            {
                "argv": argv,
                "request": None if request is None else {"kind": request.kind, "alert_id": request.alert_id},
            }
        )
    titles = [
        "AccessiWeather",
        "AccessiWeather — Philadelphia, PA",
        "AccessiWeather - GitHub",
        "Orinks/AccessiWeather — Mozilla Firefox",
        "AccessiWeather —",
        "",
    ]
    window_titles = [
        {"title": t, "match": SingleInstanceManager._is_accessiweather_window_title(t)} for t in titles
    ]
    write("activation.json", {"tokens": tokens, "argv": extracted, "window_titles": window_titles})


# --------------------------------------------------------------------------
# Import / export and the portable copy
# --------------------------------------------------------------------------


def import_export() -> None:
    from accessiweather.config.import_export import ImportExportOperations
    from accessiweather.models import AppConfig, AppSettings, Location

    logger = logging.getLogger("golden")

    def operations(config):
        manager = SimpleNamespace(
            get_config=lambda: config,
            save_config=lambda: True,
            _get_logger=lambda: logger,
            _config=config,
            app=None,
        )
        return ImportExportOperations(manager)

    settings = AppSettings(
        temperature_unit="c",
        data_source="nws",
        update_interval_minutes=15,
        custom_instructions="Be brief",
        muted_sound_events=["startup"],
        source_priority_us=["openmeteo", "nws", "pirateweather"],
    )
    config = AppConfig(
        settings=settings,
        locations=[
            Location(name="Home", latitude=40.0, longitude=-75.25, country_code="us"),
            Location(name="Paris", latitude=48.8566, longitude=2.3522),
        ],
        current_location=None,
    )
    config_json = config.to_dict()
    with tempfile.TemporaryDirectory() as tmp:
        ops = operations(config)
        ops.export_settings(Path(tmp) / "settings.json")
        settings_doc = json.loads((Path(tmp) / "settings.json").read_text("utf-8"))
        ops.export_locations(Path(tmp) / "locations.json")
        locations_doc = json.loads((Path(tmp) / "locations.json").read_text("utf-8"))
    settings_doc.pop("exported_at")
    locations_doc.pop("exported_at")

    def location_state(cfg):
        return [
            {"name": l.name, "latitude": l.latitude, "longitude": l.longitude, "country_code": l.country_code}
            for l in cfg.locations
        ]

    def fresh():
        return AppConfig(
            settings=AppSettings(),
            locations=[Location(name="Existing Location", latitude=30.0, longitude=-90.0)],
            current_location=None,
        )

    location_cases = [
        {"locations": [{"name": "Paris", "latitude": 48.8566, "longitude": 2.3522}]},
        {"locations": [
            {"name": "Existing Location", "latitude": 1, "longitude": 2},
            {"name": "New", "latitude": "40.5", "longitude": " -80 ", "country_code": "ca"},
        ]},
        {"other_data": "value"},
        {"locations": ["invalid_string_entry", {"name": "Valid", "latitude": 40.0, "longitude": -80.0}]},
        {"locations": [{"name": "Missing Coords"}, {"latitude": 40.0, "longitude": -80.0}]},
        {"locations": [{"name": "Bad", "latitude": "not_a_number", "longitude": -80.0}]},
        {"locations": []},
        {"locations": [{"name": "", "latitude": 1, "longitude": 1}, {"name": "Zero", "latitude": 0, "longitude": 0}]},
        [1, 2],
    ]
    settings_cases = [
        {"settings": {"temperature_unit": "f", "data_source": "visualcrossing"},
         "locations": [{"name": "Existing Location", "latitude": 1, "longitude": 1},
                       {"name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503, "country_code": "jp"}]},
        {"settings": {"data_source": "pirateweather", "update_interval_minutes": 30}},
        {"settings": {"data_source": "auto"}, "locations": ["junk"]},
        {"other": 1},
        {"settings": "nope"},
        [1],
    ]

    def run_cases(cases, method):
        results = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, case in enumerate(cases):
                cfg = fresh()
                path = Path(tmp) / f"case{i}.json"
                path.write_text(json.dumps(case), encoding="utf-8")
                ok = getattr(operations(cfg), method)(path)
                results.append(
                    {
                        "input": case,
                        "result": ok,
                        "locations": location_state(cfg),
                        "settings": {
                            k: cfg.settings.to_dict()[k]
                            for k in ("temperature_unit", "data_source", "update_interval_minutes")
                        },
                    }
                )
            cfg = fresh()
            results.append(
                {"input": "<invalid json>", "result": _import_raw(operations(cfg), method, tmp), "locations": location_state(cfg)}
            )
        return results

    write(
        "import_export.json",
        {
            "config": config_json,
            "settings_export": settings_doc,
            "locations_export": locations_doc,
            "import_locations": run_cases(location_cases, "import_locations"),
            "import_settings": run_cases(settings_cases, "import_settings"),
        },
    )


def _import_raw(ops, method, tmp):
    path = Path(tmp) / "raw.json"
    path.write_text("invalid json content", encoding="utf-8")
    return getattr(ops, method)(path)


def portable_copy() -> None:
    from accessiweather.ui.dialogs.settings_dialog_portable import SettingsDialogPortableMixin

    mixin = SettingsDialogPortableMixin()
    cases = []
    full = {
        "settings": {"data_source": "nws", "ai_model_preference": "auto", "temperature_unit": "f",
                     "custom_system_prompt": None},
        "locations": [{"name": "Home", "latitude": 1, "longitude": 2}],
    }
    installed_variants = {
        "missing_dir": None,
        "empty_dir": {},
        "no_config": {"other.txt": "x"},
        "empty_file": {"accessiweather.json": ""},
        "invalid_json": {"accessiweather.json": "{nope"},
        "not_object": {"accessiweather.json": "[1]"},
        "no_locations": {"accessiweather.json": json.dumps({"settings": {}, "locations": []})},
        "ok": {"accessiweather.json": json.dumps(full)},
    }
    portable_variants = {
        "same": full,
        "changed": {"settings": {"data_source": "auto", "temperature_unit": "f", "prompt": "  "},
                    "locations": []},
        "quote": {"settings": {"data_source": "it's", "ai_model_preference": 3,
                               "temperature_unit": True, "custom_instructions": ""},
                  "locations": [1, 2]},
        "bare": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, files in installed_variants.items():
            d = Path(tmp) / "installed" / name
            if files is not None:
                d.mkdir(parents=True)
                for fname, content in files.items():
                    (d / fname).write_text(content, encoding="utf-8")
            ok, reason = mixin._has_meaningful_installed_config_data(d)
            cases.append({"installed": name, "files": files, "ok": ok, "reason": reason})
        installed_ok = Path(tmp) / "installed" / "ok"
        validations = []
        for name, data in portable_variants.items():
            d = Path(tmp) / "portable" / name
            d.mkdir(parents=True)
            (d / "accessiweather.json").write_text(json.dumps(data), encoding="utf-8")
            valid, messages = mixin._validate_portable_copy(installed_ok, d)
            validations.append(
                {
                    "portable": data,
                    "valid": valid,
                    "messages": messages,
                    "summary": mixin._build_portable_copy_summary(d),
                }
            )
    write("portable_copy.json", {"installed": full, "precheck": cases, "validation": validations})


# --------------------------------------------------------------------------
# Report Issue
# --------------------------------------------------------------------------


def report_issue() -> None:
    from accessiweather.ui.dialogs import report_issue_dialog as rid

    rid.__version__ = "0.10.1"
    real_system, real_release, real_version = platform.system, platform.release, sys.version
    platform.system = lambda: "Windows"
    platform.release = lambda: "11"
    sys.version = "3.12.4 (tags/v3.12.4:8e8a4ba, Jun  6 2024) [MSC v.1940 64 bit (AMD64)]"
    info = rid.ReportIssueDialog._get_system_info(None)
    platform.system, platform.release, sys.version = real_system, real_release, real_version

    class Text:
        def __init__(self, value):
            self.value = value

        def GetValue(self):
            return self.value

        def SetFocus(self):
            pass

    urls = []
    opened = []
    boxes = []
    rid.webbrowser.open = lambda url: opened.append(url)
    real_box = wx.MessageBox
    wx.MessageBox = lambda message, caption, style=0: boxes.append([caption, message])
    for issue_type, title, description in [
        (0, "Test & Title", "Description with <special> chars"),
        (1, "  Feature: dark mode?  ", ""),
        (0, "Crash", "Line 1\nLine 2 — ünïcode ~ * ' \" + % #"),
        (0, "   ", "no title"),
    ]:
        fake = SimpleNamespace(
            title_input=Text(title),
            desc_input=Text(description),
            info_text=Text(info),
            type_choice=SimpleNamespace(GetSelection=lambda t=issue_type: t),
            EndModal=lambda code: None,
        )
        opened.clear()
        boxes.clear()
        rid.ReportIssueDialog._on_submit(fake, None)
        urls.append(
            {
                "issue_type": issue_type,
                "title": title,
                "description": description,
                "url": opened[0] if opened else None,
                "message_box": boxes[0] if boxes else None,
            }
        )
    wx.MessageBox = real_box
    write(
        "report_issue.json",
        {
            "system_info": {
                "app_version": "0.10.1",
                "os_system": "Windows",
                "os_release": "11",
                "python": "3.12.4",
                "text": info,
            },
            "issue_url": rid.ISSUE_URL,
            "urls": urls,
        },
    )


# --------------------------------------------------------------------------
# Onboarding
# --------------------------------------------------------------------------

SCENARIOS = [
    {"name": "escape_on_welcome", "portable": False, "script": ["cancel"]},
    {"name": "add_location_skip_keys", "portable": False, "script": ["yes", "no", "no"]},
    {
        "name": "no_keyring_enter_openrouter_and_test",
        "portable": False,
        "keyring_available": False,
        "script": [
            "yes", "yes", "no", "yes", {"text": "  sk-or-1  "}, "yes",
            "yes", "yes", {"text": "   "},
        ],
    },
    {
        "name": "import_settings_with_location_finishes",
        "portable": False,
        "results": {"import_settings": True},
        "settings_adds_location": True,
        "script": ["no", "yes", {"file": "C:/backup.json"}, "no"],
    },
    {
        "name": "import_settings_without_location_continues",
        "portable": False,
        "results": {"import_settings": True},
        "script": ["no", "yes", {"file": "C:/backup.json"}, "no", "no", "no"],
    },
    {
        "name": "failed_key_import_then_configure_myself",
        "portable": False,
        "results": {"import_api_keys": False},
        "script": ["no", "no", "yes", {"file": "C:/k.keys"}, {"text": "pw"}, "cancel"],
    },
    {
        "name": "failed_settings_import",
        "portable": False,
        "results": {"import_settings": False},
        "script": ["no", "yes", {"file": "C:/bad.json"}, "cancel"],
    },
    {
        "name": "blank_bundle_passphrase_continues",
        "portable": False,
        "script": ["no", "no", "yes", {"file": "C:/k.keys"}, {"text": "  "}, "no", "no"],
    },
    {
        "name": "portable_keys_bundle_written",
        "portable": True,
        "results": {"export": True},
        "script": ["yes", "yes", "yes", {"text": "sk-or"}, "yes", "yes", {"text": "pw-key"}, {"text": " secret "}],
    },
    {
        "name": "portable_bundle_write_fails",
        "portable": True,
        "results": {"export": False},
        "script": ["yes", "yes", "yes", {"text": "sk-or"}, "no", {"text": "secret"}],
    },
    {
        "name": "portable_blank_passphrase",
        "portable": True,
        "script": ["yes", "no", "yes", "yes", {"text": "pw-key"}, {"text": ""}],
    },
    {
        "name": "portable_cancel_passphrase",
        "portable": True,
        "script": ["yes", "no", "yes", "yes", {"text": "pw-key"}, "cancel"],
    },
    {
        "name": "keys_already_saved",
        "portable": False,
        "keyring": {"openrouter_api_key": "a", "pirate_weather_api_key": "b"},
        "script": ["yes"],
    },
    {
        "name": "portable_key_import_success",
        "portable": True,
        "results": {"import_api_keys": True},
        "bundle_keys": {"openrouter_api_key": "or-key"},
        "script": ["no", "no", "yes", {"file": "D:/keys.awkeys"}, {"text": " pw "}, "no"],
    },
    {
        "name": "installed_key_import_success_with_location",
        "portable": False,
        "results": {"import_api_keys": True, "import_settings": True},
        "settings_adds_location": True,
        "bundle_keys": {"pirate_weather_api_key": "pw"},
        "script": ["no", "yes", {"file": "C:/s.json"}, "yes", {"file": "C:/k.keys"}, {"text": "pass"}],
    },
    {"name": "import_settings_then_configure_myself", "portable": False, "script": ["no", "cancel"]},
    {"name": "settings_file_cancelled", "portable": False, "script": ["no", "yes", "cancel"]},
    {"name": "keys_file_cancelled", "portable": False, "script": ["no", "no", "yes", "cancel"]},
    {"name": "key_choice_configure_myself", "portable": False, "script": ["yes", "yes", "cancel"]},
    {"name": "key_entry_cancelled", "portable": False, "script": ["yes", "yes", "yes", "cancel"]},
    {"name": "skip_openrouter_setup_cancel_pirate", "portable": False, "script": ["yes", "no", "cancel"]},
]


def onboarding() -> None:
    import accessiweather.app as app_module
    import accessiweather.config.secure_storage as secure_storage
    from accessiweather.app import AccessiWeatherApp

    icons = [(wx.ICON_ERROR, "error"), (wx.ICON_WARNING, "warning"), (wx.ICON_INFORMATION, "information")]

    def icon(style):
        return next((name for bit, name in icons if style & bit), None)

    results = []
    for sc in SCENARIOS:
        events: list = []
        script = list(sc["script"])
        keyring = dict(sc.get("keyring", {}))
        portable = sc["portable"]
        outcomes = sc.get("results", {})
        settings = SimpleNamespace(
            onboarding_wizard_shown=False, openrouter_api_key="", pirate_weather_api_key=""
        )
        locations: list = []

        class MessageDialog:
            def __init__(self, parent, message, caption="", style=0):
                self.message, self.caption, self.style, self.labels = message, caption, style, []

            def SetYesNoCancelLabels(self, *labels):
                self.labels = list(labels)

            def SetYesNoLabels(self, *labels):
                self.labels = list(labels)

            def ShowModal(self):
                events.append(["dialog", self.caption, self.message, self.labels, icon(self.style)])
                if not self.style & wx.YES_NO:
                    return wx.ID_OK
                return {"yes": wx.ID_YES, "no": wx.ID_NO, "cancel": wx.ID_CANCEL}[script.pop(0)]

            def Destroy(self):
                pass

        class TextEntryDialog:
            def __init__(self, parent, message, caption="", style=0):
                self.message, self.caption, self.value = message, caption, ""

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def ShowModal(self):
                events.append(["text", self.caption, self.message])
                answer = script.pop(0)
                if answer == "cancel":
                    return wx.ID_CANCEL
                self.value = answer["text"]
                return wx.ID_OK

            def GetValue(self):
                return self.value

        class FileDialog:
            def __init__(self, parent, message, wildcard="", style=0):
                self.message, self.wildcard, self.path = message, wildcard, ""

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def ShowModal(self):
                events.append(["file", self.message, self.wildcard])
                answer = script.pop(0)
                if answer == "cancel":
                    return wx.ID_CANCEL
                self.path = answer["file"]
                return wx.ID_OK

            def GetPath(self):
                return self.path

        wx.MessageDialog = MessageDialog
        wx.TextEntryDialog = TextEntryDialog
        wx.FileDialog = FileDialog
        wx.MessageBox = lambda message, caption="", style=0: events.append(
            ["dialog", caption, message, [], icon(style)]
        )
        app_module.webbrowser.open = lambda url: events.append(["open_url", url])

        def set_password(name, value):
            events.append(["set_password", name, value])
            keyring[name] = value
            return True

        secure_storage.SecureStorage.get_password = staticmethod(lambda name: keyring.get(name))
        secure_storage.SecureStorage.set_password = staticmethod(set_password)
        secure_storage.is_keyring_available = lambda: sc.get("keyring_available", True)

        def update_settings(**kwargs):
            events.append(["update_settings", kwargs])
            for key, value in kwargs.items():
                setattr(settings, key, value)
                if key.endswith("_api_key"):
                    keyring[key] = value
            return True

        def import_settings(path):
            events.append(["import_settings", Path(path).as_posix()])
            ok = outcomes.get("import_settings", True)
            if ok and sc.get("settings_adds_location"):
                locations.append("Imported")
            return ok

        def import_encrypted_api_keys(path, passphrase):
            events.append(["import_api_keys", Path(path).as_posix(), passphrase])
            ok = outcomes.get("import_api_keys", True)
            if ok:
                for key, value in sc.get("bundle_keys", {}).items():
                    if portable:
                        setattr(settings, key, value)
                    else:
                        keyring[key] = value
            return ok

        def export_encrypted_api_keys(path, passphrase):
            events.append(["export", PurePosixPath(path).as_posix(), passphrase])
            return outcomes.get("export", True)

        config_dir = PurePosixPath("<config>")
        app = AccessiWeatherApp.__new__(AccessiWeatherApp)
        app._portable_mode = portable
        app._force_wizard = False
        app.debug_mode = False
        app._portable_keys_imported_this_session = False
        app._startup_update_check_deferred = True
        app._check_for_updates_on_startup = lambda: events.append(["deferred_update_check"])
        app.refresh_runtime_settings = lambda: None
        app.main_window = SimpleNamespace(
            on_add_location=lambda: (events.append(["add_location"]), locations.append("Added")),
            open_settings=lambda tab=None: events.append(["open_settings", tab]),
            _populate_locations=lambda: None,
            refresh_weather_async=lambda **kwargs: None,
        )
        app.config_manager = SimpleNamespace(
            config_dir=config_dir,
            get_config=lambda: SimpleNamespace(settings=settings, locations=locations),
            get_settings=lambda: settings,
            has_locations=lambda: bool(locations),
            update_settings=update_settings,
            import_settings=import_settings,
            import_encrypted_api_keys=import_encrypted_api_keys,
            export_encrypted_api_keys=export_encrypted_api_keys,
            get_portable_api_key_bundle_path=lambda: config_dir / "api-keys.keys",
        )
        app._maybe_show_first_start_onboarding()
        assert not script, f"{sc['name']}: unused script {script}"
        results.append({**sc, "events": events})

    decisions = []
    for force in (False, True):
        for shown in (False, True):
            for has_locations in (False, True):
                app = AccessiWeatherApp.__new__(AccessiWeatherApp)
                app._force_wizard = force
                app.debug_mode = False
                app.main_window = object()
                cfg = SimpleNamespace(
                    settings=SimpleNamespace(onboarding_wizard_shown=shown),
                    locations=["x"] if has_locations else [],
                )
                app.config_manager = SimpleNamespace(get_config=lambda cfg=cfg: cfg)
                decisions.append(
                    {
                        "force_wizard": force,
                        "onboarding_wizard_shown": shown,
                        "has_locations": has_locations,
                        "show": app._should_show_first_start_onboarding(),
                    }
                )

    hints = []
    with tempfile.TemporaryDirectory() as tmp:
        for portable in (False, True):
            for hint_shown in (False, True):
                for wizard_will_show in (False, True):
                    for bundle in (False, True):
                        for imported in (False, True):
                            d = Path(tmp) / f"{portable}{hint_shown}{wizard_will_show}{bundle}{imported}"
                            d.mkdir()
                            if bundle:
                                (d / "api-keys.awkeys").write_text("{}")
                            shown_dialogs: list = []

                            class HintDialog:
                                def __init__(self, parent, message, caption="", style=0):
                                    self.record = [caption, message, [], icon(style)]

                                def SetYesNoCancelLabels(self, *labels):
                                    self.record[2] = list(labels)

                                def ShowModal(self):
                                    shown_dialogs.append(self.record)
                                    return wx.ID_NO

                                def Destroy(self):
                                    pass

                            wx.MessageDialog = HintDialog
                            settings = SimpleNamespace(
                                portable_missing_api_keys_hint_shown=hint_shown,
                                onboarding_wizard_shown=not wizard_will_show,
                            )
                            cfg = SimpleNamespace(settings=settings, locations=[])
                            app = AccessiWeatherApp.__new__(AccessiWeatherApp)
                            app._portable_mode = portable
                            app._force_wizard = False
                            app.debug_mode = False
                            app._portable_keys_imported_this_session = imported
                            app.main_window = SimpleNamespace(open_settings=lambda: None)
                            app.config_manager = SimpleNamespace(
                                get_settings=lambda s=settings: s,
                                get_config=lambda c=cfg: c,
                                update_settings=lambda **k: None,
                                config_dir=d,
                            )
                            app._maybe_show_portable_missing_keys_hint()
                            hints.append(
                                {
                                    "portable": portable,
                                    "hint_shown": hint_shown,
                                    "onboarding_will_show": wizard_will_show,
                                    "bundle_exists": bundle,
                                    "keys_imported_this_session": imported,
                                    "dialog": shown_dialogs[0] if shown_dialogs else None,
                                }
                            )

    write("onboarding.json", {"scenarios": results, "decisions": decisions, "portable_hint": hints})


if __name__ == "__main__":
    logging.basicConfig(level=logging.CRITICAL)
    os.chdir(RUST)
    updates()
    startup()
    activation()
    import_export()
    portable_copy()
    report_issue()
    onboarding()
