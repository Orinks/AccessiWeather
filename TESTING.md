# Testing Guide for AccessiWeather

## Overview

AccessiWeather uses a **two-mode test strategy** for integration tests:

1. **Cassette Replay (default)**: Uses VCR cassettes for deterministic HTTP replay—fast, reliable, no network needed
2. **Live Mode**: Makes real API calls to weather providers—useful for refreshing cassettes and validating API changes

Unit tests run independently without network access.

## Test Modes

### Default Mode (Cassette Replay)

- Uses VCR cassettes for deterministic HTTP replay
- No network access required
- Fast and reliable for CI
- Run with: `pytest tests/integration/`

### Live Mode

- Makes real API calls to weather providers
- Useful for: refreshing cassettes, validating API changes, nightly runs
- Run with: `LIVE_WEATHER_TESTS=1 pytest tests/integration/`
- Requires API keys for Visual Crossing

## Running Tests

### Quick Reference

```bash
# Run all unit tests
pytest tests/ -m "not integration"

# Run integration tests with cassettes (default, fast)
pytest tests/integration/

# Run live integration tests (slow, requires network)
LIVE_WEATHER_TESTS=1 pytest tests/integration/ -v

# Run a specific provider's tests
pytest tests/integration/test_nws_integration.py

# Run all tests in parallel (faster)
pytest -n auto

# Run tests matching a pattern
pytest -k "test_name" -v

# Run last-failed tests first
pytest --lf --ff
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LIVE_WEATHER_TESTS=1` | Enable live API mode (real network calls) |
| `VISUAL_CROSSING_API_KEY` | Required for live Visual Crossing tests |
| `HYPOTHESIS_PROFILE` | Set to `ci`, `dev`, or `thorough` for property-based tests |
| `TOGA_BACKEND=toga_dummy` | Use dummy Toga backend for UI tests |

## Cassette Management

### What are Cassettes?

Cassettes are recorded HTTP interactions stored as YAML files. When tests run in default mode, VCR replays these recordings instead of making real network calls. This ensures:

- **Determinism**: Same response every time
- **Speed**: No network latency
- **Reliability**: No flaky tests from API availability

### Directory Structure

```
tests/integration/cassettes/
├── nws/                  # National Weather Service API recordings
├── openmeteo/            # Open-Meteo API recordings
├── visual_crossing/      # Visual Crossing API recordings
├── environmental/        # AQI/pollen data recordings
└── cross_provider/       # Multi-provider scenario recordings
```

### Refreshing Cassettes

When API responses change or cassettes become stale:

```bash
# Record new cassettes (adds to existing, preserves unchanged)
LIVE_WEATHER_TESTS=1 pytest tests/integration/ --vcr-record=new_episodes

# Re-record all cassettes (replaces existing completely)
LIVE_WEATHER_TESTS=1 pytest tests/integration/ --vcr-record=all

# Record cassettes for a specific provider
LIVE_WEATHER_TESTS=1 pytest tests/integration/test_nws_integration.py --vcr-record=all
```

### Secret Scrubbing

Cassettes are automatically scrubbed of sensitive data:

- API keys (e.g., Visual Crossing keys)
- Authorization headers
- Session cookies
- Request IDs

**Always verify cassettes before committing!** Run `git diff` on cassette files to ensure no secrets leaked through.

## Provider-Specific Notes

### NWS (api.weather.gov)

- **User-Agent required**: Must include contact info per NWS policy
- **Rate limit**: ~500ms between requests recommended
- **Caching**: Tests cache `/points` lookups to reduce API calls
- **No API key needed**: Free public API

### Open-Meteo

- **Rate limits**: 600/min, 5000/hour, 10000/day
- **No API key needed**: Free tier available
- **Tests use conservative rate limiting** to avoid hitting limits

### Visual Crossing

- **API key required**: Get a free key at [visualcrossing.com](https://www.visualcrossing.com/)
- **Strict concurrency**: `concurrency=1` limit—only one request at a time
- **429 errors**: Should NOT be retried aggressively; wait for rate limit window

## Contract-Based Assertions

Integration tests use **contract-based assertions** instead of exact value matching. This approach handles cassette drift gracefully—API responses may change slightly over time, but the contract (data types, ranges, required fields) remains stable.

### ✅ Good (contract-based)

```python
def test_temperature_forecast(weather_data):
    assert weather_data.temperature is not None
    assert -100 <= weather_data.temperature <= 150  # Reasonable range
    assert weather_data.temperature_unit in ["F", "C"]
    assert isinstance(weather_data.humidity, (int, float))
    assert 0 <= weather_data.humidity <= 100
```

### ❌ Bad (exact values—will fail with cassette drift)

```python
def test_temperature_forecast(weather_data):
    assert weather_data.temperature == 72.5  # Brittle!
    assert weather_data.conditions == "Partly Cloudy"  # Will break
```

### Contract Assertion Patterns

```python
# Required field exists and has correct type
assert data.location is not None
assert isinstance(data.location, str)

# Value within expected range
assert -90 <= data.latitude <= 90
assert -180 <= data.longitude <= 180

# Value in expected set
assert data.status in ["OK", "PENDING", "ERROR"]

# Collection has expected structure
assert len(data.hourly_forecast) > 0
assert all(hasattr(h, "temperature") for h in data.hourly_forecast)
```

## CI Configuration

The CI pipeline (`ci.yml`) runs integration tests with cassettes by default:

- **No network access needed**: Works in isolated CI environments
- **Deterministic results**: Same pass/fail every run
- **Fast execution**: No waiting for API responses

### Nightly/Scheduled Runs

For catching API changes early, configure nightly runs with live mode:

```yaml
# Example GitHub Actions schedule
on:
  schedule:
    - cron: '0 3 * * *'  # 3 AM daily

env:
  LIVE_WEATHER_TESTS: 1
  VISUAL_CROSSING_API_KEY: ${{ secrets.VISUAL_CROSSING_API_KEY }}
```

## Troubleshooting

### Test fails with "Can't play back cassette"

**Cause**: Cassette doesn't exist for this test yet.

**Fix**: Run with live mode to record it:
```bash
LIVE_WEATHER_TESTS=1 pytest tests/integration/test_specific.py --vcr-record=new_episodes
```

### Test fails with stale cassette data

**Cause**: API response format changed since cassette was recorded.

**Fix**: Refresh cassettes with live mode:
```bash
LIVE_WEATHER_TESTS=1 pytest tests/integration/ --vcr-record=all
```

### 429 errors in live mode

**Cause**: Rate limit exceeded.

**Fix**:
1. Reduce test parallelism: `pytest -n 1`
2. Wait for rate limit window to clear (usually 1-60 minutes)
3. For Visual Crossing, ensure only one test runs at a time

### Tests pass locally but fail in CI

**Cause**: Usually missing cassettes or environment differences.

**Fix**:
1. Ensure all cassettes are committed to git
2. Check that cassette paths match between local and CI
3. Verify `TOGA_BACKEND=toga_dummy` is set for UI tests

### Hypothesis tests are slow

**Cause**: Default profile generates many examples.

**Fix**: Use the CI profile for faster runs:
```bash
HYPOTHESIS_PROFILE=ci pytest tests/ -m hypothesis
```

## Writing New Integration Tests

1. **Start with cassettes**: Write the test assuming cassette mode
2. **Use contract assertions**: Don't assert exact values
3. **Record cassettes**: Run once with `LIVE_WEATHER_TESTS=1 --vcr-record=new_episodes`
4. **Verify cassettes**: Check for leaked secrets before committing
5. **Test both modes**: Ensure test passes in both cassette and live mode
