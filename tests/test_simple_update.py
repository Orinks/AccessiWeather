from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.services.simple_update import (
    build_macos_update_script,
    build_portable_update_script,
    get_release_identifier,
    is_installed_version,
    is_nightly_release,
    is_update_available,
    parse_commit_hash,
    parse_nightly_date,
    plan_restart,
    select_asset,
    select_latest_release,
)


def _release(**overrides):
    data = {
        "tag_name": "v1.0.0",
        "prerelease": False,
        "body": "",
        "published_at": "2025-01-01T00:00:00Z",
        "assets": [],
    }
    data.update(overrides)
    return data


def test_parse_commit_hash_prefers_commit_label():
    notes = "Changelog\n\nCommit: abcdef1234567890"
    assert parse_commit_hash(notes) == "abcdef1234567890"


def test_parse_nightly_date_extracts_date():
    assert parse_nightly_date("nightly-20260131") == "20260131"
    assert parse_nightly_date("Nightly-20260115") == "20260115"
    assert parse_nightly_date("v1.0.0") is None


def test_get_release_identifier_nightly():
    release = _release(tag_name="nightly-20260131")
    identifier, release_type = get_release_identifier(release)
    assert identifier == "20260131"
    assert release_type == "nightly"


def test_get_release_identifier_stable():
    release = _release(tag_name="v1.2.0")
    identifier, release_type = get_release_identifier(release)
    assert identifier == "1.2.0"
    assert release_type == "stable"


def test_is_nightly_release_from_tag_name():
    # Nightly detected by tag name pattern, not commit hash in body
    release = _release(tag_name="nightly-20260131", body="What's New\n\n- Some changes")
    assert is_nightly_release(release) is True

    release_stable = _release(tag_name="v1.0.0", body="Commit: deadbeef")
    assert is_nightly_release(release_stable) is False


def test_select_latest_release_stable_filters_prerelease_and_nightly():
    releases = [
        _release(tag_name="v1.0.0", published_at="2025-01-01T00:00:00Z"),
        _release(tag_name="v1.1.0", prerelease=True, published_at="2025-02-01T00:00:00Z"),
        _release(
            tag_name="nightly-20250202",
            published_at="2025-02-02T00:00:00Z",
        ),
    ]
    latest = select_latest_release(releases, "stable")
    assert latest["tag_name"] == "v1.0.0"


def test_is_update_available_stable_version_compare():
    release = _release(tag_name="v1.2.0")
    assert is_update_available(release, "1.1.0") is True
    assert is_update_available(release, "1.2.0") is False


def test_is_update_available_nightly_date_compare():
    release = _release(tag_name="nightly-20260201")
    # Newer nightly available
    assert is_update_available(release, "1.0.0", "20260131") is True
    # Same nightly date
    assert is_update_available(release, "1.0.0", "20260201") is False
    # Running stable, checking nightly - any nightly is available
    assert is_update_available(release, "1.0.0", None) is True


def test_select_asset_windows_portable():
    release = _release(
        assets=[
            {"name": "AccessiWeather_Setup_v1.0.0.exe"},
            {"name": "AccessiWeather_Portable_v1.0.0.zip"},
        ]
    )
    asset = select_asset(release, portable=True, platform_system="Windows")
    assert asset["name"].endswith(".zip")


def test_build_portable_update_script_contains_extract_and_restart():
    script = build_portable_update_script(
        Path("C:/temp/update.zip"),
        Path("C:/Program Files/AccessiWeather"),
        Path("C:/Program Files/AccessiWeather/AccessiWeather.exe"),
    )
    assert "Expand-Archive" in script
    assert "start" in script


def test_plan_restart_windows_installer():
    plan = plan_restart(Path("C:/temp/installer.exe"), portable=False, platform_system="Windows")
    assert plan.kind == "windows_installer"


def test_plan_restart_macos_creates_script():
    plan = plan_restart(Path("/tmp/update.zip"), portable=False, platform_system="Darwin")
    assert plan.kind == "macos_script"
    assert plan.script_path is not None
    assert plan.script_path.name == "accessiweather_update.sh"


def test_build_macos_update_script_handles_zip():
    script = build_macos_update_script(
        Path("/tmp/update.zip"),
        Path("/Applications/AccessiWeather.app"),
    )
    assert "unzip -o" in script
    assert "open" in script
    assert "rm -f" in script


def test_build_macos_update_script_handles_dmg():
    script = build_macos_update_script(
        Path("/tmp/update.dmg"),
        Path("/Applications/AccessiWeather.app"),
    )
    assert "hdiutil attach" in script
    assert "hdiutil detach" in script


def test_is_installed_version_false_when_not_frozen():
    # When not frozen (running from source), should return False
    with mock.patch.object(sys, "frozen", False, create=True):
        assert is_installed_version() is False


def test_is_installed_version_true_in_program_files():
    with (
        mock.patch.object(sys, "frozen", True, create=True),
        mock.patch.object(sys, "executable", r"C:\Program Files\App\app.exe"),
        mock.patch.dict("os.environ", {"PROGRAMFILES": r"C:\Program Files"}),
    ):
        assert is_installed_version() is True


def test_is_installed_version_false_for_portable():
    with (
        mock.patch.object(sys, "frozen", True, create=True),
        mock.patch.object(sys, "executable", r"D:\PortableApps\App\app.exe"),
        mock.patch.dict(
            "os.environ",
            {"PROGRAMFILES": r"C:\Program Files", "PROGRAMFILES(X86)": r"C:\Program Files (x86)"},
        ),
    ):
        assert is_installed_version() is False


@pytest.mark.asyncio
async def test_simple_update_service_download(tmp_path):
    """Test download_update method."""
    from unittest.mock import AsyncMock, MagicMock

    from accessiweather.services.simple_update import UpdateInfo, UpdateService

    # Create a mock HTTP client
    mock_response = MagicMock()
    mock_response.headers = {"content-length": "100"}
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_bytes(chunk_size=None):
        yield b"x" * 50
        yield b"x" * 50

    mock_response.aiter_bytes = mock_aiter_bytes
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)

    service = UpdateService("TestApp", http_client=mock_client)

    update_info = UpdateInfo(
        version="1.0.0",
        download_url="https://example.com/update.zip",
        artifact_name="update.zip",
        release_notes="Test release",
        commit_hash=None,
        is_nightly=False,
        is_prerelease=False,
    )

    progress_calls = []

    def progress_callback(downloaded, total):
        progress_calls.append((downloaded, total))

    result = await service.download_update(update_info, tmp_path, progress_callback)

    assert result == tmp_path / "update.zip"
    assert result.exists()
    assert result.read_bytes() == b"x" * 100
    assert len(progress_calls) == 2
    assert progress_calls[-1] == (100, 100)


class TestApplyUpdateNoShellInjection:
    """Regression tests: subprocess calls in apply_update must never use shell=True."""

    @patch("accessiweather.services.simple_update.os._exit")
    @patch("accessiweather.services.simple_update.subprocess.Popen")
    @patch("accessiweather.services.simple_update.plan_restart")
    def test_portable_update_uses_shell_false(self, mock_plan, mock_popen, mock_exit, tmp_path):
        """Reject shell=True in portable update subprocess call."""
        from accessiweather.services.simple_update import RestartPlan, apply_update

        script_path = tmp_path / "update.bat"
        mock_plan.return_value = RestartPlan(kind="portable", script_path=script_path, command=None)

        with patch("accessiweather.services.simple_update.Path") as mock_path_cls:
            mock_exe = MagicMock()
            mock_exe.resolve.return_value = tmp_path / "app" / "app.exe"
            mock_exe.parent = tmp_path / "app"
            mock_path_cls.return_value = mock_exe
            with patch(
                "accessiweather.services.simple_update.build_portable_update_script",
                return_value="echo hi",
            ):
                apply_update(tmp_path / "update.zip", portable=True)

        # Verify Popen was called with shell=False (explicitly or via list args)
        assert mock_popen.called
        call_kwargs = mock_popen.call_args
        # shell should be False or not set (default is False)
        shell_val = call_kwargs.kwargs.get("shell", call_kwargs[1].get("shell", False))
        assert shell_val is False, f"subprocess.Popen called with shell={shell_val}, expected False"

    @patch("accessiweather.services.simple_update.os._exit")
    @patch("accessiweather.services.simple_update.subprocess.Popen")
    @patch("accessiweather.services.simple_update.plan_restart")
    def test_windows_installer_uses_shell_false(self, mock_plan, mock_popen, mock_exit, tmp_path):
        """Reject shell=True in windows installer subprocess call."""
        from accessiweather.services.simple_update import RestartPlan, apply_update

        mock_plan.return_value = RestartPlan(
            kind="windows_installer", script_path=None, command=["installer.exe", "/S"]
        )

        apply_update(tmp_path / "update.exe", portable=False, platform_system="Windows")

        assert mock_popen.called
        call_kwargs = mock_popen.call_args
        shell_val = call_kwargs.kwargs.get("shell", call_kwargs[1].get("shell", False))
        assert shell_val is False, f"subprocess.Popen called with shell={shell_val}, expected False"

    def test_no_shell_true_in_source(self):
        """Verify no shell=True in simple_update.py source code."""
        import inspect

        import accessiweather.services.simple_update as mod

        source = inspect.getsource(mod)
        assert "shell=True" not in source, "simple_update.py still contains shell=True"
