import socket
import pytest

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    connect = socket.socket.connect
    def denied(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(sock, address)
        raise AssertionError("real network disabled")
    monkeypatch.setattr(socket.socket, "connect", denied)
    for name in ("TAVILY_API_KEY", "GEMINI_API_KEY", "EPOCHGUARD_ALLOW_MODEL_CALLS"):
        monkeypatch.delenv(name, raising=False)
