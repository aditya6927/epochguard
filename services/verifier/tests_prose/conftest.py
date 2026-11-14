import socket

import pytest


@pytest.fixture(autouse=True)
def no_egress(monkeypatch):
    original = socket.socket.connect

    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original(sock, address)  # Windows asyncio's self-pipe
        raise AssertionError("004F offline test attempted external access")

    monkeypatch.setattr(socket.socket, "connect", local_only)
    for name in ("GEMINI_API_KEY", "TAVILY_API_KEY", "EPOCHGUARD_ALLOW_MODEL_CALLS"):
        monkeypatch.delenv(name, raising=False)
