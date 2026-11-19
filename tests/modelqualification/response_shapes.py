"""Synthetic native Gemini envelopes, exclusively for network-disabled runs."""
import copy
import json
from .common import SUPPORTED, OLDER


def envelope(text=SUPPORTED, *, reason="STOP", parts=None):
    return {"candidates": [{"content": {"role": "model", "parts": parts if parts is not None else [{"text": text}]},
                            "finishReason": reason, "index": 0}],
            "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 20}}


def fixtures():
    plain = envelope()
    missing_content = copy.deepcopy(plain)
    missing_content["candidates"][0].pop("content")
    missing_parts = copy.deepcopy(plain)
    missing_parts["candidates"][0]["content"].pop("parts")
    annotated = copy.deepcopy(plain)
    annotated["candidates"][0]["groundingMetadata"] = {
        "groundingChunks": [{"web": {"uri": "https://example.invalid/synthetic", "title": "synthetic"}}],
        "groundingSupports": [{"segment": {"startIndex": 0, "endIndex": 10, "text": "synthetic"}, "groundingChunkIndices": [0]}]}
    signature = envelope(parts=[{"text": SUPPORTED, "thoughtSignature": "c3ludGhldGlj"}])
    file_neighbor = copy.deepcopy(signature)
    file_neighbor["candidates"][0]["content"]["parts"].append(
        {"fileData": {"mimeType": "image/png", "fileUri": "https://example.invalid/synthetic.png"}})
    two_candidates = copy.deepcopy(signature)
    two_candidates["candidates"].append(envelope("Unaccounted second candidate.")["candidates"][0])
    return {
        "stop": (plain, "ALLOW", "evidence_policy_validated", True),
        "max_tokens": (envelope(reason="MAX_TOKENS"), "UNAVAILABLE", "unsupported_finish_reason", False),
        "empty_candidates": ({"candidates": [], "usageMetadata": plain["usageMetadata"]}, "UNAVAILABLE", "buffered_candidate_shape", False),
        "missing_content": (missing_content, "UNAVAILABLE", "evidence_policy_validation_refused", True),
        "missing_parts": (missing_parts, "UNAVAILABLE", "evidence_policy_validation_refused", True),
        "thinking_only": (envelope(parts=[{"text": "SYNTHETIC_PRIVATE_THINKING", "thought": True}]), "UNAVAILABLE", "unsupported_provider_annotations", False),
        "thought_signature": (envelope(parts=[{"text": SUPPORTED, "thoughtSignature": "c3ludGhldGlj"}]), "UNAVAILABLE", "unsupported_provider_annotations", False),
        "additional_metadata": (envelope(parts=[{"text": SUPPORTED, "syntheticMetadata": "SYNTHETIC_PRIVATE_METADATA"}]), "ALLOW", "evidence_policy_validated", True),
        "annotations": (annotated, "UNAVAILABLE", "unsupported_provider_annotations", False),
        "malformed": (b'{"candidates":', "INGRESS_REFUSED", "provider_bifrost_failure", False),
        "unsupported_prose": (envelope("Unaccounted factual prose."), "UNAVAILABLE", "evidence_policy_validation_refused", True),
        "contradicted": (envelope(OLDER), "REJECT", "evidence_policy_validation_refused", True),
        "text_and_thinking": (envelope(parts=[{"text": "SYNTHETIC_PRIVATE_THINKING", "thought": True}, {"text": SUPPORTED}]), "UNAVAILABLE", "unsupported_provider_annotations", False),
        "split_text": (envelope(parts=[{"text": SUPPORTED[:30]}, {"text": SUPPORTED[30:]}]), "UNAVAILABLE", "buffered_candidate_shape", False),
        "unknown_finish": (envelope(reason="SYNTHETIC_PRIVATE_REASON"), "UNAVAILABLE", "unsupported_finish_reason", False),
        "empty_text": (envelope(""), "UNAVAILABLE", "evidence_policy_validation_refused", True),
        "signature_file_neighbor": (file_neighbor, "UNAVAILABLE", "unsupported_provider_annotations", False),
        "signature_two_candidates": (two_candidates, "UNAVAILABLE", "unsupported_provider_annotations", False),
    }


FIXTURES = fixtures()
SHAPE_PROMPTS = {"shape_" + name: "005C-R synthetic response shape: " + name for name in FIXTURES}


def batch(number):
    return list(SHAPE_PROMPTS)[(number-1)*6:number*6]


def response(name):
    value = FIXTURES[name.removeprefix("shape_")][0]
    return value if isinstance(value, bytes) else json.dumps(value, separators=(",", ":")).encode()
