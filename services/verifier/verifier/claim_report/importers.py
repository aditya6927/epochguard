"""Read-only projection of historical G-L/005C sanitized observations.

These exports lack original mappings, comparison flags and checked_at. They
cannot establish numeric scores, even when a separate gateway review passed.
"""
import json
from pydantic import TypeAdapter
from claim_analysis.schema import strict_json
from verifier.contract import Digest
from verifier.multiclaim.contract import Evidence, PolicyID, Outcome, PYTHON_POLICY
from verifier.policy import digest
from .contract import ClaimEntry, Report
from .derive import entry, now, unavailable

DIGEST, POLICY, VERDICT = TypeAdapter(Digest), TypeAdapter(PolicyID), TypeAdapter(Outcome)


def from_qualification(value, *, profile, record_index=0, generated_at=None):
    generated_at = generated_at or now()
    try:
        raw = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
        value = strict_json(raw.decode("utf-8", "strict"))
        input_hash = digest(raw.decode("utf-8"))
        if type(record_index) is not int or not 0 <= record_index < 16:
            raise ValueError("index")
        if type(value) is not dict:
            raise ValueError("observation")
        observation = value.get("verifier", value)
        if observation["schema_version"] != "004gl.observations.v1" or observation["policy_id"] != "004g.v1/bounded-prose-v1":
            raise ValueError("schema")
        records = observation["records"]
        if type(records) is not list or not 0 <= record_index < len(records) <= 16:
            raise ValueError("record bound")
        record = records[record_index]
        candidate_hash = DIGEST.validate_python(record["candidate_sha256"], strict=True)
        verdict = VERDICT.validate_python(record["verdict"], strict=True)
        coverage = record["coverage"]
        if coverage not in {"COMPLETE", "UNCERTAIN"} or record["completed"] is not True:
            raise ValueError("incomplete observation")
        claims = record["claims"]
        if type(claims) is not list or len(claims) > 8:
            raise ValueError("claim bound")
        entries = []
        for i, claim in enumerate(claims, 1):
            policy = POLICY.validate_python(claim["policy_id"], strict=True)
            claim_verdict = VERDICT.validate_python(claim["verdict"], strict=True)
            if claim["claim_id"] != f"c{i:03d}":
                raise ValueError("order not recorded")
            values = entry(i, policy, candidate_hash).model_dump() | dict(
                coverage=coverage, verdict=claim_verdict, score_reason="NOT_RECORDED")
            try:
                evidence = claim["evidence"]
                if type(evidence) is not list or len(evidence) > 1:
                    raise ValueError("evidence bound")
                if evidence:
                    e = Evidence.model_validate_json(json.dumps(evidence[0]))
                    # Reuse existing policy-source/mode identity checks through
                    # the output schema. No original text/version is invented.
                    values.update(source_url=e.url, evidence_mode=e.retrieval_mode, observed_at=e.observed_at,
                                  observed_version=e.observed_version, evidence_digest=e.content_sha256)
                    expected = "fixture" if profile == "fixture" else "tavily_live" if policy == PYTHON_POLICY else "pypi_live"
                    if e.retrieval_mode != expected:
                        values["score_reason"] = "SOURCE_MODE_MISMATCH"
                entries.append(ClaimEntry.model_validate(values))
            except (ValueError, TypeError, KeyError):
                entries.append(entry(i, policy, candidate_hash))
        return Report(basis="qualification_diagnostic", report_status="INCOMPLETE", report_reason="NOT_RECORDED",
            input_sha256=input_hash, record_index=record_index, evidence_profile=profile,
            candidate_sha256=candidate_hash, generated_at=generated_at, coverage=coverage, verdict=verdict, claims=entries)
    except Exception:
        return unavailable(profile=profile, generated_at=generated_at, reason="NOT_RECORDED")
