"""
PyInstaller spec file for AccessiWeather.

This spec file configures PyInstaller to build AccessiWeather as a standalone
application for Windows and macOS.

Usage:
    pyinstaller installer/accessiweather.spec
"""

import platform
import sys
from pathlib import Path

# Ensure installer/ directory is on Python path so spec_utils can be imported
sys.path.insert(0, SPECPATH)
from spec_utils import filter_platform_binaries, filter_sound_lib_entries
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# Determine paths
SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
RESOURCES_DIR = SRC_DIR / "accessiweather" / "resources"
SOUNDPACKS_DIR = PROJECT_ROOT / "soundpacks"


def _safe_collect_submodules(package_name: str) -> list[str]:
    """Collect submodules when package is present in build environment."""
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


def _safe_collect_data_files(package_name: str) -> list[tuple[str, str]]:
    """Collect package data files when available."""
    try:
        return collect_data_files(package_name)
    except Exception:
        return []

# Platform-specific settings
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

# App metadata
APP_NAME = "AccessiWeather"
APP_VERSION = "0.5.0"
APP_BUNDLE_ID = "net.orinks.accessiweather"

# Read version from pyproject.toml if available
try:
    import tomllib
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        APP_VERSION = pyproject.get("project", {}).get("version", APP_VERSION)
except Exception:
    pass

# Determine icon path
if IS_WINDOWS:
    ICON_PATH = RESOURCES_DIR / "app.ico"
    if not ICON_PATH.exists():
        ICON_PATH = SPEC_DIR / "app.ico"
else:
    ICON_PATH = RESOURCES_DIR / "app.icns"

ICON_PATH = str(ICON_PATH) if ICON_PATH.exists() else None

# Data files to bundle
datas = [
    # Resources directory
    (str(RESOURCES_DIR), "accessiweather/resources"),
]

# Include backend package data used by notification and timezone logic
# (best-effort: no-op when dependency isn't installed in builder env)
datas += _safe_collect_data_files("desktop_notifier")
datas += _safe_collect_data_files("tzdata")

# Add soundpacks if they exist
if SOUNDPACKS_DIR.exists():
    # Only include default soundpack to reduce size
    default_soundpack = SOUNDPACKS_DIR / "default"
    if default_soundpack.exists():
        datas.append((str(default_soundpack), "soundpacks/default"))

# Hidden imports for wxPython and other dynamic imports
hiddenimports = [
    "wx",
    "wx.adv",
    "wx.html",
    "wx.lib.agw",
    "wx.lib.agw.aui",
    "wx.lib.mixins",
    "wx.lib.mixins.inspection",
    "gui_builder",
    "httpx",
    "httpx._transports",
    "httpx._transports.default",
    "h11",
    "h2",
    "hpack",
    "keyring",
    "keyring.backends",
    "keyring.backends.Windows",
    "keyring.backends.macOS",
    "keyring.backends.SecretService",
    "desktop_notifier",
    "playsound3",
    "sound_lib",
    "sound_lib.stream",
    "sound_lib.output",
    # sound_lib transitive deps (PyInstaller may not trace these automatically)
    "platform_utils",
    "platform_utils.paths",
    "libloader",
    "libloader.libloader",
    # toasted (WinRT toast notifications)
    "toasted",
    "toasted.toast",
    "toasted.elements",
    "toasted.common",
    "openai",
    "attrs",
    "dateutil",
    "dateutil.parser",
    "bs4",
    "beautifulsoup4",
    "psutil",
    # Generated build-time files (wrapped in try/except, so PyInstaller misses them)
    "accessiweather._version",
    "accessiweather._build_info",
    # Lazy-imported screen reader library
    "prism",
    "prismatoid",
]

# Desktop notifier backends and metadata are dynamically loaded.
hiddenimports += _safe_collect_submodules("desktop_notifier")
hiddenimports += _safe_collect_submodules("sound_lib")
hiddenimports += _safe_collect_submodules("platform_utils")
hiddenimports += _safe_collect_submodules("libloader")
hiddenimports += _safe_collect_submodules("playsound3")
hiddenimports += _safe_collect_submodules("toasted")
hiddenimports += _safe_collect_submodules("winsdk")
hiddenimports += _safe_collect_submodules("winrt")

# Platform-specific hidden imports
if IS_WINDOWS:
    hiddenimports.extend([
        "win32api",
        "win32con",
        "win32gui",
        "winsound",
    ])

# Excludes to reduce size
excludes = [
    "tkinter",
    "_tkinter",
    "tcl",
    "tk",
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "PIL.ImageTk",
    "test",
    "tests",
    "unittest",
    "pytest",
]

# Analysis
a = Analysis(
    [str(SRC_DIR / "accessiweather" / "__main__.py")],
    pathex=[str(SRC_DIR)],
    binaries=collect_dynamic_libs("prism"),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(SPEC_DIR / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# Remove unnecessary files from analysis
a.binaries = [b for b in a.binaries if not b[0].startswith("tcl")]
a.binaries = [b for b in a.binaries if not b[0].startswith("tk")]
a.binaries = [b for b in a.binaries if "_tkinter" not in b[0]]

# Remove cross-platform binary artifacts and limit sound_lib to platform-friendly bits
a.binaries = filter_platform_binaries(a.binaries, platform.system())
a.binaries = filter_sound_lib_entries(a.binaries, platform.system())
a.datas = filter_sound_lib_entries(a.datas, platform.system())

pyz = PYZ(a.pure)

if IS_MACOS:
    # macOS: Create .app bundle
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_PATH,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=APP_NAME,
    )

    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON_PATH,
        bundle_identifier=APP_BUNDLE_ID,
        version=APP_VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleVersion": APP_VERSION,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleIdentifier": APP_BUNDLE_ID,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "10.13.0",
        },
    )
else:
    # Windows/Linux: Create executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_PATH,
        version_file=None,
    )

    # Also create a directory-based distribution for Inno Setup
    coll = COLLECT(
        EXE(
            pyz,
            a.scripts,
            [],
            exclude_binaries=True,
            name=APP_NAME,
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=True,
            console=False,
            disable_windowed_traceback=False,
            argv_emulation=False,
            target_arch=None,
            codesign_identity=None,
            entitlements_file=None,
            icon=ICON_PATH,
        ),
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=f"{APP_NAME}_dir",
    )
