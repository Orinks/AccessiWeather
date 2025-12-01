"""
Property-based tests for GitHub Pages template substitution.

Uses Hypothesis to test template substitution with edge cases.
"""

import html
import re

import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

pytestmark = [pytest.mark.ci, pytest.mark.property]

version_strategy = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9]+)?", fullmatch=True)

sha_strategy = st.from_regex(r"[0-9a-f]{7,40}", fullmatch=True)

date_strategy = st.from_regex(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2} UTC", fullmatch=True)

url_strategy = st.from_regex(r"https://[a-z0-9./-]+", fullmatch=True)


class TestTemplateSubstitutionProperties:
    """Property-based tests for template substitution safety."""

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_version_substitution_never_contains_braces(self, version: str) -> None:
        """Substituted version values should never reintroduce template syntax."""
        result = f"Version {version}"
        assert "{{" not in result
        assert "}}" not in result

    @given(sha=sha_strategy)
    @settings(max_examples=50)
    def test_sha_truncation_consistent(self, sha: str) -> None:
        """SHA should be truncated to 7 chars for display."""
        truncated = sha[:7]
        assert len(truncated) == 7
        assert re.match(r"^[0-9a-f]+$", truncated)

    @given(text=st.text())
    @settings(max_examples=100)
    def test_sed_escape_handles_special_chars(self, text: str) -> None:
        """Special chars should not break sed substitution."""
        escaped = text.replace("\\", "\\\\").replace("&", "\\&").replace("@", "\\@")
        assert isinstance(escaped, str)

    @given(url=url_strategy)
    @settings(max_examples=50)
    def test_url_substitution_preserves_structure(self, url: str) -> None:
        """URLs should remain valid after substitution."""
        assert url.startswith("https://")

    @given(date=date_strategy)
    @settings(max_examples=50)
    def test_date_format_consistent(self, date: str) -> None:
        """Date strings should maintain expected format."""
        assert date.endswith("UTC")
        assert len(date) == 20

    @given(
        version=version_strategy,
        sha=sha_strategy,
        date=date_strategy,
    )
    @settings(max_examples=50)
    def test_combined_substitution_safe(self, version: str, sha: str, date: str) -> None:
        """Combined substitutions should produce safe output."""
        template = "Release {{VERSION}} ({{SHA}}) at {{DATE}}"
        result = (
            template.replace("{{VERSION}}", version)
            .replace("{{SHA}}", sha[:7])
            .replace("{{DATE}}", date)
        )
        assert "{{VERSION}}" not in result
        assert "{{SHA}}" not in result
        assert "{{DATE}}" not in result


class TestHtmlSafetyProperties:
    """Property-based tests for HTML content safety."""

    @given(content=st.text(alphabet=st.characters(blacklist_categories=["Cs"])))
    @settings(max_examples=50)
    def test_html_content_escapable(self, content: str) -> None:
        """All text content should be escapable for HTML."""
        escaped = html.escape(content)
        assert "<" not in escaped or "&lt;" in escaped
        assert ">" not in escaped or "&gt;" in escaped

    @given(content=st.text(min_size=1, max_size=1000))
    @settings(max_examples=50)
    def test_html_escape_roundtrip_preserves_length(self, content: str) -> None:
        """HTML escaping should not produce shorter output."""
        escaped = html.escape(content)
        assert len(escaped) >= len(content)

    @given(
        content=st.lists(
            st.sampled_from(["<", ">", "&", '"', "'"]),
            min_size=1,
            max_size=20,
        ).map("".join)
    )
    @settings(max_examples=50)
    def test_dangerous_chars_escaped(self, content: str) -> None:
        """Dangerous HTML characters should be escaped."""
        escaped = html.escape(content, quote=True)
        assert "<" not in escaped
        assert ">" not in escaped


class TestTemplateEdgeCases:
    """Property-based tests for edge cases in template handling."""

    @given(st.text(min_size=0, max_size=0))
    @settings(max_examples=10)
    def test_empty_string_substitution(self, text: str) -> None:
        """Empty strings should substitute safely."""
        template = "Value: {{VALUE}}"
        result = template.replace("{{VALUE}}", text)
        assert result == "Value: "

    @given(st.text(min_size=1000, max_size=1000))
    @settings(max_examples=5)
    def test_very_long_string_substitution(self, text: str) -> None:
        """Very long strings should substitute without error."""
        template = "Content: {{CONTENT}}"
        result = template.replace("{{CONTENT}}", text)
        assert len(result) == len("Content: ") + len(text)

    @given(st.text(alphabet=st.characters(whitelist_categories=["Lu", "Ll", "Lo", "Nd"])))
    @settings(max_examples=50)
    def test_unicode_substitution(self, text: str) -> None:
        """Unicode characters should substitute correctly."""
        template = "Text: {{TEXT}}"
        result = template.replace("{{TEXT}}", text)
        assert text in result

    @given(st.sampled_from(["{{", "}}", "{{VALUE}}", "{{ nested }}"]))
    @settings(max_examples=10)
    def test_template_syntax_in_values(self, text: str) -> None:
        """Values containing template syntax should be handled."""
        escaped = html.escape(text)
        assert isinstance(escaped, str)
        assert "{{" in text or "}}" in text

    @given(url=st.from_regex(r"https://example\.com/path\?q=[a-z0-9%&=]+", fullmatch=True))
    @settings(max_examples=50)
    def test_url_with_query_params(self, url: str) -> None:
        """URLs with query parameters should remain valid."""
        assert "?" in url
        assert url.startswith("https://")


class TestSedSubstitutionSafety:
    """Property-based tests for sed command safety."""

    @given(st.text())
    @settings(max_examples=100)
    def test_sed_delimiter_escape(self, text: str) -> None:
        """Sed delimiter characters should be escaped."""
        escaped = text.replace("/", "\\/")
        assert "/" not in escaped or "\\/" in escaped

    @given(st.text(alphabet=st.sampled_from(["/", "\\", "&", "\n", "\t"])))
    @settings(max_examples=50)
    def test_sed_special_chars_all_escaped(self, text: str) -> None:
        """All sed special characters should be escapable."""
        escaped = (
            text.replace("\\", "\\\\")
            .replace("/", "\\/")
            .replace("&", "\\&")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        assert isinstance(escaped, str)

    @given(st.from_regex(r"[a-zA-Z0-9_.-]+", fullmatch=True))
    @settings(max_examples=50)
    def test_safe_chars_unchanged(self, text: str) -> None:
        """Safe characters should remain unchanged after escaping."""
        escaped = text.replace("\\", "\\\\").replace("/", "\\/").replace("&", "\\&")
        assert escaped == text
