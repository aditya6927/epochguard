"""Private test-only source controls. Real parsers, explicitly simulated transports."""
import asyncio
import json
import os
import httpx
from pydantic import BaseModel, ConfigDict
from typing import Literal
from verifier.bounded_prose.app import create_app
from verifier.bounded_prose.pipeline import Pipeline
from verifier.multiclaim.pipeline import Pipeline as EvidencePipeline
from verifier.multiclaim.retrieval import PyPIRetriever
from verifier.retrieval import TavilyRetriever
from verifier.contract import SOURCE_URL
from verifier.multiclaim.contract import PYPI_URL


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fault: Literal["none", "tavily-timeout", "tavily-401", "tavily-429", "tavily-500", "pypi-timeout", "pypi-json", "pypi-identity", "slow", "work-deadline"]


def fixture_app():
    if os.getenv("EPOCHGUARD_TEST_MODE") != "1" or os.getenv("TAVILY_API_KEY"):
        raise ValueError("offline controls require test mode without live credentials")
    state = Control(fault="none")
    counts = {"python": 0, "pypi": 0}

    async def tavily(req):
        assert str(req.url) == "https://api.tavily.com/extract"
        assert json.loads(req.content)["urls"] == [SOURCE_URL]
        counts["python"] += 1
        if state.fault == "work-deadline": await asyncio.sleep(3)
        if state.fault == "slow": await asyncio.sleep(.3)
        if state.fault == "tavily-timeout": raise httpx.ReadTimeout("simulated")
        if state.fault.startswith("tavily-"): return httpx.Response(int(state.fault.split("-")[1]))
        return httpx.Response(200, json={"results": [{"url":SOURCE_URL,"raw_content":"Python Releases for Windows\nLatest Python 3 Release - Python 3.15.2\nStable Releases\n"}],"failed_results":[],"request_id":"simulated-004g"})

    async def pypi(req):
        assert str(req.url) == PYPI_URL
        counts["pypi"] += 1
        if state.fault == "work-deadline": await asyncio.sleep(3)
        if state.fault == "pypi-timeout": raise httpx.ReadTimeout("simulated")
        if state.fault == "pypi-json": return httpx.Response(200, content="invalid")
        return httpx.Response(200,json={"info":{"name":"other" if state.fault=="pypi-identity" else "requests","version":"2.34.2","yanked":False}})

    class Python:
        async def retrieve(self):
            async with httpx.AsyncClient(transport=httpx.MockTransport(tavily)) as client:
                return await TavilyRetriever(client=client, api_key="local-fixture-only").retrieve()
    class PyPI:
        async def retrieve(self):
            return await PyPIRetriever(transport=httpx.MockTransport(pypi)).retrieve()
    evidence = EvidencePipeline(Python(), PyPI(), fixture=True)
    app = create_app(Pipeline(evidence))

    @app.post("/test/control")
    async def control(value: Control):
        nonlocal state
        if evidence._active: raise ValueError("work active")
        state = value
        return {"fixture":True}

    @app.get("/test/report")
    async def report():
        return {"fixture":True,"simulated_transports":True,"active":evidence._active,"source_invocations":dict(counts)}
    return app
