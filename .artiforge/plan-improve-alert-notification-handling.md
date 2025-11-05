# ArtiForge Development Plan: Improve Alert Notification Handling

**Generated:** 2025-11-05
**Task:** Improve alert notification handling in AccessiWeather to enhance reliability, user experience, and code maintainability.

---

## Step 1: Code Audit

**Action:** Perform a comprehensive code audit of `src/accessiweather/alert_manager.py` and `src/accessiweather/alert_notification_system.py`. Identify:
- Magic numbers related to severity, cooldown, and rate limits.
- Duplicate logic between AlertManager and AlertNotificationSystem (e.g., formatting, rate‑limit checks).
- Gaps in alert history tracking (only a single hash stored).
- Accessibility shortcomings in notification messages (missing screen‑reader friendly text).
- Points where UI updates occur off the main thread.

**Reasoning:** This audit creates a definitive map of current issues, ensuring that subsequent refactoring targets the right locations without overlooking hidden dependencies.

**Implementation Details:**
- Clone the repository locally (if not already) and open the two target files.
- Use static analysis (`ruff check --select PLR2004,FA100,FA102`) to locate magic numbers.
- Search for repeated code blocks (e.g., `if severity >= ...` or `self._notify(...)`).
- Document each finding in a markdown table (file, line, issue, suggested fix).
- Verify that all UI updates use `app.add_background_task` or `self.window.app.schedule` to stay on the main thread.
- Produce a mermaid class diagram showing current relationships between `AlertManager`, `AlertState`, `AlertSettings`, `AlertNotificationSystem`, and `SafeDesktopNotifier`.

**Error Handling:** If the audit script crashes due to import errors, fall back to manual inspection. Ensure the environment variable `TOGA_BACKEND=toga_dummy` is set to avoid GUI initialization errors during static analysis.

**Testing:** Run the existing test suite (`pytest -q`) after the audit to confirm that no tests are broken before modifications.

**Tip:** Automate the magic‑number search with a small script using `ast` to speed up future audits.

**Question:** Do you want the audit results saved as `docs/alert_audit_report.md`?

---

## Step 2: Introduce Constants Module

**Action:** Introduce a dedicated `constants.py` module under `src/accessiweather/` to house all numeric thresholds and default configuration values:
```python
# src/accessiweather/constants.py
from __future__ import annotations

SEVERITY_PRIORITY: dict[str, int] = {
    "Minor": 1,
    "Moderate": 2,
    "Severe": 3,
    "Extreme": 4,
}
DEFAULT_COOLDOWN_SECONDS = 300  # 5‑minute default
MAX_NOTIFICATIONS_PER_HOUR = 12
```
Replace every hard‑coded magic number with a reference to these constants.

**Reasoning:** Centralizing constants eliminates PLR2004 warnings, simplifies future adjustments, and makes the values discoverable for users and developers.

**Implementation Details:**
- Add the new file with a module docstring.
- Update imports in `alert_manager.py` and `alert_notification_system.py` (`from .constants import ...`).
- Modify any inline numbers (e.g., `if severity_level >= 3:` → `if severity_level >= SEVERITY_PRIORITY["Severe"]:`).
- Ensure type hints use modern syntax (`dict[str, int]`).
- Run `ruff check --fix` to automatically replace some literals.

**Error Handling:** If an import fails due to circular dependencies, place the constants import at the top of each file after standard library imports and before local imports.

**Testing:**
- Add unit tests in `tests/test_constants.py` that verify the mapping and default values.
- Update existing tests that previously relied on magic numbers to import the constants.

**Tip:** Document the constants in the README under a "Configuration" section for end‑users.

---

## Step 3: Refactor AlertState with History

**Action:** Refactor `AlertState` (currently in `alert_manager.py`) to maintain a bounded history of content hashes with timestamps. Implement methods:
- `add_hash(hash: str) -> None`
- `has_changed(new_hash: str) -> bool`
- `is_escalated(new_priority: int) -> bool`
Store history in a `deque[maxlen=5]` to limit memory usage.

**Reasoning:** Richer history enables accurate change detection, escalation detection beyond a simple priority comparison, and prevents duplicate notifications during rapid updates.

**Implementation Details:**
- Import `collections.deque`.
- Replace the single `content_hash: str | None` attribute with `hash_history: deque[tuple[str, float]]`.
- In `add_hash`, append `(hash, time.time())`.
- `has_changed` checks the most recent hash; if different, returns True.
- `is_escalated` compares the new priority with the highest priority seen in history.
- Add appropriate `@property` methods for current hash and last notification time.
- Update all usages of `AlertState` throughout the codebase to reflect new API.

**Error Handling:** Guard against empty history when `has_changed` or `is_escalated` is called; default to `True` for change detection on first run.

**Testing:**
- Create parametrized tests (`tests/test_alert_state.py`) covering:
  * Initial state has no history.
  * Adding the same hash does not indicate a change.
  * Adding a new hash indicates a change.
  * Escalation detection when a higher priority appears in history.
- Use `freezegun` or monkeypatch `time.time` to control timestamps.

**Tip:** Consider exposing the `maxlen` as a configurable setting in `AlertSettings` for power users.

---

## Step 4: Rewrite Core Alert Processing Loop

**Action:** Rewrite the core alert processing loop in `AlertManager` to:
1. Retrieve alerts from the API wrappers (NWS → fallback → Visual Crossing).
2. For each incoming alert, compute a deterministic hash (e.g., SHA‑256 of JSON payload).
3. Use the new `AlertState` methods to decide if the alert is new, updated, or escalated.
4. Apply rate‑limit logic using a token‑bucket approach (tokens refill at `MAX_NOTIFICATIONS_PER_HOUR / 3600` per second).
5. Respect user‑configured cooldown (`AlertSettings.cooldown_seconds`). If the last notification for this alert was sent within the cooldown, suppress it.
6. Pass the finalized alert to `AlertNotificationSystem` for rendering.

**Reasoning:** This redesign consolidates change detection, escalation handling, and rate limiting into a single, well‑tested workflow, eliminating duplicated checks and edge‑case failures.

**Implementation Details:**
- Create a helper async method `_rate_limiter()` inside `AlertManager` that updates a `self._tokens` float and returns `True`/`False`.
- On each iteration, call `await self._rate_limiter()`. If False, log and skip notification.
- Use `hashlib.sha256(json.dumps(alert, sort_keys=True).encode()).hexdigest()` for hashing.
- Ensure all async calls are awaited; wrap API calls with `asyncio.wait_for` (timeout 10 s) to prevent hangs.
- Use `app.add_background_task` to schedule the processing loop; UI updates (e.g., badge count) must be dispatched via `app.schedule`.

**Error Handling:**
- If an API call raises `httpx.HTTPError`, log the error, fall back to the next provider, and continue.
- On unexpected payload structures, catch `KeyError`/`TypeError`, mark the alert as malformed, and skip notification.
- If rate limiter fails (e.g., negative tokens), reset token count to `MAX_NOTIFICATIONS_PER_HOUR / 3600`.

**Testing:**
- Mock API wrappers with `pytest-asyncio` and `unittest.mock` to emit controlled alert streams.
- Verify that:
  * Duplicate alerts within cooldown are not notified.
  * Escalated alerts bypass cooldown (if policy permits) and are flagged.
  * Rate limiting caps notifications per hour.
  * Errors in one provider trigger fallback without crashing the loop.

**Tip:** Implement a small logging helper (`log_debug`, `log_info`, `log_warning`) to keep the loop readable.

**Question:** Should the rate‑limit token bucket be user‑configurable via `AlertSettings`?

---

## Step 5: Enhance AlertNotificationSystem Accessibility

**Action:** Enhance `AlertNotificationSystem` to generate screen‑reader friendly messages:
- Add `aria_label` and `aria_description` to every notification widget.
- Create a helper `format_accessible_message(alert: WeatherAlert) -> str` that includes severity, headline, and a brief plain‑language summary.
- Ensure the text passed to `SafeDesktopNotifier` is concise but contains the same information for auditory feedback.

**Reasoning:** Improving accessibility aligns with the core mission of AccessiWeather and ensures that visually impaired users receive the same critical information.

**Implementation Details:**
- In `alert_notification_system.py`, import `toga` and use `toga.Label` with `aria_label`/`aria_description`.
- Update the `notify` method to build the accessible message and pass it to `SafeDesktopNotifier`.
- Add unit tests for the formatter covering all severity levels and missing fields.
- Update any UI dialogs that display alerts to include the same attributes.

**Error Handling:**
- If an alert lacks a headline, fallback to `alert.event` or a generic "Weather alert".
- Guard against `None` values in optional fields; substitute with "N/A".

**Testing:**
- Write tests in `tests/test_notification_format.py` that assert the presence of `aria_label` and correct phrasing.
- Use the dummy Toga backend to instantiate widgets without a display.

**Tip:** Leverage Python f‑strings for clear message construction and keep line length <100 characters.

---

## Step 6: Audit UI Components for Accessibility

**Action:** Audit all UI components that present alert information (e.g., `ui_builder.py`, settings dialogs). Add missing `aria_label` and `aria_description` attributes, and verify keyboard navigation order using Tab/Shift+Tab.

**Reasoning:** Consistent accessibility across the entire UI prevents regression and ensures compliance with the project's accessibility policy.

**Implementation Details:**
- Search for `toga.Button`, `toga.Label`, `toga.OptionContainer` creations related to alerts.
- For each widget, add:
```python
widget.aria_label = "Alert severity: Severe"
widget.aria_description = "Thunderstorm with heavy rain expected until 3 PM."
```
- Use `OptionContainer.content.append(title, widget)` with exactly two arguments as required.
- Run a manual keyboard navigation test on a development machine (or use an automated accessibility tester if available).

**Error Handling:** If a widget does not expose `aria_label` (unlikely with Toga), wrap it in a `toga.Box` that does.

**Testing:**
- Add UI integration tests in `tests/test_ui_accessibility.py` using the `toga_dummy` backend to assert that every alert‑related widget has the two attributes.
- Include a regression test that simulates Tab navigation depth.

**Tip:** Document the accessibility conventions in `docs/ACCESSIBILITY.md` for future contributors.

---

## Step 7: Update Configuration Schema

**Action:** Update the configuration schema (`src/accessiweather/models/config.py`) to persist new settings:
- `cooldown_seconds` (int, default `DEFAULT_COOLDOWN_SECONDS`)
- `max_notifications_per_hour` (int, default `MAX_NOTIFICATIONS_PER_HOUR`)
- `severity_threshold` (list[str], default `["Severe", "Extreme"]`)

**Reasoning:** Storing these values allows users to customize the new behavior without editing code.

**Implementation Details:**
- Extend `AlertSettings` dataclass with the new fields, using `attrs` defaults.
- Update `ConfigManager` to read/write these fields from the JSON config file.
- Add migration logic: if older config files lack the new keys, inject defaults on load.
- Ensure backward compatibility by handling missing keys gracefully.

**Error Handling:** Wrap config loading in a `try/except` block; on `KeyError`, merge defaults and rewrite the file.

**Testing:**
- Add tests in `tests/test_config_migration.py` that load a legacy config (without new keys) and verify that defaults are added.
- Verify that round‑trip save/load preserves the new settings.

**Tip:** Expose the new options in the Settings UI (`settings_handlers.py`) with appropriate sliders or dropdowns.

---

## Step 8: Run Full Test Suite with Coverage

**Action:** Run the full test suite with coverage, enforce 80%+ coverage, and address any failures:
- Execute `pytest --cov=src --cov-report=term-missing`.
- Fix failing tests caused by the refactor.
- Add missing tests to reach the coverage target.

**Reasoning:** Ensuring high test coverage guarantees that the new logic behaves as expected and protects against regressions.

**Implementation Details:**
- Update `pyproject.toml` to set `ruff` line‑length to 100 and include `ruff format` as a pre‑commit hook.
- Add a GitHub Actions workflow step (if not present) to run `ruff check --fix` and the coverage report.

**Error Handling:** If coverage falls short, identify uncovered branches in `AlertManager` and add targeted tests.

**Testing:** All tests run in the dummy Toga backend; verify that `TOGA_BACKEND=toga_dummy` is exported in CI.

**Tip:** Use `pytest.mark.integration` for tests that hit real APIs (mocked in CI) and keep them separate from unit tests.

---

## Step 9: Code Formatting and Linting

**Action:** Perform code formatting and linting across the entire codebase:
- Run `ruff format .` to auto‑format.
- Run `ruff check --fix .` to automatically correct style violations.
- Verify that no new PLR2004 (magic number) warnings appear.

**Reasoning:** Consistent formatting and linting keep the repository clean and reduce future maintenance overhead.

**Implementation Details:**
- Ensure `ruff` version in `pyproject.toml` matches `0.9.0+`.
- Commit the formatted changes as a separate commit for traceability.

**Error Handling:** If `ruff` fails due to syntax errors introduced during refactor, revert the problematic file and fix syntax first.

**Testing:** Run `ruff check` in CI after each push to guarantee compliance.

**Tip:** Enable pre‑commit hooks locally (`pre-commit install`) to catch style issues early.

---

## Step 10: Update Documentation

**Action:** Update documentation:
- Add a "Alert System Improvements" section in `README.md` describing the new cooldown, rate‑limit, and accessibility features.
- Refresh docstrings in all modified public classes and functions.
- Include a usage example showing how to customize `AlertSettings` via the Settings UI.

**Reasoning:** Clear documentation helps users understand the new capabilities and assists developers in future maintenance.

**Implementation Details:**
- Use triple‑quoted docstrings with `:param:` and `:returns:` annotations.
- Ensure docs render correctly with `mkdocs` if the project uses it.

**Error Handling:** Run `pydocstyle` to ensure docstring completeness; fix any missing sections.

**Testing:** No automated tests needed, but perform a manual build of the docs (`mkdocs build`) to verify there are no warnings.

**Tip:** Link to the new `ACCESSIBILITY.md` from the main README for visibility.

---

## Execution Rules

For every step:
1. **ALWAYS** Read the entire step_content tag
2. **ALWAYS** Extract key technical requirements and constraints
3. **ALWAYS** Show reasoning to the user
4. **ALWAYS** Show a mermaid diagram if applicable
5. Offer a tip to enhance the step
6. Ask questions if clarification needed
7. **ALWAYS** Ask user for confirmation before executing
8. **ALWAYS AFTER** user confirms, call Artiforge "act-as-agent" tool and execute
