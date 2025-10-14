# Repository Guidelines

## Project Structure & Module Organization
AccessiWeather is a Python application packaged under `src/accessiweather`, with UI logic, API clients, and services grouped by feature (for example `display/` for widgets and `api/` for data access). Automated checks live in `tests`, helper scripts in `scripts`, packaging helpers in `installer`, and long-form references in `docs`. Runtime assets (icons, sound packs, templates) remain within `resources` and `soundpacks`, and quick-start snippets are kept in `examples`.

## Build, Test, and Development Commands
- `source venv/bin/activate` — enter the shared virtual environment before any development work.
- `pip install -e ".[dev]"` — install the app and dev-only tooling into the active environment.
- `briefcase dev` — launch the desktop app with BeeWare’s live-reload workflow.
- `python installer/make.py dev` — alternate launcher that mirrors `briefcase dev`.
- `ruff check .` / `ruff format` — run static analysis and formatting.
- `mypy src` — validate typing across the codebase.

## Coding Style & Naming Conventions
Code targets Python 3.12 with Ruff enforcing PEP 8-compatible spacing (4-space indents, 100-character lines) and double-quoted strings. Favor explicit imports grouped with Ruff’s isort profile. Modules and packages use `snake_case`, classes use `PascalCase`, async helpers end with `_async`, and comments explain only non-obvious intent.

## Testing Guidelines
Adopt TDD: add or adjust tests before changing production code. Tests live in `tests` mirroring the `src` layout; name files `test_<module>.py` and functions `test_<behavior>`. Run the suite from an activated environment using `pytest -q`, or `pytest --cov=accessiweather` for coverage checks. Use `pytest -k "<pattern>"` to focus on a failing path, prefer fixtures over ad-hoc setup, and lean on the bundled dummy Toga bindings when exercising UI logic. Ensure each feature lands with regression coverage before closing the task.

## Commit & Pull Request Guidelines
Follow Conventional Commits (`feat:`, `fix:`, `ci:`, `chore:`) as seen in the history, referencing task IDs when available. Group related changes into cohesive commits and write messages in the imperative mood. Pull requests should summarize scope, list testing commands executed (for example `source venv/bin/activate && pytest -q`), and link to issues or release notes. Include screenshots or screen-reader transcripts when UI changes affect accessibility. Request review only after CI is green and Ruff, MyPy, and pytest have been run locally.
