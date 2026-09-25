"""
Golden outputs for the aw-audio crate (sound events, pack lookup and
validation, alert sound mapping, ZIP install/import/export, Sound Pack
Manager and wizard file operations, community pack discovery/download and
pack submission).

Run from the Python checkout:

    uv run python <worktree>/rust/tools/golden/audio.py

Writes rust/testdata/golden/audio/*.json. File-system fixtures are described
as data ({relative path: text}) so the Rust tests can build the same trees.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import wx

from accessiweather import sound_events
from accessiweather.models.alerts import WeatherAlert
from accessiweather.notifications import sound_pack_helpers as helpers
from accessiweather.notifications.alert_sound_mapper import get_candidate_sound_events
from accessiweather.notifications.sound_pack_installer import SoundPackInstaller
from accessiweather.services.community_soundpack_models import CommunityPack
from accessiweather.services.community_soundpack_service import CommunitySoundPackService
from accessiweather.services.pack_submission_service import PackSubmissionService
from accessiweather.ui.dialogs.community_packs_dialog import CommunityPacksBrowserDialog
from accessiweather.ui.dialogs.soundpack_manager_dialog import SoundPackManagerDialog
from accessiweather.ui.dialogs.soundpack_wizard_dialog import SoundPackWizardDialog
from accessiweather.ui.dialogs.soundpack_wizard_state import WizardState
from accessiweather.utils.url_validation import SSRFError, validate_backend_url

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "audio"
LOG = logging.getLogger("golden")


def write(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def materialize(root: Path, tree: dict[str, str]) -> None:
    for rel, text in tree.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def listing(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def rel(path: Path | None, root: Path) -> str | None:
    return None if path is None else path.relative_to(root).as_posix()


def zip_bytes(entries: list[list[str]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in entries:
            zf.writestr(name, text)
    return buf.getvalue()


def zip_listing(data: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {n: zf.read(n).decode("utf-8") for n in sorted(zf.namelist())}


def pj(obj) -> str:
    return json.dumps(obj)


# ---------------------------------------------------------------------------
# sound_events.py
# ---------------------------------------------------------------------------


def golden_events() -> None:
    muted_cases = [
        [],
        ["data_updated", " data_updated ", "", "startup", "tornado_warning", "bogus"],
        ["  ", "exit", "EXIT", "exit"],
    ]
    write(
        "events.json",
        {
            "default_muted": list(sound_events.DEFAULT_MUTED_SOUND_EVENTS),
            "sections": [
                [title, desc, [list(e) for e in events]]
                for title, desc, events in sound_events.SOUND_EVENT_SECTIONS
            ],
            "legacy_keys": sorted(sound_events.LEGACY_SOUND_EVENT_KEYS),
            "known_keys": sorted(sound_events.KNOWN_SOUND_EVENT_KEYS),
            "friendly_choices": [list(c) for c in sound_events.FRIENDLY_SOUND_EVENT_CHOICES],
            "normalize": [
                [c, sound_events.normalize_muted_sound_events(c)] for c in muted_cases
            ],
            "normalize_known": [
                [c, sound_events.normalize_known_muted_sound_events(c)] for c in muted_cases
            ],
        },
    )


# ---------------------------------------------------------------------------
# sound_pack_helpers.py
# ---------------------------------------------------------------------------

PACK_FIXTURE = {
    "default/pack.json": pj(
        {
            "name": "Default",
            "sounds": {
                "alert": "alert.ogg",
                "notify": "notify.ogg",
                "startup": "startup.ogg",
                "severe": "severe.ogg",
                "data_updated": "data.ogg",
                "moderate": {"file": "severe.ogg", "volume": 0.6},
            },
            "volumes": {"startup": 0.8},
        }
    ),
    "default/alert.ogg": "a",
    "default/notify.ogg": "n",
    "default/startup.ogg": "s",
    "default/severe.ogg": "v",
    "default/data.ogg": "d",
    "default/exit.ogg": "x",
    "custom/pack.json": pj(
        {
            "name": "Custom",
            "author": "Me",
            "sounds": {
                "alert": {"file": "a.wav", "volume": 0.5},
                "notify": "n.wav",
                "startup": "missing.wav",
                "moderate": "m.wav",
                "warning": "w.wav",
                "severe": None,
                "extreme": {"volume": 0.2},
            },
            "volumes": {"notify": 0.25, "moderate": "0.75", "exit": 1.5, "error": 0.4},
        }
    ),
    "custom/a.wav": "a",
    "custom/n.wav": "n",
    "custom/m.wav": "m",
    "custom/w.wav": "w",
    "custom/error.ogg": "e",
    "custom/extreme.ogg": "x",
    "specific/pack.json": pj(
        {"name": "Specific", "specific_alert_sounds": False, "sounds": {"tornado_warning": "t.wav"}}
    ),
    "specific/t.wav": "t",
    "legacy/pack.json": pj({"name": "Legacy", "sounds": {"tornado_warning": "t.wav"}}),
    "optin/pack.json": pj({"name": "Opt In", "specific_alert_sounds": True, "sounds": {}}),
    "broken/pack.json": "not json",
    "nojson/readme.txt": "no manifest",
    "badvol/pack.json": pj({"name": "BadVol", "sounds": {}, "volumes": {"alert": "loud"}}),
    "range/pack.json": pj({"name": "Range", "sounds": {}, "volumes": {"alert": 1.5}}),
    "volnotdict/pack.json": pj({"name": "VolList", "sounds": {}, "volumes": [1]}),
    "volnull/pack.json": pj({"name": "VolNull", "sounds": {}, "volumes": None}),
    "noname/pack.json": pj({"sounds": {}}),
    "nosounds/pack.json": pj({"name": "x"}),
    "soundslist/pack.json": pj({"name": "x", "sounds": ["a"]}),
    "inline/pack.json": pj(
        {
            "name": "Inline",
            "sounds": {"alert": {"file": "x.wav", "volume": 0.3}, "notify": {"volume": 0.2}},
            "volumes": {"alert": "0.9", "success": "abc"},
        }
    ),
    "inline/x.wav": "x",
    "inline/notify.ogg": "n",
    "strvol/pack.json": pj({"name": "StrVol", "sounds": {}, "volumes": {"alert": " 0.5 "}}),
    "notadir": "plain file",
}

EVENTS = [
    "alert",
    "notify",
    "startup",
    "exit",
    "error",
    "data_updated",
    "moderate",
    "severe",
    "extreme",
    "warning",
    "unknown_event",
]
PACKS = ["default", "custom", "nojson", "broken", "missingpack", "inline"]
CANDIDATES = [
    ["severe", "alert", "notify"],
    ["moderate", "alert"],
    ["tornado_warning", "warning", "severe", "alert", "notify"],
    ["exit"],
    ["error"],
    ["zzz"],
    ["extreme"],
    [],
]

PARSE_CASES = [
    ["alert.wav", "alert", {}],
    ["alert.wav", "alert", {"alert": 0.4}],
    ["alert.wav", "alert", {"alert": "0.4"}],
    ["alert.wav", "alert", {"alert": "loud"}],
    [{"file": "a.wav", "volume": 0.7}, "alert", {"alert": 0.1}],
    [{"file": "a.wav"}, "alert", {}],
    [{"volume": 0.3}, "alert", {}],
    [{"file": "a.wav", "volume": 1.5}, "alert", {}],
    [{"file": "a.wav", "volume": -1}, "alert", {}],
    [{"file": "a.wav", "volume": "loud"}, "alert", {}],
    [{"file": "a.wav", "volume": None}, "alert", {}],
    [{"file": "a.wav", "volume": True}, "alert", {}],
    ["", "alert", {}],
    [None, "notify", {"notify": 0.5}],
    [5, "alert", {}],
]


def golden_packs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        materialize(root, PACK_FIXTURE)

        entries = []
        for event in EVENTS:
            for pack in PACKS:
                path, vol = helpers.get_sound_entry(
                    event, pack, soundpacks_dir=root, default_pack="default", logger=LOG
                )
                entries.append([event, pack, rel(path, root), vol])

        candidates = []
        for cands in CANDIDATES:
            for pack in PACKS:
                try:
                    path, vol = helpers.get_sound_entry_for_candidates(
                        cands,
                        pack,
                        soundpacks_dir=root,
                        default_pack="default",
                        default_event="alert",
                    )
                    candidates.append([cands, pack, rel(path, root), vol])
                except Exception:
                    candidates.append([cands, pack, None, None])

        available = helpers.get_available_sound_packs(soundpacks_dir=root, logger=LOG)
        available_out = sorted(
            [
                {
                    "directory": data["directory"],
                    "path": rel(Path(data["path"]), root),
                    "data": {k: v for k, v in data.items() if k not in ("directory", "path")},
                }
                for data in available.values()
            ],
            key=lambda d: d["directory"],
        )

        pack_dirs = sorted(
            {k.split("/")[0] for k in PACK_FIXTURE} | {"missingpack"}
        )
        specific = {
            p: helpers.sound_pack_prefers_specific_alert_sounds(
                p,
                soundpacks_dir=root,
                specific_alert_keys=sound_events.LEGACY_SOUND_EVENT_KEYS,
                logger=LOG,
            )
            for p in pack_dirs
        }
        validate = {p: list(helpers.validate_sound_pack(root / p)) for p in pack_dirs}

    write(
        "packs.json",
        {
            "fixture": PACK_FIXTURE,
            "parse_sound_entry": [
                [entry, event, volumes, list(helpers.parse_sound_entry(entry, event, volumes))]
                for entry, event, volumes in PARSE_CASES
            ],
            "get_sound_entry": entries,
            "get_sound_entry_for_candidates": candidates,
            "available": available_out,
            "specific_alert_sounds": specific,
            "validate": validate,
        },
    )


# ---------------------------------------------------------------------------
# alert_sound_mapper.py
# ---------------------------------------------------------------------------

ALERTS = [
    {"title": "Tornado Warning", "description": "x", "severity": "Extreme", "event": "Tornado Warning"},
    {"title": "t", "description": "Heavy snow expected", "severity": "high", "event": "Winter Storm Watch"},
    {"title": "Flood Advisory issued", "description": "", "severity": "Moderate", "event": None},
    {"title": "Special Weather Statement", "description": "Dense fog", "severity": "minor",
     "event": "Special Weather Statement", "headline": "Areas of dense fog"},
    {"title": "Air Quality Alert", "description": "smoke", "severity": None, "event": "Air Quality Alert"},
    {"title": "x", "description": "y", "severity": "  CRITICAL ", "event": "Excessive  Heat -- Watch!"},
    {"title": "prewarnings", "description": "", "severity": "bogus", "event": "Red Flag Warning"},
    {"title": "Hurricane", "description": "", "severity": "", "event": "__"},
    {"title": "Blowing Dust Advisory", "description": "", "severity": "low", "event": "Dust Advisory",
     "headline": "Freezing rain and ice"},
]
REASONS = [None, "new_alert", "content_changed", "alert_updated", "updated", "escalated"]


def golden_alert_sounds() -> None:
    cases = []
    for spec in ALERTS:
        alert = WeatherAlert(**spec)
        for specific in (False, True):
            for reason in REASONS:
                cases.append(
                    [
                        spec,
                        specific,
                        reason,
                        get_candidate_sound_events(
                            alert, include_specific_events=specific, notification_reason=reason
                        ),
                    ]
                )
    write("alert_sounds.json", cases)


# ---------------------------------------------------------------------------
# sound_pack_installer.py
# ---------------------------------------------------------------------------

INSTALL_CASES = [
    ["nested", [["MyPack/pack.json", pj({"name": "My Pack", "sounds": {"alert": "a.wav"}})],
                ["MyPack/a.wav", "a"], ["MyPack/sub/extra.txt", "e"]]],
    ["root", [["pack.json", pj({"name": "Root Pack", "author": "R", "sounds": {"alert": "s/a.wav"}})],
              ["s/a.wav", "a"]]],
    ["nested", [["pack.json", pj({"name": "Again", "sounds": {}})]]],
    ["noname_display", [["pack.json", pj({"sounds": {}})]]],
    ["nopack", [["a.wav", "a"]]],
    ["missingfile", [["pack.json", pj({"name": "M", "sounds": {"alert": "gone.wav", "b": "b.wav"}})],
                     ["b.wav", "b"]]],
    ["noname", [["pack.json", pj({"sounds": {}})], ["x/pack.json", pj({"name": "deeper"})]]],
    ["nosounds", [["pack.json", pj({"name": "N"})]]],
    ["dictentry", [["pack.json", pj({"name": "D", "sounds": {"alert": {"file": "a.wav"}}})], ["a.wav", "a"]]],
    ["slip", [["pack.json", pj({"name": "S", "sounds": {}})], ["../evil.txt", "pwned"]]],
    ["badzip", None],
    ["deep", [["a/b/pack.json", pj({"name": "Deep", "sounds": {}})], ["c/pack.txt", "x"]]],
]


def golden_installer() -> None:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        packs = root / "soundpacks"
        installer = SoundPackInstaller(packs)
        for name, entries in INSTALL_CASES:
            zip_path = root / "zips" / f"{name}.zip"
            zip_path.parent.mkdir(exist_ok=True)
            zip_path.write_bytes(b"not a zip" if entries is None else zip_bytes(entries))
            ok, msg = installer.install_from_zip(zip_path, None)
            results.append([name, entries, ok, msg])
        tree = listing(packs)
    write("installer.json", {"cases": results, "tree": tree})


# ---------------------------------------------------------------------------
# Sound Pack Manager / wizard
# ---------------------------------------------------------------------------


class FakeList:
    def __init__(self):
        self.items: list[tuple[str, object]] = []
        self.sel = wx.NOT_FOUND

    def Append(self, label, data=None):
        self.items.append((label, data))

    def Clear(self):
        self.items = []
        self.sel = wx.NOT_FOUND

    def GetCount(self):
        return len(self.items)

    def GetSelection(self):
        return self.sel

    def SetSelection(self, i):
        self.sel = i

    def GetClientData(self, i):
        return self.items[i][1]


class FakeValue:
    def __init__(self, value=None):
        self.value = value
        self.enabled = None

    def SetValue(self, v):
        self.value = v

    def GetValue(self):
        return self.value

    def Enable(self, flag=True):
        self.enabled = flag

    def __getattr__(self, name):
        return MagicMock()


class FakeChoice(FakeValue):
    def __init__(self):
        super().__init__()
        self.sel = wx.NOT_FOUND

    def GetSelection(self):
        return self.sel


class FakeFileDialog:
    path = ""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ShowModal(self):
        return wx.ID_OK

    def GetPath(self):
        return str(FakeFileDialog.path)


MANAGER_FIXTURE = {
    "default/pack.json": pj({"name": "Default", "author": "AccessiWeather Team",
                             "sounds": {"alert": "alert.ogg", "notify": "notify.ogg",
                                        "tornado_warning": "alert.ogg", "wind2x_gust": "gone.ogg"}}),
    "default/alert.ogg": "a",
    "default/notify.ogg": "n",
    "custom/pack.json": json.dumps(
        {"name": "Custom", "author": "Me", "description": "Mine",
         "sounds": {"notify": "n.wav", "alert": {"file": "a.wav", "volume": 0.29},
                    "startup": "missing.wav"},
         "volumes": {"notify": 0.25, "startup": 0.5}, "extra_field": [1, 2]},
        indent=4,
    ),
    "custom/n.wav": "n",
    "custom/a.wav": "a",
    "unicode/pack.json": pj({"name": "Café ☂", "author": "Zoë", "sounds": {"alert": "a.ogg"}}),
    "unicode/a.ogg": "a",
    "unicode/sub/deep.txt": "d",
    "broken/pack.json": "{",
    "external/siren.wav": "siren",
    "external/chime.wav": "chime",
}


def _manager(packs: Path) -> SoundPackManagerDialog:
    dlg = SoundPackManagerDialog.__new__(SoundPackManagerDialog)
    dlg.soundpacks_dir = packs
    dlg.sound_packs = {}
    dlg.selected_pack = None
    dlg.pack_listbox = FakeList()
    dlg.sounds_listbox = FakeList()
    dlg.category_choice = FakeChoice()
    dlg.volume_spin = FakeValue(100)
    dlg.mapping_file_text = FakeValue("")
    dlg.custom_key_input = FakeValue("")
    for name in ("preview_btn", "set_volume_btn", "duplicate_btn", "edit_btn", "delete_btn",
                 "export_btn", "share_btn", "name_label", "author_label", "description_label"):
        setattr(dlg, name, FakeValue())
    dlg._preview_player = MagicMock()
    dlg._preview_player.is_playing.return_value = False
    return dlg


def golden_manager() -> None:
    messages: list[str] = []

    def box(message, *args, **kwargs):
        messages.append(message)
        return wx.YES

    out: dict = {"fixture": MANAGER_FIXTURE}
    with tempfile.TemporaryDirectory() as tmp, \
            patch("wx.MessageBox", box), patch("wx.FileDialog", FakeFileDialog):
        root = Path(tmp)
        materialize(root, MANAGER_FIXTURE)
        packs = root
        dlg = _manager(packs)
        dlg._load_sound_packs()
        out["loaded"] = sorted(
            [
                {"pack_id": i.pack_id, "name": i.name, "author": i.author,
                 "description": i.description, "sounds": i.sounds}
                for i in dlg.sound_packs.values()
            ],
            key=lambda d: d["pack_id"],
        )
        dlg._refresh_pack_list()
        out["pack_list"] = [label for label, _ in dlg.pack_listbox.items]

        details = {}
        for pack_id in sorted(dlg.sound_packs):
            dlg.selected_pack = pack_id
            dlg._update_pack_details()
            categories = []
            from accessiweather.ui.dialogs.soundpack_manager_models import FRIENDLY_ALERT_CATEGORIES
            for i, (_label, key) in enumerate(FRIENDLY_ALERT_CATEGORIES):
                dlg.category_choice.sel = i
                dlg.set_volume_btn.enabled = None
                dlg._on_category_changed(None)
                categories.append([key, dlg.mapping_file_text.value, dlg.volume_spin.value,
                                   bool(dlg.set_volume_btn.enabled)])
            dlg.category_choice.sel = wx.NOT_FOUND
            details[pack_id] = {
                "sounds": [[label, list(data)] for label, data in dlg.sounds_listbox.items],
                "categories": categories,
            }
        out["details"] = details

        def select(pack_id):
            dlg._load_sound_packs()
            dlg.selected_pack = pack_id
            dlg._update_pack_details()

        def pack_json(pack_id):
            return (packs / pack_id / "pack.json").read_text(encoding="utf-8")

        steps = []
        # Set Vol from the sounds list.
        select("custom")
        idx = [d[0] for _, d in dlg.sounds_listbox.items].index("notify")
        dlg.sounds_listbox.sel = idx
        dlg.volume_spin.value = 55
        dlg._on_set_volume(None)
        steps.append(["set_volume", "custom", "notify", "n.wav", 0.55, pack_json("custom")])
        select("custom")
        dlg.sounds_listbox.sel = [d[0] for _, d in dlg.sounds_listbox.items].index("startup")
        dlg.volume_spin.value = 100
        dlg._on_set_volume(None)
        steps.append(["set_volume", "custom", "startup", "missing.wav", 1.0, pack_json("custom")])

        # Browse / custom key mappings.
        for key, src, pct in (("severe", "siren.wav", 40), ("exit", "chime.wav", 100),
                              ("tornado_warning", "siren.wav", 100)):
            select("custom")
            FakeFileDialog.path = root / "external" / src
            dlg.volume_spin.value = pct
            messages.clear()
            dlg._apply_mapping(key)
            steps.append(["apply_mapping", "custom", key, src, pct / 100.0, messages[-1], pack_json("custom")])

        for key in ("  Severe ", "nothere"):
            select("custom")
            dlg.custom_key_input.value = key
            messages.clear()
            dlg._on_remove_mapping(None)
            steps.append(["remove_mapping", "custom", key, messages[-1], pack_json("custom")])
        out["steps"] = steps

        # Duplicate twice.
        dups = []
        for _ in range(2):
            select("unicode")
            before = {p.name for p in packs.iterdir()}
            messages.clear()
            dlg._on_duplicate_pack(None)
            new_id = sorted({p.name for p in packs.iterdir()} - before)[0]
            dups.append([new_id, messages[-1], listing(packs / new_id)])
        out["duplicate"] = dups

        # Export.
        select("unicode")
        FakeFileDialog.path = root / "export.zip"
        messages.clear()
        dlg._on_export_pack(None)
        out["export"] = zip_listing((root / "export.zip").read_bytes())

        # Import (manager flavour): pack.json at the root, id from the name.
        imports = []
        for name, entries in (
            ["first", [["pack.json", pj({"name": "Imported Pack-One", "sounds": {"alert": "a.wav"}})],
                       ["a.wav", "1"], ["sub/b.wav", "b"]]],
            ["overwrite", [["pack.json", pj({"name": "Imported Pack-One", "sounds": {}})], ["c.wav", "2"]]],
            ["unnamed", [["pack.json", pj({"sounds": {}})]]],
            ["nested", [["x/pack.json", pj({"name": "Nested"})]]],
        ):
            zip_path = root / f"import_{name}.zip"
            zip_path.write_bytes(zip_bytes(entries))
            FakeFileDialog.path = zip_path
            messages.clear()
            dlg._on_import_pack(None)
            imports.append([name, entries, list(messages)])
        out["import"] = imports
        out["import_tree"] = {
            "imported_pack_one": listing(packs / "imported_pack_one"),
            "unknown_pack": listing(packs / "unknown_pack"),
        }

        # Wizard: create twice with the same name.
        created = []
        src = root / "wizard_src"
        materialize(src, {"one.wav": "1", "two.ogg": "2"})
        for _ in range(2):
            wiz = SoundPackWizardDialog.__new__(SoundPackWizardDialog)
            wiz.soundpacks_dir = packs
            wiz.staging_dir = Path(tempfile.mkdtemp())
            wiz.state = WizardState(
                pack_name="My Cool-Pack! é",
                author="",
                description="Desc é",
                selected_alert_keys=["startup", "alert", "exit"],
                sound_mappings={
                    "exit": str(src / "two.ogg"),
                    "startup": str(src / "one.wav"),
                    "alert": str(src / "gone.wav"),
                    "notify": str(src / "one.wav"),
                },
            )
            wiz.created_pack_id = None
            wiz.EndModal = lambda code: None
            messages.clear()
            wiz._create_pack()
            created.append([wiz.created_pack_id, messages[-1], listing(packs / wiz.created_pack_id)])
        out["wizard"] = {
            "state": {"pack_name": "My Cool-Pack! é", "author": "", "description": "Desc é",
                      "sources": ["exit=two.ogg", "startup=one.wav", "alert=gone.wav", "notify=one.wav"]},
            "created": created,
        }
    write("manager.json", out)


# ---------------------------------------------------------------------------
# Community packs
# ---------------------------------------------------------------------------

API = "https://api.github.com/repos/orinks/accessiweather-soundpacks"
RAW = "https://raw.githubusercontent.com/orinks/accessiweather-soundpacks/main"

INDEX = {
    "packs": [
        {"name": "Storm", "author": "Ann", "description": "Loud", "version": "2.1",
         "download_url": "https://example.com/storm.zip", "file_size": 262144,
         "homepage": "https://example.com/storm", "release_tag": "v2.1", "download_count": 7,
         "created_date": "2025-01-02", "preview_image_url": "https://example.com/s.png"},
        {"id": "only-id"},
        {"name": "", "id": "", "version": 2, "file_size": 1572864},
        {"name": "Tiny", "file_size": 786432, "release_tag": 3},
    ]
}

RELEASES = [
    {"tag_name": "vv1.2", "body": "  Release notes \n", "author": {"login": "bob"},
     "published_at": "2025-03-04T00:00:00Z", "html_url": "https://github.com/x/releases/1",
     "assets": [
         {"name": "alpha.zip", "browser_download_url": "https://dl/alpha.zip", "size": 1048576,
          "download_count": 3},
         {"name": "Beta.ZIP", "browser_download_url": "https://dl/beta", "size": 0},
         {"name": "readme.txt"},
     ]},
    {"tag_name": "", "body": None, "author": None,
     "assets": [{"name": "c.zip.zip", "size": 52428, "browser_download_url": "https://dl/c"}]},
    {"tag_name": "v", "assets": None},
]

REPO_ENTRIES = [
    {"type": "dir", "name": "alpha", "path": "packs/alpha", "sha": "a1"},
    {"type": "dir", "name": "beta", "path": "packs/beta"},
    {"type": "file", "name": "README.md", "path": "packs/README.md"},
    {"type": "dir", "name": "gamma", "path": "packs/gamma", "sha": "g1"},
    {"type": "dir", "name": "delta", "sha": "d1"},
]

TREE_A1 = {"tree": [
    {"type": "blob", "path": "pack.json", "size": 40},
    {"type": "tree", "path": "sounds"},
    {"type": "blob", "path": "sounds/a.wav", "size": 5},
    {"type": "blob", "path": "sounds/b.wav"},
]}


def _b64(obj) -> str:
    raw = base64.b64encode(json.dumps(obj).encode()).decode()
    return "\n".join(raw[i:i + 60] for i in range(0, len(raw), 60)) + "\n"


SCENARIOS = {
    "index": {
        f"{API}/contents/index.json": [200, {"content": _b64(INDEX)}],
    },
    "releases": {
        f"{API}/contents/index.json": [404, {"message": "Not Found"}],
        f"{API}/releases?per_page=50": [200, RELEASES],
    },
    "repo": {
        f"{API}/contents/index.json": [200, {"content": ""}],
        f"{API}/releases?per_page=50": [403, {"message": "rate limited"}],
        f"{API}/contents/packs?ref=main": [200, REPO_ENTRIES],
        f"{RAW}/packs/alpha/pack.json": [200, {"name": "Alpha", "author": "A", "version": 1.5,
                                                "description": "First", "preview_image_url": "http://p"}],
        f"{RAW}/packs/beta/pack.json": [200, {}],
        f"{RAW}/packs/gamma/pack.json": [404, "Not Found"],
        f"{RAW}/packs/delta/pack.json": [200, {"name": "Delta"}],
        f"{API}/git/trees/a1?recursive=1": [200, TREE_A1],
        f"{API}/git/trees/d1?recursive=1": [500, {"message": "oops"}],
    },
    "empty": {
        f"{API}/contents/index.json": [200, {"content": _b64({"packs": []})}],
        f"{API}/releases?per_page=50": [200, []],
        f"{API}/contents/packs?ref=main": [404, {"message": "Not Found"}],
    },
}


def _body(value) -> bytes:
    return value.encode() if isinstance(value, str) else json.dumps(value).encode()


def _text_routes(routes: dict) -> dict:
    """Routes with the exact response body text the mock serves."""
    return {url: [status, _body(body).decode()] for url, (status, body) in routes.items()}


def _service(routes: dict, log: list) -> CommunitySoundPackService:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        log.append(url)
        status, body = routes[url]
        return httpx.Response(status, content=_body(body))

    service = CommunitySoundPackService()
    service._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return service


def golden_community() -> None:
    out: dict = {"scenarios": {}}
    for name, routes in SCENARIOS.items():
        log: list[str] = []
        service = _service(routes, log)
        packs = asyncio.run(service.fetch_available_packs())
        out["scenarios"][name] = {
            "routes": _text_routes(routes),
            "packs": [p.__dict__.copy() for p in packs],
            "requests": log,
        }

    # Dialog list/details strings for the index and repo packs.
    all_packs = []
    for name in ("index", "releases", "repo"):
        all_packs += [CommunityPack(**p) for p in out["scenarios"][name]["packs"]]
    dlg = CommunityPacksBrowserDialog.__new__(CommunityPacksBrowserDialog)
    dlg._packs = all_packs
    dlg.pack_listbox = FakeList()
    dlg.install_btn = FakeValue()
    labels = {}
    for attr in ("name_label", "author_label", "version_label", "size_label"):
        labels[attr] = MagicMock()
        setattr(dlg, attr, labels[attr])
    dlg.description_text = FakeValue()
    filters = {}
    for ft in ("", "  ALPHA ", "bob", "zzz"):
        dlg._populate_list(ft)
        filters[ft] = [label for label, _ in dlg.pack_listbox.items]
    details = []
    for pack in all_packs:
        dlg._update_details(pack)
        details.append([labels[a].SetLabel.call_args[0][0] for a in labels] + [dlg.description_text.value])
    out["display"] = {
        "keys": [dlg._pack_key(p) for p in all_packs],
        "installable": [bool(p.download_url or getattr(p, "repo_path", None)) for p in all_packs],
        "filters": filters,
        "details": details,
        "str": [str(p) for p in all_packs],
    }
    progress = []
    for downloaded, total in ((0, 0), (52428, 0), (262144, 1048576), (1048576, 1048576), (1100000, 3000000)):
        if total > 0:
            detail = f"{downloaded / (1024 * 1024):.1f} MB of {total / (1024 * 1024):.1f} MB"
        else:
            detail = f"{downloaded / (1024 * 1024):.1f} MB downloaded"
        progress.append([downloaded, total, detail])
    out["progress_detail"] = progress

    # Downloads.
    downloads = []
    repo_routes = dict(SCENARIOS["repo"])
    repo_routes[f"{RAW}/packs/alpha/pack.json"] = [200, {"name": "Alpha", "sounds": {"a": "sounds/a.wav"}}]
    repo_routes[f"{RAW}/packs/alpha/sounds/a.wav"] = [200, "AAAAA"]
    repo_routes[f"{RAW}/packs/alpha/sounds/b.wav"] = [200, "bb"]
    repo_routes["https://dl/alpha.zip"] = [200, "zip-bytes-here"]
    repo_routes["https://dl/fail"] = [404, "nope"]
    repo_routes[f"{API}/git/trees/evil?recursive=1"] = [200, {"tree": [
        {"type": "blob", "path": "ok.wav", "size": 1}, {"type": "blob", "path": "../escape.wav", "size": 4}]}]
    repo_routes[f"{RAW}/packs/evil/ok.wav"] = [200, "o"]
    alpha = CommunityPack(name="Alpha Pack", author="A", description="", version="1.5",
                          download_url="", file_size=None, repository_url="", release_tag="main",
                          repo_path="packs/alpha", tree_sha="a1")
    url_pack = CommunityPack(name="alpha", author="bob", description="", version="1.2",
                             download_url="https://dl/alpha.zip", file_size=14, repository_url="",
                             release_tag="vv1.2")
    fail_pack = CommunityPack(name="fail", author="x", description="", version="1",
                              download_url="https://dl/fail", file_size=None, repository_url="",
                              release_tag="")
    evil = CommunityPack(name="Evil", author="x", description="", version="1", download_url="",
                         file_size=None, repository_url="", release_tag="", repo_path="packs/evil",
                         tree_sha="evil")
    nosource = CommunityPack(name="Nothing", author="x", description="", version="1",
                             download_url="", file_size=None, repository_url="", release_tag="")
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "_downloads"
        for pack in (alpha, alpha, url_pack, fail_pack, evil, nosource):
            log: list[str] = []
            calls: list = []
            service = _service(repo_routes, log)
            try:
                path = asyncio.run(service.download_pack(
                    pack, dest, lambda pct, done, total: calls.append([pct, done, total])))
                result = {"file": path.name, "zip": zip_listing(path.read_bytes())
                          if zipfile.is_zipfile(path) else path.read_text()}
            except Exception as exc:
                result = {"error": str(exc)}
            downloads.append({"pack": pack.__dict__.copy(), "result": result, "progress": calls,
                              "requests": log})
        leftovers = sorted(p.name for p in dest.iterdir())
    out["downloads"] = {"routes": _text_routes(repo_routes), "cases": downloads, "leftovers": leftovers}
    write("community.json", out)


# ---------------------------------------------------------------------------
# Pack submission
# ---------------------------------------------------------------------------


def golden_submission() -> None:
    derive = []
    for dir_name, meta in (
        ("my_pack", {"name": "My Pack", "author": "Jane Doe"}),
        ("my_pack", {"name": "  Storm Sounds!  ", "author": "Unknown"}),
        ("dir name", {"name": "", "author": ""}),
        ("x", {"name": "Café ☂", "author": "UNKNOWN"}),
        ("weird", {"name": "!!!", "author": None}),
        ("a", {"name": "Name_With_Underscores", "author": "B-C"}),
    ):
        derive.append([dir_name, meta, PackSubmissionService._derive_pack_id(Path("/p") / dir_name, meta)])

    urls = []
    for url in ("", "   ", "http://example.com", "ftp://x", "not a url", "https://", "https://localhost/x",
                "https://127.0.0.1", "https://[::1]:8443/", "https://0.0.0.0", "https://10.1.2.3",
                "https://172.20.0.1/api", "https://192.168.1.1", "https://169.254.1.1",
                "https://100.64.0.1", "https://8.8.8.8/", "https://[fe80::1]", "https://[2001:db8::1]",
                "https://[2606:4700::1111]", "https://[::ffff:10.0.0.1]", "https://240.0.0.1",
                "https://192.0.0.9", "https://example.invalid/path", "  https://example.invalid  "):
        try:
            urls.append([url, True, validate_backend_url(url)])
        except SSRFError as exc:
            urls.append([url, False, str(exc)])

    submissions = []
    pack_tree = {"pack.json": pj({"name": "My Pack", "author": "Jane", "sounds": {"alert": "s/a.wav"}}),
                 "s/a.wav": "a", "notes.txt": "n"}
    with tempfile.TemporaryDirectory() as tmp:
        pack_path = Path(tmp) / "my_pack"
        materialize(pack_path, pack_tree)
        bad_path = Path(tmp) / "bad_pack"
        materialize(bad_path, {"pack.json": pj({"name": "Bad", "sounds": {"alert": "gone.wav"}})})
        for case, path, status, body in (
            ("ok", pack_path, 200, {"html_url": "https://github.com/orinks/accessiweather-soundpacks/pull/9"}),
            ("no_url", pack_path, 200, {"number": 3}),
            ("http_500", pack_path, 500, {"detail": "boom"}),
            ("http_422", pack_path, 422, {"detail": [{"loc": ["body"], "msg": "bad", "type": "x"}]}),
            ("http_502", pack_path, 502, "Bad Gateway"),
            ("invalid_pack", bad_path, 200, {}),
        ):
            requests = []

            def handler(request: httpx.Request, status=status, body=body):
                content_type = request.headers["content-type"]
                boundary = content_type.split("boundary=")[1].encode()
                raw = request.read()
                part = [p for p in raw.split(b"--" + boundary) if b"filename=" in p][0]
                head, _, data = part.partition(b"\r\n\r\n")
                head = head.decode()
                requests.append({
                    "url": str(request.url),
                    "method": request.method,
                    "field": re.search(r'name="([^"]+)"', head).group(1),
                    "filename": re.search(r'filename="([^"]+)"', head).group(1),
                    "content_type": re.search(r"Content-Type: (\S+)", head).group(1),
                    "zip": zip_listing(data[:-2]),
                })
                return httpx.Response(status, content=_body(body))

            real_client = httpx.AsyncClient
            progress = []
            with patch(
                "accessiweather.services.github_backend_client.httpx.AsyncClient",
                lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
            ):
                service = PackSubmissionService()
                meta = {"name": "My Pack", "author": "Jane", "description": "", "sounds": {}}
                try:
                    result = {"url": asyncio.run(service.submit_pack(
                        path, meta, lambda pct, status: progress.append([pct, status])))}
                except Exception as exc:
                    result = {"error": str(exc).replace(str(path), "<PACK>")}
            submissions.append({"case": case, "status": status, "body": body, "result": result,
                                "progress": progress, "requests": requests})
    write("submission.json", {"derive_pack_id": derive, "validate_backend_url": urls,
                              "pack_tree": pack_tree, "submissions": submissions})


def main() -> None:
    logging.basicConfig(level=logging.CRITICAL)
    golden_events()
    golden_packs()
    golden_alert_sounds()
    golden_installer()
    golden_manager()
    golden_community()
    golden_submission()
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
