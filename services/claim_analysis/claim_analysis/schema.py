"""Independent 004a.v1 schema; never imported by the qualified verifier."""

from datetime import date
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
        if self.end <= self.start or len(set(self.uncertainty)) != len(self.uncertainty):
            raise ValueError("invalid span/repeated uncertainty")
        if self.temporal_reference is not None and (not self.temporal_reference or self.temporal_reference not in self.source_text):
            raise ValueError("temporal reference must be verbatim")
        if self.factuality == "NON_FACTUAL":
            if self.temporal != "UNCERTAIN" or self.fresh_evidence != "NOT_APPLICABLE":
                raise ValueError("non-factual unit cannot imply factual evidence policy")
        else:
            if self.fresh_evidence == "NOT_APPLICABLE":
                raise ValueError("checkable/uncertain statement needs evidence classification")
            if self.factuality == "UNCERTAIN" and not self.uncertainty:
                raise ValueError("uncertain factuality needs a reason")
            if self.temporal == "UNCERTAIN" and (not self.uncertainty or self.fresh_evidence == "NOT_REQUIRED"):
                raise ValueError("uncertain temporal scope cannot waive fresh evidence")
            if self.temporal == "DYNAMIC" and self.fresh_evidence != "REQUIRED":
                raise ValueError("dynamic facts need fresh evidence")
            if self.temporal in {"STABLE", "HISTORICAL"} and self.fresh_evidence != "NOT_REQUIRED":
                raise ValueError("inconsistent temporal requirement")
        return self


class Extraction(Strict):
    schema_version: Literal["004a.v1"]
    claims: list[Claim] = Field(max_length=MAX_CLAIMS)

    def bind(self, request: AnalysisInput):
        previous = 0
        for i, claim in enumerate(self.claims, 1):
            if claim.claim_id != f"c{i:03d}" or claim.start < previous:
                raise ValueError("claims must have sequential IDs and nonoverlapping source order")
            if claim.end > len(request.text) or request.text[claim.start:claim.end] != claim.source_text:
                raise ValueError("claim is not the exact original substring")
            previous = claim.end
        return self


def strict_json(data: str | bytes):
    if len(data.encode("utf-8") if isinstance(data, str) else data) > MAX_JSON:
        raise ValueError("JSON output bound exceeded")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("non-finite JSON number")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant)


def parse_extraction(data: str | bytes, request: AnalysisInput) -> Extraction:
    return Extraction.model_validate(strict_json(data)).bind(request)
