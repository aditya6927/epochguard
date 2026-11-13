import asyncio
import json
import sys

import pytest

from verifier.multiclaim.__main__ import main
from verifier.multiclaim.demo import make_request, pypi_claim
from verifier.multiclaim.live import observe
from verifier.policy import claim_text


def test_cli_demo_and_custom_request(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", ["multiclaim"])
    main()
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(";")[0] for line in lines] == [
        "A: SUPPORTED", "B: CONTRADICTED", "C: INSUFFICIENT", "D: INSUFFICIENT",
        "E: CONTRADICTED", "F: INSUFFICIENT"]
    path = tmp_path / "request.json"
    request = make_request(claim_text("3.88.7") + "\n" + pypi_claim())
    path.write_text(request.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["multiclaim", "--request", str(path), "--json"])
    main()
    record = json.loads(capsys.readouterr().out)
    assert record["result"]["verdict"] == "SUPPORTED"
    assert record["result"]["candidate"] == request.candidate


@pytest.mark.parametrize("content", ['{"request_id":"a","request_id":"b"}', 'PRIVATE_KEY' * 10000,
                                     '{"policy_id":"PRIVATE_KEY"}', '["PRIVATE_KEY"]'])
def test_cli_invalid_input_has_sanitized_diagnostics(monkeypatch, capsys, tmp_path, content):
    path = tmp_path / "request.json"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["multiclaim", "--request", str(path)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert capsys.readouterr().err == "004B input rejected\n"


@pytest.mark.parametrize("source", ["pypi", "python"])
def test_live_probe_requires_optin(monkeypatch, source):
    monkeypatch.delenv("EPOCHGUARD_RUN_LIVE_004B", raising=False)
    with pytest.raises(ValueError, match="opt-in"):
        asyncio.run(observe(source))


def test_live_probe_refuses_fixture_endpoint(monkeypatch):
    monkeypatch.setenv("EPOCHGUARD_RUN_LIVE_004B", "1")
    monkeypatch.setenv("EPOCHGUARD_TEST_TAVILY_ENDPOINT", "http://fixture.invalid/extract")
    with pytest.raises(ValueError, match="override"):
        asyncio.run(observe("python"))
