import sys
from pathlib import Path
import socket
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/"tests"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    connect = socket.socket.connect
    def denied(sock, address):
        # Windows asyncio implements its local wakeup socketpair on loopback.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(sock, address)
        raise AssertionError("005D tests forbid network")
    monkeypatch.setattr(socket.socket, "connect", denied)
