"""Trusted 004E composition. Importing this module performs no source requests."""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import time

from fastapi.responses import JSONResponse

from verifier.policy import primary_label
from verifier.retrieval import TavilyRetriever
from verifier.settings import TimeoutSettings
from .app import MultiBound, create_app
from .pipeline import Pipeline
from .policies import pypi_version, reference, validate_page
from .retrieval import PyPIRetriever

# Fixed profile: 19 < 20; sequential 20 + 4 + 2 overhead < Go's 30 seconds.
TAVILY = TimeoutSettings(tavily_api_seconds=19, retrieval_seconds=20, verification_seconds=26)
WORK_SECONDS = 26
PYPI_SECONDS = 4
CANARY = "EpochGuard readiness canary: intentionally outside the trusted claim grammar."


def live_key():
    """Only a bounded runtime secret file. Never echo paths, contents or errors."""
    if os.getenv("EPOCHGUARD_RUN_LIVE_004E") != "1":
        raise ValueError("004E live opt-in required")
    forbidden = ("EPOCHGUARD_TEST_MODE", "EPOCHGUARD_TEST_TAVILY_ENDPOINT",
                 "EPOCHGUARD_004C_FIXTURE_CASE", "TAVILY_API_KEY")
    if any(os.getenv(name) for name in forbidden):
        raise ValueError("004E live source overrides forbidden")
    # No independent override may silently undermine this fixed hierarchy.
    if os.getenv("EPOCHGUARD_004E_PROFILE") != "live" or any(
        name.startswith("EPOCHGUARD_") and any(part in name for part in
            ("TIMEOUT", "POLICY", "SOURCE", "ENDPOINT", "PACKAGE", "_URL"))
        for name in os.environ
    ):
        raise ValueError("004E trusted profile required; overrides forbidden")
    try:
        with Path(os.environ["EPOCHGUARD_TAVILY_SECRET_FILE"]).open("rb") as stream:
            raw = stream.read(259)
        key = raw.decode("ascii").rstrip("\r\n")
        if len(raw) > 258 or not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", key):
            raise ValueError()
    except (OSError, KeyError, UnicodeError, ValueError):
        raise ValueError("004E credential unavailable") from None
    return key


class BudgetedSource:
    """Process-wide no-wait call budget shared by preflight and inference.

    Counts retrieval invocations, not upstream billing/origin fetches. A returned
    Page counts as completed even if the subsequent trusted parser rejects it.
    """
    def __init__(self, source, name):
        self.source, self.name = source, name
        self.attempted = self.completed = 0
        self.calls = []

    async def retrieve(self):
        if self.attempted >= 3:
            raise ValueError("qualification source budget exhausted")
        self.attempted += 1
        row = {"source": self.name, "attempt": self.attempted,
               "started_at": datetime.now(timezone.utc).isoformat(), "completed": False}
        self.calls.append(row)
        started = time.monotonic()
        try:
            page = await self.source.retrieve()
            self.completed += 1
            row["completed"] = True
            return page
        except asyncio.CancelledError:
            row["failure"] = "cancelled"
            raise
        except Exception as error:
            category = getattr(error, "category", "retrieval_unavailable")
            row["failure"] = category if category in {
                "tavily_timeout", "tavily_http_unauthorized", "tavily_http_rate_limited",
                "tavily_http_server_error", "tavily_http_failure", "tavily_request_failure",
                "invalid_evidence", "ambiguous_evidence", "retrieval_unavailable",
                "retrieval_credentials_unavailable"} else "retrieval_unavailable"
            raise
        finally:
            row["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
            row["finished_at"] = datetime.now(timezone.utc).isoformat()


class ObservedPipeline(Pipeline):
    def __init__(self, python, pypi, *, fixture=False):
        self.python = BudgetedSource(python, "python")
        self.pypi = BudgetedSource(pypi, "pypi")
        self.records = []
        self.preflight_started = False
        super().__init__(self.python, self.pypi, fixture=fixture, max_requests=1,
                         work_seconds=WORK_SECONDS, retrieval_seconds=20.5)

    async def verify(self, request, **kwargs):
        # Routine negative readiness must not consume paid budget OR telemetry
        # slots. It still runs the actual grammar and returns no release verdict.
        if request.candidate == CANARY:
            return await super().verify(request, **kwargs)
        # Bounded telemetry; exhausting it refuses work, never drops enforcement.
        if len(self.records) >= 16:
            raise ValueError("qualification record budget exhausted")
        row = {"candidate_sha256": request.candidate_sha256,
               "started_at": datetime.now(timezone.utc).isoformat()}
        self.records.append(row)
        started = time.monotonic()
        try:
            result = await super().verify(request, **kwargs)
            row.update(verdict=result.verdict, claims=[{
                "policy_id": c.claim.policy_id, "claimed_version": c.claim.version,
                "verdict": c.verdict, "reason_code": c.reason_code,
                "evidence": [e.model_dump(mode="json") for e in c.evidence]
            } for c in result.claims])
            return result
        finally:
            row["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
            row["finished_at"] = datetime.now(timezone.utc).isoformat()

    async def preflight(self):
        if self.preflight_started or self._active:
            raise ValueError("preflight already used or work active")
        self.preflight_started = True
        self._active += 1
        try:
            async with asyncio.timeout(WORK_SECONDS):
                observations = []
                for source, python in ((self.python, True), (self.pypi, False)):
                    page = validate_page(await source.retrieve(), python=python, fixture=self.fixture)
                    if not -2 <= (self.clock() - page.retrieved_at).total_seconds() <= 60:
                        raise ValueError("stale preflight")
                    version = primary_label(page.content)[0] if python else pypi_version(page.content)
                    observations.append(reference(page, version).model_dump(mode="json"))
                return {"observations": observations, "fixture": self.fixture}
        finally:
            self._active -= 1

    def report(self):
        return {"fixture": self.fixture, "records": self.records, "sources": {
            s.name: {"attempted": s.attempted, "completed": s.completed, "calls": s.calls}
            for s in (self.python, self.pypi)},
            "count_scope": "retrieval invocations in this process; not billing or origin-fetch counts"}


def qualification_app(pipeline):
    app = create_app(pipeline)
    app.add_middleware(MultiBound, path="/qualification/preflight")
    app.state.pipeline = pipeline

    # Private operator-only network, no client route to these endpoints. No
    # arbitrary candidate/source input, reset, budget increase or live fallback.
    @app.post("/qualification/preflight")
    async def preflight():
        try:
            return await pipeline.preflight()
        except Exception:
            return JSONResponse({"failure": "preflight_unavailable"}, status_code=503)

    @app.get("/qualification/report")
    async def report():
        return pipeline.report()

    return app


def live_app():
    key = live_key()
    pipeline = ObservedPipeline(TavilyRetriever(api_key=key, timeouts=TAVILY),
                                PyPIRetriever(timeout_seconds=PYPI_SECONDS), fixture=False)
    return qualification_app(pipeline)
