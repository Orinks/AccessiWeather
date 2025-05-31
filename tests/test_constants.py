"""Tests for constants module."""

import pytest


@pytest.mark.unit
def test_constants_import():
    """Test that constants module can be imported."""
    try:
        import accessiweather.constants  # noqa: F401

        # If we get here, the import was successful
        assert True
    except ImportError:
        pytest.fail("Failed to import accessiweather.constants")


@pytest.mark.unit
def test_constants_has_update_interval():
    """Test that UPDATE_INTERVAL constant exists."""
    from accessiweather.constants import UPDATE_INTERVAL

    # Should be a positive integer representing minutes
    assert isinstance(UPDATE_INTERVAL, int)
    assert UPDATE_INTERVAL > 0
