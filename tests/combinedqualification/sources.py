"""Isolated source composition: existing parsers/pipeline/budgets, no new policy."""
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import time
import httpx
from verifier.contract import SOURCE_URL
from verifier.retrieval import TavilyRetriever, Page
from verifier.multiclaim.retrieval import PyPIRetriever
from verifier.multiclaim.contract import PYPI_URL
from verifier.multiclaim.deployment import ObservedPipeline, TAVILY, PYPI_SECONDS, live_key, CANARY
from verifier.bounded_prose.qualification import ObservedProse
from verifier.bounded_prose.app import create_app
from verifier.multiclaim.app import MultiBound
from verifier.claim_report import from_result
from fastapi.responses import JSONResponse
from .common import read_runtime, live_guards, SOURCE_LIMIT, RUN_SECONDS, runtime_code_hash

PHASE = ContextVar("005e_source_phase", default="verification")


class Ledger:
    def __init__(self, settings):
        self.rates = {"python": Decimal(str(settings.python_request_usd)), "pypi": Decimal(str(settings.pypi_request_usd))}
        self.maximum = Decimal(str(settings.max_source_run_usd))
        self.reserved, self.calls = Decimal(0), []
        self.started = time.monotonic()

    def reserve(self, source):
        # No await before retained reservation. Failed/cancelled work is charged
        # against this planning budget; no refund/reset/retry endpoint exists.
        if (time.monotonic()-self.started >= RUN_SECONDS or
            sum(c["source"] == source for c in self.calls) >= SOURCE_LIMIT or
            self.reserved+self.rates[source] > self.maximum):
            raise ValueError("source reservation refused")
        self.reserved += self.rates[source]
        self.calls.append({"source": source, "phase": PHASE.get(), "reservation_usd": float(self.rates[source])})

    def report(self):
        return {"maximum_calls_per_policy": SOURCE_LIMIT, "maximum_planning_usd": float(self.maximum),
                "reserved_planning_usd": float(self.reserved), "calls": self.calls,
                "count_scope": "application retrieval reservations; not billing or origin-fetch counts"}


class ReservedSource:
    def __init__(self, source, name, ledger):
        self.source, self.name, self.ledger = source, name, ledger

    async def retrieve(self):
        self.ledger.reserve(self.name)
        return await self.source.retrieve()


class CombinedEvidence(ObservedPipeline):
    def __init__(self, python, pypi, runtime):
        self.ledger = Ledger(runtime.settings)
        super().__init__(ReservedSource(python, "python", self.ledger), ReservedSource(pypi, "pypi", self.ledger), fixture=not runtime.live)

    async def preflight(self):
        token = PHASE.set("preflight")
        try:
            return await super().preflight()
        finally:
            PHASE.reset(token)


class CombinedProse(ObservedProse):
    def __init__(self, evidence, runtime):
        super().__init__(evidence, simulated=not runtime.live)
        self.runtime = runtime
        self.reporting_failures = 0

    async def verify(self, request):
        index = len(self.records)
        source_calls_before = len(self.evidence_pipeline.ledger.calls)
        result = await super().verify(request)
        if request.candidate != CANARY:
            self.records[index].update(grammar_reason=result.reason_code,
                source_calls_before=source_calls_before,
                source_calls_after=len(self.evidence_pipeline.ledger.calls))
            try:
                report = from_result(result, profile="live" if self.runtime.live else "fixture")
                self.records[index]["claim_report"] = report.model_dump(mode="json")
            except Exception:
                self.reporting_failures += 1  # Never changes the returned result.
        return result

    def report(self):
        value = super().report()
        value.update(schema_version="005e.verifier.v1", source_budget=self.evidence_pipeline.ledger.report(),
                     reporting_failures=self.reporting_failures, runtime_code_sha256=runtime_code_hash())
        return value


def simulated_sources(runtime):
    # Fixed fault schedule selected only by offline trusted batch configuration.
    # Neither candidate text nor HTTP input can change it or reset a budget.
    counts = {"python": 0, "pypi": 0}

    async def tavily(request):
        assert str(request.url) == "https://api.tavily.com/extract"
        counts["python"] += 1
        n = counts["python"]
        if runtime.batch == "sample-failure" or (runtime.batch == "faults" and n == 2):
            return httpx.Response(503)
        version = "3.88.8" if runtime.batch == "drift" and n > 1 else "3.88.7"
        return httpx.Response(200, json={"results": [{"url": SOURCE_URL, "raw_content":
            f"Python Releases for Windows\nLatest Python 3 Release - Python {version}\nStable Releases\n"}],
            "failed_results": [], "request_id": "simulated-005e"})

    async def pypi(request):
        assert str(request.url) == PYPI_URL
        counts["pypi"] += 1
        if runtime.batch == "faults" and counts["pypi"] == 3:
            return httpx.Response(200, text="synthetic malformed evidence", headers={"Content-Type": "application/json"})
        return httpx.Response(200, json={"info": {"name": "requests", "version": "2.88.7", "yanked": False}})

    class Python:
        async def retrieve(self):
            async with httpx.AsyncClient(transport=httpx.MockTransport(tavily)) as client:
                page = await TavilyRetriever(client=client, api_key="offline-only", timeouts=TAVILY).retrieve()
            mode = "pypi_live" if runtime.batch == "identity" and counts["python"] == 2 else page.retrieval_mode
            stamp = page.retrieved_at-timedelta(seconds=61) if runtime.batch == "clock" and counts["python"] == 2 else page.retrieved_at
            return Page(page.url, page.content, stamp, page.retrieval_id, mode)

    class PyPI:
        async def retrieve(self):
            page = await PyPIRetriever(transport=httpx.MockTransport(pypi), timeout_seconds=PYPI_SECONDS).retrieve()
            url = "https://unexpected.invalid/" if runtime.batch == "identity" and counts["pypi"] == 3 else page.url
            stamp = page.retrieved_at+timedelta(seconds=3) if runtime.batch == "clock" and counts["pypi"] == 3 else page.retrieved_at
            return Page(url, page.content, stamp, page.retrieval_id, page.retrieval_mode)

    return Python(), PyPI()


def create_qualification_app(runtime, python, pypi):
    evidence = CombinedEvidence(python, pypi, runtime)
    pipeline = CombinedProse(evidence, runtime)
    app = create_app(pipeline)
    app.state.pipeline = pipeline
    app.add_middleware(MultiBound, path="/qualification/preflight")

    @app.post("/qualification/preflight")
    async def preflight():
        try:
            return {**await evidence.preflight(), "simulated_transports": not runtime.live}
        except Exception:
            return JSONResponse({"failure": "preflight_unavailable"}, status_code=503)

    @app.get("/qualification/report")
    async def report():
        return pipeline.report()

    return app


def app():
    runtime = read_runtime()
    if runtime.live:
        live_guards()
        # Existing source authorization/override/secret checks remain in force.
        key = live_key()
        python, pypi = TavilyRetriever(api_key=key, timeouts=TAVILY), PyPIRetriever(timeout_seconds=PYPI_SECONDS)
    else:
        python, pypi = simulated_sources(runtime)
    return create_qualification_app(runtime, python, pypi)
