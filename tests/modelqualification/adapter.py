"""Trusted 005C-only structural projection, before any lossy native decoding.

No evidence, policy, fixture answers, I/O or authorization belongs here. The
digests describe this process's observation; they are not source attestations.
"""
import base64
import json
import re
from datetime import datetime
from claim_analysis.schema import strict_json
from .common import sha

VERSION = "005ct.projection.v1"
BODY_LIMIT, TEXT_LIMIT, SIGNATURE_LIMIT = 65536, 32768, 16384
COUNTS = {"cachedContentTokenCount", "candidatesTokenCount", "promptTokenCount",
          "thoughtsTokenCount", "toolUsePromptTokenCount", "totalTokenCount"}
DETAILS = {"cacheTokensDetails", "candidatesTokensDetails", "promptTokensDetails", "toolUsePromptTokensDetails"}
TRAFFIC = {"TRAFFIC_TYPE_UNSPECIFIED", "ON_DEMAND", "ON_DEMAND_PRIORITY", "ON_DEMAND_FLEX", "PROVISIONED_THROUGHPUT"}
TIERS = {"unspecified", "flex", "standard", "priority"}


class Refusal(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise Refusal(code)


def fields(value, required, optional, code):
    require(type(value) is dict and required <= value.keys() and value.keys() <= required | optional, code)


def count(value):
    return type(value) is int and 0 <= value <= 2147483647


def usage(value):
    fields(value, set(), COUNTS | DETAILS | {"trafficType", "serviceTier"}, "usage_fields")
    for key, item in value.items():
        if key in COUNTS:
            require(count(item), "usage_type")
            if key == "toolUsePromptTokenCount":
                require(item == 0, "tool_usage")
        elif key in DETAILS:
            require(type(item) is list and len(item) <= 1, "usage_details")
            if key == "toolUsePromptTokensDetails":
                require(not item, "tool_usage")
            for detail in item:
                fields(detail, {"modality", "tokenCount"}, set(), "usage_details")
                require(detail["modality"] == "TEXT" and count(detail["tokenCount"]), "usage_details")
        elif key == "trafficType":
            require(type(item) is str and item in TRAFFIC, "usage_type")
        else:
            require(type(item) is str and item in TIERS, "usage_type")
    if "totalTokenCount" in value:
        require(all(value[key] <= value["totalTokenCount"] for key in COUNTS & value.keys()), "usage_counts")


def validated_text(value):
    # Exact native camelCase fields only. Even empty unsupported fields refuse.
    fields(value, {"candidates"}, {"modelVersion", "responseId", "createTime", "usageMetadata"}, "root_fields")
    for key in ("modelVersion", "responseId"):
        if key in value:
            require(type(value[key]) is str and re.fullmatch(r"[\x21-\x7e]{1,256}", value[key]) is not None, "metadata_type")
    if "createTime" in value:
        stamp = value["createTime"]
        require(type(stamp) is str and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z", stamp) is not None, "metadata_type")
        try:
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            raise Refusal("metadata_type") from None
    if "usageMetadata" in value:
        usage(value["usageMetadata"])
    candidates = value["candidates"]
    require(type(candidates) is list and len(candidates) == 1, "candidate_count")
    candidate = candidates[0]
    fields(candidate, {"content", "finishReason"}, {"index", "tokenCount"}, "candidate_fields")
    require(candidate["finishReason"] == "STOP", "finish_reason")
    if "index" in candidate:
        require(type(candidate["index"]) is int and candidate["index"] == 0, "candidate_index")
    if "tokenCount" in candidate:
        require(count(candidate["tokenCount"]), "candidate_tokens")
    content = candidate["content"]
    fields(content, {"role", "parts"}, set(), "content_fields")
    require(content["role"] == "model", "content_role")
    require(type(content["parts"]) is list and len(content["parts"]) == 1, "part_count")
    part = content["parts"][0]
    fields(part, {"text"}, {"thought", "thoughtSignature"}, "part_fields")
    require("thought" not in part or part["thought"] is False, "thinking")
    text = part["text"]
    require(type(text) is str and 0 < len(text) <= 8192, "text_bound")
    try:
        encoded = text.encode("utf-8", "strict")
    except UnicodeError:
        raise Refusal("text_encoding") from None
    require(len(encoded) <= TEXT_LIMIT and all(ord(c) >= 32 or c in "\t\n\r" for c in text), "text_bound")
    signature = part.get("thoughtSignature")
    if "thoughtSignature" in part:
        require(type(signature) is str and 0 < len(signature) <= SIGNATURE_LIMIT, "signature_encoding")
        try:
            decoded = base64.b64decode(signature, validate=True)
            require(bool(decoded) and base64.b64encode(decoded).decode("ascii") == signature, "signature_encoding")
        except (ValueError, UnicodeError):
            raise Refusal("signature_encoding") from None
    return text, signature is not None


def adapt(body):
    """Return (minimal native bytes or None, bounded diagnostic). Never repair.

    A refused projection has no candidate hash and must never be forwarded as
    the original. Every unexpected validation/diagnostic exception fails closed.
    """
    diagnostic = {"schema_version": VERSION, "original_received": True,
                  "original_response_sha256": sha(body), "validation": "REFUSED",
                  "reason": "validation_unavailable", "signature_present": None,
                  "projection_performed": False, "projected_response_sha256": None,
                  "original_text_sha256": None, "projected_text_sha256": None, "text_equal": False}
    try:
        require(type(body) is bytes and 0 < len(body) <= BODY_LIMIT, "body_bound")
        try:
            # Decode explicitly: json.loads(bytes) would also accept UTF-16/32.
            value = strict_json(body.decode("utf-8", "strict"))
        except Exception:
            raise Refusal("invalid_json") from None
        text, signature = validated_text(value)
        projection = json.dumps({"candidates": [{"content": {"role": "model", "parts": [{"text": text}]},
                                                  "finishReason": "STOP", "index": 0}]},
                                ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        projected_text = strict_json(projection)["candidates"][0]["content"]["parts"][0]["text"]
        require(text.encode("utf-8") == projected_text.encode("utf-8"), "text_correspondence")
        diagnostic.update(validation="ACCEPTED", reason="validated_projection", signature_present=signature,
                          projection_performed=True, projected_response_sha256=sha(projection),
                          original_text_sha256=sha(text), projected_text_sha256=sha(projected_text), text_equal=True)
        return projection, diagnostic
    except Refusal as error:
        diagnostic["reason"] = str(error)  # Only locally defined fixed codes.
    except Exception:
        pass
    return None, diagnostic
