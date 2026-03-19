# Phase 3 Plan — Extract Windows Toast Identity & Timer Management from app.py

## Phase Goal

Extract the ~390-line module-level Windows toast identity block (lines 49–441) into
`windows_toast_identity.py`, and extract timer management methods into `app_timer_manager.py`.
Reduce `app.py` from 1,693 lines to ≤1,270 lines. All existing tests stay green.

**Starting line count:** 1,693 lines
**Estimated savings:** ≥420 lines
**Projected post-phase count:** ≤1,270 lines

---

## Pre-Analysis Findings

### What to Extract — Task 1 (Toast Identity)

Module-level functions and global in `app.py` (lines 49–441):
- `set_windows_app_user_model_id` (line 49)
- `_is_unc_path` (line 70)
- `_needs_shortcut_repair` (line 76)
- `_run_powershell_json` (line 87)
- `_resolve_start_menu_shortcut_path` (line 121)
- `_toast_identity_stamp_path` (line 141)
- `_load_toast_identity_stamp` (line 145)
- `_should_repair_shortcut` (line 155)
- `_write_toast_identity_stamp` (line 175)
- `_TOAST_IDENTITY_ENSURED_THIS_STARTUP = False` (line 199)
- `ensure_windows_toast_identity` (line 202)

**Test impact:** `tests/test_windows_app_user_model_id.py` imports these from `accessiweather.app`
and monkeypatches them at `"accessiweather.app.*"` paths. After extraction:
- Update test imports to `from accessiweather.windows_toast_identity import (...)`
- Update monkeypatches to patch at `"accessiweather.windows_toast_identity.*"`
- Keep `from accessiweather.app import AccessiWeatherApp` (separate import)
- Add import forwarding in `app.py` so `from accessiweather.app import ensure_windows_toast_identity`
  still works (for callers in app.py and elsewhere)

### What to Extract — Task 2 (Timer Management)

Class methods in `AccessiWeatherApp` (lines 1240–1527):
- `_stop_auto_update_checks` (line 1240)
- `_start_auto_update_checks` (line 1257)
- `_on_auto_update_check_timer` (line 1285)
- `_stop_background_updates` (line 1481)
- `_start_background_updates` (line 1491)
- `_on_background_update` (line 1518)
- `_on_event_check_update` (line 1523)

**Pattern:** Move method bodies to module-level functions in `app_timer_manager.py` taking
`app: AccessiWeatherApp` as first parameter. Replace method bodies in app.py with one-line
delegation calls. This preserves method signatures so all existing tests remain unchanged.

### What NOT to Extract

- `_check_for_updates_on_startup` — update-check logic, not pure timer management
- `_download_and_apply_update` — download/update logic
- `update_tray_tooltip` — tray display, not timer management

---

## Pre-Flight Checks

```bash
cd /home/openclaw/projects/AccessiWeather

# 1. Confirm baseline line count
python3 -c "
with open('src/accessiweather/app.py') as f:
    print(len(f.readlines()), 'lines (baseline)')
"
# Expected: 1693

# 2. Run relevant tests baseline
python3 -m pytest tests/test_windows_app_user_model_id.py tests/test_split_update_timers.py tests/test_app_auto_update_checks.py --tb=short -q
# Must: all pass

# 3. Confirm imports work
python3 -c "from accessiweather.app import ensure_windows_toast_identity; print('OK')"
```

---

## Task 1 — Extract Windows Toast Identity Block

### Step 1a — Create `windows_toast_identity.py`

Create `src/accessiweather/windows_toast_identity.py` containing:
- All imports needed (json, logging, os, subprocess, sys, pathlib.Path)
- `from .constants import WINDOWS_APP_USER_MODEL_ID`
- All 11 module-level items moved verbatim from app.py (lines 49–441)

### Step 1b — Update `app.py`

Replace lines 49–441 (everything before `class AccessiWeatherApp`) with:
```python
from .windows_toast_identity import (
    _is_unc_path,
    _load_toast_identity_stamp,
    _needs_shortcut_repair,
    _resolve_start_menu_shortcut_path,
    _run_powershell_json,
    _should_repair_shortcut,
    _toast_identity_stamp_path,
    _write_toast_identity_stamp,
    ensure_windows_toast_identity,
    set_windows_app_user_model_id,
)
```

Remove now-redundant imports from app.py (json, os, subprocess) if only used in the extracted block.

### Step 1c — Update test file

In `tests/test_windows_app_user_model_id.py`:
- Change `from accessiweather.app import (_is_unc_path, ...)` to `from accessiweather.windows_toast_identity import (...)`
- Keep `from accessiweather.app import AccessiWeatherApp` separate
- Change all `monkeypatch.setattr("accessiweather.app.SYMBOL", ...)` to `monkeypatch.setattr("accessiweather.windows_toast_identity.SYMBOL", ...)`

### Verify Task 1:

```bash
# No dangling symbols in app.py's module-level
python3 -c "
import accessiweather.app as m
for name in ['set_windows_app_user_model_id', 'ensure_windows_toast_identity', '_is_unc_path']:
    assert hasattr(m, name), f'Missing: {name}'
print('Forward exports OK')
"

# Line count reduced
python3 -c "
with open('src/accessiweather/app.py') as f:
    print(len(f.readlines()), 'lines (after Task 1)')
"
# Expected: ~1310 lines (saved ~383 lines)

# Tests still pass
python3 -m pytest tests/test_windows_app_user_model_id.py --tb=short -q
# Must: all pass

# Ruff lint
python3 -m ruff check src/accessiweather/windows_toast_identity.py src/accessiweather/app.py
# Must: no errors
```

**Commit:**
```bash
git add src/accessiweather/windows_toast_identity.py src/accessiweather/app.py tests/test_windows_app_user_model_id.py
git commit -m "refactor: extract Windows toast identity block into windows_toast_identity.py"
```

---

## Task 2 — Extract Timer Management Methods

### Step 2a — Create `app_timer_manager.py`

Create `src/accessiweather/app_timer_manager.py` with module-level functions:

```python
"""Timer management functions for AccessiWeatherApp."""
from __future__ import annotations
import contextlib
import logging
from typing import TYPE_CHECKING
import wx
if TYPE_CHECKING:
    from .app import AccessiWeatherApp
logger = logging.getLogger(__name__)

def stop_auto_update_checks(app: AccessiWeatherApp) -> None: ...
def start_auto_update_checks(app: AccessiWeatherApp) -> None: ...
def on_auto_update_check_timer(app: AccessiWeatherApp, event) -> None: ...
def stop_background_updates(app: AccessiWeatherApp) -> None: ...
def start_background_updates(app: AccessiWeatherApp) -> None: ...
def on_background_update(app: AccessiWeatherApp, event) -> None: ...
def on_event_check_update(app: AccessiWeatherApp, event) -> None: ...
```

Move method bodies verbatim into each function, replacing `self` with `app`.

### Step 2b — Update `app.py` class methods

Replace each method body with a one-line delegation:
```python
def _stop_auto_update_checks(self) -> None:
    app_timer_manager.stop_auto_update_checks(self)

def _start_auto_update_checks(self) -> None:
    app_timer_manager.start_auto_update_checks(self)

def _on_auto_update_check_timer(self, event) -> None:
    app_timer_manager.on_auto_update_check_timer(self, event)

def _stop_background_updates(self) -> None:
    app_timer_manager.stop_background_updates(self)

def _start_background_updates(self) -> None:
    app_timer_manager.start_background_updates(self)

def _on_background_update(self, event) -> None:
    app_timer_manager.on_background_update(self, event)

def _on_event_check_update(self, event) -> None:
    app_timer_manager.on_event_check_update(self, event)
```

Add `from . import app_timer_manager` to app.py imports.

### Verify Task 2:

```bash
# Tests still pass (methods unchanged from caller perspective)
python3 -m pytest tests/test_split_update_timers.py tests/test_app_auto_update_checks.py --tb=short -q
# Must: all pass

# Line count
python3 -c "
with open('src/accessiweather/app.py') as f:
    print(len(f.readlines()), 'lines (after Task 2)')
"
# Expected: ~1,270 lines or less

# Ruff lint
python3 -m ruff check src/accessiweather/app_timer_manager.py src/accessiweather/app.py
# Must: no errors
```

**Commit:**
```bash
git add src/accessiweather/app_timer_manager.py src/accessiweather/app.py
git commit -m "refactor: extract timer management into app_timer_manager.py"
```

---

## Task 3 — Full Verification Pass

```bash
cd /home/openclaw/projects/AccessiWeather

# 1. Full test suite
python3 -m pytest --tb=short -q 2>&1 | tail -10
# Must: no new regressions vs baseline

# 2. Final line count
python3 -c "
with open('src/accessiweather/app.py') as f:
    count = len(f.readlines())
print(f'{count} lines (was 1693, saved {1693 - count})')
"

# 3. No circular imports
python3 -c "
import accessiweather.windows_toast_identity
import accessiweather.app_timer_manager
import accessiweather.app
print('All imports OK')
"

# 4. Ruff lint both new modules
python3 -m ruff check src/accessiweather/windows_toast_identity.py src/accessiweather/app_timer_manager.py src/accessiweather/app.py
```

---

## Definition of Done

- [ ] `windows_toast_identity.py` created with full toast identity block
- [ ] `app_timer_manager.py` created with 7 timer management functions
- [ ] `app.py` reduced by ≥420 lines (≤1,270 lines)
- [ ] `app.py` re-exports toast identity functions for backward compat
- [ ] Test patches updated to `accessiweather.windows_toast_identity.*`
- [ ] All existing tests pass with no new regressions
- [ ] `ruff check` passes on all modified/created files
- [ ] All tasks committed as separate git commits
