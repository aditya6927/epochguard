import socket
import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(sock, address)
        raise AssertionError("unexpected external call")
    monkeypatch.setattr(socket.socket, "connect", local_only)
    for key in ("TAVILY_API_KEY", "GEMINI_API_KEY", "EPOCHGUARD_ALLOW_MODEL_CALLS"):
        monkeypatch.delenv(key, raising=False)
