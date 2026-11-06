import asyncio
import json

import httpx
import pytest

from verifier.app import create_app
from verifier.policy import claim_text
from verifier.retrieval import TavilyRetriever
from verifier.settings import TimeoutSettings
from tests.test_verifier import PRIMARY, request


@pytest.mark.parametrize("values", [
    {"retrieval_seconds": 0}, {"retrieval_seconds": -1}, {"retrieval_seconds": 61},
    {"retrieval_seconds": float("nan")}, {"retrieval_seconds": float("inf")},
    {"verification_seconds": 66}, {"verification_seconds": 4},
    {"tavily_api_seconds": 0.9}, {"tavily_api_seconds": 60},
    {"tavily_api_seconds": 4}, {"verification_seconds": "unbounded"},
])
def test_invalid_timeout_values(values):
    with pytest.raises(ValueError):
        TimeoutSettings(**values)


def test_trusted_environment_profiles_and_overrides(monkeypatch):
    for variable in ["EPOCHGUARD_TIMEOUT_PROFILE", "EPOCHGUARD_TAVILY_API_TIMEOUT_SECONDS",
                     "EPOCHGUARD_RETRIEVAL_TIMEOUT_SECONDS", "EPOCHGUARD_VERIFICATION_TIMEOUT_SECONDS"]:
        monkeypatch.delenv(variable, raising=False)
    assert TimeoutSettings.from_environment() == TimeoutSettings()
    monkeypatch.setenv("EPOCHGUARD_TIMEOUT_PROFILE", "live")
    assert TimeoutSettings.from_environment().model_dump() == {
        "tavily_api_seconds": 19, "retrieval_seconds": 20, "verification_seconds": 22}
    monkeypatch.setenv("EPOCHGUARD_RETRIEVAL_TIMEOUT_SECONDS", "21")
    assert TimeoutSettings.from_environment().retrieval_seconds == 21
    monkeypatch.setenv("EPOCHGUARD_VERIFICATION_TIMEOUT_SECONDS", "21")
    with pytest.raises(ValueError):
        create_app()
    monkeypatch.setenv("EPOCHGUARD_TIMEOUT_PROFILE", "client-selected")
    with pytest.raises(ValueError):
        TimeoutSettings.from_environment()


def test_live_budgets_propagate_through_fastapi_and_httpx(monkeypatch):
    budgets = TimeoutSettings(tavily_api_seconds=19, retrieval_seconds=20, verification_seconds=22)
    seen = []

    async def run():
        async def handler(req):
            assert json.loads(req.content)["timeout"] == 19
            assert set(req.extensions["timeout"].values()) == {20}
            return httpx.Response(200, json={"results": [{"url": "https://www.python.org/downloads/windows/",
                                                          "raw_content": PRIMARY}],
                                             "failed_results": [], "request_id": "timeout-propagation"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            def factory(*, timeouts):
                seen.append(timeouts)
                return TavilyRetriever(client=client, api_key="local-fixture-only", timeouts=timeouts)
            monkeypatch.setattr(TavilyRetriever, "from_environment", factory)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(timeouts=budgets)),
                                         base_url="http://verifier") as caller:
                payload = request(claim_text("3.88.7")).model_dump(mode="json")
                response = await caller.post("/v1/verify", json=payload,
                    headers={"X-EpochGuard-Retrieval-Timeout-Seconds": "0.001",
                             "X-EpochGuard-Verification-Timeout-Seconds": "99999"})
                assert response.json()["verdict"] == "SUPPORTED"
                assert seen == [budgets]
                assert (await caller.post("/v1/verify", json={**payload, "timeout": 99999})).status_code == 422
    asyncio.run(run())


def test_fastapi_deadline_cancels_work_and_fails_closed():
    cancelled = []

    class Stalled:
        async def retrieve(self):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)

    async def run():
        budgets = TimeoutSettings(tavily_api_seconds=1, retrieval_seconds=1.01, verification_seconds=1.02)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(Stalled(), timeouts=budgets)),
                                     base_url="http://verifier") as caller:
            async with asyncio.timeout(2):
                response = await caller.post("/v1/verify", json=request(claim_text("3.88.7")).model_dump(mode="json"))
            value = response.json()
            assert value["verdict"] == "INSUFFICIENT" and value["reason_code"] == "VERIFIER_ERROR"
            assert value["evidence"] == [] and cancelled == [True]
    asyncio.run(run())


def test_retrieval_cancellation_propagates_without_a_verdict():
    async def run():
        entered = asyncio.Event()
        cancelled = asyncio.Event()

        async def handler(req):
            entered.set()
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
            return httpx.Response(200)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = TavilyRetriever(client=client, api_key="local-fixture-only")
            task = asyncio.create_task(source.retrieve())
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert cancelled.is_set()
    asyncio.run(run())
