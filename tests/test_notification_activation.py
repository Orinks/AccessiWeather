from __future__ import annotations

from accessiweather.notification_activation import (
    NotificationActivationRequest,
    consume_activation_request_handoff,
    extract_activation_request_from_argv,
    serialize_activation_request,
    write_activation_request_handoff,
)
from accessiweather.paths import RuntimeStoragePaths


def test_serialize_round_trips_alert_details_request() -> None:
    request = NotificationActivationRequest(
        kind="alert_details",
        alert_id="https://alerts.weather.gov/id/123",
    )

    token = serialize_activation_request(request)
    restored = extract_activation_request_from_argv(["accessiweather.exe", token])

    assert restored == request


def test_extract_activation_request_returns_none_when_missing() -> None:
    restored = extract_activation_request_from_argv(["accessiweather.exe", "--debug"])

    assert restored is None


def test_handoff_file_round_trips_request(tmp_path) -> None:
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    request = NotificationActivationRequest(kind="discussion")

    assert write_activation_request_handoff(runtime_paths, request) is True
    assert runtime_paths.activation_request_file.exists()

    restored = consume_activation_request_handoff(runtime_paths)

    assert restored == request
    assert not runtime_paths.activation_request_file.exists()


def test_unknown_kind_raises_value_error() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unsupported activation kind"):
        NotificationActivationRequest(kind="bogus")


def test_alert_details_without_alert_id_raises_value_error() -> None:
    import pytest

    with pytest.raises(ValueError, match="alert_details activation requires alert_id"):
        NotificationActivationRequest(kind="alert_details")


def test_extract_ignores_unknown_kind_in_token() -> None:
    token = "accessiweather-toast:kind=unknown_kind"
    assert extract_activation_request_from_argv(["app.exe", token]) is None


def test_extract_returns_none_for_alert_details_without_id() -> None:
    token = "accessiweather-toast:kind=alert_details"
    assert extract_activation_request_from_argv(["app.exe", token]) is None


def test_consume_returns_none_when_no_file(tmp_path) -> None:
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    assert consume_activation_request_handoff(runtime_paths) is None


def test_consume_returns_none_on_corrupt_file(tmp_path) -> None:
    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    handoff_file = runtime_paths.activation_request_file
    handoff_file.parent.mkdir(parents=True, exist_ok=True)
    handoff_file.write_text("NOT JSON", encoding="utf-8")

    result = consume_activation_request_handoff(runtime_paths)
    assert result is None
    # File should be cleaned up even on error
    assert not handoff_file.exists()


def test_write_handoff_returns_false_on_permission_error(tmp_path) -> None:
    from unittest.mock import patch

    runtime_paths = RuntimeStoragePaths(config_root=tmp_path / "config")
    request = NotificationActivationRequest(kind="discussion")

    with patch.object(
        type(runtime_paths.activation_request_file.parent), "mkdir", side_effect=PermissionError
    ):
        result = write_activation_request_handoff(runtime_paths, request)
    assert result is False


def test_serialize_generic_fallback() -> None:
    request = NotificationActivationRequest(kind="generic_fallback")
    token = serialize_activation_request(request)
    restored = extract_activation_request_from_argv(["app.exe", token])
    assert restored == request
