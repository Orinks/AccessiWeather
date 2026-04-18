# Alert Dialog: Copy-to-Clipboard Button — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Copy to clipboard" button to `AlertDialog` that works identically in both display styles (separate and combined), copying the same text block via the existing `_build_combined_text` helper.

**Architecture:** Extract the close-button sizer block into a shared `_add_action_buttons(panel, main_sizer)` helper (Copy on the left, Close on the right). Copy uses `wx.TheClipboard` with a try/finally around `Close()`, logs + flashes the button to "Copy failed" on lock contention, and flashes to "Copied!" on success. Label flip reverts after 2 s via `wx.CallLater`. Payload comes from a new `@staticmethod _copy_payload` that delegates to `_build_combined_text` — giving tests a named entry point independent of button wiring.

**Tech Stack:** Python 3.10+, wxPython 4.2.x, pytest. Runtime: `uv run accessiweather` (NOT `briefcase dev` — the worktree CLAUDE.md is stale on that).

**Design doc:** [docs/plans/2026-04-18-alert-copy-button-design.md](2026-04-18-alert-copy-button-design.md)

**Ground truth already verified in the code on this branch:**
- `AlertDialog._build_combined_text(alert, settings)` exists at `src/accessiweather/ui/dialogs/alert_dialog.py:205-236` as a `@staticmethod`. It handles `settings=None` gracefully (via `getattr` fallbacks).
- Both `_create_separate_ui` and `_create_combined_ui` end with a very similar close-button block (`button_sizer` → `AddStretchSpacer` → `wx.Button(panel, wx.ID_CLOSE, "Close")` bound to `_on_close`).
- `self._focus_target` is already assigned in both UI builders; Task 3 must not disturb focus.
- `tests/test_alert_dialog_dispatch.py` already provides a `hidden_parent` fixture pattern we can reuse.

---

## Task 1: Add `_copy_payload` staticmethod + pure tests

**Files:**
- Modify: `src/accessiweather/ui/dialogs/alert_dialog.py` (add one `@staticmethod`)
- Create: `tests/test_alert_dialog_copy_text.py`

### Step 1.1: Write failing tests

Create `tests/test_alert_dialog_copy_text.py`:

```python
"""Tests for AlertDialog._copy_payload (clipboard text source)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog


def _alert():
    return SimpleNamespace(
        title="t",
        description="WHAT...Frost.\nWHERE...Michigan.",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Frost Advisory",
        headline="FROST ADVISORY IN EFFECT 2 AM TO 10 AM",
        instruction="Protect tender plants.",
        areas=[],
        references=[],
        sent=datetime(2026, 4, 18, 14, 10),
        expires=datetime(2026, 4, 18, 22, 15),
    )


class TestCopyPayload:
    def test_matches_build_combined_text(self) -> None:
        alert = _alert()
        settings = AppSettings()
        assert AlertDialog._copy_payload(alert, settings) == AlertDialog._build_combined_text(
            alert, settings
        )

    def test_contains_expected_sections(self) -> None:
        alert = _alert()
        payload = AlertDialog._copy_payload(alert, AppSettings())
        assert "FROST ADVISORY" in payload
        assert "WHAT...Frost" in payload
        assert "Protect tender plants" in payload
        assert "Issued:" in payload
        assert "Expires:" in payload

    def test_identical_regardless_of_display_style(self) -> None:
        alert = _alert()
        separate = AlertDialog._copy_payload(
            alert, AppSettings(alert_display_style="separate")
        )
        combined = AlertDialog._copy_payload(
            alert, AppSettings(alert_display_style="combined")
        )
        assert separate == combined

    def test_settings_none_does_not_crash(self) -> None:
        alert = _alert()
        payload = AlertDialog._copy_payload(alert, None)
        assert "FROST ADVISORY" in payload
```

### Step 1.2: Run test — verify red

```
cd C:/Users/joshu/accessiweather/.worktrees/alert-copy-button
uv run pytest tests/test_alert_dialog_copy_text.py -n 0 -v
```

Expected: `AttributeError: type object 'AlertDialog' has no attribute '_copy_payload'`.

### Step 1.3: Add `_copy_payload`

In `src/accessiweather/ui/dialogs/alert_dialog.py`, add this `@staticmethod` inside the `AlertDialog` class, immediately **after** `_build_combined_text` (around line 236):

```python
@staticmethod
def _copy_payload(alert, settings) -> str:
    """Text placed on the clipboard when the Copy button is pressed.

    Identical in both display styles (separate and combined).
    """
    return AlertDialog._build_combined_text(alert, settings)
```

### Step 1.4: Run tests — verify green

```
uv run pytest tests/test_alert_dialog_copy_text.py -n 0 -v
```

Expected: 4 passed.

### Step 1.5: Commit

```
git add tests/test_alert_dialog_copy_text.py src/accessiweather/ui/dialogs/alert_dialog.py
git commit -m "feat(alert-dialog): add _copy_payload staticmethod for clipboard text"
```

---

## Task 2: Extract shared `_add_action_buttons` helper (behavior-preserving refactor)

**Files:**
- Modify: `src/accessiweather/ui/dialogs/alert_dialog.py`

No new tests — pure refactor. Existing dispatch / separate-mode / combined-mode tests (in `tests/test_alert_dialog_dispatch.py`) already exercise both code paths and must remain green.

### Step 2.1: Add the shared helper

In `src/accessiweather/ui/dialogs/alert_dialog.py`, add a new method on `AlertDialog` (place it after `_create_separate_ui` and before `_build_subject_text`, roughly around line 184-185):

```python
def _add_action_buttons(self, panel, main_sizer):
    """Add the right-aligned Close button to the provided sizer.

    Shared by both display modes. The button row is constructed once here
    so that future additions (e.g. a Copy button) only need one change site.
    """
    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    button_sizer.AddStretchSpacer()

    close_btn = wx.Button(panel, wx.ID_CLOSE, "&Close")
    close_btn.Bind(wx.EVT_BUTTON, self._on_close)
    button_sizer.Add(close_btn, 0)

    main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)
```

Note: label changes from `"Close"` to `"&Close"` so the Alt+C mnemonic is explicit. wx previously bound Alt+C implicitly via `wx.ID_CLOSE`; being explicit is better for screen readers.

### Step 2.2: Replace the two inline blocks

In `_create_separate_ui`, replace lines 173-181 (`# Close button` through `main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)`) with:

```python
self._add_action_buttons(panel, main_sizer)
```

In `_create_combined_ui`, replace lines 104-109 (`button_sizer = wx.BoxSizer(wx.HORIZONTAL)` through `main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)`) with the same:

```python
self._add_action_buttons(panel, main_sizer)
```

The `self._focus_target = self.subject_ctrl` / `self.combined_ctrl` assignments at the END of each UI builder stay where they are.

### Step 2.3: Run regression

```
uv run pytest tests/test_alert_dialog_dispatch.py tests/test_alert_dialog_combined_text.py tests/test_alert_dialog_copy_text.py -n 0 -v
```

Expected: same count as before (20 tests — 4 dispatch + 12 combined-text variants + 4 copy-text) all passing. If any fails, investigate before committing.

### Step 2.4: Commit

```
git add src/accessiweather/ui/dialogs/alert_dialog.py
git commit -m "refactor(alert-dialog): extract shared action-button sizer"
```

---

## Task 3: Wire the Copy button + `_on_copy` + flash feedback

**Files:**
- Modify: `src/accessiweather/ui/dialogs/alert_dialog.py`
- Create: `tests/test_alert_dialog_copy_integration.py`

### Step 3.1: Write failing tests

Create `tests/test_alert_dialog_copy_integration.py`:

```python
"""Integration tests for the Copy-to-clipboard button on AlertDialog."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
import wx

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog


@pytest.fixture(scope="module")
def wx_app():
    app = wx.GetApp() or wx.App()
    yield app


@pytest.fixture
def hidden_parent(wx_app):
    frame = wx.Frame(None)
    frame.Hide()
    yield frame
    frame.Destroy()


def _alert():
    return SimpleNamespace(
        title="t",
        description="D",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Frost Advisory",
        headline="H",
        instruction="I",
        areas=[],
        references=[],
        sent=datetime(2026, 4, 18, 14, 10),
        expires=datetime(2026, 4, 18, 22, 15),
    )


def _read_clipboard_text() -> str:
    assert wx.TheClipboard.Open(), "test could not open clipboard"
    try:
        data = wx.TextDataObject()
        ok = wx.TheClipboard.GetData(data)
        return data.GetText() if ok else ""
    finally:
        wx.TheClipboard.Close()


class TestCopyButton:
    def test_copy_button_exists_in_separate_mode(self, hidden_parent):
        settings = AppSettings(alert_display_style="separate")
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            assert hasattr(dlg, "copy_btn")
            assert dlg.copy_btn.GetId() == wx.ID_COPY
            assert dlg.copy_btn.GetLabel() == "Cop&y to clipboard"
        finally:
            dlg.Destroy()

    def test_copy_button_exists_in_combined_mode(self, hidden_parent):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            assert hasattr(dlg, "copy_btn")
            assert dlg.copy_btn.GetId() == wx.ID_COPY
        finally:
            dlg.Destroy()

    def test_copy_writes_combined_text_to_clipboard(self, hidden_parent):
        settings = AppSettings(alert_display_style="separate")
        alert = _alert()
        dlg = AlertDialog(hidden_parent, alert, settings)
        try:
            dlg._on_copy(None)
            assert _read_clipboard_text() == AlertDialog._copy_payload(alert, settings)
        finally:
            dlg.Destroy()

    def test_copy_flashes_copied_label(self, hidden_parent):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            dlg._on_copy(None)
            assert dlg.copy_btn.GetLabel() == "Copied!"
        finally:
            dlg.Destroy()

    def test_copy_failure_path_flashes_copy_failed(self, hidden_parent, monkeypatch):
        settings = AppSettings()
        dlg = AlertDialog(hidden_parent, _alert(), settings)
        try:
            monkeypatch.setattr(wx.TheClipboard, "Open", lambda: False)
            # Should NOT raise.
            dlg._on_copy(None)
            assert dlg.copy_btn.GetLabel() == "Copy failed"
        finally:
            dlg.Destroy()
```

### Step 3.2: Run tests — verify red

```
uv run pytest tests/test_alert_dialog_copy_integration.py -n 0 -v
```

Expected: 5 tests fail — `copy_btn` doesn't exist yet, `_on_copy` doesn't exist yet.

### Step 3.3: Modify `_add_action_buttons` to add Copy first

Replace the `_add_action_buttons` body (added in Task 2) with:

```python
def _add_action_buttons(self, panel, main_sizer):
    """Add the right-aligned Copy + Close button row.

    Shared by both display modes.
    """
    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    button_sizer.AddStretchSpacer()

    self.copy_btn = wx.Button(panel, wx.ID_COPY, "Cop&y to clipboard")
    self.copy_btn.SetName("Copy alert text to clipboard")
    self.copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
    button_sizer.Add(self.copy_btn, 0, wx.RIGHT, 10)

    close_btn = wx.Button(panel, wx.ID_CLOSE, "&Close")
    close_btn.Bind(wx.EVT_BUTTON, self._on_close)
    button_sizer.Add(close_btn, 0)

    main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)
```

### Step 3.4: Add `_on_copy`, `_flash_button`, `_revert_button_label`

Add these three methods on `AlertDialog`, placing them together next to `_on_close` (near the bottom of the class, after `_on_key` / `_on_close`):

```python
def _on_copy(self, event):
    """Copy the alert text to the system clipboard with visible feedback."""
    text = self._copy_payload(self.alert, self.settings)
    if not wx.TheClipboard.Open():
        logger.warning("Alert copy: could not open clipboard")
        self._flash_button(self.copy_btn, "Copy failed", "Cop&y to clipboard")
        return
    try:
        wx.TheClipboard.SetData(wx.TextDataObject(text))
    finally:
        wx.TheClipboard.Close()
    self._flash_button(self.copy_btn, "Copied!", "Cop&y to clipboard")

def _flash_button(self, btn, temp_label, revert, ms=2000):
    """Temporarily replace a button label for `ms` milliseconds."""
    btn.SetLabel(temp_label)
    btn.GetParent().Layout()
    wx.CallLater(ms, self._revert_button_label, btn, revert)

def _revert_button_label(self, btn, revert):
    """Restore a button's original label. Guards against post-destroy firings."""
    if btn:
        btn.SetLabel(revert)
        btn.GetParent().Layout()
```

### Step 3.5: Run tests — verify green

```
uv run pytest tests/test_alert_dialog_copy_integration.py -n 0 -v
```

Expected: 5 passed.

### Step 3.6: Run broader regression

```
uv run pytest tests/ -n 0 -q -k "alert or settings or config" 2>&1 | tail -5
```

Expected: baseline (whatever it was after merge into dev) + 9 new tests (4 from Task 1 + 5 from Task 3) all passing.

### Step 3.7: Commit

```
git add tests/test_alert_dialog_copy_integration.py src/accessiweather/ui/dialogs/alert_dialog.py
git commit -m "feat(alert-dialog): add Copy to clipboard button with flash feedback"
```

---

## Task 4: Changelog + full regression + push + PR

### Step 4.1: CHANGELOG entry

Read `CHANGELOG.md`. Find the current "Unreleased" / upcoming section. Append one bullet under its "Added" subsection (or at the top of the list if there is no subsection structure):

```markdown
- You can now grab the whole alert — headline, details, instructions, timestamps — in one click with the new **Copy to clipboard** button in the alert dialog. Works the same whether you use separate fields or the combined view.
```

Match the file's existing voice (conversational, user-focused, no hedging, no emojis).

### Step 4.2: Full pytest

```
uv run pytest -n auto -q --tb=short 2>&1 | tail -20
```

Expected: all tests pass, or only the already-documented-on-dev pre-existing failures (Windows toast / portable-API-key plumbing). If anything NEW fails, investigate before moving on.

### Step 4.3: Lint + format

```
uv run ruff check --fix .
uv run ruff format .
```

Expected: clean. Stage + commit any auto-fixes under `chore: apply ruff fixes`.

### Step 4.4: Pyright sanity

```
uv run pyright 2>&1 | tail -20
```

Count errors in OUR new/changed code (alert_dialog.py Copy additions, two new test files). Expected: zero. Ignore pre-existing wx-typing and cross-worktree-path noise.

### Step 4.5: Commit CHANGELOG

```
git add CHANGELOG.md
git commit -m "docs(changelog): Copy to clipboard button on alert dialog"
```

### Step 4.6: Manual eyeball block (for the user)

Do NOT launch the app yourself. Present this checklist:

```
## Manual eyeball checklist (user to run)

1. Launch: `uv run accessiweather`
   - If you suspect stale install, first: `uv sync --reinstall-package accessiweather`
2. Open any active alert in the default (separate-fields) mode.
   - Confirm a "Cop&y to clipboard" button sits to the LEFT of the Close button.
   - Click it. Confirm label briefly changes to "Copied!" then reverts.
   - Paste into Notepad. Confirm you get the whole alert in one block.
3. Switch to Settings > Display > Alert display style = "Single combined view". Save.
4. Reopen an active alert.
   - Confirm the same Copy button is present.
   - Click, paste into Notepad.
   - Confirm the pasted text is IDENTICAL to what you pasted in step 2.
5. (Optional) Hold the clipboard busy in another app (e.g. open Word's clipboard pane and keep copying there), then click Copy.
   - Confirm the button briefly shows "Copy failed".
   - Confirm the app does NOT crash.
```

### Step 4.7: Push + open PR

```
git push -u origin feature/alert-copy-button
gh pr create --base dev --head feature/alert-copy-button \
  --title "feat(alerts): Copy to clipboard button on alert dialog" \
  --body "..."
```

PR body template (adapt if needed):

```
## Summary

- New **Copy to clipboard** button in the alert dialog, present in both display styles.
- Copied text is identical in separate and combined modes — headline, description, instructions, Issued/Expires — via the existing `_build_combined_text` helper.
- Button label flashes "Copied!" for 2 s on success, "Copy failed" if another app holds the clipboard.
- Refactored the per-mode close-button sizer into a shared `_add_action_buttons` helper.

Design and plan under `docs/plans/2026-04-18-alert-copy-button-*.md`.

## Verification

- [x] pytest: feature's new tests (9) all pass; broader alert/settings/config filter unchanged.
- [x] ruff check + format: clean.
- [x] pyright: zero errors in new/changed code.

## Test plan

See manual eyeball checklist in the plan doc.
```

---

## Done checklist

- [ ] Task 1: `_copy_payload` staticmethod + 4 pure tests committed
- [ ] Task 2: `_add_action_buttons` extracted (behavior-preserving) committed
- [ ] Task 3: Copy button + `_on_copy` + flash + 5 integration tests committed
- [ ] Task 4: CHANGELOG + full pytest/ruff/pyright green + PR opened against dev

## Notes for the executing engineer

- The worktree's `CLAUDE.md` says `briefcase dev` and mentions Toga. Both are stale. The app runs via `uv run accessiweather` and uses wxPython. Ignore the Toga sections.
- Per user's standing rule: never launch/kill the app yourself. The eyeball step is for the user.
- Windows bash: prefix `git` with `--no-pager` before any subcommand that might page (`log`, `diff`, `show`).
- `wx.TheClipboard` is a process-global singleton; tests that monkeypatch it must restore (pytest's `monkeypatch` fixture handles this automatically).
