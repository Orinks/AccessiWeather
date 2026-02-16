"""Regression tests for log injection prevention."""

import logging

import pytest

from accessiweather.utils.log_sanitize import sanitize_log


class TestSanitizeLog:
    """Verify that control characters are stripped from log input."""

    def test_should_strip_newlines(self):
        result = sanitize_log("line1\nline2")
        assert "\n" not in result
        assert "\\n" in result

    def test_should_strip_carriage_return(self):
        result = sanitize_log("line1\rline2")
        assert "\r" not in result
        assert "\\r" in result

    def test_should_strip_null_bytes(self):
        result = sanitize_log("before\x00after")
        assert "\x00" not in result

    def test_should_strip_tabs(self):
        result = sanitize_log("col1\tcol2")
        assert "\t" not in result

    def test_should_preserve_normal_text(self):
        assert sanitize_log("New York") == "New York"

    def test_should_handle_empty_string(self):
        assert sanitize_log("") == ""

    def test_should_neutralize_log_forge_attack(self):
        """Attacker tries to inject a fake log line via newline."""
        payload = "NYC\nINFO:root:User logged in as admin"
        result = sanitize_log(payload)
        # The result must be a single line — no real newlines
        assert "\n" not in result
        assert "\\n" in result


class TestLocationManagerLogSanitization:
    """Verify that LocationManager sanitizes queries in log output."""

    @pytest.mark.asyncio
    async def test_should_not_log_raw_newlines_from_query(self, caplog):
        from accessiweather.location_manager import LocationManager

        mgr = LocationManager()
        malicious_query = "test\nFAKE LOG ENTRY"

        with caplog.at_level(logging.INFO):
            # Will fail the geocoding call, but the log should still be sanitized
            import contextlib

            with contextlib.suppress(Exception):
                await mgr.search_locations(malicious_query)

        # Check that no log record contains a raw newline from the payload
        for record in caplog.records:
            assert "\n" not in record.message, (
                f"Raw newline found in log message: {record.message!r}"
            )
