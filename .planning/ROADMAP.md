# AccessiWeather Monolith Refactor — Roadmap

## Milestone 1: Decompose Large Files

**Goal**: Break the 4 largest source files (1,300–1,700 lines each) into focused modules of <500 lines each, using extraction-without-rewriting. No breaking API/interface changes. All existing tests must stay green. Each extraction ships as its own atomic PR.

### Phase 1: weather_client_base.py — Extract Unit Conversion & Merge Logic
**Goal**: Reduce `weather_client_base.py` from 1,399 lines to <900 lines by extracting unit conversion helpers and merge logic into dedicated utility modules.

**Success criteria**:
- `weather_client_base.py` line count reduced by ≥30%
- New `utils/unit_conversion.py` module with all `_convert_*` helpers
- New `weather_client_merge.py` with `_merge_current_conditions` logic
- All existing tests pass
- New tests cover previously-uncovered extracted code
- Import forwarding in place where needed

### Phase 2: weather_client_nws.py — Extract Parsers Module
**Goal**: Extract the 4 large NWS parsing functions (~300 lines, lines 1235–end) and module-level helpers into `weather_client_nws_parsers.py`.

### Phase 3: app.py — Extract Windows Toast Identity & Timer Management
**Goal**: Extract the 440-line module-level Windows toast identity block into `windows_toast_identity.py`, and extract timer management into `app_timer_manager.py`.

### Phase 4: main_window.py — Extract Notification Event Handling
**Goal**: Extract notification event processing methods (~100 lines) into a mixin or helper module, reducing `main_window.py` complexity.
