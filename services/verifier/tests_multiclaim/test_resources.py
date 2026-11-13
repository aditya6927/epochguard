import asyncio
from datetime import datetime, timezone
import json

import httpx
import pytest

from claim_analysis.model import ModelExtractor
from verifier.contract import SOURCE_URL
from verifier.policy import claim_text
from verifier.retrieval import TavilyRetriever
from verifier.multiclaim.contract import PYPI_URL
from verifier.multiclaim.demo import PYTHON, PYPI, FixtureSource, make_request, pypi_claim, scenario
from verifier.multiclaim.pipeline import Pipeline
from verifier.multiclaim.retrieval import PyPIRetriever

TEXT = claim_text("3.88.7") + "\n" + pypi_claim()


def test_both_http_clients_in_complete_application():
    async def run():
        seen = []

        async def tavily(req):
            seen.append(str(req.url))
            assert json.loads(req.content)["urls"] == [SOURCE_URL]
            assert b"candidate" not in req.content and TEXT.encode() not in req.content
            return httpx.Response(200, json={"results": [{"url": SOURCE_URL, "raw_content": PYTHON}],
                                             "failed_results": [], "request_id": "offline-http"})

        async def pypi(req):
            seen.append(str(req.url))
            assert req.method == "GET" and req.content == b"" and str(req.url) == PYPI_URL
            assert "authorization" not in req.headers
            return httpx.Response(200, content=PYPI, headers={"Content-Type": "application/json; charset=UTF-8"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(tavily)) as client:
            pipeline = Pipeline(TavilyRetriever(client=client, api_key="local-fixture-only"),
                                PyPIRetriever(transport=httpx.MockTransport(pypi)), fixture=True)
            result = await pipeline.verify(make_request(TEXT))
            assert result.verdict == "SUPPORTED"
            assert seen == ["https://api.tavily.com/extract", PYPI_URL]
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["401", "404", "429", "500", "302", "content-type", "oversized",
                                   "malformed", "duplicate", "timeout", "transport", "slow-body"])
def test_pypi_http_failures_cannot_support(mode):
    async def run():
        seen, closed = [], []

        class Slow(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b"{"
                await asyncio.sleep(1)
                yield b"}"

            async def aclose(self):
                closed.append(True)

        async def handler(req):
            seen.append(req)
            if mode.isdigit():
                return httpx.Response(int(mode), headers={"location": "https://unexpected.invalid/"})
            if mode == "timeout":
                raise httpx.ReadTimeout("PRIVATE_KEY_URL_BODY")
            if mode == "transport":
                raise httpx.ConnectError("PRIVATE_KEY_URL_BODY")
            if mode == "slow-body":
                return httpx.Response(200, stream=Slow(), headers={"content-type": "application/json"})
            content = ("x" * (1024 * 1024 + 1) if mode == "oversized" else "invalid"
                       if mode == "malformed" else '{"info":{},"info":{}}' if mode == "duplicate" else PYPI)
            return httpx.Response(200, content=content,
                                  headers={"content-type": "text/html" if mode == "content-type" else "application/json"})

        pipeline, request = scenario("A")
        pipeline.sources["pypi-requests-reported-v1"] = PyPIRetriever(
            transport=httpx.MockTransport(handler), timeout_seconds=0.02)
        result = await pipeline.verify(request)
        assert result.verdict == "INSUFFICIENT" and len(seen) == 1  # No retries or redirect following.
        assert result.claims[0].verdict == "SUPPORTED" and result.claims[1].evidence == []
        if mode == "slow-body":
            assert closed == [True]
        assert "PRIVATE_KEY" not in result.model_dump_json()
    asyncio.run(run())


@pytest.mark.parametrize("shared", [False, True])
def test_deadline_cancels_remaining_evidence(shared):
    async def run():
        cancelled = []

        class Stalled:
            async def retrieve(self):
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.append(True)

        pipeline = Pipeline(FixtureSource(SOURCE_URL, PYTHON), Stalled(), fixture=True,
                            retrieval_seconds=0.02 if not shared else 0.03,
                            work_seconds=0.1 if not shared else 0.03)
        async with asyncio.timeout(1):
            result = await pipeline.verify(make_request(TEXT))
        assert result.verdict == "INSUFFICIENT" and cancelled == [True]
        assert [c.verdict for c in result.claims] == ["SUPPORTED", "INSUFFICIENT"]
        assert result.claims[1].reason_code == "RETRIEVAL_TIMEOUT"
        assert pipeline._active == 0
    asyncio.run(run())


def test_external_cancellation_propagates_and_frees_admission():
    async def run():
        entered, cancelled = asyncio.Event(), asyncio.Event()

        class Stalled:
            async def retrieve(self):
                entered.set()
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.set()

        pipeline = Pipeline(FixtureSource(SOURCE_URL, PYTHON), Stalled(), fixture=True)
        task = asyncio.create_task(pipeline.verify(make_request(TEXT)))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set() and pipeline._active == 0
        pipeline.sources["pypi-requests-reported-v1"] = FixtureSource(PYPI_URL, PYPI)
        assert (await pipeline.verify(make_request(TEXT))).verdict == "SUPPORTED"
    asyncio.run(run())


def test_model_work_uses_shared_deadline_and_cancels():
    async def run():
        cancelled = []

        class Provider:
            async def generate(self, request, schema):
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.append(True)

        pipeline = Pipeline(FixtureSource(SOURCE_URL, PYTHON), FixtureSource(PYPI_URL, PYPI),
                            fixture=True, work_seconds=0.02, retrieval_seconds=0.01)
        result = await pipeline.verify(make_request(TEXT), extractor=ModelExtractor(Provider()))
        assert result.verdict == "INSUFFICIENT" and result.extraction_status == "FAILED"
        assert result.coverage.reason_code == "EXTRACTION_FAILURE" and cancelled == [True]
        assert all(s.calls == 0 for s in pipeline.sources.values())
    asyncio.run(run())


def test_concurrent_requests_are_bounded_and_results_are_not_shared():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        class Held(FixtureSource):
            def __init__(self):
                super().__init__(SOURCE_URL, PYTHON)
                self.active, self.maximum = 0, 0

            async def retrieve(self):
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                if self.active == 2:
                    entered.set()
                try:
                    await release.wait()
                    return await super().retrieve()
                finally:
                    self.active -= 1

        source = Held()
        pipeline = Pipeline(source, FixtureSource(PYPI_URL, PYPI), fixture=True, max_requests=2)
        tasks = [asyncio.create_task(pipeline.verify(make_request(TEXT, f"request-{i}"))) for i in range(20)]
        await asyncio.wait_for(entered.wait(), 1)
        # Scheduling all tasks means excess requests are rejected immediately, without a waiter queue.
        await asyncio.sleep(0)
        assert sum(t.done() for t in tasks) == 18
        release.set()
        results = await asyncio.gather(*tasks)
        assert source.maximum == 2 and source.calls == 2 and pipeline._active == 0
        assert [r.verdict for r in results].count("SUPPORTED") == 2
        assert all(r.request_id == f"request-{i}" and r.candidate_sha256 == make_request(TEXT).candidate_sha256
                   for i, r in enumerate(results))
        assert all(r.verdict == "INSUFFICIENT" and len(r.claims) == 2 for r in results[2:])
    asyncio.run(run())


@pytest.mark.parametrize("values", [{"max_requests": 0}, {"max_requests": 17}, {"max_requests": True},
                                     {"retrieval_seconds": 0}, {"work_seconds": 0}, {"work_seconds": 61},
                                     {"work_seconds": float("nan")}, {"retrieval_seconds": float("inf")}])
def test_invalid_resource_configuration(values):
    with pytest.raises(ValueError):
        Pipeline(None, None, **values)
