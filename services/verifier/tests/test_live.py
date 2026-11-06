"""Explicit opt-in; derives the claim from current retrieval, never a frozen fact."""

import asyncio
import json
import os

from fastapi.testclient import TestClient
import pytest

from verifier.app import create_app
from verifier.policy import claim_text, primary_label
from verifier.retrieval import TavilyRetriever
from tests.test_verifier import request


@pytest.mark.live
def test_live_tavily_evidence_metadata():
    if os.getenv("EPOCHGUARD_RUN_LIVE_TAVILY") != "1":
        pytest.skip("explicit live opt-in is required")
    if not os.getenv("TAVILY_API_KEY"):
        pytest.fail("TAVILY_API_KEY is required for an explicitly requested live run")
    # Ignore test endpoint overrides: credentials go only to the real HTTPS API.
    source = TavilyRetriever(api_key=os.environ["TAVILY_API_KEY"])
    page = asyncio.run(source.retrieve())
    version, _ = primary_label(page.content)
    with TestClient(create_app(source)) as client:
        record = client.post("/v1/verify", json=request(claim_text(version)).model_dump(mode="json"))
    assert record.status_code == 200
    value = record.json()
    assert value["evidence"], "live source format or retrieval no longer meets this policy"
    # A release can change between the two real requests. Assert contract and
    # metadata, not that any hardcoded version remains current forever.
    assert value["reason_code"] in {"MATCHED_PRIMARY_LABEL", "OLDER_THAN_PRIMARY_LABEL", "CLAIM_AHEAD_OF_SOURCE"}
    assert value["evidence"][0]["retrieval_id"]
    assert value["evidence"][0]["retrieval_mode"] == "tavily_live"
    assert value["evidence"][0]["retrieved_at"] and value["evidence"][0]["observed_at"]
    print(json.dumps({"policy_id": value["policy_id"], "verdict": value["verdict"],
                      "reason_code": value["reason_code"], "evidence": value["evidence"]}))
