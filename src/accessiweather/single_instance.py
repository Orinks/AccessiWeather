"""Win32 mutex-backed single-instance support for AccessiWeather."""

from __future__ import annotations

import contextlib
import ctypes
import logging
import sys
from collections.abc import Callable

from .activation_ipc import ActivationIpcServer, send_activation_request
from .notification_activation import (
    NotificationActivationRequest,
    consume_activation_request_handoff,
    write_activation_request_handoff,
)
from .paths import RuntimeStoragePaths

logger = logging.getLogger(__name__)

SINGLE_INSTANCE_MUTEX_NAME = "Local\\AccessiWeather.SingleInstance"
ERROR_ALREADY_EXISTS = 183
SW_SHOWNORMAL = 1
SW_RESTORE = 9


def _configure_kernel32_signatures(kernel32) -> None:
    """
    Declare kernel32 signatures so 64-bit HANDLEs are not truncated.

    ctypes defaults a function's restype/argtypes to 32-bit ``c_int``. On
    64-bit Windows a HANDLE is pointer-width, so without these declarations the
    handle returned by CreateMutexW would be truncated before being passed back
    to CloseHandle. The suppression keeps the test fakes (plain methods, which
    reject attribute assignment) working unchanged.
    """
    with contextlib.suppress(Exception):
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


def _configure_user32_signatures(user32) -> None:
    """Declare user32 signatures so window handles are not truncated to int."""
    with contextlib.suppress(Exception):
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        user32.EnumWindows.restype = ctypes.c_bool
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        user32.ShowWindow.restype = ctypes.c_bool
        user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetForegroundWindow.restype = ctypes.c_bool
        user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]


class SingleInstanceManager:
    """Coordinates one running AccessiWeather instance per Windows session."""

    def __init__(
        self,
        app,
        mutex_name: str = SINGLE_INSTANCE_MUTEX_NAME,
        runtime_paths: RuntimeStoragePaths | None = None,
    ) -> None:
        """Initialize the manager with the app and optional mutex/runtime paths."""
        self.app = app
        self.mutex_name = mutex_name
        self.runtime_paths = runtime_paths or getattr(app, "runtime_paths", None)
        self._mutex_handle: int | None = None
        self._lock_acquired = False
        self._activation_ipc_server = ActivationIpcServer()

    def write_activation_handoff(self, request: NotificationActivationRequest) -> bool:
        """Write a notification activation request for the primary instance."""
        runtime_paths = self.runtime_paths or getattr(self.app, "runtime_paths", None)
        if runtime_paths is None:
            return False
        return write_activation_request_handoff(runtime_paths, request)

    def consume_activation_handoff(self) -> NotificationActivationRequest | None:
        """Read and remove any pending notification activation request."""
        runtime_paths = self.runtime_paths or getattr(self.app, "runtime_paths", None)
        if runtime_paths is None:
            return None
        return consume_activation_request_handoff(runtime_paths)

    def try_acquire_lock(self) -> bool:
        """
        Acquire the process-wide mutex.

        Non-Windows platforms do not use the old lock-file fallback. They run
        without single-instance enforcement until a native strategy is added.
        """
        if sys.platform != "win32":
            self._lock_acquired = True
            return True

        # Policy: on any unexpected failure of the mutex check we return True
        # ("allow startup"). A guard that occasionally permits a second instance
        # is far better than one that can wedge the app shut, so every error
        # path below intentionally falls through to launching.
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _configure_kernel32_signatures(kernel32)
            handle = kernel32.CreateMutexW(None, False, self.mutex_name)
            if not handle:
                logger.warning("CreateMutexW failed; allowing startup to continue")
                return True

            if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
                logger.info("Another AccessiWeather instance already owns the mutex")
                kernel32.CloseHandle(handle)
                self._mutex_handle = None
                self._lock_acquired = False
                return False

            if self._existing_window_is_present():
                logger.info(
                    "Found an existing AccessiWeather window without the mutex; "
                    "treating it as the running instance"
                )
                kernel32.CloseHandle(handle)
                self._mutex_handle = None
                self._lock_acquired = False
                return False

            self._mutex_handle = handle
            self._lock_acquired = True
            logger.info("Acquired AccessiWeather single-instance mutex")
            return True
        except Exception as exc:
            logger.warning("Single-instance mutex check failed; allowing startup: %s", exc)
            return True

    def request_existing_instance_show(
        self, request: NotificationActivationRequest | None = None
    ) -> bool:
        """Ask the existing instance to become visible and optionally route activation."""
        handoff_request = request or NotificationActivationRequest(kind="generic_fallback")
        if sys.platform == "win32" and _send_activation_request_ipc(handoff_request):
            return True

        if sys.platform != "win32":
            self.write_activation_handoff(handoff_request)
            return False

        shown = self._show_existing_window()
        # The direct window restore only raises the window; it cannot act on a
        # specific request. Write the handoff so the primary instance still
        # routes discussion/alert_details intents — but skip it for a plain
        # generic_fallback that a successful restore already satisfied, so the
        # primary doesn't handle the same generic request a second time when it
        # polls for handoffs.
        if not shown or handoff_request.kind != "generic_fallback":
            self.write_activation_handoff(handoff_request)
        return shown

    def _show_existing_window(self) -> bool:
        """Restore and foreground the existing main window; True if one was shown."""
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            _configure_user32_signatures(user32)
            hwnd = self._find_accessiweather_window(user32)
            if not hwnd:
                logger.info("No existing AccessiWeather window found to restore")
                return False

            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.ShowWindow(hwnd, SW_SHOWNORMAL)
            user32.SetForegroundWindow(hwnd)
            return True
        except Exception as exc:
            logger.warning("Failed to show existing AccessiWeather instance: %s", exc)
            return False

    def start_activation_ipc_server(
        self, on_request: Callable[[NotificationActivationRequest], None]
    ) -> bool:
        """Start a Windows named-pipe listener for duplicate-launch activation."""
        return self._activation_ipc_server.start(on_request)

    def stop_activation_ipc_server(self) -> None:
        """Stop the duplicate-launch activation IPC listener."""
        self._activation_ipc_server.stop()

    def _find_accessiweather_window(self, user32) -> int:
        """Find the primary AccessiWeather top-level window."""
        hwnd = user32.FindWindowW(None, "AccessiWeather")
        if hwnd:
            return int(hwnd)

        found_hwnd = 0

        try:
            enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def _enum_window_callback(candidate_hwnd, _lparam):
                nonlocal found_hwnd
                title = self._get_window_title(user32, candidate_hwnd).strip()
                if self._is_accessiweather_window_title(title):
                    found_hwnd = int(candidate_hwnd)
                    return False
                return True

            user32.EnumWindows(enum_windows_proc(_enum_window_callback), None)
        except Exception:
            return 0

        return found_hwnd

    @staticmethod
    def _is_accessiweather_window_title(title: str) -> bool:
        """Return True for AccessiWeather's main window titles, but not browser pages."""
        return title == "AccessiWeather" or title.startswith("AccessiWeather \u2014 ")

    def _existing_window_is_present(self) -> bool:
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            _configure_user32_signatures(user32)
            return bool(self._find_accessiweather_window(user32))
        except Exception:
            return False

    @staticmethod
    def _get_window_title(user32, hwnd) -> str:
        try:
            length = int(user32.GetWindowTextLengthW(hwnd))
            if length <= 0:
                return ""
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value
        except Exception:
            return ""

    def release_lock(self) -> None:
        """Release the owned mutex handle."""
        self.stop_activation_ipc_server()
        if not self._mutex_handle:
            self._lock_acquired = False
            return

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _configure_kernel32_signatures(kernel32)
            kernel32.CloseHandle(self._mutex_handle)
            logger.info("Released AccessiWeather single-instance mutex")
        except Exception as exc:
            logger.debug("Failed to close single-instance mutex handle: %s", exc)
        finally:
            self._mutex_handle = None
            self._lock_acquired = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit."""
        self.release_lock()


def _send_activation_request_ipc(request: NotificationActivationRequest) -> bool:
    """Send an activation request to the primary instance over a Windows named pipe."""
    return send_activation_request(request)
