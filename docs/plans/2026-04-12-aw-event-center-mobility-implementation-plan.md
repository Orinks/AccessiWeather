# AccessiWeather implementation plan: Event Center, section jumps, and 90-minute mobility briefing

Date: 2026-04-12
Branch: docs/aw-polish-event-center-mobility
Status: implementation-ready plan

## Goal

Implement the approved polish design in a staged, test-driven way:

1. Toggleable main-window Event Center
2. F6 section cycling plus Ctrl+1..Ctrl+5 direct jumps
3. 90-minute mobility briefing in the hourly / near-term section
4. Cleaner confidence wording built on existing confidence plumbing
5. Follow-on hazard surfacing hooks without overbuilding the first slice

## Current code reality

### Main window ownership

The visible top-level weather UI already lives in:
- `src/accessiweather/ui/main_window.py`

Current visible order in the default single-location view is effectively:
1. Location chooser
2. Current Conditions
3. Daily Forecast
4. Hourly Forecast
5. Weather Alerts
6. Action buttons

This means the approved canonical order maps naturally to the existing widgets, with one wording adjustment in implementation/docs:
- Current conditions
- Hourly / near-term
- Daily forecast
- Alerts
- Event Center

Because the current layout renders daily above hourly, implementation must decide whether to:
- preserve current visual order and adjust number mapping, or
- reorder the two forecast sections to match the approved jump order.

Recommendation: reorder visible forecast sections so Hourly / near-term appears before Daily Forecast. That keeps the keyboard model, docs, and visible layout aligned rather than teaching an exception.

### Shortcut ownership

Global accelerators currently live in:
- `src/accessiweather/app.py`

Existing shortcuts include:
- Ctrl+R, Ctrl+L, Ctrl+D, Ctrl+H, Ctrl+S, Ctrl+Q, F5

This is the right place to add:
- F6 section cycling
- Ctrl+1..Ctrl+5 direct section jumps

### Notification/event plumbing

Relevant notification paths already exist in:
- `src/accessiweather/ui/main_window_notification_events.py`
- `src/accessiweather/ui/main_window.py`
- `src/accessiweather/alert_notification_system.py`
- `src/accessiweather/screen_reader.py`

Important current behavior:
- lightweight polling already processes discussion/severe-risk/minutely event notifications
- full refresh path already processes alert notifications and event notifications
- `MainWindow` already owns a `ScreenReaderAnnouncer`

This means the Event Center should not invent a third notification system. It should be a reviewable capture surface for user-facing spoken/event text.

### Forecast presentation ownership

Forecast text currently comes from:
- `src/accessiweather/display/presentation/forecast.py`
- `src/accessiweather/display/weather_presenter.py`

Relevant existing support:
- `ForecastPresentation.daily_section_text`
- `ForecastPresentation.hourly_section_text`
- `ForecastPresentation.confidence_label`
- existing confidence text is already appended into the daily section

The mobility briefing belongs in this presentation layer, not directly in `MainWindow` string assembly.

### Weather data model

Relevant weather model fields already exist in:
- `src/accessiweather/models/weather.py`

Important existing fields:
- `WeatherData.hourly_forecast`
- `WeatherData.minutely_precipitation`
- `WeatherData.forecast_confidence`
- `CurrentConditions.visibility_*`
- `CurrentConditions.severe_weather_risk`
- `ForecastPeriod.precipitation_probability`, `wind_gust`, etc.

This is enough to implement a first-pass mobility briefing without introducing a brand-new persisted weather model.

## Data-source research summary

Research used:
- existing AccessiWeather clients
- provider official docs pages fetched with curl
- direct inspection of current request parameters already in repo

### Pirate Weather

Current client:
- `src/accessiweather/pirate_weather_client.py`

Current request already uses:
- `extend=hourly`
- full payload fetch returning `currently`, `hourly`, `daily`, `minutely`, `alerts`

Docs/page evidence from official docs page indicates support for:
- `minutely`
- `include`
- `extend=hourly`
- `visibility`
- `cape` / `capeMaxTime`

Practical implication:
- AW already has a single full-payload request path for PW
- first-pass mobility briefing can reuse `weather_data.minutely_precipitation` when available
- if we later want richer PW-driven risk phrasing, CAPE is a plausible extension point

### Open-Meteo

Current client:
- `src/accessiweather/openmeteo_client.py`

Current repo already requests/supports:
- current visibility
- hourly precipitation probability
- hourly visibility
- hourly wind gusts

Official docs page content confirms support for:
- `minutely_15`
- 15-minute variables including precipitation-oriented and wind-oriented series
- hourly `visibility`
- hourly `wind_gusts_10m`
- hourly `cape`

Practical implication:
- Open-Meteo is the strongest fallback for a near-term mobility summary when Pirate Weather minutely data is absent
- first-pass implementation can likely begin with existing hourly data path, then add a narrower `minutely_15` enhancement path if needed
- visibility and CAPE can support better confidence/hazard messaging later

### Visual Crossing

Current client:
- `src/accessiweather/visual_crossing_client.py`

Current repo already uses official API parameters like:
- `include=current,days`
- `include=days`
- `include=hours`
- `include=alerts`
- `elements=...visibility...windgust...precip...severerisk...`

Official docs page and examples confirm:
- `include=days`
- `hours`
- `alerts`
- `visibility`
- `severerisk`
- configurable `elements`

Practical implication:
- Visual Crossing is already a usable fallback source for hourly wind/visibility/severe-risk context
- it is not the first choice for the mobility briefing, but it is useful for fallback and hazard enrichment

## Implementation strategy

## Phase 1: Event Center foundation

### Production changes

Add a simple Event Center section to `MainWindow`:
- label: `Event Center:`
- widget: multiline read-only `wx.TextCtrl`
- visible by default
- toggleable from the View menu
- append-only timestamped text

Recommended widget shape:
- `wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2`
- explicit helper methods on `MainWindow`:
  - `append_event_center_entry(text: str, *, category: str | None = None)`
  - `show_event_center()`
  - `hide_event_center()`
  - `toggle_event_center()`
  - `_focus_event_center()`

### Test-first slices

1. RED: Event Center helper appends timestamped text to the control
2. RED: toggle hides and shows the Event Center section
3. RED: hidden Event Center can be revealed and focused
4. RED: F6 traversal skips Event Center when hidden

### Notes

Do not couple Event Center logging directly to desktop notifications. It should capture user-facing text, not notifier internals.

## Phase 2: Section navigation

### Production changes

Implement a canonical section map in `MainWindow`, not scattered logic.

Recommended helpers:
- `_get_top_level_sections() -> list[tuple[str, wx.Window]]`
- `_focus_section_by_index(index: int)`
- `_cycle_section_focus()`

Approved mapping:
- 1 = Current conditions
- 2 = Hourly / near-term
- 3 = Daily forecast
- 4 = Alerts
- 5 = Event Center

Add global accelerators in `app.py` for:
- F6
- Ctrl+1..Ctrl+5

### Test-first slices

1. RED: canonical section order returns expected widgets in expected order
2. RED: hidden Event Center is omitted from visible traversal
3. RED: Ctrl+5 reveals and focuses Event Center when hidden
4. RED: F6 advances through visible sections in order

### Important UI note

To match the approved behavior cleanly, move Hourly Forecast above Daily Forecast in `_create_widgets()`.

## Phase 3: Event capture wiring

### Production changes

Route user-facing spoken/event text into the Event Center.

First-pass sources:
- spoken alerts / notifications
- spoken briefings / summaries generated by this work

Possible integration points:
- `MainWindow.set_status()` is not sufficient by itself and should not become the Event Center sink
- add a dedicated `log_user_event(...)` / `log_spoken_event(...)` path on `MainWindow`
- call it from places that already decide user-facing text

For alert notifications, prefer logging the text composed for the user, not low-level event metadata.

### Test-first slices

1. RED: alert/event text passed through main-window event logging is appended in Event Center
2. RED: plain reviewable text is stored even if sound/notifier delivery path is mocked

## Phase 4: 90-minute mobility briefing

### Production changes

Add a new builder module, preferably under presentation/service layer, for example:
- `src/accessiweather/services/mobility_briefing.py`
  or
- `src/accessiweather/display/presentation/mobility.py`

Recommendation: keep generation logic out of `MainWindow` and out of `forecast.py` line-formatting code. Use a small helper that returns a concise string or `None`.

Suggested API:
- `build_mobility_briefing(weather_data: WeatherData, settings: AppSettings | None = None) -> str | None`

Inputs to use in priority order:
1. Pirate Weather minutely precipitation (`weather_data.minutely_precipitation`)
2. Open-Meteo near-term/hourly fallback
3. Visual Crossing hourly fallback

First-pass output rules:
- one concise sentence
- next 90 minutes only
- mention only meaningful mobility impacts:
  - precip start/stop timing
  - precip intensity shift
  - gust increase
  - visibility degradation or staying good
  - thunder concern when meaningful

Rendering integration:
- prepend or insert the briefing at the top of `hourly_section_text`
- also expose it separately on `ForecastPresentation` if helpful for reuse/testing

Recommended small model extension:
- add `mobility_briefing: str | None = None` to `ForecastPresentation`

### Test-first slices

1. RED: returns concise precip-start message from minutely precipitation data
2. RED: omits irrelevant categories when conditions are stable
3. RED: falls back to hourly wind/precip summary when minutely data absent
4. RED: mentions visibility stability/degradation when materially relevant
5. RED: limits scope to the next 90 minutes
6. RED: hourly section text includes the mobility briefing ahead of generic hourly lines

## Phase 5: Confidence wording cleanup

### Current behavior

`forecast.py` already appends:
- `Forecast confidence: Medium. <rationale>.`

### Production change

Refine wording to approved explanation-first style without creating a separate diagnostics UI.

Recommendation:
- keep confidence in the daily section for now
- convert internal `Medium` to user-facing `Moderate`
- ensure rationale reads naturally as disagreement explanation

Potential helper:
- `format_confidence_line(confidence: ForecastConfidence) -> str`

### Test-first slices

1. RED: medium confidence renders as `Moderate`
2. RED: disagreement rationale is preserved in plain language
3. RED: confidence line stays concise and readable

## Phase 6: Event Center capture for briefings

### Production changes

When a mobility briefing is actively spoken or surfaced as a user-facing summary, append it to the Event Center as:
- `[time] Briefing: ...`

### Test-first slices

1. RED: a generated briefing can be logged to Event Center with `Briefing:` prefix
2. RED: Event Center stores the same user-facing text used for review

## Phase 7: Hazard-card hooks (deferred unless time remains)

Do not implement full cards in the first coding pass unless earlier phases land cleanly with tests.

If time remains, add only a tiny internal hook:
- helper that detects whether a hazard callout should exist
- no large UI surfacing yet

## Test plan

### Existing likely test targets to extend

- `tests/test_main_window_forecast_sections.py`
- `tests/test_main_window_announcer.py`
- `tests/test_notification_event_manager.py`
- `tests/test_hourly_forecast_presentation.py`
- `tests/test_forecast_confidence_presentation.py`
- `tests/test_all_locations_view.py`

### New likely test files

- `tests/test_main_window_event_center.py`
- `tests/test_main_window_section_navigation.py`
- `tests/test_mobility_briefing.py`

## Recommended implementation order in code

1. Add failing Event Center tests
2. Implement Event Center helpers and toggle UI
3. Add failing section-jump tests
4. Implement F6 / Ctrl+1..Ctrl+5 navigation
5. Add failing mobility briefing tests
6. Implement mobility briefing builder
7. Integrate briefing into forecast presentation
8. Add failing confidence wording tests
9. Refine confidence wording
10. Wire briefing/event text into Event Center
11. Run targeted tests, then broader relevant suite

## Verification commands

Start narrow during TDD:

```bash
pytest -q tests/test_main_window_event_center.py
pytest -q tests/test_main_window_section_navigation.py
pytest -q tests/test_mobility_briefing.py
pytest -q tests/test_hourly_forecast_presentation.py
pytest -q tests/test_forecast_confidence_presentation.py
```

Then run the touched broader set:

```bash
pytest -q \
  tests/test_main_window_forecast_sections.py \
  tests/test_main_window_announcer.py \
  tests/test_notification_event_manager.py \
  tests/test_hourly_forecast_presentation.py \
  tests/test_forecast_confidence_presentation.py \
  tests/test_all_locations_view.py
```

## Risks

1. `MainWindow` already has a lot of responsibilities
   - Mitigation: keep Event Center and section traversal behind small helper methods

2. Shortcut logic split across `MainWindow` and `app.py`
   - Mitigation: accelerators in `app.py`, destination resolution in `MainWindow`

3. Mobility briefing could become verbose
   - Mitigation: hard cap it to one concise sentence and 90-minute scope

4. Forecast order mismatch between approved design and current UI
   - Mitigation: reorder hourly above daily now so the keyboard model stays truthful

5. Event Center could become a duplicate debug log
   - Mitigation: only user-facing spoken/event text in first pass

## Decision log

- Proceed without Bright Data MCP for now; use curl and official docs directly
- Keep implementation grounded in current client capabilities instead of building speculative new provider adapters first
- Use TDD for each feature slice before production code changes
