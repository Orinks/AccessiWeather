# Phase 1 Plan — Slim `weather_client_base.py`

## Phase Goal

Reduce `weather_client_base.py` from 1,399 lines to under 900 lines by removing dead
delegation stubs, extracting `_merge_current_conditions` into a standalone function, and
eliminating duplicated conversion helpers in `visual_crossing_client.py`. No public API
changes. All existing tests must stay green throughout.

---

## What We Actually Found (Pre-Analysis)

Before writing tasks, read the codebase. Key findings that change the plan:

**Finding 1 — Stubs, not logic.**
The 13 `_convert_*` / `_normalize_*` / `_degrees_to_cardinal` / etc. methods in
`WeatherClient` (lines 1354–1399) are one-line delegation stubs that call
`parsers.<function>(...)`. They contain zero logic. They exist only because
callers used `self._convert_*`. The real implementations already live in
`weather_client_parsers.py`. The correct action is to delete the stubs and update
callers to call `parsers.*` directly (or import the function module-level).

**Finding 2 — `VisualCrossingClient` has private copies.**
`visual_crossing_client.py` (lines 848–876) owns its own `_convert_f_to_c` and
`_degrees_to_cardinal` private methods that duplicate implementations already in
`weather_client_parsers.py`. These should be replaced with direct imports.

**Finding 3 — `_merge_current_conditions` is purely functional.**
The method (lines 1194–1238) takes two `CurrentConditions` attrs instances and merges
fields. It accesses no `self` state beyond the two arguments. It can become a
module-level function immediately. The only caller is `_augment_current_with_openmeteo`
at line 1192.

**Finding 4 — `DataFusionEngine.merge_current_conditions` is a different method.**
`weather_client_fusion.py:49` has its own `merge_current_conditions` with a different
signature (`sources: list`, `location: Location`). It is unrelated. Do not confuse them.

**Estimated line savings:**
- Remove 13 stub methods from `WeatherClient`: ~46 lines
- Remove 2 private helpers from `VisualCrossingClient`: ~30 lines
- Extract `_merge_current_conditions` (net zero — function moves, call site simplifies): ~0
- Total reduction in `weather_client_base.py`: ~46 lines (1,399 → ~1,353)

**Honest gap:** 46 lines of savings will NOT reach the <900 target. The original
discussion assumed these methods had real implementations. They do not. After this phase,
`weather_client_base.py` will be ~1,353 lines — still large. A follow-up phase targeting
the parse delegation stubs (lines ~1100–1350, another ~250 lines of one-liners) and the
inline fetch orchestration logic is needed to reach <900. This plan documents what the
code actually contains and executes a safe, complete extraction of the real candidates.

---

## Pre-Flight Checks

Run these before starting. Record results as your baseline.

```bash
# 1. Confirm line counts
python3 -c "
files = [
    'src/accessiweather/weather_client_base.py',
    'src/accessiweather/visual_crossing_client.py',
    'src/accessiweather/weather_client_parsers.py',
]
for f in files:
    with open(f) as fh:
        print(len(fh.readlines()), f)
"
# Expected: ~1399, ~876, ~246

# 2. Run baseline test suite (all tests, parallel)
python3 -m pytest --tb=short -q
# Expected: all pass

# 3. Capture baseline coverage for weather_client_base.py
python3 -m pytest --cov=src/accessiweather/weather_client_base \
    --cov-report=term-missing --tb=no -q 2>&1 | grep weather_client_base
# Record the covered/missing numbers for comparison after

# 4. Verify the stub methods exist as expected
python3 -c "
import ast, sys
with open('src/accessiweather/weather_client_base.py') as f:
    tree = ast.parse(f.read())
cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'WeatherClient')
stubs = [m.name for m in cls.body if isinstance(m, ast.FunctionDef) and m.name.startswith('_convert_')]
print('Stub methods found:', stubs)
"
```

---

## Task 1 — Remove Stub Delegation Methods from `WeatherClient`

**File:** `src/accessiweather/weather_client_base.py`

**What to do:**

The following 13 methods (lines 1354–1399) are pure delegation stubs. Delete all of them
from the `WeatherClient` class body. Do not change anything else in the file.

Methods to delete:
- `_convert_mps_to_mph` (line 1355)
- `_convert_wind_speed_to_mph` (line 1358)
- `_convert_wind_speed_to_kph` (line 1363)
- `_convert_wind_speed_to_mph_and_kph` (line 1368)
- `_convert_pa_to_inches` (line 1373)
- `_convert_pa_to_mb` (line 1376)
- `_normalize_temperature` (line 1379)
- `_normalize_pressure` (line 1384)
- `_convert_f_to_c` (line 1389)
- `_degrees_to_cardinal` (line 1392)
- `_weather_code_to_description` (line 1395)
- `_format_date_name` (line 1398)

Also delete `_normalize_datetime` at line 1351 (it delegates to `trends.normalize_datetime`
and is unused within `WeatherClient` itself — verify with grep before deleting).

**Verify no internal callers exist first:**

```bash
# Must return zero results for each before deleting
grep -n "self\._convert_\|self\._normalize_temperature\|self\._normalize_pressure\|self\._normalize_datetime\|self\._degrees_to_cardinal\|self\._weather_code_to_description\|self\._format_date_name" \
    src/accessiweather/weather_client_base.py
```

If any caller is found inside `weather_client_base.py`, replace `self._<method>(...)` with
`parsers.<method>(...)` (the `parsers` alias is already imported at line 20) before
deleting the stub.

**Check external callers (subclasses, other modules):**

```bash
grep -rn "self\._convert_mps_to_mph\|self\._convert_wind\|self\._convert_pa\|self\._normalize_temperature\|self\._normalize_pressure\|self\._convert_f_to_c\|self\._degrees_to_cardinal\|self\._weather_code_to_description\|self\._format_date_name\|self\._normalize_datetime" \
    src/accessiweather/
```

If any file calls these via `self.` (i.e., a subclass inheriting from `WeatherClient`),
replace those call sites with `from .weather_client_parsers import <function>` and call the
function directly. Based on the pre-analysis this should be zero hits — but verify.

**After deleting:**

```bash
# Confirm file shrank by ~45 lines
python3 -c "
with open('src/accessiweather/weather_client_base.py') as f:
    print(len(f.readlines()), 'lines')
"
# Expected: ~1354 (was 1399)

python3 -m pytest tests/test_weather_client.py tests/test_parsers.py --tb=short -q
# Must: all pass
```

---

## Task 2 — Replace Duplicate Helpers in `VisualCrossingClient`

**File:** `src/accessiweather/visual_crossing_client.py`

**What to do:**

`VisualCrossingClient` (lines 848–876) owns private copies of two functions that duplicate
implementations in `weather_client_parsers.py`:

- `_convert_f_to_c` (line 848) — identical to `parsers.convert_f_to_c`
- `_degrees_to_cardinal` (line 852) — identical to `parsers.degrees_to_cardinal`

**Step 2a — Add imports at the top of the file.**

`visual_crossing_client.py` already imports `describe_moon_phase` from
`weather_client_parsers` (line 25). Extend that import:

```python
# Change line 25 from:
from .weather_client_parsers import describe_moon_phase
# To:
from .weather_client_parsers import convert_f_to_c, degrees_to_cardinal, describe_moon_phase
```

**Step 2b — Replace all call sites.**

All calls within `VisualCrossingClient` that use `self._convert_f_to_c(...)` become
`convert_f_to_c(...)`. All calls using `self._degrees_to_cardinal(...)` become
`degrees_to_cardinal(...)`. Known call sites:

- Line 417: `self._convert_f_to_c(temp_f)` → `convert_f_to_c(temp_f)`
- Line 423: `self._convert_f_to_c(dewpoint_f)` → `convert_f_to_c(dewpoint_f)`
- Line 427: `self._convert_f_to_c(dewpoint_f)` → `convert_f_to_c(dewpoint_f)`
- Line 442: `self._convert_f_to_c(feels_like_f)` → `convert_f_to_c(feels_like_f)`
- Line 475: `self._convert_f_to_c(wind_chill_f)` → `convert_f_to_c(wind_chill_f)`
- Line 478: `self._convert_f_to_c(heat_index_f)` → `convert_f_to_c(heat_index_f)`
- Line 668: `self._convert_f_to_c(hourly_wind_chill_f)` → `convert_f_to_c(hourly_wind_chill_f)`
- Line 670: `self._convert_f_to_c(hourly_heat_index_f)` → `convert_f_to_c(hourly_heat_index_f)`
- Line 563: `self._degrees_to_cardinal(day_data.get("winddir"))` → `degrees_to_cardinal(day_data.get("winddir"))`
- Line 658: `self._degrees_to_cardinal(hour_data.get("winddir"))` → `degrees_to_cardinal(hour_data.get("winddir"))`

Confirm no call sites missed:

```bash
grep -n "self\._convert_f_to_c\|self\._degrees_to_cardinal" src/accessiweather/visual_crossing_client.py
# Must return 0 results after replacement
```

**Step 2c — Delete the private method definitions** (lines 848–876).

**Step 2d — Verify:**

```bash
python3 -m pytest tests/ -k "visual_crossing or vc" --tb=short -q
# Must: all pass (or no tests collected — both acceptable)

python3 -m pytest --tb=short -q
# Must: all pass
```

---

## Task 3 — Extract `_merge_current_conditions` into a Module-Level Function

**Files touched:**
- `src/accessiweather/weather_client_base.py` (remove method, update caller)
- `src/accessiweather/weather_client_parsers.py` (add function + export)

**Why this belongs in `weather_client_parsers.py`:**
The function is pure: takes two `CurrentConditions` instances, copies missing fields from
fallback to primary, calls `primary.__post_init__()`, returns `CurrentConditions`. No `self`
state. `weather_client_parsers.py` already imports nothing from the class hierarchy —
no circular import risk.

**Step 3a — Add the function to `weather_client_parsers.py`.**

Add this import at the top of `weather_client_parsers.py` (after existing imports):

```python
from __future__ import annotations
# already present

# Add after existing imports:
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CurrentConditions
```

Wait — check whether `models` is already imported in `weather_client_parsers.py` before
adding the import:

```bash
head -30 src/accessiweather/weather_client_parsers.py
```

If `CurrentConditions` is not imported, add it inside a `TYPE_CHECKING` guard for the
type hint, and use a string annotation `"CurrentConditions"` in the function signature, OR
do a direct import (safe since `models/__init__.py` imports nothing from parsers — verify):

```bash
grep -rn "weather_client_parsers" src/accessiweather/models/ 2>/dev/null
# Must return 0 results (no circular risk)
```

Add the function body at the end of `weather_client_parsers.py`, before or after
`describe_moon_phase`:

```python
def merge_current_conditions(
    primary: "CurrentConditions | None",
    fallback: "CurrentConditions",
) -> "CurrentConditions":
    """Merge missing fields from fallback into primary; return merged result.

    If primary is None, returns fallback unchanged. Otherwise, iterates over
    the known supplemental fields and copies non-None, non-empty values from
    fallback to primary wherever primary has no data. Calls __post_init__ on
    the result to recompute any derived fields.
    """
    from .models import CurrentConditions  # local import avoids top-level circular risk

    if primary is None:
        return fallback

    for field in [
        "temperature",
        "temperature_f",
        "temperature_c",
        "condition",
        "humidity",
        "dewpoint_f",
        "dewpoint_c",
        "wind_speed",
        "wind_speed_mph",
        "wind_speed_kph",
        "wind_direction",
        "pressure",
        "pressure_in",
        "pressure_mb",
        "feels_like_f",
        "feels_like_c",
        "visibility_miles",
        "visibility_km",
        "uv_index",
        "sunrise_time",
        "sunset_time",
        "moon_phase",
        "moonrise_time",
        "moonset_time",
    ]:
        value = getattr(primary, field, None)
        if value not in (None, ""):
            continue
        fallback_value = getattr(fallback, field, None)
        if fallback_value in (None, ""):
            continue
        setattr(primary, field, fallback_value)

    primary.__post_init__()
    return primary
```

Also add `"merge_current_conditions"` to the `__all__` list at the top of the file.

**Step 3b — Update `weather_client_base.py`.**

1. Replace `self._merge_current_conditions(current, fallback)` at line 1192 with:
   `parsers.merge_current_conditions(current, fallback)`
   (The `parsers` alias already covers `weather_client_parsers`.)

2. Delete the `_merge_current_conditions` method definition (lines 1194–1238).

**Step 3c — Verify the call site is correct:**

```bash
grep -n "_merge_current_conditions\|merge_current_conditions" \
    src/accessiweather/weather_client_base.py
# Must show exactly one hit: the parsers.merge_current_conditions(...) call at ~line 1192
# The method definition must be gone
```

**Step 3d — Verify no test breakage:**

```bash
python3 -m pytest --tb=short -q
# Must: all pass
```

---

## Task 4 — Write New Tests for Extracted / Standalone Functions

**File:** `tests/test_parsers.py` (extend existing) or new file `tests/test_parsers_merge.py`

**What to test:**

The existing `tests/test_parsers.py` already covers the conversion functions (28 tests,
all pass). Add tests specifically for `merge_current_conditions` since it is newly promoted
to a module-level public function.

Construct minimal `CurrentConditions` instances using the attrs factory. Test:

1. `primary=None` → returns `fallback` unchanged
2. Primary has all fields populated → fallback fields not applied (primary wins)
3. Primary has `temperature=None`, fallback has value → fallback value copied
4. Primary has `temperature=""` (empty string), fallback has value → fallback value copied
5. Primary has `temperature=None`, fallback has `temperature=None` → field stays `None`
6. After merge, `__post_init__` was called (verify a derived field is set, e.g. that the
   object is still a valid `CurrentConditions` instance without raising)
7. Merge does not mutate the `fallback` object (the returned object is `primary`)

Example test structure:

```python
# tests/test_parsers_merge.py
import pytest
from accessiweather.models import CurrentConditions
from accessiweather.weather_client_parsers import merge_current_conditions


def make_conditions(**kwargs):
    """Return a minimal CurrentConditions with defaults overridden by kwargs."""
    defaults = dict(
        temperature=None, temperature_f=None, temperature_c=None,
        condition=None, humidity=None, dewpoint_f=None, dewpoint_c=None,
        wind_speed=None, wind_speed_mph=None, wind_speed_kph=None,
        wind_direction=None, pressure=None, pressure_in=None, pressure_mb=None,
        feels_like_f=None, feels_like_c=None, visibility_miles=None, visibility_km=None,
        uv_index=None, sunrise_time=None, sunset_time=None, moon_phase=None,
        moonrise_time=None, moonset_time=None,
    )
    defaults.update(kwargs)
    return CurrentConditions(**defaults)
```

Adjust the `make_conditions` helper to match the actual `CurrentConditions.__init__`
signature — run `python3 -c "from accessiweather.models import CurrentConditions; help(CurrentConditions)"` to inspect required fields.

**Verify:**

```bash
python3 -m pytest tests/test_parsers_merge.py -v --tb=short
# Must: all new tests pass
```

---

## Task 5 — Full Verification Pass

Run all checks in sequence. All must pass before this phase is considered done.

```bash
# 1. Full test suite
python3 -m pytest --tb=short -q
# Expected: same pass count as baseline (or higher)

# 2. Final line count check
python3 -c "
files = {
    'src/accessiweather/weather_client_base.py': 1399,
    'src/accessiweather/visual_crossing_client.py': 876,
    'src/accessiweather/weather_client_parsers.py': 246,
}
for path, baseline in files.items():
    with open(path) as f:
        count = len(f.readlines())
    delta = count - baseline
    sign = '+' if delta > 0 else ''
    print(f'{count:>5} lines ({sign}{delta:>+4})  {path}')
"
# Expected approximate output:
#  ~1353 lines (-46)  weather_client_base.py
#   ~846 lines (-30)  visual_crossing_client.py
#   ~295 lines (+49)  weather_client_parsers.py  (added merge_current_conditions + tests)

# 3. No references to deleted methods remain
grep -rn "self\._convert_mps_to_mph\|self\._convert_wind_speed\|self\._convert_pa_to\|self\._normalize_temperature\|self\._normalize_pressure\|self\._convert_f_to_c\|self\._degrees_to_cardinal\|self\._weather_code_to_description\|self\._format_date_name\|self\._normalize_datetime\|self\._merge_current_conditions" \
    src/accessiweather/
# Must: 0 results

# 4. No circular import introduced
python3 -c "
import importlib
mods = [
    'accessiweather.weather_client_parsers',
    'accessiweather.weather_client_base',
    'accessiweather.visual_crossing_client',
]
for m in mods:
    importlib.import_module(m)
    print('OK:', m)
"
# Must: all three print OK without ImportError

# 5. Ruff lint check
python3 -m ruff check src/accessiweather/weather_client_base.py \
    src/accessiweather/visual_crossing_client.py \
    src/accessiweather/weather_client_parsers.py
# Must: no errors (warnings are acceptable)

# 6. Coverage on parsers (should improve or hold)
python3 -m pytest --cov=src/accessiweather/weather_client_parsers \
    --cov-report=term-missing --tb=no -q tests/test_parsers.py tests/test_parsers_merge.py
# Must: coverage >= prior baseline for this file
```

---

## Rollback Plan

If any step breaks tests and the fix is not obvious, revert using git:

```bash
# Revert all changes in the three touched files
git checkout -- src/accessiweather/weather_client_base.py \
                src/accessiweather/visual_crossing_client.py \
                src/accessiweather/weather_client_parsers.py

# Confirm revert worked
python3 -m pytest --tb=short -q
```

If you added a new test file and want to keep it while reverting the source files:
```bash
git checkout -- src/accessiweather/weather_client_base.py \
                src/accessiweather/visual_crossing_client.py \
                src/accessiweather/weather_client_parsers.py
# New test file (tests/test_parsers_merge.py) is untracked — it is unaffected by checkout
```

Work task-by-task with a `git add -p` + `git commit` after each task passes. This makes
rollback surgical: revert only the last commit rather than all changes.

Suggested commit sequence:
```bash
# After Task 1:
git add src/accessiweather/weather_client_base.py
git commit -m "refactor: remove stub delegation methods from WeatherClient"

# After Task 2:
git add src/accessiweather/visual_crossing_client.py
git commit -m "refactor: replace private conversion helpers in VisualCrossingClient with parsers imports"

# After Task 3:
git add src/accessiweather/weather_client_parsers.py src/accessiweather/weather_client_base.py
git commit -m "refactor: extract _merge_current_conditions to module-level function in parsers"

# After Task 4:
git add tests/test_parsers_merge.py
git commit -m "test: add coverage for merge_current_conditions"
```

---

## Honest Scope Note

After completing all four tasks, `weather_client_base.py` will be approximately
**1,353 lines** — not the originally stated <900 target. This is because the unit
conversion methods were already stubs (the analysis in the discuss doc was based on an
older state of the file before partial extraction had occurred). A follow-up phase is
needed to reach <900. Candidates for Phase 1b or Phase 2:

- Parse delegation stubs (lines ~1100–1350 in current file): another ~15 methods that
  delegate to `nws_client.*`, `openmeteo_client.*`, `trends.*` — same stub pattern.
  Removing them saves ~120 additional lines.
- The inline fetch orchestration logic and HTTP client lifecycle (~300 lines) requires
  more careful extraction due to async coordination.

Reaching <900 is achievable but requires a second pass. This plan executes the safe,
verified part of the work.

---

## Definition of Done

- [ ] `weather_client_base.py` has no `_convert_*`, `_normalize_temperature`,
      `_normalize_pressure`, `_normalize_datetime`, `_degrees_to_cardinal`,
      `_weather_code_to_description`, `_format_date_name`, or `_merge_current_conditions`
      method definitions in the `WeatherClient` class body
- [ ] `visual_crossing_client.py` has no `_convert_f_to_c` or `_degrees_to_cardinal`
      private method definitions
- [ ] `weather_client_parsers.py` exports `merge_current_conditions` in its `__all__`
- [ ] `tests/test_parsers_merge.py` exists with at least 7 test cases covering the
      `merge_current_conditions` behavior
- [ ] `python3 -m pytest --tb=short -q` passes with no regressions
- [ ] `grep -rn "self\._convert_\|self\._merge_current_conditions" src/accessiweather/`
      returns 0 results
- [ ] `python3 -m ruff check src/accessiweather/weather_client_base.py
      src/accessiweather/visual_crossing_client.py src/accessiweather/weather_client_parsers.py`
      returns no errors
- [ ] All four tasks committed as separate git commits with descriptive messages
