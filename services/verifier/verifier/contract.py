"""003A's deliberately narrow wire contract. No free-form decision instructions."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

SCHEMA = "003a.v1"
POLICY = "python-windows-latest-v1"
SOURCE_URL = "https://www.python.org/downloads/windows/"
VERSION_PATTERN = r"3\.(?:0|[1-9][0-9]?)\.(?:0|[1-9][0-9]{0,2})"
Version = Annotated[str, Field(pattern="^" + VERSION_PATTERN + "$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Reason = Literal[
    "MATCHED_PRIMARY_LABEL", "OLDER_THAN_PRIMARY_LABEL", "CLAIM_AHEAD_OF_SOURCE",
    "UNSUPPORTED_CLAIM", "INSUFFICIENT_EVIDENCE", "AMBIGUOUS_EVIDENCE",
    "RETRIEVAL_TIMEOUT", "RETRIEVAL_FAILURE", "VERIFIER_ERROR", "STALE_OBSERVATION",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class VerificationRequest(StrictModel):
    schema_version: Literal["003a.v1"]
    policy_id: Literal["python-windows-latest-v1"]
    request_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    candidate: Annotated[str, Field(min_length=1, max_length=512)]
    candidate_sha256: Digest


class Claim(StrictModel):
    kind: Literal["python_windows_latest_stable"] = "python_windows_latest_stable"
    version: Version


class Evidence(StrictModel):
    url: Literal["https://www.python.org/downloads/windows/"] = SOURCE_URL
    retrieval_mode: Literal["fixture", "tavily_live"]
    content_sha256: Digest
    retrieved_at: AwareDatetime
    observed_at: AwareDatetime
    retrieval_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    observed_version: Version
    excerpt: Annotated[str, Field(min_length=1, max_length=160)]


class VerificationResponse(StrictModel):
    schema_version: Literal["003a.v1"] = SCHEMA
    policy_id: Literal["python-windows-latest-v1"] = POLICY
    request_id: str
    candidate_sha256: Digest
    claim: Claim | None
    verdict: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT"]
    reason_code: Reason
    evidence: list[Evidence] = Field(max_length=1)
    checked_at: AwareDatetime
