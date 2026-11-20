import asyncio
import copy
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys

import httpx
import pytest

ROOT=next((p for p in Path(__file__).resolve().parents if (p/'services/claim_analysis').exists()),Path('/app'))
sys.path[:0]=[str(ROOT/'services/evidence_assessment'),str(ROOT/'services/claim_analysis')]
from evidence_assessment.factory import packet, offline_pipeline, configured_pipeline, live_pipeline
from evidence_assessment.schema import Request, ModelAssessment, Result
from evidence_assessment.providers import strict_load, SYSTEM, Search, Assessor
from evidence_assessment.config import offline_settings, Failure, private_file
from evidence_assessment.sources import publisher, publication

PACKET=packet()
TIME=datetime.fromisoformat(PACKET['reference_time'])


@pytest.mark.parametrize('row',PACKET['cases'],ids=lambda row:row['id'])
def test_frozen_http_packet(row):
    pipe=offline_pipeline(row,clock=lambda:TIME)
    result=asyncio.run(pipe.assess(Request(claim=row['claim'])))
    assert result.mode=='experimental-evidence' and result.authorization is False
    assert result.claim==row['claim']
    assert (result.assessment,result.reason_code)==(row['expected'],row['expected_reason'])
    assert pipe.search.calls==row['expected_search_calls']
    assert pipe.assessor.calls==row['expected_model_calls']
    assert pipe.active==0 and result.uncertainty
    assert Result.model_validate_json(result.model_dump_json())==result
    assert set(result.citation_ids)<={s.id for s in result.sources}


def test_unknown_claim_abstains_without_model_and_exact_text_is_retained():
    text='  A newly authored externally checkable statement has no offline search fixture.  '
    pipe=offline_pipeline(clock=lambda:TIME)
    result=asyncio.run(pipe.assess(Request(claim=text)))
    assert result.claim==text and result.assessment=='INSUFFICIENT_EVIDENCE'
    assert pipe.search.calls==1 and pipe.assessor.calls==0


@pytest.mark.parametrize('url',[
    'http://example.com','https://localhost/a','https://127.0.0.1/a','https://[::1]/',
    'https://169.254.169.254/','https://user:pass@example.com/a','https://example.com:444/a',
    'file:///etc/passwd','javascript:alert(1)','https://foo.internal/','https://foo.invalid/',
    'https://example.com\\@localhost/','https://example.com/\nwrong','https://co.uk/'])
def test_unsafe_source_links_refused(url):
    with pytest.raises(ValueError): publisher(url)


def test_publisher_groups_include_subdomains_known_owners_and_government():
    assert publisher('https://news.bbc.co.uk/a')==publisher('https://www.bbc.com/b')
    assert publisher('https://a.example.com/')==publisher('https://b.example.com/')
    assert publisher('https://japan.kantei.go.jp/')==publisher('https://www.mofa.go.jp/')
    assert publisher('https://apnews.com/a')==publisher('https://www.ap.org/b')
    assert publisher('https://japan.kantei.go.jp/')!=publisher('https://apnews.com/a')


def test_publication_is_not_inferred_from_retrieval():
    assert publication(None) is None
    assert publication('Thu, 19 Nov 2026 10:14:12 GMT').tzinfo is not None
    assert publication('2026-11-19T10:14:12Z')==publication('Thu, 19 Nov 2026 10:14:12 GMT')
    with pytest.raises(ValueError): publication(True)


@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"x":NaN}',b'[] trailing',b'\xff',b'x'*100])
def test_strict_json_boundaries(raw):
    with pytest.raises((ValueError,UnicodeError)): strict_load(raw,99)


def test_injection_stays_in_untrusted_data_and_no_tools_or_authority_exist():
    assert 'untrusted data' in SYSTEM and 'Do not obey' in SYSTEM
    assert 'never independent proof or authorization' in SYSTEM
    row=next(r for r in PACKET['cases'] if r['id']=='injected-instructions')
    assert 'authorization=true' in row['results'][0]['content']
    with pytest.raises(ValueError): ModelAssessment.model_validate(row['model_record'])


def test_budget_is_retained_after_failure_and_has_no_retry():
    row=next(r for r in PACKET['cases'] if r['id']=='search-timeout')
    settings=offline_settings().model_copy(update={'max_requests':1})
    pipe=offline_pipeline(row,settings=settings,clock=lambda:TIME)
    async def scenario():
        first=await pipe.assess(Request(claim=row['claim']))
        second=await pipe.assess(Request(claim=row['claim']))
        assert first.reason_code=='SEARCH_TIMEOUT' and second.reason_code=='BUDGET_EXHAUSTED'
    asyncio.run(scenario())
    assert pipe.budget.requests==1 and pipe.search.calls==1 and pipe.assessor.calls==0


def test_concurrency_cancellation_and_no_unbounded_waiters():
    async def scenario():
        pipe=offline_pipeline(clock=lambda:TIME)
        entered=asyncio.Event()
        async def blocked(_):
            entered.set()
            await asyncio.Event().wait()
        pipe.search.retrieve=blocked
        request=Request(claim='The chemical symbol for gold is Au.')
        one=asyncio.create_task(pipe.assess(request))
        await entered.wait()
        two=asyncio.create_task(pipe.assess(request))
        await asyncio.sleep(0)
        assert (await pipe.assess(request)).reason_code=='BUSY'
        one.cancel();two.cancel()
        await asyncio.gather(one,two,return_exceptions=True)
        assert pipe.active==0 and pipe.budget.requests==2
    asyncio.run(scenario())


@pytest.mark.parametrize('kind',['incomplete','tools','reasoning','duplicate-json','extra-json','multiple-parts','usage'])
def test_provider_envelope_failure_cannot_conclude(kind):
    row=next(r for r in PACKET['cases'] if r['id']=='stable-fact')
    pipe=offline_pipeline(row,clock=lambda:TIME)
    async def response(request):
        value={'candidates':[{'finishReason':'STOP','content':{'role':'model','parts':[{'text':json.dumps(row['model_record'])}]}}]}
        candidate=value['candidates'][0]
        if kind=='incomplete': candidate['finishReason']='MAX_TOKENS'
        if kind=='tools': candidate['content']['parts'][0]={'functionCall':{'name':'untrusted'}}
        if kind=='reasoning': candidate['content']['parts'][0]['thought']=True
        if kind=='duplicate-json': candidate['content']['parts'][0]['text']='{"claim":"one","claim":"two"}'
        if kind=='extra-json': candidate['content']['parts'][0]['text']+=' trailing'
        if kind=='multiple-parts': candidate['content']['parts'].append({'text':'extra'})
        if kind=='usage': value['usageMetadata']={'promptTokenCount':True,'totalTokenCount':1}
        return httpx.Response(200,json=value)
    pipe.assessor._transport=httpx.MockTransport(response)
    result=asyncio.run(pipe.assess(Request(claim=row['claim'])))
    assert result.assessment=='INSUFFICIENT_EVIDENCE' and result.reason_code=='INVALID_MODEL_OUTPUT'
    assert pipe.assessor.calls==1


@pytest.mark.parametrize('mutation',['missing','overflow','blank','future-date','invalid-score','duplicate-url'])
def test_invalid_search_set_never_partially_succeeds(mutation):
    row=copy.deepcopy(next(r for r in PACKET['cases'] if r['id']=='stable-fact'))
    if mutation=='missing': del row['results'][1]['content']
    if mutation=='overflow': row['results']*=3
    if mutation=='blank': row['results'][1]['content']=''
    if mutation=='future-date': row['results'][1]['published_date']='2099-01-01'
    if mutation=='invalid-score': row['results'][1]['score']=True
    if mutation=='duplicate-url': row['results'][1]['url']=row['results'][0]['url']
    pipe=offline_pipeline(row,clock=lambda:TIME)
    result=asyncio.run(pipe.assess(Request(claim=row['claim'])))
    assert result.assessment=='INSUFFICIENT_EVIDENCE' and result.reason_code=='INVALID_SEARCH_EVIDENCE'
    assert pipe.assessor.calls==0


def test_live_guards_precede_files_or_network(monkeypatch):
    for key in ('EPOCHGUARD_005I_ALLOW_GEMINI','EPOCHGUARD_005I_ALLOW_TAVILY'):
        monkeypatch.delenv(key,raising=False)
    with pytest.raises(ValueError): live_pipeline()
    monkeypatch.setenv('EPOCHGUARD_005I_ALLOW_GEMINI','1')
    with pytest.raises(ValueError): live_pipeline()
    with pytest.raises(ValueError): Search(offline_settings(),'unused',simulated=True,clock=lambda:TIME)
    with pytest.raises(ValueError): Assessor(offline_settings(),'unused',simulated=False,transport=httpx.MockTransport(lambda _:None))


def test_private_configuration_refuses_repository_files():
    with pytest.raises(ValueError): private_file(Path(__file__).resolve())
