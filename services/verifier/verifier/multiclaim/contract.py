"""Strict experimental records; metadata describes observations, not attestations."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from claim_analysis.schema import AnalysisInput, Claim, Extraction
from verifier.contract import Digest, Reason as PythonReason, SOURCE_URL
from verifier.policy import digest

POLICY = "multi-claim-templates-v1"
PYTHON_POLICY = "python-windows-latest-v1"
PYPI_POLICY = "pypi-requests-reported-v1"
PYPI_URL = "https://pypi.org/pypi/requests/json"
MAX_CLAIMS = 8
PolicyID = Literal["python-windows-latest-v1", "pypi-requests-reported-v1"]
Outcome = Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT"]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
NumericVersion = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})$")]
ClaimReason = PythonReason | Literal["MATCHED_PYPI_VERSION", "OLDER_THAN_PYPI_VERSION"]
CoverageReason = Literal["EXACT_TEMPLATES", "UNRECOGNIZED_CONTENT", "NO_CLAIMS",
                         "CLAIM_LIMIT", "REPEATED_CLAIM", "HASH_MISMATCH",
                         "EXTRACTION_FAILURE", "SOURCE_BINDING_FAILURE", "EXTRACTION_CONFLICT"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


class Request(Strict):
    schema_version: Literal["004b.v1"] = "004b.v1"
    policy_id: Literal["multi-claim-templates-v1"] = POLICY
    request_id: Identifier
    candidate: Annotated[str, Field(max_length=8192)]
    candidate_sha256: Digest
    extraction: Extraction | None = None

    @model_validator(mode="after")
    def bounded(self):
        # Reuse 004A's UTF-8, control-character and character limits unchanged.
        AnalysisInput(text=self.candidate, reference_date="2026-11-12")
        if self.extraction is not None and len(self.extraction.claims) > MAX_CLAIMS:
            raise ValueError("claim limit")
        return self


class BoundClaim(Strict):
    source: Claim
    candidate_sha256: Digest
    policy_id: PolicyID
    version: NumericVersion


class Evidence(Strict):
    evidence_id: Digest
    url: Literal["https://www.python.org/downloads/windows/", "https://pypi.org/pypi/requests/json"]
    retrieval_mode: Literal["fixture", "tavily_live", "pypi_live"]
    retrieval_id: Identifier
    content_sha256: Digest
    observed_version: NumericVersion
    retrieved_at: AwareDatetime
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def identity(self):
        if self.observed_at != self.retrieved_at:
            raise ValueError("observation time mismatch")
        identity = f"{self.url}|{self.retrieval_mode}|{self.retrieval_id}|{self.content_sha256}"
        if self.evidence_id != digest(identity):
            raise ValueError("evidence identifier mismatch")
        return self


class ClaimResult(Strict):
    claim: BoundClaim
    verdict: Outcome
    reason_code: ClaimReason
    evidence_requirements_satisfied: bool
    evidence: list[Evidence] = Field(max_length=1)

    @model_validator(mode="after")
    def consistent(self):
        python = self.claim.policy_id == PYTHON_POLICY
        for evidence in self.evidence:
            if evidence.url != (SOURCE_URL if python else PYPI_URL):
                raise ValueError("policy source mismatch")
            if evidence.retrieval_mode not in {"fixture", "tavily_live" if python else "pypi_live"}:
                raise ValueError("policy retrieval mode mismatch")
        if self.evidence_requirements_satisfied != (len(self.evidence) == 1):
            raise ValueError("evidence requirements mismatch")
        if self.evidence:
            observed = tuple(map(int, self.evidence[0].observed_version.split(".")))
            candidate = tuple(map(int, self.claim.version.split(".")))
            expected = (("SUPPORTED", "MATCHED_PRIMARY_LABEL" if python else "MATCHED_PYPI_VERSION")
                        if candidate == observed else
                        ("CONTRADICTED", "OLDER_THAN_PRIMARY_LABEL" if python else "OLDER_THAN_PYPI_VERSION")
                        if candidate < observed else ("INSUFFICIENT", "CLAIM_AHEAD_OF_SOURCE"))
            if (self.verdict, self.reason_code) != expected:
                raise ValueError("comparison mismatch")
        elif self.verdict != "INSUFFICIENT" or self.reason_code in {
            "MATCHED_PRIMARY_LABEL", "MATCHED_PYPI_VERSION", "OLDER_THAN_PRIMARY_LABEL",
            "OLDER_THAN_PYPI_VERSION", "CLAIM_AHEAD_OF_SOURCE",
        }:
            raise ValueError("missing evidence")
        return self


class Coverage(Strict):
    status: Literal["COMPLETE", "UNCERTAIN"]
    reason_code: CoverageReason
    required_claim_ids: list[Annotated[str, Field(pattern=r"^c[0-9]{3}$")]] = Field(max_length=MAX_CLAIMS)

    @model_validator(mode="after")
    def consistent(self):
        if self.status == "COMPLETE":
            if self.reason_code != "EXACT_TEMPLATES" or not self.required_claim_ids:
                raise ValueError("invalid complete coverage")
        elif self.reason_code == "EXACT_TEMPLATES" or self.required_claim_ids:
            raise ValueError("invalid uncertain coverage")
        if self.required_claim_ids != [f"c{i:03d}" for i in range(1, len(self.required_claim_ids)+1)]:
            raise ValueError("invalid required IDs")
        return self


class Result(Strict):
    schema_version: Literal["004b.v1"] = "004b.v1"
    policy_id: Literal["multi-claim-templates-v1"] = POLICY
    request_id: Identifier
    candidate: Annotated[str, Field(max_length=8192)]
    candidate_sha256: Digest
    extraction_status: Literal["TRUSTED_GRAMMAR", "VALIDATED", "FAILED", "NOT_RUN"]
    binding_status: Literal["VALID", "FAILED", "NOT_RUN"]
    extraction: Extraction | None
    coverage: Coverage
    claims: list[ClaimResult] = Field(max_length=MAX_CLAIMS)
    verdict: Outcome
    checked_at: AwareDatetime

    @model_validator(mode="after")
    def consistent(self):
        # This also catches missing, duplicate, reordered or stale claim results.
        from .coverage import qualify
        from .pipeline import aggregate, agrees
        if self.claims:
            if self.binding_status != "VALID" or self.extraction is None:
                raise ValueError("unbound results")
            analysis = AnalysisInput(text=self.candidate, reference_date=self.checked_at.date().isoformat())
            Extraction.model_validate(self.extraction.model_dump(warnings=False)).bind(analysis)
        required, coverage = qualify(self.candidate)
        if self.coverage.status == "COMPLETE":
            if self.extraction_status not in {"TRUSTED_GRAMMAR", "VALIDATED"} or self.binding_status != "VALID":
                raise ValueError("incomplete extraction or binding")
            if self.candidate_sha256 != digest(self.candidate) or coverage != self.coverage:
                raise ValueError("coverage binding mismatch")
            if self.extraction is None or not agrees(self.extraction, required):
                raise ValueError("extraction coverage mismatch")
        expected = aggregate(required if self.coverage.status == "COMPLETE" else [], self.claims,
                             self.coverage, self.checked_at)
        if self.verdict != expected:
            raise ValueError("aggregation mismatch")
        return self
