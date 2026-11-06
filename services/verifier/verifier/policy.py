"""Exact claim and primary-label comparison; retrieved instructions are data."""

from datetime import datetime, timezone
import hashlib
import re

from .contract import Claim, Evidence, VerificationRequest, VerificationResponse, VERSION_PATTERN, SOURCE_URL
from .retrieval import RetrievalFailure, RetrievalTimeout

CLAIM_RE = re.compile(
    r"The latest stable Python 3 release for Windows listed on Python\.org is ("
    + VERSION_PATTERN + r")\."
)
LABEL_RE = re.compile(r"(?:[-*•] )?Latest Python 3 Release - Python (" + VERSION_PATTERN + r")")


class MissingLabel(ValueError):
    pass


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claim_text(version: str) -> str:
    return f"The latest stable Python 3 release for Windows listed on Python.org is {version}."


def primary_label(content: str) -> tuple[str, str]:
    lines = [line.strip() for line in content.splitlines()]
    headers = [i for i, line in enumerate(lines) if line == "Python Releases for Windows"]
    stable = [i for i, line in enumerate(lines) if line == "Stable Releases"]
    matches = [(i, LABEL_RE.fullmatch(line)) for i, line in enumerate(lines)]
    matches = [(i, match) for i, match in matches if match is not None]
    if not headers or not stable or not matches:
        raise MissingLabel("primary label/context missing")
    if len(headers) != 1 or len(stable) != 1 or len(matches) != 1:
        raise ValueError("missing/ambiguous primary label")
    index, match = matches[0]
    if not headers[0] < index < stable[0]:
        raise MissingLabel("unexpected primary label context")
    return match.group(1), lines[index].removeprefix("* ").removeprefix("- ").removeprefix("• ")


async def verify(request: VerificationRequest, retriever, clock=lambda: datetime.now(timezone.utc)) -> VerificationResponse:
    claim = None
    evidence = []

    def response(verdict, reason):
        return VerificationResponse(request_id=request.request_id,
                                    candidate_sha256=request.candidate_sha256, claim=claim,
                                    verdict=verdict, reason_code=reason,
                                    evidence=evidence, checked_at=clock())

    if digest(request.candidate) != request.candidate_sha256:
        return response("INSUFFICIENT", "VERIFIER_ERROR")
    match = CLAIM_RE.fullmatch(request.candidate)
    if not match:
        return response("INSUFFICIENT", "UNSUPPORTED_CLAIM")
    claim = Claim(version=match.group(1))
    try:
        page = await retriever.retrieve()
        now = clock()
        # These are observation times, not the page's unknown publication time.
        if page.url != SOURCE_URL or page.retrieved_at.tzinfo is None:
            return response("INSUFFICIENT", "INSUFFICIENT_EVIDENCE")
        age = (now - page.retrieved_at).total_seconds()
        if not -2 <= age <= 60:
            return response("INSUFFICIENT", "STALE_OBSERVATION")
        try:
            observed, excerpt = primary_label(page.content)
        except MissingLabel:
            return response("INSUFFICIENT", "INSUFFICIENT_EVIDENCE")
        except ValueError:
            return response("INSUFFICIENT", "AMBIGUOUS_EVIDENCE")
        evidence.append(Evidence(content_sha256=digest(page.content),
                                 retrieval_mode=page.retrieval_mode,
                                 retrieved_at=page.retrieved_at, observed_at=page.retrieved_at,
                                 retrieval_id=page.retrieval_id,
                                 observed_version=observed, excerpt=excerpt))
        current = tuple(map(int, observed.split(".")))
        candidate = tuple(map(int, claim.version.split(".")))
        if candidate == current:
            return response("SUPPORTED", "MATCHED_PRIMARY_LABEL")
        if candidate < current:
            return response("CONTRADICTED", "OLDER_THAN_PRIMARY_LABEL")
        # A source extraction may lag an announcement. Never call a newer claim
        # false merely because this observation lists an older version.
        return response("INSUFFICIENT", "CLAIM_AHEAD_OF_SOURCE")
    except RetrievalTimeout:
        return response("INSUFFICIENT", "RETRIEVAL_TIMEOUT")
    except RetrievalFailure:
        return response("INSUFFICIENT", "RETRIEVAL_FAILURE")
    except Exception:
        # Never echo provider/page/credential/exception text across the boundary.
        return response("INSUFFICIENT", "VERIFIER_ERROR")
