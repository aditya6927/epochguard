"""Independent risk accounting. Unknown syntax never earns semantic credit."""

import re

from .mapping import canonical, match
from .schema import Correspondence, Mapping, Unit

NONFACTUAL = frozenset({"Hello.", "Thanks.", "Thank you."})
BOUNDARY = re.compile(r"\n|(?<=[.!?;])(?=\s|$)")
COMPOUND = re.compile(r"\b(?:and|but|while|whereas|although|because|which)\b|;", re.I)
CONTEXT = re.compile(
    r"[`\"'“”‘’()\[\]{}<>:]|^[ \t]*[-*#>] |"
    r"\b(?:not|never|false|deny|might|may|must|guarantee\w*|if|will|tomorrow|yesterday|"
    r"last year|next year|said|says|wrote|claims|suppose|imagine)\b", re.I | re.M)
PREDICATE = re.compile(r"\b(?:is|are|was|were|has|have|lists|reports|costs|contains|guarantees|"
                       r"supports|runs|boils|equals|orbits|requires|released|uses)\b", re.I)


def units(text):
    """All nonwhitespace is retained, including delimiters and unknown tails.

    Segmentation is independent of extractor output. Periods in versions and
    Python.org are not boundaries. Compound markers make a whole sentence MIXED:
    this scanner does not pretend to decompose scope or multiple predicates.
    """
    spans, start = [], 0
    for boundary in BOUNDARY.finditer(text):
        end = boundary.start() if boundary.group() == "\n" else boundary.end()
        spans.append((start, end))
        start = boundary.end()
    spans.append((start, len(text)))
    trimmed = []
    for start, end in spans:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end-1].isspace():
            end -= 1
        if start < end:
            trimmed.append((start, end))
    overflow = len(trimmed) > 64
    if overflow:
        trimmed = trimmed[:63] + [(trimmed[63][0], trimmed[-1][1])]
    contextual = bool(CONTEXT.search(text)) or any(ord(c) > 127 for c in text)
    result = []
    for index, (start, end) in enumerate(trimmed):
        source = text[start:end]
        if overflow and index == 63:
            kind, reason = "LIMIT_TAIL", "UNIT_LIMIT"
        elif contextual:
            kind, reason = "AMBIGUOUS", "CONTEXT_OR_FORMAT"
        elif COMPOUND.search(source):
            kind, reason = "MIXED", "COMPOUND_MARKER"
        elif source in NONFACTUAL:
            kind, reason = "NONFACTUAL_RULE", "EXPLICIT_NONFACTUAL"
        elif match(source) is not None:
            kind, reason = "KNOWN_FACT", "CLOSED_FORM"
        elif PREDICATE.search(source):
            kind, reason = "POTENTIAL_FACT", "UNSUPPORTED_PREDICATE"
        else:
            kind, reason = "UNRECOGNIZED", "UNKNOWN_CONTENT"
        result.append(Unit(unit_id=f"u{index+1:03d}", source_text=source, start=start, end=end,
                           kind=kind, reason=reason))
    return tuple(result)


def derive(text, proposals, failure=None):
    risk = units(text)
    mappings, correspondences = [], []
    for unit in risk:
        overlapping = tuple(c for c in proposals if c.start < unit.end and c.end > unit.start)
        exact = len(overlapping) == 1 and (overlapping[0].start, overlapping[0].end) == (unit.start, unit.end)
        if unit.kind == "KNOWN_FACT" and len(mappings) < 8:
            policy, version = match(unit.source_text)
            mappings.append(Mapping(unit_id=unit.unit_id, policy_id=policy, version=version,
                                    canonical_text=canonical(policy, version)))
            if not overlapping:
                disposition, reason = "UNACCOUNTED", "MISSING_PROPOSAL"
            elif not exact:
                disposition, reason = "UNCERTAIN", "NONATOMIC_OR_PARTIAL"
            elif (overlapping[0].factuality, overlapping[0].temporal, overlapping[0].fresh_evidence) != ("FACTUAL", "DYNAMIC", "REQUIRED") or any(r != "BASELINE_HEURISTIC" for r in overlapping[0].uncertainty):
                disposition, reason = "UNCERTAIN", "CLASSIFICATION_CONFLICT"
            else:
                disposition, reason = "COVERED_FACT", "EXACT_ATOMIC_MATCH"
        elif unit.kind == "NONFACTUAL_RULE":
            if not overlapping or (exact and overlapping[0].factuality == "NON_FACTUAL"):
                disposition, reason = "NONFACTUAL_RULE", "EXPLICIT_NONFACTUAL"
            else:
                disposition, reason = "UNCERTAIN", "CLASSIFICATION_CONFLICT"
        elif not overlapping:
            disposition, reason = "UNACCOUNTED", "MISSING_PROPOSAL"
        elif unit.kind == "POTENTIAL_FACT" and exact and overlapping[0].factuality == "FACTUAL":
            disposition, reason = "UNSUPPORTED", "NO_SUPPORTED_POLICY"
        else:
            disposition, reason = "UNCERTAIN", "AUDIT_UNCERTAIN"
        correspondences.append(Correspondence(unit_id=unit.unit_id, overlapping_claim_ids=tuple(c.claim_id for c in overlapping),
                                             disposition=disposition, reason=reason))
    gaps = tuple(c.unit_id for c in correspondences if c.disposition in {"UNACCOUNTED", "UNCERTAIN"})
    unsupported = tuple(u.unit_id for u in risk if u.kind == "POTENTIAL_FACT")
    # No character/sentence percentage can waive an unresolved assertion.
    accounted = bool(mappings) and all(c.disposition in {"COVERED_FACT", "NONFACTUAL_RULE"} for c in correspondences)
    no_assertions = not mappings and all(u.kind == "NONFACTUAL_RULE" for u in risk)
    coverage = "BOUNDED_ACCOUNTED" if accounted else "NO_ASSERTIONS" if no_assertions else "UNRESOLVED"
    status = ("ANALYSIS_FAILED" if failure else "PLAN_READY" if accounted else
              "PLAN_UNCERTAIN" if gaps or no_assertions else "PLAN_UNSUPPORTED")
    covered = set()
    for claim in proposals:
        covered.update(range(claim.start, claim.end))
    return dict(risk_units=risk, policy_mappings=tuple(mappings), correspondences=tuple(correspondences),
                unaccounted_unit_ids=gaps, unsupported_unit_ids=unsupported, coverage=coverage,
                syntactic_covered_characters=len(covered), overall_status=status)


def shadow_status(observations):
    if not observations:
        return "NOT_RUN"
    if any(o.verdict == "CONTRADICTED" for o in observations):
        return "MAPPED_CLAIM_CONTRADICTED"
    if all(o.verdict == "SUPPORTED" for o in observations):
        return "MAPPED_CLAIMS_SUPPORTED"
    return "MAPPED_CLAIMS_INSUFFICIENT"
