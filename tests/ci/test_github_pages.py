"""
Tests for GitHub Pages template and workflow validation.

These tests validate the GitHub Pages HTML template structure,
template variable substitution, and download link generation.

Marked with 'ci' marker to separate from main application tests.
Run with: pytest tests/ci/ -v
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.ci


@pytest.fixture
def template_path():
    return Path(__file__).parent.parent.parent / "docs" / "index.template.html"


@pytest.fixture
def template_content(template_path):
    return template_path.read_text()


@pytest.fixture
def template_variables():
    return [
        "MAIN_VERSION",
        "MAIN_DATE",
        "MAIN_COMMIT",
        "MAIN_INSTALLER_URL",
        "MAIN_PORTABLE_URL",
        "MAIN_MACOS_INSTALLER_URL",
        "MAIN_HAS_RELEASE",
        "MAIN_RELEASE_NOTES",
        "DEV_VERSION",
        "DEV_DATE",
        "DEV_COMMIT",
        "DEV_INSTALLER_URL",
        "DEV_PORTABLE_URL",
        "DEV_MACOS_INSTALLER_URL",
        "DEV_HAS_RELEASE",
        "DEV_RECENT_COMMITS",
        "DEV_RELEASE_URL",
        "LAST_UPDATED",
    ]


class TestTemplateStructure:
    """Tests for the HTML template file structure."""

    def test_template_exists(self, template_path):
        """Verify the template file exists."""
        assert template_path.exists(), f"Template file not found at {template_path}"

    def test_template_is_valid_html(self, template_content):
        """Verify the template has basic HTML structure."""
        assert "<!DOCTYPE html>" in template_content
        assert "<html" in template_content
        assert "</html>" in template_content
        assert "<head>" in template_content
        assert "</head>" in template_content
        assert "<body>" in template_content
        assert "</body>" in template_content

    def test_all_template_variables_defined(self, template_content, template_variables):
        """Verify all expected template variables are present in the template."""
        for var in template_variables:
            pattern = f"{{{{{var}}}}}"
            assert pattern in template_content, f"Template variable {{{{{var}}}}} not found"

    def test_html_structure_valid(self, template_content):
        """Verify the HTML has proper structure with required elements."""
        assert "<title>" in template_content
        assert "</title>" in template_content
        assert "AccessiWeather" in template_content

    def test_stable_section_exists(self, template_content):
        """Verify the stable release section exists."""
        assert 'class="download-section stable"' in template_content
        assert 'id="main-section"' in template_content
        assert "Stable Release" in template_content

    def test_dev_section_exists(self, template_content):
        """Verify the development build section exists."""
        assert 'class="download-section dev"' in template_content
        assert 'id="dev-section"' in template_content
        assert "Development Build" in template_content

    def test_footer_exists(self, template_content):
        """Verify footer section with links exists."""
        assert "<footer" in template_content
        assert "View on GitHub" in template_content
        assert "github.com/Orinks/AccessiWeather" in template_content


class TestDownloadUrls:
    """Tests for download button and URL structure."""

    def test_windows_installer_button_exists(self, template_content):
        """Verify Windows installer download buttons exist for both sections."""
        assert 'id="main-installer"' in template_content
        assert 'id="dev-installer"' in template_content
        assert "Installer (.msi)" in template_content

    def test_windows_portable_button_exists(self, template_content):
        """Verify Windows portable download buttons exist."""
        assert 'id="main-portable"' in template_content
        assert 'id="dev-portable"' in template_content
        assert "Portable (.zip)" in template_content

    def test_macos_download_buttons_exist(self, template_content):
        """Verify macOS download buttons exist for both sections."""
        assert 'id="main-macos-installer"' in template_content
        assert 'id="dev-macos-installer"' in template_content
        assert "Installer (.dmg)" in template_content

    def test_main_installer_url_uses_template_variable(self, template_content):
        """Verify main installer URL uses the correct template variable."""
        assert 'href="{{MAIN_INSTALLER_URL}}"' in template_content

    def test_main_portable_url_uses_template_variable(self, template_content):
        """Verify main portable URL uses the correct template variable."""
        assert 'href="{{MAIN_PORTABLE_URL}}"' in template_content

    def test_main_macos_url_uses_template_variable(self, template_content):
        """Verify main macOS URL uses the correct template variable."""
        assert 'href="{{MAIN_MACOS_INSTALLER_URL}}"' in template_content

    def test_download_buttons_have_aria_labels(self, template_content):
        """Verify download buttons have accessibility labels."""
        assert 'aria-label="Download Windows Installer"' in template_content
        assert 'aria-label="Download Windows Portable"' in template_content
        assert 'aria-label="Download macOS Installer"' in template_content
        assert 'aria-label="Download Windows Installer (Dev)"' in template_content
        assert 'aria-label="Download Windows Portable (Dev)"' in template_content
        assert 'aria-label="Download macOS Installer (Dev)"' in template_content

    def test_platform_groups_exist(self, template_content):
        """Verify platform groupings exist for Windows and macOS."""
        assert 'class="platform-label">Windows</span>' in template_content.replace("\n", "")
        assert 'class="platform-label">macOS</span>' in template_content.replace("\n", "")


class TestTemplateVariables:
    """Tests for template variable patterns and substitution."""

    def test_variable_pattern_format(self, template_content):
        """Verify all template variables use the {{VAR}} pattern."""
        pattern = r"\{\{([A-Z_]+)\}\}"
        matches = re.findall(pattern, template_content)
        assert len(matches) > 0, "No template variables found"
        for match in matches:
            assert match.isupper(), f"Variable {match} should be uppercase"
            assert "_" in match or match.isalpha(), f"Variable {match} has invalid format"

    def test_no_malformed_template_variables(self, template_content):
        """Verify there are no malformed template variables (single braces, lowercase)."""
        single_brace_pattern = r"(?<!\{)\{[A-Z_]+\}(?!\})"
        matches = re.findall(single_brace_pattern, template_content)
        assert len(matches) == 0, f"Found malformed single-brace variables: {matches}"

    def test_all_template_variables_properly_closed(self, template_content):
        """Verify all template variables have proper {{VAR}} format."""
        pattern = r"\{\{([A-Z_]+)\}\}"
        matches = re.findall(pattern, template_content)
        for match in matches:
            full_var = f"{{{{{match}}}}}"
            opening_idx = template_content.find(full_var)
            assert opening_idx != -1, f"Variable {full_var} not properly formatted"

    def test_javascript_build_info_contains_variables(self, template_content):
        """Verify the JavaScript buildInfo object contains template variables."""
        assert "const buildInfo = {" in template_content
        assert "main:" in template_content
        assert "dev:" in template_content
        assert "version: '{{MAIN_VERSION}}'" in template_content
        assert "version: '{{DEV_VERSION}}'" in template_content

    def test_version_info_sections_exist(self, template_content):
        """Verify version info sections contain all required fields."""
        assert 'id="main-version"' in template_content
        assert 'id="dev-version"' in template_content
        assert 'id="main-date"' in template_content
        assert 'id="dev-date"' in template_content
        assert 'id="main-commit"' in template_content
        assert 'id="dev-commit"' in template_content

    def test_last_updated_field_exists(self, template_content):
        """Verify the last updated field uses template variable."""
        assert 'id="last-updated"' in template_content
        assert "{{LAST_UPDATED}}" in template_content


class TestReleaseNotesSection:
    """Tests for release notes and commit history sections."""

    def test_main_release_notes_section_exists(self, template_content):
        """Verify main release notes section exists."""
        assert "Release Notes" in template_content
        assert "{{MAIN_RELEASE_NOTES}}" in template_content

    def test_dev_recent_commits_section_exists(self, template_content):
        """Verify dev recent commits section exists."""
        assert "Recent Changes" in template_content
        assert "{{DEV_RECENT_COMMITS}}" in template_content

    def test_commit_list_styling_exists(self, template_content):
        """Verify commit list has proper CSS styling."""
        assert "commit-list" in template_content


class TestHasReleaseFlags:
    """Tests for release availability flags."""

    def test_main_has_release_flag_exists(self, template_content):
        """Verify main section has release availability flag."""
        assert 'data-has-release="{{MAIN_HAS_RELEASE}}"' in template_content

    def test_dev_has_release_flag_exists(self, template_content):
        """Verify dev section has release availability flag."""
        assert 'data-has-release="{{DEV_HAS_RELEASE}}"' in template_content

    def test_hide_downloads_function_exists(self, template_content):
        """Verify JavaScript function to hide downloads when no release exists."""
        assert "hideDownloadsIfNoRelease" in template_content


class TestAccessibility:
    """Tests for accessibility features in the template."""

    def test_html_has_lang_attribute(self, template_content):
        """Verify HTML element has lang attribute for accessibility."""
        assert 'lang="en"' in template_content

    def test_all_images_have_viewbox(self, template_content):
        """Verify SVG icons have viewBox for proper scaling."""
        svg_pattern = r"<svg[^>]*>"
        svgs = re.findall(svg_pattern, template_content)
        for svg in svgs:
            assert "viewBox" in svg, f"SVG missing viewBox: {svg}"

    def test_download_buttons_have_download_btn_class(self, template_content):
        """Verify all download buttons use consistent styling class."""
        download_links = re.findall(r'<a[^>]*class="download-btn[^"]*"[^>]*>', template_content)
        assert len(download_links) >= 6, "Expected at least 6 download buttons"


class TestUrlFormatValidation:
    """Tests for URL format validation patterns."""

    def test_github_repo_links_format(self, template_content):
        """Verify GitHub repository links are properly formatted."""
        github_links = re.findall(
            r'href="(https://github\.com/Orinks/AccessiWeather[^"]*)"', template_content
        )
        assert len(github_links) >= 3, "Expected at least 3 GitHub links"
        for link in github_links:
            assert link.startswith("https://github.com/Orinks/AccessiWeather")

    def test_external_links_have_target_blank(self, template_content):
        """Verify external links open in new tab."""
        github_link_pattern = r'<a[^>]*href="https://github\.com[^"]*"[^>]*>'
        github_links = re.findall(github_link_pattern, template_content)
        for link in github_links:
            assert 'target="_blank"' in link, f"External link missing target='_blank': {link}"
