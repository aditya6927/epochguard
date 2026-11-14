import socket

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original = socket.socket.connect

    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original(sock, address)
        raise AssertionError("004E unit test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", local_only)
    for name in list(__import__("os").environ):
        if name.startswith("EPOCHGUARD_") or name in {"TAVILY_API_KEY", "GEMINI_API_KEY"}:
            monkeypatch.delenv(name, raising=False)
