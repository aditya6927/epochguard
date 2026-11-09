"""Independent 004a.v1 schema; never imported by the qualified verifier."""

from datetime import date
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from .validation_diagnostics import BindingFailure, Code, JSONFailure

MAX_CHARS, MAX_BYTES, MAX_JSON, MAX_CLAIMS = 8192, 32768, 65536, 64
SCHEMA = "004a.v1"
Factuality = Literal["FACTUAL", "NON_FACTUAL", "UNCERTAIN"]
Temporal = Literal["DYNAMIC", "HISTORICAL", "STABLE", "UNCERTAIN"]
Fresh = Literal["REQUIRED", "NOT_REQUIRED", "UNCERTAIN", "NOT_APPLICABLE"]
Reason = Literal["MISSING_CONTEXT", "AMBIGUOUS_REFERENCE", "MIXED_REQUIREMENTS",
                 "MODEL_ABSTENTION", "BASELINE_HEURISTIC", "UNTRUSTED_INSTRUCTION"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AnalysisInput(Strict):
    schema_version: Literal["004a.v1"] = SCHEMA
    text: Annotated[str, Field(max_length=MAX_CHARS)]
    reference_date: str

    @field_validator("reference_date")
    @classmethod
    def valid_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("reference date must be YYYY-MM-DD")
        return value

    @field_validator("text")
    @classmethod
    def valid_text(cls, value):
        if len(value.encode("utf-8")) > MAX_BYTES:
            raise ValueError("UTF-8 input bound exceeded")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError("invalid control character")
        return value


class Claim(Strict):
    claim_id: Annotated[str, Field(pattern=r"^c[0-9]{3}$")]
    source_text: Annotated[str, Field(min_length=1, max_length=MAX_CHARS)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    normalized_proposition: Annotated[str, Field(max_length=MAX_CHARS)] | None
    factuality: Factuality
    temporal: Temporal
    fresh_evidence: Fresh
    uncertainty: list[Reason] = Field(max_length=6)
    temporal_reference: Annotated[str, Field(max_length=160)] | None

    @model_validator(mode="after")
    def consistent(self):
        if self.end <= self.start:
            raise PydanticCustomError("claim_span_order", "invalid span order")
        if len(set(self.uncertainty)) != len(self.uncertainty):
            raise PydanticCustomError("claim_duplicate_uncertainty", "repeated uncertainty")
        if self.temporal_reference is not None and (not self.temporal_reference or self.temporal_reference not in self.source_text):
            raise PydanticCustomError("claim_reference_mismatch", "temporal reference must be verbatim")
        if self.factuality == "NON_FACTUAL":
            if self.temporal != "UNCERTAIN" or self.fresh_evidence != "NOT_APPLICABLE":
                raise PydanticCustomError("claim_nonfactual_combination", "non-factual unit cannot imply factual evidence policy")
        else:
            if self.fresh_evidence == "NOT_APPLICABLE":
                raise PydanticCustomError("claim_evidence_not_applicable", "checkable/uncertain statement needs evidence classification")
            if self.factuality == "UNCERTAIN" and not self.uncertainty:
                raise PydanticCustomError("claim_uncertainty_missing", "uncertain factuality needs a reason")
            if self.temporal == "UNCERTAIN" and (not self.uncertainty or self.fresh_evidence == "NOT_REQUIRED"):
                raise PydanticCustomError("claim_uncertain_temporal_combination", "uncertain temporal scope cannot waive fresh evidence")
            if self.temporal == "DYNAMIC" and self.fresh_evidence != "REQUIRED":
                raise PydanticCustomError("claim_dynamic_requires_fresh", "dynamic facts need fresh evidence")
            if self.temporal in {"STABLE", "HISTORICAL"} and self.fresh_evidence != "NOT_REQUIRED":
                raise PydanticCustomError("claim_non_dynamic_evidence", "inconsistent temporal requirement")
        return self


class Extraction(Strict):
    schema_version: Literal["004a.v1"]
    claims: list[Claim] = Field(max_length=MAX_CLAIMS)

    def bind(self, request: AnalysisInput):
        previous = 0
        for i, claim in enumerate(self.claims, 1):
            if claim.claim_id != f"c{i:03d}":
                raise BindingFailure(Code.BINDING_ID_SEQUENCE, ("claims", i-1, "claim_id"))
            if claim.start < previous:
                raise BindingFailure(Code.BINDING_OVERLAP, ("claims", i-1, "start"))
            if claim.end > len(request.text):
                raise BindingFailure(Code.BINDING_RANGE, ("claims", i-1, "end"))
            if request.text[claim.start:claim.end] != claim.source_text:
                raise BindingFailure(Code.BINDING_TEXT_MISMATCH, ("claims", i-1, "source_text"))
            previous = claim.end
        return self


def strict_json(data: str | bytes):
    if len(data.encode("utf-8") if isinstance(data, str) else data) > MAX_JSON:
        raise JSONFailure(Code.OUTPUT_TOO_LARGE)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise JSONFailure(Code.JSON_DUPLICATE_KEY)
            result[key] = value
        return result

    def invalid_constant(_):
        raise JSONFailure(Code.JSON_NONFINITE_NUMBER)

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def parse_extraction(data: str | bytes, request: AnalysisInput) -> Extraction:
    return Extraction.model_validate(strict_json(data)).bind(request)
