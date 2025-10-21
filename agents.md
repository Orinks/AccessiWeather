# Agent Operations Guide

## API Verification

- Before merging changes, manually verify every agent-backed API integration with a `curl` call to the live service and confirm it returns the expected payload.
- Aviation Weather (NWS) example for TAF retrieval:

```bash
curl --fail --silent "https://aviationweather.gov/api/data/taf?ids=KEWR&format=json"
```

- Inspect the response for a populated `rawTAF` field (for example, KEWR) and address missing data before shipping.

## Toga Development Workflow

- Always activate the shared virtual environment (`source venv/bin/activate`) before running any Briefcase commands so project hooks and plugins load correctly.
- Use `briefcase dev` for live-reload development and `briefcase run` when you need the packaged app experience; both accept `--test` to execute the integrated Briefcase test harness.
- Keep practicing test-driven development when building Toga UI logic—add or update tests before implementation and lean on `briefcase dev --test`, `briefcase run --test`, or `pytest` to validate changes.

## UI Testing with `toga_dummy`

- Point UI tests at the BeeWare dummy backend by exporting `TOGA_BACKEND=toga_dummy` (or configuring the test fixture) so tests run headless without real GUI dependencies.
- Ensure the dummy backend is available in the active environment (`pip install -e ".[dev]"` covers it) before executing the suite.
- Use the dummy backend in CI and local runs so accessibility regressions surface consistently without relying on platform-specific GUI drivers.
