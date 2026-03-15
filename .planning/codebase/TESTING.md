# Testing Patterns

**Analysis Date:** 2026-03-14

## Test Framework

**Runner:**
- pytest (configured in `pytest.ini`)
- Async support: pytest-asyncio (auto mode enabled)
- Parallel execution: pytest-xdist (default: `-n auto` runs all tests in parallel by worker pool)

**Assertion Library:**
- Built-in pytest assertions (`assert`, `assert x == y`)
- No specialized assertion libraries (unittest.mock used for mocking)

**Run Commands:**
```bash
pytest                              # Run all tests (parallel by default)
pytest tests/test_file.py           # Run single test file
pytest tests/test_file.py::TestClass::test_method  # Run specific test
pytest -k "cache"                   # Run tests matching pattern
pytest -n 0                         # Run tests serially (disable parallel)
pytest -m "not integration"         # Skip integration tests
pytest --cov=accessiweather         # With coverage report
HYPOTHESIS_PROFILE=fast pytest      # Fast property tests
```

## Test File Organization

**Location:**
- Unit tests: `tests/test_*.py` (co-located with test subjects, not in source tree)
- Integration tests: `tests/integration/test_*.py` (marked with `@pytest.mark.integration`)
- GUI tests: `tests/gui/test_*.py`

**Naming:**
- Files: `test_<module_name>.py` (e.g., `test_cache.py` for `cache.py`)
- Test classes: `Test<Subject>` (e.g., `TestCache`, `TestWeatherDataCache`)
- Test methods: `test_<scenario_or_behavior>` (e.g., `test_expired_entry_returns_none()`)

**Structure:**
```
tests/
├── test_cache.py              # Unit tests for cache module
├── test_alert_manager.py      # Unit tests for alert_manager module
├── conftest.py                # Shared fixtures (global scope)
├── integration/
│   ├── conftest.py            # Integration-specific fixtures
│   ├── cassettes/             # VCR-recorded HTTP responses
│   └── test_openmeteo_integration.py
└── gui/
    └── test_main_window_minimize.py
```

## Test Structure

**Suite Organization:**
```python
class TestCache:
    """Tests for the in-memory Cache class."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = Cache(default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key_returns_none(self):
        """Test that getting a missing key returns None."""
        cache = Cache()
        assert cache.get("nonexistent") is None
```

**Patterns:**
- Descriptive docstrings explaining what the test does
- Clear test names that read like assertions: `test_expired_entry_returns_none`
- Arrange-Act-Assert pattern (implicit grouping in short tests)
- One behavioral outcome per test (but may test multiple assertions)

**Setup/Teardown:**
- Use pytest fixtures (`@pytest.fixture`) instead of setUp/tearDown
- Fixtures are function-scoped by default
- Class-scoped fixtures with `@pytest.fixture(scope="class")` for expensive setup

**Example with fixtures:**
```python
class TestWeatherDataCache:
    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create a temporary cache directory."""
        return tmp_path / "weather_cache"

    @pytest.fixture
    def cache(self, cache_dir):
        """Create a WeatherDataCache instance."""
        return WeatherDataCache(cache_dir, max_age_minutes=60)

    def test_store_and_load(self, cache, location, weather_data):
        """Test storing and retrieving weather data."""
        cache.store(location, weather_data)
        loaded = cache.load(location, allow_stale=True)
        assert loaded is not None
```

## Mocking

**Framework:** `unittest.mock` (from Python stdlib)

**Patterns:**
```python
from unittest.mock import MagicMock, AsyncMock, patch

# Basic mock
mock_client = MagicMock()
mock_client.get.return_value = {"temp": 72}

# Async mock
async_mock = AsyncMock()
async_mock.fetch_data = AsyncMock(return_value={"status": "ok"})

# Patching
with patch("httpx.AsyncClient") as mock:
    client_instance = AsyncMock()
    mock.return_value.__aenter__.return_value = client_instance
    # Test code here
```

**What to Mock:**
- External API calls (httpx.AsyncClient)
- File I/O operations (Path.open, json.load)
- Time-dependent operations (datetime.now, time.sleep)
- System calls (subprocess, os.environ)

**What NOT to Mock:**
- Core business logic classes (Cache, AlertManager)
- Data models (Location, WeatherData)
- Utility functions with no external dependencies
- The code you're testing (unless testing mocking behavior itself)

**Fixture-based Mocking:**
```python
@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for API tests."""
    with patch("httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__.return_value = client_instance
        mock.return_value.__aexit__.return_value = None
        yield client_instance
```

## Fixtures and Factories

**Test Data:**
All fixtures are in `tests/conftest.py` (global) or `tests/integration/conftest.py`.

**Location Fixtures:**
```python
@pytest.fixture
def sample_location() -> Location:
    """Return a sample US location for testing."""
    return Location(
        name="Test City, NY",
        latitude=40.7128,
        longitude=-74.0060,
        country_code="US",
    )

@pytest.fixture
def international_location() -> Location:
    """Return a sample international location (outside US)."""
    return Location(
        name="London, UK",
        latitude=51.5074,
        longitude=-0.1278,
        country_code="GB",
    )
```

**Weather Data Fixtures:**
```python
@pytest.fixture
def sample_weather_data(sample_location, sample_current_conditions, sample_forecast):
    """Complete sample weather data."""
    return WeatherData(
        location=sample_location,
        current=sample_current_conditions,
        forecast=sample_forecast,
        alerts=WeatherAlerts(alerts=[]),
    )
```

**Location:**
- `tests/conftest.py` - Global fixtures (shared by all tests)
- No factory classes - just fixture functions

## Coverage

**Requirements:** Not enforced (see `pyproject.toml` omit list)

**View Coverage:**
```bash
pytest --cov=accessiweather --cov-report=html
# Open htmlcov/index.html
```

**Exclusions (omit in coverage):**
- Auto-generated code: `*/weather_gov_api_client/*`
- UI code: `*/accessiweather/ui/*` (hard to test with wxPython)
- Pragma comments: `# pragma: no cover` for unreachable code

## Test Types

**Unit Tests:**
- Scope: Single module or class
- Dependencies: Mocked (no real API calls, no I/O)
- Speed: Fast (< 100ms each)
- Location: `tests/test_*.py`
- Marked with: No marker (default)
- Example: `test_cache.py` - tests Cache and WeatherDataCache without filesystem

**Integration Tests:**
- Scope: Multiple components working together
- Dependencies: Real API calls (recorded with VCR), real file I/O
- Speed: Slower (seconds per test)
- Location: `tests/integration/test_*.py`
- Marked with: `@pytest.mark.integration`
- Example: `test_openmeteo_integration.py` - tests actual API calls against Open-Meteo

**Live Tests:**
- Scope: Against actual remote APIs
- Disabled by default: Skipped unless `LIVE_TESTS=true`
- Marked with: `@pytest.mark.live_only` (custom marker)
- Used for: Periodic validation of API contracts
- Command: `LIVE_TESTS=true pytest -m "live_only"`

**GUI Tests:**
- Location: `tests/gui/test_*.py`
- Use wxPython mocking via conftest.py stubs
- Example: `test_main_window_minimize.py`

## Common Patterns

**Async Testing:**
```python
import pytest

@pytest.mark.asyncio
async def test_fetch_weather():
    """Test async weather fetch."""
    from accessiweather.weather_client import WeatherClient

    client = WeatherClient()
    data = await client.fetch_weather(location)
    assert data is not None
    assert data.current is not None
```

**Error Testing:**
```python
def test_invalid_coordinates():
    """Test that invalid coordinates are rejected."""
    service = GeocodingService()
    assert service.validate_coordinates(91, 0, us_only=False) is False
    assert service.validate_coordinates(0, 181, us_only=False) is False
```

**Time-dependent Testing:**
```python
def test_expired_entry_returns_none(self):
    """Test that expired entries return None."""
    cache = Cache(default_ttl=0.01)  # 10ms TTL
    cache.set("key", "value")
    time.sleep(0.02)  # Wait for expiration
    assert cache.get("key") is None
```

## VCR Integration Tests

**Framework:** VCR (vcrpy) records HTTP interactions to YAML cassettes

**Configuration Location:** `tests/integration/conftest.py`

**Setup:**
```python
CASSETTE_DIR = Path(__file__).parent / "cassettes"
RECORD_MODE = os.environ.get("VCR_RECORD_MODE", "none")

integration_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=RECORD_MODE,
    match_on=["method", "scheme", "host", "port", "path"],
    filter_query_parameters=["key", "api_key", "apikey", "token"],
    filter_headers=["authorization", "x-api-key", "api-key", "user-agent"],
)
```

**Usage:**
```python
@pytest.mark.integration
class TestOpenMeteoCurrentWeather:
    @integration_vcr.use_cassette("openmeteo/current_weather_nyc.yaml")
    def test_get_current_weather_us_location(self, us_location):
        """Test fetching current weather for a US location."""
        client = OpenMeteoApiClient(timeout=30.0)
        data = client.get_current_weather(
            latitude=us_location.latitude,
            longitude=us_location.longitude,
        )
        assert data is not None
        assert "current" in data
```

**Record Modes:**
- `"none"`: Only replay cassettes (CI default) - fails if cassette missing
- `"once"`: Record if missing, replay if exists (dev default)
- `"new_episodes"`: Record new requests, replay existing (good for adding tests)
- `"all"`: Always record (use sparingly - rewrites cassettes)

**Best Practices:**
1. Match on `method`, `host`, `path` (NOT query params with API keys)
2. Filter sensitive headers and query parameters automatically
3. Store cassettes in `tests/integration/cassettes/`
4. Commit cassettes to version control so CI doesn't need API keys
5. Use `@pytest.mark.integration` to skip in fast unit test runs

## Markers

**Available Markers** (defined in `pytest.ini`):
```ini
markers =
    unit: Unit tests (fast, mocked dependencies)
    integration: Integration tests (may use network)
    live_only: Tests requiring live API access (skipped by default)
    slow: Slow tests
```

**Usage:**
```python
@pytest.mark.integration
def test_openmeteo_api():
    pass

@pytest.mark.live_only
def test_against_live_api():
    pass

@pytest.mark.slow
def test_expensive_computation():
    pass
```

## Hypothesis (Property-based Testing)

**Framework:** hypothesis (installed in `dev` extras)

**Configuration:**
```python
# In conftest.py
from hypothesis import settings as hypothesis_settings

hypothesis_settings.register_profile("ci", max_examples=25, deadline=None)
hypothesis_settings.register_profile("dev", max_examples=50, deadline=None)
hypothesis_settings.register_profile("thorough", max_examples=200, deadline=None)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))
```

**Profiles:**
- `ci`: 25 examples (fast CI runs)
- `dev`: 50 examples (development)
- `thorough`: 200 examples (pre-release validation)

**Run:**
```bash
pytest                                    # Uses 'ci' profile
HYPOTHESIS_PROFILE=dev pytest             # Slower, more thorough
HYPOTHESIS_PROFILE=thorough pytest        # Most thorough
```

## Environment Setup

**Test Environment Variables** (set in `conftest.py`):
```python
os.environ["ACCESSIWEATHER_TEST_MODE"] = "1"
os.environ["PYTEST_CURRENT_TEST"] = "true"
```

**Mock Stubs:**
- wxPython stub module (allows headless testing)
- sound_lib stub module (no audio in tests)
- gui_builder stub module (not needed for unit tests)

**Keyring Mock:**
```python
@pytest.fixture(autouse=True)
def _mock_keyring_available():
    """Pretend keyring is available in all tests unless overridden."""
    original = ss._keyring_available
    ss._keyring_available = True
    yield
    ss._keyring_available = original
```

## CI/CD Integration

**Workflow:** `.github/workflows/ci.yml`

**Test Settings in CI:**
```bash
FORCE_COLOR=0                      # Prevent encoding crashes on Windows
PYTHONUTF8=1                       # Force UTF-8
ACCESSIWEATHER_TEST_MODE=1         # Enable test mode
HYPOTHESIS_PROFILE=ci              # Fast property tests
TOGA_BACKEND=toga_dummy            # Headless UI (if using Toga)
```

**Parallel Execution in CI:**
- Default: `-n auto` (uses all CPU cores)
- Disable if flaky: `-n 0`

## Quick Reference

```bash
# All tests (parallel, fast)
pytest

# Specific test file
pytest tests/test_cache.py

# Single test
pytest tests/test_cache.py::TestCache::test_set_and_get

# Pattern match
pytest -k "cache"

# Unit tests only (skip integration)
pytest -m "not integration"

# With coverage
pytest --cov=accessiweather

# Verbose output
pytest -vv

# Show print statements
pytest -s

# Last failed, then first failed
pytest --lf --ff

# Serial (no parallel)
pytest -n 0
```

---

*Testing analysis: 2026-03-14*
