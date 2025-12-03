"""
Utility functions for GitHub Pages template processing.

This module provides functions for:
- Generating nightly.link URLs for artifact downloads
- Extracting asset URLs from GitHub release responses
- Template variable substitution with fallback handling
- Commit SHA truncation

Used by the update-pages.yml workflow to generate the download page.
"""

from __future__ import annotations

import re
from typing import Any

# Repository configuration
REPO_OWNER = "Orinks"
REPO_NAME = "AccessiWeather"
WORKFLOW_NAME = "briefcase-build"  # Must match the actual workflow file name

# nightly.link base URL
NIGHTLY_LINK_BASE = "https://nightly.link"

# GitHub releases base URL
GITHUB_RELEASES_BASE = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases"

# Artifact naming patterns
ARTIFACT_PATTERNS = {
    "windows_installer": "windows-installer-{version}",
    "windows_portable": "windows-portable-{version}",
    "macos_installer": "macOS-installer-{version}",
}


def generate_nightly_link_url(
    branch: str,
    artifact_type: str,
    version: str | None = None,
) -> str:
    """
    Generate a nightly.link URL for downloading workflow artifacts.

    Args:
        branch: The branch name (e.g., 'main', 'dev')
        artifact_type: Type of artifact ('windows_installer', 'windows_portable', 'macos_installer')
        version: Optional version string (e.g., '0.9.3'). If None, uses generic artifact name.

    Returns:
        A nightly.link URL for the artifact.

    Raises:
        ValueError: If artifact_type is not recognized.

    """
    if artifact_type not in ARTIFACT_PATTERNS:
        raise ValueError(
            f"Unknown artifact type: {artifact_type}. Valid types: {list(ARTIFACT_PATTERNS.keys())}"
        )

    pattern = ARTIFACT_PATTERNS[artifact_type]

    if version:
        artifact_name = pattern.format(version=version)
        return f"{NIGHTLY_LINK_BASE}/{REPO_OWNER}/{REPO_NAME}/workflows/{WORKFLOW_NAME}/{branch}/{artifact_name}.zip"
    # Generic URL without version - nightly.link will resolve to latest
    base_name = pattern.split("-{version}")[0]
    return f"{NIGHTLY_LINK_BASE}/{REPO_OWNER}/{REPO_NAME}/workflows/{WORKFLOW_NAME}/{branch}/{base_name}"


def extract_asset_url(
    release_assets: list[dict[str, Any]],
    asset_type: str,
) -> str | None:
    """
    Extract a download URL from GitHub release assets.

    Args:
        release_assets: List of asset dictionaries from GitHub Releases API.
        asset_type: Type of asset to find ('msi', 'dmg', 'portable', 'zip').

    Returns:
        The browser_download_url for the matching asset, or None if not found.

    """
    if not release_assets:
        return None

    asset_type_lower = asset_type.lower()

    for asset in release_assets:
        name = asset.get("name", "").lower()

        if (
            asset_type_lower == "msi"
            and name.endswith(".msi")
            or asset_type_lower == "dmg"
            and name.endswith(".dmg")
            or asset_type_lower == "portable"
            and "portable" in name
            and name.endswith(".zip")
            or asset_type_lower == "zip"
            and name.endswith(".zip")
            and "portable" not in name
        ):
            return asset.get("browser_download_url")

    return None


def truncate_commit_sha(sha: str | None, length: int = 7) -> str:
    """
    Truncate a commit SHA to the specified length.

    Args:
        sha: The full commit SHA string, or None.
        length: Number of characters to keep (default: 7).

    Returns:
        The truncated SHA, or empty string if sha is None/empty.

    """
    if not sha:
        return ""
    return sha[:length]


def substitute_template(
    template_content: str,
    variables: dict[str, str | None],
    fallbacks: dict[str, str] | None = None,
) -> str:
    """
    Substitute template variables in the format {{VARIABLE}}.

    Args:
        template_content: The template string containing {{VARIABLE}} placeholders.
        variables: Dictionary mapping variable names to values.
        fallbacks: Optional dictionary of fallback values for empty/None variables.

    Returns:
        The template with all variables substituted.

    """
    if fallbacks is None:
        fallbacks = {}

    result = template_content

    for var_name, value in variables.items():
        placeholder = f"{{{{{var_name}}}}}"

        # Use fallback if value is None or empty
        if value is None or value == "":
            value = fallbacks.get(var_name, "")

        result = result.replace(placeholder, str(value))

    return result


def verify_no_placeholders(content: str) -> tuple[bool, list[str]]:
    """
    Verify that no template placeholders remain in the content.

    Args:
        content: The processed template content.

    Returns:
        A tuple of (is_valid, list_of_remaining_placeholders).
        is_valid is True if no placeholders remain.

    """
    pattern = r"\{\{([A-Z_]+)\}\}"
    matches = re.findall(pattern, content)
    return len(matches) == 0, matches


# Default fallback values for template variables
DEFAULT_FALLBACKS: dict[str, str] = {
    "MAIN_VERSION": "Latest Release",
    "MAIN_DATE": "Check GitHub",
    "MAIN_COMMIT": "",
    "MAIN_INSTALLER_URL": GITHUB_RELEASES_BASE,
    "MAIN_PORTABLE_URL": GITHUB_RELEASES_BASE,
    "MAIN_MACOS_INSTALLER_URL": GITHUB_RELEASES_BASE,
    "MAIN_HAS_RELEASE": "false",
    "MAIN_RELEASE_NOTES": "<p>No release notes available.</p>",
    "DEV_VERSION": "Development (latest)",
    "DEV_DATE": "Check pre-release page",
    "DEV_COMMIT": "",
    "DEV_RELEASE_URL": GITHUB_RELEASES_BASE,
    "DEV_INSTALLER_URL": GITHUB_RELEASES_BASE,
    "DEV_PORTABLE_URL": GITHUB_RELEASES_BASE,
    "DEV_MACOS_INSTALLER_URL": GITHUB_RELEASES_BASE,
    "DEV_HAS_RELEASE": "false",
    "DEV_RELEASE_NOTES": "<p>No pre-release notes available.</p>",
    "LAST_UPDATED": "",
}
