from __future__ import annotations

from types import SimpleNamespace

from accessiweather.paths import RuntimeStoragePaths
from accessiweather.single_instance import SingleInstanceManager


def test_lock_file_uses_runtime_storage_root(tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    assert manager.try_acquire_lock() is True
    assert manager.lock_file_path == tmp_path / "config" / "state" / "accessiweather.lock"
    assert manager.lock_file_path.exists()

    manager.release_lock()
    assert not manager.lock_file_path.exists()


def test_force_remove_lock_uses_runtime_storage_root(tmp_path):
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    app = SimpleNamespace(runtime_paths=runtime_paths, formal_name="AccessiWeather")
    manager = SingleInstanceManager(app, runtime_paths=runtime_paths)

    runtime_paths.lock_file.parent.mkdir(parents=True, exist_ok=True)
    runtime_paths.lock_file.write_text("stale", encoding="utf-8")

    assert manager.force_remove_lock() is True
    assert not runtime_paths.lock_file.exists()
