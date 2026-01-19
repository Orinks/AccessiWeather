#!/usr/bin/env python3
"""
AccessiWeather Build Script using installer_builder2.

This script replaces Briefcase with installer_builder2 for building
installable and updatable applications for Windows and macOS.

Usage:
    python installer/build.py                    # Build for current platform
    python installer/build.py --platform windows # Build for Windows
    python installer/build.py --platform macos   # Build for macOS
    python installer/build.py --clean            # Clean build artifacts
    python installer/build.py --version 1.0.0    # Override version

Requirements:
    - installer_builder2: pip install git+https://github.com/accessibleapps/installer_builder2.git
    - Nuitka: pip install nuitka
    - Windows: Inno Setup installed (https://jrsoftware.org/isinfo.php)
    - macOS: create-dmg (brew install create-dmg)
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path

# Project root directory
ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"

# Application metadata
APP_NAME = "AccessiWeather"
APP_AUTHOR = "Orinks"
APP_DESCRIPTION = "An accessible weather application with NOAA and Open-Meteo support"
APP_URL = "https://github.com/Orinks/AccessiWeather"
MAIN_MODULE = "accessiweather.main"


def read_version() -> str:
    """Read version from pyproject.toml."""
    pyproject = ROOT / "pyproject.toml"
    try:
        import tomllib

        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        # Fallback to naive parsing
        text = pyproject.read_text(encoding="utf-8")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("version") and '"' in s:
                return s.split('"', 2)[1]
        return "0.0.0"


def detect_platform() -> str:
    """Detect the current platform."""
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def clean_build() -> None:
    """Clean build artifacts."""
    print("Cleaning build artifacts...")
    for path in [BUILD_DIR, DIST_DIR]:
        if path.exists():
            print(f"  Removing {path}")
            shutil.rmtree(path, ignore_errors=True)
    print("Clean complete.")


def get_data_directories() -> list[str]:
    """Get list of data directories to include in the build."""
    data_dirs = []

    # Include resources directory
    resources_dir = SRC_DIR / "accessiweather" / "resources"
    if resources_dir.exists():
        data_dirs.append(str(resources_dir))

    # Include soundpacks (only default)
    soundpacks_dir = SRC_DIR / "accessiweather" / "soundpacks" / "default"
    if soundpacks_dir.exists():
        data_dirs.append(str(soundpacks_dir))

    return data_dirs


def get_hidden_imports() -> list[str]:
    """Get list of hidden imports that Nuitka might miss."""
    return [
        "wx",
        "wx.adv",
        "wx.html",
        "wx.lib.agw",
        "httpx",
        "httpx._transports",
        "httpx._transports.default",
        "h11",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "sniffio",
        "certifi",
        "idna",
        "charset_normalizer",
        "dateutil",
        "dateutil.parser",
        "dateutil.tz",
        "bs4",
        "soupsieve",
        "attrs",
        "psutil",
        "keyring",
        "keyring.backends",
        "openai",
        "playsound3",
        "desktop_notifier",
    ]


def build_windows(version: str, console: bool = False) -> int:
    """Build Windows installer using installer_builder2."""
    try:
        from installer_builder2 import InstallerBuilder
    except ImportError:
        print("Error: installer_builder2 not installed.")
        print(
            "Install with: pip install git+https://github.com/accessibleapps/installer_builder2.git"
        )
        return 1

    print(f"Building {APP_NAME} v{version} for Windows...")

    # Prepare build configuration
    builder = InstallerBuilder(
        app_name=APP_NAME,
        dist_path=str(DIST_DIR),
        main_module=MAIN_MODULE,
        version=version,
        author=APP_AUTHOR,
        description=APP_DESCRIPTION,
        url=APP_URL,
        console=console,
        run_at_startup=False,
        include_modules=get_hidden_imports(),
        data_directories=get_data_directories(),
    )

    try:
        builder.build()
        print(f"Build complete! Installer is in {DIST_DIR}")
        return 0
    except Exception as e:
        print(f"Build failed: {e}")
        return 1


def build_macos(version: str, console: bool = False) -> int:
    """Build macOS DMG using installer_builder2."""
    try:
        from installer_builder2 import InstallerBuilder
    except ImportError:
        print("Error: installer_builder2 not installed.")
        print(
            "Install with: pip install git+https://github.com/accessibleapps/installer_builder2.git"
        )
        return 1

    print(f"Building {APP_NAME} v{version} for macOS...")

    builder = InstallerBuilder(
        app_name=APP_NAME,
        dist_path=str(DIST_DIR),
        main_module=MAIN_MODULE,
        version=version,
        author=APP_AUTHOR,
        description=APP_DESCRIPTION,
        url=APP_URL,
        console=console,
        include_modules=get_hidden_imports(),
        data_directories=get_data_directories(),
    )

    try:
        builder.build()
        print(f"Build complete! DMG is in {DIST_DIR}")
        return 0
    except Exception as e:
        print(f"Build failed: {e}")
        return 1


def main() -> int:
    """Run the build process."""
    parser = argparse.ArgumentParser(description="Build AccessiWeather using installer_builder2")
    parser.add_argument(
        "--platform",
        choices=["windows", "macos", "auto"],
        default="auto",
        help="Target platform (default: auto-detect)",
    )
    parser.add_argument(
        "--version",
        help="Override version (default: read from pyproject.toml)",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Build as console application (show terminal window)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts and exit",
    )

    args = parser.parse_args()

    if args.clean:
        clean_build()
        return 0

    # Determine version
    version = args.version or read_version()
    print(f"Version: {version}")

    # Determine platform
    target_platform = args.platform
    if target_platform == "auto":
        target_platform = detect_platform()

    print(f"Target platform: {target_platform}")

    # Ensure output directories exist
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # Build for target platform
    if target_platform == "windows":
        return build_windows(version, args.console)
    if target_platform == "macos":
        return build_macos(version, args.console)

    print(f"Error: Unsupported platform: {target_platform}")
    print("installer_builder2 only supports Windows and macOS.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
