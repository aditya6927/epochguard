"""Separate frozen 004F draft collection. Never opens the 004A held-out set."""

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from claim_analysis.schema import AnalysisInput, strict_json
from .schema import Frozen, Proposal

DATA = Path(__file__).resolve().parents[2] / "data/prose-v1"


def file_hash(path):
    # Git's text checkout conversion must not change dataset/source identity.
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class Gold(Frozen):
    source: Proposal
    policy_id: Literal["python-windows-latest-v1", "pypi-requests-reported-v1"] | None


class Case(Frozen):
    dataset_version: Literal["004f.dataset.v1"]
    case_id: str = Field(pattern=r"^eg004f-[0-9]{4}$")
    split: Literal["dev", "heldout"]
    text: str
    source_sha256: str
    reference_date: str
    tags: tuple[str, ...]
    gold: tuple[Gold, ...] = Field(max_length=8)
    expected_bounded_accounting: bool
    review_status: Literal["draft", "human_reviewed"]
    reviewer: str | None
    annotation_note: str

    @model_validator(mode="after")
    def validate_annotations(self):
        AnalysisInput(text=self.text, reference_date=self.reference_date)
        if hashlib.sha256(self.text.encode()).hexdigest() != self.source_sha256:
            raise ValueError("dataset source hash mismatch")
        if (self.review_status == "human_reviewed") != bool(self.reviewer and self.reviewer.strip()):
            raise ValueError("independent reviewer required")
        previous = 0
        for i, gold in enumerate(self.gold, 1):
            c = gold.source
            if c.claim_id != f"c{i:03d}" or c.start < previous or self.text[c.start:c.end] != c.source_text:
                raise ValueError("invalid gold binding")
            previous = c.end
        if self.expected_bounded_accounting and (not self.gold or any(g.policy_id is None for g in self.gold)):
            raise ValueError("invalid positive annotation")
        return self


def load(split="dev", *, directory=DATA, require_reviewed=False):
    if split not in {"dev", "heldout"}:
        raise ValueError("invalid split")
    directory = Path(directory)
    path = directory / f"{split}.jsonl"
    if path.stat().st_size > 512*1024:
        raise ValueError("dataset size bound")
    manifest = strict_json((directory / "manifest.json").read_bytes())
    if manifest["schema_version"] != "004f.dataset-manifest.v1" or manifest["files"][path.name] != file_hash(path):
        raise ValueError("frozen dataset hash mismatch")
    cases = []
    for line in path.read_bytes().splitlines():
        if line.strip():
            strict_json(line)
            cases.append(Case.model_validate_json(line))
    ids = [c.case_id for c in cases]
    if not cases or len(cases) > 100 or ids != manifest["splits"][split] or len(set(ids)) != len(ids) or any(c.split != split for c in cases):
        raise ValueError("invalid frozen split membership")
    if require_reviewed and any(c.review_status != "human_reviewed" for c in cases):
        raise ValueError("independent human review pending")
    return cases
