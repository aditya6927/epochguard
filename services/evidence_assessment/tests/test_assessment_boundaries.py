import asyncio
import copy
from datetime import datetime
import json

import httpx
import pytest

from evidence_assessment.factory import packet, offline_pipeline
from evidence_assessment.schema import Request
from evidence_assessment.config import Budget, Failure, offline_settings
from evidence_assessment.providers import SEARCH_URL, MODEL_ROOT, SYSTEM, post

TIME = datetime.fromisoformat(packet()['reference_time'])
BASE = next(row for row in packet()['cases'] if row['id'] == 'stable-fact')


@pytest.mark.parametrize('mutation,reason', [
    ('opposite', 'SOURCE_DISAGREEMENT'), ('unclear', 'SOURCE_DISAGREEMENT'),
    ('uncertain', 'INSUFFICIENT_CORROBORATION'), ('one-citation', 'INSUFFICIENT_CORROBORATION'),
    ('wrong-claim', 'INVALID_MODEL_OUTPUT'), ('missing-source', 'INVALID_MODEL_OUTPUT'),
    ('duplicate-source', 'INVALID_MODEL_OUTPUT'), ('blank-quote', 'INVALID_MODEL_OUTPUT')])
def test_model_cannot_bypass_corroboration(mutation, reason):
    row = copy.deepcopy(BASE)
    record = row['model_record']
    if mutation == 'opposite': record['source_assessments'][1]['stance'] = 'CONTRADICTS'
    if mutation == 'unclear': record['source_assessments'][1]['stance'] = 'UNCLEAR'
    if mutation == 'uncertain': record['independence_uncertain'] = True
    if mutation == 'one-citation': record['citation_ids'] = ['S1']
    if mutation == 'wrong-claim': record['claim'] += ' '
    if mutation == 'missing-source': record['source_assessments'].pop()
    if mutation == 'duplicate-source': record['source_assessments'][1]['source_id'] = 'S1'
    if mutation == 'blank-quote': record['source_assessments'][1]['quote'] = ' ' * 20
    pipe = offline_pipeline(row, clock=lambda: TIME)
    result = asyncio.run(pipe.assess(Request(claim=row['claim'])))
    assert result.assessment == 'INSUFFICIENT_EVIDENCE' and result.reason_code == reason
    assert result.authorization is False


def test_actual_outgoing_payloads_use_fixed_endpoints_and_untrusted_data_channel():
    pipe = offline_pipeline(BASE, clock=lambda: TIME)
    seen = []
    search_inner, model_inner = pipe.search._transport, pipe.assessor._transport
    async def search(request):
        assert str(request.url) == SEARCH_URL
        assert request.headers['Authorization'] == 'Bearer offline-fixture-only'
        body = json.loads(request.content)
        assert body == {'query': BASE['claim'], 'max_results': 5, 'search_depth': 'basic', 'topic': 'general',
            'auto_parameters': False, 'include_answer': False, 'include_raw_content': False,
            'include_images': False, 'include_published_date': True}
        seen.append('search')
        return await search_inner.handle_async_request(request)
    async def model(request):
        assert str(request.url) == MODEL_ROOT + pipe.settings.model + ':generateContent'
        assert request.headers['x-goog-api-key'] == 'offline-fixture-only'
        body = json.loads(request.content)
        assert body['systemInstruction']['parts'] == [{'text': SYSTEM}]
        assert not any(k in body for k in ('tools', 'toolConfig', 'cachedContent'))
        assert body['generationConfig']['candidateCount'] == 1
        data = json.loads(body['contents'][0]['parts'][0]['text'])
        assert data['original_claim'] == BASE['claim']
        assert [s['url'] for s in data['untrusted_search_results']] == [s['url'] for s in BASE['results']]
        seen.append('model')
        return await model_inner.handle_async_request(request)
    pipe.search._transport, pipe.assessor._transport = httpx.MockTransport(search), httpx.MockTransport(model)
    result = asyncio.run(pipe.assess(Request(claim=BASE['claim'])))
    assert result.assessment == 'SUPPORTED' and seen == ['search', 'model']


@pytest.mark.parametrize('status', [301, 302, 307, 400, 429, 500])
def test_provider_failure_has_one_attempt_and_no_redirect(status):
    calls = []
    async def handler(request):
        calls.append(str(request.url))
        return httpx.Response(status, headers={'Location': 'https://example.com/other'}, text='untrusted error')
    async def check():
        with pytest.raises(Failure, match='^SEARCH_PROVIDER_ERROR$'):
            await post(SEARCH_URL, {}, {}, 1, httpx.MockTransport(handler), 'SEARCH', 100)
    asyncio.run(check())
    assert calls == [SEARCH_URL]


def test_timeout_and_body_limits_stop_transport_without_retry():
    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})
    async def large(request): return httpx.Response(200, content=b'x' * 101)
    async def check():
        for handler, seconds, reason in ((slow, .01, 'MODEL_TIMEOUT'), (large, 1, 'MODEL_INVALID_RESPONSE')):
            with pytest.raises(Failure, match='^' + reason + '$'):
                await post(MODEL_ROOT + 'gemini-test:generateContent', {}, {}, seconds,
                           httpx.MockTransport(handler), 'MODEL', 100)
    asyncio.run(check())


def test_cost_admission_precedes_any_source_call():
    settings = offline_settings().model_copy(update={'input_usd_per_million': 1000.0, 'max_request_usd': .01})
    pipe = offline_pipeline(BASE, settings=settings, clock=lambda: TIME)
    result = asyncio.run(pipe.assess(Request(claim=BASE['claim'])))
    assert result.reason_code == 'BUDGET_EXHAUSTED' and pipe.search.calls == pipe.assessor.calls == 0


def test_budget_is_atomic_under_concurrent_admission():
    budget = Budget(offline_settings().model_copy(update={'max_requests': 1}))
    async def admit():
        try:
            await budget.admit()
            return True
        except Failure: return False
    async def check(): return await asyncio.gather(*(admit() for _ in range(10)))
    assert sum(asyncio.run(check())) == 1 and budget.requests == 1


def test_live_factory_constructs_real_clients_without_automatic_network(tmp_path, monkeypatch):
    from evidence_assessment.factory import live_pipeline
    settings = tmp_path/'settings.json'
    settings.write_text(offline_settings().model_copy(update={'model':'gemini-test', 'max_requests':1}).model_dump_json())
    gemini, tavily = tmp_path/'gemini.key', tmp_path/'tavily.key'
    gemini.write_text('synthetic-gemini-key-only')
    tavily.write_text('synthetic-tavily-key-only')
    for key in ('GEMINI_API_KEY','TAVILY_API_KEY'): monkeypatch.delenv(key,raising=False)
    for key in ('EPOCHGUARD_005I_ALLOW_GEMINI','EPOCHGUARD_005I_ALLOW_TAVILY'): monkeypatch.setenv(key,'1')
    for key, path in (('SETTINGS_FILE',settings),('GEMINI_SECRET_FILE',gemini),('TAVILY_SECRET_FILE',tavily)):
        monkeypatch.setenv('EPOCHGUARD_005I_'+key,str(path))
    def forbidden(*args, **kwargs): raise AssertionError('startup must be source-free')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    pipe = live_pipeline()
    assert pipe.simulated is False and pipe.search._transport is None and pipe.assessor._transport is None
    assert pipe.search.calls == pipe.assessor.calls == 0
    assert pipe.settings.max_requests == 1
