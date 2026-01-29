"""Tests for the Report Issue dialog."""

from __future__ import annotations

import platform
import sys
from unittest.mock import patch


class TestReportIssueDialog:
    """Test ReportIssueDialog functionality."""

    def test_get_system_info_contains_version(self):
        """System info should contain app version."""
        from accessiweather import __version__
        from accessiweather.ui.dialogs.report_issue_dialog import ReportIssueDialog

        # Mock wx.Dialog to avoid GUI initialization
        with patch.object(ReportIssueDialog, "__init__", lambda self, parent: None):
            dialog = ReportIssueDialog(None)
            dialog._get_system_info = ReportIssueDialog._get_system_info.__get__(
                dialog, ReportIssueDialog
            )
            info = dialog._get_system_info()

            assert __version__ in info
            assert platform.system() in info
            assert sys.version.split()[0] in info

    def test_github_url_constants(self):
        """GitHub URL constants should be correct."""
        from accessiweather.ui.dialogs.report_issue_dialog import (
            GITHUB_REPO,
            ISSUE_URL,
        )

        assert GITHUB_REPO == "Orinks/AccessiWeather"
        assert "github.com" in ISSUE_URL
        assert GITHUB_REPO in ISSUE_URL
        assert "issues/new" in ISSUE_URL


class TestBuildIssueUrl:
    """Test URL building for GitHub issues."""

    def test_url_encoding(self):
        """URL should properly encode special characters."""
        import urllib.parse

        title = "Test & Title"
        body = "Description with <special> chars"

        params = {"title": title, "body": body, "labels": "bug"}
        url = f"https://github.com/test/repo/issues/new?{urllib.parse.urlencode(params)}"

        assert "Test+%26+Title" in url or "Test%20%26%20Title" in url
        assert "%3Cspecial%3E" in url
