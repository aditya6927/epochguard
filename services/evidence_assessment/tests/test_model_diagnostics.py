import asyncio
import copy
from datetime import datetime
import json
import logging

import httpx
import pytest

from evidence_assessment.app import create_app, ORIGIN
from evidence_assessment.config import offline_settings
from evidence_assessment.diagnostics import CATEGORIES, LOGGER, ModelDiagnostics, field_paths
from evidence_assessment.factory import packet, offline_pipeline
from evidence_assessment.schema import Request, Result

BASE = next(row for row in packet()['cases'] if row['id']=='stable-fact')
TIME = datetime.fromisoformat(packet()['reference_time'])
LOG_NAME = 'epochguard.experimental.model_validation'
USAGE = {'promptTokenCount':4000,'candidatesTokenCount':800,'thoughtsTokenCount':736,'totalTokenCount':5536}


def envelope(record, finish='STOP'):
    return {'candidates':[{'finishReason':finish,'content':{'role':'model','parts':[{'text':json.dumps(record)}]}}],
            'usageMetadata':dict(USAGE)}


def pipeline(value):
    pipe = offline_pipeline(BASE, clock=lambda:TIME)
    async def model(request): return httpx.Response(200,json=value)
    pipe.assessor._transport = httpx.MockTransport(model)
    return pipe


def events(caplog):
    return [json.loads(record.getMessage()) for record in caplog.records if record.name==LOG_NAME]


@pytest.mark.parametrize('kind,category,path',[
    ('max-tokens','MODEL_FINISH_INCOMPLETE',None),
    ('safety','MODEL_FINISH_INCOMPLETE',None),
    ('envelope','MODEL_ENVELOPE_INVALID',None),
    ('json','MODEL_JSON_INVALID',None),
    ('duplicate-json','MODEL_JSON_INVALID',None),
    ('nonfinite-json','MODEL_JSON_INVALID',None),
    ('json-scalar','MODEL_SCHEMA_INVALID','$'),
    ('schema','MODEL_SCHEMA_INVALID','$.assessment'),
    ('claim','MODEL_CLAIM_MISMATCH','$.claim'),
    ('coverage-missing','MODEL_SOURCE_COVERAGE','$.source_assessments'),
    ('coverage-extra','MODEL_SOURCE_COVERAGE','$.source_assessments'),
    ('coverage-duplicate','MODEL_SOURCE_COVERAGE','$.source_assessments'),
    ('citation-unknown','MODEL_CITATION_BINDING','$.citation_ids'),
    ('citation-duplicate','MODEL_CITATION_BINDING','$.citation_ids'),
    ('quotation','MODEL_QUOTATION_BINDING','$.source_assessments[0].quote'),
    ('quotation-short','MODEL_QUOTATION_BINDING','$.source_assessments[0].quote'),
])
def test_diagnostic_category_retains_fail_closed_response(kind,category,path,caplog):
    value = envelope(copy.deepcopy(BASE['model_record']))
    record = json.loads(value['candidates'][0]['content']['parts'][0]['text'])
    if kind=='max-tokens': value['candidates'][0]['finishReason']='MAX_TOKENS'
    if kind=='safety': value['candidates'][0]['finishReason']='SAFETY'
    if kind=='envelope': value['candidates'][0]['content']['parts'].append({'text':'extra'})
    if kind=='schema': record['assessment']='unexpected'
    if kind=='claim': record['claim']+=' '
    if kind=='coverage-missing': record['source_assessments'].pop()
    if kind=='coverage-extra': record['source_assessments'].append({'source_id':'S3','stance':'IRRELEVANT','quote':''})
    if kind=='coverage-duplicate': record['source_assessments'][1]['source_id']='S1'
    if kind=='citation-unknown': record['citation_ids']=['S1','S3']
    if kind=='citation-duplicate': record['citation_ids']=['S1','S1']
    if kind=='quotation': record['source_assessments'][0]['quote']='A paraphrase never found verbatim in the supplied evidence.'
    if kind=='quotation-short': record['source_assessments'][0]['quote']=BASE['results'][0]['content'][:19]
    text=json.dumps(record)
    if kind=='json': text='{"claim":'
    if kind=='duplicate-json': text='{"claim":"first","claim":"second"}'
    if kind=='nonfinite-json': text='{"claim":NaN}'
    if kind=='json-scalar': text='42'
    value['candidates'][0]['content']['parts'][0]['text']=text
    pipe=pipeline(value)
    result=asyncio.run(pipe.assess(Request(claim=BASE['claim'])))
    assert result.reason_code==category and result.assessment=='INSUFFICIENT_EVIDENCE'
    assert result.authorization is False and result.claim==BASE['claim']
    assert Result.model_validate_json(result.model_dump_json())==result
    assert pipe.search.calls==pipe.assessor.calls==1 and pipe.budget.requests==1 and pipe.active==0
    logged=events(caplog)
    assert len(logged)==1 and logged[0]['category']==category
    assert logged[0]['token_counts']==USAGE and logged[0]['max_output_tokens']==1536
    assert logged[0]['source_count']==2
    if path is not None: assert path in logged[0]['validation_fields']
    assert logged[0]['finish_reason']=={'max-tokens':'MAX_TOKENS','safety':'SAFETY'}.get(kind,'STOP')


@pytest.mark.parametrize('location',['unknown-finish','extra-field','schema-value','inner-json'])
def test_diagnostic_logs_never_contain_inputs_secrets_or_provider_values(location,caplog):
    row=copy.deepcopy(BASE)
    row['claim']='PRIVATE_CLAIM_SENTINEL is an offline test assertion.'
    row['model_record']['claim']=row['claim']
    row['results'][0]['content']+=' PRIVATE_SNIPPET_SENTINEL'
    record=row['model_record']
    secret='PRIVATE_API_KEY_SENTINEL'
    value=envelope(record)
    if location=='unknown-finish': value['candidates'][0]['finishReason']='PRIVATE_FINISH_SENTINEL'
    if location=='extra-field': record['PRIVATE_FIELD_SENTINEL']=secret
    if location=='schema-value': record['assessment']=secret
    text=json.dumps(record)
    if location=='inner-json': text='PRIVATE_RAW_MODEL_SENTINEL'+secret
    value['candidates'][0]['content']['parts'][0]['text']=text
    value['usageMetadata']['PRIVATE_USAGE_FIELD']=secret
    pipe=offline_pipeline(row,clock=lambda:TIME)
    pipe.assessor._key=secret
    async def model(request):
        assert request.headers['x-goog-api-key']==secret
        return httpx.Response(200,json=value)
    pipe.assessor._transport=httpx.MockTransport(model)
    result=asyncio.run(pipe.assess(Request(claim=row['claim'])))
    assert result.assessment=='INSUFFICIENT_EVIDENCE'
    logged=events(caplog)
    assert len(logged)==1
    raw=json.dumps(logged)
    assert 'PRIVATE_' not in raw and row['claim'] not in raw
    assert all(source['content'] not in raw for source in row['results'])
    if location=='unknown-finish': assert logged[0]['finish_reason']=='UNKNOWN'
    if location=='extra-field': assert logged[0]['validation_fields']==['$.[unknown]']
    for log in caplog.records:
        if log.name==LOG_NAME: assert log.exc_info is None and log.stack_info is None


def test_token_and_field_metadata_are_bounded_allowlists():
    value=envelope({})
    value['usageMetadata']={'promptTokenCount':True,'candidatesTokenCount':-1,'thoughtsTokenCount':1.5,
                            'totalTokenCount':2**80,'cachedContentTokenCount':12,'arbitrary':'untrusted'}
    event=ModelDiagnostics.capture(value,1536,5)
    assert dict(event.token_counts)=={'cachedContentTokenCount':12}
    paths=field_paths((('source_assessments',999,'private field'),)*100)
    assert paths==['$.source_assessments[index].[unknown]']
    assert len(field_paths((('private'+str(i),i) for i in range(100))))<=8


def test_success_has_no_failure_log_and_identical_public_schema(caplog):
    pipe=pipeline(envelope(BASE['model_record']))
    result=asyncio.run(pipe.assess(Request(claim=BASE['claim'])))
    assert result.assessment=='SUPPORTED' and result.authorization is False and not events(caplog)
    assert set(json.loads(result.model_dump_json()))==set(Result.model_fields)


def test_log_sink_failure_cannot_change_refusal(monkeypatch):
    def broken(*args,**kwargs): raise RuntimeError('private sink details')
    monkeypatch.setattr(LOGGER,'warning',broken)
    pipe=pipeline(envelope(BASE['model_record'],'MAX_TOKENS'))
    result=asyncio.run(pipe.assess(Request(claim=BASE['claim'])))
    assert result.reason_code=='MODEL_FINISH_INCOMPLETE' and result.authorization is False


def test_concurrent_responses_keep_their_own_diagnostics(caplog):
    pipe=offline_pipeline(BASE,clock=lambda:TIME)
    entered=0
    both=asyncio.Event()
    async def model(request):
        nonlocal entered
        entered+=1
        index=entered
        if entered==2: both.set()
        await both.wait()
        value=envelope(BASE['model_record'],'MAX_TOKENS' if index==1 else 'STOP')
        value['usageMetadata']['thoughtsTokenCount']=index*100
        if index==2: value['candidates'][0]['content']['parts'][0]['text']='invalid-json'
        return httpx.Response(200,json=value)
    pipe.assessor._transport=httpx.MockTransport(model)
    async def check(): return await asyncio.gather(*(pipe.assess(Request(claim=BASE['claim'])) for _ in range(2)))
    results=asyncio.run(check())
    assert {result.reason_code for result in results}=={'MODEL_FINISH_INCOMPLETE','MODEL_JSON_INVALID'}
    observed={event['category']:event for event in events(caplog)}
    assert observed['MODEL_FINISH_INCOMPLETE']['token_counts']['thoughtsTokenCount']==100
    assert observed['MODEL_JSON_INVALID']['token_counts']['thoughtsTokenCount']==200


def test_http_response_exposes_category_but_no_diagnostic_envelope(caplog):
    async def check():
        pipe=pipeline(envelope(BASE['model_record'],'MAX_TOKENS'))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(pipe)),base_url=ORIGIN) as client:
            response=await client.post('/api/assess',json={'claim':BASE['claim']},
                headers={'Origin':ORIGIN,'X-EpochGuard-Explorer':'1'})
            assert response.status_code==200
            value=response.json()
            assert set(value)==set(Result.model_fields)
            assert value['reason_code']=='MODEL_FINISH_INCOMPLETE' and value['authorization'] is False
            assert value['assessment']=='INSUFFICIENT_EVIDENCE'
            assert not any(k in value for k in ('token_counts','finish_reason','validation_fields'))
    asyncio.run(check())
    assert len(events(caplog))==1


@pytest.mark.parametrize('outer',[None,[],{}, {'candidates':[]}, {'candidates':[{},{}]},
    {'candidates':[{'finishReason':'STOP','content':{'role':'model','parts':[]}}]}])
def test_missing_and_ambiguous_envelopes_remain_refused(outer,caplog):
    pipe=pipeline(outer)
    result=asyncio.run(pipe.assess(Request(claim=BASE['claim'])))
    assert result.reason_code=='MODEL_ENVELOPE_INVALID' and result.authorization is False
    assert len(events(caplog))==1


def test_category_allowlist_cannot_reflect_untrusted_text():
    with pytest.raises(ValueError):
        ModelDiagnostics.capture({},1536,2).failure('untrusted error text')
    assert len(CATEGORIES)==8


@pytest.mark.parametrize('fault,expected',[
    ('none','AI_EVIDENCE_ASSESSMENT'),('missing-fifth','MODEL_SOURCE_COVERAGE'),
    ('bad-citation','MODEL_CITATION_BINDING'),('bad-quote','MODEL_QUOTATION_BINDING'),
    ('max-tokens','MODEL_FINISH_INCOMPLETE')])
def test_five_retrieved_sources_need_complete_exact_model_bindings(fault,expected,caplog):
    row=copy.deepcopy(BASE)
    evidence=[
        ('https://periodic-table.rsc.org/element/79/gold',
         'Gold is the element represented by the chemical symbol Au in the periodic table.'),
        ('https://www.britannica.com/science/gold-chemical-element',
         'The Latin name aurum gives gold its internationally used symbol, Au.'),
        ('https://iupac.org/what-we-do/periodic-table-of-elements/',
         'An element entry for atomic number 79 identifies Au as gold.'),
        ('https://www.acs.org/education/whatischemistry/periodictable.html',
         'The precious yellow metal gold has Au as its two-letter element symbol.'),
        ('https://www.webelements.com/gold/',
         'Element 79: Gold. The chemical notation for this element is Au.')]
    # Authored offline excerpts, not observations of these public pages.
    row['results']=[{'url':url,'title':'Synthetic chemistry excerpt','content':text} for url,text in evidence]
    record=row['model_record']
    record['source_assessments']=[{'source_id':f'S{i}','stance':'SUPPORTS','quote':text}
                                 for i,(_,text) in enumerate(evidence,1)]
    record['citation_ids']=[f'S{i}' for i in range(1,6)]
    if fault=='missing-fifth': record['source_assessments'].pop()
    if fault=='bad-citation': record['citation_ids'][-1]='S6'
    if fault=='bad-quote': record['source_assessments'][4]['quote']='A mismatched quotation not found in the supplied excerpt.'
    pipe=offline_pipeline(row,clock=lambda:TIME)
    if fault=='max-tokens':
        async def model(request): return httpx.Response(200,json=envelope(record,'MAX_TOKENS'))
        pipe.assessor._transport=httpx.MockTransport(model)
    result=asyncio.run(pipe.assess(Request(claim=row['claim'])))
    assert result.reason_code==expected and result.authorization is False and len(result.sources)==5
    assert result.assessment==('SUPPORTED' if fault=='none' else 'INSUFFICIENT_EVIDENCE')
    assert pipe.assessor.calls==1 and pipe.search.calls==1
    if fault=='none': assert not events(caplog)
    else:
        logged=events(caplog)
        assert len(logged)==1 and logged[0]['source_count']==5
