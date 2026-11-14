import asyncio
import json
from pathlib import Path
import pytest
import httpx
from verifier.bounded_prose.grammar import parse
from verifier.bounded_prose.contract import Request, Result
from verifier.bounded_prose.pipeline import Pipeline
from verifier.bounded_prose.app import create_app, fixture_app
from verifier.multiclaim.pipeline import Pipeline as EvidencePipeline
from verifier.multiclaim.demo import FixtureSource
from verifier.contract import SOURCE_URL
from verifier.multiclaim.contract import PYPI_URL
from verifier.policy import digest

FIXTURES = next((p / "tests/conformance" for p in Path(__file__).resolve().parents
                 if (p / "tests/conformance").exists()), Path("/app/conformance"))
VECTORS = json.loads((FIXTURES / "004g-grammar.json").read_text())
TEXT = VECTORS[9]["text"]


def request(text=TEXT):
    return Request(request_id="test", candidate=text, candidate_sha256=digest(text))


def pipeline():
    python = FixtureSource(SOURCE_URL, "Python Releases for Windows\nLatest Python 3 Release - Python 3.15.2\nStable Releases\n")
    pypi = FixtureSource(PYPI_URL, '{"info":{"name":"requests","version":"2.34.2","yanked":false}}')
    return Pipeline(EvidencePipeline(python, pypi, fixture=True)), python, pypi


@pytest.mark.parametrize("row", VECTORS)
def test_conformance(row):
    mappings, reason = parse(row["text"])
    assert reason == row["reason"]
    assert [m.model_dump() for m in mappings] == row["mappings"]


@pytest.mark.parametrize("case", "ABC")
def test_shared_contract(case):
    Result.model_validate_json((FIXTURES / f"004g-{case}.json").read_bytes())


@pytest.mark.anyio
async def test_supported_contradicted_unsupported():
    p, a, b = pipeline()
    for text, expected in [(TEXT, "SUPPORTED"), (TEXT.replace("3.15.2", "3.15.1"), "CONTRADICTED")]:
        result = await p.verify(request(text))
        assert result.verification.verdict == expected
        assert len(result.mappings) == len(result.verification.claims) == 2
    for row in VECTORS:
        if row["reason"] != "BOUNDED_GRAMMAR":
            before = a.calls, b.calls
            result = await p.verify(request(row["text"]))
            assert result.coverage == "UNCERTAIN" and result.verification is None
            assert before == (a.calls, b.calls)


@pytest.mark.anyio
@pytest.mark.parametrize("which", [0, 1])
async def test_missing_source(which):
    p, a, b = pipeline()
    (a, b)[which].unavailable = True
    r = await p.verify(request())
    assert r.verification.verdict == "INSUFFICIENT"
    assert len(r.verification.claims) == 2


@pytest.mark.anyio
async def test_cancel_and_admission():
    p, a, _ = pipeline()
    entered = asyncio.Event()
    async def blocked():
        entered.set()
        await asyncio.Event().wait()
    a.retrieve = blocked
    p.evidence_pipeline.max_requests = 1
    task = asyncio.create_task(p.verify(request()))
    await entered.wait()
    r = await p.verify(request())
    assert r.verification.verdict == "INSUFFICIENT"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert p.evidence_pipeline._active == 0


@pytest.mark.anyio
async def test_endpoint_contract_rejection():
    p, _, _ = pipeline()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(p)), base_url="http://test") as client:
        payload = request().model_dump()
        response = await client.post("/v1/verify/prose", json=payload)
        assert response.status_code == 200
        assert Result.model_validate_json(response.content).verification.verdict == "SUPPORTED"
        for mutation in [dict(payload, extraction={}), dict(payload, policy_id="multi-claim-templates-v1"), dict(payload, candidate_sha256="0"*64),dict(payload, timeout=1)]:
            assert (await client.post("/v1/verify/prose", json=mutation)).status_code == 422
        raw = json.dumps(payload)[:-1] + ',"candidate":"other"}'
        assert (await client.post("/v1/verify/prose", content=raw, headers={"content-type":"application/json"})).status_code == 422
        assert (await client.post("/v1/verify/prose", content=b"x"*65537)).status_code == 413


def test_fixture_requires_optin(monkeypatch):
    monkeypatch.delenv("EPOCHGUARD_TEST_MODE", raising=False)
    with pytest.raises(ValueError):
        fixture_app()


def test_live_factory_requires_separate_optin(monkeypatch):
    from verifier.bounded_prose.deployment import live_app
    monkeypatch.delenv("EPOCHGUARD_RUN_LIVE_004G", raising=False)
    with pytest.raises(ValueError, match="004G live opt-in"):
        live_app()
    monkeypatch.setenv("EPOCHGUARD_RUN_LIVE_004G", "1")
    monkeypatch.delenv("EPOCHGUARD_RUN_LIVE_004E", raising=False)
    with pytest.raises(ValueError, match="004E live opt-in"):
        live_app()


@pytest.mark.parametrize("mutation", ["offset", "mapping", "canonical", "omitted", "order", "hash", "coverage", "original"])
def test_outer_tampering(mutation):
    record = json.loads((FIXTURES / "004g-A.json").read_text())
    if mutation == "offset": record["mappings"][0]["start"] += 1
    if mutation == "mapping": record["mappings"][0]["policy_id"] = "pypi-requests-reported-v1"
    if mutation == "canonical": record["mappings"][0]["canonical"] += "Other."
    if mutation == "omitted": record["verification"]["claims"].pop()
    if mutation == "order": record["mappings"].reverse()
    if mutation == "hash": record["candidate_sha256"] = "0"*64
    if mutation == "coverage": record["coverage"] = "UNCERTAIN"
    if mutation == "original": record["candidate"] += "\nUnsupported."
    with pytest.raises(ValueError):
        Result.model_validate_json(json.dumps(record))
