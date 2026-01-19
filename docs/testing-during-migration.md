# Testing During wxPython Migration

This document explains how to run tests while migrating AccessiWeather from Toga to wxPython.

## Quick Reference

```bash
# Run backend-only tests (recommended during migration)
pytest -m "not toga_ui" --ignore=tests/test_toga*.py

# Run all non-UI tests (fastest option)
pytest --ignore=tests/test_toga*.py -m "not gui"

# Run specific backend test files
pytest tests/test_cache.py tests/test_weather_client*.py tests/test_config*.py

# Run with verbose output
pytest -v -m "not toga_ui" --ignore=tests/test_toga*.py
```

## Test Categories

### Backend Tests (Always Safe to Run)

These tests have no UI framework dependencies:

| Test Pattern | Description |
|-------------|-------------|
| `test_cache.py` | Cache and data persistence |
| `test_weather_client*.py` | Weather API clients |
| `test_config*.py` | Configuration management |
| `test_geocoding*.py` | Geocoding services |
| `test_openmeteo*.py` | Open-Meteo API parsing |
| `test_alert_*.py` | Alert logic (most files) |
| `test_retry*.py` | Retry utilities |
| `test_models*.py` | Data models |
| `test_simple_*.py` | Simple utility tests |
| `test_format_string*.py` | String formatting |
| `test_temperature*.py` | Temperature utilities |

### Toga UI Tests (Skip During Migration)

These tests require `toga_dummy` and should be skipped:

| Test Pattern | Description |
|-------------|-------------|
| `test_toga_*.py` | All Toga-specific tests |
| `test_*_dialog.py` | Dialog tests (Toga-based) |
| `test_*_handlers.py` | Handler tests (may have Toga deps) |
| `test_*_ui_*.py` | UI-specific tests |

## Pytest Markers

The following markers are available:

```python
@pytest.mark.toga_ui      # Requires Toga UI components
@pytest.mark.toga         # Toga-specific test
@pytest.mark.wxpython     # wxPython-specific test
@pytest.mark.wx_only      # Only runs with wxPython
@pytest.mark.gui          # Requires any GUI framework
@pytest.mark.backend      # Backend-only (no UI deps)
```

## Running Tests

### Option 1: Exclude Toga Tests by File (Recommended)

```bash
# Ignore all test_toga_*.py files
pytest --ignore=tests/test_toga_simple.py \
       --ignore=tests/test_toga_comprehensive.py \
       --ignore=tests/test_toga_config.py \
       --ignore=tests/test_toga_integration.py \
       --ignore=tests/test_toga_isolated.py \
       --ignore=tests/test_toga_ui_components.py \
       --ignore=tests/test_toga_weather_client.py
```

Or use glob pattern:
```bash
pytest --ignore-glob="tests/test_toga*.py"
```

### Option 2: Use Markers

```bash
# Skip tests marked as toga_ui
pytest -m "not toga_ui"

# Skip all Toga-related tests
pytest -m "not toga_ui and not toga"

# Run only backend tests
pytest -m "backend or unit"
```

### Option 3: Run Specific Test Files

```bash
# Run known-safe backend tests
pytest tests/test_cache.py \
       tests/test_weather_client_nws.py \
       tests/test_weather_client_retry.py \
       tests/test_config_utils.py \
       tests/test_config_properties.py \
       tests/test_geocoding.py \
       tests/test_openmeteo_*.py
```

## Automatic Skipping

The test configuration (`tests/conftest.py`) automatically:

1. Detects if `toga_dummy` is installed
2. Skips `toga_ui` marked tests if Toga is unavailable
3. Skips tests in `test_toga_*.py` files if Toga is unavailable
4. Allows backend tests to run regardless of UI framework

## Adding New Tests During Migration

When adding new tests during the wxPython migration:

### For Backend Logic

```python
# tests/test_my_backend.py
import pytest

@pytest.mark.backend
def test_my_backend_function():
    """Test backend logic without UI dependencies."""
    # No UI imports here
    from accessiweather.cache import Cache
    cache = Cache()
    assert cache is not None
```

### For wxPython UI (Future)

```python
# tests/test_my_wx_dialog.py
import pytest

@pytest.mark.wxpython
@pytest.mark.gui
def test_my_wx_dialog(requires_wxpython):
    """Test wxPython dialog."""
    import wx
    # Test wxPython UI components
```

## CI/CD Considerations

During the migration period, update CI to run backend-only tests:

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    steps:
      - name: Run backend tests
        run: pytest -m "not toga_ui" --ignore-glob="tests/test_toga*.py"
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'toga_dummy'"

This is expected during wxPython migration. Use one of these options:

```bash
# Option 1: Install toga_dummy (if you still need Toga tests)
pip install toga-dummy

# Option 2: Skip Toga tests (recommended during migration)
pytest --ignore-glob="tests/test_toga*.py" -m "not toga_ui"
```

### "ImportError: cannot import name 'X' from 'toga'"

Some test files import Toga at module level. Either:
1. Skip those files with `--ignore`
2. Install Toga packages temporarily

### Tests Hanging or Timing Out

Some UI tests may hang without a proper backend. Skip them:

```bash
pytest --ignore-glob="tests/test_toga*.py" -m "not gui" --timeout=30
```
