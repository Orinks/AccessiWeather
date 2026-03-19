# Phase 2 Plan — Slim `weather_client_base.py` (Delegation Stub Batch 2)

## Phase Goal

Remove the next batch of delegation stubs from `weather_client_base.py`, continuing
the Phase 1 effort. Target: dead-code parse/trend stubs (never called) and inlineable
enrichment/trend stubs (called internally, not mocked). Preserve the NWS/OpenMeteo
fetch stubs (`_get_nws_*`, `_get_openmeteo_*`) — they are intentional mock seam points
used heavily in tests via `_methods_overridden` and `AsyncMock` patching.

**Starting line count:** 1,303 lines (after Phase 1)
**Estimated savings:** ~65 lines
**Projected post-phase count:** ~1,238 lines

---

## Pre-Analysis Findings

### What to Remove

**Group A — Dead-code parse stubs (7 methods, ~24 lines)**
Never called anywhere in the codebase (verified via grep). Pure noise.
- `_parse_nws_current_conditions` (line ~1131)
- `_parse_nws_forecast` (line ~1135)
- `_parse_nws_alerts` (line ~1139)
- `_parse_nws_hourly_forecast` (line ~1143)
- `_parse_openmeteo_current_conditions` (line ~1149)
- `_parse_openmeteo_forecast` (line ~1153)
- `_parse_openmeteo_hourly_forecast` (line ~1157)

**Group B — Dead-code trend stubs (4 methods, ~14 lines)**
Never called anywhere in the codebase (verified via grep). Pure noise.
- `_compute_temperature_trend` (line ~1291)
- `_compute_pressure_trend` (line ~1294)
- `_trend_descriptor` (line ~1297)
- `_period_for_hours_ahead` (line ~1300)

**Group C — Inlineable enrichment stubs (7 methods, ~27 lines)**
Called internally (in `_launch_enrichment_tasks` / `_await_enrichments`).
Not mocked in any test. Replacing `self._method(args)` with direct module calls
is safe and removes unnecessary indirection.
- `_enrich_with_nws_discussion` → `enrichment.enrich_with_nws_discussion(self, ...)`
- `_enrich_with_aviation_data` → `enrichment.enrich_with_aviation_data(self, ...)`
- `_enrich_with_visual_crossing_alerts` → `enrichment.enrich_with_visual_crossing_alerts(self, ...)`
- `_enrich_with_visual_crossing_moon_data` → `enrichment.enrich_with_visual_crossing_moon_data(self, ...)`
- `_enrich_with_sunrise_sunset` → `enrichment.enrich_with_sunrise_sunset(self, ...)`
- `_populate_environmental_metrics` → `enrichment.populate_environmental_metrics(self, ...)`
- `_apply_trend_insights` → `trends.apply_trend_insights(weather_data, self.trend_insights_enabled, self.trend_hours, include_pressure=self.show_pressure_trend)`

### What NOT to Remove

**NWS/OpenMeteo fetch stubs — mock seam points (keep)**
`_get_nws_current_conditions`, `_get_nws_forecast_and_discussion`, `_get_nws_alerts`,
`_get_nws_hourly_forecast`, `_get_nws_discussion_only`, `_get_openmeteo_current_conditions`,
`_get_openmeteo_forecast`, `_get_openmeteo_hourly_forecast`.

These exist intentionally:
1. `_fetch_nws_data` and `_fetch_openmeteo_data` use `_methods_overridden([names...])` to
   detect mock/subclass overrides and fall back to the individual stub calls.
2. Tests in `test_nws_afd_notification.py`, `test_split_notification_timers.py`, and
   `test_coverage_gaps.py` mock them directly via `AsyncMock`.

**Methods with real logic (keep)**
`_get_forecast_days_for_source`, `_persist_weather_data`,
`_enrich_with_visual_crossing_history`, `_augment_current_with_openmeteo`.

---

## Pre-Flight Checks

```bash
cd /home/openclaw/projects/AccessiWeather

# 1. Confirm baseline line count
python3 -c "
with open('src/accessiweather/weather_client_base.py') as f:
    print(len(f.readlines()), 'lines (baseline)')
"
# Expected: 1303

# 2. Confirm dead-code stubs have no callers
grep -rn "\._parse_nws_\|\._parse_openmeteo_\|\._compute_temperature_trend\|\._compute_pressure_trend\|\._trend_descriptor\|\._period_for_hours_ahead" \
    src/ tests/ --include="*.py"
# Must: 0 results (definitions only in weather_client_base.py)

# 3. Run baseline tests
python3 -m pytest --tb=short -q 2>&1 | tail -5
# Expected: 7 pre-existing failures in test_visual_crossing_integration.py, 2649 pass
```

---

## Task 1 — Delete Dead-Code Parse Stubs

**File:** `src/accessiweather/weather_client_base.py`

Delete the 7 `_parse_*` methods (approximately lines 1131–1159). These are one-line
delegation stubs that call `nws_client.*` or `openmeteo_client.*` parse functions.
They have zero callers — anywhere in the codebase.

Methods to delete:
- `_parse_nws_current_conditions`
- `_parse_nws_forecast`
- `_parse_nws_alerts`
- `_parse_nws_hourly_forecast`
- `_parse_openmeteo_current_conditions`
- `_parse_openmeteo_forecast`
- `_parse_openmeteo_hourly_forecast`

**Verify no callers first:**
```bash
grep -rn "\._parse_nws_\|\._parse_openmeteo_" src/ tests/ --include="*.py"
# Must: 0 results
```

**After deleting, verify:**
```bash
python3 -c "
with open('src/accessiweather/weather_client_base.py') as f:
    print(len(f.readlines()), 'lines (after Task 1)')
"
# Expected: ~1279 (reduced by ~24)

python3 -m pytest tests/test_weather_client.py tests/test_parsers.py tests/test_nws_alerts.py --tb=short -q
# Must: all pass
```

**Commit:**
```bash
git add src/accessiweather/weather_client_base.py
git commit -m "refactor: remove dead-code parse delegation stubs from WeatherClient"
```

---

## Task 2 — Delete Dead-Code Trend Stubs

**File:** `src/accessiweather/weather_client_base.py`

Delete the 4 unused trend delegation methods (approximately lines 1291–1303).
These delegate to `trends.*` functions but are never called.

Methods to delete:
- `_compute_temperature_trend`
- `_compute_pressure_trend`
- `_trend_descriptor`
- `_period_for_hours_ahead`

**Verify no callers first:**
```bash
grep -rn "\._compute_temperature_trend\|\._compute_pressure_trend\|\._trend_descriptor\|\._period_for_hours_ahead" \
    src/ tests/ --include="*.py"
# Must: 0 results
```

**After deleting, verify:**
```bash
python3 -c "
with open('src/accessiweather/weather_client_base.py') as f:
    print(len(f.readlines()), 'lines (after Task 2)')
"
# Expected: ~1265

python3 -m pytest tests/test_weather_client_trends.py tests/test_weather_client.py --tb=short -q
# Must: all pass
```

**Commit:**
```bash
git add src/accessiweather/weather_client_base.py
git commit -m "refactor: remove dead-code trend delegation stubs from WeatherClient"
```

---

## Task 3 — Inline Enrichment and Trend Stubs

**File:** `src/accessiweather/weather_client_base.py`

Replace each `self._enrich_with_*` / `self._populate_environmental_metrics` call with
a direct `enrichment.*` call, and `self._apply_trend_insights` with `trends.*`. Then
delete the now-unused stub method definitions.

### Step 3a — Update call sites in `_launch_enrichment_tasks`

In method `_launch_enrichment_tasks` (around lines 890–940), replace:

| Old call | New call |
|----------|----------|
| `self._enrich_with_sunrise_sunset(weather_data, location)` | `enrichment.enrich_with_sunrise_sunset(self, weather_data, location)` |
| `self._enrich_with_nws_discussion(weather_data, location)` | `enrichment.enrich_with_nws_discussion(self, weather_data, location)` |
| `self._enrich_with_visual_crossing_alerts(weather_data, location, skip_notifications)` | `enrichment.enrich_with_visual_crossing_alerts(self, weather_data, location, skip_notifications)` |
| `self._enrich_with_visual_crossing_moon_data(weather_data, location)` | `enrichment.enrich_with_visual_crossing_moon_data(self, weather_data, location)` |
| `self._populate_environmental_metrics(weather_data, location)` | `enrichment.populate_environmental_metrics(self, weather_data, location)` |
| `self._enrich_with_aviation_data(weather_data, location)` | `enrichment.enrich_with_aviation_data(self, weather_data, location)` |

### Step 3b — Update call site in `_await_enrichments`

In method `_await_enrichments` (around line 963), replace:
```python
self._apply_trend_insights(weather_data)
```
with:
```python
trends.apply_trend_insights(
    weather_data,
    self.trend_insights_enabled,
    self.trend_hours,
    include_pressure=self.show_pressure_trend,
)
```

### Step 3c — Delete the 7 stub method definitions

Delete:
- `_enrich_with_nws_discussion` (lines ~1194–1197)
- `_enrich_with_aviation_data` (lines ~1199–1202)
- `_enrich_with_visual_crossing_alerts` (lines ~1222–1227)
- `_enrich_with_visual_crossing_moon_data` (lines ~1229–1232)
- `_enrich_with_sunrise_sunset` (lines ~1234–1237)
- `_populate_environmental_metrics` (lines ~1239–1242)
- `_apply_trend_insights` (lines ~1271–1277)

### Verify:

```bash
# No lingering self._enrich_with_* or self._apply_trend calls
grep -n "self\._enrich_with_\|self\._populate_environmental\|self\._apply_trend" \
    src/accessiweather/weather_client_base.py
# Must: 0 results

# File shrank further
python3 -c "
with open('src/accessiweather/weather_client_base.py') as f:
    print(len(f.readlines()), 'lines (after Task 3)')
"
# Expected: ~1230

# Full suite
python3 -m pytest --tb=short -q 2>&1 | tail -5
# Must: same pass/fail counts as baseline
```

**Commit:**
```bash
git add src/accessiweather/weather_client_base.py
git commit -m "refactor: inline enrichment/trend delegation stubs in WeatherClient"
```

---

## Task 4 — Full Verification Pass

```bash
cd /home/openclaw/projects/AccessiWeather

# 1. Full test suite
python3 -m pytest --tb=short -q 2>&1 | tail -10
# Must: ≥2649 pass, only the 7 pre-existing VC integration failures

# 2. Final line count
python3 -c "
with open('src/accessiweather/weather_client_base.py') as f:
    count = len(f.readlines())
print(f'{count} lines (was 1303, saved {1303 - count})')
"

# 3. No dead stub references remain
grep -rn "self\._parse_nws_\|self\._parse_openmeteo_\|self\._compute_temperature_trend\|self\._compute_pressure_trend\|self\._trend_descriptor\|self\._period_for_hours_ahead\|self\._enrich_with_\|self\._populate_environmental\|self\._apply_trend_insights" \
    src/accessiweather/ --include="*.py"
# Must: 0 results

# 4. No circular import introduced
python3 -c "
import importlib
for m in ['accessiweather.weather_client_base', 'accessiweather.weather_client_enrichment', 'accessiweather.weather_client_trends']:
    importlib.import_module(m)
    print('OK:', m)
"
# Must: all 3 print OK

# 5. Ruff lint
python3 -m ruff check src/accessiweather/weather_client_base.py
# Must: no errors
```

---

## Rollback Plan

If any task breaks tests and the fix is not obvious:

```bash
git checkout -- src/accessiweather/weather_client_base.py
python3 -m pytest --tb=short -q 2>&1 | tail -5
```

Work task-by-task with a commit after each task passes. Revert only the last commit
if needed rather than all changes.

---

## Definition of Done

- [ ] All 11 dead-code stubs deleted (7 parse + 4 trend)
- [ ] All 7 enrichment/trend stubs inlined and deleted
- [ ] `weather_client_base.py` ≤ 1,240 lines (saved ≥ 63 lines from 1,303)
- [ ] NWS/OpenMeteo fetch stubs untouched
- [ ] `python3 -m pytest --tb=short -q` passes with no new regressions
- [ ] `python3 -m ruff check src/accessiweather/weather_client_base.py` returns no errors
- [ ] All tasks committed as separate git commits
