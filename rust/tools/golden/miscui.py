"""Golden parity data for the Help menu, update flow and Debug menu dialogs.

Covers ui/dialogs/update_dialog.py, the Help > Check for Updates flow
(ui/main_window_commands.py `_on_check_updates`), the download/apply flow
(app_lifecycle.py `_download_and_apply_update`), ui/dialogs/report_issue_dialog.py,
ui/dialogs/debug_alert_dialog.py and the Debug menu handlers.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/miscui.py

Dialogs are built under a hidden frame (never shown, no main loop). The
flows run with wx's message boxes, CallAfter, threads and the update
service replaced by recorders, so every box, dialog and progress update
is captured with the exact text and style Python passes.
Writes rust/testdata/golden/miscui/cases.json.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import wx

import accessiweather.notifications.notification_test as notification_test
import accessiweather.services.simple_update as simple_update
import accessiweather.ui.dialogs.update_dialog as update_dialog
import accessiweather.ui.main_window as main_window_module
from accessiweather.app_lifecycle import AppLifecycleMixin
from accessiweather.models import AppSettings
from accessiweather.ui.dialogs.debug_alert_dialog import ALERT_PRESETS, DebugAlertDialog
from accessiweather.ui.dialogs.report_issue_dialog import ReportIssueDialog
from accessiweather.ui.main_window_commands import MainWindowCommandMixin

OUT = Path(__file__).resolve().parents[2] / "testdata" / "golden" / "miscui" / "cases.json"

RELEASE_NOTES = (
    "## Added\n- **National Products** now use `IEM AFOS` text.\n\n"
    "## Fixed\n- Pirate Weather handles _freezing rain_ correctly.\n"
)
DOWNLOAD_PATH = r"C:\Users\Test\AppData\Local\Temp\accessiweather-windows-x86_64.zip"

WX_CONSTANTS = {
    name: getattr(wx, name)
    for name in [
        "OK",
        "CANCEL",
        "YES_NO",
        "YES",
        "NO",
        "ICON_INFORMATION",
        "ICON_WARNING",
        "ICON_ERROR",
        "ICON_QUESTION",
        "TE_PASSWORD",
        "FD_OPEN",
        "FD_FILE_MUST_EXIST",
        "PD_APP_MODAL",
        "PD_AUTO_HIDE",
        "PD_CAN_ABORT",
        "ID_OK",
        "ID_CANCEL",
        "ID_CLOSE",
        "ID_YES",
        "ID_NO",
    ]
}


class Recorder:
    """Stands in for wx's top-level helpers while a flow runs."""

    def __init__(self):
        self.events: list = []
        self.message_box_answer = wx.OK

    def message_box(self, message, caption="Message", style=wx.OK | wx.CENTRE, *args, **kwargs):
        self.events.append(["message_box", message, caption, style])
        return self.message_box_answer


class SyncThread:
    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


class Patch:
    """Set attributes for the duration of a `with` block."""

    def __init__(self, *triples):
        self.triples = triples
        self.saved = []

    def __enter__(self):
        for obj, name, value in self.triples:
            self.saved.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

    def __exit__(self, *exc):
        for obj, name, value in reversed(self.saved):
            setattr(obj, name, value)


def text_flags(ctrl) -> dict:
    style = ctrl.GetWindowStyleFlag()
    return {
        "multiline": bool(style & wx.TE_MULTILINE),
        "readonly": bool(style & wx.TE_READONLY),
        "rich2": bool(style & wx.TE_RICH2),
        "dont_wrap": bool(style & wx.TE_DONTWRAP),
        "no_vscroll": bool(style & wx.TE_NO_VSCROLL),
    }


def describe(child) -> dict:
    if isinstance(child, wx.Button):
        # wx numbers controls created with ID_ANY itself (negative ids).
        button_id = child.GetId() if child.GetId() > 0 else "auto"
        return {
            "kind": "button",
            "id": button_id,
            "label": child.GetLabel(),
            "name": child.GetName(),
        }
    if isinstance(child, wx.TextCtrl):
        return {
            "kind": "text",
            "name": child.GetName(),
            "value": child.GetValue(),
            "hint": child.GetHint(),
            **text_flags(child),
        }
    if isinstance(child, wx.StaticText):
        return {"kind": "label", "label": child.GetLabel()}
    if isinstance(child, wx.Choice):
        return {
            "kind": "choice",
            "name": child.GetName(),
            "items": list(child.GetItems()),
            "selection": child.GetSelection(),
        }
    if isinstance(child, wx.ListBox):
        return {
            "kind": "listbox",
            "name": child.GetName(),
            "items": list(child.GetItems()),
            "selection": child.GetSelection(),
            "single": not child.GetWindowStyleFlag() & (wx.LB_MULTIPLE | wx.LB_EXTENDED),
        }
    raise TypeError(type(child))


def default_item(dlg):
    item = dlg.GetDefaultItem()
    return item.GetLabel() if item else None


# --------------------------------------------------------------------------
# Update available dialog
# --------------------------------------------------------------------------


def update_dialogs(parent) -> list:
    cases = [
        ("0.10.1", "0.11.0", "Stable", RELEASE_NOTES),
        ("20260924", "20260925", "Nightly", ""),
        ("0.10.1", "20260925", "Nightly", "Commit: abc1234\n\n* one\n* two"),
    ]
    out = []
    for current, new, channel, notes in cases:
        dlg = update_dialog.UpdateAvailableDialog(parent, current, new, channel, notes)
        try:
            out.append(
                {
                    "current_version": current,
                    "new_version": new,
                    "channel_label": channel,
                    "release_notes": notes,
                    "title": dlg.GetTitle(),
                    "resizable": bool(dlg.GetWindowStyleFlag() & wx.RESIZE_BORDER),
                    "size": list(dlg.GetSize()),
                    "controls": [describe(c) for c in dlg.GetChildren()],
                    "default": default_item(dlg),
                    "focus": dlg.changelog_text.HasFocus()
                    or wx.Window.FindFocus() is dlg.changelog_text,
                    "insertion_point": dlg.changelog_text.GetInsertionPoint(),
                }
            )
        finally:
            dlg.Destroy()
    return out


# --------------------------------------------------------------------------
# Help > Check for Updates
# --------------------------------------------------------------------------


def update_info(version, nightly):
    return simple_update.UpdateInfo(
        version=version,
        download_url="https://example.com/a.zip",
        artifact_name="accessiweather-windows-x86_64.zip",
        release_notes=RELEASE_NOTES,
        commit_hash=None,
        is_nightly=nightly,
        is_prerelease=False,
    )


def check_updates() -> list:
    scenarios = [
        {"name": "source", "compiled": False},
        {"name": "up_to_date", "version": "0.10.1", "build_tag": None, "channel": "stable"},
        {
            "name": "nightly_on_stable",
            "version": "0.10.1",
            "build_tag": "nightly-20260924",
            "channel": "stable",
        },
        {
            "name": "latest_nightly",
            "version": "0.10.1",
            "build_tag": "nightly-20260924",
            "channel": "nightly",
        },
        {
            "name": "stable_update",
            "version": "0.10.1",
            "build_tag": None,
            "channel": "stable",
            "update": ("0.11.0", False),
        },
        {
            "name": "nightly_update",
            "version": "0.10.1",
            "build_tag": "nightly-20260924",
            "channel": "nightly",
            "update": ("20260925", True),
        },
        {
            "name": "stable_to_nightly",
            "version": "0.10.1",
            "build_tag": None,
            "channel": "nightly",
            "update": ("20260925", True),
        },
        {
            "name": "failure",
            "version": "0.10.1",
            "build_tag": None,
            "channel": "stable",
            "error": "network down",
        },
    ]
    out = []
    for sc in scenarios:
        rec = Recorder()
        checks = []

        class FakeService:
            def __init__(self, *args, **kwargs):
                pass

            async def check_for_updates(self, **kwargs):
                checks.append(kwargs)
                if "error" in sc:
                    raise RuntimeError(sc["error"])
                if "update" in sc:
                    return update_info(*sc["update"])
                return None

            async def close(self):
                pass

        class FakeDialog:
            def __init__(self, parent, **kwargs):
                rec.events.append(["update_dialog", kwargs])

            def ShowModal(self):
                return wx.ID_CANCEL

            def Destroy(self):
                pass

        settings = SimpleNamespace(update_channel=sc.get("channel", "stable"))
        view = SimpleNamespace(
            app=SimpleNamespace(
                config_manager=SimpleNamespace(get_settings=lambda s=settings: s),
                version=sc.get("version", "0.0.0"),
                build_tag=sc.get("build_tag"),
            )
        )
        view._get_update_channel = lambda: MainWindowCommandMixin._get_update_channel(view)
        with Patch(
            (main_window_module, "is_compiled_runtime", lambda c=sc.get("compiled", True): c),
            (wx, "MessageBox", rec.message_box),
            (wx, "CallAfter", lambda f, *a, **k: f(*a, **k)),
            (wx, "BeginBusyCursor", lambda *a: rec.events.append(["begin_busy_cursor"])),
            (wx, "EndBusyCursor", lambda *a: rec.events.append(["end_busy_cursor"])),
            (threading, "Thread", SyncThread),
            (simple_update, "UpdateService", FakeService),
            (update_dialog, "UpdateAvailableDialog", FakeDialog),
        ):
            MainWindowCommandMixin._on_check_updates(view)
        out.append({**sc, "check_args": checks, "events": rec.events})
    return out


# --------------------------------------------------------------------------
# Download and apply
# --------------------------------------------------------------------------


def download_flows() -> list:
    progress_pairs = [
        (0, 0),
        (65536, 0),
        (51200, 102400),
        (29, 100),
        (1536000, 3072000),
        (102400, 102400),
    ]
    scenarios = [
        {"name": "manual_install", "can_auto_apply": False},
        {"name": "apply_declined", "can_auto_apply": True, "answer": "NO"},
        {"name": "apply_accepted", "can_auto_apply": True, "answer": "YES"},
        {"name": "download_error", "error": "Checksum verification failed for app.zip."},
    ]
    out = []
    for sc in scenarios:
        rec = Recorder()
        rec.message_box_answer = getattr(wx, sc.get("answer", "OK"))

        class FakeProgress:
            def __init__(self, title, message, maximum=100, parent=None, style=0):
                rec.events.append(["progress_dialog", title, message, maximum, style])

            def Update(self, value, newmsg=""):
                rec.events.append(["progress_update", value, newmsg])
                return (True, False)

            def Destroy(self):
                rec.events.append(["progress_destroy"])

        class FakeService:
            def __init__(self, *args, **kwargs):
                pass

            async def download_update(self, info, dest_dir, progress_callback):
                for downloaded, total in progress_pairs:
                    progress_callback(downloaded, total)
                if "error" in sc:
                    raise RuntimeError(sc["error"])
                return DOWNLOAD_PATH

            async def close(self):
                pass

        app = SimpleNamespace(main_window=None, _portable_mode=False)
        with Patch(
            (wx, "MessageBox", rec.message_box),
            (wx, "CallAfter", lambda f, *a, **k: f(*a, **k)),
            (wx, "ProgressDialog", FakeProgress),
            (wx, "GetTopLevelWindows", lambda: []),
            (wx, "SafeYield", lambda *a, **k: True),
            (threading, "Thread", SyncThread),
            (simple_update, "UpdateService", FakeService),
            (simple_update, "can_auto_apply", lambda path, **k: sc.get("can_auto_apply", False)),
            (
                simple_update,
                "apply_update",
                lambda path, **k: rec.events.append(["apply_update", str(path)]),
            ),
        ):
            AppLifecycleMixin._download_and_apply_update(app, update_info("0.11.0", False))
        out.append({**sc, "progress_pairs": progress_pairs, "events": rec.events})
    return out


# --------------------------------------------------------------------------
# Report Issue
# --------------------------------------------------------------------------


def report_issue(parent) -> dict:
    dlg = ReportIssueDialog(parent)
    try:
        controls = [describe(c) for c in dlg.GetChildren()]
        controls[7]["value"] = None
        data = {
            "title": dlg.GetTitle(),
            "resizable": bool(dlg.GetWindowStyleFlag() & wx.RESIZE_BORDER),
            "size": list(dlg.GetSize()),
            "controls": controls,
            "info_min_height": dlg.info_text.GetMinSize().GetHeight(),
            # Machine-specific; the Rust edition's block is golden-tested in services.
            "system_info_lines": [
                line.split(":")[0] for line in dlg.info_text.GetValue().splitlines()
            ],
            "default": default_item(dlg),
        }
        rec = Recorder()
        with Patch((wx, "MessageBox", rec.message_box)):
            dlg.title_input.SetValue("   ")
            dlg._on_submit(None)
        data["empty_title_events"] = rec.events
        return data
    finally:
        dlg.Destroy()


# --------------------------------------------------------------------------
# Debug menu
# --------------------------------------------------------------------------


def debug_alert(parent) -> dict:
    sent: list = []
    answers = [True, False]

    def send_notification(**kwargs):
        sent.append(kwargs)
        return answers[len(sent) - 1]

    app = SimpleNamespace(
        config_manager=SimpleNamespace(get_settings=lambda: AppSettings()),
        notifier=SimpleNamespace(send_notification=send_notification),
    )
    dlg = DebugAlertDialog(parent, app)
    try:
        (panel,) = dlg.GetChildren()
        data = {
            "title": dlg.GetTitle(),
            "resizable": bool(dlg.GetWindowStyleFlag() & wx.RESIZE_BORDER),
            "size": list(dlg.GetSize()),
            "controls": [describe(c) for c in panel.GetChildren()],
            "default": default_item(dlg),
            "candidates_height": dlg._candidates_label.GetSize().GetHeight(),
        }
        candidates = []
        for i, preset in enumerate(ALERT_PRESETS):
            dlg._list.SetSelection(i)
            dlg._update_candidates()
            candidates.append({"label": preset.label, "text": dlg._candidates_label.GetValue()})
        data["candidates"] = candidates
        statuses = []
        for index in (0, 7):
            dlg._list.SetSelection(index)
            dlg._on_send(None)
            statuses.append(dlg._status.GetLabel())
        for kwargs in sent:
            kwargs["sound_candidates"] = list(kwargs["sound_candidates"])
        data["sends"] = [
            {"preset": i, "kwargs": k, "status": s} for i, k, s in zip((0, 7), sent, statuses)
        ]
        return data
    finally:
        dlg.Destroy()


def debug_commands() -> dict:
    rec = Recorder()
    sent: list = []

    def send_notification(**kwargs):
        sent.append(kwargs)
        return False

    view = SimpleNamespace(
        app=SimpleNamespace(
            config_manager=SimpleNamespace(
                get_settings=lambda: AppSettings(), get_current_location=lambda: None
            ),
            notifier=SimpleNamespace(send_notification=send_notification),
            weather_client=object(),
        )
    )
    with Patch((wx, "MessageBox", rec.message_box)):
        MainWindowCommandMixin._on_test_discussion_notification(view)
    discussion = {"kwargs": sent[0], "events": rec.events}

    rec = Recorder()
    with Patch((wx, "MessageBox", rec.message_box)):
        MainWindowCommandMixin._on_debug_simulate_alert(view)
        view.app.weather_client = None
        MainWindowCommandMixin._on_debug_simulate_alert(view)
    simulate = rec.events

    diagnostics = []
    for passed in ([True, True, True], [True, False, True]):
        keys = ["safe_desktop_notifier", "alert_notification_system", "discussion_update_path"]
        results = {k: {"passed": p, "message": f"{k} detail"} for k, p in zip(keys, passed)}
        results.update(passed_count=sum(passed), total_count=len(passed), all_passed=all(passed))
        rec = Recorder()
        with Patch(
            (wx, "MessageBox", rec.message_box),
            (notification_test, "run_notification_test", lambda app, r=results: r),
        ):
            MainWindowCommandMixin._on_test_notifications(view)
        diagnostics.append({"passed": passed, "events": rec.events})
    return {"discussion": discussion, "simulate": simulate, "diagnostics": diagnostics}


def main() -> None:
    app = wx.App()
    parent = wx.Frame(None)
    parent.Hide()
    try:
        data = {
            "wx": WX_CONSTANTS,
            "update_dialogs": update_dialogs(parent),
            "check_updates": check_updates(),
            "downloads": download_flows(),
            "report_issue": report_issue(parent),
            "debug_alert": debug_alert(parent),
            "debug_commands": debug_commands(),
        }
    finally:
        parent.Destroy()
        del app
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
