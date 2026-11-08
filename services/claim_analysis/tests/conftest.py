import socket

import pytest


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    connect = socket.socket.connect
    def forbidden(*args, **kwargs):
        raise AssertionError("offline test attempted network access")
    def local_self_pipe(sock, address):
        # Windows asyncio constructs its socketpair with a loopback connection.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(sock, address)
        return forbidden()
    monkeypatch.setattr(socket.socket, "connect", local_self_pipe)
    monkeypatch.delenv("EPOCHGUARD_ALLOW_MODEL_CALLS", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
