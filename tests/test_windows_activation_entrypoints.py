from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

from accessiweather.notification_activation import (
    NotificationActivationRequest,
    serialize_activation_request,
)


def test_main_entrypoint_forwards_activation_request(monkeypatch) -> None:
    main_module = importlib.import_module("accessiweather.main")

    request = NotificationActivationRequest(kind="discussion")
    token = serialize_activation_request(request)
    monkeypatch.setattr(sys, "argv", ["accessiweather", token])
    monkeypatch.setattr(main_module, "setup_logging", lambda debug=False: None)

    with patch("accessiweather.app.main") as mock_app_main:
        main_module.main()

    assert mock_app_main.call_args.kwargs["activation_request"] == request


def test_python_m_entrypoint_forwards_activation_request(monkeypatch) -> None:
    module_entry = importlib.import_module("accessiweather.__main__")
    main_module = importlib.import_module("accessiweather.main")

    request = NotificationActivationRequest(kind="discussion")
    token = serialize_activation_request(request)
    monkeypatch.setattr(sys, "argv", ["accessiweather", token])
    monkeypatch.setattr(main_module, "setup_logging", lambda debug=False: None)

    with patch("accessiweather.app.main") as mock_app_main:
        module_entry.main()

    assert mock_app_main.call_args.kwargs["activation_request"] == request
