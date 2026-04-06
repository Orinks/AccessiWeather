"""Helpers for notification click activation on Windows."""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import asdict, dataclass
from urllib.parse import parse_qs, urlencode

from .paths import RuntimeStoragePaths

logger = logging.getLogger(__name__)

ACTIVATION_PREFIX = "accessiweather-toast:"
_KNOWN_KINDS = {"discussion", "alert_details", "generic_fallback"}


@dataclass(frozen=True)
class NotificationActivationRequest:
    """Structured toast activation request."""

    kind: str
    alert_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in _KNOWN_KINDS:
            raise ValueError(f"Unsupported activation kind: {self.kind}")
        if self.kind == "alert_details" and not self.alert_id:
            raise ValueError("alert_details activation requires alert_id")


def serialize_activation_request(request: NotificationActivationRequest) -> str:
    """Serialize an activation request into a single argv-safe token."""
    payload = {"kind": request.kind}
    if request.alert_id:
        payload["alert_id"] = request.alert_id
    return f"{ACTIVATION_PREFIX}{urlencode(payload)}"


def extract_activation_request_from_argv(
    argv: list[str] | tuple[str, ...],
) -> NotificationActivationRequest | None:
    """Extract the first AccessiWeather activation request token from argv."""
    for arg in argv:
        if not isinstance(arg, str) or not arg.startswith(ACTIVATION_PREFIX):
            continue
        parsed = parse_qs(arg.removeprefix(ACTIVATION_PREFIX), keep_blank_values=False)
        kind = next(iter(parsed.get("kind", [])), None)
        alert_id = next(iter(parsed.get("alert_id", [])), None)
        if kind not in _KNOWN_KINDS:
            return None
        try:
            return NotificationActivationRequest(kind=kind, alert_id=alert_id)
        except ValueError:
            logger.debug("Ignoring invalid activation token: %s", arg)
            return None
    return None


def write_activation_request_handoff(
    runtime_paths: RuntimeStoragePaths,
    request: NotificationActivationRequest,
) -> bool:
    """Write an activation request to the shared runtime handoff file."""
    handoff_file = runtime_paths.activation_request_file
    temp_file = handoff_file.with_suffix(".tmp")
    try:
        handoff_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_text(json.dumps(asdict(request)), encoding="utf-8")
        temp_file.replace(handoff_file)
        return True
    except Exception as exc:
        logger.warning("Failed to write activation handoff: %s", exc)
        with contextlib.suppress(OSError):
            temp_file.unlink()
        return False


def consume_activation_request_handoff(
    runtime_paths: RuntimeStoragePaths,
) -> NotificationActivationRequest | None:
    """Consume the next activation handoff request, deleting the file after read."""
    handoff_file = runtime_paths.activation_request_file
    if not handoff_file.exists():
        return None

    try:
        payload = json.loads(handoff_file.read_text(encoding="utf-8"))
        return NotificationActivationRequest(
            kind=payload.get("kind", ""),
            alert_id=payload.get("alert_id"),
        )
    except Exception as exc:
        logger.warning("Failed to consume activation handoff: %s", exc)
        return None
    finally:
        with contextlib.suppress(OSError):
            handoff_file.unlink()
