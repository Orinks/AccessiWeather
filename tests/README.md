# AccessiWeather Test Suite

Focused unit tests for core business logic, emphasizing **accuracy** and **speed**.

## Quick Start

```bash
# Run all tests (parallel by default)
pytest

# Run specific test file
pytest tests/test_cache.py

# Run specific test
pytest tests/test_cache.py::TestCache::test_set_and_get

# Run tests matching a pattern
pytest -k "alert"

# Disable parallel execution
pytest -n 0
```

## Test Structure

| File | Description |
|------|-------------|
| `test_cache.py` | In-memory and file-based caching |
| `test_alert_manager.py` | Alert state tracking and notifications |
| `test_config_manager.py` | Configuration loading/saving |
| `test_weather_client.py` | Weather data orchestration |
| `test_geocoding.py` | Address geocoding and validation |
| `test_openmeteo_client.py` | Open-Meteo API client |
| `test_visual_crossing_client.py` | Visual Crossing API client |
| `test_models.py` | Data models |
| `test_parsers.py` | Data parsing utilities |
| `test_utils.py` | Utility functions |

## Design Principles

1. **Fast execution**: All external API calls are mocked
2. **Focused scope**: Each test tests one thing
3. **Clear naming**: Test names describe expected behavior
4. **Minimal fixtures**: Only essential fixtures in conftest.py
5. **Parallel-safe**: Tests don't share mutable state

## Fixtures

Common fixtures are defined in `conftest.py`:

- `sample_location` - US test location
- `international_location` - Non-US test location
- `sample_current_conditions` - Mock current weather
- `sample_forecast` - Mock forecast data
- `sample_weather_alert` - Mock weather alert
- `temp_config_dir` - Temporary config directory
- `mock_app` - Mock Toga app for ConfigManager
- `mock_httpx_client` - Mock HTTP client

## Adding Tests

1. Create a new `test_*.py` file or add to existing one
2. Group related tests in a class (e.g., `TestCacheMethods`)
3. Use descriptive test names: `test_expired_entry_returns_none`
4. Mock external dependencies (network, filesystem, etc.)
5. Keep tests independent - no reliance on test order

## Hypothesis Testing

Property-based tests using Hypothesis are supported:

```bash
# Default profile (25 examples, fast)
pytest

# Development profile (50 examples)
HYPOTHESIS_PROFILE=dev pytest

# Thorough profile (200 examples)
HYPOTHESIS_PROFILE=thorough pytest
```
