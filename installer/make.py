#!/usr/bin/env python3
"""A simple make-like utility for AccessiWeather using BeeWare Briefcase.

This replaces the legacy PyInstaller/Inno Setup scripts.

Usage examples:
  python installer/make.py create          # First-time platform scaffold
  python installer/make.py build           # Build app bundle
  python installer/make.py package         # Create installer (e.g., MSI on Windows)
  python installer/make.py dev             # Run app in development mode
  python installer/make.py test            # Run test suite in a Briefcase dev app
  python installer/make.py zip             # Create a temporary portable ZIP from the build
  python installer/make.py status          # Show detected settings and versions
  python installer/make.py clean           # Clean Briefcase build artifacts (best-effort)

Options:
  --platform windows|macOS|linux (default: windows)
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

TRY_BREF_CLEAN = True  # call `briefcase clean` if available
ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"$ {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
        return res.returncode
    except FileNotFoundError:
        print(f"Error: command not found: {cmd[0]}")
        return 127


def _briefcase_exists() -> bool:
    # Use version check; some CLIs return non-zero for --help
    code = _run([sys.executable, "-m", "briefcase", "-V"], cwd=ROOT)
    return code == 0


def _briefcase(*args: str) -> int:
    return _run([sys.executable, "-m", "briefcase", *args], cwd=ROOT)


def _read_version() -> str:
    """Read version from pyproject.toml (project.version)."""
    pyproject = ROOT / "pyproject.toml"
    try:
        # Prefer tomllib on Python 3.11+; fall back to naive parsing without external deps
        try:
            import tomllib  # Python 3.11+

            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("version", "0.0.0")
        except Exception:
            text = pyproject.read_text(encoding="utf-8")
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("version") and '"' in s:
                    return s.split('"', 2)[1]
            return "0.0.0"
    except Exception:
        return "0.0.0"


def _detect_default_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macOS"
    return "linux"


def cmd_status(args: argparse.Namespace) -> int:
    print("AccessiWeather make-like utility (Briefcase)")
    print(f"Root: {ROOT}")
    print(f"Platform: {args.platform}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Briefcase available: {'yes' if _briefcase_exists() else 'no'}")
    print(f"Version: {_read_version()}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    return _briefcase("create", args.platform)


def cmd_build(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    # Update+build tends to be more robust during dev
    return _briefcase("build", args.platform)


def cmd_package(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    return _briefcase("package", args.platform)


def cmd_dev(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    return _briefcase("dev")


def cmd_test(args: argparse.Namespace) -> int:
    if not _briefcase_exists():
        print("Error: Briefcase is not installed. Install with: pip install briefcase")
        return 1
    # Prefer Briefcase to run tests in the app context; fallback to pytest
    code = _briefcase("dev", "--test")
    if code != 0:
        print("briefcase dev --test failed; falling back to pytest")
        code = _run([sys.executable, "-m", "pytest"], cwd=ROOT)
    return code


def cmd_zip(args: argparse.Namespace) -> int:
    """Create a portable ZIP from the Briefcase build output (temporary)."""
    version = _read_version()
    if args.platform != "windows":
        print("Note: ZIP recipe is primarily intended for Windows.")
    app_build_dir = ROOT / args.platform / "AccessiWeather" / "build" / "AccessiWeather"
    if not app_build_dir.exists():
        print(
            f"Error: build output not found at {app_build_dir}. Run: briefcase build {args.platform}"
        )
        return 1
    dist_dir = ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / f"AccessiWeather_Portable_v{version}.zip"
    # Create zip
    print(f"Creating ZIP: {zip_path}")
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(zip_path.with_suffix(""), "zip", app_build_dir)
    print("ZIP created.")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Clean Briefcase artifacts (best-effort)."""
    # Try Briefcase clean first if available
    if TRY_BREF_CLEAN and _briefcase_exists():
        code = _briefcase("clean", args.platform)
        if code == 0:
            return 0
    # Fallback: remove known build trees (non-destructive to sources)
    patterns = [
        ROOT / args.platform / "AccessiWeather" / "build",
        ROOT / args.platform / "AccessiWeather" / "support",
        ROOT / "dist",
    ]
    for p in patterns:
        if p.exists():
            print(f"Removing {p}")
            shutil.rmtree(p, ignore_errors=True)
    print("Clean complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AccessiWeather Briefcase make-like tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument(
            "--platform",
            default=_detect_default_platform(),
            choices=["windows", "macOS", "linux"],
            help="Target platform (default: auto-detected)",
        )

    p_status = sub.add_parser("status", help="Show environment and settings")
    add_common(p_status)
    p_status.set_defaults(func=cmd_status)

    p_create = sub.add_parser("create", help="Create platform scaffold")
    add_common(p_create)
    p_create.set_defaults(func=cmd_create)

    p_build = sub.add_parser("build", help="Build app bundle")
    add_common(p_build)
    p_build.set_defaults(func=cmd_build)

    p_package = sub.add_parser("package", help="Create installer (MSI on Windows)")
    add_common(p_package)
    p_package.set_defaults(func=cmd_package)

    p_dev = sub.add_parser("dev", help="Run app in dev mode")
    p_dev.set_defaults(func=cmd_dev)

    p_test = sub.add_parser("test", help="Run tests via Briefcase (fallback to pytest)")
    p_test.set_defaults(func=cmd_test)

    p_zip = sub.add_parser("zip", help="Create a portable ZIP from build output")
    add_common(p_zip)
    p_zip.set_defaults(func=cmd_zip)

    p_clean = sub.add_parser("clean", help="Clean Briefcase artifacts")
    add_common(p_clean)
    p_clean.set_defaults(func=cmd_clean)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
