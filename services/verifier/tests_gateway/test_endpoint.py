import asyncio
import json
from pathlib import Path

import httpx
import pytest

from verifier.multiclaim.app import PATH, create_app, fixture_app
from verifier.multiclaim.coverage import qualify
from verifier.multiclaim.demo import scenario, make_request
from verifier.multiclaim.contract import Result


def conformance():
    for parent in Path(__file__).resolve().parents:
        for candidate in (parent / "tests/conformance", parent / "conformance"):
            if candidate.is_dir():
                return candidate
    raise AssertionError("shared conformance fixtures missing")


def test_shared_conformance_vectors_and_records():
    for row in json.loads((conformance() / "004b-grammar.json").read_text(encoding="utf-8")):
        required, coverage = qualify(row["text"])
        assert coverage.reason_code == row["reason"]
        assert [c.model_dump() for c in required] == row["claims"]
    for case in "ABC":
        Result.model_validate_json((conformance() / f"004b-{case}.json").read_bytes())


@pytest.mark.parametrize("case,expected", [("A", "SUPPORTED"), ("C", "INSUFFICIENT"), ("E", "CONTRADICTED"), ("F", "INSUFFICIENT")])
def test_endpoint_reuses_pipeline(case, expected):
    async def run():
        pipeline, request = scenario(case)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(pipeline)), base_url="http://test") as client:
            response = await client.post(PATH, content=request.model_dump_json(), headers={"content-type": "application/json"})
            assert response.status_code == 200
            result = Result.model_validate_json(response.content)
            assert result.verdict == expected
            assert (await client.get("/health")).status_code == 200
            # The separately composed legacy route still validates 003A requests.
            assert (await client.post("/v1/verify", json=request.model_dump(mode="json"))).status_code == 422
    asyncio.run(run())


@pytest.mark.parametrize("mode,status", [("large", 413), ("format", 415), ("encoding", 415),
                                        ("duplicate", 422), ("extra", 422), ("hash", 200),
                                        ("empty", 200), ("malformed", 422), ("mode-field", 422)])
def test_invalid_endpoint_inputs_are_sanitized(mode, status, caplog):
    async def run():
        pipeline, request = scenario("A")
        payload = request.model_dump(mode="json")
        headers = {"content-type": "application/json"}
        if mode == "large":
            data = b"PRIVATE_SENTINEL" * 5000
        elif mode == "duplicate":
            data = '{"request_id":"PRIVATE_SENTINEL","request_id":"b"}'
        elif mode == "malformed":
            data = "PRIVATE_SENTINEL"
        else:
            if mode == "extra":
                payload["decision"] = "PRIVATE_SENTINEL"
            if mode == "mode-field":
                payload["evidence_mode"] = "live"
            if mode == "hash":
                payload["candidate_sha256"] = "0" * 64
            if mode == "empty":
                payload = make_request("").model_dump(mode="json")
            data = json.dumps(payload)
        if mode == "format":
            headers["content-type"] = "text/plain"
        if mode == "encoding":
            headers["content-encoding"] = "gzip"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(pipeline)), base_url="http://test") as client:
            response = await client.post(PATH, content=data, headers=headers)
        assert response.status_code == status
        if status == 200:
            assert response.json()["verdict"] == "INSUFFICIENT"
        else:
            assert "PRIVATE_SENTINEL" not in response.text
        assert all(s.calls == 0 for s in pipeline.sources.values())
    asyncio.run(run())
    assert "PRIVATE_SENTINEL" not in caplog.text


def test_disconnect_cancels_work_and_releases_pipeline():
    async def run():
        entered, cancelled = asyncio.Event(), asyncio.Event()
        pipeline, request = scenario("A")
        async def stalled():
            entered.set()
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.set()
        pipeline.sources["python-windows-latest-v1"].retrieve = stalled
        app = create_app(pipeline)
        first = True
        async def receive():
            nonlocal first
            if first:
                first = False
                return {"type": "http.request", "body": request.model_dump_json().encode(), "more_body": False}
            await entered.wait()
            return {"type": "http.disconnect"}
        sent = []
        async def send(message):
            sent.append(message)
        scope = {"type": "http", "path": PATH, "method": "POST", "headers": [(b"content-type", b"application/json")], "query_string": b"", "http_version": "1.1", "scheme": "http", "server": ("test", 80)}
        async with asyncio.timeout(1):
            await app(scope, receive, send)
        assert cancelled.is_set() and pipeline._active == 0 and not sent
    asyncio.run(run())


@pytest.mark.parametrize("enabled,case", [(False, "A"), (True, "unknown")])
def test_fixture_startup_is_explicit(monkeypatch, enabled, case):
    monkeypatch.setenv("EPOCHGUARD_TEST_MODE", "1" if enabled else "0")
    monkeypatch.setenv("EPOCHGUARD_004C_FIXTURE_CASE", case)
    with pytest.raises(ValueError):
        fixture_app()


@pytest.mark.parametrize("mode,status", [("chunked", 413), ("deadline", 408)])
def test_body_receipt_bounds_before_json_parsing(mode, status):
    async def run():
        pipeline, _ = scenario("A")
        app = create_app(pipeline)
        sent, chunks = [], 0
        async def receive():
            nonlocal chunks
            chunks += 1
            if mode == "deadline":
                await asyncio.sleep(10)
            return {"type": "http.request", "body": b"x" * 40000, "more_body": True}
        async def send(message):
            sent.append(message)
        scope = {"type": "http", "path": PATH, "method": "POST", "headers": [], "query_string": b""}
        async with asyncio.timeout(3):
            await app(scope, receive, send)
        assert sent[0]["status"] == status
        assert chunks == (2 if mode == "chunked" else 1)
        assert all(s.calls == 0 for s in pipeline.sources.values())
    asyncio.run(run())
