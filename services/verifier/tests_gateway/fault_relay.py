"""Isolated test-only relay. Runner control is separate from inference traffic.

Never package this as a production endpoint. No inference text/header chooses a
fault. Every mutation starts from a real pipeline record unless testing HTTP or
wire failure. It has no live credentials or external destination configuration.
"""

import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import httpx
from pydantic import BaseModel, ConfigDict
from typing import Literal

if os.getenv("EPOCHGUARD_TEST_MODE") != "1":
    raise RuntimeError("fault relay requires explicit test mode")

app = FastAPI()
counts = Counter()


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["supported", "missing", "injected", "wrong"] = "supported"
    fault: Literal["none", "missing", "duplicate", "reorder", "verdict", "comparison", "hash", "id",
                   "stale", "alias", "nested-duplicate", "policy", "extraction", "binding", "coverage",
                   "mode", "evidence-id", "request-mismatch", "http500", "malformed", "timeout", "slow",
                   "missing-field", "null-flag", "oversized", "missing-neighbor"] = "none"


state = Control()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/test/control")
async def control(value: Control):
    global state
    state = value
    return {"status": "configured"}


@app.get("/test/stats")
async def stats():
    return dict(counts)


@app.post("/v1/verify/multiclaim")
async def corrupt(request: Request):
    selected = state
    counts[selected.fault] += 1
    if selected.fault == "http500":
        return JSONResponse({"detail": "synthetic verifier failure"}, status_code=500)
    if selected.fault == "timeout":
        await asyncio.sleep(4)
    if selected.fault == "slow":
        await asyncio.sleep(0.25)
    if selected.fault == "malformed":
        return Response("not JSON", media_type="application/json")
    if selected.fault == "oversized":
        return Response(" " * (256 * 1024 + 1), media_type="application/json")
    if selected.fault == "request-mismatch":
        return JSONResponse({"schema_version": "003a.v1", "verdict": "SUPPORTED"})
    body = await request.body()
    if len(body) > 65536:
        return Response(status_code=413)
    async with httpx.AsyncClient(timeout=5, trust_env=False, follow_redirects=False) as client:
        response = await client.post(f"http://verifier-{selected.target}:8000/v1/verify/multiclaim",
                                     content=body, headers={"content-type": "application/json"})
    if response.status_code != 200:
        return Response(status_code=503)
    result = response.json()
    fault = selected.fault
    if fault == "missing":
        result["claims"].pop()
    elif fault == "missing-neighbor":
        result["claims"].pop(0)
    elif fault == "duplicate":
        result["claims"].append(result["claims"][0])
    elif fault == "reorder":
        result["claims"].reverse()
    elif fault == "verdict":
        result["claims"][1].update(verdict="INSUFFICIENT", reason_code="RETRIEVAL_FAILURE",
                                    evidence_requirements_satisfied=False, evidence=[])
        result["verdict"] = "SUPPORTED"
    elif fault == "comparison":
        result["claims"][1]["evidence"][0]["observed_version"] = "2.88.6"
    elif fault == "hash":
        result["candidate_sha256"] = "0" * 64
    elif fault == "id":
        result["request_id"] = "different-request"
    elif fault == "stale":
        stamp = (datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
        for key in ("observed_at", "retrieved_at"):
            result["claims"][1]["evidence"][0][key] = stamp
    elif fault == "policy":
        result["claims"][1]["claim"]["policy_id"] = "unsupported-policy"
    elif fault == "extraction":
        result["extraction_status"] = "FAILED"
    elif fault == "binding":
        result["binding_status"] = "FAILED"
    elif fault == "coverage":
        result["coverage"]["required_claim_ids"].pop()
    elif fault == "mode":
        result["claims"][1]["evidence"][0]["retrieval_mode"] = "pypi_live"
    elif fault == "evidence-id":
        result["claims"][1]["evidence"][0]["evidence_id"] = "0" * 64
    elif fault == "missing-field":
        del result["claims"][1]["evidence_requirements_satisfied"]
    elif fault == "null-flag":
        result["claims"][1]["evidence_requirements_satisfied"] = None
    text = json.dumps(result, separators=(",", ":"))
    if fault == "alias":
        text = text.replace('"observed_version":', '"Observed_Version":', 1)
    elif fault == "nested-duplicate":
        text = text.replace('"claim_id":"c001"', '"claim_id":"c001","claim_\\u0069d":"c001"', 1)
    return Response(text, media_type="application/json")
