"""A provider that keeps a connection alive must not stall a request past its deadline."""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from openai import OpenAI

from accessiweather.ai_explainer_models import RequestTimeoutError
from accessiweather.ai_provider import RequestDeadline


class _KeepAliveHandler(BaseHTTPRequestHandler):
    """Mimic a busy model: 200 headers, then whitespace forever, never a body."""

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            for _ in range(200):
                self.wfile.write(b" ")
                self.wfile.flush()
                time.sleep(0.1)
        except OSError:
            pass

    def log_message(self, *args):
        pass


@pytest.fixture
def stalling_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _KeepAliveHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


def test_deadline_cuts_off_keep_alive_stall_and_client_is_replaceable(stalling_server):
    # The per-read timeout never fires because bytes keep arriving.
    client = OpenAI(base_url=stalling_server, api_key="test", timeout=5.0, max_retries=0)
    started = time.monotonic()
    with pytest.raises(RequestTimeoutError), RequestDeadline(client, seconds=0.5):
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}])
    assert time.monotonic() - started < 3
    assert client.is_closed()


def test_deadline_is_silent_when_the_call_finishes_in_time():
    class _Client:
        closed = False

        def close(self):
            self.closed = True

    client = _Client()
    with RequestDeadline(client, seconds=5):
        pass
    time.sleep(0.05)
    assert client.closed is False
