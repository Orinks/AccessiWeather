# Phase 1: weather_client_base.py — Extract Unit Conversion & Merge Logic - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract cohesive, stateless helper logic from `weather_client_base.py` (1,399 lines) into purpose-built modules. Specifically:
- All unit conversion helpers (`_convert_*` functions) → `src/accessiweather/utils/unit_conversion.py`
- `_merge_current_conditions` and related merge logic → `src/accessiweather/weather_client_merge.py`

This is extraction only — no redesign of algorithm, no API surface changes.

</domain>

<decisions>
## Implementation Decisions

### Extraction approach
- Extract-don't-rewrite: move code verbatim, minimal changes to make it importable
- Keep all function signatures identical
- Add import forwarding aliases in weather_client_base.py for any names consumed by external callers
- No functional changes in this phase

### API compatibility
- All public method signatures on WeatherClient remain unchanged
- Module-level helpers that are private (underscore prefix) can be moved freely
- Any re-exported name must be verified against external imports before removal

### File size target
- weather_client_base.py target: < 900 lines after phase 1 extraction (full <500 target achieved across multiple phases)
- New modules: < 300 lines each

### Testing strategy
- All existing tests must pass unchanged after extraction
- New unit tests added for extracted functions in isolation
- No mocking of extracted helpers — test them directly with inputs

### Commit strategy
- Each extracted module ships as its own atomic commit
- PR per extraction (weather_client_merge in one PR, unit_conversion in another)

### Cross-platform considerations
- All file paths use pathlib.Path
- No platform-specific code in extracted modules (purely computation)

</decisions>

<code_context>
## Existing Code Insights

### Files being extracted from
- `src/accessiweather/weather_client_base.py` (1,399 lines) — WeatherClient class + module-level helpers

### Existing patterns
- Unit conversion helpers already exist in `weather_client_parsers.py` (`convert_pa_to_inches`, `convert_pa_to_mb`, `convert_wind_speed_to_mph_and_kph`) — new extraction should be consistent with that style
- `src/accessiweather/utils/` directory already exists — place `unit_conversion.py` there

### Integration points
- `weather_client_base.py` imports from weather_client_parsers — can follow same import pattern
- Tests in `tests/` reference weather_client_base directly — must not break test imports

</code_context>

<specifics>
## Specific Ideas

- Unit conversion helpers to extract: anything matching `_convert_*` pattern plus pure calculation helpers
- Merge logic: `_merge_current_conditions` and any helpers it calls that aren't used elsewhere in the file
- Import forwarding: `from .utils.unit_conversion import *` style in weather_client_base.py to preserve any direct imports from external code

</specifics>

<deferred>
## Deferred Ideas

- weather_client_nws.py parser extraction → Phase 2
- app.py timer/tray extraction → Phase 3
- main_window.py notification event extraction → Phase 4
- settings_dialog.py decomposition → future milestone (too large/risky for phase 1)

</deferred>

---

*Phase: 01-weather-client-base-py-extract-unit-conversion-merge-logic*
*Context gathered: 2026-03-14*
