"""Tests for log sanitization utilities."""

from accessiweather.utils.log_sanitize import sanitize_log


class TestSanitizeLog:
    """Tests for sanitize_log."""

    def test_plain_text_unchanged(self):
        assert sanitize_log("hello world") == "hello world"

    def test_empty_string(self):
        assert sanitize_log("") == ""

    def test_strips_newlines(self):
        result = sanitize_log("line1\nline2")
        assert "\n" not in result
        assert "\\n" in result

    def test_strips_carriage_return(self):
        result = sanitize_log("line1\rline2")
        assert "\r" not in result
        assert "\\r" in result

    def test_strips_tabs(self):
        result = sanitize_log("col1\tcol2")
        assert "\t" not in result
        assert "\\t" in result

    def test_strips_null_byte(self):
        result = sanitize_log("before\x00after")
        assert "\x00" not in result

    def test_preserves_spaces(self):
        assert sanitize_log("hello   world") == "hello   world"

    def test_strips_escape_char(self):
        result = sanitize_log("test\x1binjection")
        assert "\x1b" not in result

    def test_log_injection_attempt(self):
        """Classic log injection: fake log line via newline."""
        malicious = "user input\n2026-01-01 INFO Fake log entry"
        result = sanitize_log(malicious)
        assert "\n" not in result

    def test_unicode_safe(self):
        """Non-ASCII printable characters should be preserved."""
        assert sanitize_log("café ñ 日本語") == "café ñ 日本語"
