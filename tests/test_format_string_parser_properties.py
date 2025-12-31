"""
Property-based tests for format string parser.

These tests verify correctness properties of the FormatStringParser class
using Hypothesis for exhaustive input space exploration.
"""

from __future__ import annotations

import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

from accessiweather.format_string_parser import FormatStringParser

# -----------------------------------------------------------------------------
# Hypothesis Strategies for generating test data
# -----------------------------------------------------------------------------

SUPPORTED_PLACEHOLDERS = list(FormatStringParser.SUPPORTED_PLACEHOLDERS.keys())

placeholder_names = st.sampled_from(SUPPORTED_PLACEHOLDERS)

placeholder_values = st.one_of(
    st.text(min_size=0, max_size=50),
    st.integers().map(str),
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: f"{f:.1f}"),
    st.just("N/A"),
    st.just(""),
)


@st.composite
def valid_format_string(draw: st.DrawFn) -> str:
    """Generate a valid format string with supported placeholders."""
    num_placeholders = draw(st.integers(min_value=0, max_value=5))
    parts: list[str] = []

    for _ in range(num_placeholders):
        prefix = draw(st.text(min_size=0, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz :,.-"))
        placeholder = draw(placeholder_names)
        parts.append(f"{prefix}{{{placeholder}}}")

    suffix = draw(st.text(min_size=0, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz :,.-"))
    parts.append(suffix)

    return "".join(parts)


@st.composite
def valid_format_string_with_data(draw: st.DrawFn) -> tuple[str, dict[str, str]]:
    """Generate a valid format string with matching data dictionary."""
    format_str = draw(valid_format_string())
    parser = FormatStringParser()
    placeholders = parser.get_placeholders(format_str)

    data = {p: draw(placeholder_values) for p in placeholders}
    return format_str, data


@st.composite
def unbalanced_braces_string(draw: st.DrawFn) -> str:
    """Generate a string with unbalanced braces."""
    base = draw(st.text(min_size=0, max_size=20, alphabet="abcdefghijklmnop "))
    choice = draw(st.integers(min_value=0, max_value=3))

    if choice == 0:
        return base + "{"
    if choice == 1:
        return base + "}"
    if choice == 2:
        return "{" + base + "{" + base
    return base + "}" + base + "}"


@st.composite
def unknown_placeholder_string(draw: st.DrawFn) -> str:
    """Generate a format string with unknown placeholders."""
    prefix = draw(st.text(min_size=0, max_size=10, alphabet="abcdefghijklmnop "))
    unknown_name = draw(
        st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz_").filter(
            lambda s: s not in SUPPORTED_PLACEHOLDERS
        )
    )
    suffix = draw(st.text(min_size=0, max_size=10, alphabet="abcdefghijklmnop "))
    return f"{prefix}{{{unknown_name}}}{suffix}"


# -----------------------------------------------------------------------------
# Property Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
class TestValidFormatStringDoesNotCrash:
    """Tests that valid format strings don't crash when formatted."""

    @given(data=valid_format_string_with_data())
    @settings(max_examples=50)
    def test_valid_format_string_does_not_crash(self, data: tuple[str, dict[str, str]]) -> None:
        """Valid format strings should never cause format_string to crash."""
        format_str, values = data
        parser = FormatStringParser()

        is_valid, _ = parser.validate_format_string(format_str)
        if is_valid:
            result = parser.format_string(format_str, values)
            assert isinstance(result, str)


@pytest.mark.unit
class TestPlaceholderReplacement:
    """Tests that format_string replaces placeholders with values."""

    @given(data=valid_format_string_with_data())
    @settings(max_examples=50)
    def test_all_placeholders_replaced(self, data: tuple[str, dict[str, str]]) -> None:
        """All provided placeholder values should appear in the result."""
        format_str, values = data
        parser = FormatStringParser()

        result = parser.format_string(format_str, values)

        for placeholder, value in values.items():
            placeholder_pattern = f"{{{placeholder}}}"
            if placeholder_pattern in format_str and value:
                assert str(value) in result, (
                    f"Value '{value}' for placeholder '{placeholder}' not found in result"
                )

    @given(data=valid_format_string_with_data())
    @settings(max_examples=50)
    def test_no_placeholder_syntax_remains(self, data: tuple[str, dict[str, str]]) -> None:
        """After formatting, no supported placeholder syntax should remain."""
        format_str, values = data
        parser = FormatStringParser()

        result = parser.format_string(format_str, values)

        for placeholder in values:
            assert f"{{{placeholder}}}" not in result, (
                f"Placeholder '{{{placeholder}}}' should have been replaced"
            )


@pytest.mark.unit
class TestUnbalancedBracesDetection:
    """Tests that mismatched braces fail validation."""

    @given(format_str=unbalanced_braces_string())
    @settings(max_examples=50)
    def test_unbalanced_braces_fail_validation(self, format_str: str) -> None:
        """Strings with unbalanced braces should fail validation."""
        parser = FormatStringParser()
        is_valid, error = parser.validate_format_string(format_str)

        assert not is_valid, f"Unbalanced braces string '{format_str}' should fail validation"
        assert error is not None
        assert "unbalanced" in error.lower() or "brace" in error.lower()


@pytest.mark.unit
class TestUnknownPlaceholderBehavior:
    """Tests that unknown placeholders behavior is consistent."""

    @given(format_str=unknown_placeholder_string())
    @settings(max_examples=50)
    def test_unknown_placeholders_fail_validation(self, format_str: str) -> None:
        """Unknown placeholders should fail validation."""
        parser = FormatStringParser()
        is_valid, error = parser.validate_format_string(format_str)

        assert not is_valid, f"Unknown placeholder string '{format_str}' should fail validation"
        assert error is not None
        assert "unsupported" in error.lower() or "placeholder" in error.lower()

    @given(format_str=unknown_placeholder_string())
    @settings(max_examples=50)
    def test_unknown_placeholders_preserved_in_output(self, format_str: str) -> None:
        """Unknown placeholders should be preserved (not replaced) in output."""
        parser = FormatStringParser()
        placeholders = parser.get_placeholders(format_str)

        result = parser.format_string(format_str, {})

        for placeholder in placeholders:
            if placeholder not in SUPPORTED_PLACEHOLDERS:
                assert f"{{{placeholder}}}" in result, (
                    f"Unknown placeholder '{{{placeholder}}}' should be preserved in output"
                )


@pytest.mark.unit
class TestGetPlaceholdersProperties:
    """Tests that get_placeholders returns unique, ordered list."""

    @given(format_str=valid_format_string())
    @settings(max_examples=50)
    def test_placeholders_match_regex_order(self, format_str: str) -> None:
        """Placeholders should be returned in order of regex matches."""
        import re

        parser = FormatStringParser()
        placeholders = parser.get_placeholders(format_str)

        expected = re.findall(r"\{([a-zA-Z_]+)\}", format_str)
        assert placeholders == expected, (
            f"Placeholders {placeholders} should match regex order {expected}"
        )

    @given(format_str=valid_format_string())
    @settings(max_examples=50)
    def test_all_placeholders_are_supported(self, format_str: str) -> None:
        """All returned placeholders should be from the supported set."""
        parser = FormatStringParser()
        placeholders = parser.get_placeholders(format_str)

        for placeholder in placeholders:
            assert placeholder in SUPPORTED_PLACEHOLDERS, (
                f"Placeholder '{placeholder}' should be in supported set"
            )

    @given(format_str=st.text(min_size=0, max_size=100))
    @settings(max_examples=50)
    def test_get_placeholders_returns_list(self, format_str: str) -> None:
        """get_placeholders should always return a list."""
        parser = FormatStringParser()
        result = parser.get_placeholders(format_str)
        assert isinstance(result, list)


@pytest.mark.unit
class TestCrashResistance:
    """Tests that parser handles any string input without exceptions."""

    @given(format_str=st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_validate_never_crashes(self, format_str: str) -> None:
        """validate_format_string should never raise an exception."""
        parser = FormatStringParser()
        is_valid, error = parser.validate_format_string(format_str)

        assert isinstance(is_valid, bool)
        assert error is None or isinstance(error, str)

    @given(format_str=st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_format_string_never_crashes(self, format_str: str) -> None:
        """format_string should never raise an exception."""
        parser = FormatStringParser()
        result = parser.format_string(format_str, {})
        assert isinstance(result, str)

    @given(
        format_str=st.text(min_size=0, max_size=500),
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_"),
            values=st.text(min_size=0, max_size=50),
            max_size=10,
        ),
    )
    @settings(max_examples=50)
    def test_format_string_with_arbitrary_data_never_crashes(
        self, format_str: str, data: dict[str, str]
    ) -> None:
        """format_string should never raise an exception with arbitrary data."""
        parser = FormatStringParser()
        result = parser.format_string(format_str, data)
        assert isinstance(result, str)

    @given(format_str=st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_get_placeholders_never_crashes(self, format_str: str) -> None:
        """get_placeholders should never raise an exception."""
        parser = FormatStringParser()
        result = parser.get_placeholders(format_str)
        assert isinstance(result, list)


@pytest.mark.unit
class TestEmptyInputHandling:
    """Property tests for empty/edge case inputs."""

    def test_empty_string_is_valid(self) -> None:
        """Empty string should be valid."""
        parser = FormatStringParser()
        is_valid, error = parser.validate_format_string("")
        assert is_valid
        assert error is None

    def test_empty_string_returns_empty(self) -> None:
        """Empty string should return empty string."""
        parser = FormatStringParser()
        result = parser.format_string("", {"temp": "72"})
        assert result == ""

    def test_empty_string_has_no_placeholders(self) -> None:
        """Empty string should have no placeholders."""
        parser = FormatStringParser()
        result = parser.get_placeholders("")
        assert result == []

    @given(format_str=valid_format_string())
    @settings(max_examples=50)
    def test_empty_data_preserves_unknown_placeholders(self, format_str: str) -> None:
        """With empty data dict, placeholders should remain in output."""
        parser = FormatStringParser()
        result = parser.format_string(format_str, {})
        placeholders = parser.get_placeholders(format_str)

        for placeholder in placeholders:
            assert f"{{{placeholder}}}" in result
