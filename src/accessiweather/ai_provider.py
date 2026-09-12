"""Provider selection and redacted Venice API integration helpers."""

from __future__ import annotations

import httpx

from .ai_explainer_models import (
    AIExplainerError,
    InsufficientCreditsError,
    InvalidAPIKeyError,
    InvalidModelError,
    NetworkError,
    RateLimitError,
    RequestTimeoutError,
)

VENICE_BASE_URL = "https://api.venice.ai/api/v1"
DEFAULT_VENICE_MODEL = "venice-uncensored-1-2"


def venice_request_options() -> dict:
    """Keep application and user prompts authoritative on every request."""
    return {"extra_body": {"venice_parameters": {"include_venice_system_prompt": False}}}


def venice_error(error: Exception) -> AIExplainerError:
    """Map failures without exposing response bodies, request headers, or credentials."""
    if isinstance(error, AIExplainerError):
        return error
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if status in (401, 403):
        return InvalidAPIKeyError(
            "Your Venice API key is invalid or lacks access. Check Settings > AI Explanations."
        )
    if status == 402:
        return InsufficientCreditsError(
            "Your Venice account has insufficient API credits. Add prepaid USD credits "
            "in your Venice account, then try again."
        )
    if status == 429:
        return RateLimitError("Venice rate limit reached. Wait a moment and try again.")
    if status == 404:
        return InvalidModelError(
            "The selected Venice model is unavailable. Check Settings > AI Explanations."
        )
    if (
        isinstance(error, (httpx.TimeoutException, TimeoutError))
        or "Timeout" in type(error).__name__
    ):
        return RequestTimeoutError("Venice request timed out. Please try again.")
    if (
        isinstance(error, (httpx.RequestError, ConnectionError))
        or "Connection" in type(error).__name__
    ):
        return NetworkError("Could not reach Venice. Check your internet connection and try again.")
    if isinstance(status, int) and status >= 500:
        return NetworkError("Venice is temporarily unavailable. Please try again later.")
    return AIExplainerError(
        "Venice could not complete the request. Check your selected model and try again."
    )


async def validate_venice_api_key(api_key: str) -> tuple[bool, str]:
    """Validate authentication without spending credits on a generation."""
    if not api_key or not api_key.strip():
        return (
            False,
            "A Venice API key is required. Add your own key in Settings > AI Explanations.",
        )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{VENICE_BASE_URL}/api_keys/rate_limits",
                headers={"Authorization": f"Bearer {api_key.strip()}"},
            )
            response.raise_for_status()
            data = response.json()["data"]
            if data.get("accessPermitted") is False:
                return (
                    False,
                    "Your Venice key is recognized but API access is not permitted. Check your Venice account.",
                )
        return (
            True,
            "Venice API key verified. Generating responses uses your account's API credits.",
        )
    except Exception as error:
        return False, str(venice_error(error))


def create_venice_client(api_key: str | None):
    """Create an authenticated client; never fall back to another provider."""
    if not api_key or not api_key.strip():
        raise InvalidAPIKeyError(
            "A Venice API key is required. Add your own key in Settings > AI Explanations."
        )
    from openai import OpenAI

    return OpenAI(base_url=VENICE_BASE_URL, api_key=api_key.strip(), timeout=30.0, max_retries=0)
