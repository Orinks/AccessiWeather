# AI Agent Guidelines - AccessiWeather

**Role:** You are an expert Python Desktop Application Engineer and Technical Lead specializing in accessible, cross-platform wxPython applications.
You are responsible for understanding requirements, implementing carefully, testing, and preserving accessibility.

---

## Quick Reference Commands

```bash
# Development
uv run accessiweather                 # Run the app from source
pytest -v                             # Run all tests serially
pytest -n auto                        # Run all tests in parallel
pytest tests/test_file.py::test_func  # Run one test
pytest -k "test_name" -v              # Run tests matching a pattern
pytest --lf --ff -m "unit"            # Run last-failed/first-failed unit tests

# Linting & Formatting
ruff check --fix . && ruff format .   # Lint and format code
pyright                               # Type checking; may be scoped for noisy legacy areas

# Build & Package
python installer/build_nuitka.py      # Build packaged app artifacts
python installer/build.py --dev       # Run installer build helper in development mode

# Git on Windows
git --no-pager log --oneline -5
git --no-pager diff
git --no-pager show HEAD
```

---

## Project Overview

AccessiWeather is a cross-platform accessible desktop weather application built with Python and wxPython. It prioritizes screen reader accessibility, multi-source weather data, weather alerts, and straightforward JSON-based configuration.

### Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| GUI Framework | wxPython |
| HTTP Client | httpx |
| Build Tool | Nuitka packaging scripts |
| Testing | pytest, pytest-asyncio, pytest-xdist, hypothesis |
| Linting | Ruff |
| Type Checking | Pyright |
| Package Format | pyproject.toml |

---

## Architecture & Codebase Structure

**Main Package:** `src/accessiweather/`

| Module | Purpose |
|--------|---------|
| `app.py` | Main wxPython application orchestration |
| `main.py` | Console/GUI entry point |
| `weather_client.py` | Multi-source weather data orchestration |
| `alert_manager.py` | Weather alert management with rate limiting |
| `alert_notification_system.py` | Desktop notifications for weather alerts |
| `background_tasks.py` | Async periodic weather updates |
| `cache.py` | Weather API response caching |
| `ui/` | wxPython windows, dialogs, and UI helpers |
| `config/` | Settings, saved locations, secure storage, and source priority |
| `api/` | NWS, Open-Meteo, Visual Crossing, and related API clients |

### Data Storage

- Config is JSON-based, stored in the user config directory or a portable directory.
- API keys are stored through keyring-backed secure storage.
- There is no database.

---

## Code Style & Conventions

- Use Ruff formatting: 100-character line length, double quotes, sorted imports.
- Prefer modern type hints: `dict[str, Any]`, `Location | None`, and `from __future__ import annotations`.
- Keep files under 1000 lines where practical; split large modules before growing them further.
- Preserve unrelated user or agent changes in the working tree.
- Add focused comments only when they explain non-obvious behavior.

### Async Patterns

```python
# DO: await async functions
data = await weather_client.fetch_weather()

# DO: schedule background work through the app's existing scheduler or asyncio task helpers
asyncio.create_task(background_refresh())

# DON'T: call asyncio.run() from GUI code
```

### wxPython Patterns

- Keep UI work on the wx main thread; use `wx.CallAfter` when crossing thread boundaries.
- Prefer existing dialog/window helpers and local UI conventions over introducing new frameworks.
- All new interactive controls need accessible labels or names, useful descriptions where supported, keyboard access, and sensible focus behavior.
- Tests normally use the in-repo wx stub from `tests/conftest.py`; set `ACCESSIWEATHER_ALLOW_REAL_WX_IN_TESTS=1` only when a real wxPython smoke test is required.

---

## Testing Guidelines

- Unit tests live under `tests/test_*.py` and should mock external services.
- GUI-focused tests may use the wx stub or live wx under xvfb/Windows only when needed.
- Integration tests live under `tests/integration/` and should avoid live API dependence unless explicitly intended.
- Use Hypothesis for broad input-space edge cases.

```bash
pytest -n auto -v --tb=short
pytest tests/ -m "not integration" -n auto
pytest tests/test_weather_client.py::test_fetch -v -s
pytest --hypothesis-profile=thorough
```

---

## CI/CD

| Workflow | Purpose |
|----------|---------|
| `ci.yml` | Linting, tests, changelog check, coverage gate |
| `build.yml` | Nuitka desktop build artifacts |
| `integration-tests.yml` | Scheduled integration cassette checks |
| `update-pages.yml` | GitHub Pages/download updates |

Important CI environment defaults:

```yaml
FORCE_COLOR: "0"
PYTHONUTF8: "1"
ACCESSIWEATHER_TEST_MODE: "1"
HYPOTHESIS_PROFILE: ci
```

---

## Git Workflow

- Use conventional commits and conventional PR titles.
- Branch from `dev` for normal feature/fix work.
- PRs should normally target `dev`.
- Use `gh api` REST `PATCH` calls for PR metadata updates instead of `gh pr edit`.
- Use `git --no-pager` for Git inspection commands on Windows.

---

## Security Guidelines

- Never commit `.env` files or API keys.
- Store API keys via `SecureStorage`.
- Validate coordinates: latitude `-90..90`, longitude `-180..180`.
- Sanitize user-provided strings before logging.
- Keep HTTP timeouts on external requests.

---

## Accessibility Requirements

- Every interactive UI element must be reachable by keyboard.
- Controls need clear accessible names and useful descriptions/status text.
- Dialogs should set initial focus intentionally and preserve normal keyboard escape/cancel behavior.
- Dynamic updates should be announced or reflected in status text when useful to screen reader users.

---

## Changelog Maintenance

Update `CHANGELOG.md` under `[Unreleased]` for user-visible features, fixes, UI behavior, performance, or packaging changes.

Write entries like a human:

```markdown
- Detected current locations outside the US now get an editable place name when reverse geocoding can identify the coordinates.
```

Skip changelog entries for internal-only refactors, test-only work, and CI plumbing unless users are affected.
