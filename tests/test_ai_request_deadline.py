"""A provider that keeps a connection alive must not stall a request past its deadline."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from openai import OpenAI

from accessiweather.ai_explainer_models import RequestTimeoutError
from accessiweather.ai_provider import RequestDeadline, stream_chat_completion


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


def _chunk(content=None, usage=None, finish=None):
    choices = (
        []
        if content is None and finish is None
        else [
            {"index": 0, "delta": {"content": content} if content else {}, "finish_reason": finish}
        ]
    )
    body = {"id": "c", "object": "chat.completion.chunk", "created": 0, "model": "picked/model"}
    body["choices"] = choices
    if usage:
        body["usage"] = usage
    return f"data: {json.dumps(body)}\n\n".encode()


class _StreamHandler(BaseHTTPRequestHandler):
    """Serve SSE: ``queued`` only pings, ``stalls`` pings after one word, ``slow`` crawls."""

    mode = "queued"

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        try:
            if self.mode in ("queued", "stalls"):
                if self.mode == "stalls":
                    self.wfile.write(_chunk("Clear "))
                for _ in range(200):
                    self.wfile.write(b": OPENROUTER PROCESSING\n\n")
                    self.wfile.flush()
                    time.sleep(0.1)
                return
            for word in ("Clear ", "skies ", "tonight."):
                self.wfile.write(_chunk(word))
                self.wfile.flush()
                time.sleep(0.4)
            self.wfile.write(_chunk(finish="stop"))
            usage = {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
            self.wfile.write(_chunk(usage=usage))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except OSError:
            pass

    def log_message(self, *args):
        pass


def _stream_server(mode):
    handler = type("Handler", (_StreamHandler,), {"mode": mode})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _client(server):
    return OpenAI(
        base_url=f"http://127.0.0.1:{server.server_port}/v1",
        api_key="test",
        timeout=5.0,
        max_retries=0,
    )


def test_stream_drops_a_model_that_never_starts_answering():
    server = _stream_server("queued")
    client = _client(server)
    started = time.monotonic()
    try:
        with pytest.raises(RequestTimeoutError, match="start answering"):
            stream_chat_completion(
                client, model="m", messages=[], first_token_seconds=0.5, stall_seconds=5, seconds=10
            )
    finally:
        server.shutdown()
    assert time.monotonic() - started < 3
    assert client.is_closed()


def test_stream_drops_a_model_that_stops_answering_midway():
    server = _stream_server("stalls")
    client = _client(server)
    started = time.monotonic()
    try:
        with pytest.raises(RequestTimeoutError, match="stopped answering"):
            stream_chat_completion(
                client, model="m", messages=[], first_token_seconds=5, stall_seconds=0.5, seconds=10
            )
    finally:
        server.shutdown()
    assert time.monotonic() - started < 3


def test_stream_keeps_a_model_that_writes_longer_than_the_stall_limit():
    # Each word arrives inside the stall limit, but the whole answer takes longer than it.
    server = _stream_server("slow")
    try:
        result = stream_chat_completion(
            _client(server),
            model="m",
            messages=[],
            first_token_seconds=0.5,
            stall_seconds=0.5,
            seconds=10,
        )
    finally:
        server.shutdown()
    assert result == {
        "content": "Clear skies tonight.",
        "model": "picked/model",
        "finish_reason": "stop",
        "total_tokens": 7,
        "prompt_tokens": 3,
        "completion_tokens": 4,
    }
