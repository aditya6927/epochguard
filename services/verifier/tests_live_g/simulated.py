"""Offline only: real source parsers over synthetic HTTP transports, never origins."""
import json
import os
import httpx
from pydantic import BaseModel, ConfigDict
from typing import Literal

from verifier.contract import SOURCE_URL
from verifier.retrieval import TavilyRetriever, Page
from verifier.multiclaim.contract import PYPI_URL
from verifier.multiclaim.retrieval import PyPIRetriever
from verifier.multiclaim.deployment import TAVILY, ObservedPipeline
from verifier.bounded_prose.qualification import qualification_app


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fault: Literal["none", "timeout", "ambiguous", "pypi-failure", "source-change", "wrong-mode"]


def fixture_app():
    if os.getenv("EPOCHGUARD_TEST_MODE") != "1":
        raise ValueError("offline controls require test mode")
    if any(os.getenv(n) for n in ("TAVILY_API_KEY", "EPOCHGUARD_TAVILY_SECRET_FILE",
                                  "EPOCHGUARD_RUN_LIVE_004G", "EPOCHGUARD_RUN_LIVE_004E")):
        raise ValueError("offline controls refuse live configuration")
    state = Control(fault="none")

    async def tavily(request):
        assert str(request.url) == "https://api.tavily.com/extract"
        assert json.loads(request.content)["urls"] == [SOURCE_URL]
        if state.fault == "timeout":
            raise httpx.ReadTimeout("simulated")
        version = "3.88.8" if state.fault == "source-change" else "3.88.7"
        content = f"Python Releases for Windows\nLatest Python 3 Release - Python {version}\nStable Releases\n"
        if state.fault == "ambiguous":
            content += "Latest Python 3 Release - Python 3.88.9\n"
        return httpx.Response(200, json={"results": [{"url": SOURCE_URL, "raw_content": content}],
                                        "failed_results": [], "request_id": "simulated-004gl"})

    async def pypi(request):
        assert request.method == "GET" and str(request.url) == PYPI_URL
        return httpx.Response(500) if state.fault == "pypi-failure" else httpx.Response(
            200, json={"info": {"name": "requests", "version": "2.88.7", "yanked": False}})

    class Python:
        async def retrieve(self):
            async with httpx.AsyncClient(transport=httpx.MockTransport(tavily)) as client:
                page = await TavilyRetriever(client=client, api_key="local-fixture-only", timeouts=TAVILY).retrieve()
            return Page(page.url, page.content, page.retrieved_at, page.retrieval_id, "pypi_live") if state.fault == "wrong-mode" else page

    class PyPI:
        async def retrieve(self):
            return await PyPIRetriever(transport=httpx.MockTransport(pypi)).retrieve()

    evidence = ObservedPipeline(Python(), PyPI(), fixture=True)
    app = qualification_app(evidence, simulated=True)

    @app.post("/test/control")
    async def control(value: Control):
        nonlocal state
        if evidence._active:
            raise ValueError("work active")
        state = value
        evidence.records.clear()
        app.state.pipeline.records.clear()
        evidence.preflight_started = False
        for source in (evidence.python, evidence.pypi):
            source.attempted = source.completed = 0
            source.calls.clear()
        return {"simulated_transports": True}

    return app
