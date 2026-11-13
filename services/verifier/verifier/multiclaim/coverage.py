"""Independent whole-response grammar. No semantic completeness claim."""

import re

from claim_analysis.schema import Claim
from verifier.policy import CLAIM_RE, digest

from .contract import BoundClaim, Coverage, MAX_CLAIMS, PYTHON_POLICY, PYPI_POLICY

PYPI_RE = re.compile(r"The version reported for requests by the PyPI JSON API is "
                     r"((?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2}))\.")
REGISTRY = ((PYTHON_POLICY, CLAIM_RE), (PYPI_POLICY, PYPI_RE))
SPACE = " \t\r\n"


def uncertain(reason):
    return Coverage(status="UNCERTAIN", reason_code=reason, required_claim_ids=[])


def qualify(text: str) -> tuple[list[BoundClaim], Coverage]:
    cursor, claims, seen = 0, [], set()
    while cursor < len(text):
        if text[cursor] in SPACE:
            cursor += 1
            continue
        for policy_id, pattern in REGISTRY:
            match = pattern.match(text, cursor)
            if match is not None:
                break
        else:
            return [], uncertain("UNRECOGNIZED_CONTENT")
        if match.end() < len(text) and text[match.end()] not in SPACE:
            return [], uncertain("UNRECOGNIZED_CONTENT")
        if match.group() in seen:
            return [], uncertain("REPEATED_CLAIM")
        if len(claims) == MAX_CLAIMS:
            return [], uncertain("CLAIM_LIMIT")
        seen.add(match.group())
        source = Claim(claim_id=f"c{len(claims)+1:03d}", source_text=match.group(),
                       start=cursor, end=match.end(), normalized_proposition=None,
                       factuality="FACTUAL", temporal="DYNAMIC", fresh_evidence="REQUIRED",
                       uncertainty=[], temporal_reference=None)
        claims.append(BoundClaim(source=source, candidate_sha256=digest(text),
                                 policy_id=policy_id, version=match.group(1)))
        cursor = match.end()
    if not claims:
        return [], uncertain("NO_CLAIMS")
    return claims, Coverage(status="COMPLETE", reason_code="EXACT_TEMPLATES",
                            required_claim_ids=[c.source.claim_id for c in claims])
