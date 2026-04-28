from __future__ import annotations

from types import SimpleNamespace

from accessiweather.services.startup_utils import StartupManager


def _manager_for_windows(tmp_path):
    platform_detector = SimpleNamespace(
        get_platform_info=lambda: SimpleNamespace(
            platform="windows",
            app_directory=tmp_path,
        )
    )
    return StartupManager(platform_detector=platform_detector)


def test_launch_command_uses_executable_for_nuitka_runtime(monkeypatch, tmp_path):
    from accessiweather.services import startup_utils

    exe_path = tmp_path / "AccessiWeather.exe"
    manager = _manager_for_windows(tmp_path)

    monkeypatch.setattr(startup_utils, "is_compiled_runtime", lambda: True)
    monkeypatch.setattr(startup_utils.sys, "executable", str(exe_path))

    assert manager._get_launch_command() == (exe_path.resolve(), [])
