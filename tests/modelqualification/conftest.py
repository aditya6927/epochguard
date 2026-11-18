"""Every 005C offline unit test denies network connections."""
import socket
import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    connect = socket.socket.connect
    def denied(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(sock, address)
        raise AssertionError("005C offline test attempted network access")
    monkeypatch.setattr(socket.socket, "connect", denied)
    for name in ("GEMINI_API_KEY", "TAVILY_API_KEY", "EPOCHGUARD_ALLOW_MODEL_CALLS", "EPOCHGUARD_RUN_MODEL_005C", "EPOCHGUARD_RUN_ANALYSIS_005C"):
        monkeypatch.delenv(name, raising=False)
