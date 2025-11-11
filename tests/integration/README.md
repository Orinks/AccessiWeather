# Integration Tests for Weather Providers

This directory contains integration tests that make real API calls to weather providers (NWS and Open-Meteo) to validate data quality, especially sunrise/sunset times and timezone handling.

## Purpose

These tests were created to catch issues like incorrect sunrise/sunset times (as seen in issue where times were displayed incorrectly). They verify:

- **Sunrise/sunset times** are parseable, timezone-aware, and within reasonable ranges
- **Timestamps** (last_updated, observation times) are recent and not epoch (1970)
- **Timezone information** is present and valid (IANA format)
- **Cross-provider consistency** between NWS and Open-Meteo data
- **Data freshness** to ensure no stale cached responses

## Test Files

### `test_openmeteo_integration.py`
Tests for Open-Meteo API integration:
- ✅ Sunrise/sunset parsing and validation
- ✅ Timezone-aware timestamp handling
- ✅ Current conditions, forecast, and hourly data
- ✅ Parser handling of missing data
- ✅ Raw API response structure validation

### `test_nws_integration.py`
Tests for National Weather Service (NWS) API integration:
- ✅ Grid point metadata (timezone, forecast URLs)
- ✅ Observation timestamp validation
- ✅ Forecast period timestamps and data
- ✅ Hourly forecast validation
- ✅ Quality control (QC) code handling
- ✅ Parser validation with sample responses

### `test_cross_provider.py`
Cross-provider comparison tests:
- ✅ Sunrise/sunset consistency
- ✅ Temperature comparison (within tolerance)
- ✅ Humidity comparison
- ✅ Wind speed comparison
- ✅ Data freshness verification

## Running the Tests

### Local Development

By default, integration tests are **skipped** to avoid hitting external APIs during normal test runs.

To run integration tests:

```bash
# Set environment variable to enable integration tests
export RUN_INTEGRATION_TESTS=1

# Run all integration tests
pytest tests/integration/ -v

# Run specific test file
pytest tests/integration/test_openmeteo_integration.py -v

# Run specific test
pytest tests/integration/test_openmeteo_integration.py::test_openmeteo_current_conditions_sunrise_sunset -v

# Run with markers
pytest -m "integration and network" -v
```

### Without Environment Variable

If you don't set `RUN_INTEGRATION_TESTS=1`, the tests will be skipped:

```bash
pytest tests/integration/ -v
# Output: SKIPPED [X] Set RUN_INTEGRATION_TESTS=1 to run integration tests
```

### In CI/CD

To run integration tests in GitHub Actions, add the environment variable:

```yaml
- name: Run Integration Tests
  run: pytest tests/integration/ -v
  env:
    RUN_INTEGRATION_TESTS: "1"
```

**⚠️ Warning:** Integration tests make real API calls and may:
- Take longer to run (30-60 seconds)
- Hit rate limits if run too frequently
- Fail due to network issues or API downtime

## Rate Limiting

The tests include built-in rate limiting:
- **NWS:** 1.0 second delay between requests
- **Open-Meteo:** 0.5 second delay between requests

These delays are courtesy measures to avoid hitting rate limits. Do not run integration tests in rapid succession.

## Assertions

### Sunrise/Sunset Validation
- ✅ Parseable ISO 8601 datetime
- ✅ Timezone-aware (tzinfo not None)
- ✅ Within ±48 hours of current time
- ✅ Year > 2000 (not epoch)
- ✅ Sunrise before sunset
- ✅ Day length between 8-16 hours (mid-latitude sanity check)

### Timestamp Validation
- ✅ Not None
- ✅ Valid datetime object
- ✅ Year > 2000 (not epoch 1970-01-01)
- ✅ Recent (within 2-3 hours for observations)
- ✅ Not in the future

### Cross-Provider Tolerance
- 🌡️ Temperature: ±10°F
- 💧 Humidity: ±20%
- 💨 Wind speed: ±15 mph
- ☀️ Sunrise/sunset: Should be consistent (same source for NWS enrichment)

## Test Location

All tests use **Lumberton, New Jersey** (39.9643°N, -74.8099°W) as the test location, matching the location from the original bug report screenshot.

## Troubleshooting

### Tests are skipped
- Ensure `RUN_INTEGRATION_TESTS=1` is set in your environment

### Tests fail with timeout
- Check your internet connection
- APIs may be temporarily down (NWS especially)
- Try increasing `REQUEST_TIMEOUT` in test files

### Tests fail with 429 (rate limit)
- Wait a few minutes before re-running
- Ensure delays between requests are adequate
- Check if you have other processes hitting the same APIs

### NWS tests return None
- NWS observation stations may be offline or delayed
- This is expected behavior; tests skip when data unavailable
- NWS forecast endpoints are more reliable than observations

### Temperature/humidity differences too large
- Weather can change rapidly between API calls
- Providers use different observation stations
- Check timestamps to see if observations are from different times

## Adding New Tests

When adding integration tests:

1. **Mark appropriately:**
   ```python
   @pytest.mark.integration
   @pytest.mark.network
   @pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
   @pytest.mark.asyncio
   ```

2. **Use fixtures for HTTP clients:**
   - Reuse `http_client` fixture to avoid connection churn
   - Include proper User-Agent for NWS

3. **Add delays between requests:**
   ```python
   await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
   ```

4. **Handle None responses gracefully:**
   ```python
   if data is None:
       pytest.skip("Provider did not return data")
   ```

5. **Use realistic assertions:**
   - Allow reasonable tolerances for cross-provider comparisons
   - Account for timezone differences
   - Expect some variability in weather data

## Coverage

Integration tests complement unit tests by:
- Validating real API contract adherence
- Catching parser bugs with real-world data
- Verifying timezone and timestamp handling
- Ensuring data quality and freshness

They do **not** replace unit tests, which should still cover:
- Edge cases and error conditions
- Mocked responses for rare scenarios
- Fast, deterministic validation

## Resources

- [NWS API Documentation](https://www.weather.gov/documentation/services-web-api)
- [Open-Meteo API Documentation](https://open-meteo.com/en/docs)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [httpx Documentation](https://www.python-httpx.org/)
