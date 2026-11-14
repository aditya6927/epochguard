import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verifier.prose.cli import main, request
from verifier.prose.dataset import load
from verifier.prose.evaluation import score
from verifier.prose.pipeline import Analyzer
from tests_prose.support import PYPI


def test_separate_frozen_data_and_draft_review_gate():
    cases = load("dev") + load("heldout")
    assert len(cases) == 66 and len({c.case_id for c in cases}) == 66
    assert sum("adversarial" in c.tags for c in cases) >= 20
    assert sum(any(g.policy_id is None and g.source.factuality == "FACTUAL" for g in c.gold) for c in cases) >= 10
    assert sum("negative" in c.tags for c in cases) >= 5
    assert all(c.review_status == "draft" and c.reviewer is None for c in cases)
    with pytest.raises(ValueError):
        load("dev", require_reviewed=True)


def test_false_complete_and_wrong_mapping_negative_control():
    case = next(c for c in load("dev") if c.gold and any(g.policy_id is None for g in c.gold))
    result = asyncio.run(Analyzer().analyze(request(case.text, case.reference_date, case.case_id)))
    unsafe = result.model_copy(update={"coverage": "BOUNDED_ACCOUNTED", "overall_status": "PLAN_READY"})
    scored = score([{"case": case, "result": unsafe}])
    assert scored["false_complete_count"] == 1 and scored["false_complete_cases"][0]["case_id"] == case.case_id
    target = next(g for g in case.gold if g.policy_id is None)
    unit = SimpleNamespace(unit_id="u999", start=target.source.start, end=target.source.end)
    mapped = SimpleNamespace(unit_id="u999", policy_id="python-windows-latest-v1")
    fake = SimpleNamespace(proposals=(), policy_mappings=(mapped,), risk_units=(unit,),
                           overall_status="PLAN_READY", coverage="BOUNDED_ACCOUNTED", unaccounted_unit_ids=())
    scored = score([{"case": case, "result": fake}])
    assert scored["unsupported_assertions_mapped"] == 1 and scored["false_complete_count"] == 1
    assert "WRONG_POLICY_MAPPING" in scored["false_complete_cases"][0]["failure_categories"]


def test_deterministic_cli_evaluation_keeps_failures_in_denominator(tmp_path, monkeypatch, capsys):
    outputs = []
    for i in range(2):
        output = tmp_path / f"report-{i}.json"
        monkeypatch.setattr("sys.argv", ["prose", "evaluate", "--engine", "baseline", "--split", "dev", "--output", str(output)])
        assert main() == 0
        outputs.append(output.read_bytes())
    assert outputs[0] == outputs[1]
    report = json.loads(outputs[0])
    assert report["review_pending"] == 33 and report["model_attempts"] == 0
    assert report["model_quality_status"] == "MODEL QUALITY QUALIFICATION PENDING"
    combined = report["metrics"]["combined_extractor_and_auditor"]
    assert combined["responses"] == 33 and combined["extraction_failures"] > 0
    assert combined["dynamic_omitted"] > 0 and combined["false_complete_count"] == 0
    assert report["metrics"]["extractor_only"]["false_complete_count"] is None
    assert report["model_measurements"]["estimated_cost_usd_reported"] is None


def test_default_human_cli_omits_text_and_json_is_explicit(tmp_path, monkeypatch, capsys):
    path = tmp_path / "response.txt"
    text = PYPI + " PRIVATE_CANDIDATE_SENTINEL has 500 vulnerabilities."
    path.write_text(text)
    monkeypatch.setattr("sys.argv", ["prose", "analyze", "--text-file", str(path)])
    assert main() == 0
    output = capsys.readouterr().out
    assert "PRIVATE_CANDIDATE_SENTINEL" not in output and "PLAN_UNSUPPORTED" in output
    monkeypatch.setattr("sys.argv", ["prose", "analyze", "--text-file", str(path), "--json"])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["request"]["candidate"] == text and output["authorization"] is False


@pytest.mark.parametrize("content", [b"\xff", b"x"*65537, b"bad\x00text", "\ud800".encode("utf-8", errors="surrogatepass")])
def test_invalid_file_diagnostics_are_fixed(content, tmp_path, monkeypatch, capsys):
    path = tmp_path / "PRIVATE_PATH_INPUT.txt"
    path.write_bytes(content)
    monkeypatch.setattr("sys.argv", ["prose", "analyze", "--text-file", str(path)])
    assert main() == 2
    output = capsys.readouterr()
    assert not output.out and "PRIVATE_PATH_INPUT" not in output.err
    assert json.loads(output.err)["authorization"] is False


def test_live_opt_in_and_ten_case_guard_never_make_default_calls(tmp_path, monkeypatch, capsys):
    output = tmp_path / "not-created.json"
    # Missing explicit subset/max count is refused even before provider creation.
    monkeypatch.setattr("sys.argv", ["prose", "evaluate", "--engine", "gemini", "--output", str(output)])
    assert main() == 2 and not output.exists()
    monkeypatch.setattr("sys.argv", ["prose", "evaluate", "--engine", "gemini", "--case-ids", "eg004f-0001", "--max-requests", "1", "--output", str(output)])
    assert main() == 2 and not output.exists()
    assert "authorization" in capsys.readouterr().err


def test_argument_errors_do_not_echo_arbitrary_values(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["prose", "analyze", "--engine", "PRIVATE_ARGUMENT_SENTINEL"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    output = capsys.readouterr()
    assert not output.out and "PRIVATE_ARGUMENT_SENTINEL" not in output.err
    assert json.loads(output.err)["reason"] == "INVALID_ARGUMENTS"


def test_case_failure_is_not_filtered_out_of_metrics():
    case = next(c for c in load("dev") if any(g.source.temporal == "DYNAMIC" for g in c.gold))
    scored = score([{"case": case, "result": None}])
    assert scored["responses"] == scored["extraction_failures"] == 1
    assert scored["dynamic_omitted"] == scored["dynamic_gold"] > 0
    assert scored["claim"]["recall"] == 0
    negative = next(c for c in load("dev") if not c.expected_bounded_accounting)
    scored = score([{"case": negative, "result": None}])
    assert scored["correct_abstentions"] == 0 and scored["safe_refusals_including_failures"] == 1


def test_false_complete_metric_detects_wrong_version_mapping():
    case = next(c for c in load("dev") if c.expected_bounded_accounting)
    result = asyncio.run(Analyzer(engine="auditor").analyze(request(case.text, case.reference_date, case.case_id)))
    bad = result.policy_mappings[0].model_copy(update={"version": "0.0.0"})
    unsafe = result.model_copy(update={"policy_mappings": (bad, *result.policy_mappings[1:])})
    metric = score([{"case": case, "result": unsafe}])
    assert metric["false_complete_count"] == metric["unsupported_assertions_mapped"] == 1


def test_exported_result_schema_matches_runtime():
    from verifier.prose.schema import Result
    path = Path(__file__).resolve().parents[1] / "schema-004f.prose-plan.v1.json"
    assert json.loads(path.read_text()) == Result.model_json_schema()


def test_simulated_model_evaluation_does_not_duplicate_usage_on_empty_input(tmp_path, monkeypatch):
    import httpx
    from claim_analysis.gemini import GeminiProvider, ModelSettings
    from verifier.policy import digest
    from tests_prose.support import reply

    positive = next(c for c in load("dev") if c.expected_bounded_accounting)
    empty = positive.model_copy(update={"case_id": "eg004f-9999", "text": "", "source_sha256": digest(""), "gold": (), "expected_bounded_accounting": False})
    monkeypatch.setattr("verifier.prose.cli.load", lambda *a, **kw: [positive, empty])

    async def transport(_):
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": reply([positive.text])}]}}],
                                        "usageMetadata": {"promptTokenCount": 100, "totalTokenCount": 150}})

    provider = GeminiProvider(ModelSettings(model="gemini-offline-test", max_requests=2,
        input_usd_per_million=1.0, output_usd_per_million=1.0), "local-test-only", transport=httpx.MockTransport(transport))
    monkeypatch.setattr("verifier.prose.cli.GeminiProvider.from_environment", lambda *_: provider)
    output = tmp_path / "simulated-model.json"
    monkeypatch.setattr("sys.argv", ["prose", "evaluate", "--engine", "gemini", "--case-ids",
        positive.case_id + "," + empty.case_id, "--max-requests", "2", "--output", str(output)])
    assert main() == 0
    report = json.loads(output.read_text())
    assert report["model_attempts"] == 1 and report["model_measurements"]["observed_calls"] == 1
    assert report["model_measurements"]["input_tokens"] == 100
    assert report["records"][1]["model_call_attempted"] is False
    assert report["records"][1]["provider_measurement"] is None
