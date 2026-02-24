"""Tests for FormatStringParser."""

import pytest

from accessiweather.format_string_parser import FormatStringParser


@pytest.fixture
def parser():
    return FormatStringParser()


class TestGetPlaceholders:
    def test_no_placeholders(self, parser):
        assert parser.get_placeholders("plain text") == []

    def test_single_placeholder(self, parser):
        assert parser.get_placeholders("{temp}") == ["temp"]

    def test_multiple_placeholders(self, parser):
        result = parser.get_placeholders("{temp} and {humidity}")
        assert result == ["temp", "humidity"]

    def test_empty_string(self, parser):
        assert parser.get_placeholders("") == []

    def test_embedded_in_text(self, parser):
        result = parser.get_placeholders("It is {temp} with {wind}")
        assert result == ["temp", "wind"]


class TestValidateFormatString:
    def test_empty_is_valid(self, parser):
        valid, err = parser.validate_format_string("")
        assert valid is True
        assert err is None

    def test_valid_placeholders(self, parser):
        valid, err = parser.validate_format_string("{temp} - {condition}")
        assert valid is True

    def test_unsupported_placeholder(self, parser):
        valid, err = parser.validate_format_string("{bogus}")
        assert valid is False
        assert "bogus" in err

    def test_unbalanced_braces(self, parser):
        valid, err = parser.validate_format_string("{temp")
        assert valid is False
        assert "Unbalanced" in err

    def test_plain_text_valid(self, parser):
        valid, err = parser.validate_format_string("no placeholders here")
        assert valid is True


class TestFormatString:
    def test_basic_substitution(self, parser):
        result = parser.format_string("{temp}", {"temp": "72°F"})
        assert result == "72°F"

    def test_multiple_substitutions(self, parser):
        result = parser.format_string(
            "{temp}, {condition}",
            {"temp": "72°F", "condition": "Sunny"},
        )
        assert result == "72°F, Sunny"

    def test_missing_data_keeps_placeholder(self, parser):
        result = parser.format_string("{temp}", {})
        assert result == "{temp}"

    def test_empty_format_string(self, parser):
        assert parser.format_string("", {"temp": "72"}) == ""

    def test_unbalanced_braces_returns_error(self, parser):
        result = parser.format_string("{temp", {"temp": "72"})
        assert "Error" in result

    def test_numeric_values(self, parser):
        result = parser.format_string("{humidity}%", {"humidity": 65})
        assert result == "65%"

    def test_plain_text_no_substitution(self, parser):
        result = parser.format_string("no placeholders", {"temp": "72"})
        assert result == "no placeholders"


class TestGetSupportedPlaceholdersHelp:
    def test_returns_help_text(self):
        help_text = FormatStringParser.get_supported_placeholders_help()
        assert "temp" in help_text
        assert "condition" in help_text
        assert "Supported Placeholders" in help_text
