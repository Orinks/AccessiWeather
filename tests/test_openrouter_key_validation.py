"""Authentication checks must not depend on models or expose remote error text."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from accessiweather import ai_explainer_validation as validation
from accessiweather.ai_explainer import AIExplainer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, valid, phrase",
    [
        (200, True, "valid"),
        (401, False, "rejected"),
        (403, False, "permissions"),
        (429, False, "rate limit"),
        (500, False, "unavailable"),
        (503, False, "unavailable"),
        (402, False, "unavailable"),
    ],
)
async def test_key_check_uses_auth_endpoint_and_safe_status_messages(
    monkeypatch, status, valid, phrase
):
    client = AsyncMock()
    client.get.return_value = httpx.Response(status, text="secret response body")
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = client
    monkeypatch.setattr(validation.httpx, "AsyncClient", factory)

    result, message = await validation.validate_openrouter_api_key("  secret-key  ")

    assert result is valid
    assert phrase in message
    assert "secret" not in message
    factory.assert_called_once_with(timeout=15.0)
    client.get.assert_awaited_once_with(
        "https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer secret-key"}
    )
    client.post.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, phrase",
    [
        (httpx.ConnectError("secret-key"), "connection"),
        (httpx.ReadTimeout("secret-key"), "timed out"),
        (RuntimeError("secret-key"), "Unable"),
    ],
)
async def test_network_and_unexpected_errors_are_redacted(monkeypatch, caplog, error, phrase):
    factory = MagicMock()
    factory.return_value.__aenter__.side_effect = error
    monkeypatch.setattr(validation.httpx, "AsyncClient", factory)
    valid, message = await validation.validate_openrouter_api_key("secret-key")
    assert valid is False
    assert phrase in message
    assert "secret-key" not in message + caplog.text


@pytest.mark.asyncio
async def test_blank_key_does_not_send_request(monkeypatch):
    factory = MagicMock()
    monkeypatch.setattr(validation.httpx, "AsyncClient", factory)
    assert (await validation.validate_openrouter_api_key("  "))[0] is False
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_validation_preserves_explainer_client_and_key(monkeypatch):
    check = AsyncMock(return_value=(True, "Verified"))
    monkeypatch.setattr(validation, "validate_openrouter_api_key", check)
    explainer = AIExplainer(api_key="original-key")
    client = explainer._client = object()
    assert await explainer.validate_api_key("candidate-key") is True
    assert explainer.api_key == "original-key"
    assert explainer._client is client


@pytest.mark.parametrize(
    "outcome, phrase",
    [
        ((True, "OpenRouter API key is valid!"), "valid"),
        ((False, "OpenRouter rate limit reached. Try again."), "rate limit"),
        (RuntimeError("secret-key"), "Unable to validate"),
    ],
)
def test_settings_displays_safe_validation_outcome(monkeypatch, caplog, outcome, phrase):
    from accessiweather.ui.dialogs import settings_dialog_handlers as handlers

    check = AsyncMock()
    if isinstance(outcome, Exception):
        check.side_effect = outcome
    else:
        check.return_value = outcome
    monkeypatch.setattr(validation, "validate_openrouter_api_key", check)
    message = MagicMock()
    monkeypatch.setattr(handlers.wx, "MessageBox", message)
    import threading

    targets = []
    thread = MagicMock(side_effect=lambda **kwargs: targets.append(kwargs["target"]) or MagicMock())
    monkeypatch.setattr(threading, "Thread", thread)
    callbacks = []
    monkeypatch.setattr(handlers.wx, "CallAfter", lambda *args: callbacks.append(args))
    key_control = MagicMock()
    key_control.GetValue.return_value = "secret-key"
    button = MagicMock()
    announcer = MagicMock()
    dialog = SimpleNamespace(
        _controls={"openrouter_key": key_control},
        _openrouter_validation_announcer=announcer,
        IsBeingDeleted=lambda: False,
    )
    event = SimpleNamespace(GetEventObject=lambda: button)
    handlers.SettingsDialogHandlersMixin._on_validate_openrouter_key(dialog, event)

    # The event handler returns before network work starts, with announced progress.
    check.assert_not_awaited()
    button.Disable.assert_called_once()
    key_control.SetFocus.assert_called_once()
    announcer.announce.assert_called_once_with("Validating OpenRouter key\u2026")
    assert thread.call_args.kwargs["daemon"] is True
    targets[0]()
    message.assert_not_called()
    callback, *args = callbacks[0]
    callback(*args)
    assert phrase in message.call_args.args[0]
    assert "secret-key" not in str(message.call_args) + caplog.text
    assert message.call_args.kwargs["parent"] is dialog
    button.Enable.assert_called_once()
    button.SetFocus.assert_called_once()

    # A late result after closing the settings window must not touch destroyed UI.
    message.reset_mock()
    button.reset_mock()
    dialog.IsBeingDeleted = lambda: True
    callback(*args)
    message.assert_not_called()
    button.Enable.assert_not_called()
    button.SetFocus.assert_not_called()


@pytest.mark.asyncio
async def test_valid_key_with_zero_credits_and_unavailable_model_is_accepted(monkeypatch):
    client = AsyncMock()
    client.get.return_value = httpx.Response(200, json={"data": {"limit_remaining": 0}})
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = client
    monkeypatch.setattr(validation.httpx, "AsyncClient", factory)
    explainer = AIExplainer(api_key="stored-key", model="removed/model")
    explainer._call_openrouter = MagicMock(side_effect=AssertionError("Must not generate"))

    assert await explainer.validate_api_key("candidate-key") is True
    explainer._call_openrouter.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data, exhausted",
    [
        ({"limit_remaining": 0}, True),
        ({"limit_remaining": -1}, True),
        ({"limit_remaining": None}, False),
        ({"limit_remaining": 5.5}, False),
        ({"limit_remaining": False}, False),
        ({"limit_remaining": "secret-remote-value"}, False),
        ({}, False),
        (None, False),
        ([], False),
    ],
)
async def test_valid_key_reports_only_known_spending_allowance(monkeypatch, data, exhausted):
    client = AsyncMock()
    client.get.return_value = httpx.Response(200, json={"data": data})
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = client
    monkeypatch.setattr(validation.httpx, "AsyncClient", factory)
    valid, message = await validation.validate_openrouter_api_key("test-secret")
    assert valid is True
    assert ("spending allowance is exhausted" in message) is exhausted
    assert ("Account credits and model access" in message) is not exhausted
    assert "secret" not in message


@pytest.mark.parametrize("provider", ["openrouter", "venice"])
def test_changed_key_does_not_receive_stale_validation_result(monkeypatch, provider):
    import threading

    from accessiweather import ai_provider
    from accessiweather.ui.dialogs import settings_dialog_handlers as handlers

    check = AsyncMock(return_value=(True, "Original key is valid"))
    module = validation if provider == "openrouter" else ai_provider
    monkeypatch.setattr(module, f"validate_{provider}_api_key", check)
    targets = []
    monkeypatch.setattr(
        threading,
        "Thread",
        lambda **kwargs: targets.append(kwargs["target"]) or MagicMock(),
    )
    callbacks = []
    monkeypatch.setattr(handlers.wx, "CallAfter", lambda *args: callbacks.append(args))
    message = MagicMock()
    monkeypatch.setattr(handlers.wx, "MessageBox", message)
    key_control = MagicMock()
    key_control.GetValue.return_value = "original-secret"
    button = MagicMock()
    announcer = MagicMock()
    dialog = SimpleNamespace(
        _controls={f"{provider}_key": key_control, f"validate_{provider}_key": button},
        IsBeingDeleted=lambda: False,
    )
    setattr(dialog, f"_{provider}_validation_announcer", announcer)
    event = SimpleNamespace(GetEventObject=lambda: button)
    handler = getattr(handlers.SettingsDialogHandlersMixin, f"_on_validate_{provider}_key")
    handler(dialog, event)
    key_control.GetValue.return_value = "replacement-secret"
    targets[0]()
    callback, *args = callbacks[0]
    callback(*args)

    text = message.call_args.args[0]
    assert "key changed during validation" in text
    assert "validate again" in text
    assert "secret" not in text
    announcer.announce.assert_called_with(text)
    button.Enable.assert_called_once()
    button.SetFocus.assert_called_once()
