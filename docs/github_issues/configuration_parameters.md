# Configuration Parameters Integration (#316)

**Title:** Wire CLI configuration parameters through to the GUI application

## Motivation
- Honor command-line options that users expect to affect runtime behavior (config directory, debug, caching, portable mode).
- Simplify automated deployments that rely on consistent parameter handling across CLI and GUI layers.
- Reduce confusion documented in support requests about flags appearing to do nothing.

## Proposed Solution
1. Update `AccessiWeatherApp` (and related managers) to accept explicit configuration overrides from the CLI surface.
2. Thread configuration objects through startup so logging, caching, and storage locations align with user intent.
3. Extend tests to verify each parameter toggles the correct behaviors.

## References
- `src/accessiweather/main.py:10` - module-level note documenting the current limitation and linking to #316.
- `src/accessiweather/main.py:84` - function docstring note describing the temporary behavior.
- `src/accessiweather/main.py:99` - inline comment explaining the pending constructor update.
- `src/accessiweather/cli.py:43` - CLI epilog advising users that flags are currently no-ops and pointing at #316.

## Alternatives Considered
- Removing the CLI flags until the wiring is complete. Rejected to avoid breaking existing scripts or installers that already pass the parameters.
- Implementing partial support (e.g., only debug mode). Rejected because inconsistent behavior would add more complexity to document and test.

## Phased Approach
1. **Phase 1 – Configuration plumbing:** Accept overrides in `AccessiWeatherApp` and ensure config_dir/portable_mode affect storage paths.
2. **Phase 2 – Runtime features:** Apply debug and caching flags to logging verbosity, feature toggles, and service initialization.
3. **Phase 3 – Hardening:** Add regression tests, update documentation, and record release notes confirming the behavior change.

## Labels
- `backend`
- `cli`
- `needs-updates`

## Milestone
- Target `v0.5.0` to align with broader configuration improvements.
