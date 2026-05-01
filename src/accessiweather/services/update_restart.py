"""Restart planning and script builders for app updates."""

from __future__ import annotations

import os
import platform
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RestartPlan:
    kind: str
    command: list[str]
    script_path: Path | None = None


def build_macos_update_script(
    update_path: Path,
    app_path: Path,
) -> str:
    """Build a shell script to apply a macOS update."""
    app_dir = app_path.parent
    return textwrap.dedent(
        f"""
        #!/bin/bash
        sleep 2
        if [[ "{update_path}" == *.zip ]]; then
            unzip -o "{update_path}" -d "{app_dir}"
        elif [[ "{update_path}" == *.dmg ]]; then
            hdiutil attach "{update_path}" -nobrowse -quiet
            cp -R /Volumes/*/*.app "{app_dir}/"
            hdiutil detach /Volumes/* -quiet
        fi
        open "{app_path}" --args --updated
        rm -f "$0" "{update_path}"
        """
    ).strip()


def build_portable_update_script(
    zip_path: Path,
    target_dir: Path,
    exe_path: Path,
) -> str:
    """Build a Windows batch script to replace a portable install."""
    return textwrap.dedent(
        f"""
        @echo off
        set "PID={os.getpid()}"
        set "ZIP_PATH={zip_path}"
        set "TARGET_DIR={target_dir}"
        set "EXE_PATH={exe_path}"
        set "EXTRACT_DIR={target_dir / "update_tmp"}"

        :WAIT_LOOP
        tasklist /FI "PID eq %PID%" 2>NUL | find /I /N "%PID%" >NUL
        if "%ERRORLEVEL%"=="0" (
            timeout /t 1 /nobreak >NUL
            goto WAIT_LOOP
        )

        if exist "%EXTRACT_DIR%" rd /s /q "%EXTRACT_DIR%"
        powershell -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%EXTRACT_DIR%' -Force"

        REM Find actual content dir (zip may have a subfolder)
        set "COPY_SRC=%EXTRACT_DIR%"
        if not exist "%EXTRACT_DIR%\\AccessiWeather.exe" (
            for /d %%D in ("%EXTRACT_DIR%\\*") do (
                if exist "%%D\\AccessiWeather.exe" set "COPY_SRC=%%D"
            )
        )

        xcopy "%COPY_SRC%\\*" "%TARGET_DIR%\\" /E /H /Y /Q
        rd /s /q "%EXTRACT_DIR%"
        del "%ZIP_PATH%"
        timeout /t 2 /nobreak >NUL
        start "" "%EXE_PATH%" --updated
        (goto) 2>nul & del "%~f0"
        """
    ).strip()


def plan_restart(
    update_path: Path,
    *,
    portable: bool,
    platform_system: str | None = None,
) -> RestartPlan:
    """Plan how to apply an update and restart."""
    system = (platform_system or platform.system()).lower()
    if "windows" in system and portable:
        exe_path = Path(sys.executable).resolve()
        script_path = exe_path.parent / "accessiweather_portable_update.bat"
        return RestartPlan("portable", [str(script_path)], script_path=script_path)
    if "windows" in system:
        return RestartPlan("windows_installer", [str(update_path)])
    if "darwin" in system or "mac" in system:
        secure_dir = Path(tempfile.mkdtemp(prefix="accessiweather_update_"))
        script_path = secure_dir / "accessiweather_update.sh"
        return RestartPlan("macos_script", ["bash", str(script_path)], script_path=script_path)
    return RestartPlan("unsupported", [str(update_path)])
