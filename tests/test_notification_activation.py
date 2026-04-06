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
