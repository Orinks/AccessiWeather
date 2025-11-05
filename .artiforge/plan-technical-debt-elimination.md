# Technical Debt Elimination Plan for AccessiWeather

## Overview
Comprehensive technical debt elimination project focusing on:
- Enforcing toga_dummy backend for all UI tests (CRITICAL)
- Removing redundant tests while maintaining 80%+ coverage
- Eliminating code smells and architectural issues
- Improving performance, type safety, and error handling
- Cleaning up configuration and documentation
- Removing dead code

---

## Step 1: Set up Clean Development Environment

**Action:** Set up a clean development environment and ensure the TOGA_BACKEND is forced to `toga_dummy` for all test runs.

**Reasoning:** All UI widget tests must run against the dummy backend; any stray real backend import will cause failures and violate the critical requirement.

**Implementation Details:**
- Create a dedicated virtual environment (Python 3.12)
- Install project dependencies from `pyproject.toml`
- Add `export TOGA_BACKEND=toga_dummy` (Linux/macOS) or set the env var in `pytest.ini` via `addopts = -W ignore::DeprecationWarning --env TOGA_BACKEND=toga_dummy`
- Verify that `toga_dummy` is available (`pip install toga_dummy` if needed)
- Run `pytest -q` to confirm all tests pass before modifications

**Error Handling:**
- If `toga_dummy` cannot be imported, abort and report missing package
- If any test crashes because of real backend usage, note the file and line for later fixing

**Testing:**
- Execute full test suite with coverage (`pytest --cov=src/accessiweather --cov-report=term-missing`)
- Capture baseline coverage numbers (should be ≈85%)

---

## Step 2: Automate Detection of Test Backend Issues

**Action:** Automate detection of test files that import `toga` or instantiate UI widgets without explicitly setting the dummy backend.

**Reasoning:** Fast identification of violations ensures we can fix them systematically and meet the "no real backend" rule.

**Implementation Details:**
- Write a Python script `scripts/find_toga_backend_issues.py` that:
  - Walks through `tests/` recursively
  - Parses each file with `ast` to locate `import toga` or `from toga import …`
  - Checks for the presence of `os.environ["TOGA_BACKEND"]` assignment or the `@pytest.mark.usefixtures("toga_dummy")` pattern
  - Generates a markdown report listing offending files and line numbers
- Add the script as a pre-commit hook (via `.pre-commit-config.yaml`) to enforce rule on future commits

**Error Handling:**
- If the script fails to parse a file (syntax error), log the file name and continue

**Testing:**
- Run the script and manually verify the report matches expected violations
- Ensure the script exits with status 0 when no violations are present

---

## Step 3: Fix All Test Files to Enforce Dummy Backend

**Action:** Fix all identified test files to enforce the dummy backend.

**Reasoning:** Ensures every UI test complies with the critical requirement and prevents accidental real-backend usage.

**Implementation Details:**
- For each offending test file:
  - Add `import os; os.environ["TOGA_BACKEND"] = "toga_dummy"` at the top **before** any `toga` import
  - Or add `@pytest.fixture(autouse=True) def set_dummy_backend(monkeypatch): monkeypatch.setenv("TOGA_BACKEND", "toga_dummy")`
  - Remove any explicit backend selections (e.g., `toga_winforms`)
- Run `ruff` to auto-format imports after changes

**Error Handling:**
- If a test still fails after fix, re-run the detection script to ensure no hidden backend usage

**Testing:**
- Re-run the full test suite; all UI tests should now pass using the dummy backend
- Verify coverage unchanged (or improved if tests were corrected)

---

## Step 4: Remove Redundant Tests

**Action:** Identify and remove redundant or obsolete tests while preserving ≥80% overall coverage.

**Reasoning:** Redundant tests add maintenance overhead; trimming them reduces technical debt without compromising quality.

**Implementation Details:**
- Use `pytest --cov=src/accessiweather --cov-report=term-missing` to list uncovered lines
- Run `coverage html` and examine `htmlcov/index.html` for duplicated test paths
- Apply heuristics:
  - Tests that duplicate the same scenario → keep one representative
  - Tests for deprecated APIs → delete
  - Tests with <5% code coverage contribution → consider removal
- Update `pytest.ini` to mark removed tests with `skipif` comments for historical reference

**Error Handling:**
- If removal drops coverage below 80%, add a minimal test covering the uncovered lines before final deletion

**Testing:**
- After each deletion, run `pytest --cov=src/accessiweather` to confirm coverage ≥80%

---

## Step 5: Run Static Analysis

**Action:** Run static analysis (ruff, mypy, pyright) to locate code smells: duplicate code, high cyclomatic complexity, unused imports, commented-out code.

**Reasoning:** Identifies concrete refactoring targets necessary for technical debt reduction.

**Implementation Details:**
- Configure `ruff` with `--select=F401,F811,FURB101` (unused imports, duplicate code) and `--ignore=E501`
- Use `ruff check --select=complexity --max-complexity=10 src/accessiweather`
- Run `mypy --strict src/accessiweather` and `pyright src/accessiweather`
- Collect results into `reports/static_analysis_report.md`

**Error Handling:**
- If `mypy` reports many missing types, prioritize fixing them in subsequent steps rather than aborting

**Testing:**
- Ensure the analysis runs without crashing; manually verify a sample of reported issues

---

## Step 6: Refactor Duplicate and Complex Functions

**Action:** Refactor duplicate and overly complex functions identified in step 5.

**Reasoning:** Reduces maintenance cost, improves readability, and aligns with SOLID principles.

**Implementation Details:**
- For each duplicate code block:
  - Extract common logic into a utility function within an appropriate module (e.g., `utils.py`)
  - Add proper type hints using modern syntax (`dict[str, Any]`)
- For functions with cyclomatic complexity >10:
  - Apply early returns, split into smaller helper functions
  - Ensure each helper has a single responsibility
- Apply `from __future__ import annotations` at top of modified files
- Run `ruff` to re-format and ensure line length ≤100

**Error Handling:**
- If refactoring introduces regressions, run impacted unit tests immediately

**Testing:**
- Execute relevant unit tests plus a full regression suite (`pytest -q`)

---

## Step 7: Eliminate Architectural Issues

**Action:** Eliminate architectural issues: tight coupling, circular dependencies, and god objects.

**Reasoning:** Improves modularity, future extensibility, and aligns with the MVC-like pattern described.

**Implementation Details:**
- Identify circular imports via `pyright` warnings and runtime import errors
- Introduce `TYPE_CHECKING` guards for type-only imports
- Decouple tightly coupled modules by extracting interfaces:
  - Create abstract base classes in `services/interfaces.py`
  - Inject implementations via constructor parameters (dependency injection)
- Refactor any "god object" into separate responsibilities:
  - Split UI logic into `ui/` modules
  - Move configuration handling to `config/`
  - Keep networking in `api/` and `api_client/`
- Update `app_initialization.py` to wire dependencies using a simple factory pattern

**Error Handling:**
- If a circular dependency persists after `TYPE_CHECKING` guards, consider lazy imports

**Testing:**
- Add integration tests that instantiate the app with mocked services to verify wiring
- Run full test suite to ensure no breakage

---

## Step 8: Optimize Performance

**Action:** Optimize performance: improve caching, remove redundant API calls, and replace blocking operations with async equivalents.

**Reasoning:** Reduces latency, aligns with async-first design, and prevents UI freezes.

**Implementation Details:**
- Review `services/` for cache usage:
  - Ensure `WeatherDataCache` respects a 5-minute TTL
  - Add explicit `await cache.get(key)` and `await cache.set(key, value)` calls
  - Replace any synchronous file I/O with `aiofiles`
- Search for duplicated API requests:
  - Use a request deduplication layer in `api_client/core_client.py`
- Identify blocking calls:
  - Convert them to `await asyncio.sleep` and replace sync client with `httpx.AsyncClient`
- Ensure UI updates occur on the main thread using `toga.App().asyncio_loop.call_soon_threadsafe`

**Error Handling:**
- Wrap async calls with `asyncio.timeout` to avoid hanging
- Log warnings if cache miss exceeds expected threshold

**Testing:**
- Write performance benchmarks using `pytest-benchmark` for critical paths
- Validate that UI remains responsive during background fetches

---

## Step 9: Enhance Type Safety

**Action:** Enhance type safety: add missing type hints, replace `Any` with concrete types, and enforce strict mypy/pyright checks.

**Reasoning:** Improves code reliability and aids future maintenance.

**Implementation Details:**
- Scan `mypy` report for `type: ignore` comments; replace them with proper types
- For functions returning JSON from APIs, define TypedDicts or `dataclass` models
- Use `typing.Protocol` for duck-typed interfaces
- Ensure `from __future__ import annotations` is present in all modules
- Run `mypy --strict` until exit code 0

**Error Handling:**
- If a third-party library returns `Any`, wrap it in a small adapter class with explicit attributes

**Testing:**
- Re-run the full test suite; type-checking does not affect runtime but ensures no regressions

---

## Step 10: Improve Error Handling

**Action:** Improve error handling: replace bare `except:` clauses, add descriptive error messages, and handle edge cases.

**Reasoning:** Prevents silent failures and provides better diagnostics for users.

**Implementation Details:**
- Search codebase for `except:` patterns using grep
- Replace with specific exceptions (e.g., `except httpx.HTTPError as exc:`) and log `exc`
- For UI focus calls, wrap in `try: widget.focus() except Exception as e: logger.debug(f"Focus failed: {e}")`
- Add custom exception hierarchy in `api_client/exceptions.py`
- Ensure all public APIs raise these custom exceptions

**Error Handling:**
- Preserve backward compatibility by catching old exceptions in higher layers and re-raising new ones

**Testing:**
- Add tests that deliberately trigger error paths and assert the correct exception type and message

---

## Step 11: Clean Up Configuration

**Action:** Clean up configuration: eliminate hard-coded values, validate settings, and centralize defaults.

**Reasoning:** Ensures configurability, reduces bugs caused by magic numbers, and aligns with the config manager usage rule.

**Implementation Details:**
- Review `config/` modules for literals and move them to `settings.py` as defaults
- Add validation logic in `ConfigManager.load_config()` using `attrs` validators
- Ensure every access to settings calls `config_manager.load_config()` first
- Remove any direct file-path strings; use `Path(__file__).parent / "data"` constructs

**Error Handling:**
- If validation fails, raise `ConfigError` with a clear message

**Testing:**
- Write tests that load malformed config files and assert appropriate validation errors
- Verify that existing config files still load successfully

---

## Step 12: Update Documentation

**Action:** Update documentation: purge outdated comments, add missing docstrings, and improve naming for accessibility.

**Reasoning:** Accurate docs aid developers and maintain compliance with accessibility rules.

**Implementation Details:**
- Run `pydocstyle` to identify missing docstrings
- For each public class/method, add concise docstrings following the NumPy style
- Remove stale comments that no longer reflect code behavior
- Ensure UI element creation includes `aria_label` and `aria_description` arguments with docstrings
- Update `README.md` with a section on testing guidelines (including dummy backend requirement)

**Error Handling:**
- If a docstring reference points to a removed function, update or delete it

**Testing:**
- Run `sphinx-build -b html docs/` (if docs generated) to ensure no warnings

---

## Step 13: Remove Dead Code

**Action:** Remove dead code: delete unused functions, classes, and deprecated features.

**Reasoning:** Reduces codebase size, eliminates confusion, and prevents accidental usage.

**Implementation Details:**
- Use `vulture` to list dead code across `src/`
- Cross-check each reported item against the test suite and runtime usage
- Delete confirmed dead modules/functions
- Update `__all__` exports in packages to reflect removed symbols

**Error Handling:**
- If deletion causes ImportError, roll back and investigate hidden usage

**Testing:**
- Re-run the full test suite; coverage should remain ≥80%

---

## Step 14: Run Final Quality Gates

**Action:** Run final quality gates: lint, type check, coverage, and accessibility compliance.

**Reasoning:** Ensures all changes meet project standards before merging.

**Implementation Details:**
- Execute `ruff check src/ tests/` (no warnings)
- Run `mypy --strict src/`
- Run `pyright src/`
- Run `pytest --cov=src/accessiweather --cov-fail-under=80`
- Use `pytest --tb=short -m integration` to verify integration tests still pass
- Optionally run an automated accessibility audit to ensure ARIA attributes exist

**Error Handling:**
- If any gate fails, isolate the failing file and revert or fix the offending change

**Testing:**
- All checks must succeed; generate a final report `reports/final_quality_report.md`

---

## Step 15: Commit Changes and Create Pull Request

**Action:** Commit the changes with a detailed commit message and open a pull request for review.

**Reasoning:** Provides traceability and allows team review before integration.

**Implementation Details:**
- Stage all modifications: `git add .`
- Commit with detailed message describing all changes
- Push to feature branch `tech-debt-elimination`
- Open PR targeting `main` with reviewers and attach quality report

**Error Handling:**
- If CI fails on the PR, address failures before merge

**Testing:**
- CI pipeline will re-run all quality gates; verify success

---

## Execution Notes

- Each step requires user confirmation before execution
- Steps build upon each other and should be executed in order
- Maintain ≥80% test coverage throughout the process
- CRITICAL: All Toga UI tests must use toga_dummy backend - no exceptions
