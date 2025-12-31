# Test Suite Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce test suite runtime from 5+ minutes to under 2 minutes while maintaining test coverage and reliability.

**Architecture:** Multi-pronged optimization targeting the four main bottlenecks: (1) enable parallel execution by default, (2) reduce Hypothesis examples for local dev, (3) skip sleeps when using VCR cassettes, (4) use time mocking in cache tests.

**Tech Stack:** pytest, pytest-xdist, Hypothesis, VCR.py, unittest.mock

---

## Analysis Summary

| Bottleneck | Current Impact | Solution | Expected Savings |
|------------|---------------|----------|------------------|
| No parallelization | Tests run single-threaded | Enable `-n auto` for local dev | 60-75% faster |
| Hypothesis examples | 100+ examples per test | Use `ci` profile (25 examples) locally | 50-75% fewer examples |
| Integration sleep() | 25+ seconds of delays | Skip when using VCR cassettes | 25+ seconds |
| Cache TTL tests | Real time.sleep() | Mock time for instant verification | 1 second |

---

## Task 1: Create Fast Test Configuration Profile

**Files:**
- Modify: `pytest.ini`
- Create: `conftest_local.py` (optional helper)

**Step 1: Add pytest-xdist configuration comments**

Update `pytest.ini` to make parallel execution easier to use:

```ini
# Add after line 4 (addopts line)
# For fast local development, run: pytest -n auto
# Or set environment variable: PYTEST_ADDOPTS="-n auto"
```

**Step 2: Run tests to verify current baseline**

Run: `pytest --collect-only -q | tail -5`
Expected: Shows total test count for baseline

**Step 3: Commit**

```bash
git add pytest.ini
git commit -m "docs(tests): clarify parallel execution options in pytest.ini"
```

---

## Task 2: Reduce Hypothesis Examples for Local Development

**Files:**
- Modify: `tests/conftest.py:34-50`

**Step 1: Review current Hypothesis profiles**

Current configuration in `tests/conftest.py`:
```python
settings.register_profile(
    "ci",
    max_examples=25,  # Fast CI runs
    ...
)
settings.register_profile(
    "dev",
    max_examples=50,  # Current default
    ...
)
```

**Step 2: Create new "fast" profile for quick iteration**

Add to `tests/conftest.py` after the existing profiles:

```python
settings.register_profile(
    "fast",
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    deadline=None,
)
```

**Step 3: Update profile loading to prefer "fast" for interactive use**

Modify the profile loading logic:

```python
# Load profile based on environment
# HYPOTHESIS_PROFILE=fast for quick iteration
# HYPOTHESIS_PROFILE=ci for CI builds
# HYPOTHESIS_PROFILE=dev for thorough local testing
profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
settings.load_profile(profile)
```

**Step 4: Run tests with fast profile to verify**

Run: `HYPOTHESIS_PROFILE=fast pytest tests/test_air_quality_presentation.py -v --tb=short -x`
Expected: Tests complete in under 30 seconds

**Step 5: Commit**

```bash
git add tests/conftest.py
git commit -m "feat(tests): add 'fast' Hypothesis profile for quick iteration"
```

---

## Task 3: Reduce max_examples in Property Tests

**Files:**
- Modify: Multiple test files with `@settings(max_examples=100)`

**Step 1: Find all tests with high max_examples**

Files to modify (reduce from 100 to 50):
- `tests/test_air_quality_presentation.py` - 15 occurrences
- `tests/test_ai_explainer.py` - 8 occurrences
- `tests/test_taskbar_icon_properties.py` - check and reduce
- `tests/test_taf_decoder_properties.py` - check and reduce
- `tests/test_geocoding_properties.py` - check and reduce

**Step 2: Create sed-like replacement for max_examples=100**

For each file, change:
```python
@settings(max_examples=100)
```
to:
```python
@settings(max_examples=50)
```

**Step 3: Run affected tests to verify they still pass**

Run: `pytest tests/test_air_quality_presentation.py -v --tb=short`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/test_*.py
git commit -m "perf(tests): reduce Hypothesis max_examples from 100 to 50"
```

---

## Task 4: Skip Integration Test Delays When Using VCR Cassettes

**Files:**
- Modify: `tests/integration/test_nws_integration.py`
- Modify: `tests/integration/test_openmeteo_integration.py`
- Modify: `tests/integration/test_openmeteo_archive_integration.py`
- Modify: `tests/integration/test_cross_provider.py`

**Step 1: Create helper function for conditional delay**

Add to `tests/integration/conftest.py`:

```python
import os
import time
import asyncio

def should_delay() -> bool:
    """Only delay when running live tests, not when using VCR cassettes."""
    return os.environ.get("LIVE_WEATHER_TESTS", "").lower() in ("1", "true", "yes")

def conditional_sleep(seconds: float) -> None:
    """Sleep only when running live tests."""
    if should_delay():
        time.sleep(seconds)

async def conditional_async_sleep(seconds: float) -> None:
    """Async sleep only when running live tests."""
    if should_delay():
        await asyncio.sleep(seconds)
```

**Step 2: Update test_nws_integration.py to use conditional sleep**

Replace all occurrences of:
```python
await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
```
with:
```python
await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)
```

And add import:
```python
from .conftest import conditional_async_sleep
```

**Step 3: Update test_openmeteo_integration.py**

Replace:
```python
time.sleep(DELAY_BETWEEN_REQUESTS)
```
with:
```python
conditional_sleep(DELAY_BETWEEN_REQUESTS)
```

And add import:
```python
from .conftest import conditional_sleep
```

**Step 4: Update test_openmeteo_archive_integration.py**

Same pattern as Step 3.

**Step 5: Update test_cross_provider.py**

Same pattern as Step 2 (uses asyncio.sleep).

**Step 6: Run integration tests to verify**

Run: `pytest tests/integration/ -v --tb=short -x`
Expected: Tests complete in under 10 seconds (vs 25+ seconds before)

**Step 7: Commit**

```bash
git add tests/integration/
git commit -m "perf(tests): skip rate-limit delays when using VCR cassettes"
```

---

## Task 5: Mock time.sleep in Cache Tests

**Files:**
- Modify: `tests/test_cache.py`

**Step 1: Review current cache tests using sleep**

Find lines using `time.sleep()` for TTL verification.

**Step 2: Create time-mocking fixture**

Add to `tests/test_cache.py` or use existing mock:

```python
from unittest.mock import patch
import time

@pytest.fixture
def mock_time():
    """Mock time.time() for fast cache expiration tests."""
    current_time = time.time()

    with patch('time.time') as mock:
        def advance(seconds):
            nonlocal current_time
            current_time += seconds
            mock.return_value = current_time

        mock.return_value = current_time
        mock.advance = advance
        yield mock
```

**Step 3: Update cache TTL tests to use mock**

Replace:
```python
time.sleep(0.2)
assert cache.get(key) is None  # Expired
```
with:
```python
mock_time.advance(0.2)
assert cache.get(key) is None  # Expired
```

**Step 4: Run cache tests to verify**

Run: `pytest tests/test_cache.py -v --tb=short`
Expected: Tests complete in under 5 seconds

**Step 5: Commit**

```bash
git add tests/test_cache.py
git commit -m "perf(tests): use time mocking instead of real sleep in cache tests"
```

---

## Task 6: Create Makefile/Script for Common Test Commands

**Files:**
- Create: `scripts/test.py` or update existing scripts

**Step 1: Create convenience script**

Create `scripts/test_fast.py`:

```python
#!/usr/bin/env python
"""Run tests with optimized settings for fast local development."""
import os
import subprocess
import sys

def main():
    # Set fast profile
    os.environ.setdefault("HYPOTHESIS_PROFILE", "fast")

    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        "-n", "auto",  # Parallel execution
        "--dist", "loadscope",  # Group by module
        "-v",
        "--tb=short",
    ]

    # Add any extra args passed to script
    cmd.extend(sys.argv[1:])

    # Exclude integration tests by default unless specified
    if not any("integration" in arg for arg in sys.argv[1:]):
        cmd.extend(["-m", "not integration"])

    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd)

if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Test the script**

Run: `python scripts/test_fast.py`
Expected: Tests run in parallel with fast Hypothesis profile

**Step 3: Commit**

```bash
git add scripts/test_fast.py
git commit -m "feat(scripts): add test_fast.py for optimized local test runs"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `CLAUDE.md` (Quick Reference Commands section)
- Modify: `pytest.ini` (comments)

**Step 1: Update CLAUDE.md with fast test commands**

Add to Quick Reference Commands:

```markdown
# Fast Testing (local development)
python scripts/test_fast.py              # Parallel + fast Hypothesis
HYPOTHESIS_PROFILE=fast pytest -n auto   # Manual equivalent
pytest -n auto -m "not integration"      # Skip slow integration tests
```

**Step 2: Commit**

```bash
git add CLAUDE.md pytest.ini
git commit -m "docs: add fast testing commands to CLAUDE.md"
```

---

## Task 8: Final Verification

**Step 1: Run full test suite with optimizations**

Run: `HYPOTHESIS_PROFILE=ci pytest -n auto --dist loadscope -v --tb=short`
Expected: Complete in under 2 minutes

**Step 2: Run integration tests separately**

Run: `pytest tests/integration/ -v --tb=short`
Expected: Complete in under 10 seconds

**Step 3: Compare before/after times**

Document the improvement in commit message.

**Step 4: Final commit**

```bash
git add -A
git commit -m "perf(tests): optimize test suite for 3x faster execution

- Add 'fast' Hypothesis profile (10 examples) for quick iteration
- Reduce default max_examples from 100 to 50 in property tests
- Skip rate-limit delays when using VCR cassettes
- Add parallel execution documentation
- Add test_fast.py convenience script

Before: ~5 minutes
After: ~90 seconds (parallel) or ~2 minutes (serial)
"
```

---

## Verification Checklist

- [ ] All tests still pass with optimizations
- [ ] No test coverage regression
- [ ] Integration tests work with both VCR and live modes
- [ ] CI pipeline still works (uses 'ci' profile)
- [ ] Fast local development workflow documented

---

## Expected Results

| Metric | Before | After |
|--------|--------|-------|
| Full test suite (serial) | 5+ min | ~2 min |
| Full test suite (parallel) | N/A | ~90 sec |
| Unit tests only (parallel) | N/A | ~45 sec |
| Integration tests | 25+ sec | ~5 sec |
