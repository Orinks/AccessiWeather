"""
Regression tests for OpenAI chat packaging in frozen builds (#749).

OpenRouter and Venice both use ``OpenAI(...).chat.completions.create``. The
failure mode is the shared ``openai.resources.chat.chat`` submodule missing
from Nuitka builds, so both providers must stay on the same packaging path.
"""

from __future__ import annotations

import ast
import importlib.util
import tomllib
from pathlib import Path

import pytest

from installer import build_nuitka

ROOT = Path(__file__).resolve().parents[1]
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
VENICE_BASE_URL = "https://api.venice.ai/api/v1"
PROVIDER_CLIENT_SOURCES = (
    ROOT / "src" / "accessiweather" / "ai_provider.py",
    ROOT / "src" / "accessiweather" / "ai_explainer_openrouter_client.py",
    ROOT / "src" / "accessiweather" / "ui" / "dialogs" / "weather_assistant_dialog.py",
)


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


def _require_openai():
    """Skip when openai is absent; packaging CI installs it via project deps."""
    if importlib.util.find_spec("openai") is None:
        pytest.skip("openai is not installed in this environment")


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
    _require_openai()

    from accessiweather.openai_runtime import ensure_openai_chat_runtime

    OpenAI = ensure_openai_chat_runtime()
    assert callable(OpenAI)

    chat_mod = importlib.import_module("openai.resources.chat.chat")
    completions_mod = importlib.import_module("openai.resources.chat.completions")
    assert chat_mod.__name__ == "openai.resources.chat.chat"
    assert completions_mod.__name__.startswith("openai.resources.chat.completions")


@pytest.mark.parametrize(
    ("label", "base_url"),
    [
        ("openrouter", OPENROUTER_BASE_URL),
        ("venice", VENICE_BASE_URL),
    ],
)
def test_openrouter_and_venice_clients_resolve_shared_chat_module(label, base_url) -> None:
    """
    Both providers share the OpenAI chat.completions path (#749).

    Repro matrix coverage without a Windows runner: construct each provider's
    client the same way production does and prove ``client.chat`` loads
    ``openai.resources.chat.chat`` (the missing frozen module).
    """
    _require_openai()

    from accessiweather.ai_explainer_openrouter import OPENROUTER_BASE_URL as PROVIDER_OR_URL
    from accessiweather.ai_provider import (
        VENICE_BASE_URL as PROVIDER_VENICE_URL,
        create_venice_client,
    )
    from accessiweather.openai_runtime import ensure_openai_chat_runtime

    assert PROVIDER_VENICE_URL == VENICE_BASE_URL
    assert PROVIDER_OR_URL == OPENROUTER_BASE_URL

    if label == "venice":
        client = create_venice_client("test-venice-key")
        assert str(client.base_url).rstrip("/") == VENICE_BASE_URL.rstrip("/")
    else:
        OpenAI = ensure_openai_chat_runtime()
        client = OpenAI(base_url=base_url, api_key="test-openrouter-key", timeout=30.0)
        assert str(client.base_url).rstrip("/") == OPENROUTER_BASE_URL.rstrip("/")

    assert type(client.chat).__module__ == "openai.resources.chat.chat"
    assert type(client.chat.completions).__module__.startswith("openai.resources.chat.completions")
    assert callable(client.chat.completions.create)


def test_provider_call_sites_use_shared_openai_runtime_helper() -> None:
    """OpenRouter, Venice, and Weather Assistant must all go through the helper."""
    for path in PROVIDER_CLIENT_SOURCES:
        source = path.read_text(encoding="utf-8")
        assert "ensure_openai_chat_runtime" in source, (
            f"{path.relative_to(ROOT)} must use ensure_openai_chat_runtime "
            "so OpenRouter and Venice share packaging (#749)"
        )
        assert "from openai import OpenAI" not in source, (
            f"{path.relative_to(ROOT)} must not import OpenAI directly; "
            "that bypasses the chat submodule import edge"
        )


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
