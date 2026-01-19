# Integration Tests

This directory contains integration tests for AccessiWeather API clients using VCR cassette recording.

## Overview

Integration tests verify actual API behavior by recording HTTP interactions as "cassettes" that can be replayed without hitting live APIs. This approach provides:

- **Fast tests**: Replay recorded responses instead of making network calls
- **Reliable tests**: No flaky tests due to network issues or API rate limits
- **Deterministic tests**: Same response every time for consistent assertions

## Test Categories

| Marker | Description | When to Use |
|--------|-------------|-------------|
| `integration` | Standard integration tests with VCR cassettes | Default run |
| `live_only` | Tests requiring live API access | Recording new cassettes, API validation |

## Running Tests

```bash
# Default: Run integration tests with recorded cassettes (fast)
pytest tests/integration/ -v

# Run all tests including live_only (requires network + API keys)
pytest tests/integration/ -v -m "integration"

# Run only live_only tests (for recording/validation)
pytest tests/integration/ -v -m "live_only"

# Run with fresh API calls (re-records cassettes)
set VCR_RECORD_MODE=all && pytest tests/integration/ -v
```

## VCR Recording Modes

Set `VCR_RECORD_MODE` environment variable:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `none` (default) | Only replay, fail if missing | CI, normal development |
| `once` | Record if missing, replay if exists | Adding new tests |
| `new_episodes` | Record new requests, replay existing | Updating tests |
| `all` | Always record (overwrites) | Full cassette refresh |

## API Keys

Some tests require API keys for recording:

```bash
# Visual Crossing API (required for Visual Crossing tests)
set VISUAL_CROSSING_API_KEY=your-api-key-here
```

**Note**: API keys are automatically filtered from recorded cassettes.

## Cassette Structure

```
tests/integration/cassettes/
├── geocoding/         # Geocoding API tests
├── openmeteo/         # OpenMeteo weather API tests
├── visual_crossing/   # Visual Crossing API tests
└── weather_client/    # WeatherClient orchestration tests
```

## Best Practices

1. **Record cassettes in isolation**: Run one test at a time when recording
2. **Review cassettes before committing**: Ensure no sensitive data leaked
3. **Use meaningful cassette names**: Match the test name for clarity
4. **Don't match on query params**: API keys vary between environments
5. **Filter headers**: User-Agent and auth headers should be filtered
6. **Keep cassettes small**: Request only data needed for assertions

## Troubleshooting

### "Cassette not found" errors
Run with `VCR_RECORD_MODE=once` to record missing cassettes.

### Empty API responses in cassettes
The API may have been rate-limited during recording. Delete the cassette and re-record with `VCR_RECORD_MODE=all`.

### Tests fail with "no attribute" errors
The test may be using wrong method names. Check the actual API in `src/accessiweather/`.

### Tests marked `live_only` are skipped
This is intentional. Run with `-m "integration"` to include them.
