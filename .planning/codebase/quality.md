# Code Quality — AccessiWeather

## Test Coverage Summary
- **Overall**: 76.1% (5,213 / 6,852 statements)
- **UI excluded** from measurement: `src/accessiweather/ui/` has `pragma: no cover` equivalent via pyproject.toml `omit`
- **weather_gov_api_client/** also excluded (auto-generated)

### Per-Target File Coverage
| File | Coverage | Covered | Missing |
|------|----------|---------|---------|
| `app.py` | 91.3% | 84 covered | 8 missing |
| `weather_client_base.py` | 63.4% | 256 covered | **148 missing** |
| `weather_client_nws.py` | 54.8% | 375 covered | **309 missing** |
| `main_window.py` | excluded from measurement | — | — |

### Hotspot: weather_client_nws.py
- Worst coverage of the 4 targets (54.8%)
- 309 uncovered lines — likely the large parsing functions `parse_nws_current_conditions` (1,235+), `parse_nws_forecast` (1,326+), `parse_nws_alerts` (1,385+), `parse_nws_hourly_forecast` (1,477+)
- Existing test: `tests/test_parsers.py` — may have gaps in edge cases

### Hotspot: weather_client_base.py
- 63.4% — 148 missing lines
- Unit conversion methods (lines 1355–1398), error handling paths, edge cases
- Many existing tests: `test_weather_client.py`, `test_weather_client_parallel.py`, etc.

## Type Annotations
- `from __future__ import annotations` used throughout (deferred evaluation)
- `TYPE_CHECKING` guards on heavy imports in `app.py`, `weather_client_base.py`
- **mypy + pyright** both configured; `mypy.ini` present

## Linting
- **ruff ≥ 0.9.0** — enforces E/W/F/I/D/UP/B/C4/PIE/SIM/RET rule sets
- Line length: 100
- Docstring rules (D2xx) partially relaxed: D100-D105 ignored (missing docstrings not enforced)
- C901 (complexity) ignored — managed via mccabe max-complexity = 15 in ruff.lint.mccabe
- `__init__.py` files allow F401 (unused imports, used for re-exports)

## Test Suite Structure
- **~130 test files** in `tests/`
- Subdirectories: `tests/gui/`, `tests/integration/`
- Fixtures in `tests/conftest.py`
- pytest plugins: mock, cov, asyncio, xdist (parallel), recording/VCR, rerunfailures, hypothesis
- Notable: `test_coverage_fix_pr449.py`, `test_coverage_gaps.py` — targeted coverage gap tests

## Documentation
- Docstrings present on most public methods (enforced on some rules; D101-D105 ignored)
- `IMPLEMENTATION_DETAILS.md`, `HOURLY_AQI_IMPLEMENTATION.md` — feature docs
- `knowledge.md` — domain knowledge reference
- `AGENTS.md` — AI agent instructions
- `CLAUDE.md` — Claude Code instructions

## Code Complexity Hotspots
- `app.py`: `OnInit` (~74 lines), `_maybe_auto_import_keys_file` (~80 lines), `_download_and_apply_update` (~80 lines)
- `weather_client_base.py`: main fetch orchestration method(s) and `_merge_current_conditions`
- `weather_client_nws.py`: `parse_nws_current_conditions` is likely 80–100 lines

## Import Hygiene
- Circular import risk managed via lazy imports (functions do `from .module import X` inline)
- `TYPE_CHECKING` blocks for cross-module type hints
- `app_initialization.py` uses lazy import for `WeatherClient` (line 67: `from .weather_client import WeatherClient`)
- `weather_client_enrichment.py` uses `TYPE_CHECKING` guard for `WeatherClient` import (no circular at runtime)
