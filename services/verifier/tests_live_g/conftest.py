"""No credentials or external sockets in qualification regression tests."""
import os
import socket
import sys
from pathlib import Path
import pytest

root = next((p for p in Path(__file__).resolve().parents if (p / "tests/boundedproselive").exists()), None)
if root is not None:
    sys.path.insert(0, str(root / "tests"))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    original = socket.socket.connect

    def denied(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original(sock, address)
        raise AssertionError("004G-L tests attempted external network")

    monkeypatch.setattr(socket.socket, "connect", denied)
    for name in list(os.environ):
        if name.startswith("EPOCHGUARD_") or name in {"TAVILY_API_KEY", "GEMINI_API_KEY"}:
            monkeypatch.delenv(name, raising=False)
