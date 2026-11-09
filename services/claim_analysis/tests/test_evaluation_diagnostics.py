import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from claim_analysis import cli
from claim_analysis.dataset import DATA, load
from claim_analysis.model import AnalysisFailure


def evaluate_one(tmp_path, reply, *, case=None):
    case = case or load(DATA/"dev.jsonl")[0]
    dataset = tmp_path/"one.jsonl"
    dataset.write_text(case.model_dump_json()+"\n",encoding="utf-8")
    fixture = tmp_path/"fake.jsonl"
    fixture.write_text(json.dumps({"case_id":case.case_id,"reply":reply})+"\n",encoding="utf-8")
    output = tmp_path/"report.json"
    args = SimpleNamespace(dataset=dataset,split=case.split,require_human_reviewed=False,
                           engine="fake",fake_replies=fixture,max_requests=1,output=output)
    assert asyncio.run(cli.evaluate(args)) == 0
    return json.loads(output.read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind,stage,code,path", [
    ("json","MODEL_JSON","JSON_INVALID_OR_INCOMPLETE","$"),
    ("schema","MODEL_SCHEMA","SCHEMA_MISSING_FIELD","$.claims[0].temporal"),
    ("binding","SOURCE_BINDING","BINDING_RANGE","$.claims[0].end"),
])
def test_evaluation_serializes_existing_safe_details_and_preserves_scoring(tmp_path,kind,stage,code,path,capsys):
    case = load(DATA/"dev.jsonl")[0]
    value = copy.deepcopy(case.gold.model_dump())
    if kind == "schema":
        del value["claims"][0]["temporal"]
    elif kind == "binding":
        value["claims"][0]["end"] = len(case.text)+1
    raw = '{"claims":' if kind == "json" else json.dumps(value)
    report = evaluate_one(tmp_path,raw)
    record = report["records"][0]
    assert report["report_schema"] == "004a.evaluation.v1"
    assert record["reason"] == "INVALID_MODEL_ANALYSIS" and record["status"] == "ANALYSIS_FAILED"
    assert record["extraction"] is None
    assert record["failure_details"] == {"stage":stage,"errors":[{"code":code,"field_path":path}],
                                         "error_count":1,"truncated":False}
    # Failed analyses still contribute all factual omissions, unchanged.
    metric = report["metrics"]["all"]
    assert metric["analysis_failures_or_invalid_outcomes"] == 1
    assert metric["claim"] == {"precision":None,"recall":0.0,"f1":0.0,"matched":0,"predicted":0,"gold":2}
    assert metric["fresh_evidence"]["recall"] == 0.0
    assert metric["critical_misses"]["omitted"] == 1
    assert case.text not in json.dumps(record) + capsys.readouterr().out


def test_successful_evaluation_keeps_extraction_and_metrics_with_null_details(tmp_path):
    case = load(DATA/"dev.jsonl")[0]
    report = evaluate_one(tmp_path,case.gold.model_dump_json())
    record = report["records"][0]
    assert record["status"] == "ANALYZED" and record["reason"] is None
    assert record["failure_details"] is None and record["extraction"] == case.gold.model_dump()
    metrics = report["metrics"]["all"]
    assert metrics["analysis_failures_or_invalid_outcomes"] == 0
    assert metrics["claim"]["precision"] == metrics["claim"]["recall"] == metrics["claim"]["f1"] == 1
    assert metrics["fresh_evidence"]["recall"] == 1
    assert metrics["critical_misses"]["omitted"] == 0


def test_failure_without_diagnostic_metadata_is_null(tmp_path,monkeypatch):
    async def no_metadata(self,*args):
        raise AnalysisFailure("INVALID_MODEL_ANALYSIS")
    monkeypatch.setattr(cli.ModelExtractor,"analyze",no_metadata)
    report = evaluate_one(tmp_path,"{}")
    record = report["records"][0]
    assert record["reason"] == "INVALID_MODEL_ANALYSIS"
    assert record["failure_details"] is None and record["extraction"] is None


def test_evaluation_unknown_fields_values_and_error_count_are_sanitized(tmp_path,capsys):
    secret = "PRIVATE_CANDIDATE_MODEL_OUTPUT_API_KEY_PROVIDER_BODY"
    report = evaluate_one(tmp_path,json.dumps({"schema_version":"004a.v1","claims":[{secret:secret} for _ in range(64)]}))
    record = report["records"][0]
    details = record["failure_details"]
    assert details["stage"] == "MODEL_SCHEMA"
    assert details["error_count"] == 64 and details["truncated"] is True
    assert len(details["errors"]) == 4
    assert secret not in json.dumps(record) + capsys.readouterr().out
    report = evaluate_one(tmp_path,json.dumps({"schema_version":"004a.v1","claims":[],secret:secret}))
    assert report["records"][0]["failure_details"]["errors"] == [{"code":"SCHEMA_EXTRA_FIELD","field_path":"$.<unknown>"}]
    assert secret not in json.dumps(report["records"][0])


def test_invalid_input_records_have_null_details(tmp_path):
    invalid = next(case for case in load(DATA/"heldout.jsonl") if case.expected_outcome == "INVALID_INPUT")
    report = evaluate_one(tmp_path,"{}",case=invalid)
    record = report["records"][0]
    assert record["status"] == "INVALID_INPUT" and record["reason"] == "INVALID_INPUT"
    assert record["failure_details"] is None


def test_details_do_not_leak_between_requested_development_cases(tmp_path):
    ids = {"eg004a-0001","eg004a-0007","eg004a-0019"}
    cases = [case for case in load(DATA/"dev.jsonl") if case.case_id in ids]
    assert len(cases) == 3
    dataset,fixture,output = tmp_path/"three.jsonl",tmp_path/"replies.jsonl",tmp_path/"report.json"
    dataset.write_text("".join(case.model_dump_json()+"\n" for case in cases),encoding="utf-8")
    replies = []
    for i,case in enumerate(cases):
        value = copy.deepcopy(case.gold.model_dump())
        if i == 0:
            value["claims"][0]["end"] = len(case.text)+1
        elif i == 1:
            del value["claims"][0]["temporal"]
        replies.append(json.dumps({"case_id":case.case_id,"reply":json.dumps(value)})+"\n")
    fixture.write_text("".join(replies),encoding="utf-8")
    args = SimpleNamespace(dataset=dataset,split="dev",require_human_reviewed=False,
                           engine="fake",fake_replies=fixture,max_requests=3,output=output)
    assert asyncio.run(cli.evaluate(args)) == 0
    records = json.loads(output.read_text(encoding="utf-8"))["records"]
    assert [r["case_id"] for r in records] == [c.case_id for c in cases]
    assert [r["failure_details"]["stage"] if r["failure_details"] else None for r in records] == ["SOURCE_BINDING","MODEL_SCHEMA",None]
    assert [r["status"] for r in records] == ["ANALYSIS_FAILED","ANALYSIS_FAILED","ANALYZED"]
