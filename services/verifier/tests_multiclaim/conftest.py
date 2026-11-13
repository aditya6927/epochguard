"""004B acceptance is offline even when operator credentials are present."""

import socket
import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    connect = socket.socket.connect

    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(sock, address)  # Windows asyncio self-pipe.
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", local_only)
    for name in ("TAVILY_API_KEY", "GEMINI_API_KEY", "EPOCHGUARD_ALLOW_MODEL_CALLS"):
        monkeypatch.delenv(name, raising=False)
