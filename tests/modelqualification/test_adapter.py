import asyncio
import copy
import json
import httpx
import pytest
from modelqualification.adapter import adapt, BODY_LIMIT
from modelqualification.adapter_shapes import FIXTURES, response
from modelqualification.common import Settings, SUPPORTED, sha
from modelqualification.relay import Relay
from modelqualification.response_shapes import envelope
from modelqualification.test_controls import settings, native
from modelqualification.qualify import control_gateway, gateway


@pytest.mark.parametrize("name", FIXTURES)
def test_entire_original_before_projection(name):
    original = response("adapter_" + name)
    projected, diagnostic = adapt(original)
    accepted = FIXTURES[name][1] != "PROVIDER_ERROR"
    assert (projected is not None) is accepted
    assert diagnostic["original_response_sha256"] == sha(original)
    assert diagnostic["projection_performed"] is accepted
    assert diagnostic["validation"] == ("ACCEPTED" if accepted else "REFUSED")
    if accepted:
        before = json.loads(original)["candidates"][0]["content"]["parts"][0]["text"]
        minimal = {"candidates": [{"content": {"role": "model", "parts": [{"text": before}]}, "finishReason": "STOP", "index": 0}]}
        assert json.loads(projected) == minimal
        assert diagnostic["text_equal"] is True
        assert diagnostic["original_text_sha256"] == diagnostic["projected_text_sha256"] == sha(before)
    else:
        assert diagnostic["projected_response_sha256"] is None and diagnostic["original_text_sha256"] is None
    encoded = json.dumps(diagnostic)
    assert len(encoded) < 1200
    assert SUPPORTED not in encoded and "c3ludGhldGlj" not in encoded and "https://" not in encoded


@pytest.mark.parametrize("raw", [b"", b"null", b"[]", b"true", b'{} trailing', b'{"x":NaN}',
    b'{"x":Infinity}', b'{"x":1,"x":2}', b'{"candidates":[{"content":{"role":"model","parts":[{"text":"a","text":"b"}]},"finishReason":"STOP"}]}',
    b'\xef\xbb\xbf{}', '{}'.encode('utf-16'), b'[' * 2000, b'x' * (BODY_LIMIT + 1)])
def test_parser_failure_never_repairs(raw):
    projected, diagnostic = adapt(raw)
    assert projected is None and diagnostic["validation"] == "REFUSED"


@pytest.mark.parametrize("signature", [None, False, 1, [], {}, "", "?", "eA", "eA===", "eA==\n", "eB==", "____", "é"])
def test_signature_canonical_encoding(signature):
    value = envelope(parts=[{"text": SUPPORTED, "thoughtSignature": signature}])
    assert adapt(json.dumps(value).encode())[0] is None


@pytest.mark.parametrize("text", ["\n café\t雪 👩‍💻\r\n", " ", "a" * 8192, "\u2028\u2029", "e\u0301"])
def test_decoded_text_is_preserved_without_normalization(text):
    value = envelope(text)
    projected, diagnostic = adapt(json.dumps(value, ensure_ascii=True).encode())
    assert json.loads(projected)["candidates"][0]["content"]["parts"][0]["text"].encode() == text.encode()
    assert diagnostic["original_text_sha256"] == sha(text) and diagnostic["text_equal"]


@pytest.mark.parametrize("text", ["\ud800", "\u0000", "\x01", "x" * 8193, False, None, ["text"]])
def test_invalid_text(text):
    assert adapt(json.dumps(envelope(text)).encode())[0] is None


def test_audited_metadata_is_validated_then_excluded():
    value = envelope()
    value.update(modelVersion="gemini-fixture-1", responseId="synthetic-1", createTime="2026-11-19T00:00:00.123456789Z")
    value["usageMetadata"].update(candidatesTokenCount=5, thoughtsTokenCount=5, cachedContentTokenCount=0,
        toolUsePromptTokenCount=0, promptTokensDetails=[{"modality": "TEXT", "tokenCount": 10}],
        candidatesTokensDetails=[{"modality": "TEXT", "tokenCount": 5}], cacheTokensDetails=[],
        toolUsePromptTokensDetails=[], trafficType="ON_DEMAND", serviceTier="standard")
    value["candidates"][0]["tokenCount"] = 5
    value["candidates"][0]["content"]["parts"][0]["thought"] = False
    projected, diagnostic = adapt(json.dumps(value).encode())
    assert projected is not None and diagnostic["signature_present"] is False
    assert set(json.loads(projected)) == {"candidates"}
    for key, invalid in [("totalTokenCount", True), ("promptTokenCount", -1), ("totalTokenCount", 2**31),
                         ("thoughtsTokenCount", 0.0), ("trafficType", "UNKNOWN"), ("serviceTier", "UNKNOWN"),
                         ("promptTokensDetails", [{"modality": "TEXT", "tokenCount": 1, "other": 1}]),
                         ("promptTokensDetails", [{"modality": "TEXT", "tokenCount": 1}] * 2),
                         ("promptTokensDetails", None), ("toolUsePromptTokensDetails", [{"modality": "TEXT", "tokenCount": 0}])]:
        bad = copy.deepcopy(value)
        bad["usageMetadata"][key] = invalid
        assert adapt(json.dumps(bad).encode())[0] is None
    for key, invalid in [("createTime", "2026-02-30T00:00:00Z"), ("createTime", "2026-11-19"),
                         ("responseId", "x" * 257), ("modelVersion", None), ("usageMetadata", [])]:
        assert adapt(json.dumps(value | {key: invalid}).encode())[0] is None


def test_signature_value_cannot_change_projection_or_evidence_input():
    outputs = []
    for signature in ("eA==", "eQ==", "c3ludGhldGlj", None):
        part = {"text": SUPPORTED}
        if signature is not None:
            part["thoughtSignature"] = signature
        outputs.append(adapt(json.dumps(envelope(parts=[part])).encode())[0])
    assert len(set(outputs)) == 1


def test_strict_relay_fail_closed_and_provider_errors_are_unchanged(monkeypatch):
    async def scenario():
        original = response("adapter_supported")
        async def provider(_):
            return httpx.Response(200, content=original)
        relay = Relay(settings(response_mode="strict-005ct"), transport=httpx.MockTransport(provider))
        result = await relay.generate(native(), "offline-only")
        assert result.status_code == 200 and result.body != original
        assert relay.records[0]["adapter"]["text_equal"]
        def unavailable(_):
            raise RuntimeError("private diagnostic failure")
        monkeypatch.setattr("modelqualification.relay.adapt", unavailable)
        result = await relay.generate(native(), "offline-only")
        assert result.status_code == 502 and SUPPORTED.encode() not in result.body
        assert relay.reserved > 0 and len(relay.records) == 2
        async def failed(_):
            return httpx.Response(400, content=b'{"error":{"code":400,"message":"synthetic private failure"}}')
        relay = Relay(settings(response_mode="strict-005ct"), transport=httpx.MockTransport(failed))
        result = await relay.generate(native(), "offline-only")
        assert result.status_code == 400 and result.body == b'{"error":{"code":400,"message":"synthetic private failure"}}'
        assert "adapter" not in relay.records[0] and "private" not in json.dumps(relay.report())
    asyncio.run(scenario())


def test_explicit_configuration_and_no_unadapted_exception():
    assert settings().response_mode == "unadapted"
    for invalid in ("strict", None, True, {}, 1):
        with pytest.raises(ValueError):
            settings(response_mode=invalid)
    assert Settings.model_fields["response_mode"].default == "unadapted"


def test_no_plugin_native_control_is_offline_only():
    config = settings(response_mode="strict-005ct")
    control = control_gateway(config, False)
    assert control["plugins"] == []
    assert control["providers"]["gemini"]["keys"][0]["value"] == "offline-only"
    assert gateway(config)["providers"]["gemini"]["keys"][0]["value"] == "env.EPOCHGUARD_005C_KEY"
    assert "gemini" not in control_gateway(config, True)["providers"]
    assert "gemini" not in control_gateway(settings(), False)["providers"]


@pytest.mark.parametrize("location,key,value", [
    ("root", "unknown", {}), ("root", "usage_metadata", {}), ("root", "error", {}),
    ("candidate", "finishMessage", ""), ("candidate", "logprobsResult", {}),
    ("candidate", "continuationToken", ""), ("candidate", "urlContextMetadata", {}),
    ("content", "unknown", {}), ("content", "role", "assistant"), ("content", "parts", []),
    ("part", "thought", 0), ("part", "thought", None), ("part", "functionResponse", {}),
    ("part", "executableCode", {}), ("part", "codeExecutionResult", {}),
    ("part", "videoMetadata", {}), ("part", "mediaResolution", {}),
])
def test_no_unsupported_field_even_if_empty(location, key, value):
    original = envelope()
    candidate = original["candidates"][0]
    content = candidate["content"]
    target = {"root": original, "candidate": candidate, "content": content, "part": content["parts"][0]}[location]
    target[key] = value
    assert adapt(json.dumps(original).encode())[0] is None
