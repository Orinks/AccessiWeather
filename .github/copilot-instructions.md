# AccessiWeather AI Coding Agent Instructions

AccessiWeather is a cross-platform accessible desktop weather app built with Python and wxPython. It targets Python 3.11+ and uses Nuitka packaging scripts for desktop artifacts.

## Architecture

- Entry point: `src/accessiweather/main.py`
- App orchestration: `src/accessiweather/app.py`
- UI: `src/accessiweather/ui/`
- Config: `src/accessiweather/config/`
- API clients: `src/accessiweather/api/`
- Weather orchestration: `src/accessiweather/weather_client.py`
- Alerts: `src/accessiweather/alert_manager.py` and `src/accessiweather/alert_notification_system.py`

Weather source strategy:

- NWS for supported US locations.
- Open-Meteo for international locations and non-alert fallback data.
- Visual Crossing for optional enhanced alert/weather data when configured.

## Development Commands

```bash
uv run accessiweather
pytest -n auto -v --tb=short
ruff check --fix . && ruff format .
pyright
python installer/build_nuitka.py
```

## wxPython Patterns

- Keep UI work on the wx main thread; use `wx.CallAfter` when crossing thread boundaries.
- Prefer existing `src/accessiweather/ui/` dialogs and helpers over adding new UI patterns.
- Add accessible names/descriptions/status text for new interactive controls.
- Preserve keyboard access and Escape/Cancel behavior in dialogs.
- Tests use the wx stub in `tests/conftest.py` by default. Use `ACCESSIWEATHER_ALLOW_REAL_WX_IN_TESTS=1` only for intentional real-wx checks.

## Testing

- Unit tests should mock external APIs and OS services.
- Add focused regression tests before fixes.
- Use integration tests only when cassette-backed or explicitly intended to touch live services.
- Run diff coverage for PRs when the CI gate is likely to care.

## Conventions

- Use modern type hints and `from __future__ import annotations`.
- Keep line length at 100 and let Ruff format imports/code.
- Update `CHANGELOG.md` for user-visible behavior.
- Use conventional commit messages and PR titles.
- Use `gh api` REST PATCH for PR metadata edits.
