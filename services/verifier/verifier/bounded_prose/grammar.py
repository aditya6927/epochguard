"""Closed ASCII grammar. Nothing except recognized assertions and SPACE is ignored."""

from pydantic import Field
from verifier.multiclaim.contract import Strict, PolicyID, NumericVersion
from verifier.multiclaim.coverage import REGISTRY as ORIGINAL, SPACE
from verifier.prose.mapping import REGISTRY as PARAPHRASES, canonical


class Mapping(Strict):
    claim_id: str = Field(pattern=r"^c[0-9]{3}$")
    source_text: str = Field(max_length=8192)
    start: int = Field(ge=0, le=8192)
    end: int = Field(ge=0, le=8192)
    policy_id: PolicyID
    version: NumericVersion
    canonical: str = Field(max_length=200)


REGISTRY = tuple(ORIGINAL) + tuple((policy, pattern) for policy, forms in PARAPHRASES for pattern in forms)


def parse(text):
    if not text.isascii() or len(text) > 8192:
        return [], "UNRECOGNIZED_CONTENT"
    cursor, mappings, seen = 0, [], set()
    while cursor < len(text):
        if text[cursor] in SPACE:
            cursor += 1
            continue
        for policy, pattern in REGISTRY:
            found = pattern.match(text, cursor)
            if found:
                break
        else:
            return [], "UNRECOGNIZED_CONTENT"
        if found.end() < len(text) and text[found.end()] not in SPACE:
            return [], "UNRECOGNIZED_CONTENT"
        sentence = canonical(policy, found[1])
        if sentence in seen:
            return [], "REPEATED_CLAIM"
        if len(mappings) == 8:
            return [], "CLAIM_LIMIT"
        seen.add(sentence)
        mappings.append(Mapping(claim_id=f"c{len(mappings)+1:03d}", source_text=found[0],
                                start=cursor, end=found.end(), policy_id=policy,
                                version=found[1], canonical=sentence))
        cursor = found.end()
    return (mappings, "BOUNDED_GRAMMAR") if mappings else ([], "NO_CLAIMS")


def comparison_text(mappings):
    return "\n".join(m.canonical for m in mappings)
