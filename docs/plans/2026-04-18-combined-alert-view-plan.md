# Combined Alert View + Date Format — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an opt-in "single combined view" mode for the Alert dialog plus a new `date_format` preset setting (wired only into the new combined view for now).

**Architecture:** Two new fields on `AppSettings` (`alert_display_style`, `date_format`), two new `wx.Choice` controls on the Display settings tab, two new pure helpers in `display/presentation/formatters.py`, and a branched UI in `AlertDialog` (separate = current layout, combined = one TextCtrl). Settings are injected into the dialog for testability.

**Tech Stack:** Python 3.10+, wxPython, pytest + Hypothesis. Run the app with `uv run accessiweather` (NOT `briefcase dev` — the worktree CLAUDE.md is stale).

**Design doc:** [docs/plans/2026-04-18-combined-alert-view-design.md](2026-04-18-combined-alert-view-design.md)

**Ground truth already verified in the codebase:**
- `WeatherAlert.sent` and `WeatherAlert.expires` are already `datetime | None` — no ISO parsing needed in the dialog.
- Existing `time_format_12hour: bool` in `AppSettings` is what the new `format_datetime` helper pairs with.
- `show_alert_dialog` is called from 3 sites: `app.py:51`, `main_window.py:1558`, `main_window.py:1570`. Settings are reachable via `self.app.config_manager.get_settings()` at the UI call sites.

---

## Task 1: Formatter helpers + unit tests

**Files:**
- Create: `tests/test_formatters_date.py`
- Modify: `src/accessiweather/display/presentation/formatters.py` (add near top, after existing imports)

### Step 1.1: Write failing tests

Create `tests/test_formatters_date.py`:

```python
"""Tests for date/datetime format helpers."""

from __future__ import annotations

from datetime import datetime

import pytest
from hypothesis import given, strategies as st

from accessiweather.display.presentation.formatters import (
    format_date,
    format_datetime,
)


FIXED_DT = datetime(2026, 4, 18, 14, 5)  # 2:05 PM / 14:05


class TestFormatDate:
    @pytest.mark.parametrize(
        "style, expected",
        [
            ("iso", "2026-04-18"),
            ("us_short", "04/18/2026"),
            ("us_long", "April 18, 2026"),
            ("eu", "18/04/2026"),
        ],
    )
    def test_each_preset(self, style: str, expected: str) -> None:
        assert format_date(FIXED_DT, style) == expected

    def test_unknown_style_falls_back_to_iso(self) -> None:
        assert format_date(FIXED_DT, "not-a-real-style") == "2026-04-18"

    def test_none_returns_empty_string(self) -> None:
        assert format_date(None, "iso") == ""

    @given(
        st.datetimes(
            min_value=datetime(1900, 1, 1),
            max_value=datetime(2100, 12, 31),
        ),
        st.sampled_from(["iso", "us_short", "us_long", "eu", "bogus"]),
    )
    def test_never_crashes(self, dt: datetime, style: str) -> None:
        result = format_date(dt, style)
        assert isinstance(result, str)
        assert result  # non-empty for any real datetime


class TestFormatDatetime:
    def test_us_long_12hour(self) -> None:
        assert format_datetime(FIXED_DT, "us_long", True) == "April 18, 2026 2:05 PM"

    def test_iso_24hour(self) -> None:
        assert format_datetime(FIXED_DT, "iso", False) == "2026-04-18 14:05"

    def test_us_short_24hour(self) -> None:
        assert format_datetime(FIXED_DT, "us_short", False) == "04/18/2026 14:05"

    def test_morning_12hour_strips_leading_zero(self) -> None:
        morning = datetime(2026, 4, 18, 9, 7)
        assert format_datetime(morning, "iso", True) == "2026-04-18 9:07 AM"

    def test_none_returns_empty_string(self) -> None:
        assert format_datetime(None, "iso", True) == ""
```

### Step 1.2: Run test — verify red

Run:
```
cd .worktrees/combined-alert-view
uv run pytest tests/test_formatters_date.py -n 0 -v
```
Expected: collection error / ImportError (`format_date` / `format_datetime` don't exist yet).

### Step 1.3: Add helpers to formatters.py

In `src/accessiweather/display/presentation/formatters.py`, immediately after the existing imports (after line 18), add:

```python
_DATE_FORMATS = {
    "iso": "%Y-%m-%d",
    "us_short": "%m/%d/%Y",
    "us_long": "%B %d, %Y",
    "eu": "%d/%m/%Y",
}


def format_date(dt: datetime | None, style: str) -> str:
    """Format a date using a preset style key; unknown keys fall back to ISO."""
    if dt is None:
        return ""
    fmt = _DATE_FORMATS.get(style, _DATE_FORMATS["iso"])
    return dt.strftime(fmt)


def format_datetime(dt: datetime | None, date_style: str, time_12hour: bool) -> str:
    """Format a full datetime as "<date> <time>"; 12h output strips leading zero."""
    if dt is None:
        return ""
    date_part = format_date(dt, date_style)
    time_fmt = "%I:%M %p" if time_12hour else "%H:%M"
    time_part = dt.strftime(time_fmt).lstrip("0")
    return f"{date_part} {time_part}"
```

### Step 1.4: Run test — verify green

Run:
```
uv run pytest tests/test_formatters_date.py -n 0 -v
```
Expected: all tests pass.

### Step 1.5: Commit

```
git add tests/test_formatters_date.py src/accessiweather/display/presentation/formatters.py
git commit -m "feat(formatters): add format_date and format_datetime helpers"
```

---

## Task 2: Settings model — new fields

**Files:**
- Modify: `src/accessiweather/models/config.py` (add fields + serialization)
- Create: `tests/test_config_alert_display.py`

### Step 2.1: Write failing tests

Create `tests/test_config_alert_display.py`:

```python
"""Tests for alert display + date format settings round-trip."""

from __future__ import annotations

from accessiweather.models.config import AppSettings


class TestDefaults:
    def test_alert_display_style_defaults_to_separate(self) -> None:
        assert AppSettings().alert_display_style == "separate"

    def test_date_format_defaults_to_iso(self) -> None:
        assert AppSettings().date_format == "iso"


class TestRoundTrip:
    def test_to_dict_includes_new_fields(self) -> None:
        data = AppSettings().to_dict()
        assert data["alert_display_style"] == "separate"
        assert data["date_format"] == "iso"

    def test_from_dict_preserves_valid_values(self) -> None:
        settings = AppSettings.from_dict(
            {"alert_display_style": "combined", "date_format": "us_long"}
        )
        assert settings.alert_display_style == "combined"
        assert settings.date_format == "us_long"

    def test_from_dict_falls_back_on_bogus_alert_display_style(self) -> None:
        settings = AppSettings.from_dict({"alert_display_style": "bogus"})
        assert settings.alert_display_style == "separate"

    def test_from_dict_falls_back_on_bogus_date_format(self) -> None:
        settings = AppSettings.from_dict({"date_format": "not-a-format"})
        assert settings.date_format == "iso"
```

### Step 2.2: Run test — verify red

```
uv run pytest tests/test_config_alert_display.py -n 0 -v
```
Expected: `AttributeError: 'AppSettings' object has no attribute 'alert_display_style'`.

### Step 2.3: Implement

In `src/accessiweather/models/config.py`:

1. Add to the `_PERSISTED_FIELD_NAMES` set (around line 80, alongside `time_format_12hour`):

```python
"alert_display_style",
"date_format",
```

2. Add fields to the `AppSettings` dataclass, near the existing `time_format_12hour` line (currently line 169). After `show_timezone_suffix`:

```python
# Alert dialog display style
alert_display_style: str = "separate"  # "separate" | "combined"
# Date format preset for rendered dates
date_format: str = "iso"  # "iso" | "us_short" | "us_long" | "eu"
```

3. In `to_dict()` (around line 483), add alongside `time_format_12hour`:

```python
"alert_display_style": self.alert_display_style,
"date_format": self.date_format,
```

4. In `from_dict()` (around line 580), use defensive fallback. Add a helper near the top of `from_dict` (if there isn't already one for enum-like strings) OR use inline validation:

```python
_VALID_ALERT_STYLES = {"separate", "combined"}
_VALID_DATE_FORMATS = {"iso", "us_short", "us_long", "eu"}

def _enum_or_default(value, valid: set[str], default: str) -> str:
    return value if isinstance(value, str) and value in valid else default
```

Place module constants/helper near the top of the module (after imports). Then in `from_dict`:

```python
alert_display_style=_enum_or_default(
    data.get("alert_display_style"), _VALID_ALERT_STYLES, "separate"
),
date_format=_enum_or_default(
    data.get("date_format"), _VALID_DATE_FORMATS, "iso"
),
```

**Important:** check the surrounding style of other `from_dict` entries before placing — if they use `cls._as_bool` / `cls._as_int` helpers inside the class, match that pattern instead of a module-level helper. Read `config.py:560-600` to confirm the convention and match it.

### Step 2.4: Run test — verify green

```
uv run pytest tests/test_config_alert_display.py -n 0 -v
```
Expected: all 6 tests pass.

### Step 2.5: Regression check on existing settings tests

```
uv run pytest tests/test_settings_operations.py -n 0 -q
```
Expected: still 38 passing.

### Step 2.6: Commit

```
git add tests/test_config_alert_display.py src/accessiweather/models/config.py
git commit -m "feat(config): add alert_display_style and date_format settings"
```

---

## Task 3: Alert dialog — extract existing UI, accept settings

This task refactors without changing behavior, so it lands **before** adding the combined mode. Pure mechanical extraction.

**Files:**
- Modify: `src/accessiweather/ui/dialogs/alert_dialog.py`
- Modify: `src/accessiweather/app.py:47-51`
- Modify: `src/accessiweather/ui/main_window.py:1558` and `:1570`

### Step 3.1: Add settings parameter, extract separate UI

In `src/accessiweather/ui/dialogs/alert_dialog.py`:

1. Change signature of `show_alert_dialog`:
```python
def show_alert_dialog(parent, alert, settings=None) -> None:
    ...
    dlg = AlertDialog(parent_ctrl, alert, settings)
```

2. Change `AlertDialog.__init__` to accept `settings=None` and store `self.settings = settings`.

3. Rename current `_create_ui` body to `_create_separate_ui(self, panel, main_sizer)`. Change the method so it receives `panel` and `main_sizer` rather than creating them. Keep all existing logic — close button, focus, etc. — inside it.

4. New `_create_ui`:
```python
def _create_ui(self):
    panel = wx.Panel(self)
    main_sizer = wx.BoxSizer(wx.VERTICAL)
    self._create_separate_ui(panel, main_sizer)
    panel.SetSizer(main_sizer)
```

(Leaves a minimal shim that the combined path will piggyback on in Task 4.)

### Step 3.2: Update call sites

- `src/accessiweather/app.py:47-51`:
```python
def show_alert_dialog(parent, alert, settings=None) -> None:
    from .ui.dialogs import show_alert_dialog as _show_alert_dialog
    _show_alert_dialog(parent, alert, settings)
```
At `app.py:282`, pass `self.config_manager.get_settings()`:
```python
show_alert_dialog(self.main_window, alerts[0], self.config_manager.get_settings())
```

- `src/accessiweather/ui/main_window.py:1558` and `:1570`: replace both `show_alert_dialog(self, alert)` with:
```python
show_alert_dialog(self, alert, self.app.config_manager.get_settings())
```

### Step 3.3: Regression check

```
uv run pytest tests/ -n 0 -q -k "alert or settings"
```
Expected: existing alert-related and settings-related tests still pass. No behavior change yet.

### Step 3.4: Commit

```
git add src/accessiweather/ui/dialogs/alert_dialog.py src/accessiweather/app.py src/accessiweather/ui/main_window.py
git commit -m "refactor(alert-dialog): accept settings and extract separate-mode UI"
```

---

## Task 4: Combined text builder (pure string)

**Files:**
- Modify: `src/accessiweather/ui/dialogs/alert_dialog.py` (add static method)
- Create: `tests/test_alert_dialog_combined_text.py`

### Step 4.1: Write failing tests

Create `tests/test_alert_dialog_combined_text.py`:

```python
"""Tests for AlertDialog._build_combined_text (pure string assembly)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog


def _alert(**kwargs):
    defaults = {
        "headline": None,
        "event": None,
        "description": None,
        "instruction": None,
        "sent": None,
        "expires": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _settings(**kwargs):
    return AppSettings(**kwargs)


class TestBuildCombinedText:
    def test_all_fields_present_in_order(self) -> None:
        alert = _alert(
            headline="FROST ADVISORY IN EFFECT FROM 2 AM TO 10 AM",
            description="WHAT...Frost.\nWHERE...Michigan.",
            instruction="Protect tender plants.",
            sent=datetime(2026, 4, 18, 14, 10),
            expires=datetime(2026, 4, 18, 22, 15),
        )
        text = AlertDialog._build_combined_text(alert, _settings())

        # Order: headline, blank, description, blank, instruction, blank, issued, expires
        headline_i = text.index("FROST ADVISORY")
        desc_i = text.index("WHAT...Frost")
        instr_i = text.index("Protect tender plants")
        issued_i = text.index("Issued:")
        expires_i = text.index("Expires:")
        assert headline_i < desc_i < instr_i < issued_i < expires_i

    def test_falls_back_to_event_when_no_headline(self) -> None:
        alert = _alert(event="Frost Advisory")
        text = AlertDialog._build_combined_text(alert, _settings())
        assert text.startswith("Frost Advisory")

    def test_missing_instruction_omitted(self) -> None:
        alert = _alert(
            headline="H", description="D",
            sent=datetime(2026, 4, 18, 14, 10),
            expires=datetime(2026, 4, 18, 22, 15),
        )
        text = AlertDialog._build_combined_text(alert, _settings())
        assert "Issued:" in text
        # No stray "None" or blank-block collapses expected
        assert "None" not in text

    def test_missing_expires_line_absent(self) -> None:
        alert = _alert(
            headline="H",
            sent=datetime(2026, 4, 18, 14, 10),
        )
        text = AlertDialog._build_combined_text(alert, _settings())
        assert "Issued:" in text
        assert "Expires:" not in text

    def test_missing_sent_line_absent(self) -> None:
        alert = _alert(headline="H", expires=datetime(2026, 4, 18, 22, 15))
        text = AlertDialog._build_combined_text(alert, _settings())
        assert "Issued:" not in text
        assert "Expires:" in text

    def test_date_format_and_12hour_applied(self) -> None:
        alert = _alert(
            headline="H", sent=datetime(2026, 4, 18, 14, 5),
        )
        settings = _settings(date_format="us_long", time_format_12hour=True)
        text = AlertDialog._build_combined_text(alert, settings)
        assert "Issued: April 18, 2026 2:05 PM" in text

    def test_empty_description_does_not_add_blank_block(self) -> None:
        alert = _alert(headline="H")
        text = AlertDialog._build_combined_text(alert, _settings())
        # No triple-newlines
        assert "\n\n\n" not in text

    def test_fallback_headline_when_nothing_given(self) -> None:
        alert = _alert()
        text = AlertDialog._build_combined_text(alert, _settings())
        assert text.startswith("Weather Alert")
```

### Step 4.2: Run test — verify red

```
uv run pytest tests/test_alert_dialog_combined_text.py -n 0 -v
```
Expected: `AttributeError: type object 'AlertDialog' has no attribute '_build_combined_text'`.

### Step 4.3: Implement the builder

In `src/accessiweather/ui/dialogs/alert_dialog.py`, add inside the `AlertDialog` class:

```python
@staticmethod
def _build_combined_text(alert, settings) -> str:
    """Assemble the combined-view text block. Pure function; settings is AppSettings-like."""
    from ...display.presentation.formatters import format_datetime

    date_style = getattr(settings, "date_format", "iso")
    time_12h = getattr(settings, "time_format_12hour", True)

    blocks: list[str] = []

    headline = (
        getattr(alert, "headline", None)
        or getattr(alert, "event", None)
        or "Weather Alert"
    )
    blocks.append(headline)

    description = getattr(alert, "description", None)
    if description:
        blocks.append(description)

    instruction = getattr(alert, "instruction", None)
    if instruction:
        blocks.append(instruction)

    times: list[str] = []
    sent = getattr(alert, "sent", None)
    if sent is not None:
        times.append(f"Issued: {format_datetime(sent, date_style, time_12h)}")
    expires = getattr(alert, "expires", None)
    if expires is not None:
        times.append(f"Expires: {format_datetime(expires, date_style, time_12h)}")
    if times:
        blocks.append("\n".join(times))

    return "\n\n".join(blocks)
```

### Step 4.4: Run test — verify green

```
uv run pytest tests/test_alert_dialog_combined_text.py -n 0 -v
```
Expected: all 8 tests pass.

### Step 4.5: Commit

```
git add tests/test_alert_dialog_combined_text.py src/accessiweather/ui/dialogs/alert_dialog.py
git commit -m "feat(alert-dialog): add combined-view text builder"
```

---

## Task 5: Wire combined-mode UI into the dialog

**Files:**
- Modify: `src/accessiweather/ui/dialogs/alert_dialog.py`
- Create: `tests/test_alert_dialog_dispatch.py`

### Step 5.1: Write failing tests

Create `tests/test_alert_dialog_dispatch.py`:

```python
"""Tests for AlertDialog mode dispatch and control creation."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
import wx

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog


@pytest.fixture(scope="module")
def wx_app():
    app = wx.App()
    yield app
    app.Destroy()


def _alert():
    return SimpleNamespace(
        title="t", description="D", severity="Moderate", urgency="Expected",
        certainty="Likely", event="Frost Advisory", headline="H",
        instruction="I", areas=[], references=[],
        sent=datetime(2026, 4, 18, 14, 10),
        expires=datetime(2026, 4, 18, 22, 15),
    )


class TestDispatch:
    def test_separate_mode_creates_subject_ctrl(self, wx_app):
        settings = AppSettings(alert_display_style="separate")
        dlg = AlertDialog(None, _alert(), settings)
        try:
            assert hasattr(dlg, "subject_ctrl")
            assert not hasattr(dlg, "combined_ctrl")
        finally:
            dlg.Destroy()

    def test_combined_mode_creates_combined_ctrl(self, wx_app):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(None, _alert(), settings)
        try:
            assert hasattr(dlg, "combined_ctrl")
            assert not hasattr(dlg, "subject_ctrl")
        finally:
            dlg.Destroy()

    def test_none_settings_defaults_to_separate(self, wx_app):
        dlg = AlertDialog(None, _alert(), None)
        try:
            assert hasattr(dlg, "subject_ctrl")
            assert not hasattr(dlg, "combined_ctrl")
        finally:
            dlg.Destroy()

    def test_combined_mode_textctrl_contains_headline(self, wx_app):
        settings = AppSettings(alert_display_style="combined")
        dlg = AlertDialog(None, _alert(), settings)
        try:
            assert "H" in dlg.combined_ctrl.GetValue()
            assert "Issued:" in dlg.combined_ctrl.GetValue()
        finally:
            dlg.Destroy()
```

### Step 5.2: Run — verify red

```
uv run pytest tests/test_alert_dialog_dispatch.py -n 0 -v
```
Expected: the combined-mode test fails (`combined_ctrl` missing).

### Step 5.3: Implement `_create_combined_ui` + dispatch

In `src/accessiweather/ui/dialogs/alert_dialog.py`, modify `_create_ui` to dispatch:

```python
def _create_ui(self):
    panel = wx.Panel(self)
    main_sizer = wx.BoxSizer(wx.VERTICAL)

    style = getattr(self.settings, "alert_display_style", "separate") if self.settings else "separate"
    if style == "combined":
        self._create_combined_ui(panel, main_sizer)
    else:
        self._create_separate_ui(panel, main_sizer)

    panel.SetSizer(main_sizer)
```

Add `_create_combined_ui`:

```python
def _create_combined_ui(self, panel, main_sizer):
    """Create a single TextCtrl containing the full alert, with a Close button."""
    label = wx.StaticText(panel, label="Alert:")
    label.SetFont(label.GetFont().Bold())
    main_sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)

    text = self._build_combined_text(self.alert, self.settings)
    self.combined_ctrl = wx.TextCtrl(
        panel,
        value=text,
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
    )
    main_sizer.Add(
        self.combined_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15
    )

    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    button_sizer.AddStretchSpacer()
    close_btn = wx.Button(panel, wx.ID_CLOSE, "Close")
    close_btn.Bind(wx.EVT_BUTTON, self._on_close)
    button_sizer.Add(close_btn, 0)
    main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 15)

    self.combined_ctrl.SetFocus()
```

Update `_setup_accessibility` to also name the combined control when present (per the user's rule, SetName alone is not sufficient — but the adjacent `"Alert:"` StaticText provides the screen-reader label; SetName is a harmless additional hint):

```python
def _setup_accessibility(self):
    if hasattr(self, "subject_ctrl"):
        self.subject_ctrl.SetName("Subject with alert headline")
    if hasattr(self, "info_ctrl"):
        self.info_ctrl.SetName("Alert information with severity, urgency, and certainty")
    if hasattr(self, "details_ctrl"):
        self.details_ctrl.SetName("Alert details")
    if hasattr(self, "instr_ctrl"):
        self.instr_ctrl.SetName("Instructions")
    if hasattr(self, "combined_ctrl"):
        self.combined_ctrl.SetName("Full alert text")
```

### Step 5.4: Run — verify green

```
uv run pytest tests/test_alert_dialog_dispatch.py tests/test_alert_dialog_combined_text.py -n 0 -v
```
Expected: all pass.

### Step 5.5: Commit

```
git add tests/test_alert_dialog_dispatch.py src/accessiweather/ui/dialogs/alert_dialog.py
git commit -m "feat(alert-dialog): add combined display mode"
```

---

## Task 6: Settings UI — add the two Choices

**Files:**
- Modify: `src/accessiweather/ui/dialogs/settings_tabs/display.py`

No new test file — the existing pattern (`_TIME_MODE_MAP` etc.) is mature; we follow it exactly. Settings round-trip is already covered by Task 2.

### Step 6.1: Add the preset maps

At the top of `display.py` near the other `_*_MAP` / `_*_VALUES` constants, add:

```python
_ALERT_DISPLAY_MAP = {"separate": 0, "combined": 1}
_ALERT_DISPLAY_VALUES = ["separate", "combined"]
_ALERT_DISPLAY_CHOICES = ["Separate fields (default)", "Single combined view"]

_DATE_FORMAT_MAP = {"iso": 0, "us_short": 1, "us_long": 2, "eu": 3}
_DATE_FORMAT_VALUES = ["iso", "us_short", "us_long", "eu"]
_DATE_FORMAT_CHOICES = [
    "ISO (2026-04-18)",
    "US short (04/18/2026)",
    "US long (April 18, 2026)",
    "EU (18/04/2026)",
]
```

### Step 6.2: Add the two controls

Inside `build()` (the method that creates controls), after the `time_format_12hour` block (around line 179 — i.e. after the CheckBox's `time_section.Add`), add a **Date format** row in the same `time_section`:

```python
controls["date_format"] = self.dialog.add_labeled_control_row(
    panel,
    time_section,
    "Date format:",
    lambda parent: wx.Choice(parent, choices=_DATE_FORMAT_CHOICES),
)
```

Create the alert display style in an appropriate section — NOT the `time_section`. Look for an "Alerts" section in the file; if none exists, add the control to the end of the existing `time_section` is acceptable but semantically it belongs with alert-related settings. Before placing, grep the file for existing sections and choose the one that best fits. If unsure, add a new small section near the end of the Display tab:

```python
alert_display_section = self.dialog.create_section(
    panel,
    sizer,
    "Alert display",
    "Choose how weather alerts are shown when you open one.",
)
controls["alert_display_style"] = self.dialog.add_labeled_control_row(
    panel,
    alert_display_section,
    "Alert display style:",
    lambda parent: wx.Choice(parent, choices=_ALERT_DISPLAY_CHOICES),
)
```

### Step 6.3: Load in `load()`

In `load()` (around line 255, near `time_format_12hour`), add:

```python
date_format = getattr(settings, "date_format", "iso")
controls["date_format"].SetSelection(_DATE_FORMAT_MAP.get(date_format, 0))

alert_display = getattr(settings, "alert_display_style", "separate")
controls["alert_display_style"].SetSelection(_ALERT_DISPLAY_MAP.get(alert_display, 0))
```

### Step 6.4: Save in `save()`

In `save()`'s dict (around line 285), add:

```python
"date_format": _DATE_FORMAT_VALUES[controls["date_format"].GetSelection()],
"alert_display_style": _ALERT_DISPLAY_VALUES[controls["alert_display_style"].GetSelection()],
```

### Step 6.5: Accessibility names

In `setup_accessibility()` (around line 300), add to the `names` dict:

```python
"date_format": "Date format",
"alert_display_style": "Alert display style",
```

### Step 6.6: Run broader regression

```
uv run pytest tests/ -n 0 -q -k "settings or config or alert"
```
Expected: all related tests pass.

### Step 6.7: Commit

```
git add src/accessiweather/ui/dialogs/settings_tabs/display.py
git commit -m "feat(settings): add Alert display style and Date format controls"
```

---

## Task 7: Changelog + full regression + manual eyeball

### Step 7.1: Add CHANGELOG entry

Edit `CHANGELOG.md`, add under the current Unreleased / upcoming section (match the existing style — conversational, user-focused, no hedging):

```markdown
- New alert display option: pick **Single combined view** in Settings → Display to read the whole alert — headline, details, instructions, and timestamps — in one scrollable edit box with a Close button. The original separate-fields layout stays the default.
- You can now choose how dates are shown: **ISO (2026-04-18)**, **US short (04/18/2026)**, **US long (April 18, 2026)**, or **EU (18/04/2026)**. Applies to timestamps in the new combined alert view for now.
```

### Step 7.2: Full test run

```
uv run pytest -n auto -q --tb=short
```
Expected: all tests pass. If anything unrelated fails, investigate — do **not** mark the task complete until green.

### Step 7.3: Lint + type check

```
uv run ruff check --fix .
uv run ruff format .
uv run pyright 2>&1 | tail -30
```
Expected: clean. Fix anything reported.

### Step 7.4: Manual eyeball

**Note to executing engineer:** per the user's standing rule, do **not** kill/relaunch the AccessiWeather process yourself. Ask the user to launch `uv run accessiweather` and verify manually:
- Open Settings → Display → confirm both new controls render with expected labels and choices.
- Pick `Single combined view`, save, open an active alert: confirm single TextCtrl with headline / description / instruction / Issued / Expires and a Close button. Escape closes.
- Switch back to `Separate fields`: confirm original four-field layout is restored.
- Toggle date format presets: confirm the Issued/Expires lines reformat correctly.

If you cannot test the UI yourself, say so explicitly rather than claiming success (per project CLAUDE.md).

### Step 7.5: Commit + final summary

```
git add CHANGELOG.md
git commit -m "docs(changelog): combined alert view and date format"
```

If lint/format/pyright made any changes in step 7.3:

```
git add -u
git commit -m "chore: apply ruff/pyright fixes"
```

---

## Done checklist

- [ ] Task 1: formatter helpers + tests committed
- [ ] Task 2: settings fields + tests committed
- [ ] Task 3: dialog accepts settings, call sites updated
- [ ] Task 4: `_build_combined_text` + tests committed
- [ ] Task 5: combined-mode UI + dispatch + tests committed
- [ ] Task 6: settings UI controls committed
- [ ] Task 7: changelog + full pytest/ruff/pyright green + user eyeballed both modes
- [ ] Worktree ready for PR against `dev`
