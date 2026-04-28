from __future__ import annotations

import importlib
import sys


def test_submodule_import_does_not_eagerly_import_app() -> None:
    for module_name in list(sys.modules):
        if module_name == "accessiweather" or module_name.startswith("accessiweather."):
            sys.modules.pop(module_name)

    runtime_env = importlib.import_module("accessiweather.runtime_env")

    assert runtime_env.is_compiled_runtime() is False
    assert "accessiweather.app" not in sys.modules


def test_legacy_top_level_exports_are_lazy() -> None:
    for module_name in list(sys.modules):
        if module_name == "accessiweather" or module_name.startswith("accessiweather."):
            sys.modules.pop(module_name)

    package = importlib.import_module("accessiweather")

    assert "accessiweather.app" not in sys.modules
    assert isinstance(package.__version__, str)
