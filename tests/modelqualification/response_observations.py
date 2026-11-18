"""Bounded structural diagnostics only. Never serialize provider text or keys."""
from verifier.bounded_prose.grammar import parse
from .common import OUTPUTS, sha

FINISH = frozenset({"STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT",
                    "SPII", "MALFORMED_FUNCTION_CALL", "IMAGE_SAFETY", "UNEXPECTED_TOOL_CALL",
                    "MISSING_THOUGHT_SIGNATURE", "MALFORMED_RESPONSE", "FINISH_REASON_UNSPECIFIED"})
PART_FIELDS = frozenset({"text", "thought", "thoughtSignature", "functionCall", "functionResponse", "inlineData",
                         "fileData", "executableCode", "codeExecutionResult", "videoMetadata", "mediaResolution"})


def count(value):
    return min(len(value), 64) if isinstance(value, list) else None


def candidate_shape(value):
    result = {"finish_reason": "INVALID_CANDIDATE", "content_present": False, "content_object": False,
              "parts_present": False, "parts_array": False, "part_count": None, "part_types": [],
              "parts_truncated": False, "non_thinking_text_part_exists": False, "thinking_only": False,
              "recognized_text_empty": None, "single_stopped_visible_text": False}
    if not isinstance(value, dict):
        return result, None
    reason = value.get("finishReason")
    result["finish_reason"] = reason if isinstance(reason, str) and reason in FINISH else "MISSING" if reason is None else "UNRECOGNIZED"
    result["content_present"] = "content" in value
    content = value.get("content")
    result["content_object"] = isinstance(content, dict)
    if not isinstance(content, dict):
        return result, None
    result["parts_present"] = "parts" in content
    parts = content.get("parts")
    result["parts_array"] = isinstance(parts, list)
    result["part_count"] = count(parts)
    if not isinstance(parts, list):
        return result, None
    result["parts_truncated"] = len(parts) > 64
    visible, thinking = [], False
    for part in parts[:64]:
        if not isinstance(part, dict):
            result["part_types"].append(["INVALID_PART"])
            continue
        types = sorted(PART_FIELDS.intersection(part))
        if set(part) - PART_FIELDS:
            types.append("OTHER_FIELD")
        result["part_types"].append(types or ["EMPTY_PART"])
        text = part.get("text")
        if isinstance(text, str):
            if part.get("thought") is True:
                thinking |= bool(text)
            elif part.get("thought", False) is False:
                visible.append(text)
    result["non_thinking_text_part_exists"] = bool(visible)
    result["recognized_text_empty"] = not any(visible) if visible else None
    result["thinking_only"] = thinking and not any(visible)
    # One original visible part only. Do not concatenate, strip or repair text.
    text = visible[0] if len(visible) == 1 and not result["parts_truncated"] else None
    result["single_stopped_visible_text"] = bool(text) and reason == "STOP"
    return result, text


def observe_envelope(value, scenario, row):
    diagnostic = {"schema_version": "005cr.response-shape.v1", "parse_outcome": "INVALID_ENVELOPE",
                  "candidate_count": None, "candidates_truncated": False, "candidates": [],
                  "finite_grammar_applied": False, "reported_output_tokens_without_usable_candidate": None}
    row["response_structure"] = diagnostic
    if not isinstance(value, dict):
        return
    candidates = value.get("candidates")
    diagnostic["parse_outcome"] = "MISSING_CANDIDATES" if "candidates" not in value else "INVALID_CANDIDATES" if not isinstance(candidates, list) else "PARSED"
    diagnostic["candidate_count"] = count(candidates)
    text, usable = None, False
    if isinstance(candidates, list):
        diagnostic["candidates_truncated"] = len(candidates) > 4
        for candidate in candidates[:4]:
            shape, visible = candidate_shape(candidate)
            diagnostic["candidates"].append(shape)
            if len(candidates) == 1:
                text, usable = visible, shape["single_stopped_visible_text"]
    if text is not None:
        row.update(candidate_sha256=sha(text), matches_intended_text=text == OUTPUTS.get(scenario))
        mappings, reason = parse(text)
        row["finite_grammar_observation"] = {"mapped_claims": len(mappings), "reason": reason}
        diagnostic["finite_grammar_applied"] = True
    # "Usable" here means a single nonempty stopped visible text part, not
    # Bifrost/Go eligibility or evidence approval. Metadata can still refuse it.
    outgoing = row.get("output_tokens_including_thoughts")
    if outgoing is not None:
        diagnostic["reported_output_tokens_without_usable_candidate"] = outgoing > 0 and not usable
