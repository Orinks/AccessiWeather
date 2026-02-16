#!/usr/bin/env python3
"""
Build script for AccessiWeather using PyInstaller.

This script handles the complete build process:
- Generates app icons if needed
- Builds the application with PyInstaller
- Creates installers (Inno Setup on Windows, DMG on macOS)
- Creates portable ZIP archives

Usage:
    python installer/build.py                    # Full build for current platform
    python installer/build.py --icons-only       # Generate icons only
    python installer/build.py --skip-installer   # Build but skip installer creation
    python installer/build.py --clean            # Clean build artifacts
    python installer/build.py --dev              # Run app in development mode
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
INSTALLER_DIR = ROOT / "installer"
SRC_DIR = ROOT / "src"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
RESOURCES_DIR = SRC_DIR / "accessiweather" / "resources"

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command and handle errors."""
    print(f"$ {' '.join(cmd)}")
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=check,
            capture_output=capture,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        raise
    except FileNotFoundError:
        print(f"Command not found: {cmd[0]}")
        raise


def get_version() -> str:
    """Read version from pyproject.toml."""
    pyproject = ROOT / "pyproject.toml"
    try:
        import tomllib

        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.0.0")
    except Exception:
        # Fallback: parse manually
        text = pyproject.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip().startswith("version") and '"' in line:
                return line.split('"')[1]
        return "0.0.0"


def check_icons() -> bool:
    """Check that app icons exist (they should be committed to the repo)."""
    ico_path = RESOURCES_DIR / "app.ico"
    icns_path = RESOURCES_DIR / "app.icns"
    png_path = RESOURCES_DIR / "app.png"  # Fallback for non-macOS

    if IS_WINDOWS:
        if ico_path.exists():
            print("✓ Windows icon found")
            return True
        print("✗ Windows icon not found at:", ico_path)
        print("  Run 'python installer/create_icons.py' to generate icons")
        return False

    if IS_MACOS:
        if icns_path.exists():
            print("✓ macOS icon found")
            return True
        if png_path.exists():
            print("✓ macOS icon (PNG fallback) found")
            return True
        print("✗ macOS icon not found at:", icns_path)
        print("  Run 'python installer/create_icons.py' on macOS to generate icons")
        return False

    # Linux or other
    if png_path.exists() or ico_path.exists():
        print("✓ Icon found")
        return True
    print("✗ No icon found")
    return False


def install_dependencies() -> None:
    """Ensure build dependencies are installed."""
    print("Checking build dependencies...")

    # Check for PyInstaller
    try:
        import PyInstaller

        print(f"✓ PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("Installing PyInstaller...")
        run_command([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Check for Pillow (for icon generation)
    try:
        import importlib.util

        if importlib.util.find_spec("PIL"):
            print("✓ Pillow found")
        else:
            raise ImportError
    except ImportError:
        print("Installing Pillow for icon generation...")
        run_command([sys.executable, "-m", "pip", "install", "Pillow"])


def build_pyinstaller() -> bool:
    """Build the application with PyInstaller."""
    print("\n" + "=" * 60)
    print("Building with PyInstaller...")
    print("=" * 60 + "\n")

    spec_file = INSTALLER_DIR / "accessiweather.spec"

    if not spec_file.exists():
        print(f"Error: Spec file not found: {spec_file}")
        return False

    # Clean previous build
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if dir_path.exists():
            print(f"Cleaning {dir_path}...")
            shutil.rmtree(dir_path, ignore_errors=True)

    # Run PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]

    try:
        run_command(cmd, cwd=ROOT)
        print("\n✓ PyInstaller build completed")
        return True
    except Exception as e:
        print(f"\n✗ PyInstaller build failed: {e}")
        return False


def create_windows_installer() -> bool:
    """Create Windows installer using Inno Setup."""
    print("\n" + "=" * 60)
    print("Creating Windows Installer (Inno Setup)...")
    print("=" * 60 + "\n")

    iss_file = INSTALLER_DIR / "accessiweather.iss"

    if not iss_file.exists():
        print(f"Error: Inno Setup script not found: {iss_file}")
        return False

    # Check if Inno Setup is available
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        "iscc",  # If in PATH
    ]

    iscc_exe = None
    for path in iscc_paths:
        if Path(path).exists() or shutil.which(path):
            iscc_exe = path
            break

    if not iscc_exe:
        print("Warning: Inno Setup not found. Skipping installer creation.")
        print("Install Inno Setup from: https://jrsoftware.org/isinfo.php")
        return False

    # Write version file for Inno Setup
    version = get_version()
    version_file = DIST_DIR / "version.txt"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    version_file.write_text(f"[version]\nvalue={version}\n")

    # Run Inno Setup compiler
    try:
        run_command([iscc_exe, str(iss_file)], cwd=INSTALLER_DIR)
        print(f"\n✓ Windows installer created: dist/AccessiWeather_Setup_v{version}.exe")
        return True
    except Exception as e:
        print(f"\n✗ Inno Setup failed: {e}")
        return False


def create_macos_dmg() -> bool:
    """Create macOS DMG installer."""
    print("\n" + "=" * 60)
    print("Creating macOS DMG...")
    print("=" * 60 + "\n")

    app_path = DIST_DIR / "AccessiWeather.app"
    if not app_path.exists():
        print(f"Error: App bundle not found: {app_path}")
        return False

    version = get_version()
    dmg_name = f"AccessiWeather_v{version}.dmg"
    dmg_path = DIST_DIR / dmg_name

    # Remove existing DMG
    if dmg_path.exists():
        dmg_path.unlink()

    # Try create-dmg first (better looking DMGs)
    if shutil.which("create-dmg"):
        try:
            icon_path = RESOURCES_DIR / "app.icns"
            cmd = [
                "create-dmg",
                "--volname",
                "AccessiWeather",
                "--window-pos",
                "200",
                "120",
                "--window-size",
                "600",
                "400",
                "--icon-size",
                "100",
                "--icon",
                "AccessiWeather.app",
                "175",
                "190",
                "--hide-extension",
                "AccessiWeather.app",
                "--app-drop-link",
                "425",
                "190",
            ]
            if icon_path.exists():
                cmd.extend(["--volicon", str(icon_path)])
            cmd.extend([str(dmg_path), str(DIST_DIR)])

            run_command(cmd, cwd=ROOT)
            print(f"\n✓ DMG created: {dmg_path}")
            return True
        except Exception as e:
            print(f"create-dmg failed: {e}, falling back to hdiutil")

    # Fallback to hdiutil
    try:
        # Create a temporary directory for the DMG contents
        dmg_temp = DIST_DIR / "dmg_temp"
        if dmg_temp.exists():
            shutil.rmtree(dmg_temp)
        dmg_temp.mkdir()

        # Copy app to temp directory
        shutil.copytree(app_path, dmg_temp / "AccessiWeather.app")

        # Create Applications symlink
        (dmg_temp / "Applications").symlink_to("/Applications")

        # Create DMG with hdiutil
        run_command(
            [
                "hdiutil",
                "create",
                "-volname",
                "AccessiWeather",
                "-srcfolder",
                str(dmg_temp),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_path),
            ]
        )

        # Cleanup
        shutil.rmtree(dmg_temp)

        print(f"\n✓ DMG created: {dmg_path}")
        return True
    except Exception as e:
        print(f"\n✗ DMG creation failed: {e}")
        return False


def create_portable_zip() -> bool:
    """Create a portable ZIP archive."""
    print("\n" + "=" * 60)
    print("Creating portable ZIP...")
    print("=" * 60 + "\n")

    version = get_version()

    if IS_WINDOWS:
        # Look for directory distribution first, then single exe
        source_dir = DIST_DIR / "AccessiWeather_dir"
        if not source_dir.exists():
            # Single exe - create a directory for it
            exe_path = DIST_DIR / "AccessiWeather.exe"
            if exe_path.exists():
                source_dir = DIST_DIR / "AccessiWeather_portable"
                source_dir.mkdir(exist_ok=True)
                shutil.copy2(exe_path, source_dir / "AccessiWeather.exe")
            else:
                print("Error: No build output found")
                return False

        zip_name = f"AccessiWeather_Portable_v{version}"
    elif IS_MACOS:
        source_dir = DIST_DIR / "AccessiWeather.app"
        if not source_dir.exists():
            print("Error: App bundle not found")
            return False
        zip_name = f"AccessiWeather_macOS_v{version}"
    else:
        source_dir = DIST_DIR / "AccessiWeather"
        if not source_dir.exists():
            print("Error: Build output not found")
            return False
        zip_name = f"AccessiWeather_Linux_v{version}"

    zip_path = DIST_DIR / zip_name

    # Remove existing zip
    if Path(f"{zip_path}.zip").exists():
        Path(f"{zip_path}.zip").unlink()

    # Create zip
    shutil.make_archive(str(zip_path), "zip", source_dir.parent, source_dir.name)

    print(f"\n✓ Portable ZIP created: {zip_path}.zip")
    return True


def clean_build() -> None:
    """Clean all build artifacts."""
    print("Cleaning build artifacts...")

    dirs_to_clean = [BUILD_DIR, DIST_DIR]
    for dir_path in dirs_to_clean:
        if dir_path.exists():
            print(f"  Removing {dir_path}")
            shutil.rmtree(dir_path, ignore_errors=True)

    # Clean PyInstaller cache
    pycache_dirs = list(ROOT.rglob("__pycache__"))
    for pycache in pycache_dirs:
        if "site-packages" not in str(pycache):
            shutil.rmtree(pycache, ignore_errors=True)

    # Clean .pyc files
    for pyc in ROOT.rglob("*.pyc"):
        if "site-packages" not in str(pyc):
            pyc.unlink(missing_ok=True)

    print("✓ Clean complete")


def run_dev() -> int:
    """Run the application in development mode."""
    print("Running in development mode...")
    return run_command(
        [sys.executable, "-m", "accessiweather"],
        cwd=ROOT,
        check=False,
    ).returncode


def generate_build_metadata(args: argparse.Namespace) -> None:
    """Generate version and build info files (mirrors CI steps)."""
    print("\n" + "=" * 60)
    print("Generating build metadata...")
    print("=" * 60 + "\n")

    # Generate unified build metadata (_build_meta.py with version + BUILD_TAG)
    build_meta_script = ROOT / "scripts" / "generate_build_meta.py"
    if build_meta_script.exists():
        tag = args.tag
        if not tag and args.nightly:
            from datetime import datetime, timezone

            tag = f"nightly-{datetime.now(timezone.utc).strftime('%Y%m%d')}"

        cmd = [sys.executable, str(build_meta_script)]
        if tag:
            cmd.append(tag)

        run_command(cmd, cwd=ROOT)
    else:
        # Fall back to legacy separate scripts
        print(f"Warning: {build_meta_script} not found, trying legacy scripts")
        version_script = ROOT / "scripts" / "generate_version.py"
        if version_script.exists():
            run_command([sys.executable, str(version_script)], cwd=ROOT)

        build_info_script = ROOT / "scripts" / "generate_build_info.py"
        if build_info_script.exists():
            tag = args.tag
            if not tag and args.nightly:
                from datetime import datetime, timezone

                tag = f"nightly-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            cmd = [sys.executable, str(build_info_script)]
            if tag:
                cmd.append(tag)
            run_command(cmd, cwd=ROOT)


def main() -> int:
    """Run the build process."""
    parser = argparse.ArgumentParser(
        description="Build AccessiWeather application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--icons-only",
        action="store_true",
        help="Generate icons only, don't build",
    )
    parser.add_argument(
        "--skip-installer",
        action="store_true",
        help="Skip installer creation (Inno Setup/DMG)",
    )
    parser.add_argument(
        "--skip-icons",
        action="store_true",
        help="Skip icon generation",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Skip portable ZIP creation",
    )
    parser.add_argument(
        "--nightly",
        action="store_true",
        help="Build as nightly (generates nightly-YYYYMMDD build tag)",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Custom build tag (e.g. nightly-20260208). Overrides --nightly.",
    )

    args = parser.parse_args()

    # Print banner
    print("\n" + "=" * 60)
    print("AccessiWeather Build Script")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Version: {get_version()}")
    print("=" * 60 + "\n")

    # Handle special commands
    if args.clean:
        clean_build()
        return 0

    if args.dev:
        return run_dev()

    # Install dependencies
    install_dependencies()

    # Check icons exist (they should be committed to repo)
    if args.icons_only:
        print("To generate icons, run: python installer/create_icons.py")
        return 0

    if not args.skip_icons:
        check_icons()

    # Generate version and build info (same as CI)
    generate_build_metadata(args)

    # Build with PyInstaller
    if not build_pyinstaller():
        return 1

    # Create installer
    if not args.skip_installer:
        if IS_WINDOWS:
            create_windows_installer()
        elif IS_MACOS:
            create_macos_dmg()

    # Create portable ZIP
    if not args.no_zip:
        create_portable_zip()

    # Print summary
    print("\n" + "=" * 60)
    print("Build Summary")
    print("=" * 60)

    if DIST_DIR.exists():
        print("\nCreated files:")
        for f in sorted(DIST_DIR.iterdir()):
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  {f.name} ({size_mb:.1f} MB)")

    print("\n✓ Build complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
