"""Explicit opt-in; derives the claim from current retrieval, never a frozen fact."""

import asyncio
import json
import os
import time

import httpx
import pytest

from verifier.app import create_app
from verifier.policy import claim_text, primary_label
from verifier.retrieval import TavilyRetriever
from verifier.contract import VerificationResponse
from verifier.settings import TimeoutSettings
from tests.test_verifier import request


@pytest.mark.live
def test_live_tavily_evidence_metadata(monkeypatch):
    if os.getenv("EPOCHGUARD_RUN_LIVE_TAVILY") != "1":
        pytest.skip("explicit live opt-in is required")
    if not os.getenv("TAVILY_API_KEY"):
        pytest.fail("TAVILY_API_KEY is required for an explicitly requested live run")
    # Explicit live test selects the trusted long profile, never a request header.
    monkeypatch.setenv("EPOCHGUARD_TIMEOUT_PROFILE", "live")
    monkeypatch.delenv("EPOCHGUARD_TEST_TAVILY_ENDPOINT", raising=False)
    monkeypatch.delenv("EPOCHGUARD_TEST_MODE", raising=False)
    budgets = TimeoutSettings.from_environment()
    source = TavilyRetriever.from_environment(timeouts=budgets)
    page = asyncio.run(source.retrieve())
    version, _ = primary_label(page.content)
    payload = request(claim_text(version)).model_dump(mode="json")

    async def through_fastapi():
        # Exercise the production route, factory, retrieval and comparison, with
        # no injected retriever or precomputed verdict. ASGI avoids a test server;
        # asyncio supplies a real total bound, unlike HTTPX's ASGI socket timeout.
        async with asyncio.timeout(30):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(timeouts=budgets)),
                                         base_url="http://verifier") as client:
                return await client.post("/v1/verify", json=payload)

    started = time.monotonic()
    record = asyncio.run(through_fastapi())
    elapsed = time.monotonic() - started
    assert record.status_code == 200
    typed = VerificationResponse.model_validate_json(record.content)
    value = typed.model_dump(mode="json")
    assert value["request_id"] == payload["request_id"]
    assert value["candidate_sha256"] == payload["candidate_sha256"]
    assert value["claim"]["version"] == version
    assert value["evidence"], "live source format or retrieval no longer meets this policy"
    # A release can change between the two real requests. Assert contract and
    # metadata, not that any hardcoded version remains current forever.
    assert value["reason_code"] in {"MATCHED_PRIMARY_LABEL", "OLDER_THAN_PRIMARY_LABEL", "CLAIM_AHEAD_OF_SOURCE"}
    assert value["verdict"] == {"MATCHED_PRIMARY_LABEL": "SUPPORTED", "OLDER_THAN_PRIMARY_LABEL": "CONTRADICTED",
                               "CLAIM_AHEAD_OF_SOURCE": "INSUFFICIENT"}[value["reason_code"]]
    assert value["evidence"][0]["retrieval_id"]
    assert value["evidence"][0]["retrieval_mode"] == "tavily_live"
    assert value["evidence"][0]["retrieved_at"] and value["evidence"][0]["observed_at"]
    print(json.dumps({"policy_id": value["policy_id"], "verdict": value["verdict"], "elapsed_seconds": elapsed,
                      "timeout_profile": budgets.model_dump(),
                      "reason_code": value["reason_code"], "evidence": value["evidence"]}))
