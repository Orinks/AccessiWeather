"""Provider selection and redacted Venice API integration helpers."""

from __future__ import annotations

import threading
import time

import httpx

from .ai_explainer_models import (
    AIExplainerError,
    InsufficientCreditsError,
    InvalidAPIKeyError,
    InvalidModelError,
    NetworkError,
    ProviderPermissionError,
    RateLimitError,
    RequestTimeoutError,
)

VENICE_BASE_URL = "https://api.venice.ai/api/v1"
DEFAULT_VENICE_MODEL = "venice-uncensored-1-2"
REQUEST_DEADLINE_SECONDS = 30.0
# Streaming limits. A queued model sends only keep-alive comments, so one with no
# token after FIRST_TOKEN_SECONDS is dropped for the retry; a model that is writing
# is kept until it goes STALL_SECONDS without a token or hits the overall ceiling.
FIRST_TOKEN_SECONDS = 10.0
STALL_SECONDS = 15.0
STREAM_DEADLINE_SECONDS = 90.0


class RequestDeadline:
    """
    Abort a completion that outlives its limits by closing its client.

    Client timeouts only bound the gap between bytes, and providers send keep-alive
    bytes while a busy model queues, so one request could otherwise hang for minutes.
    A closed client is replaced on the next request (see ``is_closed()``).
    Streaming callers pass ``first_token_seconds`` and ``stall_seconds`` and call
    ``progress()`` for each token; the request is dropped when tokens stop coming.
    """

    def __init__(
        self,
        client,
        seconds: float = REQUEST_DEADLINE_SECONDS,
        first_token_seconds: float | None = None,
        stall_seconds: float | None = None,
    ):
        """Watch ``client`` for at most ``seconds`` once the block is entered."""
        self.client = client
        self.seconds = seconds
        self.first_token_seconds = first_token_seconds
        self.stall_seconds = stall_seconds
        self.expired_message: str | None = None
        self._last_progress: float | None = None

    def _limit_exceeded(self, now: float) -> str | None:
        if now - self._started_at >= self.seconds:
            return f"The AI service did not answer within {self.seconds:.0f} seconds."
        if self._last_progress is None:
            if self.first_token_seconds and now - self._started_at >= self.first_token_seconds:
                return (
                    "The AI model did not start answering within "
                    f"{self.first_token_seconds:.0f} seconds."
                )
        elif self.stall_seconds and now - self._last_progress >= self.stall_seconds:
            return f"The AI model stopped answering for {self.stall_seconds:.0f} seconds."
        return None

    def _watch(self) -> None:
        while not self._done.wait(0.1):
            message = self._limit_exceeded(time.monotonic())
            if message:
                self.expired_message = message
                self.client.close()
                return

    def __enter__(self):
        self._started_at = time.monotonic()
        self._done = threading.Event()
        threading.Thread(target=self._watch, daemon=True).start()
        return self

    def progress(self) -> None:
        """Record that the model produced a token."""
        self._last_progress = time.monotonic()

    def __exit__(self, exc_type, exc, tb):
        self._done.set()
        if self.expired_message and exc is not None:
            raise RequestTimeoutError(self.expired_message) from None
        return False


def stream_chat_completion(
    client,
    *,
    first_token_seconds: float = FIRST_TOKEN_SECONDS,
    stall_seconds: float = STALL_SECONDS,
    seconds: float = STREAM_DEADLINE_SECONDS,
    **request,
) -> dict:
    """Stream one completion and return its text, model, finish reason and token counts."""
    parts: list[str] = []
    model = None
    finish_reason = None
    usage = None
    with RequestDeadline(client, seconds, first_token_seconds, stall_seconds) as deadline:
        stream = client.chat.completions.create(
            stream=True, stream_options={"include_usage": True}, **request
        )
        for chunk in stream:
            model = chunk.model or model
            usage = chunk.usage or usage
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            finish_reason = choice.finish_reason or finish_reason
            delta = choice.delta
            if delta is None:
                continue
            # Reasoning models stream their thinking before any answer text.
            if (
                delta.content
                or getattr(delta, "reasoning", None)
                or getattr(delta, "reasoning_content", None)
            ):
                deadline.progress()
            if delta.content:
                parts.append(delta.content)
    return {
        "content": "".join(parts),
        "model": model,
        "finish_reason": finish_reason,
        "total_tokens": usage.total_tokens if usage else 0,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
    }


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
    if status == 401:
        return InvalidAPIKeyError(
            "Venice rejected this API key. It may be invalid or expired. "
            "Check your Venice key in Settings > AI."
        )
    if status == 403:
        return ProviderPermissionError(
            "Venice denied permission for this request. Check your key and account permissions. "
            "This does not establish that your key is invalid."
        )
    if status == 402:
        return InsufficientCreditsError(
            "Your Venice account has insufficient API credits. Add prepaid USD credits "
            "in your Venice account, then try again."
        )
    if status == 429:
        return RateLimitError("Venice rate limit reached. Wait a moment and try again.")
    if status == 404:
        return InvalidModelError("The selected Venice model is unavailable. Check Settings > AI.")
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


def openrouter_error(error: Exception) -> AIExplainerError:
    """Map an OpenRouter completion failure without showing upstream text."""
    if isinstance(error, AIExplainerError):
        return error
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if status == 401:
        return InvalidAPIKeyError(
            "OpenRouter could not authenticate this request. Validate your key in Settings > AI."
        )
    if status == 402:
        return InsufficientCreditsError(
            "Your OpenRouter account has insufficient credits for this request. "
            "Add credits or choose a free model in Settings > AI."
        )
    if status == 403:
        return ProviderPermissionError(
            "OpenRouter denied this request. Check your account and model permissions. "
            "This does not establish that your key is invalid."
        )
    if status == 404:
        return InvalidModelError(
            "The selected OpenRouter model is unavailable. Choose another model in Settings > AI."
        )
    if status == 429:
        return RateLimitError("OpenRouter rate limit reached. Wait a moment and try again.")
    if (
        isinstance(error, (httpx.TimeoutException, TimeoutError))
        or "Timeout" in type(error).__name__
    ):
        return RequestTimeoutError("OpenRouter request timed out. Please try again.")
    if (
        isinstance(error, (httpx.RequestError, ConnectionError))
        or "Connection" in type(error).__name__
    ):
        return NetworkError(
            "Could not reach OpenRouter. Check your internet connection and try again."
        )
    if isinstance(status, int) and status >= 500:
        return NetworkError("OpenRouter is temporarily unavailable. Please try again later.")
    return AIExplainerError(
        "OpenRouter could not complete the request. Check your selected model and try again."
    )


def ai_request_error(error: Exception, provider: str = "openrouter") -> AIExplainerError:
    """Return a safe message for any AI request failure, including unexpected errors."""
    return venice_error(error) if provider == "venice" else openrouter_error(error)


async def validate_venice_api_key(api_key: str) -> tuple[bool, str]:
    """Validate authentication without spending credits on a generation."""
    if not api_key or not api_key.strip():
        return (
            False,
            "A Venice API key is required. Add your own key in Settings > AI.",
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
        balances = data.get("balances")
        if (
            isinstance(balances, dict)
            and {"USD", "DIEM", "BUNDLED_CREDITS"}.issubset(balances)
            and all(
                isinstance(value, (int, float)) and not isinstance(value, bool) and value <= 0
                for value in balances.values()
            )
        ):
            return (
                True,
                "Venice API key verified, but no positive balance is listed. "
                "Generation may require credits; other credit types may still apply.",
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
        raise InvalidAPIKeyError("A Venice API key is required. Add your own key in Settings > AI.")
    from openai import OpenAI

    return OpenAI(base_url=VENICE_BASE_URL, api_key=api_key.strip(), timeout=30.0, max_retries=0)
