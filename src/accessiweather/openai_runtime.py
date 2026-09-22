"""
OpenAI SDK import surface required by frozen AccessiWeather builds.

The public ``OpenAI(...).chat.completions.create`` path resolves
``openai.resources.chat.chat`` through a deferred import inside a
``cached_property``. Nuitka does not follow that import, so Explain Weather
and Weather Assistant fail for **both** OpenRouter and Venice with
``No module named 'openai.resources.chat.chat'`` (#749) unless these modules
are imported or force-included at packaging time.

Both providers construct an ``OpenAI`` client (OpenRouter or Venice base URL)
and then call ``client.chat.completions.create``. Importing the chat modules
here keeps a compile-time edge from AccessiWeather into that shared path.
"""

from __future__ import annotations

from typing import Any


def ensure_openai_chat_runtime() -> Any:
    """
    Import and return the OpenAI client class after loading chat modules.

    Raises:
        ImportError: If the openai package or its chat completions path is missing.

    """
    # Import the deferred submodule path used by client.chat.completions.create.
    import openai.resources.chat.chat  # noqa: F401
    import openai.resources.chat.completions  # noqa: F401
    from openai import OpenAI

    return OpenAI


__all__ = ["ensure_openai_chat_runtime"]
