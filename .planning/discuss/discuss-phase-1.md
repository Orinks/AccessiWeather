# Phase 1 Discussion: Monolith Refactor

## What are we refactoring?
Primary targets by priority:
1. `weather_client_base.py` (1,399 lines) - Extract cache, alert dedup, enrichment into separate coordinator modules
2. `weather_client_nws.py` (1,533 lines) - Extract parsing logic into separate parsers module
3. `app.py` (1,693 lines) - Extract timer management, notifier setup, tray management into separate modules
4. `main_window.py` (1,390 lines) - Extract notification event handling, dialog management into mixins/helpers

## Constraints
- No breaking API/public interface changes
- All existing tests must stay green
- Aim for <500 lines per file after refactor
- One module extracted per PR (atomic, reviewable)
- settings_dialog.py left for a later phase (too risky, too large)

## Approach
- Extract don't rewrite: move code, don't redesign
- Keep class names and public methods identical
- Use import forwarding where needed for backward compat
- Each extraction gets its own tests
