import asyncio
from datetime import timedelta
import json
import logging

import httpx
import pytest

from verifier import diagnostics
from verifier.app import create_app
from verifier.policy import claim_text, verify
from verifier.retrieval import RetrievalFailure, TavilyRetriever
from verifier.settings import TimeoutSettings
from tests.test_verifier import NOW, PRIMARY, Pages, request

SECRET = "PRIVATE_TEST_SENTINEL"


def events(caplog):
    records = [r for r in caplog.records if r.name == diagnostics.LOGGER.name]
    # The default Python/uvicorn formatter must emit the fields as well.
    for record in records:
        encoded = json.loads(record.getMessage())
        assert encoded["event"] == record.event
        assert encoded["category"] == record.category
        assert len(record.getMessage()) < 200
        assert SECRET not in record.getMessage()
        assert "Python" not in record.getMessage()
    return records


@pytest.mark.parametrize("status,category", [
    (401, "tavily_http_unauthorized"), (429, "tavily_http_rate_limited"),
    (500, "tavily_http_server_error"), (503, "tavily_http_server_error"),
    (302, "tavily_http_failure"), (403, "tavily_http_failure"),
])
def test_tavily_http_diagnostics_are_numeric_and_body_free(status, category, caplog):
    async def run():
        calls = []

        async def handler(req):
            calls.append(1)
            return httpx.Response(status, text=SECRET, headers={"X-Private": SECRET})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await verify(request(claim_text("3.88.7")), TavilyRetriever(client=client, api_key=SECRET))
        assert result.reason_code == "RETRIEVAL_FAILURE" and result.verdict == "INSUFFICIENT"
        assert SECRET not in result.model_dump_json() and result.evidence == []
        assert calls == [1]

    asyncio.run(run())
    record, = events(caplog)
    assert (record.event, record.category, record.http_status) == ("retrieval_failure", category, status)


@pytest.mark.parametrize("mode,category,reason", [
    ("timeout", "tavily_timeout", "RETRIEVAL_TIMEOUT"),
    ("transport", "tavily_request_failure", "RETRIEVAL_FAILURE"),
    ("malformed", "invalid_evidence", "RETRIEVAL_FAILURE"),
    ("duplicate", "invalid_evidence", "RETRIEVAL_FAILURE"),
    ("partial", "invalid_evidence", "RETRIEVAL_FAILURE"),
    ("ambiguous", "ambiguous_evidence", "RETRIEVAL_FAILURE"),
    ("credentials", "retrieval_credentials_unavailable", "RETRIEVAL_FAILURE"),
])
def test_retrieval_failure_classes(mode, category, reason, caplog):
    async def run():
        async def handler(req):
            if mode == "timeout":
                raise httpx.ReadTimeout(SECRET)
            if mode == "transport":
                raise httpx.ConnectError(SECRET)
            if mode == "duplicate":
                return httpx.Response(200, text='{"results":[],"results":[]}')
            if mode == "partial":
                return httpx.Response(200, json={"failed_results": [{"error": SECRET}]})
            if mode == "ambiguous":
                return httpx.Response(200, json={"failed_results": [], "results": []})
            return httpx.Response(200, text=SECRET)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await verify(request(claim_text("3.88.7")), TavilyRetriever(
                client=client, api_key="" if mode == "credentials" else SECRET))
        assert result.reason_code == reason and result.evidence == []

    asyncio.run(run())
    record, = events(caplog)
    assert record.category == category
    if mode in {"malformed", "duplicate", "partial", "ambiguous"}:
        assert record.http_status == 200


@pytest.mark.parametrize("source,category,reason", [
    (Pages(SECRET), "invalid_evidence", "INSUFFICIENT_EVIDENCE"),
    (Pages(PRIMARY + "\nLatest Python 3 Release - Python 3.88.8\n" + SECRET), "ambiguous_evidence", "AMBIGUOUS_EVIDENCE"),
    (Pages(observed=NOW - timedelta(seconds=61)), "stale_observation", "STALE_OBSERVATION"),
])
def test_policy_evidence_failures(source, category, reason, caplog):
    result = asyncio.run(verify(request(claim_text("3.88.7")), source, clock=lambda: NOW))
    assert result.reason_code == reason and result.verdict == "INSUFFICIENT"
    record, = events(caplog)
    assert record.category == category


def test_other_unavailable_is_allowlisted(caplog):
    class Failed:
        async def retrieve(self):
            raise RetrievalFailure(SECRET, category=SECRET, status=999)

    result = asyncio.run(verify(request(claim_text("3.88.7")), Failed()))
    assert result.reason_code == "RETRIEVAL_FAILURE"
    record, = events(caplog)
    assert record.category == "verification_unavailable" and not hasattr(record, "http_status")


@pytest.mark.parametrize("timeout", [False, True])
def test_service_failure_and_deadline_keep_public_reason(timeout, caplog):
    class Failed:
        async def retrieve(self):
            if timeout:
                await asyncio.sleep(10)
            raise RuntimeError(SECRET)

    async def run():
        budgets = TimeoutSettings(tavily_api_seconds=1, retrieval_seconds=1.01, verification_seconds=1.02)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(Failed(), timeouts=budgets)),
                                     base_url="http://verifier") as client:
            result = await client.post("/v1/verify", json=request(claim_text("3.88.7")).model_dump(mode="json"))
        assert result.status_code == 200 and result.json()["reason_code"] == "VERIFIER_ERROR"
        assert SECRET not in result.text and result.json()["evidence"] == []

    asyncio.run(run())
    record, = events(caplog)
    assert record.category == ("verification_timeout" if timeout else "verification_unavailable")


def test_broken_logging_handler_cannot_change_policy():
    class Broken(logging.Handler):
        def emit(self, record):
            raise RuntimeError(SECRET)

    handler = Broken()
    diagnostics.LOGGER.addHandler(handler)
    try:
        for version, expected in [("3.88.7", "SUPPORTED"), ("3.88.6", "CONTRADICTED"), ("3.88.8", "INSUFFICIENT")]:
            result = asyncio.run(verify(request(claim_text(version)), Pages(), clock=lambda: NOW))
            assert result.verdict == expected
        result = asyncio.run(verify(request(SECRET), Pages()))
        assert result.reason_code == "UNSUPPORTED_CLAIM"
    finally:
        diagnostics.LOGGER.removeHandler(handler)


def test_unknown_metadata_never_stringified(caplog):
    class Untrusted:
        def __str__(self):
            pytest.fail("untrusted metadata stringified")

    diagnostics.failure(Untrusted(), Untrusted(), Untrusted())
    record, = events(caplog)
    assert (record.event, record.category) == ("verification_failure", "verification_unavailable")


@pytest.mark.parametrize("mode,category,reason", [
    ("socket_timeout", "tavily_timeout", "RETRIEVAL_TIMEOUT"),
    ("total_timeout", "tavily_timeout", "RETRIEVAL_TIMEOUT"),
    ("read_failure", "tavily_request_failure", "RETRIEVAL_FAILURE"),
])
def test_failure_after_headers_retains_status(mode, category, reason, caplog):
    class FailedBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{"
            if mode == "total_timeout":
                await asyncio.sleep(10)
            if mode == "read_failure":
                raise httpx.ReadError(SECRET)
            raise httpx.ReadTimeout(SECRET)

    async def run():
        async def handler(req):
            return httpx.Response(200, stream=FailedBody())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await verify(request(claim_text("3.88.7")), TavilyRetriever(
                client=client, api_key=SECRET, timeouts=TimeoutSettings(
                    tavily_api_seconds=1, retrieval_seconds=1.01, verification_seconds=1.1)))
        assert result.reason_code == reason and result.evidence == []

    asyncio.run(run())
    record, = events(caplog)
    assert (record.category, record.http_status) == (category, 200)
