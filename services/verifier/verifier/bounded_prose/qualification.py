"""Private, opt-in qualification composition; enforcement contracts are unchanged."""
import os
import time
from datetime import datetime, timezone

from fastapi.responses import JSONResponse

from verifier.retrieval import TavilyRetriever
from verifier.multiclaim.retrieval import PyPIRetriever
from verifier.multiclaim.deployment import (
    CANARY, TAVILY, PYPI_SECONDS, ObservedPipeline, live_key,
)
from verifier.multiclaim.app import MultiBound
from .app import create_app
from .pipeline import Pipeline


class ObservedProse(Pipeline):
    def __init__(self, evidence, *, simulated=False):
        super().__init__(evidence)
        self.records = []
        self.simulated = simulated

    async def verify(self, request):
        if request.candidate == CANARY:
            return await super().verify(request)
        if len(self.records) >= 16:
            raise ValueError("qualification record budget exhausted")
        row = {"candidate_sha256": request.candidate_sha256,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "verdict": "INSUFFICIENT", "claims": [], "coverage": "UNCERTAIN",
               "canonical_sha256": None, "completed": False}
        self.records.append(row)
        started = time.monotonic()
        try:
            result = await super().verify(request)
            row.update(coverage=result.coverage, completed=True)
            if result.verification is not None:
                verified = result.verification
                row.update(verdict=verified.verdict, canonical_sha256=verified.candidate_sha256,
                           claims=[{
                               "claim_id": c.claim.source.claim_id,
                               "policy_id": c.claim.policy_id,
                               "claimed_version": c.claim.version,
                               "verdict": c.verdict,
                               "evidence": [e.model_dump(mode="json") for e in c.evidence],
                           } for c in verified.claims])
            return result  # no telemetry is used to authorize a response
        finally:
            row["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
            row["finished_at"] = datetime.now(timezone.utc).isoformat()

    def report(self):
        evidence = self.evidence_pipeline.report()
        return {"schema_version": "004gl.observations.v1", "policy_id": "004g.v1/bounded-prose-v1",
                "simulated_transports": self.simulated, "fixture": self.evidence_pipeline.fixture,
                "records": self.records, "sources": evidence["sources"],
                "count_scope": evidence["count_scope"]}


def qualification_app(evidence, *, simulated=False):
    pipeline = ObservedProse(evidence, simulated=simulated)
    app = create_app(pipeline)
    app.state.pipeline = pipeline
    app.add_middleware(MultiBound, path="/qualification/preflight")

    @app.post("/qualification/preflight")
    async def preflight():
        try:
            value = await evidence.preflight()
            return {**value, "simulated_transports": simulated}
        except Exception:
            return JSONResponse({"failure": "preflight_unavailable"}, status_code=503)

    @app.get("/qualification/report")
    async def report():
        return pipeline.report()

    return app


def live_app():
    if os.getenv("EPOCHGUARD_RUN_LIVE_004G") != "1":
        raise ValueError("004G live opt-in required")
    key = live_key()  # existing E opt-in, fixed profile, bounded runtime secret
    return qualification_app(ObservedPipeline(
        TavilyRetriever(api_key=key, timeouts=TAVILY),
        PyPIRetriever(timeout_seconds=PYPI_SECONDS), fixture=False))
