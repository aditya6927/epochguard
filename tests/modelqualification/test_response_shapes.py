import asyncio
import json
import httpx
import pytest
from modelqualification.relay import Relay
from modelqualification.response_shapes import FIXTURES, SHAPE_PROMPTS, response
from modelqualification.test_controls import settings
from modelqualification.common import sha, SUPPORTED


def native_shape(name):
    return json.dumps({"model": "gemini-offline-fixture", "contents": [{"role": "user", "parts": [{"text": SHAPE_PROMPTS["shape_"+name]}]}],
                       "generationConfig": {"maxOutputTokens": 256}}).encode()


@pytest.mark.parametrize("name", FIXTURES)
def test_native_bytes_and_bounded_observations(name):
    relay = Relay(settings())
    result = asyncio.run(relay.generate(native_shape(name), "offline-only"))
    assert result.status_code == 200 and result.body == response("shape_"+name)
    record = relay.records[0]
    encoded = json.dumps(record)
    for secret in ("SYNTHETIC_PRIVATE", SUPPORTED, "thoughtSignature\": \"c3", "https://example.invalid"):
        assert secret not in encoded
    assert len(encoded) < 8192
    diagnostic = record["response_structure"]
    if name == "malformed":
        assert diagnostic["parse_outcome"] == "INVALID_JSON"
        return
    assert diagnostic["parse_outcome"] == "PARSED"
    if name in {"stop", "thought_signature", "additional_metadata", "annotations", "text_and_thinking", "max_tokens", "unknown_finish"}:
        assert record["candidate_sha256"] == sha(SUPPORTED)
        assert diagnostic["finite_grammar_applied"] is True
    if name == "thinking_only":
        assert diagnostic["candidates"][0]["thinking_only"] is True
        assert diagnostic["reported_output_tokens_without_usable_candidate"] is True
        assert record["candidate_sha256"] is None
    if name == "max_tokens":
        assert diagnostic["candidates"][0]["finish_reason"] == "MAX_TOKENS"
        assert diagnostic["reported_output_tokens_without_usable_candidate"] is True


def test_unknown_strings_and_part_bounds_never_export_values():
    relay = Relay(settings())
    row = {}
    relay.observe(json.dumps({"candidates": [{"finishReason": "PRIVATE_ERROR_MESSAGE", "content": {
        "parts": [{"PRIVATE_KEY": "PRIVATE_TEXT"}] * 100}}], "usageMetadata": {"promptTokenCount": 1, "totalTokenCount": 5}}).encode(), "supported", row)
    assert "PRIVATE" not in json.dumps(row)
    candidate = row["response_structure"]["candidates"][0]
    assert candidate["parts_truncated"] and len(candidate["part_types"]) == 64
    assert candidate["finish_reason"] == "UNRECOGNIZED"
    assert row["output_tokens_including_thoughts"] == 4


def test_synthetic_shapes_are_refused_before_live_transport():
    relay = Relay(settings(max_requests=4), live=True)
    result = asyncio.run(relay.generate(native_shape("stop"), "test-only"))
    assert result.status_code == 429 and relay.records == []
