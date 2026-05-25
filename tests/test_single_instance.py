from __future__ import annotations

import types
from types import SimpleNamespace

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

    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is False
    assert manager.request_existing_instance_show() is True
    assert user32.find_window_calls == [(None, "AccessiWeather")]
    assert user32.show_window_calls
    assert user32.foreground_calls == [2468]
    assert kernel32.closed_handles == [100]


def test_existing_instance_activation_writes_handoff_then_shows_window(monkeypatch, tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    kernel32 = _FakeKernel32(last_error=ERROR_ALREADY_EXISTS)
    user32 = _FakeUser32(hwnd=1357)

    import accessiweather.single_instance as single_instance

    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance, "ctypes", _FakeCtypes(kernel32, user32))

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
