import asyncio

import httpx
import pytest

from verifier.multiclaim.deployment import (CANARY, TAVILY, WORK_SECONDS, BudgetedSource,
                                          ObservedPipeline, live_app, live_key)
from verifier.multiclaim.demo import scenario, make_request


def authorized(monkeypatch, tmp_path):
    path = tmp_path / "key"
    path.write_text("local-test-placeholder-only")
    monkeypatch.setenv("EPOCHGUARD_RUN_LIVE_004E", "1")
    monkeypatch.setenv("EPOCHGUARD_004E_PROFILE", "live")
    monkeypatch.setenv("EPOCHGUARD_TAVILY_SECRET_FILE", str(path))
    return path


@pytest.mark.parametrize("fault", ["opt-in", "profile", "key", "malformed", "oversized",
    "TAVILY_API_KEY", "EPOCHGUARD_TEST_MODE", "EPOCHGUARD_TEST_TAVILY_ENDPOINT",
    "EPOCHGUARD_004C_FIXTURE_CASE", "EPOCHGUARD_TIMEOUT_PROFILE",
    "EPOCHGUARD_RETRIEVAL_TIMEOUT_SECONDS", "EPOCHGUARD_SOURCE_URL", "EPOCHGUARD_POLICY",
    "EPOCHGUARD_PYPI_URL", "EPOCHGUARD_TAVILY_ENDPOINT", "EPOCHGUARD_PYPI_PACKAGE"])
def test_startup_rejects_unsafe_configuration(monkeypatch, tmp_path, fault):
    path = authorized(monkeypatch, tmp_path)
    if fault == "opt-in":
        monkeypatch.delenv("EPOCHGUARD_RUN_LIVE_004E")
    elif fault == "profile":
        monkeypatch.setenv("EPOCHGUARD_004E_PROFILE", "other")
    elif fault == "key":
        path.unlink()
    elif fault in {"malformed", "oversized"}:
        path.write_text("a b" if fault == "malformed" else "x" * 300)
    else:
        monkeypatch.setenv(fault, "PRIVATE_CONFIGURATION_SENTINEL")
    with pytest.raises(ValueError) as error:
        live_key()
    assert "PRIVATE_CONFIGURATION_SENTINEL" not in str(error.value) and str(path) not in str(error.value)


def test_factory_trust_and_deadlines(monkeypatch, tmp_path):
    authorized(monkeypatch, tmp_path)
    app = live_app()  # constructing an app never calls sources
    pipeline = app.state.pipeline
    assert pipeline.fixture is False and pipeline.max_requests == 1
    assert pipeline.work_seconds == WORK_SECONDS == 26
    assert TAVILY.tavily_api_seconds == 19 < TAVILY.retrieval_seconds == 20
    assert pipeline.python.source.endpoint == "https://api.tavily.com/extract"
    assert pipeline.python.source.client is None and pipeline.pypi.source.transport is None
    assert pipeline.pypi.source.timeout_seconds == 4
    assert not pipeline.records and pipeline.python.attempted == pipeline.pypi.attempted == 0


def test_negative_canary_and_fixture_cannot_authorize_live():
    async def run():
        original, request = scenario("A")
        pipeline = ObservedPipeline(*original.sources.values(), fixture=False)
        for _ in range(20):
            canary = await pipeline.verify(make_request(CANARY))
        assert canary.verdict == "INSUFFICIENT" and not canary.claims
        assert not pipeline.records
        assert pipeline.python.attempted == pipeline.pypi.attempted == 0
        result = await pipeline.verify(request)
        assert result.verdict == "INSUFFICIENT" and all(not c.evidence for c in result.claims)
        assert pipeline.python.attempted == pipeline.pypi.attempted == 1
        with pytest.raises(Exception):
            await pipeline.preflight()
        with pytest.raises(Exception):
            await pipeline.preflight()  # one-shot even after failure
    asyncio.run(run())


def test_budget_and_cancellation_release_resources():
    async def run():
        class Source:
            async def retrieve(self):
                await asyncio.sleep(10)
        source = BudgetedSource(Source(), "python")
        for _ in range(3):
            task = asyncio.create_task(source.retrieve())
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        with pytest.raises(ValueError):
            await source.retrieve()
        assert source.attempted == 3 and source.completed == 0 and len(source.calls) == 3
        assert all(c["failure"] == "cancelled" for c in source.calls)
        original, request = scenario("A")
        pipeline = ObservedPipeline(Source(), list(original.sources.values())[1])
        task = asyncio.create_task(pipeline.verify(request))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert pipeline._active == 0
    asyncio.run(run())


def test_shared_timeout_is_unavailable():
    async def run():
        class Slow:
            async def retrieve(self):
                await asyncio.sleep(1)
        original, request = scenario("A")
        pipeline = ObservedPipeline(Slow(), list(original.sources.values())[1])
        pipeline.work_seconds = .02
        result = await pipeline.verify(request)
        assert result.verdict == "INSUFFICIENT" and pipeline._active == 0
        assert all(c.reason_code == "RETRIEVAL_TIMEOUT" for c in result.claims)
    asyncio.run(run())


@pytest.mark.parametrize("fault", ["tavily-timeout", "tavily-401", "tavily-429", "tavily-500",
    "pypi-timeout", "pypi-json", "pypi-identity", "pypi-source", "credentials", "network"])
def test_simulated_transports_fail_closed(monkeypatch, fault):
    from tests_live.simulated import fault_app

    async def run():
        monkeypatch.setenv("EPOCHGUARD_TEST_MODE", "1")
        app = fault_app()
        _, request = scenario("A")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            await client.post("/test/control", json={"fault": fault})
            response = await client.post("/v1/verify/multiclaim", json=request.model_dump(mode="json"))
            assert response.status_code == 200 and response.json()["verdict"] == "INSUFFICIENT"
            report = (await client.get("/qualification/report")).json()
            assert report["fixture"] is True
            assert all(s["attempted"] == 1 for s in report["sources"].values())
    asyncio.run(run())


def test_preflight_one_shot_metadata_and_headers(monkeypatch):
    from tests_live.simulated import fault_app
    from tests_live.runner import versions, older

    async def run():
        monkeypatch.setenv("EPOCHGUARD_TEST_MODE", "1")
        app = fault_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            value = (await client.post("/qualification/preflight", headers={"X-EpochGuard-Source": "live"})).json()
            assert versions(value, True) == ["3.88.7", "2.88.7"]
            assert older("3.88.7") == "3.88.6" and older("3.88.0") == "3.87.0"
            assert "raw_content" not in str(value) and "content_sha256" in str(value)
            assert (await client.post("/qualification/preflight")).status_code == 503
            with pytest.raises(ValueError):
                versions(value, False)
            pipeline = app.state.pipeline
            assert pipeline.python.attempted == pipeline.pypi.attempted == 1
    asyncio.run(run())


def test_runner_total_deadline_cancels_slow_body(monkeypatch):
    from tests_live import runner

    closed, calls = [], []
    original_client, original_timeout = httpx.AsyncClient, asyncio.timeout

    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{"
            await asyncio.sleep(1)
            yield b"}"

        async def aclose(self):
            closed.append(True)

    async def transport(request):
        calls.append(str(request.url))
        return httpx.Response(200, stream=Slow())

    def client(**kwargs):
        assert kwargs == {"timeout": 52, "trust_env": False, "follow_redirects": False}
        return original_client(transport=httpx.MockTransport(transport), **kwargs)

    def short_deadline(seconds):
        assert seconds == 52
        return original_timeout(.05)  # accelerate the wall clock boundary

    monkeypatch.setattr(runner.httpx, "AsyncClient", client)
    monkeypatch.setattr(runner.asyncio, "timeout", short_deadline)
    with pytest.raises(TimeoutError):
        runner.call("ingress", 8082, "GET", "/ready")
    assert len(calls) == 1 and closed == [True]


def test_runner_preserves_case_failures_without_retry_or_raw_errors(monkeypatch):
    from tests_live import runner

    calls = []
    monkeypatch.setattr(runner, "versions", lambda *_: ["3.88.7", "2.88.7"])

    def broken(text, *args, **kwargs):
        calls.append((text, kwargs.get("host")))
        raise httpx.ReadError("PRIVATE_TRANSPORT_DETAIL")

    monkeypatch.setattr(runner, "infer", broken)
    rows = runner.client_cases({}, True)
    assert len(rows) == len(calls) == 5
    assert all(r["status"] is None and r["answer_released"] is None and not r["expectation_met"] for r in rows)
    assert all(r["failure_category"] == "transport_unavailable" for r in rows)
    assert "PRIVATE_TRANSPORT_DETAIL" not in str(rows)
