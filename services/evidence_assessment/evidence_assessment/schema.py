from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

MODE = "experimental-evidence"
Verdict = Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


def plain(value):
    if any(ord(c) < 32 and c not in "\n\t" for c in value) or any(0x202a <= ord(c) <= 0x202e or 0x2066 <= ord(c) <= 0x2069 for c in value):
        raise ValueError("invalid text")
    return value


class Request(Strict):
    claim: str = Field(min_length=1, max_length=512)

    @field_validator("claim")
    @classmethod
    def bounded(cls, value):
        plain(value)
        if len(value.encode("utf-8")) > 2048 or not value.strip():
            raise ValueError("invalid claim")
        return value


class Source(Strict):
    id: str = Field(pattern=r"^S[1-5]$")
    url: str = Field(max_length=2048)
    title: str = Field(min_length=1, max_length=240)
    snippet: str = Field(min_length=1, max_length=4000)
    publisher_group: str = Field(max_length=255)
    retrieved_at: AwareDatetime
    published_at: AwareDatetime | None
    publication_basis: Literal["provider_metadata_unverified", "unknown"]

    @field_validator("title", "snippet")
    @classmethod
    def text(cls, value):
        if not value.strip(): raise ValueError("empty source text")
        return plain(value)


class SourceAssessment(Strict):
    source_id: str = Field(pattern=r"^S[1-5]$")
    stance: Literal["SUPPORTS", "CONTRADICTS", "UNCLEAR", "IRRELEVANT"]
    quote: str = Field(max_length=600)


class ModelAssessment(Strict):
    claim: str = Field(min_length=1, max_length=512)
    scope: Literal["SINGLE_FACT", "MULTIPLE_CLAIMS", "AMBIGUOUS", "SUBJECTIVE", "CONTEXT_DEPENDENT", "UNANSWERABLE"]
    assessment: Verdict
    explanation: str = Field(min_length=1, max_length=900)
    uncertainty: list[str] = Field(max_length=5)
    independence_uncertain: bool
    source_assessments: list[SourceAssessment] = Field(min_length=1, max_length=5)
    citation_ids: list[str] = Field(max_length=5)

    @field_validator("explanation")
    @classmethod
    def text(cls, value):
        return plain(value)

    @field_validator("uncertainty")
    @classmethod
    def uncertainties(cls, values):
        if any(not value.strip() or len(value) > 180 for value in values):
            raise ValueError("uncertainty bound")
        return [plain(v) for v in values]


class Result(Strict):
    mode: Literal["experimental-evidence"] = MODE
    authorization: Literal[False] = False
    claim: str | None
    evidence_mode: Literal["simulated", "live"]
    assessment: Verdict = "INSUFFICIENT_EVIDENCE"
    reason_code: str = Field(pattern=r"^[A-Z_]{1,48}$")
    explanation: str = Field(min_length=1, max_length=1000)
    uncertainty: list[str] = Field(min_length=1, max_length=6)
    sources: list[Source] = Field(max_length=5)
    citation_ids: list[str] = Field(max_length=5)
    assessed_at: AwareDatetime

    @model_validator(mode="after")
    def coherent(self):
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("source ids")
        if len(set(self.citation_ids)) != len(self.citation_ids) or not set(self.citation_ids) <= {s.id for s in self.sources}:
            raise ValueError("citation binding")
        if self.assessment != "INSUFFICIENT_EVIDENCE" and (
            self.claim is None or len(self.citation_ids) < 2 or self.reason_code != "AI_EVIDENCE_ASSESSMENT"):
            raise ValueError("incomplete assessment")
        return self
