"""Tests for Linux AppImage self-update support."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from accessiweather.services.platform_detector import PlatformDetector
from accessiweather.services.simple_update import apply_update, can_auto_apply
from accessiweather.services.update_restart import (
    build_appimage_update_script,
    plan_restart,
    running_appimage_path,
)


def _fake_appimage(tmp_path: Path) -> Path:
    appimage = tmp_path / "AccessiWeather-0.9.0-linux-x86_64.AppImage"
    appimage.write_bytes(b"old")
    return appimage


def test_running_appimage_path_requires_existing_file(tmp_path, monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert running_appimage_path() is None

    missing = tmp_path / "missing.AppImage"
    monkeypatch.setenv("APPIMAGE", str(missing))
    assert running_appimage_path() is None

    appimage = _fake_appimage(tmp_path)
    monkeypatch.setenv("APPIMAGE", str(appimage))
    assert running_appimage_path() == appimage


def test_plan_restart_appimage(tmp_path):
    appimage = _fake_appimage(tmp_path)
    update = tmp_path / "AccessiWeather-1.0.0-linux-x86_64.AppImage"
    update.write_bytes(b"new")

    plan = plan_restart(
        update,
        portable=False,
        platform_system="Linux",
        appimage_path=str(appimage),
    )

    assert plan.kind == "appimage_script"
    assert plan.script_path is not None
    assert plan.command[0] == "bash"


def test_plan_restart_linux_without_appimage_is_unsupported(tmp_path, monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    update = tmp_path / "AccessiWeather-1.0.0-linux.tar.gz"
    update.write_bytes(b"new")

    plan = plan_restart(update, portable=False, platform_system="Linux")

    assert plan.kind == "unsupported"


def test_plan_restart_appimage_run_with_tarball_update_is_unsupported(tmp_path):
    appimage = _fake_appimage(tmp_path)
    update = tmp_path / "AccessiWeather-1.0.0-linux.tar.gz"
    update.write_bytes(b"new")

    plan = plan_restart(
        update,
        portable=False,
        platform_system="Linux",
        appimage_path=str(appimage),
    )

    assert plan.kind == "unsupported"


def test_build_appimage_update_script_quotes_and_replaces(tmp_path):
    appimage = tmp_path / "dir with space" / "App.AppImage"
    appimage.parent.mkdir()
    appimage.write_bytes(b"old")
    update = tmp_path / "App-new.AppImage"
    update.write_bytes(b"new")

    script = build_appimage_update_script(update, appimage)

    assert "'" in script  # paths with spaces are shell-quoted
    assert "chmod +x" in script
    assert "mv -f" in script
    assert "--updated" in script
    # Staged copy sits next to the target so the final rename is atomic.
    assert ".update-new" in script


def test_can_auto_apply_matrix(tmp_path, monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    tarball = tmp_path / "u.tar.gz"
    tarball.write_bytes(b"x")
    assert can_auto_apply(tarball, portable=False, platform_system="Linux") is False

    appimage = _fake_appimage(tmp_path)
    monkeypatch.setenv("APPIMAGE", str(appimage))
    update = tmp_path / "u.AppImage"
    update.write_bytes(b"x")
    assert can_auto_apply(update, portable=False, platform_system="Linux") is True


def test_apply_update_unsupported_returns_false(tmp_path, monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    tarball = tmp_path / "u.tar.gz"
    tarball.write_bytes(b"x")

    result = apply_update(tarball, portable=False, platform_system="Linux")

    assert result is False


def test_apply_update_appimage_writes_script_and_exits(tmp_path, monkeypatch):
    appimage = _fake_appimage(tmp_path)
    monkeypatch.setenv("APPIMAGE", str(appimage))
    update = tmp_path / "u.AppImage"
    update.write_bytes(b"x")

    with (
        patch("accessiweather.services.simple_update.subprocess.Popen") as popen,
        patch("accessiweather.services.simple_update.os._exit") as fake_exit,
    ):
        # os._exit is mocked, so apply_update falls through; that's fine.
        apply_update(update, portable=False, platform_system="Linux")

    assert fake_exit.called
    (args,), _kwargs = popen.call_args
    assert args[0] == "bash"
    script_path = Path(args[1])
    content = script_path.read_text(encoding="utf-8")
    assert str(appimage) in content or "AppImage" in content
    assert "mv -f" in content


def test_platform_detector_reports_appimage_deployment(tmp_path, monkeypatch):
    appimage = _fake_appimage(tmp_path)
    monkeypatch.setenv("APPIMAGE", str(appimage))

    detector = PlatformDetector()
    with patch("platform.system", return_value="Linux"):
        info = detector.get_platform_info()

    assert info.platform == "linux"
    assert info.deployment_type == "appimage"
    assert info.update_capable is True


def test_platform_detector_appimage_artifacts(tmp_path, monkeypatch):
    appimage = _fake_appimage(tmp_path)
    monkeypatch.setenv("APPIMAGE", str(appimage))

    detector = PlatformDetector()
    with patch("platform.system", return_value="Linux"):
        artifacts = detector.get_update_artifacts("1.0.0")

    assert artifacts["installer"] == "AccessiWeather-1.0.0-linux-x86_64.AppImage"
    assert artifacts["portable"] == "AccessiWeather-1.0.0-linux.tar.gz"
