"""
Windows toast notification identity management for AccessiWeather.

Handles AppUserModelID registration, Start Menu shortcut creation/repair,
and identity stamp caching so Windows toast notifications — including
Action Center clicks — work reliably across source, portable, and
installer builds.

Uses pure Python ctypes COM calls (no PowerShell subprocess) to avoid
visible terminal popups.
"""

from __future__ import annotations

import ctypes
import importlib.util
import json
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from .constants import WINDOWS_APP_USER_MODEL_ID
from .runtime_env import is_compiled_runtime
from .windows_toast_identity_powershell import run_powershell_identity_fallback
from .windows_toast_identity_shortcuts import (
    _create_shortcut,
    _read_shortcut_app_id,
    _read_shortcut_target_wscript,
    _read_shortcut_toast_activator_clsid,
    _resolve_start_menu_shortcut_path,
    _set_shortcut_app_id,
    _set_shortcut_toast_activator_clsid,
)

logger = logging.getLogger(__name__)

_ole32 = None
_shell32 = None

WINDOWS_TOAST_PROTOCOL_SCHEME = "accessiweather-toast"
WINDOWS_TOAST_ACTIVATOR_CLSID = "{0D3C3F8E-7303-4C9B-81C7-FF8D8C1AFC07}"
_TOAST_IDENTITY_SCHEMA_VERSION = 2


# Minimal Windows COM availability flags used by the main orchestration path.
if sys.platform == "win32":
    try:
        _ole32 = ctypes.windll.ole32
        _shell32 = ctypes.windll.shell32
    except Exception:
        _ole32 = None
        _shell32 = None


def _normalize_clsid(clsid: str | None) -> str | None:
    """Normalize a CLSID string to uppercase-braced form."""
    if not clsid:
        return None
    try:
        return "{" + str(uuid.UUID(clsid)).upper() + "}"
    except (AttributeError, ValueError):
        return None


def _is_unc_path(path: str) -> bool:
    """Return True when *path* points to a UNC/network location."""
    normalized = path.replace("/", "\\")
    return normalized.startswith("\\\\")


def _needs_shortcut_repair(
    *, expected_target: str, current_target: str | None, current_app_id: str | None, app_id: str
) -> bool:
    """Determine whether Start Menu shortcut should be recreated/repaired."""
    if not current_target:
        return True
    if Path(current_target).resolve() != Path(expected_target).resolve():
        return True
    return (current_app_id or "") != app_id


def _run_powershell_json(script: str, **args: str) -> dict[str, str | bool | None]:
    """Run a small PowerShell script and parse JSON output."""
    if sys.platform != "win32":
        return {}

    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    for key, value in args.items():
        cmd.extend([f"-{key}", value])

    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"powershell exit {result.returncode}")

    payload = (result.stdout or "").strip()
    if not payload:
        return {}
    return json.loads(payload)


def set_windows_app_user_model_id(app_id: str = WINDOWS_APP_USER_MODEL_ID) -> None:
    """
    Register a Windows AppUserModelID for every Windows run.

    Setting the AppUserModelID explicitly ensures source, portable, and
    installer builds share the same identity (the shortcut uses this value),
    so toast notifications work consistently without conflicting with the
    registered shortcut AppID.
    """
    if sys.platform != "win32":
        return

    try:
        ctypes_module = sys.modules.get("ctypes", ctypes)
        ctypes_module.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        logger.debug("App User Model ID set: %s", app_id)
    except Exception as exc:
        logger.debug("Failed to set App User Model ID: %s", exc)


def _resolve_notification_launch_command() -> list[str]:
    """Return the command used to relaunch the current app for protocol activation."""
    if is_compiled_runtime():
        return [str(Path(sys.executable).resolve())]

    executable = (
        Path(sys.executable).resolve()
        if sys.executable
        else Path(sys.argv[0]).resolve()
        if sys.argv and sys.argv[0]
        else Path.cwd()
    )

    if importlib.util.find_spec("accessiweather") is not None:
        return [str(executable), "-m", "accessiweather"]
    if sys.argv and sys.argv[0]:
        return [str(executable), str(Path(sys.argv[0]).resolve())]
    return [str(executable)]


def _build_protocol_handler_command(protocol_argument: str = "%1") -> str:
    """Build the Windows command-line used for protocol activation relaunches."""
    return subprocess.list2cmdline([*_resolve_notification_launch_command(), protocol_argument])


def _register_protocol_activation_handler() -> bool:
    """
    Register the per-user protocol handler used by stub-CLSID toast activation.

    Microsoft documents the stub-CLSID fallback for unpackaged apps as requiring
    protocol activation to relaunch the app when a toast is clicked while the
    process is not running.
    """
    if sys.platform != "win32":
        return False

    try:
        import winreg
    except ImportError:
        logger.warning("[notify-init] winreg unavailable; protocol activation not registered")
        return False

    scheme = WINDOWS_TOAST_PROTOCOL_SCHEME
    command = _build_protocol_handler_command()
    launch_command = _resolve_notification_launch_command()
    icon_path = launch_command[0] if launch_command else ""
    base_key = rf"Software\Classes\{scheme}"

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base_key) as root_key:
            winreg.SetValueEx(root_key, None, 0, winreg.REG_SZ, "URL:AccessiWeather Toast")
            winreg.SetValueEx(root_key, "URL Protocol", 0, winreg.REG_SZ, "")

        if icon_path:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{base_key}\DefaultIcon") as icon_key:
                winreg.SetValueEx(icon_key, None, 0, winreg.REG_SZ, icon_path)

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, rf"{base_key}\shell\open\command"
        ) as command_key:
            winreg.SetValueEx(command_key, None, 0, winreg.REG_SZ, command)

        logger.debug("[notify-init] Registered protocol handler %s => %s", scheme, command)
        return True
    except OSError as exc:
        logger.warning("[notify-init] Failed to register protocol handler %s: %s", scheme, exc)
        return False


# ---------------------------------------------------------------------------
# Identity stamp caching (unchanged from before)
# ---------------------------------------------------------------------------


def _toast_identity_stamp_path(appdata: Path, display_name: str) -> Path:
    return appdata / display_name / "toast_identity_stamp.json"


def _load_toast_identity_stamp(stamp_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(stamp_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _should_repair_shortcut(
    *,
    stamp: dict[str, Any] | None,
    shortcut_path: Path,
    exe_path: str,
    app_version: str,
) -> bool:
    if not shortcut_path.exists():
        return True
    if not stamp:
        return True

    return not (
        bool(stamp.get("verified"))
        and stamp.get("exe_path") == exe_path
        and stamp.get("app_version") == app_version
        and stamp.get("shortcut_path") == str(shortcut_path)
        and stamp.get("schema_version") == _TOAST_IDENTITY_SCHEMA_VERSION
    )


def _write_toast_identity_stamp(
    *,
    stamp_path: Path,
    shortcut_path: Path,
    exe_path: str,
    app_version: str,
    verified: bool,
    readback_app_id: str | None,
    toast_activator_clsid: str | None = None,
    protocol_handler_registered: bool = False,
) -> None:
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(
        json.dumps(
            {
                "schema_version": _TOAST_IDENTITY_SCHEMA_VERSION,
                "verified": bool(verified),
                "exe_path": exe_path,
                "app_version": app_version,
                "shortcut_path": str(shortcut_path),
                "readback_app_id": readback_app_id,
                "toast_activator_clsid": _normalize_clsid(toast_activator_clsid),
                "protocol_handler_registered": bool(protocol_handler_registered),
            }
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_TOAST_IDENTITY_ENSURED_THIS_STARTUP = False


def _ensure_windows_toast_identity_via_powershell(
    *,
    shortcut_path: Path,
    exe_path: str,
    app_id: str,
    display_name: str,
    stamp_path: Path,
    app_version: str,
    protocol_handler_registered: bool,
) -> None:
    """Legacy fallback used when ctypes COM access is unavailable."""
    run_powershell_identity_fallback(
        shortcut_path=shortcut_path,
        exe_path=exe_path,
        app_id=app_id,
        display_name=display_name,
        stamp_path=stamp_path,
        app_version=app_version,
        protocol_handler_registered=protocol_handler_registered,
        run_powershell_json=_run_powershell_json,
        write_toast_identity_stamp=_write_toast_identity_stamp,
        toast_activator_clsid=WINDOWS_TOAST_ACTIVATOR_CLSID,
    )


def ensure_windows_toast_identity(
    app_id: str = WINDOWS_APP_USER_MODEL_ID,
    display_name: str = "AccessiWeather",
) -> None:
    """
    Ensure registry + Start Menu shortcut identity for reliable Windows toasts.

    Uses pure Python ctypes COM calls — no PowerShell subprocess, no visible
    terminal window.
    """
    global _TOAST_IDENTITY_ENSURED_THIS_STARTUP

    if sys.platform != "win32":
        return

    if _TOAST_IDENTITY_ENSURED_THIS_STARTUP:
        logger.debug("[notify-init] Windows toast identity already ensured this startup; skipping")
        return

    from . import __version__

    exe_path = str(Path(sys.executable).resolve())
    appdata = Path.home() / "AppData" / "Roaming"
    shortcut_path = _resolve_start_menu_shortcut_path(display_name)
    stamp_path = _toast_identity_stamp_path(appdata, display_name)
    app_version = __version__

    logger.info(
        "[notify-init] Windows toast identity: exe_path=%s shortcut_path=%s",
        exe_path,
        shortcut_path,
    )

    # Always set the process-level AUMID
    set_windows_app_user_model_id(app_id=app_id)
    protocol_handler_registered = _register_protocol_activation_handler()

    # Check cached stamp to see if repair is needed
    stamp = _load_toast_identity_stamp(stamp_path)
    if not _should_repair_shortcut(
        stamp=stamp,
        shortcut_path=shortcut_path,
        exe_path=exe_path,
        app_version=app_version,
    ):
        _TOAST_IDENTITY_ENSURED_THIS_STARTUP = True
        logger.info(
            "[notify-init] Windows toast identity: verified stamp valid, skipping shortcut repair"
        )
        return

    # Don't run repair more than once per startup
    _TOAST_IDENTITY_ENSURED_THIS_STARTUP = True

    try:
        if _ole32 is None or _shell32 is None:
            _ensure_windows_toast_identity_via_powershell(
                shortcut_path=shortcut_path,
                exe_path=exe_path,
                app_id=app_id,
                display_name=display_name,
                stamp_path=stamp_path,
                app_version=app_version,
                protocol_handler_registered=protocol_handler_registered,
            )
            return

        # Initialize COM (idempotent — safe to call multiple times)
        _ole32.CoInitialize(None)

        # Step 1: Ensure shortcut exists
        if not shortcut_path.exists():
            logger.info(
                "[notify-init] Creating Start Menu shortcut: %s -> %s", shortcut_path, exe_path
            )
            if not _create_shortcut(shortcut_path, exe_path, display_name):
                logger.warning("[notify-init] Failed to create shortcut")
                return
        else:
            # Verify target matches current exe
            current_target = _read_shortcut_target_wscript(shortcut_path)
            if current_target and Path(current_target).resolve() != Path(exe_path).resolve():
                logger.info(
                    "[notify-init] Shortcut target mismatch: %s != %s — recreating",
                    current_target,
                    exe_path,
                )
                if not _create_shortcut(shortcut_path, exe_path, display_name):
                    logger.warning("[notify-init] Failed to recreate shortcut")

        # Step 2: Read current AUMID
        current_app_id = _read_shortcut_app_id(shortcut_path)
        logger.info(
            "[notify-init] Current shortcut AUMID: %r (expected: %r)", current_app_id, app_id
        )
        current_activator_clsid = _read_shortcut_toast_activator_clsid(shortcut_path)
        logger.info(
            "[notify-init] Current shortcut ToastActivatorCLSID: %r (expected: %r)",
            current_activator_clsid,
            WINDOWS_TOAST_ACTIVATOR_CLSID,
        )

        # Step 3: Set AUMID if missing or wrong
        if current_app_id != app_id:
            logger.info("[notify-init] Setting AUMID on shortcut: %s", app_id)
            if not _set_shortcut_app_id(shortcut_path, app_id):
                logger.warning("[notify-init] Failed to set AUMID on shortcut")
                _write_toast_identity_stamp(
                    stamp_path=stamp_path,
                    shortcut_path=shortcut_path,
                    exe_path=exe_path,
                    app_version=app_version,
                    verified=False,
                    readback_app_id=current_app_id,
                    toast_activator_clsid=current_activator_clsid,
                    protocol_handler_registered=protocol_handler_registered,
                )
                return
        if _normalize_clsid(current_activator_clsid) != _normalize_clsid(
            WINDOWS_TOAST_ACTIVATOR_CLSID
        ):
            logger.info(
                "[notify-init] Setting ToastActivatorCLSID on shortcut: %s",
                WINDOWS_TOAST_ACTIVATOR_CLSID,
            )
            if not _set_shortcut_toast_activator_clsid(
                shortcut_path, WINDOWS_TOAST_ACTIVATOR_CLSID
            ):
                logger.warning("[notify-init] Failed to set ToastActivatorCLSID on shortcut")
                _write_toast_identity_stamp(
                    stamp_path=stamp_path,
                    shortcut_path=shortcut_path,
                    exe_path=exe_path,
                    app_version=app_version,
                    verified=False,
                    readback_app_id=current_app_id,
                    toast_activator_clsid=current_activator_clsid,
                    protocol_handler_registered=protocol_handler_registered,
                )
                return

        # Step 4: Verify readback
        readback_app_id = _read_shortcut_app_id(shortcut_path)
        readback_activator_clsid = _read_shortcut_toast_activator_clsid(shortcut_path)
        verified = (
            readback_app_id == app_id
            and _normalize_clsid(readback_activator_clsid)
            == _normalize_clsid(WINDOWS_TOAST_ACTIVATOR_CLSID)
            and protocol_handler_registered
        )

        logger.info(
            "[notify-init] Windows toast identity result: shortcut=%s verified=%s "
            "readback_app_id=%r readback_clsid=%r protocol_registered=%s",
            shortcut_path,
            verified,
            readback_app_id,
            readback_activator_clsid,
            protocol_handler_registered,
        )

        _write_toast_identity_stamp(
            stamp_path=stamp_path,
            shortcut_path=shortcut_path,
            exe_path=exe_path,
            app_version=app_version,
            verified=verified,
            readback_app_id=readback_app_id,
            toast_activator_clsid=readback_activator_clsid,
            protocol_handler_registered=protocol_handler_registered,
        )

    except Exception as exc:
        logger.warning("[notify-init] Failed to ensure toast identity: %s", exc)
