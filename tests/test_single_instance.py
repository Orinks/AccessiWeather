from __future__ import annotations

import queue
import sys as runtime_sys
import time
import types
import uuid
from types import SimpleNamespace

import pytest

from accessiweather.notification_activation import NotificationActivationRequest
from accessiweather.paths import RuntimeStoragePaths
from accessiweather.single_instance import (
    ERROR_ALREADY_EXISTS,
    SINGLE_INSTANCE_MUTEX_NAME,
    SingleInstanceManager,
)


class _FakeKernel32:
    def __init__(self, *, handle: int = 100, last_error: int = 0) -> None:
        self.handle = handle
        self.last_error = last_error
        self.create_mutex_calls: list[tuple[object, bool, str]] = []
        self.closed_handles: list[int] = []

    def CreateMutexW(self, security_attributes, initial_owner, name):
        self.create_mutex_calls.append((security_attributes, initial_owner, name))
        return self.handle

    def CloseHandle(self, handle):
        self.closed_handles.append(handle)
        return True


class _FakeUser32:
    def __init__(self, *, hwnd: int = 0) -> None:
        self.hwnd = hwnd
        self.find_window_calls: list[tuple[object, str]] = []
        self.show_window_calls: list[tuple[int, int]] = []
        self.foreground_calls: list[int] = []

    def FindWindowW(self, class_name, window_name):
        self.find_window_calls.append((class_name, window_name))
        return self.hwnd

    def ShowWindow(self, hwnd, command):
        self.show_window_calls.append((hwnd, command))
        return True

    def SetForegroundWindow(self, hwnd):
        self.foreground_calls.append(hwnd)
        return True


class _EnumeratingFakeUser32(_FakeUser32):
    def __init__(self, *, windows: dict[int, str]) -> None:
        super().__init__(hwnd=0)
        self.windows = windows

    def EnumWindows(self, callback, lparam):
        for hwnd in self.windows:
            if callback(hwnd, lparam) is False:
                break
        return True

    def GetWindowTextLengthW(self, hwnd):
        return len(self.windows.get(hwnd, ""))

    def GetWindowTextW(self, hwnd, buffer, max_count):
        buffer.value = self.windows.get(hwnd, "")[: max_count - 1]
        return len(buffer.value)


class _FakeCtypes(types.SimpleNamespace):
    def __init__(self, kernel32: _FakeKernel32, user32: _FakeUser32 | None = None) -> None:
        super().__init__()
        self._kernel32 = kernel32
        self._user32 = user32 or _FakeUser32()
        self.c_bool = bool
        self.c_void_p = object
        self.create_unicode_buffer = lambda size: SimpleNamespace(value="")
        self.WINFUNCTYPE = lambda *_args: lambda callback: callback

    def WinDLL(self, name, use_last_error=True):
        if name == "kernel32":
            return self._kernel32
        if name == "user32":
            return self._user32
        raise AssertionError(name)

    def get_last_error(self):
        return self._kernel32.last_error


def test_windows_mutex_uses_stable_name_and_does_not_create_lock_file(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32()

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32))

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is True
    assert kernel32.create_mutex_calls == [(None, False, SINGLE_INSTANCE_MUTEX_NAME)]
    assert not (tmp_path / "config" / "state" / "accessiweather.lock").exists()

    manager.release_lock()
    assert kernel32.closed_handles == [100]


def test_windows_startup_exits_when_legacy_window_exists_without_mutex(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32()
    user32 = _FakeUser32(hwnd=2468)

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert kernel32.closed_handles == [100]


def test_windows_startup_ignores_browser_window_with_accessiweather_title(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32()
    user32 = _EnumeratingFakeUser32(
        windows={2468: "AccessiWeather downloads - Orinks - Google Chrome"}
    )

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is True
    assert kernel32.closed_handles == []


def test_second_windows_launch_detects_existing_mutex_and_can_show_window(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _FakeUser32(hwnd=2468)

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))
    monkeypatch.setattr(single_instance, "_send_activation_request_ipc", lambda request: False)

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert manager.request_existing_instance_show() is True
    assert user32.find_window_calls == [(None, "AccessiWeather")]
    assert user32.show_window_calls
    assert user32.foreground_calls == [2468]
    assert kernel32.closed_handles == [100]


def test_second_windows_launch_restores_window_with_location_title(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _EnumeratingFakeUser32(windows={2468: "AccessiWeather \u2014 Boston, MA"})

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))
    monkeypatch.setattr(single_instance, "_send_activation_request_ipc", lambda request: False)

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert manager.request_existing_instance_show() is True
    assert user32.show_window_calls
    assert user32.foreground_calls == [2468]


def test_generic_fallback_skips_handoff_when_window_restore_succeeds(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _FakeUser32(hwnd=2468)

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))
    monkeypatch.setattr(single_instance, "_send_activation_request_ipc", lambda request: False)

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert manager.request_existing_instance_show() is True
    assert user32.foreground_calls == [2468]
    # A plain generic restore that succeeded must not also leave a handoff for
    # the primary to consume and act on a second time.
    assert manager.consume_activation_handoff() is None


def test_discussion_request_still_writes_handoff_when_window_restore_succeeds(
    monkeypatch, tmp_path
):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _FakeUser32(hwnd=2468)

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))
    monkeypatch.setattr(single_instance, "_send_activation_request_ipc", lambda request: False)

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert manager.request_existing_instance_show(NotificationActivationRequest(kind="discussion"))
    assert user32.foreground_calls == [2468]
    # The window poke can't open the discussion dialog, so the intent must still
    # be handed off for the primary to route.
    assert manager.consume_activation_handoff() == NotificationActivationRequest(kind="discussion")


def test_second_windows_launch_writes_generic_handoff_when_window_lookup_fails(
    monkeypatch, tmp_path
):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _EnumeratingFakeUser32(windows={})

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))
    monkeypatch.setattr(single_instance, "_send_activation_request_ipc", lambda request: False)

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert manager.request_existing_instance_show() is False
    request = manager.consume_activation_handoff()
    assert request == NotificationActivationRequest(kind="generic_fallback")
    assert user32.show_window_calls == []
    assert user32.foreground_calls == []


def test_second_windows_launch_uses_ipc_before_title_lookup(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _EnumeratingFakeUser32(windows={})
    sent_requests: list[NotificationActivationRequest] = []

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))

    def fake_send(request):
        sent_requests.append(request)
        return True

    monkeypatch.setattr(single_instance, "_send_activation_request_ipc", fake_send)

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert manager.request_existing_instance_show() is True
    assert sent_requests == [NotificationActivationRequest(kind="generic_fallback")]
    assert user32.show_window_calls == []
    assert user32.foreground_calls == []


def test_windows_activation_ipc_round_trips_request(monkeypatch, tmp_path):
    if runtime_sys.platform != "win32":
        pytest.skip("Windows named-pipe IPC is only available on Windows")

    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    received: queue.Queue[NotificationActivationRequest] = queue.Queue()

    from accessiweather.activation_ipc import ActivationIpcServer, send_activation_request

    pipe_address = rf"\\.\pipe\AccessiWeather.Test.{uuid.uuid4()}"

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)
    ipc_server = ActivationIpcServer(address=pipe_address)
    manager._activation_ipc_server = ipc_server
    manager.start_activation_ipc_server(received.put)
    try:
        deadline = time.monotonic() + 2
        while ipc_server._listener is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ipc_server._listener is not None

        request = NotificationActivationRequest(kind="discussion")
        assert send_activation_request(request, address=pipe_address) is True
        assert received.get(timeout=2) == request
    finally:
        manager.stop_activation_ipc_server()


def test_existing_instance_activation_writes_handoff_then_shows_window(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _FakeUser32(hwnd=1357)

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))
    monkeypatch.setattr(single_instance, "_send_activation_request_ipc", lambda request: False)

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)
    manager.try_acquire_lock()

    assert manager.request_existing_instance_show(NotificationActivationRequest(kind="discussion"))
    assert runtime_paths.activation_request_file.exists()
    assert user32.foreground_calls == [1357]


def test_non_windows_single_instance_is_non_blocking(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "linux")

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is True
    assert manager.request_existing_instance_show() is False
