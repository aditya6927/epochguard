"""Validate annotations before scoring; draft review state is never implicit."""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .schema import AnalysisInput, Extraction, Strict, strict_json

DATA = Path(__file__).resolve().parent.parent / "data" / "v1"


class Case(Strict):
    dataset_version: Literal["004a.dataset.v1"]
    case_id: str = Field(pattern=r"^eg004a-[0-9]{4}$")
    split: Literal["dev", "heldout"]
    domain: str
    tags: list[str]
    reference_date: str
    text: str
    expected_outcome: Literal["ANALYZED", "INVALID_INPUT"]
    gold: Extraction
    review_status: Literal["pending", "human_reviewed"]
    reviewer: str | None
    annotation_note: str = Field(min_length=1)

    @model_validator(mode="after")
    def annotations(self):
        if (self.review_status == "human_reviewed") != bool(self.reviewer and self.reviewer.strip()):
            raise ValueError("human review requires a named reviewer; draft must not claim one")
        try:
            request = AnalysisInput(text=self.text, reference_date=self.reference_date)
        except ValueError:
            if self.expected_outcome != "INVALID_INPUT" or self.gold.claims:
                raise ValueError("invalid input annotation") from None
        else:
            if self.expected_outcome != "ANALYZED":
                raise ValueError("expected invalid input is actually valid")
            self.gold.bind(request)
        return self


def load(path: Path, *, require_reviewed=False) -> list[Case]:
    cases = [Case.model_validate(strict_json(line)) for line in path.read_bytes().splitlines() if line.strip()]
    if not cases or len({c.case_id for c in cases}) != len(cases):
        raise ValueError("empty dataset or duplicate case ID")
    if require_reviewed and any(c.review_status != "human_reviewed" for c in cases):
        raise ValueError("independent human review pending")
    return cases
