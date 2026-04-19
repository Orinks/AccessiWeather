# Combined Alert View + Configurable Date Format — Design

**Date:** 2026-04-18
**Status:** Approved, ready for implementation
**Scope:** Add an opt-in "single combined view" mode for the Alert dialog, plus a new app-wide `date_format` preset used (for now) only by the new view.

---

## Problem

The Alert dialog currently presents alert content in four separate read-only `wx.TextCtrl` fields: Subject, Alert Info (severity/urgency/certainty), Details, Instructions. Some users prefer to read the entire alert as one block of text — roughly how NWS issues it — with a single close button.

Separately, there is no user-facing date format preference. The existing `time_format_12hour` bool covers time style but not date style.

## Goals

1. Let users pick between the current "separate fields" layout (default) and a new "single combined view" layout via a Settings preference.
2. Introduce a new `date_format` preset setting (`iso` / `us_short` / `us_long` / `eu`).
3. Use the new date format in the combined view's `Issued:` / `Expires:` lines.
4. Land a shared `format_date` / `format_datetime` helper in `display/presentation/formatters.py` so future call sites can adopt it without duplication.

## Non-goals

- No in-dialog toggle button — Settings preference only.
- No mass rollout of the new date format to other presenters in this PR. Other call sites opt in later.
- No new severity/urgency/certainty surfacing in the combined view (matches the user-supplied example).

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Mode toggle | Settings preference (`wx.Choice`) | Consistent with other settings; one-time choice |
| Date format scope | New setting, wired into combined view only for now | Small, focused PR; helper ready for later adoption |
| Date format UI | `wx.Choice` with 4 presets | Matches existing setting conventions (no RadioBox) |
| Date format helper | New in `formatters.py` | Central module already exists |
| Settings injection into dialog | Explicit argument | Testable without globals |
| Severity/urgency/certainty | Omitted from combined view | Matches example; user-approved |
| Issued/Expires | Included in combined view | User-requested; skipped on missing or unparseable |

---

## Section 1 — Settings

**Model** — `src/accessiweather/models/config.py`, `AppSettings`:

```python
alert_display_style: str = "separate"   # "separate" | "combined"
date_format: str = "iso"                # "iso" | "us_short" | "us_long" | "eu"
```

Both added to `to_dict()` and `from_dict()`. `from_dict` falls back to the defaults on unknown strings so a hand-edited JSON file cannot crash startup.

**Settings UI** — `src/accessiweather/ui/dialogs/settings_tabs/display.py`:

Two new `wx.StaticText` + `wx.Choice` pairs (matching existing conventions; no RadioBox):

- **Alert display style:** `Separate fields (default)` / `Single combined view`
- **Date format:** `ISO (2026-04-18)` / `US short (04/18/2026)` / `US long (April 18, 2026)` / `EU (18/04/2026)`

Accessible-label pairing comes from the adjacent `wx.StaticText`. Values load/save via the existing populate/collect pattern used by `time_format_12hour`.

## Section 2 — Formatter helpers

`src/accessiweather/display/presentation/formatters.py`:

```python
_DATE_FORMATS = {
    "iso":      "%Y-%m-%d",
    "us_short": "%m/%d/%Y",
    "us_long":  "%B %d, %Y",
    "eu":       "%d/%m/%Y",
}

def format_date(dt: datetime | None, style: str) -> str:
    if dt is None:
        return ""
    return dt.strftime(_DATE_FORMATS.get(style, _DATE_FORMATS["iso"]))

def format_datetime(dt: datetime | None, date_style: str, time_12hour: bool) -> str:
    if dt is None:
        return ""
    date_part = format_date(dt, date_style)
    time_fmt = "%I:%M %p" if time_12hour else "%H:%M"
    time_part = dt.strftime(time_fmt).lstrip("0")
    return f"{date_part} {time_part}"
```

Pure functions. Caller passes already-known settings strings. Unknown style keys fall back to ISO silently. `None` → `""`. String-to-`datetime` parsing is the caller's responsibility.

## Section 3 — Alert dialog

`src/accessiweather/ui/dialogs/alert_dialog.py`:

**Signature change:** `show_alert_dialog(parent, alert, settings=None)` and `AlertDialog(parent, alert, settings=None)`. Updates the one existing caller (main window) to pass settings. `None` falls back to defaults.

**Dispatch** in `_create_ui`:

```python
if self.settings and self.settings.alert_display_style == "combined":
    self._create_combined_ui(panel, main_sizer)
else:
    self._create_separate_ui(panel, main_sizer)   # existing code, extracted
```

**Combined UI** — one `wx.StaticText` labelled `"Alert:"`, one multiline read-only `wx.TextCtrl` filling the panel, one `Close` button. TextCtrl gets initial focus. Escape/close behavior unchanged.

**Text assembly** — `@staticmethod _build_combined_text(alert, settings) -> str`:

```
{headline or event}

{description verbatim}

{instruction, if present}

Issued: {format_datetime(sent, date_format, time_12hour)}
Expires: {format_datetime(expires, date_format, time_12hour)}
```

- Blank lines separate blocks.
- Missing fields are omitted entirely.
- `sent` / `expires` parsed with `datetime.fromisoformat()`; on failure, the line is skipped, no exception.

**Separate UI** — current `_create_ui` body moved verbatim into `_create_separate_ui`. No behavior change for existing users.

## Section 4 — Testing (TDD)

Red-green-refactor, four files, in this order:

1. **`tests/test_formatters_date.py`** — pure.
   - Each preset renders expected string for fixed datetime.
   - Unknown style → ISO fallback.
   - `None` → `""`.
   - `format_datetime` 12h vs 24h.
   - Hypothesis over datetimes × style keys: no crashes.

2. **`tests/test_config_alert_display.py`** — settings round-trip.
   - Defaults correct.
   - `to_dict` / `from_dict` round-trip.
   - Bogus values fall back to defaults.

3. **`tests/test_alert_dialog_combined_text.py`** — pure string assembly.
   - All fields → expected block order.
   - Missing instruction → block absent, no stray blanks.
   - Missing expires → line absent, Issued still present.
   - Unparseable ISO string → line skipped, no exception.
   - `us_long` + 12h → `"Issued: April 18, 2026 2:05 PM"`.

4. **`tests/test_alert_dialog_dispatch.py`** — wx dispatch.
   - `"combined"` → `combined_ctrl` attribute, no `subject_ctrl`.
   - `"separate"` / `None` → opposite.
   - Matches existing wx test fixture patterns.

**Verification:**
- `pytest -n auto`
- `ruff check --fix . && ruff format .`
- `pyright`
- Launch the app (`uv run accessiweather`) and eyeball both modes.

---

## Rollout / future work

- `format_date` / `format_datetime` are available for other presenters; they opt in as they're touched.
- If users later want a custom strftime string, add a fifth preset key `"custom"` with a paired text field — additive, non-breaking.
