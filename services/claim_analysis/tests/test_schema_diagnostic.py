import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from claim_analysis.gemini import GeminiProvider, ModelSettings, provider_schema
from claim_analysis.model import AnalysisFailure, FakeProvider, ModelExtractor
from claim_analysis.schema import AnalysisInput, Claim, Extraction, parse_extraction
from claim_analysis.schema_diagnostic import canonical, generation_schemas, probe, ProbeProvider, run


def request(text="The stock is available."):
    return AnalysisInput(text=text, reference_date="2026-11-08")


def record():
    text = request().text
    return {"schema_version":"004a.v1", "claims":[{
        "claim_id":"c001", "source_text":text, "start":0, "end":len(text),
        "normalized_proposition":None,"factuality":"FACTUAL","temporal":"DYNAMIC",
        "fresh_evidence":"REQUIRED","uncertainty":[],"temporal_reference":None}]}


def settings(**changes):
    return ModelSettings(model="gemini-fixture",input_usd_per_million=1.0,output_usd_per_million=2.0,
                         max_requests=2,**changes)


def test_original_reproduction_and_minimal_provider_diff():
    strict = Extraction.model_json_schema()
    before = copy.deepcopy(strict)
    schemas = generation_schemas()
    original = schemas["original"]
    assert hashlib.sha256(canonical(original)).hexdigest() == "60c4fc533d2ed73aa922a140282f91fd0e854e34ebb2e230a688a825f17e8130"
    assert original["properties"]["claims"].pop("maxItems") == 64
    assert original["$defs"]["Claim"]["properties"]["uncertainty"].pop("maxItems") == 6
    assert original == schemas["no_max_items"] == provider_schema(strict)
    assert strict == before
    snapshot = Path(__file__).parents[1]/"schema-004a.v1.json"
    assert json.loads(snapshot.read_text()) == strict


def test_incremental_variants_are_independent_diagnostic_only_changes():
    schemas = generation_schemas()
    reduced = schemas["no_max_items"]
    no_numeric = copy.deepcopy(reduced)
    assert no_numeric["$defs"]["Claim"]["properties"]["start"].pop("minimum") == 0
    assert schemas["no_numeric_bounds"] == no_numeric
    nullable = copy.deepcopy(reduced)
    for name in ("normalized_proposition","temporal_reference"):
        prop = nullable["$defs"]["Claim"]["properties"][name]
        assert prop.pop("anyOf") == [{"type":"string"},{"type":"null"}]
        prop["type"] = ["string","null"]
    assert schemas["nullable_type_union"] == nullable
    inlined = copy.deepcopy(reduced)
    claim = inlined.pop("$defs")["Claim"]
    inlined["properties"]["claims"]["items"] = claim
    assert schemas["inline_refs"] == inlined
    assert "title" not in canonical(schemas["no_titles"]).decode()
    assert schemas["no_max_items"] == provider_schema(Extraction.model_json_schema())


def test_local_claim_count_limit_survives_provider_relaxation():
    unit = record()["claims"][0]
    claims = []
    text = " ".join([unit["source_text"]]*65)
    for i in range(65):
        start = i*(len(unit["source_text"])+1)
        claims.append({**unit,"claim_id":f"c{i+1:03d}","start":start,"end":start+len(unit["source_text"])})
    Extraction.model_validate({"schema_version":"004a.v1","claims":claims[:64]}).bind(request(text))
    data = json.dumps({"schema_version":"004a.v1","claims":claims})
    with pytest.raises(ValidationError) as invalid:
        parse_extraction(data,request(text))
    assert any(e["type"] == "too_long" and e["loc"] == ("claims",) for e in invalid.value.errors())
    with pytest.raises(AnalysisFailure, match="INVALID_MODEL_ANALYSIS"):
        asyncio.run(ModelExtractor(FakeProvider(data)).analyze(request(text)))


def test_local_uncertainty_limit_survives_provider_relaxation():
    value = record()["claims"][0]
    reasons = ["MISSING_CONTEXT","AMBIGUOUS_REFERENCE","MIXED_REQUIREMENTS",
               "MODEL_ABSTENTION","BASELINE_HEURISTIC","UNTRUSTED_INSTRUCTION"]
    Claim.model_validate({**value,"uncertainty":reasons})
    with pytest.raises(ValidationError) as invalid:
        Claim.model_validate({**value,"uncertainty":reasons+[reasons[0]]})
    assert any(e["type"] == "too_long" and e["loc"] == ("uncertainty",) for e in invalid.value.errors())


class RecordingMock(httpx.AsyncBaseTransport):
    def __init__(self, status, seen, *, invalid_output=False):
        self.status = None
        self.desired_status, self.seen, self.invalid_output = status, seen, invalid_output

    async def handle_async_request(self, req):
        payload = json.loads(req.content)
        self.seen.append(payload)
        assert req.url.host == "generativelanguage.googleapis.com"
        assert set(req.extensions["timeout"].values()) == {30.0}
        self.status = self.desired_status
        text = '{"claims":[]}' if self.invalid_output else json.dumps(record())
        body = {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":text}]}}]}
        if self.status != 200:
            body = {"error":{"message":"SECRET_KEY_AND_PROVIDER_BODY","status":"INVALID_ARGUMENT"}}
        return httpx.Response(self.status,json=body)


def test_normal_adapter_sends_only_reduced_generation_schema():
    seen = []
    provider = GeminiProvider(settings(),"offline-fixture-key",transport=RecordingMock(200,seen))
    result, _ = asyncio.run(ModelExtractor(provider).analyze(request()))
    assert result.claims[0].source_text == request().text
    generation = seen[0]["generationConfig"]["responseJsonSchema"]
    assert generation == generation_schemas()["no_max_items"]
    assert "maxItems" not in canonical(generation).decode()


def test_probe_exact_original_vs_candidate_shared_budgets_and_no_error_leak():
    provider = ProbeProvider(settings(),"offline-fixture-key")
    seen, statuses = [], iter([400,200])
    def factory():
        return RecordingMock(next(statuses),seen)
    schemas = generation_schemas()
    rows = asyncio.run(probe(provider,schemas,["original","no_max_items"],transport_factory=factory))
    assert [p["generationConfig"]["responseJsonSchema"] for p in seen] == [schemas["original"],schemas["no_max_items"]]
    assert [r["http_status"] for r in rows] == [400,200]
    assert [r["strict_analysis_valid"] for r in rows] == [False,True]
    assert provider.calls == 2 and provider.reserved_usd > 0
    assert "SECRET" not in json.dumps(rows) and "offline-fixture-key" not in json.dumps(rows)
    # No retries or automatic production fallback: the caller selected two probes.
    assert len(seen) == 2
    for payload in seen:
        assert payload["generationConfig"]["candidateCount"] == 1
        assert payload["generationConfig"]["maxOutputTokens"] == 4096


def test_http_acceptance_is_separate_from_valid_analysis():
    provider = ProbeProvider(settings(),"offline-fixture-key")
    rows = asyncio.run(probe(provider,generation_schemas(),["no_max_items"],
                             transport_factory=lambda:RecordingMock(200,[],invalid_output=True)))
    assert rows[0]["http_accepted"] is True and rows[0]["strict_analysis_valid"] is False
    assert rows[0]["failure_code"] == "INVALID_MODEL_ANALYSIS"


@pytest.mark.parametrize("status", [401,403,429,500])
def test_auth_quota_server_failures_stop_further_probes(status):
    seen = []
    provider = ProbeProvider(settings(),"offline-fixture-key")
    rows = asyncio.run(probe(provider,generation_schemas(),["original","no_max_items"],
                             transport_factory=lambda:RecordingMock(status,seen)))
    assert len(rows) == len(seen) == provider.calls == 1


def test_probe_respects_existing_cost_budget_before_dispatch():
    seen = []
    provider = ProbeProvider(settings(max_request_usd=0.000001),"offline-fixture-key")
    rows = asyncio.run(probe(provider,generation_schemas(),["original","no_max_items"],
                             transport_factory=lambda:RecordingMock(200,seen)))
    assert rows[0]["failure_code"] == "MODEL_BUDGET_EXCEEDED"
    assert not seen and provider.calls == 0


def test_offline_export_no_credential_or_model_calls(tmp_path,monkeypatch):
    def forbidden(*args):
        raise AssertionError("offline export read model configuration")
    monkeypatch.setattr(ProbeProvider,"from_environment",forbidden)
    args = SimpleNamespace(output=tmp_path,live=False,variants=["original","no_max_items"],max_requests=2)
    assert asyncio.run(run(args)) == 0
    report = json.loads((tmp_path/"report.json").read_text())
    assert report["mode"] == "offline_export" and report["results"] == []
    assert report["live_qualification_pending"] is True
    assert report["schemas"]["original"]["sha256"] != report["schemas"]["no_max_items"]["sha256"]


def test_live_requires_existing_explicit_optin(tmp_path):
    args = SimpleNamespace(output=tmp_path,live=True,variants=["original","no_max_items"],max_requests=2)
    with pytest.raises(AnalysisFailure,match="MODEL_NOT_ENABLED"):
        asyncio.run(run(args))
    assert not (tmp_path/"report.json").exists()


@pytest.mark.parametrize("variants,budget", [(["original","no_max_items"],1),(["original","original"],2),(["original"],7)])
def test_diagnostic_requires_unique_variants_and_bounded_budget(tmp_path,variants,budget):
    args = SimpleNamespace(output=tmp_path,live=False,variants=variants,max_requests=budget)
    with pytest.raises(ValueError):
        asyncio.run(run(args))
