"""Strict immutable 004F records. Planning success is never authorization."""

from typing import Annotated, Literal
import json

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from claim_analysis.schema import AnalysisInput, Claim, Reason
from claim_analysis.validation_diagnostics import Stage, Code
from verifier.multiclaim.contract import Evidence, PolicyID, NumericVersion, ClaimReason
from verifier.policy import digest
from verifier.retrieval import unique_object

SCHEMA = "004f.prose-plan.v1"
POLICY = "bounded-prose-audit-v1"
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Status = Literal["PLAN_READY", "PLAN_UNCERTAIN", "PLAN_UNSUPPORTED", "ANALYSIS_FAILED"]
Failure = Literal["EXTRACTION_FAILED", "CLAIM_LIMIT", "DEADLINE", "BUSY", "OUTPUT_LIMIT"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True,
                              revalidate_instances="always", allow_inf_nan=False)


class Request(Frozen):
    schema_version: Literal["004f.prose-plan.v1"] = SCHEMA
    analysis_policy: Literal["bounded-prose-audit-v1"] = POLICY
    request_id: Identifier
    candidate: str
    candidate_sha256: Digest
    reference_date: str

    @model_validator(mode="after")
    def binding(self):
        AnalysisInput(text=self.candidate, reference_date=self.reference_date)
        if digest(self.candidate) != self.candidate_sha256:
            raise ValueError("candidate hash mismatch")
        return self


class Proposal(Claim):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True,
                              revalidate_instances="always")
    uncertainty: tuple[Reason, ...] = Field(max_length=6)


class Span(Frozen):
    source_text: Annotated[str, Field(min_length=1, max_length=8192)]
    start: Annotated[int, Field(ge=0, le=8192)]
    end: Annotated[int, Field(gt=0, le=8192)]

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start or self.end - self.start != len(self.source_text):
            raise ValueError("invalid source span")
        return self


class Unit(Span):
    unit_id: Annotated[str, Field(pattern=r"^u[0-9]{3}$")]
    kind: Literal["KNOWN_FACT", "NONFACTUAL_RULE", "POTENTIAL_FACT", "MIXED", "AMBIGUOUS", "UNRECOGNIZED", "LIMIT_TAIL"]
    reason: Literal["CLOSED_FORM", "EXPLICIT_NONFACTUAL", "UNSUPPORTED_PREDICATE", "COMPOUND_MARKER", "CONTEXT_OR_FORMAT", "UNKNOWN_CONTENT", "UNIT_LIMIT"]


class Mapping(Frozen):
    unit_id: str
    policy_id: PolicyID
    version: NumericVersion
    canonical_text: Annotated[str, Field(max_length=512)]


class Correspondence(Frozen):
    unit_id: str
    overlapping_claim_ids: tuple[str, ...] = Field(max_length=8)
    disposition: Literal["COVERED_FACT", "NONFACTUAL_RULE", "UNACCOUNTED", "UNSUPPORTED", "UNCERTAIN"]
    reason: Literal["EXACT_ATOMIC_MATCH", "EXPLICIT_NONFACTUAL", "MISSING_PROPOSAL", "CLASSIFICATION_CONFLICT", "NONATOMIC_OR_PARTIAL", "NO_SUPPORTED_POLICY", "AUDIT_UNCERTAIN"]


class ShadowObservation(Frozen):
    unit_id: str
    verdict: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT"]
    reason_code: ClaimReason
    evidence: tuple[Evidence, ...] = Field(max_length=1)
    checked_at: AwareDatetime


class Resources(Frozen):
    work_seconds: Annotated[float, Field(ge=.1, le=60)]
    elapsed_ms: Annotated[float, Field(ge=0)] | None
    extractor_ms: Annotated[float, Field(ge=0)] | None
    input_tokens: Annotated[int, Field(ge=0)] | None
    output_tokens: Annotated[int, Field(ge=0)] | None
    estimated_cost_usd: Annotated[float, Field(ge=0)] | None


class Result(Frozen):
    schema_version: Literal["004f.prose-plan.v1"] = SCHEMA
    analysis_policy: Literal["bounded-prose-audit-v1"] = POLICY
    request: Request
    authorization: Literal[False] = False
    semantic_completeness: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    extractor: Literal["baseline", "auditor", "fake-model", "gemini"]
    extractor_identity: Annotated[str, Field(min_length=1, max_length=128)]
    extractor_status: Literal["VALIDATED", "INDEPENDENT_ONLY", "FAILED"]
    failure_code: Failure | None
    diagnostic_stage: Stage | None
    diagnostic_code: Code | None
    proposals: tuple[Proposal, ...] = Field(max_length=8)
    risk_units: tuple[Unit, ...] = Field(max_length=64)
    correspondences: tuple[Correspondence, ...] = Field(max_length=64)
    policy_mappings: tuple[Mapping, ...] = Field(max_length=8)
    unaccounted_unit_ids: tuple[str, ...] = Field(max_length=64)
    unsupported_unit_ids: tuple[str, ...] = Field(max_length=64)
    coverage: Literal["BOUNDED_ACCOUNTED", "UNRESOLVED", "NO_ASSERTIONS"]
    syntactic_covered_characters: Annotated[int, Field(ge=0, le=8192)]
    overall_status: Status
    shadow_fixture: Literal[True] = True
    shadow_observations: tuple[ShadowObservation, ...] = Field(max_length=8)
    shadow_verdict: Literal["NOT_RUN", "MAPPED_CLAIMS_SUPPORTED", "MAPPED_CLAIM_CONTRADICTED", "MAPPED_CLAIMS_INSUFFICIENT"]
    resources: Resources

    @field_validator("authorization", mode="before")
    @classmethod
    def never_authorize(cls, value):
        if value is not False:
            raise ValueError("analysis cannot authorize")
        return value

    @field_validator("shadow_fixture", mode="before")
    @classmethod
    def only_fixture(cls, value):
        if value is not True:
            raise ValueError("shadow must be explicitly fixture-only")
        return value

    @model_validator(mode="after")
    def consistent(self):
        from .audit import derive, shadow_status
        from claim_analysis.schema import Extraction
        from verifier.multiclaim.coverage import qualify
        from verifier.multiclaim.contract import ClaimResult

        analysis = AnalysisInput(text=self.request.candidate, reference_date=self.request.reference_date)
        source = Extraction.model_validate({"schema_version": "004a.v1", "claims": [
            {**c.model_dump(), "uncertainty": list(c.uncertainty)} for c in self.proposals]})
        source.bind(analysis)
        for claim in self.proposals:
            if analysis.text.find(claim.source_text) != analysis.text.rfind(claim.source_text):
                raise ValueError("ambiguous proposal occurrence")
        expected = derive(self.request.candidate, self.proposals, self.failure_code)
        for key, value in expected.items():
            if getattr(self, key) != value:
                raise ValueError("inconsistent independent audit")
        if (self.extractor_status == "FAILED") != (self.failure_code is not None):
            raise ValueError("failure status mismatch")
        if (self.diagnostic_stage is None) != (self.diagnostic_code is None) or (self.failure_code is None and self.diagnostic_stage is not None):
            raise ValueError("diagnostic mismatch")
        if self.failure_code is not None and self.proposals:
            raise ValueError("failed extraction cannot retain accepted proposals")
        if self.extractor_status == "INDEPENDENT_ONLY" and self.extractor != "auditor":
            raise ValueError("invalid extractor identity")
        mappings = {m.unit_id: m for m in self.policy_mappings}
        ids = [o.unit_id for o in self.shadow_observations]
        if ids and ids != [m.unit_id for m in self.policy_mappings]:
            raise ValueError("incomplete shadow observations")
        for observation in self.shadow_observations:
            mapping = mappings[observation.unit_id]
            bound, _ = qualify(mapping.canonical_text)
            if any(e.retrieval_mode != "fixture" for e in observation.evidence):
                raise ValueError("shadow accepts fixture observations only")
            if any(not -2 <= (observation.checked_at - e.observed_at).total_seconds() <= 60 for e in observation.evidence):
                raise ValueError("invalid shadow observation age")
            ClaimResult(claim=bound[0], verdict=observation.verdict, reason_code=observation.reason_code,
                        evidence_requirements_satisfied=bool(observation.evidence), evidence=list(observation.evidence))
        if self.shadow_verdict != shadow_status(self.shadow_observations):
            raise ValueError("invalid shadow summary")
        return self


def parse_request(data: bytes | str):
    from claim_analysis.schema import strict_json
    strict_json(data)
    return Request.model_validate_json(data)


def parse_result(data: bytes | str):
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > 256*1024:
        raise ValueError("analysis output bound")

    def nonfinite(_):
        raise ValueError("nonfinite JSON")

    # Reuse the existing duplicate-key guard. Validation from JSON preserves
    # strict tuple/date decoding without accepting Python coercions.
    json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=nonfinite)
    return Result.model_validate_json(raw)
