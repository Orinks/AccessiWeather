# AGENTS.md - AccessiWeather Development Guide

## Build/Test Commands

```bash
# Development
briefcase dev                          # Run app with hot reload
pytest -v                             # Run all tests
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
```

## Architecture & Codebase Structure

**Main Package**: `src/accessiweather/` (Toga-based desktop app, Python 3.10+)

**Key Modules**:
- `app.py` - Main `AccessiWeatherApp(toga.App)` entry point
- `weather_client.py` - Orchestrates multi-source weather data (NWS, Open-Meteo, Visual Crossing)
- `alert_manager.py` + `alert_notification_system.py` - Handle weather alerts with rate limiting
- `config/` - `ConfigManager`, `AppSettings`, `LocationOperations` (JSON-based config)
- `api/` - Weather API wrappers (NWS, Open-Meteo, Visual Crossing)
- `ui_builder.py` - Toga UI construction; dialogs in `dialogs/`
- `cache.py` - 5-minute default TTL cache for API responses
- `background_tasks.py` - Async periodic weather updates via `asyncio.create_task()`

**Databases**: None; JSON config at `~/.config/accessiweather/accessiweather.json` (or portable directory)

## Code Style & Conventions

**Formatting**: Ruff (line length 100, double quotes, auto-import sorting). Pre-commit auto-formats before commit.

**Type Hints**: Modern syntax (`dict[str, Any]` not `Dict`); use `from __future__ import annotations` for forward refs.

**Async**: Use `await` for async functions; `asyncio.create_task()` for fire-and-forget; never `asyncio.run()` in Toga.

**Imports**: Ruff auto-sorts; group stdlib, third-party, local with blank lines; use `TYPE_CHECKING` guard for type-only imports.

**Toga Patterns**:
- OptionContainer: Use `.content.append(title, widget)` (two arguments, NOT tuple)
- ALL UI elements MUST have `aria_label` + `aria_description` (accessibility)
- Modal dialogs: Create with `toga.Window`, show with `.show()`, close with `.close()`
- Test with `TOGA_BACKEND=toga_dummy` env var

**Naming**: `snake_case` functions/vars, `PascalCase` classes, `UPPER_CASE` constants.

**Error Handling**: Defensive `getattr(obj, attr, default)` for attributes; async operations with try-except; rate-limit alerts.

**Docs**: See `.github/copilot-instructions.md` for detailed patterns and gotchas.

## CI/CD & Platform Specifics

**Workflows**:
- `briefcase-build.yml`: Matrix-based build for Windows (MSI) and macOS (DMG). Uses `installer/make.py`.
- `ci.yml`: Runs linting (Ruff) and unit tests (Pytest) on Ubuntu/Windows/macOS.

**Audio Support**:
- **Windows**: Uses `winsound` (stdlib) primarily.
- **macOS/Linux**: Uses `playsound3` (external dep) as `winsound` is unavailable.
- **Fallback**: `playsound3` is used as a fallback on Windows if `winsound` fails.

**Build Quirks**:
- **Windows Encoding**: `FORCE_COLOR="0"` must be set in CI to prevent `rich` library encoding crashes (`UnicodeEncodeError`).
- **Version Extraction**: CI extracts version directly from `pyproject.toml` using `tomllib`.

## Changelog Maintenance

Keep `CHANGELOG.md` updated with user-facing changes during development:

- **When to Add**: Any user-visible feature, fix, or change (UI, behavior, performance, appearance)
- **Where to Add**: Add to the "Unreleased" section under the appropriate subsection (Added, Changed, Fixed)
- **What to Skip**: Internal refactoring, CI/CD improvements, test-only changes, documentation-only updates, and developer-facing changes
- **Format**: Use plain language focused on what the user experiences, not implementation details
- **Example**: Instead of "Refactored cache layer to use stale-while-revalidate", write "Improved app responsiveness on slow connections with smarter caching"

When releasing, promote the "Unreleased" section to a new version entry with today's date.

## Writing Human-Authentic Changelogs & Release Notes

Avoid AI-generated writing patterns. Users should hear a person, not a chatbot:

**Avoid These AI Tells:**
- Over-predictable structure (topic sentence → summary sentence pattern)
- Passive voice ("API calls will be reduced" → use active: "You'll see 80% fewer API calls")
- Hedging language ("may improve," "tend to," on-the-one-hand-on-the-other-hand phrasing)
- Jargon without context; overly formal tone
- Perfect grammar everywhere; flawless transitions (ironically a red flag)
- Generic language ("enhanced," "optimized," "streamlined," "integrated")

**Write Like a Human:**
- Use contractions ("You're" not "You are")
- Vary sentence length and structure
- Be direct and specific: "Stop storing API keys in plain text" not "API credential storage mechanisms have been fortified"
- Take a clear stance; don't hedge
- Address the user directly ("You can now," "Your data is moved to")
- Include the why: "80%+ fewer API calls, noticeably faster on slower connections"
- Write as if explaining to a friend; cut unnecessary words
- Use active voice and short sentences when listing improvements

**Example Rewrite:**
- ❌ "Performance improvements have been implemented via cache-first design with background enrichment updates, resulting in reduced API calls"
- ✅ "Performance boost: We restructured how the app handles data. Now it serves cached results instantly while refreshing in the background—80%+ fewer API calls, noticeably faster on slower connections."

## Branching & Merge Strategy

To avoid massive merge conflicts and ensure repository health:

1. **Frequent Merges**: Regularly merge `main` into `dev` (or your feature branch) to keep it up-to-date.
2. **Feature Branches**: Use short-lived feature branches branched from `dev`. Merge back to `dev` frequently.
3. **Release Flow**: Treat `dev` as the upstream for `main`. Never commit directly to `main`. Hotfixes on `main` must be immediately backported to `dev`.
