from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run_import_probe(code: str) -> dict[str, object]:
    env = os.environ.copy()
    pythonpath = str(ROOT / "src")
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_submodule_import_does_not_eagerly_import_app() -> None:
    result = _run_import_probe(
        """
import importlib
import json
import sys

runtime_env = importlib.import_module("accessiweather.runtime_env")
print(json.dumps({
    "compiled": runtime_env.is_compiled_runtime(),
    "has_app": "accessiweather.app" in sys.modules,
}))
"""
    )

    assert result == {"compiled": False, "has_app": False}


def test_legacy_top_level_exports_are_lazy() -> None:
    result = _run_import_probe(
        """
import importlib
import json
import sys

package = importlib.import_module("accessiweather")
print(json.dumps({
    "has_app": "accessiweather.app" in sys.modules,
    "version_type": type(package.__version__).__name__,
}))
"""
    )

    assert result == {"has_app": False, "version_type": "str"}


def test_legacy_top_level_export_getattr_loads_lazily() -> None:
    import accessiweather
    from accessiweather.utils import TemperatureUnit

    assert accessiweather.TemperatureUnit is TemperatureUnit


def test_unknown_top_level_export_raises_attribute_error() -> None:
    import accessiweather

    with pytest.raises(AttributeError):
        accessiweather.__getattr__("missing_export")
