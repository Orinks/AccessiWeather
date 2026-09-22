"""Regression tests for OpenAI chat packaging in frozen builds (#749)."""

from __future__ import annotations

import ast
import importlib.util
import tomllib
from pathlib import Path

import pytest

from installer import build_nuitka

ROOT = Path(__file__).resolve().parents[1]


def _openai_dependency_specs() -> list[str]:
    """Return openai requirement strings from packaging metadata."""
    with (ROOT / "pyproject.toml").open("rb") as handle:
        deps = tomllib.load(handle)["project"]["dependencies"]
    pyproject_specs = [dep for dep in deps if dep.lower().startswith("openai")]
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    requirement_specs = [
        line.strip()
        for line in requirements
        if line.strip().lower().startswith("openai") and not line.strip().startswith("#")
    ]
    return pyproject_specs + requirement_specs


def test_openai_dependency_is_pinned_below_major_break() -> None:
    """Keep openai on a bounded range so frozen builds cannot float unboundedly."""
    specs = _openai_dependency_specs()
    assert specs, "openai must be declared in pyproject.toml and requirements.txt"
    for spec in specs:
        assert "<4" in spec, f"openai pin must exclude openai 4+: {spec}"
        assert ">=" in spec, f"openai pin must set a minimum version: {spec}"


def test_nuitka_command_includes_openai_chat_package() -> None:
    """Frozen builds must force-include the deferred openai.resources.chat path."""
    command = build_nuitka.build_nuitka_command(
        output_dir=Path("dist"),
        build_tag=None,
        assume_platform="Windows",
    )
    assert "--include-package=openai.resources.chat" in command


def test_openai_runtime_helper_imports_chat_modules() -> None:
    """
    Fail if the chat completions submodule path used by Explain Weather is missing.

    ``client.chat.completions.create`` resolves ``openai.resources.chat.chat``.
    If that import fails here, the Nuitka-packaged app will fail the same way.
    """
    openai_spec = importlib.util.find_spec("openai")
    if openai_spec is None:
        pytest.skip("openai is not installed in this environment")

    from accessiweather.openai_runtime import ensure_openai_chat_runtime

    OpenAI = ensure_openai_chat_runtime()
    assert callable(OpenAI)

    chat_mod = importlib.import_module("openai.resources.chat.chat")
    completions_mod = importlib.import_module("openai.resources.chat.completions")
    assert chat_mod.__name__ == "openai.resources.chat.chat"
    assert completions_mod.__name__.startswith("openai.resources.chat.completions")


def test_openai_runtime_module_statically_imports_chat_path() -> None:
    """Keep a compile-time import edge so Nuitka's analyzer can see chat modules."""
    source = (ROOT / "src" / "accessiweather" / "openai_runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "openai.resources.chat.chat" in imported
    assert "openai.resources.chat.completions" in imported
