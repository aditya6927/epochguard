import socket
import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    connect = socket.socket.connect
    def denied(sock,address):
        if isinstance(address,tuple) and address[0] in {"127.0.0.1","::1"}:
            return connect(sock,address)
        raise AssertionError("005E offline test attempted external network")
    monkeypatch.setattr(socket.socket,"connect",denied)
    for name in ("GEMINI_API_KEY","TAVILY_API_KEY","EPOCHGUARD_005E_ALLOW_MODEL","EPOCHGUARD_005E_ALLOW_EVIDENCE",
                 "EPOCHGUARD_RUN_LIVE_004E","EPOCHGUARD_RUN_LIVE_004G","EPOCHGUARD_RUN_MODEL_005C"):
        monkeypatch.delenv(name,raising=False)
