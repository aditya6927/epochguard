import asyncio
import copy
import json
from datetime import timedelta
from pathlib import Path
import subprocess
import sys
import pytest
from claimreporting.fixtures import CASES, TIME, PY, PI, snapshot
from verifier.bounded_prose.contract import Result
from verifier.claim_report import from_result, Report
from verifier.claim_report.contract import ClaimEntry
from verifier.claim_report.importers import from_qualification
from verifier.claim_report.presentation import render
from verifier.policy import digest


def make(text=PY, fault="none"):
    return asyncio.run(snapshot(text, fault))[0]


@pytest.mark.parametrize("name,text,fault,outcome,scores,reasons", CASES, ids=[c[0] for c in CASES])
def test_fixed_cases(name, text, fault, outcome, scores, reasons):
    value, authoritative = asyncio.run(snapshot(text, fault))
    before = copy.deepcopy(value)
    report = from_result(value, profile="fixture", generated_at=TIME)
    assert value == before
    assert [c.freshness_score for c in report.claims] == scores
    assert [c.score_reason for c in report.claims] == reasons
    assert [c.claim_index for c in report.claims] == list(range(1, len(scores)+1))
    assert report.authorization is False and report.generated_at == TIME
    assert Report.model_validate_json(report.model_dump_json()) == report
    assert text not in report.model_dump_json()
    if any(score is not None for score in scores):
        assert all(c.evidence_mode == "fixture" for c in report.claims if c.freshness_score is not None)
    vectors = json.loads((Path(__file__).resolve().parents[3]/"tests/conformance/005d-reporting.json").read_text())
    vector = next(v for v in vectors if v["name"] == name)
    assert vector["result"] == value and vector["expected"] == outcome
    # Go's independent validator consumes these same fixed vectors. The report
    # never modifies the actual Python result, including on malformed inputs.
    if fault not in {"map-order", "map-missing", "map-offset", "hash", "evidence-hash", "bound-expired"}:
        assert Result.model_validate_json(json.dumps(value)).model_dump(mode="json") == authoritative


def test_report_failure_cannot_modify_verification(monkeypatch):
    value = make(PY.replace("3.88.7", "3.88.6"))
    original = copy.deepcopy(value)
    def fail(*args): raise RuntimeError("PRIVATE_FAILURE_TEXT")
    monkeypatch.setattr("verifier.claim_report.derive._derive", fail)
    report = from_result(value, profile="fixture", generated_at=TIME)
    assert report.report_reason == "REPORT_UNAVAILABLE" and report.claims == []
    assert "PRIVATE_FAILURE_TEXT" not in report.model_dump_json()
    assert value == original and Result.model_validate_json(json.dumps(value)).verification.verdict == "CONTRADICTED"


@pytest.mark.parametrize("text", [PY.replace("3.88.7", "3.88.6"), PI.replace("2.88.7", "2.88.8"), PY+" Unsupported."])
def test_scores_are_never_authorization_inputs(text):
    value = make(text)
    before = copy.deepcopy(value)
    report = from_result(value, profile="fixture", generated_at=TIME).model_dump(mode="json")
    for claim in report["claims"]: claim["freshness_score"] = 100
    report["authorization"] = True
    with pytest.raises(ValueError): Report.model_validate_json(json.dumps(report))
    with pytest.raises(ValueError): Result.model_validate_json(json.dumps(report))
    assert value == before
    parsed = Result.model_validate_json(json.dumps(value))
    assert parsed.verification is None or parsed.verification.verdict != "SUPPORTED"


@pytest.mark.parametrize("age,score,status,ms", [(-2,100,"FUTURE_WITHIN_TOLERANCE",None),(-2.001,None,"INVALID",None),
    (0,100,"MEASURED",0),(1.001,100,"MEASURED",1001),(60,100,"MEASURED",60000),(60.001,None,"INVALID",None)])
def test_observation_window(age, score, status, ms):
    value = make()
    evidence = value["verification"]["claims"][0]["evidence"][0]
    evidence["observed_at"] = evidence["retrieved_at"] = (TIME-timedelta(seconds=age)).isoformat()
    if score is None: value["verification"]["verdict"] = "INSUFFICIENT"
    claim = from_result(value, profile="fixture", generated_at=TIME+timedelta(days=30)).claims[0]
    assert (claim.freshness_score,claim.observation_time_status,claim.observation_age_ms) == (score,status,ms)
    assert claim.evaluated_at == TIME  # Viewing never moves the historical evaluation.


def test_mode_mismatch_and_actual_live_mode_are_explicit():
    value = make()
    mismatch = from_result(value, profile="live", generated_at=TIME)
    assert mismatch.claims[0].freshness_score is None and mismatch.claims[0].score_reason == "SOURCE_MODE_MISMATCH"
    evidence = value["verification"]["claims"][0]["evidence"][0]
    evidence["retrieval_mode"] = "tavily_live"
    evidence["evidence_id"] = digest(f'{evidence["url"]}|tavily_live|{evidence["retrieval_id"]}|{evidence["content_sha256"]}')
    report = from_result(value, profile="live", generated_at=TIME)
    assert report.claims[0].freshness_score == 100 and report.claims[0].evidence_mode == "tavily_live"
    # Synthetic metadata-mode test only; no actual source was contacted.


def test_historical_import_never_invents_missing_bindings_or_times():
    value = make(PY+"\n"+PI)
    claims = [{"claim_id": c["claim"]["source"]["claim_id"], "policy_id": c["claim"]["policy_id"],
               "claimed_version": c["claim"]["version"], "verdict": c["verdict"], "evidence": c["evidence"]}
              for c in value["verification"]["claims"]]
    observation = {"schema_version":"004gl.observations.v1","policy_id":"004g.v1/bounded-prose-v1", "records":[{
        "candidate_sha256":value["candidate_sha256"],"coverage":"COMPLETE","verdict":"SUPPORTED","completed":True,"claims":claims}]}
    report = from_qualification(observation, profile="fixture", generated_at=TIME)
    assert report.basis == "qualification_diagnostic" and report.report_status == "INCOMPLETE"
    assert len(report.claims) == 2 and all(c.freshness_score is None and c.score_reason == "NOT_RECORDED" for c in report.claims)
    assert report.evaluated_at is None and all(c.observed_at == TIME and c.observation_age_ms is None for c in report.claims)
    assert all(c.evidence_digest for c in report.claims)
    claims.reverse()
    assert from_qualification(observation, profile="fixture").claims == []


@pytest.mark.parametrize("raw", [b'{}', b'[]', b'null', b'{"candidate":1,"candidate":2}', b'{"x":NaN}', b'\xff', b'x'*65537])
def test_invalid_inputs_are_bounded_and_safe(raw):
    report = from_result(raw, profile="fixture", generated_at=TIME)
    assert report.report_status == "INCOMPLETE" and not report.claims


def test_html_is_static_escaped_and_contains_no_candidate_or_secrets():
    report = from_result(make(), profile="fixture", generated_at=TIME)
    html = render(report)
    assert PY not in html and "<script" not in html and "default-src 'none'" in html and "fixture" in html
    assert "Supported by the observed source" in html and "100" in html and "origin freshness" in html
    assert "not_recorded" in render(from_result(make(PY+" Unsupported."), profile="fixture")) or "Unsupported claim language" in render(from_result(make(PY+" Unsupported."), profile="fixture"))
    invalid = report.model_copy(update={"candidate_sha256":"<img src=x onerror=alert(1)>"})
    with pytest.raises(ValueError): render(invalid)


@pytest.mark.parametrize("score", [False, True, 50, 100.0, "100"])
def test_schema_rejects_noncanonical_score(score):
    entry = from_result(make(), profile="fixture", generated_at=TIME).claims[0].model_dump()
    entry["freshness_score"] = score
    with pytest.raises(ValueError): ClaimEntry.model_validate(entry)


def test_cli_sanitized_outputs_and_no_overwrite(tmp_path):
    source, output, page = (tmp_path/n for n in ("source.json", "report.json", "report.html"))
    source.write_text(json.dumps(make()), encoding="utf-8")
    before = source.read_bytes()
    command = [sys.executable, "-m", "verifier.claim_report", "--input", str(source), "--kind", "bounded-result",
               "--evidence-profile", "fixture", "--output", str(output), "--html", str(page)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0 and PY not in result.stdout+result.stderr
    assert Report.model_validate_json(output.read_bytes()).claims[0].freshness_score == 100
    assert PY not in page.read_text(encoding="utf-8") and source.read_bytes() == before
    saved = output.read_bytes(), page.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode == 1
    assert saved == (output.read_bytes(), page.read_bytes())
    command[-3:] = [str(source)]  # Malformed CLI invocation is safe and cannot rewrite input.
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert source.read_bytes() == before


def test_cli_oversize_and_existing_input_alias_refuse(tmp_path):
    source, output = tmp_path/"source.json", tmp_path/"report.json"
    command = [sys.executable, "-m", "verifier.claim_report", "--input", str(source), "--kind", "bounded-result",
               "--evidence-profile", "fixture", "--output", str(output)]
    source.write_bytes(b"x"*65537)
    assert subprocess.run(command, capture_output=True).returncode == 1
    assert not output.exists()
    command[-1] = str(source)
    assert subprocess.run(command, capture_output=True).returncode == 1
    assert source.stat().st_size == 65537


def test_scores_cannot_be_injected_into_original_records():
    value = make()
    value["freshness_score"] = 100
    report = from_result(value, profile="fixture", generated_at=TIME)
    assert report.claims and all(c.freshness_score is None for c in report.claims)
    with pytest.raises(ValueError): Result.model_validate_json(json.dumps(value))


def test_valid_neighbor_score_does_not_cover_missing_evidence():
    value = make(PY+"\n"+PI, "unavailable")
    original = copy.deepcopy(value)
    report = from_result(value, profile="fixture", generated_at=TIME)
    assert [c.freshness_score for c in report.claims] == [None,100]
    assert report.verdict == "INSUFFICIENT" and report.authorization is False
    assert value == original and Result.model_validate_json(json.dumps(value)).verification.verdict == "INSUFFICIENT"
