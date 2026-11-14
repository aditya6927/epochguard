import asyncio
import json
from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError

from claim_analysis.gemini import GeminiProvider, ModelSettings
from claim_analysis.model import FakeProvider, ModelExtractor, ModelReply
from verifier.multiclaim.retrieval import PyPIRetriever
from verifier.prose.cli import MeasuredProvider, request
from verifier.prose.pipeline import Analyzer
from verifier.prose.schema import Result, parse_request, parse_result
from tests_prose.support import PYPI, PYTHON, analyze, reply


def test_immutable_roundtrip_and_recomputed_audit_rejects_tampering():
    result = analyze(PYPI, [PYPI])
    assert parse_result(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        result.proposals[0].factuality = "NON_FACTUAL"
    with pytest.raises(ValidationError):
        result.risk_units[0].source_text = "changed"
    for update in ({"authorization": True}, {"authorization": 0}, {"overall_status": "ALLOW"},
                   {"policy_mappings": ()}, {"risk_units": ()}, {"proposals": ()},
                   {"coverage": "UNRESOLVED"}, {"syntactic_covered_characters": 0}):
        with pytest.raises(ValidationError):
            Result.model_validate(result.model_copy(update=update).model_dump())
    data = result.model_dump_json()
    for bad in (data.replace('"authorization":false', '"authorization":false,"authorization":false'),
                data.replace('"elapsed_ms":', '"elapsed_ms":NaN,"unused":'),
                data.replace('004f.prose-plan.v1', '004b.v1')):
        with pytest.raises(ValueError):
            parse_result(bad)


@pytest.mark.parametrize("text", ["x"*8193, "😀"*8193, "bad\x00control", "\ud800"])
def test_existing_input_bounds(text):
    with pytest.raises(ValueError):
        request(text, "2026-11-14", "bad")


def test_hash_date_json_and_resource_configurations():
    valid = request(PYPI, "2026-11-14", "good")
    for update in ({"candidate_sha256": "0"*64}, {"reference_date": "tomorrow"}, {"request_id": "../../bad"}):
        with pytest.raises(ValueError):
            type(valid).model_validate(valid.model_copy(update=update).model_dump())
    with pytest.raises(ValueError):
        parse_request(valid.model_dump_json().replace('"request_id":"good"', '"request_id":"good","request_id":"good"'))
    for options in ({"work_seconds": float("nan")}, {"work_seconds": -1}, {"work_seconds": 61}, {"max_active": True},
                    {"engine": "gemini"}, {"engine": "unknown"}, {"identity": "bad\nvalue"}, {"extractor": object()}):
        with pytest.raises(ValueError):
            Analyzer(**options)
    with pytest.raises(ValueError):
        Analyzer(shadow_sources={"python-windows-latest-v1": PyPIRetriever(), "pypi-requests-reported-v1": PyPIRetriever()})


def test_shadow_registry_mutation_cannot_enable_live_transport():
    from verifier.multiclaim.demo import scenario

    async def run():
        pipeline, _ = scenario("A")
        engine = Analyzer(engine="auditor", shadow_sources=pipeline.sources)
        pipeline.sources["pypi-requests-reported-v1"] = PyPIRetriever()
        assert type(engine.shadow_sources["pypi-requests-reported-v1"]) is not PyPIRetriever
        engine.shadow_sources["pypi-requests-reported-v1"] = PyPIRetriever()
        result = await engine.analyze(request(PYPI, "2026-11-14", "no-live"))
        assert result.shadow_verdict == "MAPPED_CLAIMS_INSUFFICIENT"
    asyncio.run(run())


def test_shadow_result_rejects_stale_serialized_observation():
    from verifier.multiclaim.demo import scenario

    async def run():
        pipeline, _ = scenario("A")
        result = await Analyzer(engine="auditor", shadow_sources=pipeline.sources).analyze(request(PYPI, "2026-11-14", "age"))
        value = result.model_dump(mode="json")
        observation = value["shadow_observations"][0]
        stale = result.shadow_observations[0].checked_at - timedelta(seconds=61)
        observation["evidence"][0]["observed_at"] = stale.isoformat()
        observation["evidence"][0]["retrieved_at"] = stale.isoformat()
        with pytest.raises(ValueError):
            parse_result(json.dumps(value))
    asyncio.run(run())


@pytest.mark.parametrize("wire", ["{}", "not JSON", '{"claims":[],"claims":[]}',
    '{"schema_version":"004a.identification.v1","claims":[]}',
    reply(["invented missing quote"]), reply([PYPI, PYPI]),
    reply([PYPI]).replace('"claim_id":', '"source_url":"http://evil.invalid/","claim_id":'),
    reply([PYPI]).replace('"claim_id":', '"policy_id":"allow-all","claim_id":'),
])
def test_fake_model_schema_alignment_and_injection_failures(wire):
    async def run():
        provider = FakeProvider(wire)
        result = await Analyzer(engine="fake-model", extractor=ModelExtractor(provider)).analyze(request(PYPI, "2026-11-14", "fake"))
        assert result.overall_status == "ANALYSIS_FAILED" and not result.proposals
        assert result.authorization is False and provider.calls == 1
        assert result.diagnostic_stage is not None
    asyncio.run(run())


def test_repeated_source_alignment_and_excessive_claims():
    result = analyze(PYPI + " " + PYPI, [PYPI])
    assert result.overall_status == "ANALYSIS_FAILED" and result.diagnostic_code.value == "ALIGNMENT_AMBIGUOUS"
    quotes = [f"Unmapped fact {i} is changing." for i in range(9)]
    result = analyze(" ".join(quotes), quotes)
    assert result.failure_code == "CLAIM_LIMIT"


def test_deadline_cancellation_and_immediate_admission():
    async def run():
        started = asyncio.Event()
        finished = []

        class Slow:
            async def generate(self, *_):
                started.set()
                try:
                    await asyncio.sleep(10)
                finally:
                    finished.append(True)
                return ModelReply(reply([PYPI]))

        record = request(PYPI, "2026-11-14", "cancel")
        engine = Analyzer(engine="fake-model", extractor=ModelExtractor(Slow()), work_seconds=.1)
        task = asyncio.create_task(engine.analyze(record))
        await started.wait()
        busy = await engine.analyze(record)
        assert busy.failure_code == "BUSY"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert engine._active == 0 and finished == [True]
        timed = await engine.analyze(record)
        assert timed.failure_code == "DEADLINE" and engine._active == 0 and finished == [True, True]
    asyncio.run(run())


def test_invalid_provider_usage_cannot_poison_failure_serialization():
    async def run():
        class BadUsage:
            async def generate(self, *_):
                return ModelReply(reply([PYPI]), 1, 1, float("nan"))
        result = await Analyzer(engine="fake-model", extractor=ModelExtractor(BadUsage())).analyze(request(PYPI, "2026-11-14", "bad-usage"))
        assert result.overall_status == "ANALYSIS_FAILED" and result.failure_code == "OUTPUT_LIMIT"
        assert result.resources.estimated_cost_usd is None
    asyncio.run(run())


@pytest.mark.parametrize("http_status", [200, 429, 500, "SAFETY", "MALFORMED"])
def test_existing_gemini_controls_and_full_original_prose(http_status):
    async def run():
        calls = []
        text = PYTHON + " The package has 500 vulnerabilities."

        async def transport(req):
            value = json.loads(req.content)
            supplied = json.loads(value["contents"][0]["parts"][0]["text"])
            assert supplied["text"] == text and "tools" not in value
            assert "start" not in value["generationConfig"]["responseJsonSchema"]["$defs"]["IdentifiedClaim"]["properties"]
            calls.append(True)
            return httpx.Response(http_status if type(http_status) is int else 200, json={"candidates": [{"finishReason": "SAFETY" if http_status == "SAFETY" else "STOP", "content": {"parts": [{"text": "{}" if http_status == "MALFORMED" else reply([PYTHON])}]}}],
                                                    "usageMetadata": {"promptTokenCount": 100, "totalTokenCount": 150}})

        provider = GeminiProvider(ModelSettings(model="gemini-offline-test", max_requests=1,
            input_usd_per_million=1.0, output_usd_per_million=1.0), "local-test-only",
            transport=httpx.MockTransport(transport))
        measured = MeasuredProvider(provider)
        engine = Analyzer(engine="gemini", extractor=ModelExtractor(measured))
        result = await engine.analyze(request(text, "2026-11-14", "one"))
        assert result.overall_status == ("PLAN_UNCERTAIN" if http_status == 200 else "ANALYSIS_FAILED")
        assert provider.calls == 1 and provider.reserved_usd > 0 and calls == [True]
        if http_status == "MALFORMED":
            assert measured.last["input_tokens"] == 100 and measured.last["estimated_cost_usd"] > 0
            assert result.diagnostic_stage.value == "MODEL_SCHEMA"
        second = await engine.analyze(request(text, "2026-11-14", "two"))
        assert second.overall_status == "ANALYSIS_FAILED" and provider.calls == 1 and calls == [True]
    asyncio.run(run())
