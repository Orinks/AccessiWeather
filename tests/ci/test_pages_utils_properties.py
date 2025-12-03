"""
Property-based tests for GitHub Pages utility functions.

Uses Hypothesis to verify correctness properties for URL generation,
template substitution, and data extraction functions.

Run with: pytest tests/ci/test_pages_utils_properties.py -v
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

# Add scripts directory to path for imports
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from pages_utils import (  # noqa: E402
    ARTIFACT_PATTERNS,
    NIGHTLY_LINK_BASE,
    WORKFLOW_NAME,
    extract_asset_url,
    generate_nightly_link_url,
    substitute_template,
    truncate_commit_sha,
    verify_no_placeholders,
)

pytestmark = [pytest.mark.ci, pytest.mark.property]

# Strategies for generating test data
# Use tuples of integers for version to avoid slow regex generation
version_strategy = st.tuples(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=99),
).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}")
branch_strategy = st.sampled_from(["main", "dev"])
artifact_type_strategy = st.sampled_from(list(ARTIFACT_PATTERNS.keys()))
# Use text strategy with hex alphabet for faster SHA generation
sha_strategy = st.text(alphabet="0123456789abcdef", min_size=40, max_size=40)


class TestNightlyLinkUrlProperties:
    """
    Property-based tests for nightly.link URL generation.

    Feature: github-pages-workflow-fix, Property 1: nightly.link URL workflow name correctness
    Feature: github-pages-workflow-fix, Property 2: nightly.link URL format validity
    Feature: github-pages-workflow-fix, Property 3: Artifact naming convention
    """

    @given(branch=branch_strategy, artifact_type=artifact_type_strategy, version=version_strategy)
    @settings(max_examples=100)
    def test_url_contains_briefcase_build_workflow(
        self, branch: str, artifact_type: str, version: str
    ) -> None:
        """
        Feature: github-pages-workflow-fix, Property 1: nightly.link URL workflow name correctness.

        For any generated nightly.link URL, the URL path SHALL contain
        'workflows/briefcase-build/' and SHALL NOT contain 'workflows/build/'
        (without the 'briefcase-' prefix).
        """
        url = generate_nightly_link_url(branch, artifact_type, version)

        # Must contain the correct workflow name
        assert f"workflows/{WORKFLOW_NAME}/" in url
        assert "workflows/briefcase-build/" in url

        # Must NOT contain the incorrect pattern 'workflows/build/' (without briefcase-)
        # The correct pattern is 'workflows/briefcase-build/'
        # We check that '/build/' only appears after 'briefcase' in the URL
        assert "/workflows/build/" not in url.replace(
            "/workflows/briefcase-build/", "/workflows/REPLACED/"
        )

    @given(branch=branch_strategy, artifact_type=artifact_type_strategy, version=version_strategy)
    @settings(max_examples=100)
    def test_url_format_validity(self, branch: str, artifact_type: str, version: str) -> None:
        """
        Feature: github-pages-workflow-fix, Property 2: nightly.link URL format validity.

        For any generated nightly.link URL, the URL SHALL match the pattern
        'https://nightly.link/Orinks/AccessiWeather/workflows/briefcase-build/{branch}/{artifact-name}.zip'
        """
        url = generate_nightly_link_url(branch, artifact_type, version)

        # Verify URL structure
        assert url.startswith(NIGHTLY_LINK_BASE)
        assert "/Orinks/AccessiWeather/" in url
        assert f"/workflows/{WORKFLOW_NAME}/" in url
        assert f"/{branch}/" in url
        assert url.endswith(".zip")

        # Verify full pattern match
        pattern = rf"^{re.escape(NIGHTLY_LINK_BASE)}/Orinks/AccessiWeather/workflows/{WORKFLOW_NAME}/{branch}/[a-zA-Z0-9_-]+-{re.escape(version)}\.zip$"
        assert re.match(pattern, url), f"URL {url} does not match expected pattern"

    @given(branch=branch_strategy, artifact_type=artifact_type_strategy, version=version_strategy)
    @settings(max_examples=100)
    def test_artifact_naming_convention(
        self, branch: str, artifact_type: str, version: str
    ) -> None:
        """
        Feature: github-pages-workflow-fix, Property 3: Artifact naming convention.

        For any artifact URL containing a version string, the artifact name SHALL
        follow the pattern '{platform}-{type}-{version}' where platform is 'windows'
        or 'macOS', type is 'installer' or 'portable'.
        """
        url = generate_nightly_link_url(branch, artifact_type, version)

        # Extract artifact name from URL (last path segment without .zip)
        artifact_name = url.split("/")[-1].replace(".zip", "")

        # Verify naming pattern
        pattern = r"^(windows|macOS)-(installer|portable)-[0-9]+\.[0-9]+\.[0-9]+$"
        assert re.match(pattern, artifact_name), (
            f"Artifact name {artifact_name} does not match pattern"
        )

        # Verify version is in the artifact name
        assert version in artifact_name

    @given(branch=branch_strategy, artifact_type=artifact_type_strategy)
    @settings(max_examples=50)
    def test_url_without_version_still_valid(self, branch: str, artifact_type: str) -> None:
        """URLs generated without version should still be valid nightly.link URLs."""
        url = generate_nightly_link_url(branch, artifact_type, version=None)

        assert url.startswith(NIGHTLY_LINK_BASE)
        assert f"/workflows/{WORKFLOW_NAME}/" in url
        assert f"/{branch}/" in url
        # Without version, URL should not end with .zip
        assert not url.endswith(".zip")


class TestAssetUrlExtractionProperties:
    """
    Property-based tests for release asset URL extraction.

    Feature: github-pages-workflow-fix, Property 4: Release asset URL extraction
    """

    @given(
        version=version_strategy,
        asset_type=st.sampled_from(["msi", "dmg", "portable"]),
    )
    @settings(max_examples=100)
    def test_asset_url_extraction_from_valid_assets(self, version: str, asset_type: str) -> None:
        """
        Feature: github-pages-workflow-fix, Property 4: Release asset URL extraction.

        For any GitHub release response containing assets with MSI, DMG, or ZIP files,
        the generated download URLs SHALL be extracted from the 'browser_download_url'
        field of matching assets.
        """
        # Generate mock release assets
        base_url = f"https://github.com/Orinks/AccessiWeather/releases/download/v{version}"

        if asset_type == "msi":
            filename = f"AccessiWeather-{version}.msi"
        elif asset_type == "dmg":
            filename = f"AccessiWeather-{version}.dmg"
        else:  # portable
            filename = f"AccessiWeather_Portable_v{version}.zip"

        assets = [
            {
                "name": filename,
                "browser_download_url": f"{base_url}/{filename}",
            }
        ]

        result = extract_asset_url(assets, asset_type)

        # Should extract the URL
        assert result is not None
        assert result == f"{base_url}/{filename}"
        assert result.startswith("https://github.com/")

    @given(asset_type=st.sampled_from(["msi", "dmg", "portable", "zip"]))
    @settings(max_examples=50)
    def test_empty_assets_returns_none(self, asset_type: str) -> None:
        """Empty asset list should return None."""
        result = extract_asset_url([], asset_type)
        assert result is None

    @given(asset_type=st.sampled_from(["msi", "dmg", "portable"]))
    @settings(max_examples=50)
    def test_missing_asset_type_returns_none(self, asset_type: str) -> None:
        """Assets without matching type should return None."""
        # Create assets that don't match the requested type
        assets = [
            {"name": "README.md", "browser_download_url": "https://example.com/README.md"},
            {"name": "checksums.txt", "browser_download_url": "https://example.com/checksums.txt"},
        ]
        result = extract_asset_url(assets, asset_type)
        assert result is None


class TestCommitShaTruncationProperties:
    """
    Property-based tests for commit SHA truncation.

    Feature: github-pages-workflow-fix, Property 5: Commit SHA truncation
    """

    @given(sha=sha_strategy)
    @settings(max_examples=100)
    def test_sha_truncation_length(self, sha: str) -> None:
        """
        Feature: github-pages-workflow-fix, Property 5: Commit SHA truncation.

        For any displayed commit SHA, the output SHALL be exactly 7 characters
        (or empty if no commit available), representing the first 7 characters
        of the full SHA.
        """
        result = truncate_commit_sha(sha)

        assert len(result) == 7
        assert result == sha[:7]
        # Should only contain hex characters
        assert re.match(r"^[0-9a-f]+$", result)

    @given(sha=sha_strategy, length=st.integers(min_value=1, max_value=40))
    @settings(max_examples=100)
    def test_sha_truncation_custom_length(self, sha: str, length: int) -> None:
        """SHA truncation with custom length should work correctly."""
        result = truncate_commit_sha(sha, length=length)

        assert len(result) == length
        assert result == sha[:length]

    def test_sha_truncation_none_returns_empty(self) -> None:
        """None SHA should return empty string."""
        result = truncate_commit_sha(None)
        assert result == ""

    def test_sha_truncation_empty_returns_empty(self) -> None:
        """Empty SHA should return empty string."""
        result = truncate_commit_sha("")
        assert result == ""


class TestTemplateSubstitutionProperties:
    """
    Property-based tests for template variable substitution.

    Feature: github-pages-workflow-fix, Property 6: Template placeholder substitution completeness
    Feature: github-pages-workflow-fix, Property 7: Empty value fallback handling
    """

    @given(
        var_name=st.from_regex(r"[A-Z][A-Z_]{2,20}", fullmatch=True),
        value=st.text(
            min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=["Cs"])
        ),
    )
    @settings(max_examples=100)
    def test_placeholder_substitution_completeness(self, var_name: str, value: str) -> None:
        """
        Feature: github-pages-workflow-fix, Property 6: Template placeholder substitution completeness.

        For any template string containing {{VARIABLE}} placeholders and a corresponding
        values map, the output string SHALL NOT contain any '{{' or '}}' sequences.
        """
        template = f"Before {{{{{var_name}}}}} After"
        variables = {var_name: value}

        result = substitute_template(template, variables)

        # No placeholders should remain
        assert "{{" not in result
        assert "}}" not in result
        # Value should be in result
        assert value in result

    @given(
        var_names=st.lists(
            st.from_regex(r"[A-Z][A-Z_]{2,10}", fullmatch=True),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        values=st.lists(
            st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=["Cs"])),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_multiple_placeholders_all_substituted(
        self, var_names: list[str], values: list[str]
    ) -> None:
        """Multiple placeholders should all be substituted."""
        # Ensure we have matching lengths
        min_len = min(len(var_names), len(values))
        var_names = var_names[:min_len]
        values = values[:min_len]

        # Build template with multiple placeholders
        template_parts = [f"{{{{{name}}}}}" for name in var_names]
        template = " | ".join(template_parts)

        variables = dict(zip(var_names, values, strict=False))
        result = substitute_template(template, variables)

        # Verify no placeholders remain
        is_valid, remaining = verify_no_placeholders(result)
        assert is_valid, f"Remaining placeholders: {remaining}"

    @given(
        var_name=st.from_regex(r"[A-Z][A-Z_]{2,20}", fullmatch=True),
        fallback=st.text(
            min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=["Cs"])
        ),
    )
    @settings(max_examples=100)
    def test_empty_value_uses_fallback(self, var_name: str, fallback: str) -> None:
        """
        Feature: github-pages-workflow-fix, Property 7: Empty value fallback handling.

        For any template variable with an empty, null, or undefined value,
        the substitution SHALL replace the placeholder with the defined fallback
        value (not an empty string or the original placeholder).
        """
        template = f"Value: {{{{{var_name}}}}}"
        variables = {var_name: None}  # None value
        fallbacks = {var_name: fallback}

        result = substitute_template(template, variables, fallbacks)

        # Placeholder should be replaced with fallback
        assert "{{" not in result
        assert fallback in result
        assert result == f"Value: {fallback}"

    @given(
        var_name=st.from_regex(r"[A-Z][A-Z_]{2,20}", fullmatch=True),
        fallback=st.text(
            min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=["Cs"])
        ),
    )
    @settings(max_examples=100)
    def test_empty_string_uses_fallback(self, var_name: str, fallback: str) -> None:
        """Empty string values should also use fallback."""
        template = f"Value: {{{{{var_name}}}}}"
        variables = {var_name: ""}  # Empty string
        fallbacks = {var_name: fallback}

        result = substitute_template(template, variables, fallbacks)

        assert "{{" not in result
        assert fallback in result

    @given(
        template_text=st.text(
            min_size=10, max_size=200, alphabet=st.characters(blacklist_categories=["Cs"])
        ),
    )
    @settings(max_examples=50)
    def test_template_without_placeholders_unchanged(self, template_text: str) -> None:
        """Templates without placeholders should remain unchanged."""
        # Ensure no accidental placeholders in generated text
        template_text = template_text.replace("{", "[").replace("}", "]")

        result = substitute_template(template_text, {})

        assert result == template_text


class TestVerifyNoPlaceholdersProperties:
    """Property-based tests for placeholder verification."""

    @given(
        var_names=st.lists(
            st.from_regex(r"[A-Z][A-Z_]{2,10}", fullmatch=True),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @settings(max_examples=50)
    def test_detects_remaining_placeholders(self, var_names: list[str]) -> None:
        """Should detect all remaining placeholders."""
        template = " ".join(f"{{{{{name}}}}}" for name in var_names)

        is_valid, remaining = verify_no_placeholders(template)

        assert not is_valid
        assert set(remaining) == set(var_names)

    @given(
        text=st.text(
            min_size=10, max_size=200, alphabet=st.characters(blacklist_categories=["Cs"])
        ),
    )
    @settings(max_examples=50)
    def test_clean_text_passes_verification(self, text: str) -> None:
        """Text without placeholders should pass verification."""
        # Remove any accidental placeholder-like patterns
        clean_text = text.replace("{", "[").replace("}", "]")

        is_valid, remaining = verify_no_placeholders(clean_text)

        assert is_valid
        assert remaining == []
