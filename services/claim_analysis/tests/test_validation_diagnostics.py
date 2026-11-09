import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from claim_analysis.gemini import GeminiProvider, ModelSettings
from claim_analysis.model import AnalysisFailure, FakeProvider, ModelExtractor
from claim_analysis.schema import AnalysisInput, parse_extraction
from claim_analysis.schema_diagnostic import ProbeProvider, generation_schemas, probe
from claim_analysis.validation_diagnostics import BindingFailure, Code, Issue, Stage, safe_path, schema_details
from wire_helpers import identification

SECRET = "PRIVATE_CANDIDATE_API_KEY_PROVIDER_MESSAGE"


def request():
    return AnalysisInput(text=SECRET, reference_date="2026-11-08")


def record():
    return {"schema_version":"004a.v1", "claims":[{
        "claim_id":"c001", "source_text":SECRET, "start":0, "end":len(SECRET),
        "normalized_proposition":None,"factuality":"FACTUAL","temporal":"DYNAMIC",
        "fresh_evidence":"REQUIRED","uncertainty":[],"temporal_reference":None}]}


def failure(raw, source=None):
    with pytest.raises(AnalysisFailure) as caught:
        asyncio.run(ModelExtractor(FakeProvider(raw)).analyze(source or request()))
    error = caught.value
    metadata = error.diagnostic.to_dict()
    assert SECRET not in json.dumps(metadata) + str(error) + repr(error.diagnostic)
    assert not {"input","msg","ctx","url","message"} & metadata.keys()
    return error, metadata


@pytest.mark.parametrize("change,code,path", [
    ({"start":1},"BINDING_TEXT_MISMATCH","$.claims[0].source_text"),
    ({"end":999},"BINDING_RANGE","$.claims[0].end"),
    ({"claim_id":"c002"},"BINDING_ID_SEQUENCE","$.claims[0].claim_id"),
])
def test_source_binding_failure_is_identified_without_source_text(change,code,path):
    value = record()
    value["claims"][0].update(change)
    # Canonical binding still rejects bad offsets; the model now never supplies
    # them. Keep this canonical regression rather than accepting legacy output.
    with pytest.raises(BindingFailure) as caught:
        parse_extraction(json.dumps(value),request())
    assert caught.value.code == code
    assert safe_path(caught.value.location) == path


def test_overlap_is_rejected_not_repaired():
    value = record()
    value["claims"].append({**value["claims"][0],"claim_id":"c002"})
    with pytest.raises(BindingFailure) as caught:
        parse_extraction(json.dumps(value),request())
    assert caught.value.code == Code.BINDING_OVERLAP


@pytest.mark.parametrize("change,code,path", [
    ({"temporal":SECRET},"SCHEMA_LITERAL_INVALID","$.claims[0].temporal"),
    ({"fresh_evidence":"NOT_REQUIRED"},"CLAIM_DYNAMIC_REQUIRES_FRESH","$.claims[0].fresh_evidence"),
    ({"source_text":""},"SCHEMA_LIMIT","$.claims[0].source_text"),
    ({"source_text":True},"SCHEMA_TYPE_INVALID","$.claims[0].source_text"),
    ({"factuality":"UNCERTAIN"},"CLAIM_UNCERTAINTY_MISSING","$.claims[0].uncertainty"),
    ({"temporal_reference":"not a source substring"},"CLAIM_REFERENCE_MISMATCH","$.claims[0].temporal_reference"),
    ({"factuality":"NON_FACTUAL"},"CLAIM_NONFACTUAL_COMBINATION","$.claims[0]"),
    ({"temporal":"STABLE"},"CLAIM_NON_DYNAMIC_EVIDENCE","$.claims[0].fresh_evidence"),
])
def test_pydantic_and_cross_field_rules_remain_strict(change,code,path):
    value = identification(record())
    value["claims"][0].update(change)
    error, metadata = failure(json.dumps(value))
    assert str(error) == "INVALID_MODEL_ANALYSIS"
    assert metadata["stage"] == "MODEL_SCHEMA"
    assert metadata["errors"] == [{"code":code,"field_path":path}]


def test_missing_required_field():
    value = identification(record())
    del value["claims"][0]["temporal"]
    _, metadata = failure(json.dumps(value))
    assert metadata["errors"] == [{"code":"SCHEMA_MISSING_FIELD","field_path":"$.claims[0].temporal"}]


def test_untrusted_extra_keys_never_appear_in_paths_or_diagnostic_objects():
    value = identification(record())
    value["claims"][0][SECRET] = SECRET
    _, metadata = failure(json.dumps(value))
    assert metadata["errors"] == [{"code":"SCHEMA_EXTRA_FIELD","field_path":"$.claims[0].<unknown>"}]


@pytest.mark.parametrize("raw,code", [
    ('{"claims":',"JSON_INVALID_OR_INCOMPLETE"),
    ('{"'+SECRET+'":0,"'+SECRET+'":1}',"JSON_DUPLICATE_KEY"),
    ('{"n":NaN}',"JSON_NONFINITE_NUMBER"),
    ('\ud800',"JSON_INVALID_ENCODING"),
    ('x'*65537,"OUTPUT_TOO_LARGE"),
])
def test_json_failures_are_separate_from_pydantic(raw,code):
    error, metadata = failure(raw)
    assert str(error) == "INVALID_MODEL_ANALYSIS"
    assert metadata["stage"] == "MODEL_JSON" and metadata["errors"] == [{"code":code,"field_path":"$"}]


def test_empty_model_analysis_preserves_public_failure():
    error, metadata = failure('{"schema_version":"004a.identification.v1","claims":[]}')
    assert str(error) == "EMPTY_MODEL_ANALYSIS"
    assert metadata["stage"] == "EMPTY_ANALYSIS"
    assert metadata["errors"] == [{"code":"EMPTY_MODEL_ANALYSIS","field_path":"$.claims"}]


def test_error_collection_and_numeric_locations_are_bounded():
    value = {"schema_version":"004a.identification.v1","claims":[{SECRET:SECRET} for _ in range(64)]}
    _, metadata = failure(json.dumps(value))
    assert metadata["error_count"] == 64 and metadata["truncated"] is True
    assert len(metadata["errors"]) == 4
    assert safe_path(("claims",63,"temporal")) == "$.claims[63].temporal"
    for index in [-1,64,10**100]:
        assert safe_path(("claims",index,SECRET)) == "$.claims[*].<unknown>"
    assert len(safe_path((SECRET,)*100)) <= 192
    assert SECRET not in repr(Issue(Code.SCHEMA_INVALID, (SECRET,)))
    assert safe_path((True,)) == "$.<unknown>"


def test_unknown_pydantic_types_messages_context_and_inputs_are_not_copied():
    error = ValidationError.from_exception_data("ignored", [{
        "type":PydanticCustomError(SECRET, SECRET, {"private":SECRET}),
        "loc":("claims",999,SECRET), "input":SECRET}])
    details = schema_details(error)
    assert details.to_dict()["errors"] == [{"code":"SCHEMA_INVALID","field_path":"$.claims[*].<unknown>"}]
    assert SECRET not in repr(details) + json.dumps(details.to_dict())


def settings():
    return ModelSettings(model="gemini-fixture",input_usd_per_million=1.0,output_usd_per_million=2.0)


def envelope(raw=None):
    return {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":raw or json.dumps(identification(record()))}]}}]}


@pytest.mark.parametrize("kind,public,stage,code", [
    ("http","MODEL_PROVIDER_FAILURE","PROVIDER_HTTP","HTTP_FAILURE"),
    ("transport","MODEL_PROVIDER_FAILURE","PROVIDER_TRANSPORT","TRANSPORT_FAILURE"),
    ("timeout","MODEL_TIMEOUT","PROVIDER_TRANSPORT","TIMEOUT"),
    ("envelope_json","MODEL_PROVIDER_FAILURE","PROVIDER_ENVELOPE","JSON_INVALID_OR_INCOMPLETE"),
    ("envelope_shape","MODEL_PROVIDER_FAILURE","PROVIDER_ENVELOPE","ENVELOPE_INVALID"),
    ("envelope_incomplete","MODEL_INCOMPLETE","PROVIDER_ENVELOPE","ENVELOPE_INCOMPLETE"),
    ("envelope_content","MODEL_INVALID_RESPONSE","PROVIDER_ENVELOPE","ENVELOPE_CONTENT_INVALID"),
    ("envelope_usage","MODEL_INVALID_USAGE","PROVIDER_ENVELOPE","ENVELOPE_USAGE_INVALID"),
    ("model_json","INVALID_MODEL_ANALYSIS","MODEL_JSON","JSON_INVALID_OR_INCOMPLETE"),
])
def test_provider_and_local_failure_stages_are_distinct(kind,public,stage,code):
    async def handler(req):
        if kind == "http":
            return httpx.Response(400,json={"error":{"message":SECRET}})
        if kind == "transport":
            raise httpx.ConnectError(SECRET)
        if kind == "timeout":
            raise httpx.ReadTimeout(SECRET)
        if kind == "envelope_json":
            return httpx.Response(200,content=(SECRET+"{").encode())
        body = envelope()
        if kind == "envelope_shape":
            body = {SECRET:SECRET}
        elif kind == "envelope_incomplete":
            body = {"candidates":[]}
        elif kind == "envelope_content":
            body["candidates"][0]["content"]["parts"] = [{"functionCall":{SECRET:SECRET}}]
        elif kind == "envelope_usage":
            body["usageMetadata"] = {"promptTokenCount":SECRET}
        elif kind == "model_json":
            body = envelope(SECRET+"{")
        return httpx.Response(200,json=body)
    provider = GeminiProvider(settings(),SECRET,transport=httpx.MockTransport(handler))
    with pytest.raises(AnalysisFailure) as caught:
        asyncio.run(ModelExtractor(provider).analyze(request()))
    assert str(caught.value) == public
    metadata = caught.value.diagnostic.to_dict()
    assert metadata["stage"] == stage and metadata["errors"][0]["code"] == code
    assert SECRET not in json.dumps(metadata) + str(caught.value)
    assert provider.calls == 1


def test_unexpected_provider_exception_and_builtin_timeout_preserve_public_codes():
    class Broken:
        async def generate(self,*args):
            raise RuntimeError(SECRET)
    class TimedOut:
        async def generate(self,*args):
            raise TimeoutError(SECRET)
    for provider,public in [(Broken(),"INVALID_MODEL_ANALYSIS"),(TimedOut(),"MODEL_TIMEOUT")]:
        with pytest.raises(AnalysisFailure) as caught:
            asyncio.run(ModelExtractor(provider).analyze(request()))
        assert str(caught.value) == public
        assert caught.value.diagnostic.stage == Stage.PROVIDER_TRANSPORT
        assert SECRET not in repr(caught.value.diagnostic)


@pytest.mark.parametrize("invalid", [False,True])
def test_probe_report_keeps_http_and_strict_results_and_adds_safe_details(invalid):
    text = "The stock is available."
    value = identification(record())
    value["claims"][0].update(source_text=text)
    if invalid:
        value["claims"][0]["source_text"] = "not in the original response"
    class Observed(httpx.AsyncBaseTransport):
        status = None
        async def handle_async_request(self,req):
            self.status = 200
            return httpx.Response(200,json=envelope(json.dumps(value)))
    provider = ProbeProvider(settings(),SECRET)
    rows = asyncio.run(probe(provider,generation_schemas(),["no_max_items"],transport_factory=Observed))
    row = rows[0]
    assert row["http_accepted"] is True and row["http_status"] == 200
    assert row["strict_analysis_valid"] is (not invalid)
    if invalid:
        assert row["failure_code"] == "INVALID_MODEL_ANALYSIS"
        assert row["failure_details"]["stage"] == "ALIGNMENT"
        assert row["failure_details"]["errors"][0]["code"] == "ALIGNMENT_TEXT_NOT_FOUND"
    else:
        assert row["failure_code"] is None and row["failure_details"] is None
    assert SECRET not in json.dumps(row) and text not in json.dumps(row)


def test_valid_analysis_is_unchanged_and_diagnostics_do_not_authorize():
    expected = record()
    result, _ = asyncio.run(ModelExtractor(FakeProvider(json.dumps(identification(expected)))).analyze(request()))
    assert result.model_dump() == expected
    assert "diagnostic" not in result.model_dump() and "authorization" not in result.model_dump()
