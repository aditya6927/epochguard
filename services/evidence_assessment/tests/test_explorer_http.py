import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

ROOT=next((p for p in Path(__file__).resolve().parents if (p/'services/claim_analysis').exists()),Path('/app'))
sys.path[:0]=[str(ROOT/'services/evidence_assessment'),str(ROOT/'services/claim_analysis')]
from evidence_assessment.app import create_app,ORIGIN
from evidence_assessment.factory import offline_pipeline

HEADERS={'Origin':ORIGIN,'X-EpochGuard-Explorer':'1'}


def test_actual_asgi_assessment_and_safe_static_ui():
    async def scenario():
        app=create_app(offline_pipeline())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as client:
            for path in ('/','/app.js','/app.css','/health','/api/info'):
                response=await client.get(path)
                assert response.status_code==200 and response.headers['cache-control']=='no-store'
                assert "frame-ancestors 'none'" in response.headers['content-security-policy']
            for claim,wanted in [("Trump is Japan's prime minister.",'CONTRADICTED'),
                ('The chemical symbol for gold is Au.','SUPPORTED'),
                ('A statement with no offline evidence.','INSUFFICIENT_EVIDENCE')]:
                response=await client.post('/api/assess',json={'claim':claim},headers=HEADERS)
                value=response.json()
                assert response.status_code==200 and value['claim']==claim and value['assessment']==wanted
                assert value['mode']=='experimental-evidence' and value['authorization'] is False
                assert not any(name.startswith('x-epochguard-') for name in response.headers)
    asyncio.run(scenario())


@pytest.mark.parametrize('change', ['origin','host','no-origin','no-header','query','route','extra','duplicate','oversized','control'])
def test_refused_requests_never_dispatch_providers(change):
    async def scenario():
        pipeline=offline_pipeline()
        app=create_app(pipeline)
        headers=dict(HEADERS)
        path='/api/assess'
        body=json.dumps({'claim':'The chemical symbol for gold is Au.'}).encode()
        headers['Content-Type']='application/json'
        if change=='origin': headers['Origin']='https://attacker.invalid'
        if change=='host': headers['Host']='attacker.invalid'
        if change=='no-origin': del headers['Origin']
        if change=='no-header': del headers['X-EpochGuard-Explorer']
        if change=='query': path+='?url=https://attacker.invalid'
        if change=='route': path='/v1/verify/prose'
        if change=='extra': body=b'{"claim":"x","endpoint":"https://attacker.invalid"}'
        if change=='duplicate': body=b'{"claim":"x","claim":"y"}'
        if change=='oversized': body=b'x'*4097
        if change=='control': body=b'{"claim":"bad\\u0000text"}'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as client:
            response=await client.post(path,content=body,headers=headers)
            assert response.status_code>=400
            value=response.json()
            assert value['mode']=='experimental-evidence' and value['authorization'] is False
            assert value['claim'] is None and 'detail' not in value
            assert pipeline.search.calls==pipeline.assessor.calls==0
    asyncio.run(scenario())


def test_ui_uses_text_nodes_and_clears_prior_results_on_edits():
    web=Path(__file__).resolve().parents[1]/'evidence_assessment/web'
    if not web.exists(): web=Path('/app/evidence_assessment/web')
    script=(web/'app.js').read_text()
    assert 'innerHTML' not in script and 'textContent' in script
    assert "editor.addEventListener('input', reset)" in script
    assert 'ticket !== generation' in script and 'result.hidden = true' in script
