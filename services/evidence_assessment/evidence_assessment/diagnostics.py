"""Per-response structural diagnostics. No provider/input text enters this sink."""
from dataclasses import dataclass
import json
import logging

from .config import Failure
from .schema import ModelAssessment

LOGGER = logging.getLogger("epochguard.experimental.model_validation")
CATEGORIES = frozenset({
    "MODEL_FINISH_INCOMPLETE", "MODEL_ENVELOPE_INVALID", "MODEL_JSON_INVALID",
    "MODEL_SCHEMA_INVALID", "MODEL_CLAIM_MISMATCH", "MODEL_SOURCE_COVERAGE",
    "MODEL_CITATION_BINDING", "MODEL_QUOTATION_BINDING",
})
# Unknown provider enum values and schema keys must never be reflected.
FINISH_REASONS = frozenset({"STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "LANGUAGE",
    "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "MALFORMED_FUNCTION_CALL",
    "UNEXPECTED_TOOL_CALL", "TOO_MANY_TOOL_CALLS", "FINISH_REASON_UNSPECIFIED",
    "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT", "IMAGE_RECITATION", "IMAGE_OTHER", "NO_IMAGE"})
TOKEN_FIELDS = ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount",
                "totalTokenCount", "cachedContentTokenCount")
SCHEMA_FIELDS = frozenset({"claim", "scope", "assessment", "explanation", "uncertainty",
    "independence_uncertain", "source_assessments", "source_id", "stance", "quote", "citation_ids"})


def field_paths(locations):
    """Redact arbitrary Pydantic extra-field names, indices and nested paths."""
    paths = []
    for location in locations:
        path = "$"
        for part in tuple(location)[:4]:
            if type(part) is int:
                path += f"[{part}]" if 0 <= part < 5 else "[index]"
            else:
                path += "." + (part if isinstance(part, str) and part in SCHEMA_FIELDS else "[unknown]")
        if path not in paths:
            paths.append(path)
        if len(paths) == 8:
            break
    return paths


@dataclass(frozen=True)
class ModelDiagnostics:
    finish_reason: str
    token_counts: tuple
    max_output_tokens: int
    source_count: int

    @classmethod
    def capture(cls, envelope, max_output_tokens, source_count):
        finish = "MISSING"
        counts = ()
        if isinstance(envelope, dict):
            candidates = envelope.get("candidates")
            if isinstance(candidates, list) and len(candidates) == 1 and isinstance(candidates[0], dict):
                reason = candidates[0].get("finishReason")
                if reason is not None:
                    finish = reason if isinstance(reason, str) and reason in FINISH_REASONS else "UNKNOWN"
            usage = envelope.get("usageMetadata")
            if isinstance(usage, dict):
                counts = tuple((name, usage[name]) for name in TOKEN_FIELDS
                    if type(usage.get(name)) is int and 0 <= usage[name] <= 2**31 - 1)
        return cls(finish, counts, max_output_tokens, source_count)

    def failure(self, category, locations=()):
        if category not in CATEGORIES:
            raise ValueError("unknown diagnostic category")
        event = {"schema_version": "005j.model-validation.v1", "event": "model_validation_failed",
            "category": category, "finish_reason": self.finish_reason,
            "token_counts": dict(self.token_counts), "max_output_tokens": self.max_output_tokens,
            "source_count": self.source_count, "validation_fields": field_paths(locations)}
        try:
            LOGGER.warning("%s", json.dumps(event, sort_keys=True, separators=(",", ":")))
        except Exception:
            # An unavailable diagnostic sink cannot change the refusal.
            pass
        return Failure(category)


@dataclass(frozen=True)
class AssessedModel:
    # The record is normal pipeline data, never passed to the diagnostic logger.
    record: ModelAssessment
    diagnostics: ModelDiagnostics
