"""Frozen sentence/lexicon benchmark; no claim of semantic coverage."""

import re

from .schema import AnalysisInput, Claim, Extraction, MAX_CLAIMS, SCHEMA

SEGMENT = re.compile(r".+?(?:[.!?](?=\s|$)|\n|$)", re.S)
HISTORY = re.compile(r"\b(?:in|during|as of|on) ((?:18|19|20)\d{2}(?:-\d{2}-\d{2})?)\b", re.I)
RELATIVE = re.compile(r"\b(today|currently|now|yesterday|last year|this week|tomorrow)\b", re.I)
DYNAMIC = re.compile(r"\b(latest|current|today|now|price|costs?|trades?|ceo|president|minister|captain|ranked|ranking|forecast|weather|available|stock|sold out|delayed|cancelled|open|closed|requires?|regulations?|visa|release|version|supports?|shipping|leads?|score|wins?|tickets?|interest rate|yield|exchange rate)\b", re.I)
STABLE = re.compile(r"\b(triangle|prime|integer|hydrogen|oxygen|atom|molecule|photosynthesis|gravity|orbits|continent|capital|wrote|invented|founded|became|sum|equals|square|mammal|freezes|boils|algorithm|binary|kilometre|kilometer|unicode|utf-8|http|json)\b", re.I)
OPINION = re.compile(r"\b(I (?:think|prefer|love|expect)|best|beautiful|wonderful|should|will|predict|probably|might|may win)\b", re.I)
INSTRUCTION = re.compile(r"^(?:please|ignore|return|print|forget|use|do not|system:|assistant:)", re.I)


def analyze(request: AnalysisInput) -> Extraction:
    claims = []
    for match in SEGMENT.finditer(request.text):
        segment = match.group().strip()
        if not segment:
            continue
        start = match.start() + len(match.group()) - len(match.group().lstrip())
        factuality, temporal, fresh = "FACTUAL", "UNCERTAIN", "UNCERTAIN"
        reasons = ["BASELINE_HEURISTIC"]
        historical = HISTORY.search(segment)
        relative = RELATIVE.search(segment)
        reference = relative.group() if relative else historical.group(1) if historical else None
        if segment.endswith("?") or OPINION.search(segment) or INSTRUCTION.search(segment):
            factuality, fresh = "NON_FACTUAL", "NOT_APPLICABLE"
            if INSTRUCTION.search(segment):
                reasons.append("UNTRUSTED_INSTRUCTION")
        elif re.match(r"^(it|they|this|that|he|she)\b", segment, re.I):
            factuality = "UNCERTAIN"
            reasons.append("AMBIGUOUS_REFERENCE")
        elif historical and historical.group(1)[:4] < request.reference_date[:4]:
            if re.search(r"\b(now|today|currently)\b", segment, re.I):
                fresh = "REQUIRED"
                reasons.append("MIXED_REQUIREMENTS")
            else:
                temporal, fresh = "HISTORICAL", "NOT_REQUIRED"
        elif DYNAMIC.search(segment):
            temporal, fresh = "DYNAMIC", "REQUIRED"
        elif STABLE.search(segment):
            temporal, fresh = "STABLE", "NOT_REQUIRED"
        else:
            reasons.append("MISSING_CONTEXT")
        claims.append(Claim(claim_id=f"c{len(claims)+1:03d}", source_text=segment,
                            start=start, end=start+len(segment), normalized_proposition=None,
                            factuality=factuality, temporal=temporal, fresh_evidence=fresh,
                            uncertainty=reasons, temporal_reference=reference))
        if len(claims) > MAX_CLAIMS:
            raise ValueError("too many sentence units")
    return Extraction(schema_version=SCHEMA, claims=claims).bind(request)
