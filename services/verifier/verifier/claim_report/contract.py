"""005D diagnostic output; never an enforcement or receipt input."""
from typing import Literal
from datetime import timedelta
from pydantic import AwareDatetime, Field, field_validator, model_validator
from verifier.contract import Digest, SOURCE_URL
from verifier.multiclaim.contract import Strict, PolicyID, Outcome, NumericVersion, PYTHON_POLICY, PYPI_URL

ScoreReason = Literal["MATCHED_OBSERVATION", "OLDER_THAN_OBSERVATION", "CLAIM_AHEAD_OF_SOURCE",
    "MISSING_EVIDENCE", "INSUFFICIENT_EVIDENCE", "AMBIGUOUS_EVIDENCE", "STALE_OBSERVATION",
    "RETRIEVAL_FAILURE", "RETRIEVAL_TIMEOUT", "VERIFIER_ERROR", "SOURCE_MODE_MISMATCH",
    "INVALID_RECORD", "NOT_RECORDED"]
ReportReason = Literal["VALIDATED_RESULT", "UNSUPPORTED_LANGUAGE", "INVALID_RECORD", "NOT_RECORDED",
                       "REPORT_UNAVAILABLE", "INCOMPLETE_EVIDENCE"]
Mode = Literal["fixture", "tavily_live", "pypi_live"]
Profile = Literal["fixture", "live"]


def observation_time(observed, evaluated):
    delta = evaluated - observed
    status = ("INVALID" if not timedelta(seconds=-2) <= delta <= timedelta(seconds=60)
              else "FUTURE_WITHIN_TOLERANCE" if delta < timedelta(0) else "MEASURED")
    return status, delta // timedelta(milliseconds=1) if status == "MEASURED" else None


class ClaimEntry(Strict):
    claim_id: str = Field(pattern=r"^c00[1-8]$")
    claim_index: int = Field(ge=1, le=8)
    policy_id: PolicyID
    candidate_sha256: Digest
    coverage: Literal["COMPLETE", "UNCERTAIN"]
    verdict: Outcome
    freshness_score: Literal[0, 100] | None
    score_reason: ScoreReason
    evidence_mode: Mode | None = None
    source_id: Literal["python-windows", "pypi-requests"]
    source_url: Literal["https://www.python.org/downloads/windows/", "https://pypi.org/pypi/requests/json"] | None = None
    observed_at: AwareDatetime | None = None
    evaluated_at: AwareDatetime | None = None
    observation_age_ms: int | None = Field(default=None, ge=0, le=60000)
    observation_time_status: Literal["MEASURED", "FUTURE_WITHIN_TOLERANCE", "INVALID", "NOT_RECORDED"] = "NOT_RECORDED"
    observed_version: NumericVersion | None = None
    evidence_digest: Digest | None = None
    origin_published_at: None = None

    @field_validator("freshness_score", mode="before")
    @classmethod
    def score_type(cls, value):
        if value is not None and (type(value) is not int or value not in (0, 100)):
            raise ValueError("score type")
        return value

    @model_validator(mode="after")
    def consistent(self):
        python = self.policy_id == PYTHON_POLICY
        if self.claim_id != f"c{self.claim_index:03d}" or self.source_id != ("python-windows" if python else "pypi-requests"):
            raise ValueError("claim identity")
        if self.source_url is not None and self.source_url != (SOURCE_URL if python else PYPI_URL):
            raise ValueError("policy source")
        if self.evidence_mode is not None and self.evidence_mode not in {"fixture", "tavily_live" if python else "pypi_live"}:
            raise ValueError("policy mode")
        if self.observed_at is not None and self.evaluated_at is not None:
            status, age_ms = observation_time(self.observed_at, self.evaluated_at)
            if self.observation_time_status != status or self.observation_age_ms != age_ms:
                raise ValueError("observation age")
        elif self.observation_age_ms is not None or self.observation_time_status != "NOT_RECORDED":
            raise ValueError("unmeasured age")
        if self.freshness_score is not None:
            if type(self.freshness_score) is not int or self.coverage != "COMPLETE":
                raise ValueError("score coverage")
            expected = ("SUPPORTED", "MATCHED_OBSERVATION") if self.freshness_score == 100 else ("CONTRADICTED", "OLDER_THAN_OBSERVATION")
            if (self.verdict, self.score_reason) != expected or self.observation_time_status not in {"MEASURED", "FUTURE_WITHIN_TOLERANCE"}:
                raise ValueError("score verdict")
            if any(v is None for v in (self.source_url, self.evidence_mode, self.observed_at, self.evaluated_at, self.observed_version, self.evidence_digest)):
                raise ValueError("score evidence")
        elif self.score_reason in {"MATCHED_OBSERVATION", "OLDER_THAN_OBSERVATION"}:
            raise ValueError("missing score")
        return self


class Report(Strict):
    schema_version: Literal["005d.claim-report.v1"] = "005d.claim-report.v1"
    authorization: Literal[False] = False
    basis: Literal["python_result_diagnostic", "qualification_diagnostic", "invalid_input"]
    report_status: Literal["COMPLETE", "INCOMPLETE"]
    report_reason: ReportReason
    input_sha256: Digest | None = None
    record_index: int | None = Field(default=None, ge=0, le=15)
    evidence_profile: Profile
    candidate_sha256: Digest | None = None
    coverage: Literal["COMPLETE", "UNCERTAIN"] = "UNCERTAIN"
    verdict: Outcome = "INSUFFICIENT"
    generated_at: AwareDatetime
    evaluated_at: AwareDatetime | None = None
    claims: list[ClaimEntry] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def bindings(self):
        if [c.claim_index for c in self.claims] != list(range(1, len(self.claims)+1)):
            raise ValueError("claim order")
        if any(c.candidate_sha256 != self.candidate_sha256 or c.evaluated_at != self.evaluated_at for c in self.claims):
            raise ValueError("report binding")
        if self.basis != "python_result_diagnostic" and any(c.freshness_score is not None for c in self.claims):
            raise ValueError("incomplete provenance cannot score")
        for claim in self.claims:
            if claim.freshness_score is not None and claim.evidence_mode != ("fixture" if self.evidence_profile == "fixture" else "tavily_live" if claim.policy_id == PYTHON_POLICY else "pypi_live"):
                raise ValueError("score profile")
        return self
