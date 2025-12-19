# HTTP Cassettes

This directory contains recorded HTTP responses ("cassettes") for integration tests. Cassettes are YAML files that capture real API responses, allowing tests to replay them without making live network calls.

## What Are Cassettes?

Cassettes are recordings of HTTP request/response pairs created by [VCR.py](https://vcrpy.readthedocs.io/). When a test runs with recording enabled, VCR captures the HTTP traffic and saves it. On subsequent runs, VCR replays the saved responses instead of hitting the network.

## Directory Structure

- `nws/` - National Weather Service API cassettes
- `openmeteo/` - Open-Meteo API cassettes
- `visual_crossing/` - Visual Crossing API cassettes
- `environmental/` - EPA AirNow and other environmental API cassettes

## Refreshing Cassettes

To record new cassettes or update existing ones:

```bash
LIVE_WEATHER_TESTS=1 pytest tests/integration/ --record-mode=new_episodes -v
```

Record modes:
- `new_episodes` - Record new requests, replay existing ones
- `all` - Re-record everything
- `none` - Only replay, fail on new requests (default in CI)

## Before Committing

**Always scrub secrets from cassettes before committing.** Check for:
- API keys in URLs or headers
- Authentication tokens
- Any personal/sensitive data in responses

The test fixtures should automatically scrub common secrets, but always verify.

## Benefits

- **Deterministic**: Tests produce the same results every run
- **Fast**: No network latency or rate limiting
- **CI-friendly**: No API keys or network access needed in CI
- **Offline**: Develop and test without internet
