from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

from accessiweather.services.startup_utils import StartupManager


def _manager_for_platform(platform: str, tmp_path: Path) -> StartupManager:
    platform_detector = SimpleNamespace(
        get_platform_info=lambda: SimpleNamespace(
            platform=platform,
            app_directory=tmp_path / "AccessiWeather",
        )
    )
    return StartupManager(platform_detector=platform_detector)


def test_linux_desktop_entry_uses_current_source_launch_command(
    monkeypatch,
    tmp_path,
):
    manager = _manager_for_platform("linux", tmp_path)
    python_path = tmp_path / "Python With Spaces" / "python.exe"
    monkeypatch.setattr("accessiweather.services.startup_utils.sys.executable", str(python_path))

    desktop_entry = manager._build_desktop_entry()

    assert f'Exec="{python_path.resolve()}" -m accessiweather' in desktop_entry


def test_linux_startup_status_rejects_stale_exec_target(monkeypatch, tmp_path):
    manager = _manager_for_platform("linux", tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (Path("/opt/current/python"), ["-m", "accessiweather"]),
    )
    desktop_path = manager._get_linux_desktop_entry_path()
    desktop_path.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                'Exec="/opt/old/python" -m accessiweather',
            ]
        ),
        encoding="utf-8",
    )

    assert manager._is_linux_startup_enabled() is False


def test_macos_launch_agent_uses_current_source_launch_command(
    monkeypatch,
    tmp_path,
):
    manager = _manager_for_platform("macos", tmp_path)
    python_path = tmp_path / "Python With Spaces" / "python.exe"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("accessiweather.services.startup_utils.sys.executable", str(python_path))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0),
    )

    assert manager._enable_macos_startup() is True

    with manager._get_macos_plist_path().open("rb") as plist_file:
        payload = plistlib.load(plist_file)
    assert payload["ProgramArguments"] == [str(python_path.resolve()), "-m", "accessiweather"]


def test_macos_startup_status_rejects_stale_program_arguments(monkeypatch, tmp_path):
    manager = _manager_for_platform("macos", tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (Path("/opt/current/python"), ["-m", "accessiweather"]),
    )
    plist_path = manager._get_macos_plist_path()
    with plist_path.open("wb") as plist_file:
        plistlib.dump(
            {
                "Label": "net.orinks.accessiweather.startup",
                "ProgramArguments": ["/opt/old/python", "-m", "accessiweather"],
                "RunAtLoad": True,
            },
            plist_file,
        )

    assert manager._is_macos_startup_enabled() is False
