"""Outer original-response binding plus unchanged 004B evidence contract."""

from typing import Literal
from pydantic import Field, model_validator
from claim_analysis.schema import AnalysisInput
from verifier.contract import Digest
from verifier.policy import digest
from verifier.multiclaim.contract import Strict, Identifier, Result as EvidenceResult
from .grammar import Mapping, parse, comparison_text

SCHEMA = "004g.v1"
POLICY = "bounded-prose-v1"


class Request(Strict):
    schema_version: Literal["004g.v1"] = SCHEMA
    policy_id: Literal["bounded-prose-v1"] = POLICY
    request_id: Identifier
    candidate: str = Field(max_length=8192)
    candidate_sha256: Digest

    @model_validator(mode="after")
    def bounded(self):
        AnalysisInput(text=self.candidate, reference_date="2026-11-15")
        if digest(self.candidate) != self.candidate_sha256:
            raise ValueError("candidate binding mismatch")
        return self


class Result(Request):
    coverage: Literal["COMPLETE", "UNCERTAIN"]
    reason_code: Literal["BOUNDED_GRAMMAR", "UNRECOGNIZED_CONTENT", "REPEATED_CLAIM", "CLAIM_LIMIT", "NO_CLAIMS"]
    mappings: list[Mapping] = Field(max_length=8)
    verification: EvidenceResult | None

    @model_validator(mode="after")
    def consistent(self):
        mappings, reason = parse(self.candidate)
        if self.mappings != mappings or self.reason_code != reason:
            raise ValueError("grammar mismatch")
        if not mappings:
            if self.coverage != "UNCERTAIN" or self.verification is not None:
                raise ValueError("unrecognized response")
        else:
            v = self.verification
            text = comparison_text(mappings)
            if self.coverage != "COMPLETE" or v is None or v.candidate != text or v.candidate_sha256 != digest(text) or v.request_id != self.request_id:
                raise ValueError("evidence binding mismatch")
            # Require every result, including explicit missing-evidence records.
            if len(v.claims) != len(mappings) or [r.claim.source.claim_id for r in v.claims] != [m.claim_id for m in mappings]:
                raise ValueError("incomplete evidence results")
        return self
