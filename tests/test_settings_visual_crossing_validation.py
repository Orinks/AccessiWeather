from collections.abc import Iterable
from types import SimpleNamespace

import httpx
import pytest

from accessiweather.dialogs import settings_operations


class DummyResponse:
    def __init__(self, status_code: int):
        """Initialize dummy response with provided status."""
        self.status_code = status_code


class TrackingButton:
    def __init__(self, text: str):
        """Initialize a tracking button with initial label."""
        self._text = text
        self.enabled = True
        self.history: list[str] = [text]

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value
        self.history.append(value)

    def __bool__(self) -> bool:  # pragma: no cover - safety for truthiness checks
        return True


class FakeDialog:
    def __init__(self, api_key: str):
        """Set up minimal fake dialog state for validation tests."""
        self.visual_crossing_api_key_input = SimpleNamespace(value=api_key)
        self.validate_api_key_button = TrackingButton("Validate API Key")
        self.errors: list[tuple[str, str]] = []
        self.dialog_calls: list[tuple[str, tuple]] = []
        self.focus_calls = 0
        self.window = None
        self.app = SimpleNamespace(main_window=None)

    def _ensure_dialog_focus(self) -> None:
        self.focus_calls += 1

    async def _show_dialog_error(self, title: str, message: str) -> None:
        self.errors.append((title, message))


async def _fake_call_dialog_method(dialog, method_name, *args, **kwargs):
    dialog.dialog_calls.append((method_name, args))
    return True


def _patch_async_client(monkeypatch, responses: Iterable[object]) -> None:
    responses_list = list(responses)

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            self._responses = iter(list(responses_list))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params):
            try:
                result = next(self._responses)
            except StopIteration as exc:  # pragma: no cover - defensive
                raise AssertionError("No more responses configured for AsyncClient.get") from exc

            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)


@pytest.mark.asyncio
async def test_validate_visual_crossing_api_key_success(monkeypatch, caplog):
    caplog.set_level("INFO")
    api_key = "secret-key-123"
    dialog = FakeDialog(api_key)

    _patch_async_client(monkeypatch, [DummyResponse(200)])
    monkeypatch.setattr(settings_operations, "_call_dialog_method", _fake_call_dialog_method)

    await settings_operations.validate_visual_crossing_api_key(dialog)

    assert dialog.dialog_calls, "Expected an info dialog to be shown"
    assert dialog.dialog_calls[0][0] == "info_dialog"
    assert "Validating..." in dialog.validate_api_key_button.history
    assert dialog.validate_api_key_button.text == "Validate API Key"
    assert dialog.validate_api_key_button.enabled is True
    assert not dialog.errors
    assert api_key not in caplog.text


@pytest.mark.asyncio
async def test_validate_visual_crossing_api_key_invalid(monkeypatch, caplog):
    caplog.set_level("INFO")
    api_key = "secret-key-456"
    dialog = FakeDialog(api_key)

    _patch_async_client(monkeypatch, [DummyResponse(401)])
    monkeypatch.setattr(settings_operations, "_call_dialog_method", _fake_call_dialog_method)

    await settings_operations.validate_visual_crossing_api_key(dialog)

    assert dialog.errors, "Expected an error dialog for invalid key"
    title, message = dialog.errors[0]
    assert title == "Invalid API Key"
    assert api_key not in message
    assert api_key not in caplog.text
    assert dialog.validate_api_key_button.text == "Validate API Key"
    assert dialog.validate_api_key_button.enabled is True


@pytest.mark.asyncio
async def test_validate_visual_crossing_api_key_rate_limited(monkeypatch, caplog):
    caplog.set_level("INFO")
    api_key = "secret-key-789"
    dialog = FakeDialog(api_key)

    _patch_async_client(monkeypatch, [DummyResponse(429)])
    monkeypatch.setattr(settings_operations, "_call_dialog_method", _fake_call_dialog_method)

    await settings_operations.validate_visual_crossing_api_key(dialog)

    assert dialog.errors, "Expected an error dialog for rate limit"
    title, message = dialog.errors[0]
    assert title == "Rate Limit Exceeded"
    assert api_key not in message
    assert api_key not in caplog.text


@pytest.mark.asyncio
async def test_validate_visual_crossing_api_key_retry_backoff(monkeypatch, caplog):
    caplog.set_level("INFO")
    api_key = "retry-key-123"
    dialog = FakeDialog(api_key)

    request = httpx.Request("GET", "https://example.com")
    timeout_exc = httpx.TimeoutException("timeout", request=request)
    _patch_async_client(monkeypatch, [timeout_exc, DummyResponse(200)])
    monkeypatch.setattr(settings_operations, "_call_dialog_method", _fake_call_dialog_method)

    sleep_calls = []

    async def fake_sleep(duration: float):
        sleep_calls.append(duration)

    monkeypatch.setattr(settings_operations.asyncio, "sleep", fake_sleep)

    await settings_operations.validate_visual_crossing_api_key(dialog)

    assert 0.5 in sleep_calls, "Backoff should wait for the first schedule interval"
    assert "Retrying... (2/3)" in dialog.validate_api_key_button.history
    assert api_key not in caplog.text
    assert dialog.validate_api_key_button.enabled is True


@pytest.mark.asyncio
async def test_validate_visual_crossing_api_key_request_error_redacted(monkeypatch, caplog):
    caplog.set_level("INFO")
    api_key = "leaky-key-999"
    dialog = FakeDialog(api_key)

    request = httpx.Request("GET", "https://example.com")
    request_errors = [
        httpx.RequestError("failed to connect", request=request),
        httpx.RequestError("failed to connect", request=request),
        httpx.RequestError("failed to connect", request=request),
    ]
    _patch_async_client(monkeypatch, request_errors)
    monkeypatch.setattr(settings_operations, "_call_dialog_method", _fake_call_dialog_method)

    async def fake_sleep(duration: float):
        return None

    monkeypatch.setattr(settings_operations.asyncio, "sleep", fake_sleep)

    await settings_operations.validate_visual_crossing_api_key(dialog)

    assert dialog.errors, "Expected an error dialog for request failure"
    _, message = dialog.errors[0]
    assert api_key not in message
    assert api_key not in caplog.text
    assert dialog.validate_api_key_button.text == "Validate API Key"
    assert dialog.validate_api_key_button.enabled is True
