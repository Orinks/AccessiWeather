<!-- This file mirrors AGENTS.md. Edit AGENTS.md as the primary source. -->

# AI Agent Guidelines - AccessiWeather

**Role:** You are an expert Python Desktop Application Engineer and Technical Lead specializing in accessible, cross-platform GUI applications.
You are responsible for the entire lifecycle of a task: understanding requirements, planning, implementing, testing, and ensuring accessibility compliance.

---

## Quick Reference Commands

```bash
# Development
briefcase dev                          # Run app with hot reload
pytest -v                             # Run all tests (serial)
pytest -n auto                        # Run all tests (parallel, ~4x faster)
pytest tests/test_file.py::test_func  # Run single test
pytest -k "test_name" -v              # Run tests matching pattern
pytest --lf --ff -m "unit"            # Run last-failed/first-failed unit tests

# Linting & Formatting
ruff check --fix . && ruff format .   # Lint + format code (line length: 100)
pyright                               # Type checking (excludes tests/)

# Build & Package
briefcase create                      # Create platform-specific skeleton
briefcase build                       # Build app bundle
briefcase package                     # Generate installers (MSI/DMG/AppImage)
python installer/make.py dev          # Helper wrapper around Briefcase

# Git (Windows)
# Use --no-pager BEFORE the subcommand to prevent hanging on Windows
git --no-pager log --oneline -5       # View recent commits
git --no-pager diff                   # View changes without pager
git --no-pager show HEAD              # Show last commit
```

---

## Project Overview

**AccessiWeather** is a cross-platform desktop weather application built with Python and Toga (BeeWare framework), focusing on screen reader accessibility. It provides weather data from multiple sources (NWS, Open-Meteo, Visual Crossing) with real-time alerts.

### Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.10+ |
| GUI Framework | Toga (BeeWare) |
| HTTP Client | httpx (async) |
| Build Tool | Briefcase |
| Testing | pytest, pytest-asyncio, hypothesis |
| Linting | Ruff (format + lint) |
| Type Checking | Pyright |
| Package Format | pyproject.toml (PEP 517) |

---

## Architecture & Codebase Structure

**Main Package**: `src/accessiweather/`

### Core Modules

| Module | Purpose |
|--------|---------|
| `app.py` | Main `AccessiWeatherApp(toga.App)` entry point |
| `weather_client.py` | Orchestrates multi-source weather data (NWS, Open-Meteo, Visual Crossing) |
| `alert_manager.py` | Weather alert management with rate limiting |
| `alert_notification_system.py` | Desktop notifications for weather alerts |
| `background_tasks.py` | Async periodic weather updates via `asyncio.create_task()` |
| `cache.py` | 5-minute default TTL cache for API responses |
| `ui_builder.py` | Toga UI construction |

### Configuration (`config/`)

| Module | Purpose |
|--------|---------|
| `config_manager.py` | Main configuration orchestration |
| `settings.py` | `AppSettings` dataclass |
| `locations.py` | `LocationOperations` for saved locations |
| `secure_storage.py` | Keyring-based API key storage |
| `source_priority.py` | Weather source priority configuration |

### API Clients (`api/`)

| Module | Purpose |
|--------|---------|
| `base_wrapper.py` | Abstract base for API wrappers |
| `openmeteo_wrapper.py` | Open-Meteo API integration |
| `openrouter_models.py` | AI model configuration for explanations |

### Dialogs (`dialogs/`)

| Module | Purpose |
|--------|---------|
| `settings_dialog.py` | Settings configuration UI |
| `location_dialog.py` | Location management UI |
| `air_quality_dialog.py` | Air quality details display |
| `aviation_dialog.py` | Aviation weather (METAR/TAF) |
| `weather_history_dialog.py` | Historical weather comparison |

### Data Storage

- **Config Location**: `~/.config/accessiweather/accessiweather.json` (or portable directory)
- **No Database**: JSON-based configuration only
- **API Keys**: Stored securely via `keyring`

---

## Code Style & Conventions

### Formatting Rules

- **Tool**: Ruff (line length 100, double quotes, auto-import sorting)
- **Pre-commit**: Auto-formats before commit
- **Type Hints**: Modern syntax (`dict[str, Any]` not `Dict`)
- **Forward Refs**: Use `from __future__ import annotations`

### Import Organization

```python
from __future__ import annotations

import asyncio                          # stdlib
from typing import TYPE_CHECKING

import toga                             # third-party
import httpx

from .config import ConfigManager       # local imports
from .weather_client import WeatherClient

if TYPE_CHECKING:                       # type-only imports
    from .alert_manager import AlertManager
```

### Async Patterns

```python
# DO: Use await for async functions
data = await weather_client.fetch_weather()

# DO: Use asyncio.create_task() for fire-and-forget
asyncio.create_task(background_refresh())

# DON'T: Never use asyncio.run() in Toga (conflicts with event loop)
```

### Toga-Specific Patterns

```python
# OptionContainer: Two arguments, NOT tuple
container.content.append("Tab Title", widget)  # Correct
container.content.append(("Tab Title", widget))  # WRONG

# ALL UI elements MUST have accessibility attributes
button = toga.Button(
    "Refresh",
    on_press=self.refresh,
    aria_label="Refresh weather data",
    aria_description="Click to fetch latest weather information"
)

# Modal dialogs
dialog = toga.Window(title="Settings")
dialog.show()   # Show
dialog.close()  # Close

# Testing with dummy backend
# Set TOGA_BACKEND=toga_dummy in tests
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions/Variables | snake_case | `fetch_weather_data` |
| Classes | PascalCase | `WeatherClient` |
| Constants | UPPER_CASE | `DEFAULT_TIMEOUT` |
| Private | Leading underscore | `_internal_cache` |

### Error Handling

```python
# Defensive attribute access
value = getattr(obj, 'attr', default_value)

# Async operations with try-except
try:
    data = await fetch_data()
except httpx.TimeoutException:
    logger.warning("Request timed out")
    return cached_data
```

---

## Testing Guidelines

### Test Organization

- **Unit tests**: `tests/test_*.py` (mocked dependencies)
- **Integration tests**: `tests/integration/` (real API calls, VCR cassettes)
- **Property tests**: Use Hypothesis for edge cases

### Running Tests

```bash
# All tests (parallel)
pytest -n auto -v --tb=short

# Exclude integration tests
pytest tests/ -m "not integration" -n auto

# Single test with output
pytest tests/test_weather_client.py::test_fetch -v -s

# Property tests with thorough profile
pytest --hypothesis-profile=thorough
```

### Test Fixtures

```python
# conftest.py sets up toga_dummy backend automatically
# Use mock_simple_weather_apis fixture for API mocking

def test_weather_fetch(mock_simple_weather_apis):
    # APIs are mocked, safe to test
    pass
```

### Hypothesis Profiles

| Profile | Examples | Use Case |
|---------|----------|----------|
| `ci` | 25 | Fast CI runs |
| `dev` | 50 | Development |
| `thorough` | 200 | Release validation |

---

## CI/CD Configuration

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push to main/dev, PRs | Linting, tests on Ubuntu/Windows/macOS |
| `briefcase-build.yml` | After CI passes on dev | Build MSI/DMG installers |
| `briefcase-release.yml` | Tags (v*.*.*) | Create GitHub releases |
| `integration-tests.yml` | Nightly | Record VCR cassettes |
| `update-pages.yml` | After builds | Update GitHub Pages downloads |

### CI Environment Variables

```yaml
FORCE_COLOR: "0"           # Prevent rich encoding crashes on Windows
PYTHONUTF8: "1"            # Force UTF-8 encoding
ACCESSIWEATHER_TEST_MODE: "1"  # Enable test mode
HYPOTHESIS_PROFILE: ci     # Fast property tests
TOGA_BACKEND: toga_dummy   # Headless UI testing
```

### Build Matrix

| Platform | Output | Notes |
|----------|--------|-------|
| Windows | `.msi` installer, `.zip` portable | Includes pythonnet for WinForms |
| macOS | `.dmg` installer | Universal build (Intel + ARM) |

### Audio Support

| Platform | Primary | Fallback |
|----------|---------|----------|
| Windows | `winsound` (stdlib) | `playsound3` |
| macOS/Linux | `playsound3` | - |

---

## Git Workflow

### Branch Strategy

| Branch | Purpose | CI/CD |
|--------|---------|-------|
| `main` | Stable releases only | Tagged releases |
| `dev` | Active development | Nightly builds, GitHub Pages |
| `feature/*` | Feature work | PRs to dev |
| `hotfix/*` | Critical fixes | Merge to both main and dev |

### Commit Message Format

```
type(scope): description

[optional body]

Types: feat, fix, docs, style, refactor, test, chore
```

**Examples:**
```
feat(alerts): add rate limiting for weather notifications
fix(ui): resolve screen reader focus issue in settings dialog
chore(deps): update httpx to 0.28.1
```

### Branch Naming

```
feature/<ticket>-<description>    # feature/123-add-radar-view
fix/<ticket>-<description>        # fix/456-alert-crash
hotfix/<description>              # hotfix/critical-api-timeout
```

### Merge Strategy

1. **Feature branches**: Short-lived, PR to `dev`
2. **Releases**: Merge `dev` to `main`, tag with version
3. **Hotfixes**: Branch from `main`, merge to both `main` and `dev`

### Creating Releases

```bash
# 1. Ensure dev is ready
git checkout dev && git push origin dev

# 2. Merge to main and tag
git checkout main
git merge dev --no-ff -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags
```

---

## Security Guidelines

### Environment Variables

- **Never commit** `.env` files (use `.env.example` as template)
- **API keys** stored via `keyring` (system keychain)
- **Test mode** uses mock data, never real credentials

### API Key Storage

```python
# Secure storage via keyring
from .config.secure_storage import SecureStorage

storage = SecureStorage()
storage.set_api_key("visual_crossing", "your-api-key")
key = storage.get_api_key("visual_crossing")
```

### Input Validation

- Validate coordinates (latitude: -90 to 90, longitude: -180 to 180)
- Sanitize location names before display
- Use `httpx` with timeout limits (prevent hangs)

### Sensitive Data Handling

```python
# DON'T log API keys
logger.info(f"Using key: {api_key}")  # WRONG

# DO mask sensitive data
logger.info(f"Using key: {api_key[:4]}...")  # OK
```

---

## Accessibility Requirements

**All UI must be screen reader compatible:**

1. **Every interactive element** needs `aria_label` and `aria_description`
2. **Keyboard navigation** must work for all features
3. **Focus management** - dialogs should trap focus appropriately
4. **Status announcements** - use live regions for updates

```python
# Example accessible button
toga.Button(
    "Check Weather",
    on_press=self.check_weather,
    aria_label="Check weather",
    aria_description="Fetches current weather for your selected location"
)

# Example accessible table
toga.Table(
    headings=["Alert Type", "Severity", "Description"],
    aria_label="Weather alerts table",
    aria_description="List of active weather alerts for your area"
)
```

---

## Changelog Maintenance

Keep `CHANGELOG.md` updated with user-facing changes:

### When to Add

- User-visible features, fixes, or changes
- UI, behavior, performance, appearance changes

### What to Skip

- Internal refactoring, CI/CD improvements
- Test-only changes, documentation updates
- Developer-facing changes

### Writing Style

Write like a human, not a chatbot:

```markdown
# DON'T
- Performance improvements have been implemented via cache-first design

# DO
- Performance boost: Now serves cached results instantly while refreshing
  in the background - 80%+ fewer API calls
```

**Avoid**: Passive voice, hedging language, generic terms ("enhanced", "optimized")
**Use**: Contractions, direct address ("You can now..."), specific benefits

---

## Common Gotchas

1. **Windows Git**: Use `--no-pager` to prevent terminal hangs
2. **Toga OptionContainer**: Use two args, not tuple
3. **asyncio.run()**: Never use in Toga (use `create_task`)
4. **Pre-commit hooks**: Format before committing
5. **TOGA_BACKEND**: Set to `toga_dummy` for headless tests
6. **Encoding on Windows CI**: Set `FORCE_COLOR=0` to prevent crashes

---

## Documentation References

| Document | Purpose |
|----------|---------|
| `CONTRIBUTING.md` | Contribution guidelines |
| `docs/git-workflow.md` | Detailed git workflow |
| `docs/ACCESSIBILITY.md` | Accessibility standards |
| `docs/user_manual.md` | End-user documentation |
| `.github/workflows/README.md` | CI/CD workflow details |
