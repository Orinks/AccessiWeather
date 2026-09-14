"""Read-only Venice text catalog and account balance integration."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import httpx

from ..ai_provider import VENICE_BASE_URL


def _number(value: Any) -> float | None:
    """Return a finite nonnegative number, preserving unknown values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


# Ordered (keywords, provider id) pairs; earlier entries win. Provider ids match the
# OpenRouter-style ids used by the model browser's display-name table.
_VENICE_PROVIDER_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("venice",), "venice"),
    (("hermes",), "nousresearch"),
    (("claude",), "anthropic"),
    (("openai", "gpt"), "openai"),
    (("gemini", "gemma", "google"), "google"),
    (("grok",), "x-ai"),
    (("qwen",), "qwen"),
    (("deepseek",), "deepseek"),
    (("llama",), "meta-llama"),
    (("mistral",), "mistralai"),
    (("kimi",), "moonshotai"),
    (("glm", "z-ai", "zai-org"), "z-ai"),
    (("minimax",), "minimax"),
    (("nvidia", "nemotron"), "nvidia"),
    (("xiaomi", "mimo"), "xiaomi"),
    (("seed",), "bytedance"),
    (("mercury",), "inception"),
    (("aion",), "aion-labs"),
)


def infer_venice_provider(model_id: str, name: str = "") -> str:
    """Map a Venice model to a vendor id; Venice-hosted originals fall back to "venice"."""
    haystack = f"{model_id} {name}".lower()
    if haystack.startswith("e2ee-"):
        haystack = haystack[len("e2ee-") :]
    for keywords, provider in _VENICE_PROVIDER_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return provider
    return "venice"


@dataclass
class VeniceModel:
    """Text model metadata; prices are USD per million tokens."""

    id: str
    name: str
    description: str
    context_length: int | None
    pricing_prompt: float | None
    pricing_completion: float | None
    is_free: bool
    supports_function_calling: bool
    offline: bool

    @property
    def provider(self) -> str:
        """Infer the model vendor from the ID so the browser can filter by provider."""
        return infer_venice_provider(self.id, self.name)

    @property
    def display_name(self) -> str:
        """Include explicitly known free or offline status."""
        return (
            self.name + (" (Free)" if self.is_free else "") + (" (Offline)" if self.offline else "")
        )

    @property
    def context_display(self) -> str:
        """Format the available context length."""
        if self.context_length is None:
            return "Unknown"
        if self.context_length >= 1_000_000:
            return f"{self.context_length / 1_000_000:.1f}M"
        if self.context_length >= 1000:
            return f"{self.context_length / 1000:.0f}K"
        return str(self.context_length)


@dataclass
class VeniceBalance:
    """Account state; None means the service did not supply a known value."""

    can_consume: bool | None
    consumption_currency: str | None
    usd: float | None
    diem: float | None


class VeniceModelsError(Exception):
    """A safe user-facing catalog or account lookup failure."""


class VeniceModelsClient:
    """Fetch model metadata and balances without generating content."""

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        """Initialize the optional account key and request timeout."""
        self.api_key = api_key.strip() if api_key else ""
        self.timeout = timeout
        self._cached_models: list[VeniceModel] | None = None

    def _parse_model(self, data: dict[str, Any]) -> VeniceModel:
        spec = _mapping(data.get("model_spec"))
        pricing = _mapping(spec.get("pricing"))
        prompt = _number(_mapping(pricing.get("input")).get("usd"))
        completion = _number(_mapping(pricing.get("output")).get("usd"))
        context = _number(spec.get("availableContextTokens"))
        model_id = str(data.get("id", ""))
        return VeniceModel(
            id=model_id,
            name=spec.get("name") if isinstance(spec.get("name"), str) else model_id,
            description=spec.get("description") if isinstance(spec.get("description"), str) else "",
            context_length=int(context) if context is not None and context > 0 else None,
            pricing_prompt=prompt,
            pricing_completion=completion,
            is_free=prompt == 0 and completion == 0,
            supports_function_calling=_mapping(spec.get("capabilities")).get(
                "supportsFunctionCalling"
            )
            is True,
            offline=spec.get("offline") is True,
        )

    async def _get(self, endpoint: str, *, params: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{VENICE_BASE_URL}/{endpoint}", params=params, headers=headers
                )
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Invalid response shape")
            return payload
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == 401:
                message = (
                    "Venice could not authenticate this request. Check your API key in Settings."
                )
            elif status == 403:
                message = "Your Venice key cannot access this information. Check your account permissions or view it on the Venice website."
            elif status == 429:
                message = "Venice rate limit reached. Wait a moment and try again."
            else:
                message = "Venice could not retrieve this information. Please try again later."
            raise VeniceModelsError(message) from None
        except httpx.TimeoutException:
            raise VeniceModelsError("Venice request timed out. Please try again.") from None
        except httpx.RequestError:
            raise VeniceModelsError(
                "Could not reach Venice. Check your internet connection."
            ) from None
        except Exception:
            raise VeniceModelsError(
                "Venice returned unreadable information. Please try again later."
            ) from None

    async def fetch_models(self, force_refresh: bool = False) -> list[VeniceModel]:
        """Fetch text models, retaining offline status and unknown prices."""
        if self._cached_models is not None and not force_refresh:
            return list(self._cached_models)
        payload = await self._get("models", params={"type": "text"})
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise VeniceModelsError("Venice returned an unreadable model catalog.")
        models = [
            self._parse_model(row)
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and row["id"]
            and row.get("type", "text") == "text"
        ]
        models.sort(key=lambda model: model.name.casefold())
        self._cached_models = models
        return list(models)

    async def get_text_models(self, force_refresh: bool = False) -> list[VeniceModel]:
        """Return the text catalog using the common model-browser interface."""
        return await self.fetch_models(force_refresh)

    async def fetch_balance(self) -> VeniceBalance:
        """Retrieve fresh authenticated balance state; never infer missing amounts."""
        if not self.api_key:
            raise VeniceModelsError("A Venice API key is required to check your balance.")
        payload = await self._get("billing/balance")
        balances = _mapping(payload.get("balances"))
        allowed = payload.get("canConsume")
        currency = payload.get("consumptionCurrency")
        return VeniceBalance(
            can_consume=allowed if isinstance(allowed, bool) else None,
            consumption_currency=currency
            if currency in ("USD", "DIEM", "VCU", "BUNDLED_CREDITS")
            else None,
            usd=_number(balances.get("usd")),
            diem=_number(balances.get("diem")),
        )
