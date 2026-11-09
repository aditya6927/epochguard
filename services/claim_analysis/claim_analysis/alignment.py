"""Strict identification wire format and exact, conservative source alignment."""

from copy import deepcopy
from typing import Literal

from pydantic import Field, create_model

from .schema import AnalysisInput, Claim, Extraction, MAX_CLAIMS, Strict, strict_json
from .validation_diagnostics import AlignmentFailure, Code

IDENTIFICATION_SCHEMA = "004a.identification.v1"

# Reuse canonical field types/limits without inheriting validators that reference
# offsets. All canonical cross-field validators run after offsets are calculated.
IdentifiedClaim = create_model(
    "IdentifiedClaim", __base__=Strict,
    **{name:(field.annotation, deepcopy(field)) for name,field in Claim.model_fields.items()
       if name not in {"start", "end"}})


class Identification(Strict):
    schema_version: Literal["004a.identification.v1"]
    claims: list[IdentifiedClaim] = Field(max_length=MAX_CLAIMS)


def align(identified: Identification, request: AnalysisInput) -> Extraction:
    claims = []
    previous_start, previous_end = -1, 0
    for i, claim in enumerate(identified.claims):
        location = ("claims", i, "source_text")
        start = request.text.find(claim.source_text)
        if start < 0:
            raise AlignmentFailure(Code.ALIGNMENT_TEXT_NOT_FOUND, location)
        # Search from start+1 to detect overlapping occurrences too. Never
        # select first/nth/next occurrence based on provider ordering or context.
        if request.text.find(claim.source_text, start+1) >= 0:
            raise AlignmentFailure(Code.ALIGNMENT_AMBIGUOUS, location)
        end = start + len(claim.source_text)
        if start < previous_start:
            raise AlignmentFailure(Code.ALIGNMENT_OUT_OF_ORDER, location)
        if start < previous_end:
            raise AlignmentFailure(Code.ALIGNMENT_OVERLAP, location)
        claims.append({**claim.model_dump(), "start":start, "end":end})
        previous_start, previous_end = start, end
    # No claims removed, paraphrases substituted, or classifications changed.
    # This is the same canonical contract and final source-binding boundary.
    return Extraction.model_validate({"schema_version":"004a.v1", "claims":claims}).bind(request)


def parse_identification(data: str | bytes, request: AnalysisInput) -> Extraction:
    return align(Identification.model_validate(strict_json(data)), request)
