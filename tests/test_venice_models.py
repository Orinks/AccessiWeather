"""Contracts for Venice catalog prices and authenticated balances."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.api.venice_models import VeniceModelsClient, VeniceModelsError


@pytest.mark.parametrize("value", [None, "invalid", "nan", "inf", -1, False])
def test_unknown_prices_are_not_free(value):
    model = VeniceModelsClient()._parse_model(
        {"id": "test", "model_spec": {"pricing": {"input": {"usd": value}, "output": {"usd": 0}}}}
    )
    assert model.pricing_prompt is None
    assert model.is_free is False


def test_catalog_prices_are_already_per_million():
    model = VeniceModelsClient()._parse_model(
        {
            "id": "test",
            "type": "text",
            "model_spec": {
                "name": "Test model",
                "description": "Description",
                "availableContextTokens": 131072,
                "capabilities": {"supportsFunctionCalling": True},
                "offline": True,
                "pricing": {"input": {"usd": 0.2}, "output": {"usd": "0.9"}},
            },
        }
    )
    assert (model.pricing_prompt, model.pricing_completion) == (0.2, 0.9)
    assert model.supports_function_calling and model.offline
    assert model.provider == "Venice"
    assert model.context_display == "131K"


def test_only_explicit_zero_prices_are_free():
    model = VeniceModelsClient()._parse_model(
        {"id": "test", "model_spec": {"pricing": {"input": {"usd": 0}, "output": {"usd": "0"}}}}
    )
    assert model.is_free


def mock_client(payload=None, status=200, error=None):
    client = AsyncMock()
    response = httpx.Response(
        status, json=payload, request=httpx.Request("GET", "https://example.test")
    )
    client.get.return_value = response
    client.get.side_effect = error
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = client
    return factory, client


@pytest.mark.asyncio
async def test_public_catalog_filters_nontext_and_caches():
    factory, client = mock_client(
        {"data": [{"id": "text-model", "type": "text"}, {"id": "image-model", "type": "image"}]}
    )
    with patch("accessiweather.api.venice_models.httpx.AsyncClient", factory):
        api = VeniceModelsClient()
        models = await api.fetch_models()
        assert await api.get_text_models() == models
    assert [model.id for model in models] == ["text-model"]
    assert client.get.call_args.kwargs["params"] == {"type": "text"}
    assert client.get.call_args.kwargs["headers"] == {}
    assert client.get.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"canConsume": False, "balances": {"usd": 0, "diem": 0}}, (False, 0, 0)),
        ({"balances": {}}, (None, None, None)),
        (
            {
                "canConsume": True,
                "consumptionCurrency": "BUNDLED_CREDITS",
                "balances": {"usd": "1.50", "diem": 2},
            },
            (True, 1.5, 2),
        ),
    ],
)
async def test_balance_preserves_unknown_and_no_funds(payload, expected):
    factory, client = mock_client(payload)
    with patch("accessiweather.api.venice_models.httpx.AsyncClient", factory):
        balance = await VeniceModelsClient("test-key").fetch_balance()
    assert (balance.can_consume, balance.usd, balance.diem) == expected
    assert client.get.call_args.kwargs["headers"] == {"Authorization": "Bearer test-key"}
    assert client.get.call_args.args[0].endswith("/billing/balance")


@pytest.mark.asyncio
async def test_missing_key_never_requests_balance():
    with pytest.raises(VeniceModelsError, match="key is required"):
        await VeniceModelsClient().fetch_balance()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_errors_never_expose_response_body(status, caplog):
    factory, _client = mock_client({"error": "secret-key"}, status)
    with (
        patch("accessiweather.api.venice_models.httpx.AsyncClient", factory),
        pytest.raises(VeniceModelsError) as error,
    ):
        await VeniceModelsClient("secret-key").fetch_balance()
    assert "secret-key" not in str(error.value)
    assert "secret-key" not in caplog.text
    assert "admin" not in str(error.value).lower()


@pytest.mark.asyncio
async def test_network_error_is_redacted():
    factory, _client = mock_client(error=httpx.ConnectError("secret-key"))
    with (
        patch("accessiweather.api.venice_models.httpx.AsyncClient", factory),
        pytest.raises(VeniceModelsError, match="connection"),
    ):
        await VeniceModelsClient().fetch_models()
