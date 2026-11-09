"""Bounded diagnostic metadata. Never serialize inputs, messages or contexts."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError


class Stage(StrEnum):
    PROVIDER_TRANSPORT = "PROVIDER_TRANSPORT"
    PROVIDER_HTTP = "PROVIDER_HTTP"
    PROVIDER_ENVELOPE = "PROVIDER_ENVELOPE"
    MODEL_JSON = "MODEL_JSON"
    MODEL_SCHEMA = "MODEL_SCHEMA"
    SOURCE_BINDING = "SOURCE_BINDING"
    EMPTY_ANALYSIS = "EMPTY_ANALYSIS"
    CONTROL = "CONTROL"


class Code(StrEnum):
    HTTP_FAILURE = "HTTP_FAILURE"
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
    TIMEOUT = "TIMEOUT"
    UNEXPECTED_PROVIDER_FAILURE = "UNEXPECTED_PROVIDER_FAILURE"
    ENVELOPE_INVALID = "ENVELOPE_INVALID"
    ENVELOPE_INCOMPLETE = "ENVELOPE_INCOMPLETE"
    ENVELOPE_CONTENT_INVALID = "ENVELOPE_CONTENT_INVALID"
    ENVELOPE_USAGE_INVALID = "ENVELOPE_USAGE_INVALID"
    OUTPUT_TOO_LARGE = "OUTPUT_TOO_LARGE"
    JSON_INVALID_OR_INCOMPLETE = "JSON_INVALID_OR_INCOMPLETE"
    JSON_INVALID_ENCODING = "JSON_INVALID_ENCODING"
    JSON_DUPLICATE_KEY = "JSON_DUPLICATE_KEY"
    JSON_NONFINITE_NUMBER = "JSON_NONFINITE_NUMBER"
    SCHEMA_MISSING_FIELD = "SCHEMA_MISSING_FIELD"
    SCHEMA_EXTRA_FIELD = "SCHEMA_EXTRA_FIELD"
    SCHEMA_LITERAL_INVALID = "SCHEMA_LITERAL_INVALID"
    SCHEMA_TYPE_INVALID = "SCHEMA_TYPE_INVALID"
    SCHEMA_LIMIT = "SCHEMA_LIMIT"
    SCHEMA_CONSTRAINT = "SCHEMA_CONSTRAINT"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    CLAIM_SPAN_ORDER = "CLAIM_SPAN_ORDER"
    CLAIM_DUPLICATE_UNCERTAINTY = "CLAIM_DUPLICATE_UNCERTAINTY"
    CLAIM_REFERENCE_MISMATCH = "CLAIM_REFERENCE_MISMATCH"
    CLAIM_NONFACTUAL_COMBINATION = "CLAIM_NONFACTUAL_COMBINATION"
    CLAIM_EVIDENCE_NOT_APPLICABLE = "CLAIM_EVIDENCE_NOT_APPLICABLE"
    CLAIM_UNCERTAINTY_MISSING = "CLAIM_UNCERTAINTY_MISSING"
    CLAIM_UNCERTAIN_TEMPORAL_COMBINATION = "CLAIM_UNCERTAIN_TEMPORAL_COMBINATION"
    CLAIM_DYNAMIC_REQUIRES_FRESH = "CLAIM_DYNAMIC_REQUIRES_FRESH"
    CLAIM_NON_DYNAMIC_EVIDENCE = "CLAIM_NON_DYNAMIC_EVIDENCE"
    BINDING_ID_SEQUENCE = "BINDING_ID_SEQUENCE"
    BINDING_OVERLAP = "BINDING_OVERLAP"
    BINDING_RANGE = "BINDING_RANGE"
    BINDING_TEXT_MISMATCH = "BINDING_TEXT_MISMATCH"
    EMPTY_MODEL_ANALYSIS = "EMPTY_MODEL_ANALYSIS"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    NOT_ENABLED = "NOT_ENABLED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"


FIELDS = frozenset({"schema_version", "claims", "claim_id", "source_text", "start", "end",
                    "normalized_proposition", "factuality", "temporal", "fresh_evidence",
                    "uncertainty", "temporal_reference"})
MAX_ISSUES, MAX_ERROR_COUNT, MAX_INDEX, MAX_DEPTH, MAX_PATH = 4, 64, 63, 6, 192


def safe_path(location=()):
    path = "$"
    for item in location[:MAX_DEPTH]:
        if type(item) is int:
            path += f"[{item}]" if 0 <= item <= MAX_INDEX else "[*]"
        elif type(item) is str and item in FIELDS:
            path += "." + item
        else:
            path += ".<unknown>"
    if len(location) > MAX_DEPTH:
        path += ".<truncated>"
    return path[:MAX_PATH]


@dataclass(frozen=True, init=False)
class Issue:
    code: Code
    field_path: str

    def __init__(self, code: Code, location=()):
        object.__setattr__(self, "code", Code(code))
        object.__setattr__(self, "field_path", safe_path(location))

    def to_dict(self):
        # Only enums and sanitized locations cross the diagnostic boundary.
        return {"code":self.code.value, "field_path":self.field_path}


@dataclass(frozen=True)
class FailureDetails:
    stage: Stage
    issues: tuple[Issue, ...]
    error_count: int = 1

    def to_dict(self):
        return {"stage":Stage(self.stage).value,
                "errors":[item.to_dict() for item in self.issues[:MAX_ISSUES]],
                "error_count":min(max(self.error_count, 0), MAX_ERROR_COUNT),
                "truncated":self.error_count > MAX_ISSUES or len(self.issues) > MAX_ISSUES}


def details(stage: Stage, code: Code, location=()):
    return FailureDetails(stage, (Issue(code, tuple(location)),))


class JSONFailure(ValueError):
    def __init__(self, code: Code):
        self.code = code
        super().__init__({Code.OUTPUT_TOO_LARGE:"JSON output bound exceeded",
                          Code.JSON_DUPLICATE_KEY:"duplicate JSON key",
                          Code.JSON_NONFINITE_NUMBER:"non-finite JSON number"}[code])


class BindingFailure(ValueError):
    def __init__(self, code: Code, location):
        self.code, self.location = code, tuple(location)
        message = "claims must have sequential IDs and nonoverlapping source order" if code in {Code.BINDING_ID_SEQUENCE, Code.BINDING_OVERLAP} else "claim is not the exact original substring"
        super().__init__(message)


# Custom validator types are programmer-owned constants, not exception messages.
CUSTOM_ERRORS = {
    "claim_span_order":(Code.CLAIM_SPAN_ORDER, "end"),
    "claim_duplicate_uncertainty":(Code.CLAIM_DUPLICATE_UNCERTAINTY, "uncertainty"),
    "claim_reference_mismatch":(Code.CLAIM_REFERENCE_MISMATCH, "temporal_reference"),
    "claim_nonfactual_combination":(Code.CLAIM_NONFACTUAL_COMBINATION, None),
    "claim_evidence_not_applicable":(Code.CLAIM_EVIDENCE_NOT_APPLICABLE, "fresh_evidence"),
    "claim_uncertainty_missing":(Code.CLAIM_UNCERTAINTY_MISSING, "uncertainty"),
    "claim_uncertain_temporal_combination":(Code.CLAIM_UNCERTAIN_TEMPORAL_COMBINATION, None),
    "claim_dynamic_requires_fresh":(Code.CLAIM_DYNAMIC_REQUIRES_FRESH, "fresh_evidence"),
    "claim_non_dynamic_evidence":(Code.CLAIM_NON_DYNAMIC_EVIDENCE, "fresh_evidence")}
PYDANTIC_CODES = {
    "missing":Code.SCHEMA_MISSING_FIELD, "extra_forbidden":Code.SCHEMA_EXTRA_FIELD,
    "literal_error":Code.SCHEMA_LITERAL_INVALID,
    **{name:Code.SCHEMA_TYPE_INVALID for name in ("model_type", "dict_type", "list_type", "string_type", "int_type", "bool_type")},
    **{name:Code.SCHEMA_LIMIT for name in ("too_long", "too_short", "string_too_long", "string_too_short")},
    **{name:Code.SCHEMA_CONSTRAINT for name in ("greater_than", "greater_than_equal", "string_pattern_mismatch", "value_error")}}


def schema_details(error: ValidationError):
    issues = []
    # Pydantic input/context/URLs are explicitly excluded. Never copy msg/type
    # strings; only compare type with a fixed map and sanitize every loc token.
    for item in error.errors(include_input=False, include_context=False, include_url=False)[:MAX_ISSUES]:
        location = tuple(item["loc"])
        kind = item["type"]
        if kind in CUSTOM_ERRORS:
            code, field = CUSTOM_ERRORS[kind]
            if field is not None:
                location += (field,)
        else:
            code = PYDANTIC_CODES.get(kind, Code.SCHEMA_INVALID)
        issues.append(Issue(code, location))
    return FailureDetails(Stage.MODEL_SCHEMA, tuple(issues), error.error_count())
