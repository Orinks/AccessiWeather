"""
Integration tests for AccessiWeather API clients.

These tests verify actual API behavior using recorded HTTP cassettes.
To record new cassettes or run live tests, set the appropriate environment variables.

Usage:
    # Run with recorded cassettes (default, fast)
    pytest tests/integration/ -v

    # Record new cassettes (requires API keys for some tests)
    RECORD_MODE=all pytest tests/integration/ -v

    # Run live tests without VCR (for validation)
    LIVE_TESTS=true pytest tests/integration/ -v
"""
