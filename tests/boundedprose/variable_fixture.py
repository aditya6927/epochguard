"""Fixed per-process offline evidence; no HTTP endpoint can alter it."""
import json
import os
from pathlib import Path

import httpx
from verifier.bounded_prose.app import create_app
from verifier.bounded_prose.qualification import ObservedProse
from verifier.multiclaim.pipeline import Pipeline
from verifier.multiclaim.retrieval import PyPIRetriever
from verifier.multiclaim.deployment import CANARY
from verifier.contract import SOURCE_URL
from verifier.multiclaim.contract import PYPI_URL
from verifier.retrieval import TavilyRetriever, Page
from .variable_matrix import Profile, profiles, runtime_hash


def read_profile(path="/run/005h/profile.json"):
    raw = Path(path).read_bytes()
    if len(raw) > 1024:
        raise ValueError("profile bound")
    value = Profile(**json.loads(raw))
    if value not in profiles():
        raise ValueError("unrecognized fixed offline profile")
    return value


def fixture_app(profile):
    counts = {"python": 0, "pypi": 0}

    async def tavily(request):
        assert str(request.url) == "https://api.tavily.com/extract"
        assert json.loads(request.content)["urls"] == [SOURCE_URL]
        counts["python"] += 1
        if profile.fault in ("python-unavailable","source-faults"): return httpx.Response(503)
        version = {"python-leading-zero":"3.01.2", "python-major":"4.0.1"}.get(profile.fault, profile.python)
        content = f"Python Releases for Windows\nLatest Python 3 Release - Python {version}\n"
        if profile.fault == "python-ambiguous": content += "Latest Python 3 Release - Python 3.0.2\n"
        content += "Stable Releases\n"
        return httpx.Response(200, json={"results":[{"url":SOURCE_URL,"raw_content":content}],
                                        "failed_results":[],"request_id":"offline-005h"})

    async def pypi(request):
        assert str(request.url) == PYPI_URL
        counts["pypi"] += 1
        if profile.fault in ("pypi-malformed","source-faults"):
            return httpx.Response(200, content=b"not JSON", headers={"Content-Type":"application/json"})
        version = {"pypi-leading-zero":"00.0.1", "pypi-suffix":"0.0.1rc1", "pypi-numeric":1}.get(profile.fault, profile.pypi)
        return httpx.Response(200, json={"info":{"name":"other" if profile.fault=="pypi-project" else "requests",
            "version":version,"yanked":profile.fault=="pypi-yanked"}})

    class Python:
        async def retrieve(self):
            async with httpx.AsyncClient(transport=httpx.MockTransport(tavily), trust_env=False) as client:
                page = await TavilyRetriever(client=client, api_key="local-fixture-only").retrieve()
            if profile.fault == "python-url":
                return Page("https://unexpected.invalid/", page.content, page.retrieved_at, page.retrieval_id, page.retrieval_mode)
            return page

    class PyPI:
        async def retrieve(self):
            page = await PyPIRetriever(transport=httpx.MockTransport(pypi)).retrieve()
            if profile.fault == "pypi-mode":
                return Page(page.url, page.content, page.retrieved_at, page.retrieval_id, "pypi_live")
            return page

    class Observed(ObservedProse):
        async def verify(self, request):
            index, before = len(self.records), dict(counts)
            result = await super().verify(request)
            if request.candidate != CANARY:
                self.records[index].update(reason=result.reason_code,
                    source_invocations={key:counts[key]-before[key] for key in counts},
                    claim_reasons=[c.reason_code for c in result.verification.claims] if result.verification else [])
            return result

        def report(self):
            return {"fixture":True,"simulated_transports":True,"profile":profile.name,"records":self.records,
                "source_invocations":dict(counts), "active":self.evidence_pipeline._active,
                "runtime_sha256":runtime_hash(Path('/app/verifier'),Path('/app/boundedprose'),Path('/app/gatecompare'))
                    if Path('/app/boundedprose').exists() else None}

    pipeline = Observed(Pipeline(Python(), PyPI(), fixture=True), simulated=True)
    app = create_app(pipeline)
    app.state.pipeline = pipeline

    @app.get("/qualification/report")
    async def report():
        return pipeline.report()
    return app


def app():
    if os.getenv("EPOCHGUARD_TEST_MODE") != "1" or any(os.getenv(name) for name in ("GEMINI_API_KEY", "TAVILY_API_KEY")):
        raise ValueError("offline mode without credentials required")
    return fixture_app(read_profile())
