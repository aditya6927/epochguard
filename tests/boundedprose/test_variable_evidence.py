"""005H parser/pipeline and immutable-fixture regressions; gateway run is separate."""
import asyncio
from dataclasses import FrozenInstanceError, asdict
import json
import sys
from pathlib import Path

import httpx
import pytest
from verifier.bounded_prose.contract import Request
from verifier.bounded_prose.grammar import parse
from verifier.policy import primary_label, MissingLabel
from verifier.multiclaim.policies import pypi_version

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from boundedprose.variable_fixture import fixture_app, read_profile
from boundedprose.variable_matrix import PAIRS, Profile, profiles, cases, sha, validate


def test_four_pairs_change_each_policy_independently_and_cover_nine_forms():
    assert len(PAIRS)==4 and len({(p, q) for _,p,q in PAIRS})==4
    assert PAIRS[0][2]==PAIRS[1][2] and PAIRS[0][1]!=PAIRS[1][1]
    assert PAIRS[1][1]==PAIRS[2][1] and PAIRS[1][2]!=PAIRS[2][2]
    assert all(p!='3.15.2' and q!='2.34.2' for _,p,q in PAIRS)
    assert len(profiles())==21 and sum(len(cases(p)) for p in profiles())==90
    for profile in profiles()[:4]:
        supported=cases(profile)[:9]
        assert len(supported)==9
        assert all(parse(c.text)[1]=='BOUNDED_GRAMMAR' for c in supported)
    lower,python_only,pypi_only=profiles()[:3]
    assert cases(lower)[9].text==next(c.text for c in cases(python_only) if c.name=='older-python')
    assert cases(python_only)[9].text==next(c.text for c in cases(pypi_only) if c.name=='older-pypi')


@pytest.mark.parametrize('profile,case',[(p,c) for p in profiles() for c in cases(p) if c.route!='ingress-unsafe'],
                         ids=lambda value: value.name)
def test_supplied_values_drive_actual_python_policy(profile,case):
    app=fixture_app(profile)
    pipeline=app.state.pipeline
    result=asyncio.run(pipeline.verify(Request(request_id='offline_005h',candidate=case.text,candidate_sha256=sha(case.text.encode()))))
    report=pipeline.report()
    assert report['source_invocations']=={'python':case.sources[0],'pypi':case.sources[1]}
    if not case.reasons:
        assert result.coverage=='UNCERTAIN' and result.mappings==[] and result.verification is None
    else:
        assert result.coverage=='COMPLETE'
        assert [c.reason_code for c in result.verification.claims]==list(case.reasons)
        expected='CONTRADICTED' if case.outcome=='REJECT' else 'INSUFFICIENT' if profile.mode=='negative' else 'SUPPORTED'
        assert result.verification.verdict==expected
        for claim in result.verification.claims:
            for evidence in claim.evidence:
                assert evidence.retrieval_mode=='fixture'
                assert evidence.observed_version==(profile.python if claim.claim.policy_id.startswith('python-') else profile.pypi)


def test_parallel_instances_do_not_share_values_or_controls():
    async def scenario():
        one,two=profiles()[:2]
        apps=[fixture_app(one),fixture_app(two)]
        async def invoke(app,profile):
            text=cases(profile)[0].text
            return await app.state.pipeline.verify(Request(request_id=profile.name,candidate=text,candidate_sha256=sha(text.encode())))
        results=await asyncio.gather(*(invoke(app,p) for app,p in zip(apps,[one,two])))
        assert [r.verification.claims[0].evidence[0].observed_version for r in results]==[one.python,two.python]
        assert all(app.state.pipeline.report()['source_invocations']=={'python':1,'pypi':0} for app in apps)
        for app in apps:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://offline') as client:
                assert (await client.post('/test/control',json={'python':'3.15.2'})).status_code==404
    asyncio.run(scenario())


def test_configuration_is_frozen_closed_and_bounded(tmp_path):
    profile=profiles()[0]
    with pytest.raises(FrozenInstanceError): profile.python='3.15.2'
    path=tmp_path/'profile.json'
    path.write_text(json.dumps(asdict(profile)))
    assert read_profile(path)==profile
    for value in [dict(asdict(profile),python='3.15.2'),dict(asdict(profile),url='https://attacker.invalid/')]:
        path.write_text(json.dumps(value))
        with pytest.raises((ValueError,TypeError)): read_profile(path)
    path.write_bytes(b'x'*1025)
    with pytest.raises(ValueError): read_profile(path)


@pytest.mark.parametrize('version',['3.01.2','4.0.1','3.100.1','3.1.1000','3.0.1rc1'])
def test_existing_python_label_parser_rejects_invalid_versions(version):
    with pytest.raises(MissingLabel):
        primary_label(f'Python Releases for Windows\nLatest Python 3 Release - Python {version}\nStable Releases\n')


@pytest.mark.parametrize('version',['00.0.1','0.0.1rc1',1,'1000.0.1'])
def test_existing_pypi_parser_rejects_invalid_versions(version):
    with pytest.raises(ValueError):
        pypi_version(json.dumps({'info':{'name':'requests','yanked':False,'version':version}}))


def test_measured_denominator_cannot_be_fabricated():
    with pytest.raises((ValueError,KeyError)):
        validate(profiles()[0],{'cases':[]},{'fixture':True,'simulated_transports':True,'active':0,'profile':'lower'})
