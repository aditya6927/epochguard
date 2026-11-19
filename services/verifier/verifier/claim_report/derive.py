"""Project existing validated Python results; no source parsing or comparisons."""
import json
from datetime import datetime, timezone
from claim_analysis.schema import strict_json
from verifier.bounded_prose.contract import Request, Result
from verifier.bounded_prose.grammar import parse
from verifier.multiclaim.contract import PYTHON_POLICY
from verifier.policy import digest
from .contract import Report, ClaimEntry, observation_time


def now():
    return datetime.now(timezone.utc)


def entry(index, policy, candidate_hash, **values):
    return ClaimEntry(claim_id=f"c{index:03d}", claim_index=index, policy_id=policy,
        candidate_sha256=candidate_hash, source_id="python-windows" if policy == PYTHON_POLICY else "pypi-requests",
        coverage="UNCERTAIN", verdict="INSUFFICIENT", freshness_score=None, score_reason="INVALID_RECORD", **values)


def unavailable(*, profile, generated_at=None, reason="REPORT_UNAVAILABLE", input_hash=None):
    return Report(basis="invalid_input", report_status="INCOMPLETE", report_reason=reason,
                  evidence_profile=profile, generated_at=generated_at or now(), input_sha256=input_hash)


def from_result(value, *, profile, generated_at=None):
    """Diagnostic snapshot evaluated at the recorded verifier checked_at.

    The caller selects a trusted fixture/live profile. Invalid input yields an
    explicitly incomplete report. No raw input/text survives into its output.
    This function is never called by an enforcement hook or HTTP application.
    """
    generated_at = generated_at or now()
    try:
        raw = value if isinstance(value, bytes) else value.model_dump_json().encode() if isinstance(value, Result) else json.dumps(value, allow_nan=False).encode()
        value = strict_json(raw.decode("utf-8", "strict"))
    except Exception:
        return unavailable(profile=profile, generated_at=generated_at, reason="INVALID_RECORD")
    input_hash = digest(raw.decode("utf-8"))
    try:
        return _derive(value, profile, generated_at, input_hash)
    except Exception:
        # Reporting cannot turn an existing refusal into release, or return a
        # partially assembled numeric report after a presentation failure.
        return unavailable(profile=profile, generated_at=generated_at, input_hash=input_hash)


def _derive(value, profile, generated_at, input_hash):
    try:
        request = Request.model_validate({k: value[k] for k in Request.model_fields})
    except (ValueError, TypeError, KeyError):
        return unavailable(profile=profile, generated_at=generated_at, reason="INVALID_RECORD", input_hash=input_hash)
    mappings, _ = parse(request.candidate)
    entries = [entry(i, m.policy_id, request.candidate_sha256) for i, m in enumerate(mappings, 1)]
    report = dict(basis="python_result_diagnostic", report_status="INCOMPLETE", report_reason="INVALID_RECORD",
                  input_sha256=input_hash, evidence_profile=profile, generated_at=generated_at,
                  candidate_sha256=request.candidate_sha256, claims=entries)
    try:
        result = Result.model_validate_json(json.dumps(value, allow_nan=False))
    except (ValueError, TypeError):
        return Report(**report)
    if not mappings:
        return Report(**(report | dict(report_status="COMPLETE", report_reason="UNSUPPORTED_LANGUAGE")))
    evaluated = result.verification.checked_at
    entries = []
    incomplete = False
    for i, claim in enumerate(result.verification.claims, 1):
        # ClaimResult/Result already validate policy, numeric comparison, evidence
        # identity, complete mappings, order and canonical candidate bindings.
        values = dict(coverage="COMPLETE", verdict=claim.verdict, score_reason="MISSING_EVIDENCE",
                      evaluated_at=evaluated)
        if claim.evidence:
            evidence = claim.evidence[0]
            status, age_ms = observation_time(evidence.observed_at, evaluated)
            expected_mode = "fixture" if profile == "fixture" else "tavily_live" if claim.claim.policy_id == PYTHON_POLICY else "pypi_live"
            reason = "SOURCE_MODE_MISMATCH" if evidence.retrieval_mode != expected_mode else "STALE_OBSERVATION" if status == "INVALID" else "CLAIM_AHEAD_OF_SOURCE"
            score = None
            if reason not in {"SOURCE_MODE_MISMATCH", "STALE_OBSERVATION"}:
                if claim.verdict == "SUPPORTED": score, reason = 100, "MATCHED_OBSERVATION"
                elif claim.verdict == "CONTRADICTED": score, reason = 0, "OLDER_THAN_OBSERVATION"
            else:
                incomplete = True
            values.update(source_url=evidence.url, evidence_mode=evidence.retrieval_mode,
                observed_at=evidence.observed_at, observation_age_ms=age_ms,
                observation_time_status=status, observed_version=evidence.observed_version,
                evidence_digest=evidence.content_sha256, freshness_score=score, score_reason=reason)
        else:
            incomplete = True
            reason = claim.reason_code
            values["score_reason"] = reason if reason in {"INSUFFICIENT_EVIDENCE", "AMBIGUOUS_EVIDENCE", "STALE_OBSERVATION", "RETRIEVAL_FAILURE", "RETRIEVAL_TIMEOUT", "VERIFIER_ERROR"} else "MISSING_EVIDENCE"
        # Defaults describe malformed input; valid evidence supplies these values.
        base = entry(i, mappings[i-1].policy_id, request.candidate_sha256).model_dump()
        entries.append(ClaimEntry.model_validate(base | values))
    return Report(**(report | dict(claims=entries, evaluated_at=evaluated, coverage=result.coverage,
        verdict=result.verification.verdict, report_status="INCOMPLETE" if incomplete else "COMPLETE",
        report_reason="INCOMPLETE_EVIDENCE" if incomplete else "VALIDATED_RESULT")))
