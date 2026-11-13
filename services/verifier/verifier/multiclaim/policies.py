"""Trusted dispatch; only deterministic source-specific comparisons issue verdicts."""

import json
import re

from verifier.contract import POLICY as OLD_POLICY, SCHEMA as OLD_SCHEMA, SOURCE_URL, VerificationRequest
from verifier.policy import digest, verify as verify_python
from verifier.retrieval import Page, RetrievalFailure, RetrievalTimeout, unique_object

from .contract import ClaimResult, Evidence, NumericVersion, PYTHON_POLICY, PYPI_URL
from .retrieval import MAX_EVIDENCE_BYTES
from pydantic import TypeAdapter

VERSION = TypeAdapter(NumericVersion)


def insufficient(claim, reason):
    return ClaimResult(claim=claim, verdict="INSUFFICIENT", reason_code=reason,
                       evidence_requirements_satisfied=False, evidence=[])


def reference(page, version):
    content_hash = digest(page.content)
    identity = f"{page.url}|{page.retrieval_mode}|{page.retrieval_id}|{content_hash}"
    return Evidence(evidence_id=digest(identity), url=page.url, retrieval_mode=page.retrieval_mode,
                    retrieval_id=page.retrieval_id, content_sha256=content_hash,
                    observed_version=version, retrieved_at=page.retrieved_at, observed_at=page.retrieved_at)


def validate_page(page, *, python, fixture):
    if not isinstance(page, Page) or page.url != (SOURCE_URL if python else PYPI_URL):
        raise RetrievalFailure()
    expected_mode = "fixture" if fixture else "tavily_live" if python else "pypi_live"
    if page.retrieval_mode != expected_mode:
        raise RetrievalFailure()
    if not isinstance(page.content, str) or not 1 <= len(page.content.encode("utf-8")) <= MAX_EVIDENCE_BYTES:
        raise RetrievalFailure()
    if not isinstance(page.retrieval_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", page.retrieval_id):
        raise RetrievalFailure()
    if page.retrieved_at.tzinfo is None:
        raise RetrievalFailure()
    return page


class GuardedRetriever:
    def __init__(self, source, *, python, fixture):
        self.source, self.python, self.fixture = source, python, fixture
        self.page = None

    async def retrieve(self):
        self.page = validate_page(await self.source.retrieve(), python=self.python, fixture=self.fixture)
        return self.page


def pypi_version(content):
    def invalid_constant(_):
        raise ValueError("invalid constant")
    data = json.loads(content, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    if not isinstance(data, dict) or not isinstance(data.get("info"), dict):
        raise ValueError("invalid envelope")
    info = data["info"]
    # Other metadata (description, links, instructions) is never consulted.
    if info.get("name") != "requests" or info.get("yanked") is not False:
        raise ValueError("unresolved project identity or yanked observation")
    return VERSION.validate_python(info.get("version"), strict=True)


async def verify_claim(claim, source, *, request_id, fixture, clock):
    python = claim.policy_id == PYTHON_POLICY
    retriever = GuardedRetriever(source, python=python, fixture=fixture)
    if python:
        # The qualified parser, label extraction, ordering and reason rules are reused intact.
        request = VerificationRequest(schema_version=OLD_SCHEMA, policy_id=OLD_POLICY,
                                      request_id=request_id, candidate=claim.source.source_text,
                                      candidate_sha256=digest(claim.source.source_text))
        old = await verify_python(request, retriever, clock=clock)
        evidence = [reference(retriever.page, old.evidence[0].observed_version)] if old.evidence else []
        return ClaimResult(claim=claim, verdict=old.verdict, reason_code=old.reason_code,
                           evidence_requirements_satisfied=bool(evidence), evidence=evidence)
    try:
        page = await retriever.retrieve()
        if not -2 <= (clock() - page.retrieved_at).total_seconds() <= 60:
            return insufficient(claim, "STALE_OBSERVATION")
        try:
            observed = pypi_version(page.content)
        except (ValueError, TypeError, RecursionError):
            return insufficient(claim, "INSUFFICIENT_EVIDENCE")
        evidence = reference(page, observed)
        candidate, current = tuple(map(int, claim.version.split("."))), tuple(map(int, observed.split(".")))
        verdict, reason = (("SUPPORTED", "MATCHED_PYPI_VERSION") if candidate == current else
                           ("CONTRADICTED", "OLDER_THAN_PYPI_VERSION") if candidate < current else
                           ("INSUFFICIENT", "CLAIM_AHEAD_OF_SOURCE"))
        return ClaimResult(claim=claim, verdict=verdict, reason_code=reason,
                           evidence_requirements_satisfied=True, evidence=[evidence])
    except RetrievalTimeout:
        return insufficient(claim, "RETRIEVAL_TIMEOUT")
    except RetrievalFailure:
        return insufficient(claim, "RETRIEVAL_FAILURE")
