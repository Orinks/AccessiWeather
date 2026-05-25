"""Windows activation IPC for duplicate AccessiWeather launches."""

from __future__ import annotations

import contextlib
import json
import logging
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict
from multiprocessing.connection import Client, Listener

from .notification_activation import NotificationActivationRequest

logger = logging.getLogger(__name__)

DEFAULT_PIPE_ADDRESS = r"\\.\pipe\AccessiWeather.SingleInstance.Activation"
PIPE_AUTHKEY = b"AccessiWeather.SingleInstance.v1"


class ActivationIpcServer:
    """Background named-pipe server for duplicate-launch activation requests."""

    def __init__(
        self,
        *,
        address: str = DEFAULT_PIPE_ADDRESS,
        authkey: bytes = PIPE_AUTHKEY,
    ) -> None:
        """Initialize the server with a named-pipe address and auth key."""
        self.address = address
        self.authkey = authkey
        self._listener = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self, on_request: Callable[[NotificationActivationRequest], None]) -> bool:
        """Start listening for activation requests."""
        if sys.platform != "win32":
            return False
        if self._thread and self._thread.is_alive():
            return True

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(on_request,),
            name="AccessiWeatherActivationIPC",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop listening for activation requests."""
        self._stop.set()
        listener = self._listener
        if listener is not None:
            with contextlib.suppress(Exception):
                listener.close()
        self._listener = None

    def _run(self, on_request: Callable[[NotificationActivationRequest], None]) -> None:
        try:
            listener = Listener(self.address, family="AF_PIPE", authkey=self.authkey)
        except Exception as exc:
            logger.warning("Failed to start activation IPC listener: %s", exc)
            return

        self._listener = listener
        logger.info("Started AccessiWeather activation IPC listener")
        try:
            while not self._stop.is_set():
                try:
                    connection = listener.accept()
                except (EOFError, OSError):
                    if not self._stop.is_set():
                        logger.debug("Activation IPC listener stopped unexpectedly", exc_info=True)
                    break
                except Exception:
                    if not self._stop.is_set():
                        logger.debug("Failed to accept activation IPC connection", exc_info=True)
                    continue

                with contextlib.closing(connection):
                    request = _receive_activation_request(connection)
                    if request is not None:
                        on_request(request)
        finally:
            with contextlib.suppress(Exception):
                listener.close()
            if self._listener is listener:
                self._listener = None


def send_activation_request(
    request: NotificationActivationRequest,
    *,
    address: str = DEFAULT_PIPE_ADDRESS,
    authkey: bytes = PIPE_AUTHKEY,
) -> bool:
    """Send an activation request to the primary instance over a Windows named pipe."""
    if sys.platform != "win32":
        return False

    try:
        connection = Client(address, family="AF_PIPE", authkey=authkey)
        with contextlib.closing(connection):
            payload = json.dumps(asdict(request)).encode("utf-8")
            connection.send_bytes(payload)
        return True
    except Exception as exc:
        logger.info("Activation IPC send failed; falling back to window lookup: %s", exc)
        return False


def _receive_activation_request(connection) -> NotificationActivationRequest | None:
    """Receive and validate an activation request from an IPC connection."""
    try:
        payload = json.loads(connection.recv_bytes().decode("utf-8"))
        return NotificationActivationRequest(
            kind=payload.get("kind", ""),
            alert_id=payload.get("alert_id"),
        )
    except Exception as exc:
        logger.warning("Ignoring invalid activation IPC request: %s", exc)
        return None
